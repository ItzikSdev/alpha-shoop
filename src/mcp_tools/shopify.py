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
      seo { title description }
      variants(first: 1) { nodes { id inventoryItem { id } } }
      images(first: 10) { nodes { url } }
    }
    userErrors { field message }
  }
}
"""

_GQL_UPDATE_PRODUCT_COPY = """
mutation productUpdate($product: ProductUpdateInput!) {
  productUpdate(product: $product) {
    product { id title seo { title description } }
    userErrors { field message }
  }
}
"""


async def update_product_copy(
    product_id: str, title: str, description_html: str,
    seo_title: str = "", seo_description: str = "",
) -> dict:
    """Rewrite an EXISTING Shopify product's title/description/SEO fields — e.g. to
    replace raw supplier copy with real marketing copy. Does not touch images,
    variants, or price."""
    product_input: dict = {"id": product_id, "title": title, "descriptionHtml": description_html}
    if seo_title or seo_description:
        product_input["seo"] = {"title": seo_title or title, "description": seo_description or ""}
    try:
        data = await _shopify_gql(_GQL_UPDATE_PRODUCT_COPY, {"product": product_input})
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
    product = data.get("productUpdate", {}).get("product")
    errors = data.get("productUpdate", {}).get("userErrors", [])
    if errors or not product:
        return {"success": False, "error": str(errors) or "no product returned"}
    return {"success": True, "product": product}


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


_STOREFRONT_PUBLICATION_NAMES = ("Online Store",)
# Channels a headless/custom storefront reads from show up as their own
# publication (e.g. "ALPHA FOR BABY", "Hydrogen", "Headless"). The live Hydrogen
# site reads the store-named channel, NOT "Online Store" — so we must publish
# there too or products stay invisible on the storefront.
_HEADLESS_HINT = ("headless", "hydrogen", "storefront")


async def _storefront_publication_ids() -> list[str]:
    """Publication ids a customer-facing storefront reads from: Online Store plus
    any headless/custom-storefront channel. Excludes POS/social channels, which
    reject online-only products with userErrors."""
    data = await _shopify_gql("{ publications(first:30){ edges { node { id name } } } }", {})
    ids: list[str] = []
    for e in data.get("publications", {}).get("edges", []):
        name = (e["node"].get("name") or "")
        low = name.lower()
        if name in _STOREFRONT_PUBLICATION_NAMES or any(h in low for h in _HEADLESS_HINT):
            ids.append(e["node"]["id"])
        # A store-named channel (e.g. "ALPHA FOR BABY") is the headless storefront's
        # publication — include anything that isn't a known non-web channel.
        elif low not in ("point of sale", "facebook & instagram", "tiktok", "shop", "google & youtube"):
            ids.append(e["node"]["id"])
    return ids


async def _publish_product(product_gid: str) -> None:
    """Publish a product to every storefront channel (Online Store + headless).

    Uses GraphQL publishablePublish — the legacy REST `published:true` field only
    touches Online Store and is unreliable on current API versions (it left
    Sol-created products with publishedAt=None → invisible on the Hydrogen site).
    Raises on hard failure so the caller can log it instead of silently shipping
    an unpublished product.
    """
    pub_ids = await _storefront_publication_ids()
    if not pub_ids:
        raise RuntimeError("no storefront publications found to publish to")
    mutation = (
        "mutation Pub($id:ID!, $pubs:[PublicationInput!]!){"
        " publishablePublish(id:$id, input:$pubs){ userErrors{ field message } } }"
    )
    result = await _shopify_gql(
        mutation,
        {"id": product_gid, "pubs": [{"publicationId": pid} for pid in pub_ids]},
    )
    errs = result.get("publishablePublish", {}).get("userErrors", [])
    if errs:
        raise RuntimeError(f"publishablePublish userErrors: {errs}")


async def get_sales_channels() -> list[str]:
    """Names of the store's installed sales channels (Shopify publications).

    Used to verify, against the REAL store, whether a channel like
    'Facebook & Instagram' is actually installed — instead of trusting a flag.
    Best-effort: returns [] if the publications scope is missing or the call
    fails, so callers degrade gracefully."""
    q = "{ publications(first: 50) { edges { node { name } } } }"
    try:
        data = await _shopify_gql(q, {})
        return [e["node"]["name"] for e in data.get("publications", {}).get("edges", [])]
    except Exception:
        return []


def _specs_html(specs: dict | None) -> str:
    """Render CJ's rich spec fields (fabric, package contents, weight, customs,
    supplier) as a 'Product Details' table appended to the PDP description. Only
    non-empty fields are shown, so a sparse supplier record degrades cleanly."""
    if not specs:
        return ""
    rows = [
        ("Material", specs.get("material")),
        ("Package contents", specs.get("packaging")),
        ("Features", specs.get("properties")),
        ("Item weight", _weight_label(specs.get("product_weight_g"))),
        ("Package weight", _weight_label(specs.get("package_weight_g"))),
    ]
    cells = "".join(
        f"<tr><th style='text-align:left;padding:6px 16px 6px 0;color:#666;font-weight:600'>{k}</th>"
        f"<td style='padding:6px 0'>{v}</td></tr>"
        for k, v in rows if v
    )
    if not cells:
        return ""
    return (
        "<div class='product-specs'><h3>Product Details</h3>"
        f"<table><tbody>{cells}</tbody></table></div>"
    )


def _weight_label(grams) -> str:
    """CJ weights come as grams, sometimes a range like '170.00-369.00'. Show a
    clean gram label, or '' if missing/unparseable."""
    if not grams:
        return ""
    s = str(grams).strip()
    return f"{s} g" if s and s.lower() != "none" else ""


async def create_shopify_product(
    title: str,
    description: str,
    price: float,
    compare_at_price: float,
    images: list[str],
    variants: list[dict],
    video_url: str = "",
    specs: dict | None = None,
    seo_title: str = "",
    seo_description: str = "",
) -> dict:
    """
    Create a product in Shopify and set pricing.

    seo_title/seo_description: optional, set Shopify's `seo` field (search-result
    title/snippet) — distinct from the on-page title/description. Omit to leave
    Shopify to derive its own defaults from the product title/body.

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
    # Map each COLOR to its CJ variant image so we can (a) tag that media with a
    # distinct alt and (b) later link the color's variants to it → the storefront
    # swaps the gallery image when the shopper picks a color. First-seen wins.
    color_image: dict[str, str] = {}
    for v in variants:
        img, col = (v.get("image") or "").strip(), (v.get("color") or "").strip()
        if img and col:
            color_image.setdefault(img, col)

    def _alt_for(url: str) -> str:
        col = color_image.get(url)
        return f"cjcolor::{col}" if col else title

    media = [
        {"originalSource": url, "alt": _alt_for(url), "mediaContentType": "IMAGE"}
        for url in images if url
    ]
    # Ensure every color's image is present as media even if it wasn't in `images`.
    for url, col in color_image.items():
        if url not in images:
            media.append({"originalSource": url, "alt": f"cjcolor::{col}", "mediaContentType": "IMAGE"})
    product_input: dict = {
        "title": title,
        # Marketing copy + a real spec table built from CJ's rich REST
        # fields (material/packaging/weight) that we used to discard.
        "descriptionHtml": description + _specs_html(specs),
        "status": "ACTIVE",
    }
    if seo_title or seo_description:
        product_input["seo"] = {"title": seo_title or title, "description": seo_description or ""}
    try:
        data = await _shopify_gql(
            _GQL_CREATE_PRODUCT,
            {
                "product": product_input,
                "media": media or None,
            },
        )
    except Exception as exc:
        return {"product": None, "success": False, "error": str(exc)}

    product = data.get("productCreate", {}).get("product")
    errors = data.get("productCreate", {}).get("userErrors", [])
    if errors or not product:
        return {"product": None, "success": False, "error": str(errors) or "no product returned"}

    # Look up the media id we tagged per color (alt = "cjcolor::<color>") so each
    # color's variants can be linked to its own photo (gallery swaps on color).
    media_by_color: dict[str, str] = {}
    if color_image:
        try:
            mq = await _shopify_gql(
                '{ product(id: "%s") { media(first: 100) { nodes { id alt } } } }' % product["id"], {}
            )
            for node in mq.get("product", {}).get("media", {}).get("nodes", []):
                alt = node.get("alt") or ""
                if alt.startswith("cjcolor::"):
                    media_by_color[alt.split("cjcolor::", 1)[1]] = node["id"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("variant-image media lookup failed for %s: %s", title, exc)

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
                    # Link this variant to its color's photo → the storefront's
                    # selectedVariant.image swaps the gallery on color selection.
                    mid = media_by_color.get((match.get("color") or "").strip())
                    if mid:
                        entry["mediaId"] = mid
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

    # Publish to the storefront channels (Online Store + headless). Log on failure
    # — a silently-unpublished product is invisible on the live site (this is the
    # bug that left Sol's products with publishedAt=None / not on the storefront).
    try:
        await _publish_product(product["id"])
    except Exception as exc:
        logger.warning("Publish failed for '%s' (%s) — product is ACTIVE but NOT on the storefront: %s",
                       title, product.get("id"), exc)

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
        if node and not errors:
            return {"success": True, "code": code, "discount_id": node["id"], "error": None}
        # Idempotent: a duplicate code means the welcome discount ALREADY exists —
        # which is the desired end-state, not a failure. Shopify reports this as
        # "Code must be unique" on the code field. Treat it as success (reuse it)
        # so build_store doesn't fail/loop on a re-run of an already-set-up store.
        emsg = str(errors)
        if "must be unique" in emsg.lower() or "already" in emsg.lower() or "taken" in emsg.lower():
            return {"success": True, "code": code, "discount_id": None,
                    "error": None, "already_existed": True}
        return {"success": False, "code": code, "discount_id": None, "error": emsg}
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


_GQL_PRODUCTS_FOR_VIDEO = """
query productsForVideo {
  products(first: 50, sortKey: CREATED_AT, query: "status:active") {
    nodes {
      id
      title
      description
      images(first: 1) { nodes { url } }
    }
  }
}
"""


async def get_products_for_video() -> list[dict]:
    """Live product content for the video pipeline: id, title, description, and the
    primary image URL — everything `src/video/pipeline.py` needs to render an ad.
    Products with no image are skipped (Wan2.2 needs a source image to animate)."""
    try:
        data = await _shopify_gql(_GQL_PRODUCTS_FOR_VIDEO, {})
        nodes = data.get("products", {}).get("nodes", [])
    except Exception:
        return []

    out = []
    for n in nodes:
        images = n.get("images", {}).get("nodes", [])
        if not images:
            continue
        out.append({
            "id": n["id"],
            "title": n["title"],
            "description": n.get("description", ""),
            "image_url": images[0]["url"],
        })
    return out


_GQL_PRODUCTS_ALL_IMAGES = """
query productsAllImages {
  products(first: 50, sortKey: CREATED_AT, query: "status:active") {
    nodes {
      id
      title
      description
      images(first: 10) { nodes { url } }
    }
  }
}
"""


async def get_products_with_all_images() -> list[dict]:
    """Live product content for Reel's image pipeline: id, title, description, and
    EVERY product photo (not just the primary one, unlike `get_products_for_video`) —
    the person-detection step needs to check every photo, not just the first.
    Products with no images are skipped. This is the live-Shopify fallback used when
    the store_products RAG corpus has no `images` metadata yet for a product."""
    try:
        data = await _shopify_gql(_GQL_PRODUCTS_ALL_IMAGES, {})
        nodes = data.get("products", {}).get("nodes", [])
    except Exception:
        return []

    out = []
    for n in nodes:
        image_urls = [i["url"] for i in n.get("images", {}).get("nodes", []) if i.get("url")]
        if not image_urls:
            continue
        out.append({
            "id": n["id"],
            "title": n["title"],
            "description": n.get("description", ""),
            "image_urls": image_urls,
        })
    return out


async def attach_local_image_to_product(product_gid: str, file_path: str, alt: str = "") -> bool:
    """Upload a locally-generated image (Reel's baby-outfit-swap or 3D-showcase still)
    to Shopify via the staged-upload flow and attach it as product media. Same shape as
    `attach_local_video_to_product` below, but resource/content type IMAGE."""
    import mimetypes
    from pathlib import Path

    path = Path(file_path)
    if not path.is_file():
        logger.warning("attach_local_image_to_product: %s not found", file_path)
        return False

    content = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    try:
        staged = await _shopify_gql(_GQL_STAGED_UPLOADS_CREATE, {
            "input": [{
                "resource": "IMAGE",
                "filename": path.name,
                "mimeType": mime_type,
                "httpMethod": "POST",
                "fileSize": str(len(content)),
            }]
        })
        targets = staged.get("stagedUploadsCreate", {}).get("stagedTargets", [])
        if not targets or staged.get("stagedUploadsCreate", {}).get("userErrors"):
            logger.warning("stagedUploadsCreate (image) failed: %s", staged)
            return False
        target = targets[0]

        form = {p["name"]: p["value"] for p in target["parameters"]}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(target["url"], data=form, files={"file": (path.name, content, mime_type)})
            resp.raise_for_status()

        result = await _shopify_gql(_GQL_CREATE_MEDIA, {
            "productId": product_gid,
            "media": [{"originalSource": target["resourceUrl"], "mediaContentType": "IMAGE", "alt": alt}],
        })
        errors = result.get("productCreateMedia", {}).get("mediaUserErrors", [])
        if errors:
            logger.warning("productCreateMedia (image) failed: %s", errors)
        return not errors
    except Exception as exc:
        logger.warning("attach_local_image_to_product failed: %s", exc)
        return False


async def attach_local_video_to_product(product_gid: str, file_path: str, alt: str = "") -> bool:
    """Upload a locally-rendered mp4 (from the video pipeline) to Shopify via the
    staged-upload flow and attach it as product media. Same staged-upload mechanism
    as `upload_local_file_as_shopify_file`, but for VIDEO product media instead of a
    theme asset — Shopify's `productCreateMedia` needs a Shopify-hosted URL, and our
    render lives on this machine, so it has to go through staged uploads first."""
    from pathlib import Path

    path = Path(file_path)
    if not path.is_file():
        logger.warning("attach_local_video_to_product: %s not found", file_path)
        return False

    content = path.read_bytes()
    try:
        staged = await _shopify_gql(_GQL_STAGED_UPLOADS_CREATE, {
            "input": [{
                "resource": "VIDEO",
                "filename": path.name,
                "mimeType": "video/mp4",
                "httpMethod": "POST",
                "fileSize": str(len(content)),
            }]
        })
        targets = staged.get("stagedUploadsCreate", {}).get("stagedTargets", [])
        if not targets or staged.get("stagedUploadsCreate", {}).get("userErrors"):
            logger.warning("stagedUploadsCreate (video) failed: %s", staged)
            return False
        target = targets[0]

        form = {p["name"]: p["value"] for p in target["parameters"]}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(target["url"], data=form, files={"file": (path.name, content, "video/mp4")})
            resp.raise_for_status()

        result = await _shopify_gql(_GQL_CREATE_MEDIA, {
            "productId": product_gid,
            "media": [{"originalSource": target["resourceUrl"], "mediaContentType": "VIDEO", "alt": alt}],
        })
        errors = result.get("productCreateMedia", {}).get("mediaUserErrors", [])
        if errors:
            logger.warning("productCreateMedia (video) failed: %s", errors)
        return not errors
    except Exception as exc:
        logger.warning("attach_local_video_to_product failed: %s", exc)
        return False


async def delete_shopify_product(product_gid: str) -> bool:
    """Permanently delete a Shopify product by GID."""
    try:
        data = await _shopify_gql(_GQL_DELETE_PRODUCT, {"input": {"id": product_gid}})
        errors = data.get("productDelete", {}).get("userErrors", [])
        return not errors
    except Exception:
        return False


import re as _re

# CJK / Chinese (and Japanese/Korean) characters — a product whose title still has
# these never went through proper SEO/branding and shouldn't be live.
_CJK = _re.compile("[　-〿㐀-鿿가-힯＀-￯]")

_GQL_PRODUCTS_AUDIT = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id title images(first: 10) { nodes { url } } }
  }
}
"""


async def cleanup_bad_products(dry_run: bool = True, min_images: int = 3) -> dict:
    """Remove storefront products that aren't fit to sell: ones with FEWER than
    `min_images` images (owner rule: no product with <3 images may be on the store),
    an empty title, or a title that still contains raw foreign-language text
    (Chinese/CJK) — i.e. they never got proper images or SEO/branding.

    Returns a report; with dry_run=False it DELETES them (irreversible). After a
    cleanup, Sol must source replacement products (≥3 images, video prioritized —
    see stores/shopify/skills/product-sourcing.md) to refill the assortment.
    """
    bad: list[dict] = []
    cursor = None
    scanned = 0
    while True:
        data = await _shopify_gql(_GQL_PRODUCTS_AUDIT, {"cursor": cursor})
        conn = data.get("products", {})
        for n in conn.get("nodes", []):
            scanned += 1
            title = (n.get("title") or "").strip()
            n_imgs = len(n.get("images", {}).get("nodes", []))
            reason = ""
            if n_imgs < min_images:
                reason = f"only {n_imgs} image(s) (< {min_images} required)"
            elif not title:
                reason = "empty title"
            elif _CJK.search(title):
                reason = "foreign-language (CJK) title"
            if reason:
                bad.append({"id": n["id"], "title": title[:60], "reason": reason, "images": n_imgs})
        if conn.get("pageInfo", {}).get("hasNextPage"):
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    deleted = 0
    if not dry_run:
        for b in bad:
            if await delete_shopify_product(b["id"]):
                deleted += 1
    return {"scanned": scanned, "bad_count": len(bad), "deleted": deleted,
            "dry_run": dry_run, "min_images": min_images, "bad": bad[:50]}


def _norm_title(t: str) -> str:
    return _re.sub(r"\s+", " ", (t or "").strip().lower())


def _img_filename(url: str) -> str:
    """The image filename without query string — CJ keeps the same filename across
    re-scrapes/CDN paths, so it's a stable identity key for the same product photo."""
    base = (url or "").split("?")[0].rstrip("/")
    return base.rsplit("/", 1)[-1].lower()


