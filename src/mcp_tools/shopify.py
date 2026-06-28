"""MCP Tool Group 3: Shopify Admin GraphQL API 2024-07."""
from __future__ import annotations
import asyncio
import logging
import httpx
from src.config import get_settings
from src.stores import _current_store

logger = logging.getLogger(__name__)

_GQL_CREATE_PRODUCT = """
mutation productCreate($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
  productCreate(product: $product, media: $media) {
    product {
      id title status
      variants(first: 1) { nodes { id inventoryItem { id } } }
      images(first: 10) { nodes { url } }
    }
    userErrors { field message }
  }
}
"""

_GQL_SET_PRICE = """
mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants { id price compareAtPrice }
    userErrors { field message }
  }
}
"""

_GQL_PRODUCT_OPTIONS_CREATE = """
mutation productOptionsCreate($productId: ID!, $options: [OptionCreateInput!]!, $variantStrategy: ProductOptionCreateVariantStrategy) {
  productOptionsCreate(productId: $productId, options: $options, variantStrategy: $variantStrategy) {
    userErrors { field message }
    product {
      id
      variants(first: 50) {
        nodes { id selectedOptions { name value } inventoryItem { id } }
      }
    }
  }
}
"""

_GQL_CREATE_MEDIA = """
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media { mediaContentType }
    mediaUserErrors { field message }
  }
}
"""

_GQL_SET_INVENTORY = """
mutation inventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
  inventoryAdjustQuantities(input: $input) {
    inventoryAdjustmentGroup {
      changes { name delta quantityAfterChange }
    }
    userErrors { field message }
  }
}
"""

_GQL_GET_LOCATION = """
{ locations(first: 1) { nodes { id } } }
"""

_GQL_CREATE_COLLECTION = """
mutation collectionCreate($input: CollectionInput!) {
  collectionCreate(input: $input) {
    collection { id title handle }
    userErrors { field message }
  }
}
"""

_GQL_ADD_TO_COLLECTION = """
mutation collectionAddProducts($id: ID!, $productIds: [ID!]!) {
  collectionAddProducts(id: $id, productIds: $productIds) {
    collection { id title }
    userErrors { field message }
  }
}
"""

_GQL_FIND_COLLECTION = """
query findCollection($title: String!) {
  collections(first: 1, query: $title) {
    nodes { id title }
  }
}
"""

_GQL_LIST_COLLECTIONS_WITH_COUNTS = """
{ collections(first: 50) { nodes { title handle productsCount { count } } } }
"""

_GQL_FILE_CREATE = """
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id ... on MediaImage { image { url } } }
    userErrors { field message }
  }
}
"""

_GQL_GET_FIRST_PRODUCT_IMAGE = """
{ products(first: 10) { nodes { images(first: 1) { nodes { url } } } } }
"""

