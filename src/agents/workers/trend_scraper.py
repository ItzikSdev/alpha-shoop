"""Trend Scraper worker — finds products via CJ Dropshipping and AliExpress MCP tools."""
from __future__ import annotations

from langchain_core.messages import HumanMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.mcp_tools.sourcing import search_trending_products, get_shipping_cost
from src.tracing.context import current_node

_SYSTEM = """\
You are the Trend Scraper agent. Find the best products to arbitrage.
Use the provided tools to discover trending items and check shipping costs.
Prioritise: margin > 30%, shipping < 14 days, trend score > 60.
"""


async def trend_scraper_node(state: AgentState) -> dict:
    """LangGraph node: scrapes CJ + AliExpress for trending products."""
    current_node.set("trend_scraper")
    settings = get_settings()

    # get_llm returns ChatOpenAI → LiteLLM proxy → claude-haiku-4-5-20251001
    _llm = get_llm("scraper")  # noqa: F841 — will be used when tool-binding is wired

    raw_products = await search_trending_products(
        category="general",
        max_results=settings.max_products_per_run,
        min_margin=0.30,
    )

    enriched = []
    for p in raw_products:
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

    return {
        "trending_products": enriched,
        "messages": [HumanMessage(content=f"Scraped {len(enriched)} products")],
    }
