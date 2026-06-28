"""
CJ ⇄ Shopify product connection — automates the "Product Connection" step that
otherwise has to be done by hand in the CJ panel for every new store.

Once a Shopify product is *connected* to its CJ product/variant, the installed
CJ Dropshipping Shopify app can auto-fulfill paid orders (place the CJ order +
push tracking back to Shopify) with no custom poller. See memory cj_app_fulfillment.

We don't have to guess the CJ match by product name: our own `product_mappings`
table already records, per Shopify product, the CJ pid (`supplier_product_id`)
and CJ vid (`supplier_sku`) chosen at listing time. This module reads that table
and pushes those mappings into CJ via the connection API.

CJ API (https://developers.cjdropshipping.com/api2.0/v1), CJ-Access-Token header:
  GET    /shop/getShops                 → authorized shops (id, name, type)
  GET    /shop/product/queryPage        → a shop's products (platformProductId…)
  GET    /shop/product/queryDetail      → shop product + its platformVariantId(s)
  GET    /product/conn/connection       → existing connections
  POST   /product/conn/connection       → create a connection (bind shopify↔CJ)
  DELETE /product/conn/connection       → remove a connection
All connection/shop calls obey CJ's 1-QPS limit via the shared lock in sourcing.
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx
from sqlalchemy import select

from src.config import get_settings
from src.db.engine import get_session
from src.db.models import ProductMapping
from src.mcp_tools import sourcing
from src.mcp_tools.sourcing import _BASE, _cj_get
from src.stores import _current_store, get_store

logger = logging.getLogger(__name__)

# CJ shops we must never auto-connect to (user-excluded). Matched case-insensitively
# against a shop's aliasName/name. (Removing the shop entirely is a CJ-panel action;
# this just keeps our agents from ever binding products to it.)
_EXCLUDED_SHOP_NAMES = {"click and collectix"}


def _is_excluded(shop: dict) -> bool:
    names = {str(shop.get("aliasName", "")).strip().lower(), str(shop.get("name", "")).strip().lower()}
    return bool(names & _EXCLUDED_SHOP_NAMES)


def _token() -> str:
    settings = get_settings()
    return settings.cj_mcp_key or settings.cj_api_key


def _ok(body: dict) -> bool:
    """CJ isn't consistent across endpoints: the product API answers with
    `result:true`/`code:200`, while the shop/connection API answers with
    `success:true`/`code:0`. Accept either so a real success isn't read as a
    failure (and an empty list isn't returned as if the call had errored)."""
    return bool(body.get("result") or body.get("success") or body.get("code") in (0, 200))


def _numeric_shopify_id(gid: str) -> str:
    """`gid://shopify/Product/123` → `123`. CJ's shop API uses the bare numeric id."""
    return gid.rsplit("/", 1)[-1] if gid else gid


async def _cj_send(client: httpx.AsyncClient, method: str, path: str, json_body: dict, token: str) -> dict:
    """Rate-limited POST/DELETE that shares sourcing's 1-QPS lock with the GET path.

    The connection endpoints aren't covered by `_cj_get` (GET only), but they hit
    the same per-token QPS ceiling, so reuse the same lock + min-interval rather
    than risk interleaving a POST between two throttled GETs and tripping CJ.
    """
    async with sourcing._CJ_LOCK:
        wait = sourcing._CJ_MIN_INTERVAL - (time.monotonic() - sourcing._CJ_LAST_CALL)
        if wait > 0:
            await asyncio.sleep(wait)
        resp = await client.request(
            method, f"{_BASE}/{path}", json=json_body,
            headers={"CJ-Access-Token": token, "Content-Type": "application/json"},
        )
        sourcing._CJ_LAST_CALL = time.monotonic()
    try:
        return resp.json()
    except ValueError:
        return {"result": False, "message": f"non-JSON CJ response ({resp.status_code})"}


# ── Low-level tools (also usable directly by an agent) ─────────────────────────

async def list_cj_shops() -> list[dict]:
    """Return the stores authorized inside CJ (the CJ app's connected shops).

    Each item: {id, name, type, status, countryCode}. `id` is the `shopId` the
    other connection endpoints need. Match `name`/`type` against your Shopify
    domain to find which CJ shop corresponds to one of our stores.
    """
    token = _token()
    async with httpx.AsyncClient(timeout=20) as client:
        body = await _cj_get(client, "shop/getShops", {}, token)
    if not _ok(body):
        logger.warning("CJ getShops failed: %s", body.get("message"))
        return []
    data = body.get("data")
    return data if isinstance(data, list) else data.get("list", []) if isinstance(data, dict) else []


async def resolve_cj_shop_for_store(store_id: str) -> str | None:
    """Find the CJ shopId that corresponds to one of our stores, so agents don't
    need a hand-supplied id. Matches CJ's shop `name` (the myshopify subdomain
    prefix, e.g. "0c108b-20") against the store's shopify_domain, then falls back
    to a case-insensitive match on the store name / CJ aliasName."""
    cfg = get_store(store_id)
    if not cfg:
        return None
    prefix = (cfg.shopify_domain or "").split(".")[0].strip().lower()
    name = (cfg.name or "").strip().lower()
    shops = [s for s in await list_cj_shops() if not _is_excluded(s)]
    for s in shops:
        if s.get("type") != "shopify":
            continue
        if prefix and str(s.get("name", "")).strip().lower() == prefix:
            return str(s.get("id"))
    for s in shops:
        if s.get("type") != "shopify":
            continue
        alias = str(s.get("aliasName", "")).strip().lower()
        if name and (alias == name or name in alias or alias in name):
            return str(s.get("id"))
    return None


async def list_connections(shop_id: str) -> set[str]:
    """Return the set of platformProductIds already connected for this shop, so a
    re-run binds only the not-yet-connected products (idempotent)."""
    token = _token()
    connected: set[str] = set()
    async with httpx.AsyncClient(timeout=20) as client:
        page = 1
        while True:
            body = await _cj_get(
                client, "product/conn/connection",
                {"shopId": shop_id, "page": page, "pageSize": 100}, token,
            )
            if not _ok(body):
                break
            data = body.get("data")
            rows = data.get("list", []) if isinstance(data, dict) else (data or [])
            if not rows:
                break
            for r in rows:
                connected.add(str(r.get("platformProductId")))
            if len(rows) < 100:
                break
            page += 1
    return connected


async def get_shop_product_variants(shop_id: str, platform_product_ids: list[str]) -> dict[str, list[dict]]:
    """Map each Shopify platformProductId → its variants [{platformVariantId, sku, title}].

    queryDetail accepts up to 10 product ids per call; we batch accordingly.
    """
    token = _token()
    out: dict[str, list[dict]] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(platform_product_ids), 10):
            chunk = platform_product_ids[i:i + 10]
            body = await _cj_get(
                client, "shop/product/queryDetail",
                {"shopId": shop_id, "platformProductIds": chunk}, token,
            )
            if not _ok(body):
                logger.warning("CJ queryDetail failed for %s: %s", chunk, body.get("message"))
                continue
            for p in body.get("data", []) or []:
                out[str(p.get("platformProductId"))] = [
                    {
                        "platformVariantId": str(v.get("platformVariantId")),
                        "sku": v.get("platformVariantSku", ""),
                        "title": v.get("platformVariantTitle", ""),
                    }
                    for v in p.get("variants", []) or []
                ]
    return out


