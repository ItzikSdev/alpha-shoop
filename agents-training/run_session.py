"""
Landing-page training session — orchestrator.

Usage (bounded test, from repo root):
    .venv/bin/python3 agents-training/run_session.py --limit 1

Per reference URL, one full pass: fetch -> structural skeleton (0 site copy
included) -> local qwen3 extracts candidate lessons -> automated sanity
check + RAG semantic dedup (tier 1 of the quality gate) -> build a training
HTML page for a REAL Shopify catalog product, applying prior-promoted +
this session's candidate lessons -> screenshot both the reference page and
the generated page -> ONE Claude-vision critique call (tier 2 of the
quality gate) -> lessons promote into the real store_building_patterns RAG
only if that critique comes back CLEAN, otherwise held pending review.

Everything is written into agents-training/sessions/YYYY-MM-DD/ (SESSION.md
+ output/*.html + screenshots) and logged as one line in CHANGELOG.md.
lessons.md/agents-training/output/ (Step 1 / Step 2-v1) are legacy and are
not read or written by anything below.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pipeline as p


_EXTRACT_SYSTEM = """You are a structural design analyst for e-commerce landing pages.
You will be given a STRUCTURAL OUTLINE of one product page — tag types, CSS
class/id keyword hints, and a content-TYPE classification (e.g. "price-like",
"count-like (stock/reviews)", "countdown-like") for elements that matter.

