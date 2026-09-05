"""
Shared library for the landing-page training loop (agents-training/).

Pattern extraction and HTML-building run on the FREE local qwen3:14b model
via the existing Ollama/LiteLLM setup (call_local_model, "standup" role) —
never the paid Anthropic tiers. The ONE deliberate, scoped exception is the
per-session visual critique (vision_critique, below), which uses Claude
vision ("executive" role) because qwen3 has no vision capability at all —
bounded to one call per session, not per lesson, and protected by the
existing monthly budget cap.

HTML structure is parsed with the stdlib html.parser (no BeautifulSoup).
Screenshots use Playwright (a real new dependency — see requirements.txt).

HARD RULES enforced by design, not just by prompt:
- We only ever extract STRUCTURE from a reference page — tag types, class-
  name hints, and content-type classification (price-like / review-like /
  countdown-like, via regex) — never the actual text. The skeleton handed
  to the model never contains a reference site's real copy, so the model
  physically cannot echo a reference site's copy into a lesson.
- Product HTML is built only from real Shopify catalog data (title, price,
  images, description fetched live via the Admin GraphQL API) — never
  invented facts.
- A lesson is NOT "in the system" until it clears BOTH the automated sanity
  check (passes_sanity_check) AND that session's visual critique coming
  back CLEAN — see promote_lesson / run_session.py's quality-gate logic.
  lessons.md (Step 1/2-v1, superseded) is no longer read or written by
  anything here; the real source of truth is the store_building_patterns
  RAG corpus (src/rag/index.py), queried via the search_training_patterns
  tool. Session markdown files (sessions/YYYY-MM-DD/SESSION.md) are the
  human-readable audit trail behind each promotion, not the retrieval path.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from src.llm.client import get_llm  # noqa: E402
from src.mcp_tools.shopify import _shopify_gql  # noqa: E402

TRAINING_DIR = Path(__file__).resolve().parent
URLS_FILE = TRAINING_DIR / "urls.md"
OUTPUT_DIR = TRAINING_DIR / "output"  # legacy Step-1/Step-2-v1 location — superseded by sessions/
SESSIONS_DIR = TRAINING_DIR / "sessions"
CHANGELOG_FILE = TRAINING_DIR / "CHANGELOG.md"
STATE_FILE = TRAINING_DIR / "state.json"


# ── URL handling ──────────────────────────────────────────────────────────
def strip_tracking_params(url: str) -> str:
    """Drop fbclid and other ad-click-id junk — noise, not needed to fetch the page."""
    parts = urlsplit(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in ("fbclid", "gclid", "msclkid", "ttclid")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def load_reference_urls() -> list[str]:
    text = URLS_FILE.read_text(encoding="utf-8")
    urls = re.findall(r"https?://\S+", text)
    return [strip_tracking_params(u) for u in urls]


# ── Local LLM (qwen3:14b via Ollama/LiteLLM) ────────────────────────────────
def _strip_think(text: str) -> str:
    """qwen3 is a reasoning model that can burn its whole budget inside a
    <think> block and return nothing after it — same failure mode already
    documented in src/org/heartbeat.py/conversation.py. We append /no_think
    to the prompt to avoid it, and still strip defensively in case a block
    slips through anyway."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


async def call_local_model(system: str, user: str, max_tokens: int = 2000) -> str:
    """One call to the free local qwen3:14b model (alpha/local-fast alias —
    see litellm_config.yaml). Never touches the paid Anthropic tiers."""
    llm = get_llm("standup", temperature=0.4, max_tokens=max_tokens, timeout=240)
    user_nt = user if user.rstrip().endswith("/no_think") else user + "\n\n/no_think"
    resp = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user_nt),
    ])
    return _strip_think(str(resp.content))


# ── Structural skeleton extraction (stdlib only, no copied text) ──────────
_ROLE_KEYWORDS = {
    "price": ("price", "sale-price", "compare-at", "money"),
    "discount": ("discount", "sale", "off-badge", "percent"),
    "review": ("review", "rating", "star", "testimonial"),
    "trust": ("trust", "guarantee", "secure", "badge", "verified"),
    "urgency": ("countdown", "timer", "urgent", "urgency", "limited", "hurry"),
    "stock": ("stock", "sold", "remaining", "inventory", "left-in-stock"),
    "cta": ("add-to-cart", "atc", "buy-now", "cta", "checkout-button"),
    "hero": ("hero", "banner", "announcement-bar"),
    "gallery": ("gallery", "thumbnail", "carousel", "slider"),
    "variant": ("variant", "swatch", "size-selector", "color-selector"),
    "faq": ("faq", "accordion", "collapsible"),
    "shipping": ("shipping", "delivery", "returns", "policy"),
}

