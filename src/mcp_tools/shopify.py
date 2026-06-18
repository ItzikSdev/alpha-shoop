"""MCP Tool Group 3: Shopify Admin GraphQL API 2024-07."""
from __future__ import annotations
import httpx
from src.config import get_settings

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


def _gid_to_id(gid: str) -> str:
    """Extract numeric ID from Shopify GID. 'gid://shopify/Product/12345' → '12345'"""
    return gid.rsplit("/", 1)[-1]


async def _shopify_gql(query: str, variables: dict) -> dict:
    settings = get_settings()
    url = f"https://{settings.shopify_store_domain}/admin/api/2024-07/graphql.json"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            json={"query": query, "variables": variables},
            headers={
                "X-Shopify-Access-Token": settings.shopify_access_token,
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
    settings = get_settings()
    url = f"https://{settings.shopify_store_domain}/admin/api/2024-07/{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(
            method,
            url,
            json=body,
            headers={
                "X-Shopify-Access-Token": settings.shopify_access_token,
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
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

        # Create new collection
        data = await _shopify_gql(
            _GQL_CREATE_COLLECTION,
            {"input": {"title": title, "published": True}},
        )
        coll = data.get("collectionCreate", {}).get("collection")
        errors = data.get("collectionCreate", {}).get("userErrors", [])
        if errors or not coll:
            return {"collection_id": None, "created": False, "error": str(errors)}
        return {"collection_id": coll["id"], "created": True, "error": None}
    except Exception as exc:
        return {"collection_id": None, "created": False, "error": str(exc)}


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
