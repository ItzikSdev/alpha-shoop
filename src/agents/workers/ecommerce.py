"""E-commerce Manager — creates Shopify products from scraper results."""
from __future__ import annotations
from langchain_core.messages import HumanMessage
from src.agents.state import AgentState
from src.mcp_tools.shopify import create_shopify_product, update_inventory


async def ecommerce_node(state: AgentState) -> dict:
    """LangGraph node: publishes top-margin products to Shopify."""
    products = state.get("trending_products", [])
    # Pick top 5 by margin
    top = sorted(products, key=lambda p: p.get("margin_pct", 0), reverse=True)[:5]

    created_ids: list[str] = []
    for product in top:
        result = await create_shopify_product(
            title=product.get("title", ""),
            description=product.get("description", ""),
            price=product.get("estimated_price_shopify_usd", 0.0),
            compare_at_price=product.get("estimated_price_shopify_usd", 0.0) * 1.2,
            images=[],
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

    return {
        "shopify_products_created": created_ids,
        "messages": [HumanMessage(content=f"Created {len(created_ids)} Shopify products")],
    }
