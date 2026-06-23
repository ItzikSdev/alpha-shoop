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
      variants(first: 1) { nodes { id } }
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
) -> dict:
    """
    Create a product in Shopify and immediately set its price.

    Returns:
        Dict with keys: product (dict), success (bool), error (str | None)
    """
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

    # Set price on the default variant
    variant_nodes = product.get("variants", {}).get("nodes", [])
    if variant_nodes and price > 0:
        variant_id = variant_nodes[0]["id"]
        try:
            await _shopify_gql(
                _GQL_SET_PRICE,
                {
                    "productId": product["id"],
                    "variants": [{
                        "id": variant_id,
                        "price": f"{price:.2f}",
                        "compareAtPrice": f"{compare_at_price:.2f}" if compare_at_price > price else None,
                    }],
                },
            )
            product["price"] = price
            product["compare_at_price"] = compare_at_price
        except Exception:
            pass  # price update failure is non-fatal

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

        # Create new collection (CollectionInput has no "published" field — collections
        # are visible on the storefront by default once created)
        data = await _shopify_gql(
            _GQL_CREATE_COLLECTION,
            {"input": {"title": title}},
        )
        coll = data.get("collectionCreate", {}).get("collection")
        errors = data.get("collectionCreate", {}).get("userErrors", [])
        if errors or not coll:
            return {"collection_id": None, "created": False, "error": str(errors)}
        return {"collection_id": coll["id"], "created": True, "error": None}
    except Exception as exc:
        return {"collection_id": None, "created": False, "error": str(exc)}


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