async def dedupe_products(dry_run: bool = True) -> dict:
    """Remove DUPLICATE products. The RELIABLE key is the CJ product id in
    product_mappings — the same supplier item gets re-branded with a new title and
    Shopify re-hosts its images with new filenames, so title/image alone MISS cross-run
    dupes. So we dedupe by CJ pid first (keep the earliest-created listing), then fall
    back to same-title / same-image for anything without a mapping. dry_run=True only
    reports. This is the owner's 'no duplicate products' rule, runnable by the agents."""
    import os as _os
    import sqlite3 as _sql
    from src.stores import _current_store
    store = _current_store.get()
    store_id = store.store_id if store else ""

    dup_ids: dict[str, str] = {}  # shopify_gid -> reason

    # 0) Fetch the LIVE products first — we only ever dedupe among products that
    #    actually exist now (product_mappings keeps stale rows for deleted products,
    #    which otherwise show up as phantom "duplicates" that can't be deleted).
    cursor = None
    items: list[dict] = []
    while True:
        data = await _shopify_gql(_GQL_PRODUCTS_AUDIT, {"cursor": cursor})
        conn = data.get("products", {})
        for n in conn.get("nodes", []):
            imgs = n.get("images", {}).get("nodes", [])
            items.append({"id": n["id"], "title": n.get("title") or "",
                          "img": _img_filename(imgs[0]["url"]) if imgs else ""})
        if conn.get("pageInfo", {}).get("hasNextPage"):
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    live_gids = {it["id"] for it in items}
    title_by_id = {it["id"]: it["title"] for it in items}

    # 1) CJ-pid dedup via product_mappings — keep the oldest LIVE listing per CJ product.
    try:
        con = _sql.connect(_os.environ.get("TRACES_DB_PATH", "./data/traces.db"))
        rows = con.execute(
            "SELECT supplier_product_id, shopify_product_id, created_at FROM product_mappings"
            + (" WHERE store_id=?" if store_id else ""),
            ((store_id,) if store_id else ()),
        ).fetchall()
        con.close()
        by_pid: dict[str, list] = {}
        for pid, gid, created in rows:
            if pid and gid and str(gid) in live_gids:  # ignore stale mappings
                by_pid.setdefault(str(pid), []).append((created or "", str(gid)))
        for pid, lst in by_pid.items():
            lst.sort()  # oldest created_at first → that one survives
            for _, gid in lst[1:]:
                dup_ids[gid] = f"same CJ product {pid}"
    except Exception as exc:
        logger.warning("CJ-pid dedup read failed: %s", exc)

    # 2) Title / image fallback over the live products (catches dupes with no mapping).
    seen_title: set[str] = set()
    seen_img: set[str] = set()
    for it in items:
        if it["id"] in dup_ids:
            continue  # already a CJ-pid dupe; don't let it seed/steal the survivor
        tkey, ikey = _norm_title(it["title"]), it["img"]
        if (tkey and tkey in seen_title) or (ikey and ikey in seen_img):
            dup_ids[it["id"]] = "same title/image"
        else:
            if tkey:
                seen_title.add(tkey)
            if ikey:
                seen_img.add(ikey)

    dupes = [{"id": gid, "title": (title_by_id.get(gid, "") or "")[:60], "reason": reason}
             for gid, reason in dup_ids.items()]
    deleted = 0
    if not dry_run:
        for d in dupes:
            if await delete_shopify_product(d["id"]):
                deleted += 1
    return {"total": len(items), "duplicate_count": len(dupes), "deleted": deleted,
            "dry_run": dry_run, "duplicates": dupes[:50]}