_PRICE_RE = re.compile(r"[$€£]\s?\d")
_PERCENT_RE = re.compile(r"\d{1,3}\s?%")
_COUNT_RE = re.compile(r"\b\d{1,4}\s?(left|sold|in stock|reviews?|ratings?)\b", re.I)
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")


def _classify_text(text: str) -> str | None:
    """Regex-only content-type guess — NEVER returns or stores the text itself."""
    t = text.strip()
    if not t:
        return None
    if _PRICE_RE.search(t):
        return "price-like"
    if _PERCENT_RE.search(t):
        return "percent-like"
    if _COUNT_RE.search(t):
        return "count-like (stock/reviews)"
    if _TIME_RE.search(t):
        return "countdown-like"
    return None


@dataclass
class _Node:
    tag: str
    role_hints: list[str] = field(default_factory=list)
    content_type: str | None = None
    depth: int = 0
    order: int = 0


class _StructuralSkeletonParser(HTMLParser):
    """Walks the page in document order and records STRUCTURE only: tag type,
    nesting depth, class/id keyword hints, and a regex content-type guess.
    Actual text content is inspected only to classify it (price/discount/
    review/etc.) and is discarded immediately after — never stored."""

    _INTERESTING_TAGS = {
        "h1", "h2", "h3", "h4", "button", "a", "img", "div", "section",
        "span", "p", "form",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.order = 0
        self.nodes: list[_Node] = []
        self._stack: list[_Node] = []
        self._text_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        self.order += 1
        classes = " ".join(v or "" for k, v in attrs if k in ("class", "id")).lower()
        hints = [role for role, kws in _ROLE_KEYWORDS.items() if any(kw in classes for kw in kws)]
        node = _Node(tag=tag, role_hints=hints, depth=self.depth, order=self.order)
        if tag in self._INTERESTING_TAGS and (hints or tag in ("h1", "h2", "h3", "button")):
            self.nodes.append(node)
            self._stack.append(node)
        else:
            self._stack.append(None)  # placeholder to keep depth bookkeeping simple

    def handle_endtag(self, tag: str) -> None:
        if self._stack:
            node = self._stack.pop()
            if node is not None and self._text_buffer:
                node.content_type = _classify_text(" ".join(self._text_buffer))
        self._text_buffer = []
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._text_buffer.append(data.strip())


def build_structural_skeleton(html: str, max_nodes: int = 220) -> str:
    """Render the parsed structure as a compact, text-only OUTLINE — tag/role/
    content-type/depth/order — with zero copied site text. This is what gets
    sent to the local model for pattern extraction."""
    parser = _StructuralSkeletonParser()
    parser.feed(html)
    lines = []
    for n in parser.nodes[:max_nodes]:
        bits = [f"#{n.order}", "  " * min(n.depth, 6) + f"<{n.tag}>"]
        if n.role_hints:
            bits.append("hints=" + ",".join(n.role_hints))
        if n.content_type:
            bits.append("content=" + n.content_type)
        lines.append(" ".join(bits))
    return "\n".join(lines)


# ── Fetching a reference page ────────────────────────────────────────────
async def fetch_reference_html(url: str) -> str:
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


# ── Real Shopify catalog data (never invented) ──────────────────────────
_GQL_ONE_PRODUCT = """
query oneProduct($query: String!) {
  products(first: 1, query: $query, sortKey: CREATED_AT, reverse: true) {
    nodes {
      id
      handle
      title
      description
      priceRangeV2 { minVariantPrice { amount currencyCode } }
      images(first: 6) { nodes { url altText } }
    }
  }
}
"""


async def fetch_one_real_product(status_query: str = "status:active") -> dict | None:
    """One real, currently-active product from the live alphaforbaby catalog —
    id/handle/title/description/price/images. No fabricated data anywhere
    downstream of this call."""
    data = await _shopify_gql(_GQL_ONE_PRODUCT, {"query": status_query})
    nodes = data.get("products", {}).get("nodes", [])
    return nodes[0] if nodes else None


# ── State: which reference URLs have been processed, and when ────────────
# Replaces the old approach of grepping lessons.md's text for a URL — lessons
# are no longer stored as text at all (see the RAG section below), so URL
# coverage needs its own small, explicit record.
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"processed_urls": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def mark_url_processed(url: str, date_str: str) -> None:
    state = load_state()
    entry = state["processed_urls"].setdefault(url, {"first_processed": date_str, "times": 0})
    entry["last_processed"] = date_str
    entry["times"] += 1
    save_state(state)


def is_url_processed(url: str) -> bool:
    return url in load_state()["processed_urls"]


# ── Automated sanity check (tier 1 of the quality gate) ───────────────────
def passes_sanity_check(lesson: str) -> tuple[bool, str]:
    """Cheap, deterministic, no-LLM-call gate applied to every candidate
    lesson before it's even considered for RAG promotion. Rejects the
    obviously-broken cases: empty/near-empty fragments, and suspiciously
    long "lessons" that read more like leaked marketing prose than a
    concise structural principle."""
    words = lesson.split()
    if len(lesson.strip()) < 15:
        return False, "too short to be a real structural principle"
    if len(words) > 45:
        return False, "too long — reads like prose, not a concise structural lesson"
    if lesson.count("!") >= 2 or lesson.count("$") >= 2:
        return False, "reads like ad copy, not a structural observation"
    return True, ""


# ── Real RAG storage (Redis, via src.rag.index — same infra as Sol's
# "playbook" corpus). lessons.md is NOT the source of truth: a lesson is
# either promoted into the real "store_building_patterns" corpus (queryable
# via search_training_patterns) or it isn't in the system at all. Session
# markdown files are the human-readable audit trail behind each promotion,
# not the retrieval mechanism. ─────────────────────────────────────────────
_RAG_DEDUP_THRESHOLD = 0.90  # cosine similarity — near-duplicate rewording


async def is_new_lesson_via_rag(lesson: str) -> bool:
    """True if nothing already in the real store_building_patterns RAG is a
    near-duplicate of `lesson` (semantic similarity, not the old markdown
    word-overlap heuristic)."""
    from src.rag.index import search
    hits = await search("store_building_patterns", lesson, top_k=1)
    if not hits:
        return True
    score = hits[0].get("score")
    return score is None or score < _RAG_DEDUP_THRESHOLD


async def promote_lesson(category: str, lesson: str, session_date: str,
                          source_domain: str, session_path: str) -> bool:
    """Upsert one lesson into the real store_building_patterns RAG — the
    ONLY way a lesson becomes retrievable via search_training_patterns.
    Doc id is a stable hash of the lesson text so re-promoting identical
    text overwrites rather than duplicating."""
    from src.rag.index import upsert
    doc_id = hashlib.sha1(lesson.strip().lower().encode()).hexdigest()[:16]
    return await upsert(
        "store_building_patterns",
        doc_id=doc_id,
        text=lesson,
        metadata={
            "session_date": session_date,
            "category": category,
            "source_domain": source_domain,
            "session_path": session_path,
        },
    )


# ── Screenshots (Playwright — the visual feedback loop) ───────────────────
async def screenshot_url(url: str, out_path: Path, timeout_ms: int = 20000) -> bool:
    """Screenshot a live reference page as actually rendered (not just its
    raw HTML — this is what a vision model needs to critique layout)."""
    from playwright.async_api import async_playwright
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.goto(url, timeout=timeout_ms, wait_until="load")
            await page.screenshot(path=str(out_path), full_page=False)
            await browser.close()
        return True
    except Exception as exc:
        logging.getLogger(__name__).warning("Screenshot failed for %s: %s", url, exc)
        return False


async def screenshot_local_html(html_path: Path, out_path: Path) -> bool:
    """Screenshot our OWN generated (self-contained) HTML file, loaded
    directly as a file:// URL — no local server needed."""
    from playwright.async_api import async_playwright
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 900})
            await page.goto(html_path.resolve().as_uri(), timeout=10000, wait_until="load")
            await page.screenshot(path=str(out_path), full_page=False)
            await browser.close()
        return True
    except Exception as exc:
        logging.getLogger(__name__).warning("Screenshot failed for %s: %s", html_path, exc)
        return False


