"""MCP server registry — maps tool names to their Python implementations."""
from __future__ import annotations
from typing import Any
from src.mcp_tools import sourcing, market, shopify, ads, fulfillment, cj_connect, paypal, cloudflare, shopify_design, store_scan, design_files, variant_backfill, finance

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
    # CJ ⇄ Shopify product connection (enables the CJ app to auto-fulfill)
    "list_cj_shops": cj_connect.list_cj_shops,
    "connect_product": cj_connect.connect_product,
    "connect_store_products": cj_connect.connect_store_products,
    # Add a Color selector + per-variant CJ SKUs to a product listed before the
    # pipeline emitted colors (idempotent; binds each color/size to its CJ vid)
    "backfill_product_color": variant_backfill.backfill_product_color,
    # PayPal — read-only money signals (real revenue / balance)
    "get_paypal_transactions": paypal.get_paypal_transactions,
    "get_paypal_balance": paypal.get_paypal_balance,
    # Finance ledger — revenue vs cost (incl. per-agent LLM spend) history
    "finance_snapshot": finance.finance_snapshot,
    "log_finance_snapshot": finance.log_finance_snapshot,
    # Cloudflare — point a store subdomain at Shopify
    "point_subdomain_to_shopify": cloudflare.point_subdomain_to_shopify,
    "ensure_dns_cname": cloudflare.ensure_dns_cname,
    # Design — deterministic theme styling (Grace's reliable recipe)
    "apply_theme_css": shopify_design.apply_theme_css,
    "apply_store_design": shopify_design.apply_store_design,
    "apply_product_design": shopify_design.apply_product_design,
    # Whole-store scan → giant JSON of real state + issue flags
    "scan_store": store_scan.scan_store,
    # Design-file access (scoped to styles/) — Grace/Linus edit the JSON templates
    "list_design_files": design_files.list_design_files,
    "read_design_file": design_files.read_design_file,
    "write_design_file": design_files.write_design_file,
}


async def invoke_tool(name: str, arguments: dict) -> Any:
    """Invoke a registered MCP tool by name with keyword arguments."""
    fn = _TOOLS.get(name)
    if not fn:
        raise KeyError(f"Unknown tool: {name!r}. Available: {list(_TOOLS)}")
    return await fn(**arguments)


def list_tools() -> list[str]:
    return list(_TOOLS.keys())
