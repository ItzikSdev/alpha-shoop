"""
Price & stock monitoring — re-checks CJ supplier data for already-listed products
and updates Shopify price/availability when the supplier changes.

This is deliberately NOT an LLM agent: it's a cheap, deterministic job (one CJ
lookup + one Shopify update per mapped product) modeled on what tools like
AutoDS run on a schedule. Reads/writes `product_mappings` (see src/db/models.py).
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy import select

from src.config import get_settings
from src.db.engine import get_session
from src.db.models import ProductMapping
from src.mcp_tools.shopify import _GQL_SET_PRICE, _shopify_gql
from src.mcp_tools.sourcing import _cj_get, _parse_price_range
from src.stores import _current_store, get_store

logger = logging.getLogger(__name__)

# Don't reprice on every tiny supplier fluctuation — only react to a real move.
_REPRICE_THRESHOLD_PCT = 0.05

_GQL_PRODUCT_VARIANTS = """
{ product(id: "%s") { variants(first: 50) { nodes { id price } } } }
"""

_GQL_SET_STATUS = """
mutation productUpdate($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id status }
    userErrors { field message }
  }
}
"""


async def _reprice_shopify_product(shopify_product_id: str, markup_ratio: float) -> bool:
    """Scale every variant's current price by markup_ratio (keeps relative size pricing intact)."""
    data = await _shopify_gql(_GQL_PRODUCT_VARIANTS % shopify_product_id, {})
    nodes = data.get("product", {}).get("variants", {}).get("nodes", [])
    if not nodes:
        return False
    bulk_input = [
        {"id": n["id"], "price": f'{float(n["price"]) * markup_ratio:.2f}'}
        for n in nodes
    ]
    result = await _shopify_gql(_GQL_SET_PRICE, {"productId": shopify_product_id, "variants": bulk_input})
    return not result.get("productVariantsBulkUpdate", {}).get("userErrors")


async def check_store_prices(store_id: str) -> dict:
    """
    Re-check every product_mappings row for this store against CJ's current
    supplier price.

    - Price moved >= 5% vs what we paid at listing time: reprice every Shopify
      variant on that product using the SAME markup ratio (new_cost × ratio),
      not a fixed dollar bump — keeps size-tier pricing relationships intact.
    - CJ no longer returns the listing (delisted/discontinued): set the Shopify
      product to DRAFT. CJ's API doesn't reliably expose a live stock count for
      this catalogue (`inventoryNum` was null on every product checked), so
      "the supplier listing is gone" is the most trustworthy unavailability
      signal actually available — not a real-time quantity check.

    Returns: {checked, repriced: [...], delisted: [...], errors: [...]}
    """
    cfg = get_store(store_id)
    if not cfg:
        return {"error": f"store {store_id} not found"}
    _current_store.set(cfg)

    async with get_session() as session:
        result = await session.execute(select(ProductMapping).where(ProductMapping.store_id == store_id))
        mappings = list(result.scalars().all())

    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key

    checked = 0
    repriced: list[dict] = []
    delisted: list[str] = []
    errors: list[dict] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for m in mappings:
            checked += 1
            try:
                body = await _cj_get(client, "product/query", {"pid": m.supplier_product_id}, token)
            except Exception as exc:
                errors.append({"shopify_product_id": m.shopify_product_id, "error": str(exc)})
                continue

            if not body.get("result") or not body.get("data"):
                try:
                    await _shopify_gql(_GQL_SET_STATUS, {"input": {"id": m.shopify_product_id, "status": "DRAFT"}})
                    delisted.append(m.shopify_product_id)
                except Exception as exc:
                    errors.append({"shopify_product_id": m.shopify_product_id, "error": str(exc)})
                continue

            data = body["data"]
            variant = next((v for v in data.get("variants", []) if v.get("vid") == m.supplier_sku), None)
            current_cost = _parse_price_range(
                str((variant or {}).get("variantSellPrice") or data.get("sellPrice", "0"))
            )
            old_cost = float(m.cost_price)
            if current_cost <= 0 or old_cost <= 0:
                continue

            pct_change = abs(current_cost - old_cost) / old_cost
            if pct_change < _REPRICE_THRESHOLD_PCT:
                continue

            # Keep the same retail/cost ratio we listed at, applied to the new cost —
            # then scale every existing Shopify variant price by how much that moves
            # the representative retail price (not a flat dollar bump).
            markup_ratio = float(m.retail_price) / old_cost
            new_retail = round(current_cost * markup_ratio, 2)
            price_scale = new_retail / float(m.retail_price)
            ok = await _reprice_shopify_product(m.shopify_product_id, price_scale)
            if not ok:
                errors.append({"shopify_product_id": m.shopify_product_id, "error": "reprice failed"})
                continue
            repriced.append({
                "shopify_product_id": m.shopify_product_id,
                "old_cost": old_cost, "new_cost": current_cost,
                "old_retail": float(m.retail_price), "new_retail": new_retail,
                "change_pct": round(pct_change * 100, 1),
            })

            async with get_session() as session:
                row = await session.get(ProductMapping, m.shopify_product_id)
                if row:
                    row.cost_price = current_cost
                    row.retail_price = new_retail

    logger.info(
        "Price/stock check for store %s: %d checked, %d repriced, %d delisted, %d errors",
        store_id, checked, len(repriced), len(delisted), len(errors),
    )
    return {"checked": checked, "repriced": repriced, "delisted": delisted, "errors": errors}
