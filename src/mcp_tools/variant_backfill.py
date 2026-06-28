"""Backfill Color variants onto already-published products.

The publishing pipeline (sourcing → ecommerce → create_shopify_product) now emits
a Color selector for every newly listed product, because CJ exposes the color in
each variant's `variantKey` ("{Color}-{Size}"). Products listed *before* that fix
only have a Size selector (or no options) and carry no per-variant CJ SKU — so a
customer can't pick a color and fulfillment can't bind the exact (color, size).

`backfill_product_color(...)` repairs one such live product IN PLACE, idempotently:
  1. read the product's CJ pid from product_mappings,
  2. re-read CJ's real (color, size) grid + per-variant vid,
  3. add a "Color" product option (existing size variants are kept),
  4. price + stamp the CJ vid (SKU) on every (color, size) Shopify carries,
  5. create the (color, size) combos Shopify is still missing,
  6. stock every CJ-backed variant,
  7. bind the product to CJ per-variant via connect_store_products.

It is safe to re-run: a product that already has a "Color" option is reported as
`already_done` and left untouched. Combos CJ doesn't carry (e.g. a hand-added
"2-3Y" size) are left without a SKU and not stocked, so they show as sold out
rather than orderable-but-unshippable.
"""
from __future__ import annotations
import logging

import httpx
from sqlalchemy import select

from src.config import get_settings
from src.db.engine import get_session
from src.db.models import ProductMapping
from src.stores import get_store, _current_store
from src.mcp_tools.sourcing import _cj_get, _build_supplier_variants
from src.mcp_tools.shopify import (
    _shopify_gql,
    _GQL_PRODUCT_OPTIONS_CREATE,
    _GQL_SET_PRICE,
    update_inventory,
)

logger = logging.getLogger(__name__)

_GQL_GET_PRODUCT = """
query($id: ID!) {
  product(id: $id) {
    title
    options { id name optionValues { id name } }
    variants(first: 100) {
      nodes {
        id price compareAtPrice
        selectedOptions { name value }
        inventoryItem { id }
      }
    }
  }
}
"""

_GQL_VARIANTS_BULK_DELETE = """
mutation($productId: ID!, $variantsIds: [ID!]!) {
  productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
    userErrors { field message }
  }
}
"""

_GQL_OPTION_VALUES_DELETE = """
mutation($productId: ID!, $option: OptionUpdateInput!, $optionValuesToDelete: [ID!]) {
  productOptionUpdate(productId: $productId, option: $option, optionValuesToDelete: $optionValuesToDelete) {
    userErrors { field message }
  }
}
"""

_GQL_VARIANTS_BULK_CREATE = """
mutation bulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkCreate(productId: $productId, variants: $variants) {
    productVariants {
      id selectedOptions { name value } inventoryItem { id }
    }
    userErrors { field message }
  }
}
"""


async def _fetch_cj_variants(cj_pid: str) -> list[dict]:
    """Re-read CJ's real (color, size, vid) grid for a product. price_ratio is
    irrelevant here (we reuse the live Shopify price), so pass 1.0."""
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    async with httpx.AsyncClient(timeout=30) as client:
        body = await _cj_get(client, "product/query", {"pid": cj_pid}, token)
    detail = body.get("data") or {}
    return _build_supplier_variants(
        detail.get("variants") or [], 1.0, detail.get("description", "")
    )


def _sel(node: dict) -> dict[str, str]:
    return {o["name"]: o["value"] for o in node.get("selectedOptions", [])}