async def connect_product(
    shop_id: str,
    platform_product_id: str,
    cj_product_id: str,
    variant_list: list[dict],
    logistics: str = "CJPacket Ordinary",
    target_country_code: str = "US",
    default_area: int = 1,
) -> dict:
    """Bind one Shopify product (+variants) to its CJ product so CJ auto-fulfills it.

    variant_list: [{"platformVariantId": str, "cjVariantId": str}, ...].
    Returns {"ok": bool, "message": str}.
    """
    payload = {
        "shopId": shop_id,
        "platformProductId": platform_product_id,
        "cjProductId": cj_product_id,
        "defaultArea": default_area,
        "logistics": logistics,
        "targetCountryCode": target_country_code,
        "variantList": variant_list,
    }
    token = _token()
    async with httpx.AsyncClient(timeout=30) as client:
        body = await _cj_send(client, "POST", "product/conn/connection", payload, token)
    return {"ok": _ok(body), "message": str(body.get("message", ""))}


# ── Orchestration: connect every mapped product for a store ────────────────────

async def _resolve_logistics(vid: str, country: str, fallback: str) -> str:
    """Pick the shipping line for a product by asking CJ's own freight quote for
    this variant+country (requirement #2: a real, valid line per country — e.g.
    CJPacket Liquid Line for liquids — instead of a blind hardcoded default).
    Falls back to `fallback` if CJ returns no options."""
    from src.mcp_tools.sourcing import get_shipping_cost
    quote = await get_shipping_cost(vid, country)
    return quote.get("carrier") or fallback


