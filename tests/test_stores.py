"""Tests: multi-store config — CRUD, context var, credential routing."""
from __future__ import annotations

import os
import tempfile
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Isolated SQLite DB for each test."""
    db_file = str(tmp_path / "test_stores.db")
    with patch.dict(os.environ, {"TRACES_DB_PATH": db_file}):
        # Re-import with patched env so _DB_PATH picks up the temp file
        import importlib
        import src.stores as stores_mod
        importlib.reload(stores_mod)
        stores_mod.init_stores_table()
        yield stores_mod
    # Reset to original module state
    importlib.reload(stores_mod)


# ── Store CRUD ────────────────────────────────────────────────────────────────

def test_init_stores_table_idempotent(tmp_db):
    """Running init twice must not raise (CREATE TABLE IF NOT EXISTS)."""
    tmp_db.init_stores_table()  # second call


def test_save_and_list_store(tmp_db):
    from datetime import datetime, timezone
    store = tmp_db.StoreConfig(
        store_id="abc-123",
        name="Test Jewelry Store",
        shopify_domain="test.myshopify.com",
        shopify_access_token="shpat_test_token",
        niche="silver rings",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    tmp_db.save_store(store)
    stores = tmp_db.list_stores()
    assert len(stores) == 1
    assert stores[0].name == "Test Jewelry Store"
    assert stores[0].shopify_domain == "test.myshopify.com"
    assert stores[0].niche == "silver rings"


def test_get_store_by_id(tmp_db):
    from datetime import datetime, timezone
    store = tmp_db.StoreConfig(
        store_id="xyz-789",
        name="Baby Store",
        shopify_domain="baby.myshopify.com",
        shopify_access_token="shpat_baby_token",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    tmp_db.save_store(store)
    fetched = tmp_db.get_store("xyz-789")
    assert fetched is not None
    assert fetched.shopify_access_token == "shpat_baby_token"


def test_get_store_missing_returns_none(tmp_db):
    result = tmp_db.get_store("does-not-exist")
    assert result is None


def test_delete_store(tmp_db):
    from datetime import datetime, timezone
    store = tmp_db.StoreConfig(
        store_id="del-001",
        name="To Delete",
        shopify_domain="del.myshopify.com",
        shopify_access_token="shpat_del",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    tmp_db.save_store(store)
    assert tmp_db.delete_store("del-001") is True
    assert tmp_db.get_store("del-001") is None


def test_delete_missing_returns_false(tmp_db):
    assert tmp_db.delete_store("ghost-id") is False


def test_update_store_brand(tmp_db):
    from datetime import datetime, timezone
    store = tmp_db.StoreConfig(
        store_id="brand-001",
        name="Brand Store",
        shopify_domain="brand.myshopify.com",
        shopify_access_token="shpat_brand",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    tmp_db.save_store(store)
    brand = {"store_name": "Lumina", "niche": "silver rings", "product_category": "silver rings"}
    tmp_db.update_store_brand("brand-001", brand)
    fetched = tmp_db.get_store("brand-001")
    assert fetched.store_brand["store_name"] == "Lumina"
    assert fetched.niche == "silver rings"


def test_platform_defaults_to_shopify(tmp_db):
    from datetime import datetime, timezone
    store = tmp_db.StoreConfig(
        store_id="plat-001",
        name="Platform Test",
        shopify_domain="plat.myshopify.com",
        shopify_access_token="shpat_plat",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    tmp_db.save_store(store)
    fetched = tmp_db.get_store("plat-001")
    assert fetched.platform == "shopify"


def test_upsert_replaces_existing(tmp_db):
    from datetime import datetime, timezone
    store = tmp_db.StoreConfig(
        store_id="ups-001",
        name="Original Name",
        shopify_domain="ups.myshopify.com",
        shopify_access_token="shpat_v1",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    tmp_db.save_store(store)
    store.name = "Updated Name"
    store.shopify_access_token = "shpat_v2"
    tmp_db.save_store(store)
    fetched = tmp_db.get_store("ups-001")
    assert fetched.name == "Updated Name"
    assert fetched.shopify_access_token == "shpat_v2"
    assert len(tmp_db.list_stores()) == 1  # no duplicate


# ── Context var ───────────────────────────────────────────────────────────────

def test_context_var_defaults_none():
    from src.stores import _current_store
    assert _current_store.get(None) is None


def test_context_var_set_and_read():
    from src.stores import _current_store, StoreConfig
    from datetime import datetime, timezone
    store = StoreConfig(
        store_id="ctx-001",
        name="Ctx Store",
        shopify_domain="ctx.myshopify.com",
        shopify_access_token="shpat_ctx",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    token = _current_store.set(store)
    try:
        result = _current_store.get(None)
        assert result is not None
        assert result.shopify_domain == "ctx.myshopify.com"
    finally:
        _current_store.reset(token)
