"""Trend Scraper worker — finds niche-relevant products via CJ Dropshipping."""
from __future__ import annotations
import json
import os
import re
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.mcp_tools.sourcing import search_trending_products, get_shipping_cost, resolve_category, CJQuotaExceeded
from src.mcp_tools.shopify import list_shopify_products
from src.tracing import agent_log
from src.tracing.context import current_node

logger = logging.getLogger(__name__)

# Must match ecommerce.py's _MAX_SOURCING_ATTEMPTS — both gate the same
# sourcing_attempts counter (off-niche rejections there, zero-raw-results here).
_MAX_SOURCING_ATTEMPTS = 3

_CATEGORY_SYSTEM = """\
You are helping source products for a dropshipping store.
Given the store's brand brief, output a JSON array of 2-4 CJ Dropshipping category search keywords.
These keywords will be passed directly to the CJ product search API.
Choose specific, concrete categories that match the store's niche exactly.

Examples of good CJ category keywords:
- "home decor", "wall art", "candles", "throw pillows", "picture frames"
- "kitchen gadgets", "coffee accessories", "cooking tools"
- "yoga mat", "resistance bands", "water bottle"
- "phone stand", "desk organizer", "cable management"
- For apparel/clothing niches, use the CONCRETE GARMENT TYPE, never a generic
  category label: "baby onesie", "newborn romper", "knit cardigan", "baby sleep
  sack" — NOT "baby clothing" / "toddler clothing" / "kids apparel". CJ's free-text
  search matches literal product names, so generic category nouns pull in
  unrelated junk (adult clothing, accessories, storage items) while a specific
  garment type hits real matching listings.

Rules:
- 2–4 keywords only
- Specific, not vague ("wall art" not "home products"; "baby onesie" not "baby clothing")
- Match the brand's niche and target audience
- Return ONLY a JSON array of strings, no markdown

Example output: ["wall art", "decorative candles", "throw pillows"]
"""


async def _get_niche_categories(store_brand: dict, store_knowledge: list[dict] | None = None) -> list[str]:
    """Ask the LLM to translate store brand niche into CJ search categories.

    store_knowledge: agentic-RAG matches over the owner's own store description
    (see orchestrator.py) — the owner's ground truth about scope/assortment
    (e.g. "should carry boys AND girls clothing separately"), folded in here
    since this is the one place a "what should we actually search for" judgment
    call already goes through an LLM.
    """
    llm = get_llm("scraper", temperature=0.3)
    knowledge_line = (
        "\nStore knowledge (owner's own description — treat as ground truth about scope):\n"
        + "\n".join(f"- {k['document'][:300]}" for k in store_knowledge)
        if store_knowledge else ""
    )
    brief = (
        f"Store name: {store_brand.get('store_name', '')}\n"
        f"Niche: {store_brand.get('niche', '')}\n"
        f"Collections: {', '.join(store_brand.get('collections', []))}\n"
        f"Tone: {store_brand.get('tone', '')}"
        f"{knowledge_line}"
    )
    response = await llm.ainvoke([
        SystemMessage(content=_CATEGORY_SYSTEM),
        HumanMessage(content=brief),
    ])
    raw = str(response.content).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    try:
        cats = json.loads(raw.strip())
        if isinstance(cats, list) and all(isinstance(c, str) for c in cats):
            return cats[:4]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: derive from collections
    return store_brand.get("collections", ["general"])[:3]


_RELAX_SYSTEM = """\
You help source dropshipping products from a wholesale catalogue (CJ Dropshipping).
The store's exact product category was searched but ecommerce review rejected every
result as off-niche. Generate 2-3 ALTERNATE search phrases that describe the same
core product type but drop any modifier the wholesale catalogue won't have data for
(e.g. "organic", "certified", "handmade", brand-specific claims) while keeping the
literal product noun CONCRETE — never regress to a generic category label.
Example: "organic cotton baby onesie" → "baby onesie", "cotton baby bodysuit"
(NOT "baby clothing" — that's the generic label that just failed; stay specific).

Output ONLY a JSON array of strings, no markdown. Example: ["baby onesie", "cotton baby bodysuit"]
"""


async def _relax_search_terms(product_category: str, feedback: str) -> list[str]:
    """After rejected candidates, ask the LLM for broader/alternate search phrases."""
    llm = get_llm("scraper", temperature=0.3)
    prompt = f"Original category: {product_category}\nRejection feedback: {feedback}"
    response = await llm.ainvoke([
        SystemMessage(content=_RELAX_SYSTEM),
        HumanMessage(content=prompt),
    ])
    raw = str(response.content).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    try:
        terms = json.loads(raw.strip())
        if isinstance(terms, list) and all(isinstance(t, str) for t in terms):
            return terms[:3]
    except (json.JSONDecodeError, ValueError):
        pass
    return [product_category]


