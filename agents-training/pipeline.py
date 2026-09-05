"""
Shared library for the landing-page training loop (agents-training/).

Everything here runs on the FREE local qwen3:14b model via the existing
Ollama/LiteLLM setup (src.llm.client.get_llm("standup", ...)) — never the
paid Anthropic API. No new third-party dependencies: HTML structure is
parsed with the stdlib html.parser, not BeautifulSoup.

HARD RULES enforced by design, not just by prompt:
- We only ever extract STRUCTURE from a reference page — tag types, class-
  name hints, and content-type classification (price-like / review-like /
  countdown-like, via regex) — never the actual text. The skeleton handed
  to the model never contains a reference site's real copy, so the model
  physically cannot echo it back into lessons.md.
- Product HTML is built only from real Shopify catalog data (title, price,
  images, description fetched live via the Admin GraphQL API) — never
  invented facts.
"""
from __future__ import annotations

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
LESSONS_FILE = TRAINING_DIR / "lessons.md"
OUTPUT_DIR = TRAINING_DIR / "output"


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


# ── lessons.md read/append with dedup ────────────────────────────────────
_LESSONS_HEADER = """# Landing Page Design Lessons

Cumulative structural-pattern insights extracted from reference e-commerce
stores, session over session. **Read this file FIRST** at the start of every
training session — before analyzing any new reference site — so later
sessions build on prior findings instead of starting from zero.

Hard rules governing every entry below (never violate when adding more):
- Structural / placement / hierarchy patterns only — what's near what, in
  what order, how it's grouped.
- NEVER copy actual marketing text, images, logos, or exact CSS from a
  reference site — every lesson is a general, reusable design principle.
- Skip a pattern here if it's already covered by an existing lesson below
  (check before appending, even if the new source phrases it differently).

## Sources processed
"""

_PATTERNS_HEADING = "## Patterns"


def ensure_lessons_file() -> None:
    if not LESSONS_FILE.exists():
        LESSONS_FILE.write_text(_LESSONS_HEADER + "\n" + _PATTERNS_HEADING + "\n", encoding="utf-8")


def read_lessons() -> str:
    ensure_lessons_file()
    return LESSONS_FILE.read_text(encoding="utf-8")


def existing_lesson_lines(lessons_text: str) -> list[str]:
    """Every bullet already recorded, lower-cased, for a cheap dedup check."""
    return [ln.strip("- ").strip().lower() for ln in lessons_text.splitlines()
            if ln.strip().startswith("- ")]


def is_new_lesson(candidate: str, existing_lower: list[str]) -> bool:
    """True if `candidate` isn't already covered — simple word-overlap check
    (Jaccard), same technique already used elsewhere in this org
    (src/org/executor.py::_is_restated_goal) to catch reworded duplicates."""
    cand_words = set(re.findall(r"\w+", candidate.lower()))
    if not cand_words:
        return False
    for existing in existing_lower:
        ex_words = set(re.findall(r"\w+", existing))
        if not ex_words:
            continue
        overlap = len(cand_words & ex_words) / len(cand_words | ex_words)
        if overlap > 0.55:
            return False
    return True


def append_source_processed(url: str, date: str, note: str = "") -> None:
    """Insert a new row into the Sources-processed TABLE — not the end of the
    whole file, which (bug, fixed after the first real run) landed rows after
    the entire Patterns section instead of inside their own table."""
    text = read_lessons()
    row = f"| {date} | {url} | {note} |"
    if "| Date | URL | Notes |" not in text:
        # First source row for a fresh file — add the table header too.
        text = text.replace(
            "## Sources processed\n",
            "## Sources processed\n| Date | URL | Notes |\n|---|---|---|\n",
        )
    if _PATTERNS_HEADING in text:
        idx = text.index(_PATTERNS_HEADING)
        text = text[:idx].rstrip("\n") + "\n" + row + "\n\n" + text[idx:]
    else:
        text = text.rstrip("\n") + "\n" + row + "\n"
    LESSONS_FILE.write_text(text, encoding="utf-8")


def append_new_lessons(category: str, lessons: list[str], source_domain: str) -> list[str]:
    """Appends only genuinely-new lessons under `category` (creating the
    section if needed, right before ## Patterns' next top-level heading or
    at the end). Returns the ones actually added."""
    text = read_lessons()
    existing_lower = existing_lesson_lines(text)
    added: list[str] = []
    for lesson in lessons:
        lesson = lesson.strip("-* ").strip()
        if not lesson:
            continue
        if is_new_lesson(lesson, existing_lower):
            added.append(lesson)
            existing_lower.append(lesson.lower())
    if not added:
        return []

    heading = f"### {category}"
    if heading in text:
        idx = text.index(heading) + len(heading)
        # Insert right after the heading line.
        nl = text.index("\n", idx) + 1
        block = "".join(f"- {ls} _(source: {source_domain})_\n" for ls in added)
        text = text[:nl] + block + text[nl:]
    else:
        block = f"\n{heading}\n" + "".join(f"- {ls} _(source: {source_domain})_\n" for ls in added)
        if not text.endswith("\n"):
            text += "\n"
        text += block
    LESSONS_FILE.write_text(text, encoding="utf-8")
    return added