You are NOT given any of the page's actual text, images, or copy — only its
structure. This is intentional: your job is to describe LAYOUT PATTERNS
(what's placed near what, in what order, how things are grouped) as general,
reusable design principles — never anything specific to one brand's wording.

Output ONLY in this exact format, nothing else:

CATEGORY: <short category name, e.g. "Urgency & Scarcity">
- <one plain-language structural lesson>
- <another, if any>

CATEGORY: <another category, if relevant>
- <lesson>

Use 2-5 categories max. Each lesson must be a general structural observation
(e.g. "a countdown-style element sits directly below the price block" or "the
add-to-cart button repeats both above and below the fold"), never a copied
phrase, never mentioning the brand or site name. If the outline doesn't show
enough signal for a category, omit it — do not invent patterns."""


_BUILD_SYSTEM = """You are a conversion-focused Shopify landing-page builder.
You write ONE self-contained HTML file (inline <style> and <script>, no
external files, no external image hosts other than the ones given to you)
for a single real product.

HARD RULES — violating any of these is a failure:
1. Use ONLY the product facts given to you (title, price, description,
   image URLs). Never invent a price, a review count, a star rating, a
   stock count, or a testimonial that wasn't given to you.
2. No fake urgency ("only 3 left!", countdown timers to a fake deadline,
   "127 people viewing this") unless that exact fact was given to you.
3. Apply the STRUCTURAL patterns you're given (placement/hierarchy/layout
   only) as general design principles — do not copy any wording, image, or
   exact CSS from wherever those patterns came from; they're describing
   structure, not content to reuse.
4. Output ONLY the HTML file, starting with <!doctype html> — no markdown
   fences, no commentary before or after."""


def _domain(url: str) -> str:
    return urlsplit(url).netloc.replace("www.", "")


def _parse_categorized_lessons(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = None
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"CATEGORY:\s*(.+)", line, re.IGNORECASE)
        if m:
            current = m.group(1).strip()
            out.setdefault(current, [])
            continue
        if line.startswith("-") and current:
            out[current].append(line.lstrip("- ").strip())
    return out


async def extract_candidate_lessons(url: str, domain: str, deeper: bool = False) -> tuple[dict[str, list[str]], str]:
    """Fetch + skeleton + local-qwen3 extraction, then the tier-1 automated
    gate (sanity check + RAG semantic dedup) per lesson. Returns
    (category -> surviving lessons, raw model output)."""
    print(f"[fetch] {url}")
    html = await p.fetch_reference_html(url)
    skeleton = p.build_structural_skeleton(html)
    print(f"[skeleton] {len(skeleton.splitlines())} structural nodes extracted (0 chars of site copy included)")

    extra = ""
    if deeper:
        from src.rag.index import search
        prior = await search("store_building_patterns", domain, filters={"source_domain": domain}, top_k=20)
        existing_categories = sorted({h.get("category", "") for h in prior if h.get("category")})
        extra = (
            "\n\nThis site has already been analyzed at least once. Categories already "
            f"promoted from it: {', '.join(existing_categories) or '(none yet)'}. Only report "
            "patterns that are GENUINELY NEW — a different structural aspect not already "
            "captured above. If you find nothing genuinely new, output nothing at all."
        )
    print(f"[llm] extracting {'deeper ' if deeper else ''}structural patterns via local qwen3:14b ...")
    # qwen3 needs far more budget than the visible answer alone would suggest —
    # tested empirically: 1200 truncated to a completely empty response even
    # with /no_think, 3800 produced a clean ~780-token answer. Generous cap
    # here since local compute is free.
    raw = await p.call_local_model(_EXTRACT_SYSTEM, f"STRUCTURAL OUTLINE:\n{skeleton}{extra}", max_tokens=3800)
    categorized = _parse_categorized_lessons(raw)

    survivors: dict[str, list[str]] = {}
    for category, lessons in categorized.items():
        kept = []
        for lesson in lessons:
            lesson = lesson.strip("-* ").strip()
            if not lesson:
                continue
            ok, reason = p.passes_sanity_check(lesson)
            if not ok:
                print(f"    [sanity-reject] {reason}: {lesson[:70]}")
                continue
            if not await p.is_new_lesson_via_rag(lesson):
                print(f"    [rag-dedup] already covered: {lesson[:70]}")
                continue
            kept.append(lesson)
        if kept:
            survivors[category] = kept
    return survivors, raw


async def build_html_for_product(new_lessons: list[str], date_str: str) -> dict:
    """Applies prior-PROMOTED lessons from the real RAG (cumulative
    knowledge) plus this session's fresh candidates (not yet promoted, but
    still worth applying/testing this run) to a real Shopify catalog
    product. Output lands under this session's own output/ folder."""
    from src.rag.index import search
    prior_hits = await search("store_building_patterns", "product page layout structure", top_k=15)
    prior_lessons = [h["text"] for h in prior_hits]
    guidance_lessons = prior_lessons + new_lessons
    guidance_text = ("\n".join(f"- {ls}" for ls in guidance_lessons)
                      if guidance_lessons else "(no patterns learned yet — use general e-commerce best judgment)")

    product = await p.fetch_one_real_product()
    if not product:
        raise RuntimeError("No active product found in the live Shopify catalog — cannot build without real data.")

    price = product.get("priceRangeV2", {}).get("minVariantPrice", {})
    images = [img["url"] for img in product.get("images", {}).get("nodes", [])]
    # Strip a stray ```html / ``` code-fence wrapper some descriptions were saved
    # with in Shopify — a formatting artifact, not part of the actual content.
    description = re.sub(r"^```(?:html)?\s*|\s*```$", "", product.get("description", "").strip())
    product_facts = {
        "title": product["title"],
        "handle": product["handle"],
        "description": description,
        "price": f"{price.get('amount')} {price.get('currencyCode')}".strip(),
        "images": images,
    }

    print(f"[llm] building HTML for real product '{product_facts['title']}' via local qwen3:14b ...")
    user = (
        f"ACCUMULATED STRUCTURAL LESSONS (apply as layout guidance only):\n{guidance_text}\n\n"
        f"REAL PRODUCT DATA (the ONLY facts you may state):\n{json.dumps(product_facts, indent=2)}\n\n"
        "Build the landing page now."
    )
    # Same empty-response risk as extraction — tested at 6000 (2345 completion
    # tokens used, finish_reason=stop, ~2m40s). Local compute is free.
    html = await p.call_local_model(_BUILD_SYSTEM, user, max_tokens=6000)
    html = re.sub(r"^```(?:html)?\n?|```$", "", html.strip(), flags=re.MULTILINE).strip()

    out_dir = p.session_dir(date_str) / "output"
    out_path = out_dir / f"{product_facts['handle']}.html"
    out_path.write_text(html, encoding="utf-8")
    return {"product": product_facts, "output_path": str(out_path), "html_len": len(html)}