_GQL_PRICE_AUDIT = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id title variants(first: 100) { nodes { id price } } }
  }
}
"""

_GQL_VARIANTS_BULK_UPDATE = """
mutation bulk($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    userErrors { field message }
  }
}
"""


async def fix_zero_prices(dry_run: bool = True) -> dict:
    """Fix products that have $0-priced variants: re-price each $0 variant to the
    product's mapped retail price (product_mappings.retail_price); if no valid price
    is on file, remove the product. The owner's 'no $0 products' rule, runnable by the
    agents. Returns a report."""
    import os as _os
    import sqlite3 as _sql
    con = _sql.connect(_os.environ.get("TRACES_DB_PATH", "./data/traces.db"))
    retail = {gid: r for gid, r in con.execute(
        "SELECT shopify_product_id, retail_price FROM product_mappings").fetchall()}
    con.close()
    cursor = None
    repriced = deleted = 0
    fixed: list[dict] = []
    while True:
        data = await _shopify_gql(_GQL_PRICE_AUDIT, {"cursor": cursor})
        conn = data.get("products", {})
        for n in conn.get("nodes", []):
            zeros = [v for v in n["variants"]["nodes"] if float(v["price"]) == 0]
            if not zeros:
                continue
            rp = float(retail.get(n["id"]) or 0)
            if rp > 0:
                if not dry_run:
                    await _shopify_gql(_GQL_VARIANTS_BULK_UPDATE, {
                        "productId": n["id"],
                        "variants": [{"id": v["id"], "price": f"{rp:.2f}"} for v in zeros],
                    })
                repriced += 1
                fixed.append({"title": n["title"][:50], "action": f"repriced {len(zeros)} variant(s) → ${rp:.2f}"})
            else:
                if not dry_run and await delete_shopify_product(n["id"]):
                    deleted += 1
                fixed.append({"title": n["title"][:50], "action": "removed (no price on file)"})
        if conn.get("pageInfo", {}).get("hasNextPage"):
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    return {"repriced": repriced, "deleted": deleted, "dry_run": dry_run, "fixed": fixed[:50]}


_GQL_STOCK_AUDIT = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title totalInventory
      variants(first: 100) {
        nodes { id inventoryPolicy inventoryQuantity inventoryItem { tracked } }
      }
    }
  }
}
"""


