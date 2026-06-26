"""
Single deterministic pipeline orchestrator — replaces the old director.py +
graph.py LLM-routed LangGraph setup.

Why: director made one extra LLM call after every single step just to decide
which worker runs next, and its "ROUTING RULES" were almost entirely mechanical
(if design_spec exists -> Mode 2 review, if [MARKETING] in task -> marketing_agent).
That extra indirection was also the direct cause of a real production bug: when
trend_scraper returned zero raw candidates, director had no special-cased signal
for "stop" and just kept calling trend_scraper again with identical inputs —
confirmed via trace logs to repeat 15+ times, burning ~1.5M tokens before a
circuit breaker was added inside trend_scraper itself (see trend_scraper.py).

This module reads the same task-tag convention already used elsewhere
([REBUILD], [SETUP_ONLY], [MARKETING], [MONITOR]) and sequences the existing,
unmodified worker node functions with plain Python control flow instead.

`run_pipeline` is an async generator yielding {"node_name": delta} after each
step — the exact shape `graph.astream()` used to produce — so the consuming loop
in src/api/routes/agents.py needed only its iteration source changed.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from src.agents.state import AgentState
from src.agents.workers.ecommerce import ecommerce_node
from src.agents.workers.design_agent import design_node
from src.agents.workers.frontend_agent import frontend_node
from src.agents.workers.fulfillment import fulfillment_node
from src.agents.workers.marketing import marketing_node
from src.agents.workers.store_setup import store_setup_node
from src.agents.workers.trend_scraper import trend_scraper_node
from src.embeddings import query_store_knowledge
from src.mcp_tools.shopify import list_shopify_products
from src.mcp_tools.shopify_analytics import get_sales_summary
from src.tracing import agent_log
from src.tracing.context import current_node

# Mirrors ecommerce.py's _MAX_STORE_PRODUCTS — the catalog-fill loop stops once
# the store reaches this count (or a worker sets `error`, whichever first).
from src.agents.workers.ecommerce import _MAX_STORE_PRODUCTS

# Same safety role LangGraph's recursion_limit played — guards against any loop
# condition that fails to terminate as expected.
_MAX_STEPS = 60


async def _run_step(name: str, fn, state: AgentState) -> dict:
    """Run one worker, merge its delta into state, return the delta for yielding.

    `messages` is special: LangGraph's old `add_messages` reducer appended new
    messages rather than overwriting the list (every other field is plain
    last-write-wins, which a normal dict update already replicates correctly).
    """
    delta = await fn(state)
    new_messages = delta.pop("messages", None)
    state.update(delta)
    if new_messages:
        state["messages"] = state.get("messages", []) + new_messages
        delta["messages"] = new_messages
    return delta


async def run_pipeline(state: AgentState) -> AsyncIterator[dict]:
    """Drive the full store-building/maintenance pipeline for one run."""
    task = state.get("task", "")
    force_rebuild = "[REBUILD]" in task or "[SETUP_ONLY]" in task
    # [REDESIGN] stops after the design loop same as [SETUP_ONLY], but (per
    # agents.py) leaves store_brand cached — so this re-runs design_agent/
    # frontend_agent against the existing brand brief instead of a fresh one,
    # and never touches the product catalog.
    stop_after_design = "[SETUP_ONLY]" in task or "[REDESIGN]" in task
    do_marketing = "[MARKETING]" in task
    is_monitor = "[MONITOR]" in task

    steps = 0

    def _budget_ok() -> bool:
        nonlocal steps
        steps += 1
        return steps <= _MAX_STEPS

    if state.get("kill_switch_triggered"):
        return

    # Agentic RAG: fetch once per run, scoped to this store. Fed into
    # trend_scraper's own LLM-driven category-search step (see
    # trend_scraper.py::_get_niche_categories) rather than a director prompt —
    # that's the one place a "what should we actually search for" judgment call
    # already goes through an LLM, so the store's own description can inform it
    # directly instead of indirectly via a routing prompt.
    store_id = state.get("store_id")
    if state.get("store_knowledge") is None and store_id:
        knowledge = await query_store_knowledge(task, store_id=store_id, top_k=2)
        if knowledge:
            agent_log(f"Retrieved store knowledge ({len(knowledge)} match(es)) via RAG", "info")
        state["store_knowledge"] = knowledge
        yield {"orchestrator": {"store_knowledge": knowledge}}

    if is_monitor:
        current_node.set("orchestrator")
        agent_log("Fetching store revenue and sales data...", "info")
        health = await get_sales_summary(days=7)
        agent_log(
            f"Store health: {health['status']} | {health['order_count']} orders | "
            f"${health['revenue_usd']} revenue (7d)",
            "action",
        )
        state["store_health"] = health
        yield {"orchestrator": {"store_health": health}}

        try:
            existing_products = await list_shopify_products()
        except Exception:
            existing_products = []

        if not existing_products or health["status"] == "low":
            async for delta in _catalog_fill_loop(state, _budget_ok):
                yield delta
        elif health["status"] == "no_sales":
            delta = await _run_step("marketing_agent", marketing_node, state)
            yield {"marketing_agent": delta}
        # "healthy" -> nothing to do, fall through to fulfillment check below

    else:
        if not state.get("store_brand") or force_rebuild:
            if force_rebuild:
                state["store_brand"] = None
            delta = await _run_step("store_setup", store_setup_node, state)
            yield {"store_setup": delta}
            if state.get("error") or not _budget_ok():
                return

        async for delta in _design_loop(state, _budget_ok):
            yield delta
        if state.get("error"):
            return

        if not stop_after_design:
            async for delta in _catalog_fill_loop(state, _budget_ok):
                yield delta

            if do_marketing and not state.get("error"):
                delta = await _run_step("marketing_agent", marketing_node, state)
                yield {"marketing_agent": delta}

    if state.get("pending_orders") and not state.get("error"):
        delta = await _run_step("fulfillment_agent", fulfillment_node, state)
        yield {"fulfillment_agent": delta}


async def _design_loop(state: AgentState, budget_ok) -> AsyncIterator[dict]:
    """design_agent Mode 1 -> frontend_agent -> design_agent Mode 2, repeat.

    design_node force-approves by its own 3rd review iteration (see
    design_agent.py MAX_DESIGN_ITERATIONS), so this loop's only job is to keep
    calling the right next step until store_designed flips True.
    """
    while not state.get("store_designed"):
        if not budget_ok():
            agent_log("Design loop hit the step safety cap — stopping", "warning")
            return
        if not state.get("design_spec"):
            delta = await _run_step("design_agent", design_node, state)
            yield {"design_agent": delta}
        else:
            delta = await _run_step("frontend_agent", frontend_node, state)
            yield {"frontend_agent": delta}
            delta = await _run_step("design_agent", design_node, state)
            yield {"design_agent": delta}
        if state.get("error"):
            return


async def _catalog_fill_loop(state: AgentState, budget_ok) -> AsyncIterator[dict]:
    """trend_scraper -> ecommerce_manager, repeat until the store reaches the
    product cap or a worker reports an error.

    Both workers already enforce their own retry/circuit-breaker limits
    internally (sourcing_attempts maxes out at 3, then sets `error` directly) —
    this loop's only job is to keep requesting more batches until the cap or an
    error, mirroring director's old CATALOG-FILL LOOP rule.
    """
    while (
        len(state.get("shopify_products_created", [])) < _MAX_STORE_PRODUCTS
        and not state.get("error")
    ):
        if not budget_ok():
            agent_log("Catalog-fill loop hit the step safety cap — stopping", "warning")
            return
        delta = await _run_step("trend_scraper", trend_scraper_node, state)
        yield {"trend_scraper": delta}
        if state.get("error"):
            return
        delta = await _run_step("ecommerce_manager", ecommerce_node, state)
        yield {"ecommerce_manager": delta}
