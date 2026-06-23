"""Tests: Director routing logic — error stop, rebuild tag, design detection, loop prevention."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_state(**overrides) -> dict:
    base = {
        "task": "Build a store",
        "thread_id": "test-thread",
        "operator": "test",
        "store_id": None,
        "messages": [],
        "next_agent": None,
        "director_reasoning": None,
        "trending_products": [],
        "shopify_products_created": [],
        "campaign_ids": [],
        "total_ad_spend_usd": 0.0,
        "fulfilled_orders": [],
        "budget_remaining_usd": 100.0,
        "store_brand": None,
        "store_designed": False,
        "store_health": None,
        "kill_switch_triggered": False,
        "run_complete": False,
        "error": None,
    }
    base.update(overrides)
    return base


# ── Kill switch ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_director_kill_switch_returns_end():
    from src.agents.director import director_node
    state = _make_state(kill_switch_triggered=True)
    result = await director_node(state)
    assert result["next_agent"] == "END"
    assert "kill" in result["director_reasoning"].lower()


# ── Error hard-stop (loop prevention) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_director_stops_on_error_no_llm_call():
    """If state has an error, director must route to END without calling the LLM."""
    from src.agents.director import director_node
    state = _make_state(error="no niche-matching products found")

    with patch("src.agents.director.get_llm") as mock_llm:
        result = await director_node(state)
        mock_llm.assert_not_called()  # LLM must NOT be invoked when there's an error

    assert result["next_agent"] == "END"


@pytest.mark.asyncio
async def test_director_stops_on_any_error():
    from src.agents.director import director_node
    for error_msg in [
        "no niche-matching products found",
        "Shopify API error 422",
        "recursion limit reached",
        "store is full",
    ]:
        state = _make_state(error=error_msg)
        result = await director_node(state)
        assert result["next_agent"] == "END", f"Expected END for error: {error_msg}"


# ── LLM routing ───────────────────────────────────────────────────────────────

def _mock_llm_response(next_node: str, reasoning: str = "test"):
    mock_resp = MagicMock()
    mock_resp.content = json.dumps({"next": next_node, "reasoning": reasoning})
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
    return mock_llm


@pytest.mark.asyncio
async def test_director_routes_to_store_setup_when_no_brand():
    from src.agents.director import director_node
    state = _make_state(store_brand=None, store_designed=False)
    mock_llm = _mock_llm_response("store_setup", "No brand — must setup first")

    with patch("src.agents.director.get_llm", return_value=mock_llm):
        result = await director_node(state)

    assert result["next_agent"] == "store_setup"


@pytest.mark.asyncio
async def test_director_routes_to_design_after_setup():
    from src.agents.director import director_node
    state = _make_state(
        store_brand={"store_name": "TestBrand", "niche": "rings"},
        store_designed=False,
    )
    mock_llm = _mock_llm_response("design_agent", "Brand set, design not done")

    with patch("src.agents.director.get_llm", return_value=mock_llm):
        result = await director_node(state)

    assert result["next_agent"] == "design_agent"


@pytest.mark.asyncio
async def test_director_routes_to_end_after_ecommerce():
    from src.agents.director import director_node
    state = _make_state(
        store_brand={"store_name": "TestBrand"},
        store_designed=True,
        trending_products=[{"title": "Ring", "product_id": "1"}],
        shopify_products_created=["gid://shopify/Product/123"],
    )
    mock_llm = _mock_llm_response("END", "Products created, task done")

    with patch("src.agents.director.get_llm", return_value=mock_llm):
        result = await director_node(state)

    assert result["next_agent"] == "END"


# ── MONITOR mode ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_director_fetches_health_for_monitor_task():
    from src.agents.director import director_node
    state = _make_state(
        task="[MONITOR] Check store health",
        store_brand={"store_name": "TestBrand"},
        store_designed=True,
        store_health=None,
    )
    mock_health = {"order_count": 0, "revenue_usd": 0.0, "period_days": 7, "status": "no_sales"}
    mock_llm = _mock_llm_response("marketing_agent", "No sales — launch ads")

    with patch("src.agents.director.get_sales_summary", AsyncMock(return_value=mock_health)), \
         patch("src.agents.director.get_llm", return_value=mock_llm):
        result = await director_node(state)

    assert result["store_health"] == mock_health


@pytest.mark.asyncio
async def test_director_skips_health_fetch_if_already_set():
    from src.agents.director import director_node
    existing_health = {"order_count": 5, "revenue_usd": 200.0, "period_days": 7, "status": "healthy"}
    state = _make_state(
        task="[MONITOR] Check store health",
        store_brand={"store_name": "TestBrand"},
        store_designed=True,
        store_health=existing_health,
    )
    mock_llm = _mock_llm_response("END", "Store is healthy")

    with patch("src.agents.director.get_sales_summary", AsyncMock()) as mock_fetch, \
         patch("src.agents.director.get_llm", return_value=mock_llm):
        await director_node(state)
        mock_fetch.assert_not_called()  # must not re-fetch


# ── Context in LLM call ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_director_includes_error_in_context_if_no_hard_stop():
    """When no error is set, director calls LLM with full context."""
    from src.agents.director import director_node
    state = _make_state(
        store_brand={"store_name": "TestBrand"},
        store_designed=True,
        error=None,
    )
    captured_messages = []
    mock_resp = MagicMock()
    mock_resp.content = json.dumps({"next": "END", "reasoning": "done"})
    mock_llm = MagicMock()

    async def capture_invoke(messages):
        captured_messages.extend(messages)
        return mock_resp

    mock_llm.ainvoke = capture_invoke

    with patch("src.agents.director.get_llm", return_value=mock_llm):
        await director_node(state)

    # The human message (context) must mention the task
    human_content = next(m.content for m in captured_messages if hasattr(m, 'content') and 'Task:' in m.content)
    assert "Task:" in human_content
    assert "last error: none" in human_content.lower()