async def process_one_url_full(url: str, date_str: str, deeper: bool = False) -> dict:
    """One URL, one full pipeline pass, including the visual-critique quality
    gate. Returns everything needed for that day's SESSION.md."""
    domain = _domain(url)
    candidate_lessons, raw = await extract_candidate_lessons(url, domain, deeper=deeper)
    p.mark_url_processed(url, date_str)

    all_candidates = [ls for lst in candidate_lessons.values() for ls in lst]
    build = await build_html_for_product(all_candidates, date_str)

    out_dir = p.session_dir(date_str) / "output"
    ref_shot = out_dir / f"{domain}-reference.png"
    gen_shot = out_dir / f"{build['product']['handle']}-generated.png"
    print(f"[screenshot] reference ({domain}) and generated ({build['product']['handle']}) ...")
    ref_ok = await p.screenshot_url(url, ref_shot)
    gen_ok = await p.screenshot_local_html(Path(build["output_path"]), gen_shot)

    if ref_ok and gen_ok:
        print("[llm] visual critique via Claude vision (executive tier) ...")
        critique = await p.vision_critique(ref_shot, gen_shot, build["product"]["title"], all_candidates)
    else:
        critique = {
            "critique": f"Visual critique skipped — screenshot failed (reference_ok={ref_ok}, generated_ok={gen_ok}).",
            "verdict": "NEEDS_REVIEW",
        }
    print(f"[critique] verdict={critique['verdict']}")

    promoted: list[str] = []
    held: list[str] = []
    session_path = f"agents-training/sessions/{date_str}/SESSION.md"
    if critique["verdict"] == "CLEAN":
        for category, lessons in candidate_lessons.items():
            for lesson in lessons:
                ok = await p.promote_lesson(category, lesson, date_str, domain, session_path)
                (promoted if ok else held).append(lesson)
    else:
        held = list(all_candidates)

    return {
        "url": url, "domain": domain, "product_title": build["product"]["title"],
        "categorized_lessons": candidate_lessons, "promoted": promoted, "held": held,
        "critique": critique["critique"], "verdict": critique["verdict"],
        "output_path": build["output_path"], "raw_model_output": raw,
    }


def _finalize_session(date_str: str, entries: list[dict]) -> dict:
    """Writes ONE SESSION.md covering every URL processed this calendar day
    plus one CHANGELOG line. Shared by both the bounded-test and daily-job
    entry points so a day never ends up with more than one SESSION.md."""
    if not entries:
        return {"session_path": None, "entries": [], "total_promoted": 0, "total_held": 0, "needs_review": False}
    session_path = p.write_session_md(date_str, entries)
    total_promoted = sum(len(e["promoted"]) for e in entries)
    total_held = sum(len(e["held"]) for e in entries)
    needs_review = any(e["verdict"] != "CLEAN" for e in entries)
    status = "some lesson(s) held pending review" if needs_review else "promoted cleanly"
    p.append_changelog(
        date_str,
        f"{len(entries)} site(s) processed, {total_promoted} lesson(s) promoted, "
        f"{total_held} held — {status}",
    )
    return {"session_path": str(session_path), "entries": entries,
            "total_promoted": total_promoted, "total_held": total_held,
            "needs_review": needs_review}


