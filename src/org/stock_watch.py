"""
Standing rule (owner, 2026-08-09): a product that is OUT OF STOCK at CJ must be
removed from the store immediately.

WHY THIS EXISTS AS ITS OWN CHECK. `shopify.cleanup_out_of_stock_products` audits
Shopify-side stock, and for this catalog it is structurally blind: every variant
is a CJ dropship item with `inventoryItem.tracked = false`, so the "no stock"
condition it looks for can never be true. It reported 0 bad out of 29 products
while nothing at all was verifying supplier availability. `cj_product_inventory`
gates product CREATION only — nothing ever re-checked a product after it went
live, so a discontinued item stays purchasable until a customer pays for
something Milo cannot fulfil.

HOW AVAILABILITY IS DETERMINED. Each Shopify variant's `sku` IS the CJ variant
id (Sol writes it that way at creation), so stock is read per-variant via CJ's
`query_cj_inventory {vid}` — no `product_mappings` row required, which matters
because 22 of 29 live products have no mapping at all. A product counts as OUT
only when EVERY variant resolves and every one reports zero across all
warehouses.

SAFETY. This deletes real products automatically, so it fails CLOSED:
  - a variant whose lookup errors/times out is UNKNOWN, and any unknown variant
    disqualifies the product from removal (a CJ outage must never wipe the
    catalog),
  - a product must read zero on two CONSECUTIVE checks before removal, so a
    transient blip can't delete anything,
  - at most `max_removals` products are removed per cycle,
  - every removal is announced to Telegram.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from src.org.models import Company, get_company, update_company

logger = logging.getLogger(__name__)

# Bounded blast radius: if CJ ever reports the whole catalog as zero, this caps
# the damage at a handful of products per cycle instead of the entire store.
_MAX_REMOVALS_PER_CYCLE = 3
_CJ_QPS_SLEEP = 1.2  # CJ is globally rate-limited to ~1 request/second


async def _variant_stock(cj, vid: str) -> int | None:
    """Total CJ inventory for one variant id. None = UNKNOWN (lookup failed),
    which is deliberately different from 0 and never triggers a removal."""
    try:
        res = await asyncio.wait_for(cj.call("query_cj_inventory", {"vid": vid}), timeout=45)
    except Exception as exc:  # noqa: BLE001
        # Log the exception TYPE, not just str(exc): asyncio.TimeoutError
        # stringifies to "" so a timeout logged as "%s" looks like a blank error
        # and is indistinguishable from a real failure.
        logger.warning("CJ stock lookup failed for vid=%s: %s: %s",
                       vid, type(exc).__name__, exc or "(no detail)")
        return None
    if isinstance(res, str):        # CJ returns a human-readable error string
        return None
    if not isinstance(res, list):
        return None
    total = 0
    for row in res:
        if not isinstance(row, dict):
            return None
        total += int(row.get("totalInventoryNum") or 0)
    return total


async def check_store_stock(store_slug: str = "alphaforbaby", remove: bool = False,
                            max_removals: int = _MAX_REMOVALS_PER_CYCLE) -> dict:
    """Read real CJ stock for every live product. With `remove=True`, delete the
    ones confirmed out of stock on two consecutive checks.

    Returns a report; never raises — a stock check must not break the heartbeat.
    """
    from src.stores import list_stores, _current_store
    from src.mcp_tools.shopify import _shopify_gql
    from src.cj_mcp import CJMCPClient

    store = next((s for s in list_stores() if s.store_id == store_slug), None)
    if store is None:
        return {"error": f"unknown store {store_slug!r}"}

    token = _current_store.set(store)
    try:
        data = await _shopify_gql(
            '{ products(first:100, query:"status:active"){ nodes{ id title '
            'variants(first:100){ nodes{ sku } } } } }', {})
    except Exception as exc:  # noqa: BLE001
        _current_store.reset(token)
        return {"error": f"couldn't list products: {exc}"}
    products = data.get("products", {}).get("nodes", [])

    out_of_stock: list[dict] = []
    in_stock = unknown = 0
    try:
        async with CJMCPClient() as cj:
            for p in products:
                vids = [v["sku"] for v in p.get("variants", {}).get("nodes", []) if v.get("sku")]
                if not vids:
                    unknown += 1
                    continue
                # EARLY EXIT: one variant with stock proves the product is
                # available, so stop there. Checking every variant meant 368 CJ
                # calls for a 30-product catalog at ~1 QPS — CJ throttled the
                # whole sweep and every lookup came back as a timeout, which the
                # fail-closed rule then (correctly) reported as 30 unknowns.
                # Only a product where every variant reads zero needs the full
                # scan, and those are rare.
                totals: list[int | None] = []
                for vid in vids:
                    t = await _variant_stock(cj, vid)
                    totals.append(t)
                    await asyncio.sleep(_CJ_QPS_SLEEP)
                    if t:                    # in stock — no need to check the rest
                        break
                if any(t is None for t in totals):
                    unknown += 1            # fail CLOSED — never remove on doubt
                elif any(t for t in totals):
                    in_stock += 1
                else:
                    out_of_stock.append({"id": p["id"], "title": p["title"],
                                         "variants": len(vids)})
    except Exception as exc:  # noqa: BLE001
        logger.exception("CJ stock sweep failed")
        _current_store.reset(token)
        return {"error": f"CJ sweep failed: {exc}", "scanned": len(products)}

    # Two-strike rule: only act on a product that was ALSO zero last cycle.
    company = get_company()
    prior = set((company.daemon.get("cj_zero_stock_ids") or []) if company else [])
    now_ids = {p["id"] for p in out_of_stock}
    confirmed = [p for p in out_of_stock if p["id"] in prior]
    first_strike = [p for p in out_of_stock if p["id"] not in prior]

    def _remember(c: Company, ids: list[str] = sorted(now_ids)) -> None:
        c.daemon["cj_zero_stock_ids"] = ids
        c.daemon["cj_stock_checked_at"] = datetime.now(timezone.utc).isoformat()
    try:
        update_company(_remember)
    except Exception:  # noqa: BLE001
        pass

    removed: list[dict] = []
    if remove and confirmed:
        from src.org.telegram import post_as
        for p in confirmed[:max_removals]:
            try:
                res = await _shopify_gql(
                    "mutation($input: ProductDeleteInput!){ productDelete(input:$input)"
                    "{ deletedProductId userErrors{ field message } } }",
                    {"input": {"id": p["id"]}})
                errs = res.get("productDelete", {}).get("userErrors") or []
                if errs:
                    logger.warning("Couldn't delete %s: %s", p["title"], errs)
                    continue
                removed.append(p)
                await post_as(
                    "Sol", "Product Sourcer & Copywriter",
                    f"🗑 Removed *{p['title']}* — CJ shows zero stock on every variant "
                    "(confirmed on two consecutive checks). Standing rule: out of stock at "
                    "CJ ⇒ off the store immediately.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Delete failed for %s: %s", p["title"], exc)
    _current_store.reset(token)

    return {
        "scanned": len(products),
        "in_stock": in_stock,
        "unknown": unknown,
        "out_of_stock": out_of_stock,
        "first_strike": [p["title"] for p in first_strike],
        "confirmed_out": [p["title"] for p in confirmed],
        "removed": [p["title"] for p in removed],
    }