async def connect_store_products(
    store_id: str,
    shop_id: str = "",
    logistics: str = "auto",
    target_country_code: str = "US",
) -> dict:
    """
    Push every `product_mappings` row for this store into CJ as a product
    connection, so the CJ app can auto-fulfill that store's orders.

    `logistics="auto"` (default) resolves the shipping line per product from CJ's
    live freight quote for `target_country_code` — this sets requirement #2 (the
    preferred shipping method) automatically and correctly per product. Pass an
    explicit line name (e.g. "CJPacket Ordinary") to force one for every product.

    For each mapped Shopify product we already hold the CJ pid (supplier_product_id)
    and CJ vid (supplier_sku). We fetch the Shopify product's variants from CJ's
    shop API to learn its `platformVariantId`(s), then bind:

      - single-variant product → bind that variant to our stored CJ vid.
      - multi-variant product → our table stores ONE cj vid, which can't be
        trusted to be the right SKU for every size. Rather than silently bind all
        sizes to one CJ variant (wrong shipments), we report it under
        `needs_review` with its variant ids so it can be mapped deliberately.

    `shop_id` comes from list_cj_shops() (match the CJ shop to this store).

    Returns: {checked, connected: [...], skipped_no_variant: [...],
              needs_review: [...], errors: [...]}.
    """
    cfg = get_store(store_id)
    if not cfg:
        return {"error": f"store {store_id} not found"}
    _current_store.set(cfg)

    if not shop_id:
        shop_id = await resolve_cj_shop_for_store(store_id) or ""
        if not shop_id:
            return {"error": f"no CJ-authorized Shopify shop matches store {store_id} "
                             "(install/authorize the CJ app for this store first)"}

    async with get_session() as session:
        result = await session.execute(select(ProductMapping).where(ProductMapping.store_id == store_id))
        mappings = list(result.scalars().all())

    if not mappings:
        return {"shop_id": shop_id, "checked": 0, "connected": [], "skipped_no_variant": [],
                "already_connected": [], "needs_review": [], "errors": [],
                "message": "no product_mappings for store"}

    by_platform_id = {_numeric_shopify_id(m.shopify_product_id): m for m in mappings}
    existing = await list_connections(shop_id)
    variants_by_product = await get_shop_product_variants(shop_id, list(by_platform_id.keys()))

    connected: list[dict] = []
    already_connected: list[str] = []
    skipped_no_variant: list[str] = []
    needs_review: list[dict] = []
    errors: list[dict] = []

    for platform_id, m in by_platform_id.items():
        if platform_id in existing:
            already_connected.append(m.shopify_product_id)
            continue
        variants = variants_by_product.get(platform_id, [])
        if not variants:
            # CJ's shop API never returned this product — usually means the CJ app
            # hasn't synced it yet, or the GID→numeric id didn't match.
            skipped_no_variant.append(m.shopify_product_id)
            continue
        if len(variants) > 1:
            # Each Shopify variant carries its CJ vid in its SKU (stamped at
            # publish time), so we can bind every (color, size) to the exact CJ
            # SKU and CJ ships precisely what the customer ordered. If any variant
            # is missing that vid (e.g. an older product published before this), we
            # can't trust a blanket bind — report it for deliberate mapping.
            bound = [
                {"platformVariantId": v["platformVariantId"], "cjVariantId": v["sku"]}
                for v in variants if (v.get("sku") or "").isdigit()
            ]
            if len(bound) != len(variants):
                needs_review.append({
                    "shopify_product_id": m.shopify_product_id,
                    "cj_product_id": m.supplier_product_id,
                    "cj_variant_id": m.supplier_sku,
                    "platform_variants": variants,
                    "reason": "multi-variant product; some variants missing CJ vid in SKU",
                })
                continue
            variant_list = bound
        else:
            variant_list = [{"platformVariantId": variants[0]["platformVariantId"], "cjVariantId": m.supplier_sku}]
        line = (
            await _resolve_logistics(m.supplier_sku, target_country_code, "CJPacket Ordinary")
            if logistics == "auto" else logistics
        )
        try:
            res = await connect_product(
                shop_id=shop_id,
                platform_product_id=platform_id,
                cj_product_id=m.supplier_product_id,
                variant_list=variant_list,
                logistics=line,
                target_country_code=target_country_code,
            )
        except Exception as exc:  # network / unexpected CJ error — keep going
            errors.append({"shopify_product_id": m.shopify_product_id, "error": str(exc)})
            continue
        if res["ok"]:
            connected.append({"shopify_product_id": m.shopify_product_id, "cj_product_id": m.supplier_product_id, "logistics": line})
        else:
            errors.append({"shopify_product_id": m.shopify_product_id, "error": res["message"]})

    logger.info(
        "CJ connection for store %s (shop %s): %d checked, %d connected, %d already, "
        "%d need review, %d no-variant, %d errors",
        store_id, shop_id, len(by_platform_id), len(connected), len(already_connected),
        len(needs_review), len(skipped_no_variant), len(errors),
    )
    return {
        "shop_id": shop_id,
        "checked": len(by_platform_id),
        "connected": connected,
        "already_connected": already_connected,
        "skipped_no_variant": skipped_no_variant,
        "needs_review": needs_review,
        "errors": errors,
    }
