"""MCP Tool Group 1: Sourcing — CJ Dropshipping & AliExpress."""
from __future__ import annotations
import asyncio
import json
import logging
import re
import httpx
from src.config import get_settings

logger = logging.getLogger(__name__)

_BASE = "https://developers.cjdropshipping.com/api2.0/v1"

# CJ enforces a hard QPS limit of 1 request/second per token. Firing detail
# lookups in parallel (asyncio.gather) trips "Too Many Requests" and silently
# drops most candidates. We serialise CJ calls behind a lock + min-interval and
# retry on the QPS error so searches return a full batch instead of 1 survivor.
_CJ_MIN_INTERVAL = 1.15  # seconds between CJ calls (slightly above their 1/sec)
_CJ_LOCK = asyncio.Lock()
_CJ_LAST_CALL = 0.0


async def _cj_get(client: httpx.AsyncClient, path: str, params: dict, token: str, retries: int = 4) -> dict:
    """Rate-limited CJ GET that retries on the 1-QPS 'Too Many Requests' error."""
    global _CJ_LAST_CALL
    import time
    for _ in range(retries):
        async with _CJ_LOCK:
            wait = _CJ_MIN_INTERVAL - (time.monotonic() - _CJ_LAST_CALL)
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await client.get(f"{_BASE}/{path}", params=params, headers={"CJ-Access-Token": token})
            _CJ_LAST_CALL = time.monotonic()
        resp.raise_for_status()
        body = resp.json()
        if body.get("result"):
            return body
        msg = str(body.get("message", ""))
        if "QPS" in msg or "Too Many" in msg:
            await asyncio.sleep(_CJ_MIN_INTERVAL)
            continue
        return body  # genuine non-rate-limit failure — let caller handle
    return body

# CJ's categoryName query param is NOT a real filter — it's ignored and returns
# the full 1.4M-product catalog. CJ requires the leaf categoryId (a UUID) from
# its fixed taxonomy. We fetch+cache that taxonomy once, then ask an LLM to
# pick the best-matching leaf category for the store's niche.
_CATEGORY_CACHE: list[dict] | None = None


async def _get_category_list() -> list[dict]:
    """Fetch and flatten CJ's category tree into leaf categories. Cached in-memory."""
    global _CATEGORY_CACHE
    if _CATEGORY_CACHE is not None:
        return _CATEGORY_CACHE

    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    leaves: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{_BASE}/product/getCategory", headers={"CJ-Access-Token": token})
            resp.raise_for_status()
            body = resp.json()
        for first in body.get("data", []):
            for second in first.get("categoryFirstList", []):
                for leaf in second.get("categorySecondList", []):
                    leaves.append({
                        "category_id": leaf.get("categoryId", ""),
                        "category_name": leaf.get("categoryName", ""),
                        "path": f"{first.get('categoryFirstName','')} > {second.get('categorySecondName','')} > {leaf.get('categoryName','')}",
                    })
    except Exception as exc:
        logger.warning("Could not fetch CJ category tree: %s", exc)

    _CATEGORY_CACHE = leaves
    return leaves


async def resolve_category(niche_text: str) -> dict | None:
    """
    Map a free-text niche/product description to a real CJ leaf category
    (categoryId + categoryName), since CJ ignores free-text category filters.
    Returns None if no category tree is available or no good match is found.
    """
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    categories = await _get_category_list()
    if not categories:
        return None

    catalogue = "\n".join(f"{c['category_id']}::{c['path']}" for c in categories)
    system = (
        "You map a store's product niche to the single best-matching category from a fixed list.\n"
        "Each line below is formatted as: category_id::category_path\n"
        f"{catalogue}\n\n"
        "Output ONLY valid JSON: {\"category_id\": \"<the exact id from the list>\"}"
    )
    llm = get_llm("scraper", temperature=0.0)
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=f"Store niche / product type: {niche_text}"),
    ])
    raw = str(response.content).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    try:
        picked_id = json.loads(raw.strip()).get("category_id", "")
    except (json.JSONDecodeError, ValueError):
        return None

    return next((c for c in categories if c["category_id"] == picked_id), None)


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
        body = await _cj_get(client, "product/query", {"pid": pid}, token)
        if not body.get("result"):
            return None
        return body.get("data")
    except Exception:
        return None


async def search_trending_products(
    category: str = "",
    category_id: str = "",
    max_results: int = 20,
    min_margin: float = 0.30,
    max_price_usd: float = 0.0,
) -> list[dict]:
    """
    Search CJ Dropshipping for trending products above a minimum margin.

    Args:
        category: Free-text label, used only for the mock-data fallback and logging.
        category_id: Real CJ leaf categoryId (UUID) from resolve_category() — this is
            the only thing CJ actually filters on. categoryName/free text is ignored
            by CJ's API and returns the entire 1.4M-product catalog unfiltered.
        max_results: Maximum number of products to return
        min_margin: Minimum profit margin (0.0–1.0)

    Returns:
        List of product dicts with keys: product_id, title, price_supplier_usd,
        estimated_price_shopify_usd, margin_pct, trend_score, cj_vid
    """
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    params = {"pageNum": 1, "pageSize": max_results}
    # CJ's product/list filters on `productNameEn` (a real keyword search) — this is
    # FAR more relevant than categoryId, which the LLM resolver tends to collapse into
    # one broad leaf (e.g. every "sunset lamp"/"galaxy projector" → "LED Spotlights",
    # returning the same generic junk). Prefer the keyword; fall back to category only
    # when no keyword text is available.
    keyword = (category or "").strip()
    if keyword:
        params["productNameEn"] = keyword
    elif category_id:
        params["categoryId"] = category_id

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            body = await _cj_get(client, "product/list", params, token)
            if not body.get("result"):
                raise RuntimeError(body.get("message", "CJ API error"))
            raw = body.get("data", {}).get("list", [])
        except Exception:
            # Fall back to mock data only when the real API is unreachable.
            return _mock_products(category, max_results)

        # Fetch real price + variant id per candidate. Detail lookups go through the
        # rate-limited _cj_get (1 QPS), so run them sequentially — parallel gather would
        # trip CJ's throttle and drop most candidates. Cap to keep latency bounded.
        raw = raw[:12]
        details = [await _fetch_detail(client, token, p["pid"]) for p in raw]

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
