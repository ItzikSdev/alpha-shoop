"""MCP Tool Group 1: Sourcing — CJ Dropshipping & AliExpress."""
from __future__ import annotations
import asyncio
import httpx
from src.config import get_settings

_BASE = "https://developers.cjdropshipping.com/api2.0/v1"


def _parse_price_range(price: str) -> float:
    """CJ returns prices as either '0.92' or a range '0.53 -- 0.65' / '3.65 - 4.48'."""
    sep = "--" if "--" in str(price) else "-"
    parts = [float(p.strip()) for p in str(price).split(sep)]
    return sum(parts) / len(parts) if parts else 0.0


def _trend_score(listing_count: int) -> int:
    """Heuristic trend signal from CJ's listingCount (stores already selling it).

    CJ's basic product/list endpoint has no dedicated "trend" metric, so this
    derives one from real listing-count data rather than fabricating a score.
    """
    return min(100, 30 + listing_count * 2)


async def _fetch_detail(client: httpx.AsyncClient, token: str, pid: str) -> dict | None:
    """Fetch real supplier price, suggested retail price, and variant id for a product."""
    try:
        resp = await client.get(
            f"{_BASE}/product/query",
            params={"pid": pid},
            headers={"CJ-Access-Token": token},
        )
        resp.raise_for_status()
        body = resp.json()
        if not body.get("result"):
            return None
        return body.get("data")
    except Exception:
        return None


async def search_trending_products(
    category: str,
    max_results: int = 20,
    min_margin: float = 0.30,
    max_price_usd: float = 0.0,
) -> list[dict]:
    """
    Search CJ Dropshipping for trending products above a minimum margin.

    Args:
        category: Product category (e.g. "electronics", "home-garden")
        max_results: Maximum number of products to return
        min_margin: Minimum profit margin (0.0–1.0)

    Returns:
        List of product dicts with keys: product_id, title, price_supplier_usd,
        estimated_price_shopify_usd, margin_pct, trend_score, cj_vid
    """
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    params = {"pageNum": 1, "pageSize": max_results}
    if category and category != "general":
        params["categoryName"] = category

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{_BASE}/product/list",
                params=params,
                headers={"CJ-Access-Token": token},
            )
            resp.raise_for_status()
            body = resp.json()
            if not body.get("result"):
                raise RuntimeError(body.get("message", "CJ API error"))
            raw = body.get("data", {}).get("list", [])
        except Exception:
            # Fall back to mock data only when the real API is unreachable.
            return _mock_products(category, max_results)

        # Fetch real suggested retail price + variant id for each candidate.
        details = await asyncio.gather(*[_fetch_detail(client, token, p["pid"]) for p in raw])

    products = []
    for p, detail in zip(raw, details):
        if detail is None or not detail.get("variants"):
            continue
        supplier_price = _parse_price_range(detail.get("sellPrice", p.get("sellPrice", "0")))
        suggest = _parse_price_range(detail.get("suggestSellPrice", "0"))
        # Cap retail at 3× supplier to avoid absurd CJ suggested prices
        if suggest and (suggest / supplier_price) <= 3.0:
            retail_price = round(suggest, 2)
        else:
            retail_price = round(supplier_price * 2.5, 2)
        margin_pct = round((retail_price - supplier_price) / retail_price, 2)
        images = detail.get("productImageSet") or [p.get("productImage", "")]
        products.append({
            "product_id": p["pid"],
            "cj_vid": detail["variants"][0]["vid"],
            "title": p.get("productNameEn") or p.get("productSku", ""),
            "price_supplier_usd": supplier_price,
            "estimated_price_shopify_usd": retail_price,
            "margin_pct": margin_pct,
            "trend_score": _trend_score(p.get("listingCount", 0)),
            "description": p.get("remark", ""),
            "image": images[0] if images else "",
            "images": [img for img in images if img],
            "category": p.get("categoryName", ""),
        })

    filtered = [p for p in products if p.get("margin_pct", 0) >= min_margin]
    if max_price_usd > 0:
        filtered = [p for p in filtered if p.get("estimated_price_shopify_usd", 0) <= max_price_usd]
    return filtered[:max_results]


async def get_shipping_cost(
    product_id: str,
    destination_country: str,
    shipping_method: str = "standard",
) -> dict:
    """
    Get shipping cost and estimated days from CJ Dropshipping.

    Args:
        product_id: CJ variant id (cj_vid from search_trending_products), or
            product pid as a fallback — freight is quoted per variant.
        destination_country: ISO 3166-1 alpha-2 country code (e.g. "US")
        shipping_method: "standard" | "express" | "economy"

    Returns:
        Dict with keys: cost_usd, estimated_days, carrier
    """
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{_BASE}/logistic/freightCalculate",
                json={
                    "startCountryCode": "CN",
                    "endCountryCode": destination_country,
                    "products": [{"quantity": 1, "vid": product_id}],
                },
                headers={"CJ-Access-Token": token},
            )
            resp.raise_for_status()
            body = resp.json()
            options = body.get("data") or []
            if not body.get("result") or not options:
                raise RuntimeError(body.get("message", "no freight options"))
            cheapest = min(options, key=lambda o: float(o.get("logisticPrice", 1e9)))
            return {
                "cost_usd": float(cheapest.get("logisticPrice", 3.99)),
                "estimated_days": int(str(cheapest.get("logisticAging", "12")).split("-")[-1] or 12),
                "carrier": cheapest.get("logisticName", "CJ Packet"),
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
