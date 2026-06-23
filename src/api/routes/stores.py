"""Store management endpoints — CRUD for multi-store Shopify configs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.embeddings import upsert_store_knowledge, delete_store_knowledge
from src.stores import (
    StoreConfig,
    list_stores,
    get_store,
    save_store,
    delete_store,
    update_store_storefront,
    _current_store,
)
from src.mcp_tools.shopify import _shopify_gql, _shopify_rest

router = APIRouter()


class StoreCreateRequest(BaseModel):
    name: str
    shopify_domain: str
    shopify_access_token: str
    platform: str = "shopify"
    niche: str = ""
    description: str = ""
    payplus_api_key: str = ""
    payplus_secret: str = ""


class StoreUpdateRequest(BaseModel):
    payplus_api_key: str | None = None
    payplus_secret: str | None = None
    shopify_access_token: str | None = None
    shopify_domain: str | None = None
    niche: str | None = None
    description: str | None = None
    active: bool | None = None
    oxygen_deploy_token: str | None = None
    theme_access_password: str | None = None


async def _sync_store_embedding(store: StoreConfig) -> None:
    """Re-embed the store's description after any create/update so RAG stays current."""
    if store.description.strip():
        await upsert_store_knowledge(
            store.store_id,
            store.description,
            metadata={"name": store.name, "niche": store.niche},
        )


@router.get("/stores", summary="List all configured stores")
async def get_stores() -> list[dict]:
    stores = list_stores()
    return [
        {
            "store_id": s.store_id,
            "name": s.name,
            "shopify_domain": s.shopify_domain,
            "platform": s.platform,
            "niche": s.niche,
            "description": s.description,
            "active": s.active,
            "created_at": s.created_at,
            "has_brand": bool(s.store_brand),
            "store_name": s.store_brand.get("store_name", ""),
            "installed_theme": s.installed_theme,
            "has_payplus": bool(s.payplus_api_key),
            # Storefront/theme runner state (localhost dev dashboard).
            "storefront_slug": s.storefront_slug,
            "has_theme_password": bool(s.theme_access_password),  # needed for `shopify theme dev`
        }
        for s in stores
    ]


@router.post("/stores", summary="Add a new store", status_code=201)
async def create_store(body: StoreCreateRequest) -> dict:
    domain = body.shopify_domain.strip().removeprefix("https://").removeprefix("http://").removesuffix("/")
    store = StoreConfig(
        store_id=str(uuid.uuid4()),
        name=body.name,
        shopify_domain=domain,
        shopify_access_token=body.shopify_access_token,
        platform=body.platform,
        niche=body.niche,
        description=body.description,
        payplus_api_key=body.payplus_api_key,
        payplus_secret=body.payplus_secret,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    save_store(store)
    await _sync_store_embedding(store)
    return {"store_id": store.store_id, "name": store.name, "shopify_domain": store.shopify_domain}


@router.get("/stores/{store_id}", summary="Get store details including cached brand brief")
async def get_store_detail(store_id: str) -> dict:
    store = get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id!r} not found")
    return {
        "store_id": store.store_id,
        "name": store.name,
        "shopify_domain": store.shopify_domain,
        "platform": store.platform,
        "niche": store.niche,
        "description": store.description,
        "active": store.active,
        "created_at": store.created_at,
        "installed_theme": store.installed_theme,
        "has_payplus": bool(store.payplus_api_key),
        "store_brand": store.store_brand,
    }


@router.patch("/stores/{store_id}", summary="Update store credentials or settings")
async def update_store(store_id: str, body: StoreUpdateRequest) -> dict:
    store = get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id!r} not found")
    if body.payplus_api_key is not None:
        store.payplus_api_key = body.payplus_api_key
    if body.payplus_secret is not None:
        store.payplus_secret = body.payplus_secret
    if body.shopify_access_token is not None:
        store.shopify_access_token = body.shopify_access_token
    if body.shopify_domain is not None:
        store.shopify_domain = body.shopify_domain.strip().removeprefix("https://").removeprefix("http://").removesuffix("/")
    if body.niche is not None:
        store.niche = body.niche
    if body.description is not None:
        store.description = body.description
    if body.active is not None:
        store.active = body.active
    if body.oxygen_deploy_token is not None:
        store.oxygen_deploy_token = body.oxygen_deploy_token
    if body.theme_access_password is not None:
        store.theme_access_password = body.theme_access_password
    save_store(store)
    if body.description is not None:
        await _sync_store_embedding(store)
    return {"store_id": store_id, "updated": True}