async def run(limit: int) -> None:
    """Bounded manual test mode — no time cap, just an item-count limit."""
    date_str = date.today().isoformat()
    all_urls = p.load_reference_urls()
    pending = [u for u in all_urls if not p.is_url_processed(u)]
    print(f"[session] {len(all_urls)} reference URL(s) total, {len(pending)} not yet processed, limit={limit}")

    entries = [await process_one_url_full(u, date_str, deeper=False) for u in pending[:limit]]
    result = _finalize_session(date_str, entries)
    for e in result["entries"]:
        print(f"[html] wrote {e['output_path']} for real product '{e['product_title']}'")
        print(f"[lessons] promoted={len(e['promoted'])} held={len(e['held'])} verdict={e['verdict']}")
    print(f"[session] done — SESSION.md at {result['session_path']}")


SUMMARY_FILE = p.TRAINING_DIR / "last_run_summary.json"


async def run_daily_session(max_minutes: float = 240.0) -> dict:
    """Step 2 daily job body — called from a heartbeat tick as a background
    subprocess (see src/org/heartbeat.py::_training_tick), capped at
    `max_minutes` wall-clock. Processes any reference URL never seen before,
    then — only while genuinely new signal is still available — runs up to
    2 bounded "deeper" passes over ALL urls. Time is re-checked before EACH
    url (not pre-planned), so a slow real run stops mid-cycle exactly at the
    cap rather than a static plan silently ignoring it. Writes ONE
    SESSION.md for the day covering everything actually processed."""
    start = asyncio.get_event_loop().time()

    def elapsed_min() -> float:
        return (asyncio.get_event_loop().time() - start) / 60

    def time_left(margin: float = 6.0) -> bool:
        return elapsed_min() < max_minutes - margin

    date_str = date.today().isoformat()
    all_urls = p.load_reference_urls()
    pending = [u for u in all_urls if not p.is_url_processed(u)]

    entries: list[dict] = []
    notes: list[str] = []
    stopped_on_cap = False

    for url in pending:
        if not time_left():
            notes.append(f"Stopped mid-cycle: hit the {max_minutes:.0f}-minute time cap during first-pass processing.")
            stopped_on_cap = True
            break
        entries.append(await process_one_url_full(url, date_str, deeper=False))

    # Bounded deeper passes — only while still finding genuinely new signal,
    # capped at 2 so this can never spin indefinitely even if the model keeps
    # producing marginal "new" phrasing pass after pass. Time re-checked
    # before every single URL, not just before each pass.
    if not stopped_on_cap:
        for deep_pass in range(2):
            if not time_left():
                break
            pass_found_any = False
            for url in all_urls:
                if not time_left():
                    notes.append(f"Stopped mid-cycle: hit the {max_minutes:.0f}-minute time cap during a deeper pass.")
                    stopped_on_cap = True
                    break
                entry = await process_one_url_full(url, date_str, deeper=True)
                entries.append(entry)
                if entry["promoted"] or entry["held"]:
                    pass_found_any = True
            if stopped_on_cap:
                break
            if not pass_found_any:
                notes.append(
                    f"No new patterns found in deeper pass {deep_pass + 1} across all "
                    f"{len(all_urls)} reference URL(s) — more reference URLs would help surface "
                    "additional patterns. Stopping early rather than inventing content to fill time."
                )
                break

    result = _finalize_session(date_str, entries)
    if not entries:
        notes.append("Nothing to process — all reference URLs already covered and no time was available "
                      "for a deeper pass. More reference URLs would help surface additional patterns.")

    summary = {
        "date": date_str,
        "sites_processed": len(entries),
        "lessons_promoted": result["total_promoted"],
        "lessons_held": result["total_held"],
        "needs_review": result.get("needs_review", False),
        "htmls_generated_or_refined": len(entries),
        "elapsed_minutes": round(elapsed_min(), 1),
        "session_path": result["session_path"],
        "notes": notes,
    }
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1, help="Bounded test mode: process N URLs and stop.")
    ap.add_argument("--daily", action="store_true", help="Run the full daily session (Step 2).")
    ap.add_argument("--max-minutes", type=float, default=240.0)
    args = ap.parse_args()
    if args.daily:
        result = asyncio.run(run_daily_session(args.max_minutes))
        print(json.dumps(result, indent=2))
    else:
        asyncio.run(run(args.limit))
