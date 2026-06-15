#!/usr/bin/env python3
"""
Alpha Shoop MCP Server — Core Infrastructure
Two tools only: search_trending_products + create_shopify_product

Register in Claude Desktop:
  make mcp-config  →  prints the JSON block to paste into claude_desktop_config.json

Test without Claude Desktop:
  make mcp-test
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

CJ_EMAIL       = os.getenv("CJ_EMAIL", "")
CJ_API_KEY     = os.getenv("CJ_API_KEY", "")
CJ_TOKEN_DIRECT = os.getenv("CJ_ACCESS_TOKEN", "")   # pre-generated token (optional)

SHOPIFY_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "")
SHOPIFY_TOKEN  = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

mcp = FastMCP("alpha-shoop")

# ── CJ Auth (token cached for the process lifetime) ──────────────────────────

_cj_token_cache: str | None = CJ_TOKEN_DIRECT or None


async def _cj_token() -> str:
    global _cj_token_cache
    if _cj_token_cache:
        return _cj_token_cache
    if not CJ_EMAIL or not CJ_API_KEY:
        raise RuntimeError(
            "Set CJ_EMAIL + CJ_API_KEY in .env  "
            "(or CJ_ACCESS_TOKEN for a pre-generated token)"
        )
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            "https://developers.cjdropshipping.com/api2.0/v1/authorization/getAccessToken",
            json={"email": CJ_EMAIL, "password": CJ_API_KEY},
        )
        r.raise_for_status()
        body = r.json()
        if not body.get("result"):
            raise RuntimeError(f"CJ auth failed: {body.get('message')}")
        _cj_token_cache = body["data"]["accessToken"]
        return _cj_token_cache


# ── Tool 1: search_trending_products ─────────────────────────────────────────

@mcp.tool()
async def search_trending_products(
    category: str,
    max_results: int = 10,
    min_margin_pct: float = 30.0,
) -> dict[str, Any]:
    """
    Search CJ Dropshipping for trending products in a category.

    Returns a list with supplier price, suggested retail price, and estimated margin.
    Call this first to find products worth listing on Shopify.

    Args:
        category: Product category (e.g. "Electronics", "Home & Garden", "Beauty & Health")
        max_results: How many products to return (1–50, default 10)
        min_margin_pct: Minimum gross margin % to include (default 30)
    """
    # Try CJ API; fall back to sample data if credentials are missing or API fails
    note: str | None = None
    raw: list[dict] = []

    try:
        token = await _cj_token()
        fetch_size = min(max(max_results * 3, 20), 50)
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(
                "https://developers.cjdropshipping.com/api2.0/v1/product/list",
                json={
                    "pageNum": 1,
                    "pageSize": fetch_size,
                    "categoryName": category,
                    "orderBy": "ORDERS_COUNT",
                },
                headers={"CJ-Access-Token": token},
            )
            resp.raise_for_status()
            body = resp.json()

        if not body.get("result"):
            raw = _sample_products(category)
            note = f"CJ API: {body.get('message')} — showing sample data"
        else:
            raw = body.get("data", {}).get("list", [])

    except RuntimeError:
        # No CJ credentials configured — use sample data
        raw = _sample_products(category)
        note = "CJ_EMAIL / CJ_API_KEY not set in .env — showing sample data"
    except Exception as e:
        raw = _sample_products(category)
        note = f"CJ API unavailable ({e}) — showing sample data"

    products: list[dict] = []
    for p in raw:
        cost = float(p.get("sellPrice") or 0)
        if cost <= 0:
            # Try variant price
            variants = p.get("variants") or []
            cost = float(variants[0].get("variantSellPrice", 0)) if variants else 0
        if cost <= 0:
            continue

        # 2.5× markup → ~60 % gross margin
        retail = round(cost * 2.5, 2)
        margin = round(((retail - cost) / retail) * 100, 1)
        if margin < min_margin_pct:
            continue

        products.append({
            "product_id": p.get("pid", ""),
            "title": p.get("productNameEn", ""),
            "category": p.get("categoryName", category),
            "supplier_price_usd": cost,
            "suggested_retail_usd": retail,
            "margin_pct": margin,
            "image_url": p.get("productImage", ""),
        })

        if len(products) >= max_results:
            break

    products.sort(key=lambda x: x["margin_pct"], reverse=True)

    result: dict[str, Any] = {
        "category": category,
        "found": len(products),
        "products": products,
    }
    if note:
        result["note"] = note
    return result


# ── Tool 2: create_shopify_product ────────────────────────────────────────────

@mcp.tool()
async def create_shopify_product(
    title: str,
    description: str,
    price: float,
    compare_at_price: float | None = None,
    supplier_product_id: str = "",
    supplier_sku: str = "",
    supplier_cost: float = 0.0,
    image_url: str = "",
    product_type: str = "",
) -> dict[str, Any]:
    """
    Create a product in the Shopify development store as a DRAFT.

    The product is created in DRAFT status so you can review it before publishing.
    After this call succeeds, the mapping is saved to product_mappings DB table
    (used later by the fulfillment agent when a Shopify order webhook fires).

    Args:
        title: Product title
        description: Product description (plain text or HTML)
        price: Retail selling price in USD
        compare_at_price: Original / compare-at price (optional, shown as strikethrough)
        supplier_product_id: CJ product ID (pass from search_trending_products result)
        supplier_sku: CJ variant SKU (used when auto-placing supplier order)
        supplier_cost: Supplier cost in USD (used to track margin in DB)
        image_url: Main product image URL (optional)
        product_type: Product category/type (optional)
    """
    if not SHOPIFY_DOMAIN or not SHOPIFY_TOKEN:
        return {
            "success": False,
            "error": (
                "SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN are not set. "
                "Add them to .env — get the token from: "
                "Shopify Admin → Settings → Apps and sales channels → Develop apps"
            ),
        }

    tags = ["alpha-shoop", "dropship"]
    if supplier_product_id:
        tags.append(f"cj-{supplier_product_id}")

    # Build product payload (Shopify REST API — simpler than GraphQL)
    product_payload: dict[str, Any] = {
        "title": title,
        "body_html": description if "<" in description else f"<p>{description}</p>",
        "vendor": "Alpha Shoop",
        "status": "draft",
        "tags": ", ".join(tags),
        "variants": [{
            "price": f"{price:.2f}",
            **({"compare_at_price": f"{compare_at_price:.2f}"} if compare_at_price else {}),
            "inventory_management": "shopify",
            "inventory_quantity": 999,
        }],
    }

    if product_type:
        product_payload["product_type"] = product_type

    if image_url:
        product_payload["images"] = [{"src": image_url}]

    url = f"https://{SHOPIFY_DOMAIN}/admin/api/2024-07/products.json"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.post(
                url,
                json={"product": product_payload},
                headers={
                    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "error": f"Shopify API error {e.response.status_code}: {e.response.text[:300]}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

    product = data.get("product", {})
    pid = product.get("id")
    variant = (product.get("variants") or [{}])[0]

    result: dict[str, Any] = {
        "success": True,
        "product": {
            "id": pid,
            "title": product.get("title"),
            "status": product.get("status"),
            "price": variant.get("price"),
            "compare_at_price": variant.get("compare_at_price"),
            "admin_url": f"https://{SHOPIFY_DOMAIN}/admin/products/{pid}",
        },
        "next_step": "Open admin_url in your browser to review the draft and click Publish.",
    }

    # ── Write mapping to DB (non-fatal — Shopify product already created) ────
    if supplier_product_id and pid:
        cost = supplier_cost if supplier_cost > 0 else round(price / 2.5, 2)
        result["db"] = await _save_product_mapping(
            shopify_product_id=str(pid),
            supplier_product_id=supplier_product_id,
            supplier_sku=supplier_sku or supplier_product_id,
            cost_price=cost,
            retail_price=price,
        )

    return result


# ── DB helper ─────────────────────────────────────────────────────────────────

async def _save_product_mapping(
    shopify_product_id: str,
    supplier_product_id: str,
    supplier_sku: str,
    cost_price: float,
    retail_price: float,
) -> dict[str, Any]:
    """
    Persist a ProductMapping row after a successful Shopify product creation.

    Imported lazily so a missing DATABASE_URL or offline Postgres doesn't prevent
    the MCP server from starting — the Shopify product is already created by this point.
    """
    try:
        from src.db.engine import get_session   # lazy import — safe if DB is offline
        from src.db.models import ProductMapping

        async with get_session() as session:
            mapping = ProductMapping(
                shopify_product_id=shopify_product_id,
                supplier_product_id=supplier_product_id,
                supplier_sku=supplier_sku,
                cost_price=Decimal(str(round(cost_price, 2))),
                retail_price=Decimal(str(round(retail_price, 2))),
            )
            session.add(mapping)
            # commit happens automatically when the context manager exits cleanly

        return {
            "saved": True,
            "shopify_product_id": shopify_product_id,
            "cost_price": cost_price,
            "retail_price": retail_price,
            "margin_pct": round((retail_price - cost_price) / retail_price * 100, 1),
        }
    except Exception as exc:
        logger.warning("product_mappings DB write failed (non-fatal): %s", exc)
        return {
            "saved": False,
            "reason": str(exc),
            "action": "Run `make db-migrate` to create the table, then retry.",
        }


# ── Sample data (used when CJ API is unavailable) ────────────────────────────

def _sample_products(category: str) -> list[dict]:
    return [
        {"pid": "SAMPLE001", "productNameEn": "Wireless Bluetooth Earbuds TWS Pro",
         "categoryName": category, "sellPrice": "8.50", "productImage": ""},
        {"pid": "SAMPLE002", "productNameEn": "LED Ring Light 10 inch with Tripod",
         "categoryName": category, "sellPrice": "12.00", "productImage": ""},
        {"pid": "SAMPLE003", "productNameEn": "Adjustable Phone Stand Holder",
         "categoryName": category, "sellPrice": "3.20", "productImage": ""},
        {"pid": "SAMPLE004", "productNameEn": "Silicone Kitchen Utensil Set 5pc",
         "categoryName": category, "sellPrice": "6.80", "productImage": ""},
        {"pid": "SAMPLE005", "productNameEn": "Stainless Steel Insulated Bottle 500ml",
         "categoryName": category, "sellPrice": "4.50", "productImage": ""},
    ]


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()   # stdio transport by default (what Claude Desktop expects)