# ── GraphQL for Hydrogen storefront provisioning ────────────────────────────
_GQL_STOREFRONT_TOKEN_CREATE = """
mutation storefrontAccessTokenCreate($input: StorefrontAccessTokenInput!) {
  storefrontAccessTokenCreate(input: $input) {
    storefrontAccessToken { accessToken title }
    userErrors { field message }
  }
}
"""

_GQL_PUBLICATIONS = """
{ publications(first: 10) { nodes { id name } } }
"""

_GQL_COLLECTIONS = """
{ collections(first: 50) { nodes { id handle title } } }
"""

_GQL_PUBLISHABLE_PUBLISH = """
mutation publishablePublish($id: ID!, $pub: ID!) {
  publishablePublish(id: $id, input: { publicationId: $pub }) {
    userErrors { message }
  }
}
"""


@router.post(
    "/stores/{store_id}/storefront/provision",
    summary="Provision a Hydrogen storefront: storefront token + publish collections",
)
async def provision_storefront(store_id: str) -> dict:
    store = get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id!r} not found")

    # Derive slug from the shopify domain handle (e.g. lumibud-dev.myshopify.com -> lumibud-dev)
    slug = store.shopify_domain.split(".")[0].strip().lower()
    update_store_storefront(store_id, storefront_slug=slug)
    store.storefront_slug = slug

    # Make Shopify helpers operate against this store's credentials.
    tok = _current_store.set(store)
    try:
        token = store.storefront_api_token

        # 1. Generate a Storefront API access token if missing.
        if not token:
            data = await _shopify_gql(
                _GQL_STOREFRONT_TOKEN_CREATE,
                {"input": {"title": f"Hydrogen {store.name}"}},
            )
            result = data.get("storefrontAccessTokenCreate", {}) or {}
            errors = result.get("userErrors", [])
            sat = result.get("storefrontAccessToken") or {}
            token = sat.get("accessToken", "")
            if errors or not token:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to create storefront access token: {errors or 'no token returned'}",
                )
            update_store_storefront(store_id, storefront_api_token=token)
            store.storefront_api_token = token

        # 2. Publish all custom collections to the Online Store publication (best-effort).
        collections_published = 0
        try:
            pub_data = await _shopify_gql(_GQL_PUBLICATIONS, {})
            pub_id = ""
            for node in pub_data.get("publications", {}).get("nodes", []):
                if node.get("name") == "Online Store":
                    pub_id = node.get("id", "")
                    break

            if pub_id:
                coll_data = await _shopify_gql(_GQL_COLLECTIONS, {})
                for coll in coll_data.get("collections", {}).get("nodes", []):
                    if coll.get("handle") == "frontpage":
                        continue
                    try:
                        await _shopify_gql(
                            _GQL_PUBLISHABLE_PUBLISH,
                            {"id": coll["id"], "pub": pub_id},
                        )
                        collections_published += 1
                    except Exception:
                        pass  # best-effort per-collection
        except Exception:
            pass  # best-effort publication step

        return {
            "slug": slug,
            "domain": store.shopify_domain,
            "storefront_token": token,
            "checkout_domain": store.shopify_domain,
            "collections_published": collections_published,
        }
    finally:
        _current_store.reset(tok)


@router.get(
    "/stores/{store_id}/theme-creds",
    summary="Theme CLI creds for the host runner (domain + admin token + live theme id)",
)
async def theme_creds(store_id: str) -> dict:
    """Server-to-server creds for the host Storefront Runner's `shopify theme` calls.

    Returns the store's Admin token (used non-interactively as SHOPIFY_CLI_THEME_TOKEN)
    plus the live theme id. Localhost-only dev tool — the runner calls this so the
    Admin token never travels through the browser.
    """
    store = get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id!r} not found")

    live_theme_id = ""
    tok = _current_store.set(store)
    try:
        try:
            result = await _shopify_rest("GET", "themes.json")
            main = next((t for t in result.get("themes", []) if t.get("role") == "main"), None)
            if main:
                live_theme_id = str(main.get("id", ""))
        except Exception:
            pass  # runner falls back to `--live` if no id
    finally:
        _current_store.reset(tok)

    return {
        "domain": store.shopify_domain,
        "theme_token": store.shopify_access_token,        # admin token — works for pull/push
        "theme_password": store.theme_access_password,    # Theme Access password — required for `theme dev`
        "live_theme_id": live_theme_id,
        "slug": store.storefront_slug or store.shopify_domain.split(".")[0],
    }


@router.delete("/stores/{store_id}", summary="Remove a store")
async def remove_store(store_id: str) -> dict:
    if not delete_store(store_id):
        raise HTTPException(status_code=404, detail=f"Store {store_id!r} not found")
    delete_store_knowledge(store_id)
    return {"deleted": store_id}