def image_to_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{data}"


# ── Visual critique (Claude vision — the ONE deliberate, scoped exception
# to local-only compute in this pipeline; extraction + HTML-building stay
# on free qwen3). One call per session, not per lesson. ───────────────────
_CRITIQUE_SYSTEM = """You are a meticulous UI/layout reviewer comparing two screenshots:
IMAGE 1 is a reference e-commerce product page (for structural inspiration only).
IMAGE 2 is a newly-built training page for a DIFFERENT real product, which was
supposed to apply certain STRUCTURAL patterns (placement/hierarchy only) taken
from IMAGE 1 — never its text, images, or exact styling.

Critique IMAGE 2 on its own merits as a product page, and specifically comment
on whether the intended structural patterns are visibly present and used
sensibly (not whether the content matches IMAGE 1 — it's a different product
and content SHOULD differ). Flag anything structurally broken: overlapping
elements, unreadable contrast, a CTA that's missing entirely, obviously broken
layout, or a pattern applied in a way that doesn't make sense for this product.

End your response with EXACTLY one line, verbatim:
VERDICT: CLEAN
or
VERDICT: NEEDS REVIEW"""


async def vision_critique(reference_screenshot: Path, generated_screenshot: Path,
                           product_title: str, lessons_applied: list[str]) -> dict:
    """The one Claude-vision call per session (executive/worker-smart tier —
    Sonnet). Returns {"critique": str, "verdict": "CLEAN"|"NEEDS_REVIEW"}."""
    llm = get_llm("executive", temperature=0.2, max_tokens=1000, timeout=120)
    lessons_block = "\n".join(f"- {ls}" for ls in lessons_applied) or "(none extracted this session)"
    user_text = (
        f"Product on the generated page: {product_title}\n\n"
        f"Structural patterns it was supposed to apply:\n{lessons_block}"
    )
    content = [
        {"type": "text", "text": user_text},
        {"type": "image_url", "image_url": {"url": image_to_data_url(reference_screenshot)}},
        {"type": "image_url", "image_url": {"url": image_to_data_url(generated_screenshot)}},
    ]
    resp = await llm.ainvoke([
        SystemMessage(content=_CRITIQUE_SYSTEM),
        HumanMessage(content=content),
    ])
    text = str(resp.content).strip()
    verdict = "NEEDS_REVIEW"
    m = re.search(r"VERDICT:\s*(CLEAN|NEEDS REVIEW)", text, re.IGNORECASE)
    if m and m.group(1).upper() == "CLEAN":
        verdict = "CLEAN"
    return {"critique": text, "verdict": verdict}