async def trend_scraper_node(state: AgentState) -> dict:
    """LangGraph node: scrapes CJ for products that exactly match the store's one product category."""
    current_node.set("trend_scraper")
    settings = get_settings()

    store_brand = state.get("store_brand") or {}
    already_created = set(str(pid) for pid in state.get("shopify_products_created", []))
    feedback = state.get("sourcing_feedback")

    # Use product_category from brand brief directly — this is the ONE product type
    product_category = store_brand.get("product_category", "")
    if feedback and product_category:
        agent_log(f"Previous batch rejected — relaxing search terms ({feedback[:80]})...", "action")
        categories = await _relax_search_terms(product_category, feedback)
        agent_log(f"Retrying with: {', '.join(categories)}", "info")
    elif store_brand:
        # Search by the store's concrete product TYPES (derived from its niche +
        # collections), NOT the single abstract product_category. CJ's catalogue
        # names items by concrete type ("galaxy projector"), so an abstract phrase
        # like "ambient LED projection lamp" returns generic filler (wall/desk/
        # mosquito lamps) the niche-gate then rejects. Concrete type keywords yield
        # real, varied, on-niche hits.
        agent_log(f"Store product category: '{product_category or store_brand.get('niche','')}'", "info")
        categories = await _get_niche_categories(store_brand, state.get("store_knowledge"))
        agent_log(f"Niche search keywords: {', '.join(categories)}", "action")
    else:
        categories = ["general"]

    # Search the single focused category — fetch more than needed so we have room to filter
    seen_ids: set[str] = set()
    all_products: list[dict] = []

    # Advance CJ's result page as the catalog fills — repeated rounds against the
    # same category would otherwise always hit page 1 again, which dedup then
    # filters down to zero "new" candidates once that page is already mined.
    # Use the store's REAL live product count, not already_created (which is only
    # this run's new creations and resets to empty on every fresh run/task) —
    # otherwise every fresh run keeps re-requesting page 1 forever regardless of
    # how much inventory already exists.
    try:
        live_count = len(await list_shopify_products())
    except Exception:
        live_count = len(already_created)
    page_num = (live_count // 15) + 1

    for cat in categories:
        agent_log(f"Resolving CJ category for '{cat}'...", "action")
        resolved = await resolve_category(cat)
        if resolved:
            agent_log(f"→ CJ category: {resolved['path']}", "info")
        else:
            agent_log(f"No CJ category match for '{cat}' — search may return unrelated results", "warning")

        agent_log(f"Searching CJ: '{cat}' (focused, single-category)...", "action")
        try:
            batch = await search_trending_products(
                category=cat,
                category_id=resolved["category_id"] if resolved else "",
                max_results=20,  # fetch more — ecommerce_manager will filter & cap
                min_margin=0.30,
                max_price_usd=50.0,
                page_num=page_num,
            )
        except CJQuotaExceeded as exc:
            # Hard stop, not "0 candidates" — without this the director has no
            # signal that retrying is pointless and will loop the identical query
            # forever (confirmed: 15+ repeats, ~1.5M tokens, zero progress) until
            # CJ's daily quota resets, instead of ending the run immediately.
            agent_log(f"CJ daily quota exhausted — stopping sourcing: {exc}", "error")
            return {
                "trending_products": [],
                "error": f"CJ Dropshipping daily API quota exhausted: {exc}",
                "messages": [HumanMessage(content="Sourcing stopped — CJ daily quota exhausted")],
            }
        for p in batch:
            pid = str(p.get("product_id", ""))
            if pid not in seen_ids and pid not in already_created:
                seen_ids.add(pid)
                all_products.append(p)

    # Enrich with shipping costs (limit to top 15 by margin to avoid slow API calls)
    candidates = sorted(all_products, key=lambda p: p.get("margin_pct", 0), reverse=True)[:15]
    enriched = []
    for p in candidates:
        # The store sells GLOBALLY, not to one local market. We quote shipping to the
        # primary global market (default US — the largest English-speaking market and
        # a good proxy for "ships worldwide at a reasonable rate"). Override with
        # SHIP_DESTINATION_COUNTRY (ISO-2) if you want margins quoted for another market.
        shipping = await get_shipping_cost(
            product_id=p.get("cj_vid", p["product_id"]),
            destination_country=os.environ.get("SHIP_DESTINATION_COUNTRY", "US"),
            shipping_method="standard",
        )
        enriched.append({
            **p,
            "shipping_cost_usd": shipping["cost_usd"],
            "shipping_days": shipping["estimated_days"],
        })

    if not enriched:
        # Circuit breaker: CJ returned literally zero raw results for every
        # category this round (page exhausted, empty leaf, transient issue —
        # whatever the cause). Route through the SAME sourcing_attempts cap
        # ecommerce_manager uses for off-niche rejections, instead of returning
        # an empty batch with no signal — director would otherwise just call
        # trend_scraper again with identical inputs forever (confirmed: 15+
        # repeats, ~1.5M tokens burned, zero progress, before this fix existed).
        attempts = state.get("sourcing_attempts", 0) + 1
        agent_log(f"Zero raw candidates this round (attempt {attempts}/{_MAX_SOURCING_ATTEMPTS})", "warning")
        if attempts >= _MAX_SOURCING_ATTEMPTS:
            return {
                "trending_products": [],
                "sourcing_attempts": attempts,
                "error": "CJ returned zero candidates after multiple sourcing attempts",
                "messages": [HumanMessage(content="No candidates found after retries — stopping")],
            }
        return {
            "trending_products": [],
            "sourcing_attempts": attempts,
            "sourcing_feedback": f"Zero raw results for: {', '.join(categories)}",
            "messages": [HumanMessage(content=f"No candidates found (attempt {attempts}) for: {', '.join(categories)}")],
        }

    agent_log(f"✓ Found {len(enriched)} candidates for: {', '.join(categories)} (sorted by margin)", "success")
    return {
        "trending_products": enriched,
        "sourcing_feedback": None,  # consumed — ecommerce_manager will set it again if this batch is also rejected
        # Gate candidates against the store's broad product concept (e.g. "ambient
        # mood lighting") rather than the individual concrete search keywords — this
        # lets any genuine on-niche type through (sunset lamp, galaxy projector, LED
        # strip) while still rejecting clearly off-niche filler (dog clippers, etc.).
        "search_category_used": product_category or ", ".join(categories),
        "messages": [HumanMessage(
            content=f"Scraped {len(enriched)} products in category: {', '.join(categories)}"
        )],
    }
