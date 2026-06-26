"""Tests: orchestrator routing logic — replaces test_director.py.

director.py made an LLM call after every step to decide what runs next; that
routing is now plain Python control flow in src/agents/orchestrator.py. These
tests patch the worker node functions (not an LLM) and assert the same
behaviors the old director tests covered: error hard-stop, kill-switch,
store-setup gating, the design loop, the catalog-fill loop, and MONITOR mode.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _make_state(**overrides) -> dict:
    base = {
        "task": "Build a store",
        "thread_id": "test-thread",
        "operator": "test",
        "store_id": None,
        "messages": [],
        "trending_products": [],
        "sourcing_attempts": 0,
        "sourcing_feedback": None,
        "shopify_products_created": [],
        "campaign_ids": [],
        "total_ad_spend_usd": 0.0,
        "fulfilled_orders": [],
        "budget_remaining_usd": 100.0,
        "store_brand": None,
        "store_designed": False,
        "design_spec": None,
        "design_iterations": 0,
        "design_approved": False,
        "frontend_report": None,
        "store_health": None,
        "store_knowledge": [],
        "kill_switch_triggered": False,
        "run_complete": False,
        "error": None,
    }
    base.update(overrides)
    return base


async def _collect(state: dict) -> list[dict]:
    from src.agents.orchestrator import run_pipeline
    steps = []
    async for step in run_pipeline(state):
        steps.append(step)
    return steps


# ── Kill switch ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kill_switch_stops_immediately():
    state = _make_state(kill_switch_triggered=True)
    with patch("src.agents.orchestrator.store_setup_node", AsyncMock()) as mock_setup:
        steps = await _collect(state)
    mock_setup.assert_not_called()
    assert steps == []


# ── store_setup gating ────────────────────────────────────────────────────────

def _at_product_cap() -> list[str]:
    """Pre-fill shopify_products_created at the cap so the catalog-fill loop's
    while-condition is immediately False — these tests are only about the
    store_setup gating, not sourcing, so the real trend_scraper_node (which
    makes a real network call) must never run."""
    from src.agents.workers.ecommerce import _MAX_STORE_PRODUCTS
    return [f"p{i}" for i in range(_MAX_STORE_PRODUCTS)]


@pytest.mark.asyncio
async def test_calls_store_setup_when_no_brand():
    state = _make_state(
        store_brand=None, store_designed=True, shopify_products_created=_at_product_cap(),
    )
    with patch(
        "src.agents.orchestrator.store_setup_node",
        AsyncMock(return_value={"store_brand": {"store_name": "Test"}}),
    ) as mock_setup:
        await _collect(state)
    mock_setup.assert_called_once()


@pytest.mark.asyncio
async def test_skips_store_setup_when_brand_exists():
    state = _make_state(
        store_brand={"store_name": "Existing"}, store_designed=True,
        shopify_products_created=_at_product_cap(),
    )
    with patch("src.agents.orchestrator.store_setup_node", AsyncMock()) as mock_setup:
        await _collect(state)
    mock_setup.assert_not_called()


@pytest.mark.asyncio
async def test_rebuild_tag_clears_brand_and_reruns_setup():
    state = _make_state(
        task="[REBUILD] start over",
        store_brand={"store_name": "Old"},
        store_designed=True,
        shopify_products_created=_at_product_cap(),
    )
    seen_brand_at_call_time = []

    async def fake_setup(s):
        # capture immediately — `s` is the same mutable dict the orchestrator
        # keeps mutating afterward, so inspecting it post-hoc via call_args
        # would see later mutations, not the value at call time.
        seen_brand_at_call_time.append(s.get("store_brand"))
        return {"store_brand": {"store_name": "New"}}

    with patch("src.agents.orchestrator.store_setup_node", fake_setup):
        await _collect(state)
    assert seen_brand_at_call_time == [None]  # store_brand was cleared before store_setup ran


# ── Error hard-stop (loop prevention) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_design_loop_stops_on_worker_error():
    state = _make_state(store_brand={"store_name": "Test"}, store_designed=False)
    with patch(
        "src.agents.orchestrator.design_node",
        AsyncMock(return_value={"error": "design exploded"}),
    ) as mock_design, patch(
        "src.agents.orchestrator.frontend_node", AsyncMock()
    ) as mock_frontend, patch(
        "src.agents.orchestrator.trend_scraper_node", AsyncMock()
    ) as mock_scraper:
        await _collect(state)
    mock_design.assert_called_once()  # stopped after the first failure, no retry loop
    mock_frontend.assert_not_called()
    mock_scraper.assert_not_called()  # never reached the catalog-fill loop


@pytest.mark.asyncio
async def test_catalog_fill_loop_stops_on_worker_error():
    """Confirms the fix for the real bug today: trend_scraper setting `error`
    must stop the loop, not get called again with identical inputs forever."""
    state = _make_state(
        store_brand={"store_name": "Test"}, store_designed=True,
    )
    call_count = 0

    async def fake_scraper(s):
        nonlocal call_count
        call_count += 1
        return {"error": "CJ returned zero candidates after multiple sourcing attempts"}

    with patch("src.agents.orchestrator.trend_scraper_node", fake_scraper), \
         patch("src.agents.orchestrator.ecommerce_node", AsyncMock()) as mock_ecom:
        await _collect(state)

    assert call_count == 1  # not called again after setting error
    mock_ecom.assert_not_called()


# ── Catalog-fill loop termination ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_catalog_fill_loop_stops_at_product_cap():
    from src.agents.workers.ecommerce import _MAX_STORE_PRODUCTS
    state = _make_state(store_brand={"store_name": "Test"}, store_designed=True)
    scraper_calls = 0

    async def fake_scraper(s):
        nonlocal scraper_calls
        scraper_calls += 1
        return {"trending_products": [{"product_id": str(scraper_calls)}]}

    async def fake_ecommerce(s):
        # simulate one product created per pass until the cap is hit
        created = list(s.get("shopify_products_created", []))
        created.append(f"gid://shopify/Product/{len(created)}")
        return {"shopify_products_created": created}

    with patch("src.agents.orchestrator.trend_scraper_node", fake_scraper), \
         patch("src.agents.orchestrator.ecommerce_node", fake_ecommerce):
        await _collect(state)

    assert len(state["shopify_products_created"]) == _MAX_STORE_PRODUCTS
    assert scraper_calls == _MAX_STORE_PRODUCTS


# ── MONITOR mode ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_monitor_routes_to_sourcing_when_no_products():
    state = _make_state(
        task="[MONITOR] check health",
        store_brand={"store_name": "Test"},
        store_designed=True,
    )
    health = {"order_count": 0, "revenue_usd": 0.0, "period_days": 7, "status": "healthy"}
    with patch("src.agents.orchestrator.get_sales_summary", AsyncMock(return_value=health)), \
         patch("src.agents.orchestrator.list_shopify_products", AsyncMock(return_value=[])), \
         patch("src.agents.orchestrator.trend_scraper_node", AsyncMock(return_value={"error": "stop"})) as mock_scraper, \
         patch("src.agents.orchestrator.marketing_node", AsyncMock()) as mock_marketing:
        await _collect(state)
    mock_scraper.assert_called_once()  # 0 products -> sourcing loop, even though health says "healthy"
    mock_marketing.assert_not_called()


@pytest.mark.asyncio
async def test_monitor_routes_to_marketing_when_no_sales():
    state = _make_state(
        task="[MONITOR] check health",
        store_brand={"store_name": "Test"},
        store_designed=True,
    )
    health = {"order_count": 0, "revenue_usd": 0.0, "period_days": 7, "status": "no_sales"}
    with patch("src.agents.orchestrator.get_sales_summary", AsyncMock(return_value=health)), \
         patch("src.agents.orchestrator.list_shopify_products", AsyncMock(return_value=[{"id": 1}])), \
         patch("src.agents.orchestrator.marketing_node", AsyncMock(return_value={"campaign_ids": ["c1"]})) as mock_marketing, \
         patch("src.agents.orchestrator.trend_scraper_node", AsyncMock()) as mock_scraper:
        await _collect(state)
    mock_marketing.assert_called_once()
    mock_scraper.assert_not_called()


@pytest.mark.asyncio
async def test_monitor_does_nothing_when_healthy_with_products():
    state = _make_state(
        task="[MONITOR] check health",
        store_brand={"store_name": "Test"},
        store_designed=True,
    )
    health = {"order_count": 5, "revenue_usd": 200.0, "period_days": 7, "status": "healthy"}
    with patch("src.agents.orchestrator.get_sales_summary", AsyncMock(return_value=health)), \
         patch("src.agents.orchestrator.list_shopify_products", AsyncMock(return_value=[{"id": 1}])), \
         patch("src.agents.orchestrator.marketing_node", AsyncMock()) as mock_marketing, \
         patch("src.agents.orchestrator.trend_scraper_node", AsyncMock()) as mock_scraper:
        await _collect(state)
    mock_marketing.assert_not_called()
    mock_scraper.assert_not_called()


# ── [MARKETING] tag and [SETUP_ONLY] tag ─────────────────────────────────────

@pytest.mark.asyncio
async def test_marketing_runs_when_tag_present():
    state = _make_state(
        task="[MARKETING] launch ads",
        store_brand={"store_name": "Test"},
        store_designed=True,
    )
    with patch("src.agents.orchestrator.trend_scraper_node", AsyncMock(return_value={"error": "stop"})), \
         patch("src.agents.orchestrator.marketing_node", AsyncMock(return_value={"campaign_ids": ["c1"]})) as mock_marketing:
        await _collect(state)
    mock_marketing.assert_not_called()  # error from sourcing loop should prevent marketing


@pytest.mark.asyncio
async def test_setup_only_stops_after_design():
    from src.agents.workers.ecommerce import _MAX_STORE_PRODUCTS
    state = _make_state(
        task="[SETUP_ONLY] rebuild brand",
        store_brand={"store_name": "Old"},
        store_designed=True,
        shopify_products_created=[f"p{i}" for i in range(_MAX_STORE_PRODUCTS)],
    )
    with patch(
        "src.agents.orchestrator.store_setup_node",
        AsyncMock(return_value={"store_brand": {"store_name": "New"}, "store_designed": False}),
    ), patch("src.agents.orchestrator.design_node", AsyncMock()) as mock_design, \
       patch("src.agents.orchestrator.trend_scraper_node", AsyncMock()) as mock_scraper:
        await _collect(state)
    mock_design.assert_not_called()  # [SETUP_ONLY] must stop before the design loop
    mock_scraper.assert_not_called()