async def cleanup_out_of_stock_products(dry_run: bool = True) -> dict:
    """Remove products that are OUT OF STOCK and cannot be purchased at all: every
    variant TRACKS inventory, is at 0 (or negative) quantity, AND has inventory policy
    DENY (no backorder/overselling allowed) — a customer literally cannot check out.
    Variants with inventory tracking OFF are always purchasable regardless of quantity
    (Shopify ignores quantity/policy for untracked items — the norm for this dropship
    catalog, where CJ fulfills without Shopify-side stock counts), so they're never
    flagged. Products with any variant that still has stock, allows backorder
    (CONTINUE), or isn't tracked, are left alone. dry_run=True only reports. Owner
    rule, runnable by the agents."""
    bad: list[dict] = []
    cursor = None
    scanned = 0
    while True:
        data = await _shopify_gql(_GQL_STOCK_AUDIT, {"cursor": cursor})
        conn = data.get("products", {})
        for n in conn.get("nodes", []):
            scanned += 1
            variants = n.get("variants", {}).get("nodes", [])
            if not variants:
                continue
            purchasable = any(
                not v.get("inventoryItem", {}).get("tracked")
                or v.get("inventoryPolicy") == "CONTINUE"
                or (v.get("inventoryQuantity") or 0) > 0
                for v in variants
            )
            if not purchasable:
                bad.append({
                    "id": n["id"], "title": (n.get("title") or "")[:60],
                    "reason": "out of stock, no backorder allowed",
                    "total_inventory": n.get("totalInventory"),
                })
        if conn.get("pageInfo", {}).get("hasNextPage"):
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    deleted = 0
    if not dry_run:
        for b in bad:
            if await delete_shopify_product(b["id"]):
                deleted += 1
    return {"scanned": scanned, "bad_count": len(bad), "deleted": deleted,
            "dry_run": dry_run, "bad": bad[:50]}


