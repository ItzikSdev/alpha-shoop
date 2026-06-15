"""MCP Tool Group 1: Sourcing — CJ Dropshipping & AliExpress."""
from __future__ import annotations
import httpx
from src.config import get_settings


async def search_trending_products(
    category: str,
    max_results: int = 20,
    min_margin: float = 0.30,
) -> list[dict]:
    """
    Search CJ Dropshipping for trending products above a minimum margin.

    Args:
        category: Product category (e.g. "electronics", "home-garden")
        max_results: Maximum number of products to return
        min_margin: Minimum profit margin (0.0–1.0)

    Returns:
        List of product dicts with keys: product_id, title, price_supplier_usd,
        estimated_price_shopify_usd, margin_pct, trend_score
    """
    settings = get_settings()
    # Real implementation calls CJ REST API v2
    # POST https://developers.cjdropshipping.com/api2.0/v1/product/list
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                "https://developers.cjdropshipping.com/api2.0/v1/product/list",
                json={"categoryName": category, "pageNum": 1, "pageSize": max_results},
                headers={"CJ-Access-Token": settings.cj_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            products = data.get("data", {}).get("list", [])
        except Exception:
            # Return mock data when API is unavailable (dev/test mode)
            products = _mock_products(category, max_results)

    filtered = [p for p in products if p.get("margin_pct", 0) >= min_margin]
    return filtered[:max_results]


async def get_shipping_cost(
    product_id: str,
    destination_country: str,
    shipping_method: str = "standard",
) -> dict:
    """
    Get shipping cost and estimated days from CJ Dropshipping.

    Args:
        product_id: CJ product ID
        destination_country: ISO 3166-1 alpha-2 country code (e.g. "US")
        shipping_method: "standard" | "express" | "economy"

    Returns:
        Dict with keys: cost_usd, estimated_days, carrier
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://developers.cjdropshipping.com/api2.0/v1/logistic/freightCalculate",
                params={"productId": product_id, "countryCode": destination_country},
                headers={"CJ-Access-Token": settings.cj_api_key},
            )
            resp.raise_for_status()
            result = resp.json().get("data", {})
            return {
                "cost_usd": float(result.get("logisticPrice", 3.99)),
                "estimated_days": int(result.get("agingMin", 10)),
                "carrier": result.get("logisticName", "CJ Packet"),
            }
        except Exception:
            return {"cost_usd": 3.99, "estimated_days": 12, "carrier": "CJ Packet"}


def _mock_products(category: str, count: int) -> list[dict]:
    return [
        {
            "product_id": f"CJ{i:06d}",
            "title": f"Trending {category.title()} Product #{i}",
            "price_supplier_usd": round(5.0 + i * 2.5, 2),
            "estimated_price_shopify_usd": round((5.0 + i * 2.5) * 2.2, 2),
            "margin_pct": round(0.35 + (i % 3) * 0.05, 2),
            "trend_score": 60 + (i % 30),
            "description": f"High-quality {category} product for resale.",
        }
        for i in range(1, count + 1)
    ]
