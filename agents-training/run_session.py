"""
Landing-page training session — orchestrator.

Usage (bounded test, from repo root):
    .venv/bin/python3 agents-training/run_session.py --limit 1

Reads agents-training/lessons.md FIRST (accumulated knowledge from prior
sessions), processes up to `--limit` NOT-yet-processed reference URLs from
agents-training/urls.md (fetch -> structural skeleton -> local qwen3 ->
new lessons appended, deduped against what's already there), then builds
one self-contained product HTML file per processed URL using a REAL
Shopify catalog product, saved to agents-training/output/.

Every model call in this file goes through pipeline.call_local_model(),
which is pinned to the free local qwen3:14b model (Ollama/LiteLLM) — never
the paid Anthropic tiers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import date
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


def _already_processed(lessons_text: str, url: str) -> bool:
    return url in lessons_text


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


async def process_one_url(url: str, deeper: bool = False) -> dict:
    domain = _domain(url)
    print(f"[fetch] {url}")
    html = await p.fetch_reference_html(url)
    skeleton = p.build_structural_skeleton(html)
    print(f"[skeleton] {len(skeleton.splitlines())} structural nodes extracted (0 chars of site copy included)")

    print(f"[llm] extracting {'deeper ' if deeper else ''}structural patterns via local qwen3:14b ...")
    extra = ""
    if deeper:
        existing_categories = sorted(set(
            re.findall(r"^### (.+)$", p.read_lessons(), re.MULTILINE)
        ))
        extra = (
            "\n\nThis site has already been analyzed once. Existing categories already "
            f"covered: {', '.join(existing_categories) or '(none yet)'}. Only report "
            "patterns that are GENUINELY NEW — a different structural aspect not already "
            "captured above. If you find nothing genuinely new, output nothing at all."
        )
    # qwen3 needs far more budget than the visible answer alone would suggest —
    # tested empirically: 1200 truncated to a completely empty response even
    # with /no_think, 3800 produced a clean ~780-token answer. Generous cap
    # here since local compute is free.
    raw = await p.call_local_model(_EXTRACT_SYSTEM, f"STRUCTURAL OUTLINE:\n{skeleton}{extra}", max_tokens=3800)
    categorized = _parse_categorized_lessons(raw)

    added_total: list[str] = []
    for category, lessons in categorized.items():
        added = p.append_new_lessons(category, lessons, domain)
        added_total.extend(added)

    note = f"{len(added_total)} new lesson(s)" if added_total else "no new patterns"
    p.append_source_processed(url, date.today().isoformat(),
                               note=f"{note} (deeper pass)" if deeper else note)

    return {"url": url, "domain": domain, "raw_model_output": raw,
            "categorized": categorized, "added": added_total}


async def build_html_for_product(source_domain: str) -> dict:
    lessons_text = p.read_lessons()
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
        f"ACCUMULATED STRUCTURAL LESSONS (apply as layout guidance only):\n{lessons_text}\n\n"
        f"REAL PRODUCT DATA (the ONLY facts you may state):\n{json.dumps(product_facts, indent=2)}\n\n"
        "Build the landing page now."
    )
    # Same empty-response risk as extraction — tested at 6000 (2345 completion
    # tokens used, finish_reason=stop, ~2m40s). Local compute is free.
    html = await p.call_local_model(_BUILD_SYSTEM, user, max_tokens=6000)
    html = re.sub(r"^```(?:html)?\n?|```$", "", html.strip(), flags=re.MULTILINE).strip()

    out_path = p.OUTPUT_DIR / f"{product_facts['handle']}.html"
    p.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return {"product": product_facts, "output_path": str(out_path), "html_len": len(html)}


async def run(limit: int) -> None:
    p.ensure_lessons_file()
    lessons_text = p.read_lessons()
    all_urls = p.load_reference_urls()
    pending = [u for u in all_urls if not _already_processed(lessons_text, u)]
    print(f"[session] {len(all_urls)} reference URL(s) total, {len(pending)} not yet processed, "
          f"limit={limit}")

    processed = 0
    for url in pending[:limit]:
        result = await process_one_url(url)
        print(f"[lessons] {len(result['added'])} new lesson(s) added from {result['domain']}:")
        for lesson in result["added"]:
            print(f"    - {lesson}")
        if not result["added"]:
            print("    (no new lessons — everything the model found was already covered)")

        build = await build_html_for_product(result["domain"])
        print(f"[html] wrote {build['output_path']} ({build['html_len']} chars) "
              f"for real product '{build['product']['title']}' (${build['product']['price']})")
        processed += 1

    print(f"[session] done — processed {processed} reference URL(s) this run.")


SUMMARY_FILE = p.TRAINING_DIR / "last_run_summary.json"


async def run_daily_session(max_minutes: float = 240.0) -> dict:
    """Step 2 daily job body — called from a heartbeat tick as a background
    subprocess (see src/org/heartbeat.py::_training_tick), capped at
    `max_minutes` wall-clock. Reads lessons.md first (via process_one_url's
    own p.append_new_lessons dedup), processes any reference URL never seen
    before, then — only while genuinely new signal is still available — runs
    up to 2 bounded "deeper" passes over ALL urls. Stops the moment a full
    pass finds zero new lessons rather than spinning for the rest of the time
    budget or inventing content to fill it."""
    start = asyncio.get_event_loop().time()

    def elapsed_min() -> float:
        return (asyncio.get_event_loop().time() - start) / 60

    def time_left(margin: float = 6.0) -> bool:
        return elapsed_min() < max_minutes - margin

    p.ensure_lessons_file()
    all_urls = p.load_reference_urls()
    lessons_text = p.read_lessons()
    pending = [u for u in all_urls if not _already_processed(lessons_text, u)]

    sites_processed = 0
    new_lessons_total = 0
    htmls_written = 0
    notes: list[str] = []

    for url in pending:
        if not time_left():
            notes.append(f"Stopped mid-cycle: hit the {max_minutes:.0f}-minute time cap during first-pass processing.")
            break
        result = await process_one_url(url)
        sites_processed += 1
        new_lessons_total += len(result["added"])
        if time_left():
            await build_html_for_product(result["domain"])
            htmls_written += 1

    # Bounded deeper passes — only while still finding genuinely new signal.
    # Capped at 2 so this can never spin indefinitely even if the model keeps
    # producing marginal "new" phrasing pass after pass.
    for deep_pass in range(2):
        if not time_left():
            break
        pass_found_any = False
        for url in all_urls:
            if not time_left():
                notes.append(f"Stopped mid-cycle: hit the {max_minutes:.0f}-minute time cap during a deeper pass.")
                break
            result = await process_one_url(url, deeper=True)
            sites_processed += 1
            if result["added"]:
                pass_found_any = True
                new_lessons_total += len(result["added"])
                if time_left():
                    await build_html_for_product(result["domain"])
                    htmls_written += 1
        if not pass_found_any:
            notes.append(
                f"No new patterns found in deeper pass {deep_pass + 1} across all "
                f"{len(all_urls)} reference URL(s) — more reference URLs would help surface "
                "additional patterns. Stopping early rather than inventing content to fill time."
            )
            break

    summary = {
        "date": date.today().isoformat(),
        "sites_processed": sites_processed,
        "new_lessons": new_lessons_total,
        "htmls_generated_or_refined": htmls_written,
        "elapsed_minutes": round(elapsed_min(), 1),
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