_GQL_AGE_AUDIT = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes { id title createdAt productType descriptionHtml }
  }
}
"""


async def audit_stale_products(max_age_years: float = 3.0) -> dict:
    """READ-ONLY audit for the owner's 'no non-baby product older than 3 years' rule.
    Age is a hard, deterministic filter (createdAt), but whether a product is still a
    baby item isn't a data field on Shopify — that needs a human/agent to read the
    title+description and judge. Returns candidates (id/title/type/description/age);
    does NOT delete. Pair with `delete_shopify_product(id)` per item after review."""
    import datetime as _dt
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=max_age_years * 365.25)
    cursor = None
    candidates: list[dict] = []
    scanned = 0
    while True:
        data = await _shopify_gql(_GQL_AGE_AUDIT, {"cursor": cursor})
        conn = data.get("products", {})
        for n in conn.get("nodes", []):
            scanned += 1
            created = n.get("createdAt")
            if not created:
                continue
            created_dt = _dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created_dt < cutoff:
                desc = _re.sub("<[^>]+>", " ", n.get("descriptionHtml") or "")[:200]
                candidates.append({
                    "id": n["id"], "title": (n.get("title") or "")[:80],
                    "product_type": n.get("productType") or "",
                    "description": desc.strip(),
                    "created_at": created,
                    "age_years": round((_dt.datetime.now(_dt.timezone.utc) - created_dt).days / 365.25, 1),
                })
        if conn.get("pageInfo", {}).get("hasNextPage"):
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    return {"scanned": scanned, "max_age_years": max_age_years,
            "candidate_count": len(candidates), "candidates": candidates}


_GQL_SIZE_AUDIT = """
query($cursor: String) {
  products(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id title
      variants(first: 50) { nodes { selectedOptions { name value } } }
    }
  }
}
"""

# ~2-3 years — this store's baby/toddler niche; a size at or under this always counts
# as baby-appropriate. Sourced from the EU cm size chart CJ suppliers use (see the
# month-labeled sizes already in the catalog, e.g. "12-24 months (90cm)").
_BABY_SIZE_CM_MAX = 98


def _is_baby_size(value: str) -> bool | None:
    """True = a baby/toddler size, False = clearly too big for a baby, None =
    unrecognized format (caller should treat as 'can't tell', not as a match either
    way)."""
    v = (value or "").strip().lower()
    if not v:
        return None
    if "newborn" in v:
        return True
    if _re.search(r"\d+\s*m\b", v) or "month" in v:
        return True
    m = _re.search(r"(\d{2,3})\s*cm\b", v) or _re.fullmatch(r"(\d{2,3})", v)
    if m:
        return int(m.group(1)) <= _BABY_SIZE_CM_MAX
    if _re.search(r"\d+\s*y(ears?)?\b", v):
        return False  # an explicit "...Y" year-size (e.g. "8Y", "10-11Y") is a kids size
    return None


async def audit_size_mismatched_products() -> dict:
    """READ-ONLY. Flags products whose Size variants are ALL clearly too big for a
    baby/toddler — no size <= ~98cm / month-labeled / newborn is offered at all. This
    is what caught 'Toddler Cozy Crewneck Set' (sizes 130-150cm, i.e. ages 8-12) and
    "Girls' Sleeveless Vest & Shorts Set" (110-140cm, ages 4+) on 2026-08-01 — CJ
    listing titles say 'Toddler'/'Baby' but the actual size chart is for older kids.
    More reliable than reading title/description text, since the real signal is the
    size chart, not the marketing copy. Products with at least one baby-appropriate
    size, or with unparseable/no size data, are intentionally left alone (not
    flagged) — this only catches the unambiguous case: literally zero baby-fit sizes."""
    cursor = None
    flagged: list[dict] = []
    scanned = 0
    while True:
        data = await _shopify_gql(_GQL_SIZE_AUDIT, {"cursor": cursor})
        conn = data.get("products", {})
        for n in conn.get("nodes", []):
            scanned += 1
            sizes = [
                opt["value"] for v in n.get("variants", {}).get("nodes", [])
                for opt in v.get("selectedOptions", []) if opt.get("name", "").lower() == "size"
            ]
            if not sizes:
                continue
            verdicts = [_is_baby_size(s) for s in sizes]
            if verdicts and all(v is False for v in verdicts):
                flagged.append({"id": n["id"], "title": (n.get("title") or "")[:60], "sizes": sizes})
        if conn.get("pageInfo", {}).get("hasNextPage"):
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    return {"scanned": scanned, "flagged_count": len(flagged), "flagged": flagged[:50]}


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
