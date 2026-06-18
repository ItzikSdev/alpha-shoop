"""Trend Scraper worker — finds niche-relevant products via CJ Dropshipping."""
from __future__ import annotations
import json
import re
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.mcp_tools.sourcing import search_trending_products, get_shipping_cost
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


async def trend_scraper_node(state: AgentState) -> dict:
    """LangGraph node: scrapes CJ for products that match the store's niche."""
    current_node.set("trend_scraper")
    settings = get_settings()

    store_brand = state.get("store_brand") or {}
    already_created = set(state.get("shopify_products_created", []))

    # Determine which categories to search based on the store brand
    if store_brand:
        categories = await _get_niche_categories(store_brand)
        logger.info("Searching CJ for niche categories: %s", categories)
    else:
        categories = ["general"]

    # Search each category, merge results, deduplicate by product_id
    seen_ids: set[str] = set()
    all_products: list[dict] = []
    per_category = max(3, settings.max_products_per_run // len(categories))

    for cat in categories:
        batch = await search_trending_products(
            category=cat,
            max_results=per_category,
            min_margin=0.30,
            max_price_usd=50.0,
        )
        for p in batch:
            pid = p.get("product_id", "")
            if pid not in seen_ids and str(pid) not in already_created:
                seen_ids.add(pid)
                all_products.append(p)

    # Enrich with shipping costs
    enriched = []
    for p in all_products[:settings.max_products_per_run]:
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

    cat_summary = ", ".join(categories)
    return {
        "trending_products": enriched,
        "messages": [HumanMessage(
            content=f"Scraped {len(enriched)} products across categories: {cat_summary}"
        )],
    }
