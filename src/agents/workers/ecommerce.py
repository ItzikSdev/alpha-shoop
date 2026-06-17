"""E-commerce Manager — creates Shopify products from scraper results."""
from __future__ import annotations
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify import create_shopify_product, update_inventory
from src.tracing.context import current_node

_COPY_SYSTEM = """\
You write short, persuasive Shopify product descriptions that make casual \
shoppers trust the listing and want to buy. Given a raw supplier product \
title and category, write clean HTML (use <p> and <ul><li> tags, no images, \
no markdown) with: one punchy intro paragraph, then a bullet list of 3-4 \
concrete selling points. No invented claims (certifications, awards, fake \
stats) — keep it grounded in the product type. Output ONLY the HTML, nothing else.
"""


async def _write_description(title: str, category: str) -> str:
    llm = get_llm("ecommerce", temperature=0.4)
    response = await llm.ainvoke([
        SystemMessage(content=_COPY_SYSTEM),
        HumanMessage(content=f"Product: {title}\nCategory: {category}"),
    ])
    return str(response.content).strip()


async def ecommerce_node(state: AgentState) -> dict:
    """LangGraph node: publishes top-margin products to Shopify."""
    current_node.set("ecommerce_manager")
    already_created = set(state.get("shopify_products_created", []))
    products = state.get("trending_products", [])
    # Pick top 5 by margin, skipping ones already listed in a prior pass
    candidates = [p for p in products if p.get("product_id") not in already_created]
    top = sorted(candidates, key=lambda p: p.get("margin_pct", 0), reverse=True)[:5]

    created_ids: list[str] = list(already_created)
    last_error: str | None = None
    for product in top:
        description = await _write_description(
            product.get("title", ""), product.get("category", "")
        )
        result = await create_shopify_product(
            title=product.get("title", ""),
            description=description,
            price=product.get("estimated_price_shopify_usd", 0.0),
            compare_at_price=product.get("estimated_price_shopify_usd", 0.0) * 1.2,
            images=product.get("images") or [product.get("image", "")],
            variants=[],
        )
        if result.get("success"):
            pid = result["product"]["id"]
            created_ids.append(str(pid))
            await update_inventory(
                product_id=str(pid),
                location_id="default",
                quantity=10,
            )
        else:
            last_error = result.get("error")

    new_count = len(created_ids) - len(already_created)
    return {
        "shopify_products_created": created_ids,
        # Surface failures so the director can stop instead of retrying forever.
        "error": None if new_count else (last_error or "no eligible products to list"),
        "messages": [HumanMessage(content=f"Created {new_count} Shopify products" + (f" (error: {last_error})" if last_error else ""))],
    }
