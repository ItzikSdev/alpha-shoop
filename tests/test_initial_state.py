"""Tests: initial AgentState setup — [SETUP_ONLY] / [REBUILD] clear cached brand."""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────

CACHED_BRAND = {
    "store_name": "Lumaveil",
    "niche": "silk scarves",
    "product_category": "silk scarves",
}

LONG_TASK = "Find trending baby products under $50 with 30% margin and great copy"
SETUP_TASK = "[SETUP_ONLY] Rebuild the store brand and design CSS from scratch"
REBUILD_TASK = "[REBUILD] Completely rebuild this store from scratch for baby products"


def _mock_store(brand: dict | None = None):
    store = MagicMock()
    store.store_id = "test-store-id"
    store.shopify_domain = "test.myshopify.com"
    store.shopify_access_token = "shpat_test"
    store.store_brand = brand or {}
    return store


# ── [SETUP_ONLY] clears cached brand ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_only_clears_cached_brand(client: AsyncClient, auth_headers: dict):
    """[SETUP_ONLY] task must start with store_brand=None even if store has a cached brand."""
    captured_state = {}

    async def fake_graph_stream(state, config):
        captured_state.update(state)
        return
        yield  # make it a generator

    import asyncio
    with patch("src.api.routes.agents.get_store", return_value=_mock_store(CACHED_BRAND)), \
         patch("src.api.routes.agents.graph") as mock_graph:
        mock_graph.astream = fake_graph_stream
        resp = await client.post(
            "/api/v1/run",
            json={"task": SETUP_TASK, "store_id": "test-store-id"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        # Wait inside patch scope so background task runs with mocks active
        await asyncio.sleep(0.15)

    assert captured_state.get("store_brand") is None
    assert captured_state.get("store_designed") is False


@pytest.mark.asyncio
async def test_rebuild_clears_cached_brand(client: AsyncClient, auth_headers: dict):
    """[REBUILD] must also clear cached brand."""
    import asyncio
    captured_state = {}

    async def fake_graph_stream(state, config):
        captured_state.update(state)
        return
        yield

    with patch("src.api.routes.agents.get_store", return_value=_mock_store(CACHED_BRAND)), \
         patch("src.api.routes.agents.graph") as mock_graph:
        mock_graph.astream = fake_graph_stream
        resp = await client.post(
            "/api/v1/run",
            json={"task": REBUILD_TASK, "store_id": "test-store-id"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        await asyncio.sleep(0.15)

    assert captured_state.get("store_brand") is None
    assert captured_state.get("store_designed") is False


@pytest.mark.asyncio
async def test_normal_task_loads_cached_brand(client: AsyncClient, auth_headers: dict):
    """A normal (non-rebuild) task should load the cached brand to skip store_setup."""
    import asyncio
    captured_state = {}

    async def fake_graph_stream(state, config):
        captured_state.update(state)
        return
        yield

    with patch("src.api.routes.agents.get_store", return_value=_mock_store(CACHED_BRAND)), \
         patch("src.api.routes.agents.graph") as mock_graph:
        mock_graph.astream = fake_graph_stream
        resp = await client.post(
            "/api/v1/run",
            json={"task": LONG_TASK, "store_id": "test-store-id"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        await asyncio.sleep(0.15)

    assert captured_state.get("store_brand") == CACHED_BRAND
    assert captured_state.get("store_designed") is True


# ── store_id routing ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_without_store_id_uses_default(client: AsyncClient, auth_headers: dict):
    """No store_id → credentials come from env config, no store lookup."""
    with patch("src.api.routes.agents.get_store") as mock_get_store, \
         patch("src.api.routes.agents.graph") as mock_graph:
        mock_graph.astream = AsyncMock(return_value=iter([]))

        async def empty_stream(state, config):
            return
            yield

        mock_graph.astream = empty_stream
        resp = await client.post(
            "/api/v1/run",
            json={"task": LONG_TASK},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        mock_get_store.assert_not_called()


# ── Stores API ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stores_endpoint_returns_list(client: AsyncClient):
    """GET /stores must return a list (empty or not, always 200)."""
    with patch("src.api.routes.stores.list_stores", return_value=[]):
        resp = await client.get("/api/v1/stores")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_store_endpoint(client: AsyncClient, auth_headers: dict):
    """POST /stores creates a store and returns store_id."""
    saved = {}

    def fake_save(store):
        saved["store"] = store

    with patch("src.api.routes.stores.save_store", side_effect=fake_save):
        resp = await client.post(
            "/api/v1/stores",
            json={
                "name": "Baby Store",
                "shopify_domain": "baby.myshopify.com",
                "shopify_access_token": "shpat_test_token",
                "niche": "baby products",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "store_id" in body
    assert saved["store"].name == "Baby Store"
    assert saved["store"].shopify_domain == "baby.myshopify.com"


@pytest.mark.asyncio
async def test_create_store_strips_https_prefix(client: AsyncClient):
    """Domain cleanup: 'https://mystore.myshopify.com/' → 'mystore.myshopify.com'"""
    saved = {}

    def fake_save(store):
        saved["store"] = store

    with patch("src.api.routes.stores.save_store", side_effect=fake_save):
        await client.post(
            "/api/v1/stores",
            json={
                "name": "Test",
                "shopify_domain": "https://mystore.myshopify.com/",
                "shopify_access_token": "shpat_x",
            },
        )

    assert saved["store"].shopify_domain == "mystore.myshopify.com"


@pytest.mark.asyncio
async def test_delete_store_not_found(client: AsyncClient):
    with patch("src.api.routes.stores.delete_store", return_value=False):
        resp = await client.delete("/api/v1/stores/nonexistent-id")
    assert resp.status_code == 404