# ── Session folders + CHANGELOG ────────────────────────────────────────────
def session_dir(date_str: str) -> Path:
    d = SESSIONS_DIR / date_str
    (d / "output").mkdir(parents=True, exist_ok=True)
    return d


def write_session_md(date_str: str, entries: list[dict]) -> Path:
    """`entries`: one dict per reference URL processed this session —
    {url, domain, product_title, categorized_lessons, promoted, held,
    critique, verdict}. Overwrites the day's SESSION.md wholesale (a session
    is everything processed under one date, written once per URL-processing
    loop iteration via append semantics at the call site — see run_session.py)."""
    d = session_dir(date_str)
    path = d / "SESSION.md"
    lines = [f"# Training Session — {date_str}", ""]
    for e in entries:
        lines.append(f"## {e['domain']} → {e['product_title']}")
        lines.append(f"**Reference URL**: {e['url']}")
        lines.append("")
        lines.append("### Patterns found this session")
        for category, lessons in e["categorized_lessons"].items():
            if not lessons:
                continue
            lines.append(f"**{category}**")
            for lesson in lessons:
                lines.append(f"- {lesson}")
            lines.append("")
        lines.append("### Visual critique")
        lines.append(e["critique"])
        lines.append("")
        lines.append(f"**Verdict**: {e['verdict']}")
        lines.append("")
        if e["promoted"]:
            lines.append(f"✅ Promoted {len(e['promoted'])} lesson(s) to the store_building_patterns RAG.")
        if e["held"]:
            lines.append(f"⏸️ Held {len(e['held'])} lesson(s) pending review (visual critique flagged this session).")
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def append_changelog(date_str: str, summary: str) -> None:
    header = "# Training Sessions Changelog\n\nAppend-only — one entry per session date. This is the human-readable audit trail; the real retrieval mechanism is the store_building_patterns RAG.\n\n"
    if not CHANGELOG_FILE.exists():
        CHANGELOG_FILE.write_text(header, encoding="utf-8")
    line = f"- [{date_str}](sessions/{date_str}/SESSION.md) — {summary}\n"
    with CHANGELOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)
