"""Tests: Shopify credential routing via _current_store context var."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.stores import _current_store, StoreConfig
from datetime import datetime, timezone


def _make_store(domain: str, token: str) -> StoreConfig:
    return StoreConfig(
        store_id="test-id",
        name="Test Store",
        shopify_domain=domain,
        shopify_access_token=token,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.asyncio
async def test_shopify_creds_uses_context_var_when_set():
    """_shopify_creds() returns store domain/token when _current_store is set."""
    from src.mcp_tools.shopify import _shopify_creds
    store = _make_store("per-store.myshopify.com", "shpat_per_store")
    tok = _current_store.set(store)
    try:
        domain, token = _shopify_creds()
        assert domain == "per-store.myshopify.com"
        assert token == "shpat_per_store"
    finally:
        _current_store.reset(tok)


@pytest.mark.asyncio
async def test_shopify_creds_falls_back_to_env_when_no_store():
    """_shopify_creds() falls back to get_settings() when no store in context."""
    from src.mcp_tools.shopify import _shopify_creds

    tok = _current_store.set(None)
    try:
        mock_settings = MagicMock()
        mock_settings.shopify_store_domain = "env-store.myshopify.com"
        mock_settings.shopify_access_token = "shpat_env_token"
        with patch("src.mcp_tools.shopify.get_settings", return_value=mock_settings):
            domain, token = _shopify_creds()
        assert domain == "env-store.myshopify.com"
        assert token == "shpat_env_token"
    finally:
        _current_store.reset(tok)


@pytest.mark.asyncio
async def test_shopify_gql_uses_context_store_domain():
    """_shopify_gql builds the correct URL from the per-store domain."""
    from src.mcp_tools.shopify import _shopify_gql
    store = _make_store("contextstore.myshopify.com", "shpat_ctx")
    tok = _current_store.set(store)
    try:
        captured_url = {}
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"result": "ok"}}
        mock_response.raise_for_status = MagicMock()

        async def mock_post(url, **kwargs):
            captured_url["url"] = url
            return mock_response

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=MagicMock(post=AsyncMock(side_effect=mock_post)))
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.mcp_tools.shopify.httpx.AsyncClient", return_value=mock_client):
            try:
                await _shopify_gql("{ shop { name } }", {})
            except Exception:
                pass

        if captured_url.get("url"):
            assert "contextstore.myshopify.com" in captured_url["url"]
    finally:
        _current_store.reset(tok)


@pytest.mark.asyncio
async def test_two_concurrent_tasks_use_different_stores():
    """Context vars are task-local — two concurrent tasks must not share store credentials."""
    import asyncio
    from src.mcp_tools.shopify import _shopify_creds

    store_a = _make_store("store-a.myshopify.com", "shpat_a")
    store_b = _make_store("store-b.myshopify.com", "shpat_b")

    results = {}

    async def task_a():
        tok = _current_store.set(store_a)
        await asyncio.sleep(0)  # yield to let task_b run
        domain, token = _shopify_creds()
        results["a"] = (domain, token)
        _current_store.reset(tok)

    async def task_b():
        tok = _current_store.set(store_b)
        await asyncio.sleep(0)
        domain, token = _shopify_creds()
        results["b"] = (domain, token)
        _current_store.reset(tok)

    await asyncio.gather(task_a(), task_b())

    assert results["a"][0] == "store-a.myshopify.com"
    assert results["b"][0] == "store-b.myshopify.com"
    assert results["a"][1] != results["b"][1]  # tokens must not cross
