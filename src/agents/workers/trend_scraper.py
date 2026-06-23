"""Trend Scraper worker — finds niche-relevant products via CJ Dropshipping."""
from __future__ import annotations
import json
import re
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.mcp_tools.sourcing import search_trending_products, get_shipping_cost, resolve_category
from src.tracing import agent_log
from src.tracing.context import current_node

logger = logging.getLogger(__name__)

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

Rules:
- 2–4 keywords only
- Specific, not vague ("wall art" not "home products")
- Match the brand's niche and target audience
- Return ONLY a JSON array of strings, no markdown

Example output: ["wall art", "decorative candles", "throw pillows"]
"""


async def _get_niche_categories(store_brand: dict) -> list[str]:
    """Ask the LLM to translate store brand niche into CJ search categories."""
    llm = get_llm("scraper", temperature=0.3)
    brief = (
        f"Store name: {store_brand.get('store_name', '')}\n"
        f"Niche: {store_brand.get('niche', '')}\n"
        f"Collections: {', '.join(store_brand.get('collections', []))}\n"
        f"Tone: {store_brand.get('tone', '')}"
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
literal product noun (e.g. "organic baby clothing" → "baby clothing", "baby rompers").

Output ONLY a JSON array of strings, no markdown. Example: ["baby clothing", "baby rompers"]
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
        categories = await _get_niche_categories(store_brand)
        agent_log(f"Niche search keywords: {', '.join(categories)}", "action")
    else:
        categories = ["general"]

    # Search the single focused category — fetch more than needed so we have room to filter
    seen_ids: set[str] = set()
    all_products: list[dict] = []

    for cat in categories:
        agent_log(f"Resolving CJ category for '{cat}'...", "action")
        resolved = await resolve_category(cat)
        if resolved:
            agent_log(f"→ CJ category: {resolved['path']}", "info")
        else:
            agent_log(f"No CJ category match for '{cat}' — search may return unrelated results", "warning")

        agent_log(f"Searching CJ: '{cat}' (focused, single-category)...", "action")
        batch = await search_trending_products(
            category=cat,
            category_id=resolved["category_id"] if resolved else "",
            max_results=20,  # fetch more — ecommerce_manager will filter & cap
            min_margin=0.30,
            max_price_usd=50.0,
        )
        for p in batch:
            pid = str(p.get("product_id", ""))
            if pid not in seen_ids and pid not in already_created:
                seen_ids.add(pid)
                all_products.append(p)

    # Enrich with shipping costs (limit to top 15 by margin to avoid slow API calls)
    candidates = sorted(all_products, key=lambda p: p.get("margin_pct", 0), reverse=True)[:15]
    enriched = []
    for p in candidates:
        shipping = await get_shipping_cost(
            product_id=p.get("cj_vid", p["product_id"]),
            destination_country="US",
            shipping_method="standard",
        )
        enriched.append({
            **p,
            "shipping_cost_usd": shipping["cost_usd"],
            "shipping_days": shipping["estimated_days"],
        })

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