_GQL_STAGED_UPLOADS_CREATE = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
"""

_GQL_LIST_PRODUCTS = """
query listProducts {
  products(first: 50, sortKey: CREATED_AT) {
    nodes {
      id title status
      images(first: 1) { nodes { url } }
    }
  }
}
"""

_GQL_DELETE_PRODUCT = """
mutation productDelete($input: ProductDeleteInput!) {
  productDelete(input: $input) {
    deletedProductId
    userErrors { field message }
  }
}
"""


def _gid_to_id(gid: str) -> str:
    """Extract numeric ID from Shopify GID. 'gid://shopify/Product/12345' → '12345'"""
    return gid.rsplit("/", 1)[-1]


def _shopify_creds() -> tuple[str, str]:
    """Return (domain, access_token) — uses per-run store if set, else env config."""
    store = _current_store.get(None)
    if store:
        return store.shopify_domain, store.shopify_access_token
    settings = get_settings()
    return settings.shopify_store_domain, settings.shopify_access_token


async def _shopify_gql(query: str, variables: dict) -> dict:
    domain, token = _shopify_creds()
    url = f"https://{domain}/admin/api/2024-07/graphql.json"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            json={"query": query, "variables": variables},
            headers={
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("errors"):
            raise RuntimeError(str(body["errors"]))
        return body.get("data", {})


async def _shopify_rest(method: str, path: str, body: dict | None = None) -> dict:
    """Simple Shopify Admin REST API call."""
    domain, token = _shopify_creds()
    url = f"https://{domain}/admin/api/2024-07/{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(
            method,
            url,
            json=body,
            headers={
                "X-Shopify-Access-Token": token,
                "Content-Type": "application/json",
            },
        )
        if resp.status_code == 404 and method == "GET":
            return {}  # asset/resource doesn't exist yet — treat as empty, not an error
        if resp.status_code >= 400:
            raise RuntimeError(f"{method} {path} → {resp.status_code}: {resp.text[:500]}")
        return resp.json()


async def _publish_product(product_gid: str) -> None:
    """Publish a product to the Online Store channel via REST (no publications scope needed)."""
    numeric_id = _gid_to_id(product_gid)
    await _shopify_rest("PUT", f"products/{numeric_id}.json", {"product": {"published": True}})


async def create_shopify_product(
    title: str,
    description: str,
    price: float,
    compare_at_price: float,
    images: list[str],
    variants: list[dict],
    video_url: str = "",
) -> dict:
    """
    Create a product in Shopify and set pricing.

    variants: optional per-(color, size) options, each
        {"color": str, "label": str (size), "sku": str (supplier vid),
         "price": float, "compare_at_price": float}. Empty list → single default
        variant priced at `price`/`compare_at_price`. Otherwise we create a
        "Color" and/or "Size" option for whichever dimension has 2+ distinct
        values (so the storefront shows the right selectors + working Add to
        Cart), price each generated variant individually, and stamp its `sku`
        (the CJ variant id) onto the Shopify variant so fulfillment binds the
        exact color/size the customer picked. `color`/`sku` are optional for
        backward compatibility — a size-only list still yields a Size selector.

    Returns:
        Dict with keys: product (dict), success (bool), error (str | None).
        Each node in product["variants"]["nodes"] carries "matched_sku" (the CJ
        vid bound to it, or "" for an auto-generated combo CJ doesn't stock) so
        the caller can skip stocking unfulfillable combos.
    """
    # The CJ vid to stamp on a single-variant product's default variant (binds it
    # to the right CJ SKU even when there are no Color/Size selectors).
    default_sku = (variants[0].get("sku", "") if variants else "")
    media = [
        {"originalSource": url, "alt": title, "mediaContentType": "IMAGE"}
        for url in images if url
    ]
    try:
        data = await _shopify_gql(
            _GQL_CREATE_PRODUCT,
            {
                "product": {
                    "title": title,
                    "descriptionHtml": description,
                    "status": "ACTIVE",
                },
                "media": media or None,
            },
        )
    except Exception as exc:
        return {"product": None, "success": False, "error": str(exc)}

    product = data.get("productCreate", {}).get("product")
    errors = data.get("productCreate", {}).get("userErrors", [])
    if errors or not product:
        return {"product": None, "success": False, "error": str(errors) or "no product returned"}

    # Build a Color and/or Size selector from the supplier variants — only for a
    # dimension that actually varies (2+ distinct values), so a single-color item
    # doesn't get a pointless "Color" dropdown. CJ exposes both dimensions per SKU.
    def _distinct(field: str) -> list[str]:
        seen: list[str] = []
        for v in variants:
            val = (v.get(field) or "").strip()
            if val and val not in seen:
                seen.append(val)
        return seen

    colors = _distinct("color")
    sizes = _distinct("label")
    option_defs: list[tuple[str, list[str]]] = []
    if len(colors) >= 2:
        option_defs.append(("Color", colors))
    if len(sizes) >= 2:
        option_defs.append(("Size", sizes))

    if option_defs and variants:
        def _match_variant(node: dict) -> dict | None:
            sel = {o["name"]: o["value"] for o in node.get("selectedOptions", [])}
            for v in variants:
                if "Color" in sel and (v.get("color", "").strip() != sel["Color"]):
                    continue
                if "Size" in sel and (v.get("label", "").strip() != sel["Size"]):
                    continue
                return v
            return None

        try:
            opt_data = await _shopify_gql(_GQL_PRODUCT_OPTIONS_CREATE, {
                "productId": product["id"],
                "options": [
                    {"name": name, "values": [{"name": val} for val in vals]}
                    for name, vals in option_defs
                ],
                "variantStrategy": "CREATE",
            })
            opt_errors = opt_data.get("productOptionsCreate", {}).get("userErrors", [])
            new_nodes = opt_data.get("productOptionsCreate", {}).get("product", {}).get("variants", {}).get("nodes", [])
            if opt_errors or not new_nodes:
                logger.warning("productOptionsCreate failed for %s: %s", title, opt_errors)
                variants = []  # fall through to single-variant pricing below
            else:
                bulk_input = []
                for nv in new_nodes:
                    match = _match_variant(nv)
                    # Tag every node so the caller stocks only CJ-backed combos —
                    # the cartesian product may include combos CJ doesn't carry.
                    nv["matched_sku"] = (match or {}).get("sku", "")
                    if not match:
                        continue
                    entry = {
                        "id": nv["id"],
                        "price": f'{match["price"]:.2f}',
                        "compareAtPrice": (
                            f'{match["compare_at_price"]:.2f}'
                            if match.get("compare_at_price", 0) > match["price"] else None
                        ),
                    }
                    if match.get("sku"):
                        # Stamp the CJ vid onto the Shopify variant SKU → cj_connect
                        # binds this exact (color, size) to the right CJ SKU.
                        entry["inventoryItem"] = {"sku": match["sku"]}
                    bulk_input.append(entry)
                if bulk_input:
                    await _shopify_gql(_GQL_SET_PRICE, {"productId": product["id"], "variants": bulk_input})
                product["variants"] = {"nodes": new_nodes}
                variants = []  # signal: already priced above, skip default-variant pricing
        except Exception as exc:
            logger.warning("Variant setup failed for %s, falling back to single variant: %s", title, exc)
            variants = []

    if not variants:
        pass  # either no options requested, or already priced via bulk_input above

    # Set price on the default variant (single-variant products only — multi-size
    # products were already priced per-variant above)
    variant_nodes = product.get("variants", {}).get("nodes", [])
    if len(variant_nodes) == 1 and price > 0:
        variant_id = variant_nodes[0]["id"]
        bulk = {
            "id": variant_id,
            "price": f"{price:.2f}",
            "compareAtPrice": f"{compare_at_price:.2f}" if compare_at_price > price else None,
        }
        if default_sku:
            bulk["inventoryItem"] = {"sku": default_sku}
        try:
            await _shopify_gql(
                _GQL_SET_PRICE,
                {"productId": product["id"], "variants": [bulk]},
            )
            product["price"] = price
            product["compare_at_price"] = compare_at_price
            variant_nodes[0]["matched_sku"] = default_sku
        except Exception:
            pass  # price update failure is non-fatal

    # Attach supplier video, if any — separate call so an unexpected format
    # never risks failing the product creation itself (video presence/format
    # varies by supplier listing and hasn't been seen live yet to verify).
    if video_url:
        try:
            vid_result = await _shopify_gql(_GQL_CREATE_MEDIA, {
                "productId": product["id"],
                "media": [{"originalSource": video_url, "mediaContentType": "VIDEO", "alt": title}],
            })
            if vid_result.get("productCreateMedia", {}).get("mediaUserErrors"):
                logger.warning("Video attach failed for %s: %s", title, vid_result["productCreateMedia"]["mediaUserErrors"])
        except Exception as exc:
            logger.warning("Video attach failed for %s: %s", title, exc)

    # Publish to Online Store channel
    try:
        await _publish_product(product["id"])
    except Exception:
        pass  # publish failure is non-fatal

    return {"product": product, "success": True, "error": None}


async def create_collection(title: str) -> dict:
    """
    Get an existing collection by title or create it if it doesn't exist.

    Returns:
        Dict with keys: collection_id (str | None), created (bool), error (str | None)
    """
    try:
        # Check if collection already exists
        data = await _shopify_gql(_GQL_FIND_COLLECTION, {"title": f'title:"{title}"'})
        nodes = data.get("collections", {}).get("nodes", [])
        if nodes:
            return {"collection_id": nodes[0]["id"], "created": False, "error": None}

        # Create new collection. CollectionInput has no "published" field, and
        # collections are NOT visible on the storefront by default — confirmed live:
        # newly created collections had published_at=None and 404'd on the storefront
        # despite having products. Publish explicitly via REST, same pattern as
        # _publish_product().
        data = await _shopify_gql(
            _GQL_CREATE_COLLECTION,
            {"input": {"title": title}},
        )
        coll = data.get("collectionCreate", {}).get("collection")
        errors = data.get("collectionCreate", {}).get("userErrors", [])
        if errors or not coll:
            return {"collection_id": None, "created": False, "error": str(errors)}

        numeric_id = _gid_to_id(coll["id"])
        try:
            await _shopify_rest(
                "PUT", f"custom_collections/{numeric_id}.json",
                {"custom_collection": {"id": numeric_id, "published": True}},
            )
        except Exception:
            pass  # publish failure is non-fatal — collection still exists, just not live yet

        return {"collection_id": coll["id"], "created": True, "error": None}
    except Exception as exc:
        return {"collection_id": None, "created": False, "error": str(exc)}


_GQL_CREATE_DISCOUNT_CODE = """
mutation discountCodeBasicCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
    codeDiscountNode { id }
    userErrors { field message }
  }
}
"""


async def create_welcome_discount(code: str = "WELCOME10", percentage: float = 0.10) -> dict:
    """
    Create a storewide percentage-off discount code, active immediately, no
    minimum order, once per customer — a real AOV-booster achievable natively
    via the Discounts API (no third-party app like ReConvert needed for this
    specific kind of offer).

    Returns: {success, code, discount_id, error}
    """
    try:
        result = await _shopify_gql(_GQL_CREATE_DISCOUNT_CODE, {
            "basicCodeDiscount": {
                "title": f"{code} — storewide welcome offer",
                "code": code,
                "startsAt": "2024-01-01T00:00:00Z",
                "appliesOncePerCustomer": True,
                "customerSelection": {"all": True},
                "customerGets": {
                    "value": {"percentage": percentage},
                    "items": {"all": True},
                },
            }
        })
        node = result.get("discountCodeBasicCreate", {}).get("codeDiscountNode")
        errors = result.get("discountCodeBasicCreate", {}).get("userErrors", [])
        if errors or not node:
            return {"success": False, "code": code, "discount_id": None, "error": str(errors)}
        return {"success": True, "code": code, "discount_id": node["id"], "error": None}
    except Exception as exc:
        return {"success": False, "code": code, "discount_id": None, "error": str(exc)}


async def list_collections_with_counts() -> list[dict]:
    """Return [{"title", "handle", "count"}] for every collection — used by design review to spot empty ones."""
    try:
        data = await _shopify_gql(_GQL_LIST_COLLECTIONS_WITH_COUNTS, {})
        nodes = data.get("collections", {}).get("nodes", [])
        return [{"title": c["title"], "handle": c["handle"], "count": c["productsCount"]["count"]} for c in nodes]
    except Exception as exc:
        logger.warning("list_collections_with_counts failed: %s", exc)
        return []


async def best_populated_collection() -> str:
    """Return the handle of the collection with the most products (empty string if none have any)."""
    handle, _ = await best_populated_collection_with_count()
    return handle


async def best_populated_collection_with_count() -> tuple[str, int]:
    """Return (handle, product_count) for the most-populated collection, or ("", 0) if none have products."""
    collections = await list_collections_with_counts()
    populated = [c for c in collections if c["count"] > 0]
    if not populated:
        return "", 0
    best = max(populated, key=lambda c: c["count"])
    return best["handle"], best["count"]


async def upload_hero_image_from_product() -> str:
    """
    Upload an existing product's main image as a Shopify File so it can be used
    as a section's image_picker value. Returns "shopify://shop_images/<filename>"
    or "" if no product image is available / upload fails.
    """
    try:
        data = await _shopify_gql(_GQL_GET_FIRST_PRODUCT_IMAGE, {})
        for p in data.get("products", {}).get("nodes", []):
            nodes = p.get("images", {}).get("nodes", [])
            if nodes:
                source_url = nodes[0]["url"]
                break
        else:
            return ""

        result = await _shopify_gql(_GQL_FILE_CREATE, {
            "files": [{"originalSource": source_url, "contentType": "IMAGE", "alt": "Hero banner"}]
        })
        files = result.get("fileCreate", {}).get("files", [])
        if not files or result.get("fileCreate", {}).get("userErrors"):
            return ""
        file_id = files[0]["id"]

        # The image is processed asynchronously — poll briefly for the final URL/filename.
        for _ in range(6):
            await asyncio.sleep(2)
            check = await _shopify_gql(
                '{ node(id: "%s") { ... on MediaImage { image { url } } } }' % file_id, {}
            )
            url = (check.get("node") or {}).get("image", {}).get("url", "")
            if url:
                filename = url.split("/")[-1].split("?")[0]
                return f"shopify://shop_images/{filename}"
        return ""
    except Exception as exc:
        logger.warning("upload_hero_image_from_product failed: %s", exc)
        return ""


async def upload_local_file_as_shopify_file(file_path: str, alt: str = "") -> str:
    """
    Upload a local image file (e.g. a logo provided by the operator) to Shopify
    Files via the staged-upload flow, so it can be used as an image_picker value
    (theme logo, section image, etc). Returns "shopify://shop_images/<filename>"
    or "" on failure.
    """
    import mimetypes
    from pathlib import Path

    path = Path(file_path)
    if not path.is_file():
        logger.warning("upload_local_file_as_shopify_file: %s not found", file_path)
        return ""

    content = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"

    try:
        staged = await _shopify_gql(_GQL_STAGED_UPLOADS_CREATE, {
            "input": [{
                "resource": "FILE",
                "filename": path.name,
                "mimeType": mime_type,
                "httpMethod": "POST",
                "fileSize": str(len(content)),
            }]
        })
        targets = staged.get("stagedUploadsCreate", {}).get("stagedTargets", [])
        if not targets or staged.get("stagedUploadsCreate", {}).get("userErrors"):
            logger.warning("stagedUploadsCreate failed: %s", staged)
            return ""
        target = targets[0]

        form = {p["name"]: p["value"] for p in target["parameters"]}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                target["url"],
                data=form,
                files={"file": (path.name, content, mime_type)},
            )
            resp.raise_for_status()

        result = await _shopify_gql(_GQL_FILE_CREATE, {
            "files": [{"originalSource": target["resourceUrl"], "contentType": "IMAGE", "alt": alt}]
        })
        files = result.get("fileCreate", {}).get("files", [])
        if not files or result.get("fileCreate", {}).get("userErrors"):
            logger.warning("fileCreate failed: %s", result)
            return ""
        file_id = files[0]["id"]

        for _ in range(8):
            await asyncio.sleep(2)
            check = await _shopify_gql(
                '{ node(id: "%s") { ... on MediaImage { image { url } } } }' % file_id, {}
            )
            url = (check.get("node") or {}).get("image", {}).get("url", "")
            if url:
                filename = url.split("/")[-1].split("?")[0]
                return f"shopify://shop_images/{filename}"
        return ""
    except Exception as exc:
        logger.warning("upload_local_file_as_shopify_file failed: %s", exc)
        return ""


async def add_product_to_collection(product_id: str, collection_id: str) -> dict:
    """
    Add a product to a Shopify collection.

    Args:
        product_id: Shopify product GID
        collection_id: Shopify collection GID

    Returns:
        Dict with keys: success (bool), error (str | None)
    """
    try:
        data = await _shopify_gql(
            _GQL_ADD_TO_COLLECTION,
            {"id": collection_id, "productIds": [product_id]},
        )
        errors = data.get("collectionAddProducts", {}).get("userErrors", [])
        return {"success": not errors, "error": str(errors) if errors else None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def list_shopify_products() -> list[dict]:
    """Return all products in the store (id, title, status)."""
    try:
        data = await _shopify_gql(_GQL_LIST_PRODUCTS, {})
        return data.get("products", {}).get("nodes", [])
    except Exception:
        return []


async def delete_shopify_product(product_gid: str) -> bool:
    """Permanently delete a Shopify product by GID."""
    try:
        data = await _shopify_gql(_GQL_DELETE_PRODUCT, {"input": {"id": product_gid}})
        errors = data.get("productDelete", {}).get("userErrors", [])
        return not errors
    except Exception:
        return False


async def update_inventory(
    product_id: str,
    location_id: str,
    quantity: int,
) -> dict:
    """
    Set on-hand inventory quantity for a product's inventory item.

    product_id: Shopify InventoryItem GID (gid://shopify/InventoryItem/...)
    location_id: Shopify Location GID — if 'default', the first location is used.
    """
    try:
        # Resolve default location if needed
        loc_id = location_id
        if location_id == "default":
            loc_data = await _shopify_gql(_GQL_GET_LOCATION, {})
            nodes = loc_data.get("locations", {}).get("nodes", [])
            if not nodes:
                return {"updated": False, "available": 0}
            loc_id = nodes[0]["id"]

        data = await _shopify_gql(
            _GQL_SET_INVENTORY,
            {
                "input": {
                    "reason": "correction",
                    "name": "on_hand",
                    "changes": [{
                        "inventoryItemId": product_id,
                        "locationId": loc_id,
                        "delta": quantity,
                    }],
                }
            },
        )
        errors = data.get("inventoryAdjustQuantities", {}).get("userErrors", [])
        return {"updated": not errors, "available": quantity}
    except Exception:
        return {"updated": False, "available": 0}