async def backfill_product_color(
    shopify_product_id: str, store_id: str, run_cj_connect: bool = True
) -> dict:
    """Add the missing Color selector + per-variant CJ SKUs to one live product.

    shopify_product_id: full GID ("gid://shopify/Product/123") or numeric id.
    store_id: which store the product belongs to (selects Shopify credentials).
    run_cj_connect: bind the product to CJ at the end (default). Callers that run a
        store-wide connect_store_products themselves (e.g. the ecommerce worker)
        pass False to avoid a redundant per-product store connect.
    Returns a summary dict (status, colors, sizes, created, updated, ...).
    """
    cfg = get_store(store_id)
    if not cfg:
        return {"error": f"store {store_id} not found"}
    _current_store.set(cfg)

    pid = shopify_product_id
    if not pid.startswith("gid://"):
        pid = f"gid://shopify/Product/{pid}"

    # 1. CJ pid from the product mapping.
    async with get_session() as session:
        row = await session.execute(
            select(ProductMapping).where(ProductMapping.shopify_product_id == pid)
        )
        mapping = row.scalar_one_or_none()
    if not mapping:
        return {"error": f"no product_mapping for {pid}"}

    # 2. Current Shopify state.
    data = await _shopify_gql(_GQL_GET_PRODUCT, {"id": pid})
    product = data.get("product")
    if not product:
        return {"error": f"Shopify product {pid} not found"}
    title = product.get("title", "")
    option_names = {o["name"] for o in product.get("options", [])}
    if "Color" in option_names:
        return {"shopify_product_id": pid, "title": title, "status": "already_done"}

    existing = product.get("variants", {}).get("nodes", [])
    base_price = next((v.get("price") for v in existing if v.get("price")), None)
    base_compare = next((v.get("compareAtPrice") for v in existing if v.get("compareAtPrice")), None)

    # 3. CJ grid.
    cj_variants = await _fetch_cj_variants(mapping.supplier_product_id)
    colors: list[str] = []
    for v in cj_variants:
        c = v.get("color", "")
        if c and c not in colors:
            colors.append(c)
    if len(colors) < 2:
        return {"shopify_product_id": pid, "title": title, "status": "no_color_dimension",
                "colors": colors}
    # desired (color, size) -> vid
    desired = {(v["color"], v["size_label"]): v["vid"] for v in cj_variants}

    # 4. Add the Color option (keep existing size variants; Shopify assigns them
    #    the first color value).
    opt_res = await _shopify_gql(_GQL_PRODUCT_OPTIONS_CREATE, {
        "productId": pid,
        "options": [{"name": "Color", "values": [{"name": c} for c in colors]}],
        "variantStrategy": "LEAVE_AS_IS",
    })
    opt_errors = opt_res.get("productOptionsCreate", {}).get("userErrors", [])
    if opt_errors:
        return {"shopify_product_id": pid, "title": title, "status": "option_create_failed",
                "errors": opt_errors}

    # 5. Re-read variants now that they each carry a Color, then price + stamp the
    #    CJ vid (SKU) on every combo CJ carries.
    data = await _shopify_gql(_GQL_GET_PRODUCT, {"id": pid})
    nodes = data.get("product", {}).get("variants", {}).get("nodes", [])
    present: set[tuple[str, str]] = set()
    stock_item_ids: list[str] = []
    bulk_update: list[dict] = []
    for nv in nodes:
        s = _sel(nv)
        key = (s.get("Color", ""), s.get("Size", ""))
        present.add(key)
        vid = desired.get(key)
        if not vid:
            continue  # orphan combo CJ doesn't carry — leave unstocked/no SKU
        entry = {"id": nv["id"], "inventoryItem": {"sku": vid}}
        if base_price:
            entry["price"] = base_price
        if base_compare:
            entry["compareAtPrice"] = base_compare
        bulk_update.append(entry)
        if nv.get("inventoryItem", {}).get("id"):
            stock_item_ids.append(nv["inventoryItem"]["id"])
    if bulk_update:
        await _shopify_gql(_GQL_SET_PRICE, {"productId": pid, "variants": bulk_update})

    # 6. Create the (color, size) combos Shopify is still missing.
    to_create = [
        {
            "optionValues": [
                {"name": color, "optionName": "Color"},
                {"name": size, "optionName": "Size"},
            ],
            "inventoryItem": {"sku": vid, "tracked": True},
            **({"price": base_price} if base_price else {}),
            **({"compareAtPrice": base_compare} if base_compare else {}),
        }
        for (color, size), vid in desired.items()
        if (color, size) not in present
    ]
    created = 0
    if to_create:
        cr = await _shopify_gql(_GQL_VARIANTS_BULK_CREATE, {"productId": pid, "variants": to_create})
        cr_errors = cr.get("productVariantsBulkCreate", {}).get("userErrors", [])
        if cr_errors:
            logger.warning("bulk create errors for %s: %s", pid, cr_errors)
        for nv in cr.get("productVariantsBulkCreate", {}).get("productVariants", []) or []:
            created += 1
            if nv.get("inventoryItem", {}).get("id"):
                stock_item_ids.append(nv["inventoryItem"]["id"])

    # 7. Stock every CJ-backed variant.
    for inv_id in stock_item_ids:
        await update_inventory(product_id=inv_id, location_id="default", quantity=50)

    # 7b. Drop orphan variants/sizes — values the product carried that CJ can't
    #     fulfill (e.g. a hand-added "2-3Y"). Leaving them would show a size that's
    #     sold out in every color. Delete the orphan variants, then the now-unused
    #     size option values so they disappear from the selector entirely.
    cj_sizes = {v["size_label"] for v in cj_variants}
    orphan_variant_ids = [
        nv["id"] for nv in nodes
        if (_sel(nv).get("Color", ""), _sel(nv).get("Size", "")) not in desired
    ]
    removed_orphans = 0
    if orphan_variant_ids:
        dr = await _shopify_gql(_GQL_VARIANTS_BULK_DELETE,
                                {"productId": pid, "variantsIds": orphan_variant_ids})
        if dr.get("productVariantsBulkDelete", {}).get("userErrors"):
            logger.warning("orphan delete errors for %s: %s", pid, dr["productVariantsBulkDelete"]["userErrors"])
        else:
            removed_orphans = len(orphan_variant_ids)
        size_opt = next((o for o in data.get("product", {}).get("options", []) if o["name"] == "Size"), None)
        stale_values = [ov["id"] for ov in (size_opt or {}).get("optionValues", []) if ov["name"] not in cj_sizes]
        if size_opt and stale_values:
            await _shopify_gql(_GQL_OPTION_VALUES_DELETE, {
                "productId": pid,
                "option": {"id": size_opt["id"]},
                "optionValuesToDelete": stale_values,
            })

    # 8. Bind per-variant to CJ so the right color/size ships.
    cj: dict | str = "skipped (caller runs store-wide connect)"
    if run_cj_connect:
        from src.mcp_tools.cj_connect import connect_store_products
        cj = await connect_store_products(store_id)

    return {
        "shopify_product_id": pid,
        "title": title,
        "status": "backfilled",
        "colors": colors,
        "sizes": sorted({k[1] for k in desired}),
        "variants_priced": len(bulk_update),
        "variants_created": created,
        "variants_stocked": len(stock_item_ids),
        "orphans_removed": removed_orphans,
        "cj_connect": {k: cj.get(k) for k in ("connected", "needs_review", "errors")} if isinstance(cj, dict) else cj,
    }
