"""MCP server registry — maps tool names to their Python implementations."""
from __future__ import annotations
from typing import Any
from src.mcp_tools import sourcing, market, shopify, ads, fulfillment

_TOOLS: dict[str, Any] = {
    "search_trending_products": sourcing.search_trending_products,
    "get_shipping_cost": sourcing.get_shipping_cost,
    "search_market_prices": market.search_market_prices,
    "check_google_trends": market.check_google_trends,
    "create_shopify_product": shopify.create_shopify_product,
    "update_inventory": shopify.update_inventory,
    "create_google_campaign": ads.create_google_campaign,
    "get_campaign_metrics": ads.get_campaign_metrics,
    "place_supplier_order": fulfillment.place_supplier_order,
    "fulfill_shopify_order": fulfillment.fulfill_shopify_order,
}


async def invoke_tool(name: str, arguments: dict) -> Any:
    """Invoke a registered MCP tool by name with keyword arguments."""
    fn = _TOOLS.get(name)
    if not fn:
        raise KeyError(f"Unknown tool: {name!r}. Available: {list(_TOOLS)}")
    return await fn(**arguments)


def list_tools() -> list[str]:
    return list(_TOOLS.keys())
