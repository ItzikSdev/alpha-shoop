#!/usr/bin/env python3
"""
Smoke test for the two MCP tools — no Claude Desktop needed.
Usage: make mcp-test
"""
from __future__ import annotations
import asyncio
import json
import sys

from mcp_server import search_trending_products, create_shopify_product


async def main() -> None:
    sep = "─" * 60

    # ── Tool 1 ────────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("▶  search_trending_products(category='Electronics', max_results=5)")
    print(sep)
    try:
        result = await search_trending_products(
            category="Electronics",
            max_results=5,
            min_margin_pct=30.0,
        )
        print(json.dumps(result, indent=2))
        products = result.get("products", [])
        top = products[0] if products else None
        if top:
            print(f"\n✓  Found {len(products)} products. Best: {top['title']} "
                  f"(${top['supplier_price_usd']} → ${top['suggested_retail_usd']}, "
                  f"{top['margin_pct']}% margin)")
        else:
            print("\n⚠  No products returned — check CJ credentials in .env")
    except Exception as e:
        print(f"✗  Error: {e}")
        sys.exit(1)

    # ── Tool 2 ────────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("▶  create_shopify_product(title='Test Product', price=24.99)")
    print(sep)
    try:
        result = await create_shopify_product(
            title="[TEST] Wireless Earbuds TWS Pro — Alpha Shoop",
            description="<p>Premium wireless earbuds. Auto-pairing. 30h battery.</p>",
            price=24.99,
            compare_at_price=39.99,
            supplier_product_id=top["product_id"] if top else "SAMPLE001",
            product_type="Electronics",
        )
        print(json.dumps(result, indent=2))
        if result.get("success"):
            print(f"\n✓  Product created → {result['product']['admin_url']}")
        else:
            print(f"\n⚠  Shopify not configured: {result.get('error','')[:120]}")
            print("   → Add SHOPIFY_STORE_DOMAIN + SHOPIFY_ACCESS_TOKEN to .env")
    except Exception as e:
        print(f"✗  Error: {e}")

    print(f"\n{sep}")
    print("Both tools ran. Run  make mcp-config  to register with Claude Desktop.")
    print(sep)


if __name__ == "__main__":
    asyncio.run(main())
