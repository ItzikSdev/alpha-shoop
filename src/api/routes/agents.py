"""Agent execution endpoints — trigger and poll the LangGraph graph."""
from __future__ import annotations
import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from src.agents.orchestrator import run_pipeline
from src.agents.state import AgentState
from src.models.requests import RunAgentRequest, KillSwitchRequest, TestToolRequest
from src.models.responses import (
    AgentRunResponse,
    RunStatus,
    RunStatusResponse,
    KillSwitchResponse,
    ToolCallResponse,
)
from src.api.deps import get_current_operator
from src.guardrails.kill_switch import KillSwitch
from src.stores import _current_store, get_store, update_store_brand, update_store_designed
from src.tracing import trace_store, TraceCallback, current_thread_id, current_trace_callback
from src.tracing.persist import save_all

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory run store (kill-switch tracking)
_runs: dict[str, RunStatusResponse] = {}
_kill_switch = KillSwitch()

# ── Daemon mode config (in-memory) ────────────────────────────────────────────
DEFAULT_DAEMON_TASK = (
    "Build a store for trending home decor products under $50. "
    "Set up the store brand, find top products with 30%+ margin, "
    "list them on Shopify with great copy."
)

_daemon: dict = {
    "enabled": False,
    "interval_minutes": 60,
    "task": DEFAULT_DAEMON_TASK,
    "last_started_at": None,
    "next_run_at": None,
}


async def _execute_graph(
    thread_id: str, task: str, operator: str, max_budget_usd: float, store_id: str | None = None
) -> None:
    """Background task: streams the LangGraph run, updating _runs live per node."""
    current_thread_id.set(thread_id)
    # NOTE: trace_store.start_run() is called before this task is spawned so the
    # /trace endpoint is immediately available (avoids 404 race condition).

    run = _runs[thread_id]
    run.status = RunStatus.RUNNING

    # Activate per-store credentials so all Shopify tools use the right store
    store_cfg = None
    cached_brand: dict | None = None
    cached_designed = False
    if store_id:
        store_cfg = get_store(store_id)
        if store_cfg:
            _current_store.set(store_cfg)
            if store_cfg.store_brand:
                cached_brand = store_cfg.store_brand
            # store_designed must be its own persisted fact, not derived from
            # "has a brand brief" — confirmed real bug: a store can have a
            # cached brand from store_setup while its theme was never actually
            # customized (design loop never ran), and deriving store_designed
            # as bool(cached_brand) made that permanent — design_agent/
            # frontend_agent would silently never run again for that store.
            cached_designed = store_cfg.store_designed

    # [SETUP_ONLY] and [REBUILD] always start fresh — ignore cached brand/design
    # so design_agent + store_setup are guaranteed to run
    force_rebuild = "[SETUP_ONLY]" in task or "[REBUILD]" in task
    if force_rebuild:
        cached_brand = None
        cached_designed = False
    elif "[REDESIGN]" in task:
        # Re-run just the design loop against the existing brand brief — unlike
        # [REBUILD]/[SETUP_ONLY] this keeps cached_brand so store_setup_node
        # (and its brand-new brand brief) never runs again.
        cached_designed = False

    state: AgentState = {
        "task": task,
        "thread_id": thread_id,
        "operator": operator,
        "store_id": store_id,
        "messages": [],
        "trending_products": [],
        "sourcing_attempts": 0,
        "sourcing_feedback": None,
        "shopify_products_created": [],
        "campaign_ids": [],
        "total_ad_spend_usd": 0.0,
        "fulfilled_orders": [],
        "budget_remaining_usd": max_budget_usd,
        # Pre-load cached brand brief so agents don't rebuild from scratch
        "store_brand": cached_brand,
        "store_designed": cached_designed,
        "design_spec": None,
        "design_iterations": 0,
        "design_approved": False,
        "frontend_report": None,
        "store_health": None,
        "store_knowledge": None,
        "kill_switch_triggered": False,
        "run_complete": False,
        "error": None,
    }
    try:
        callback = TraceCallback()
        current_trace_callback.set(callback)
        # run_pipeline mutates `state` in place as it goes (same object reference) —
        # unlike the old graph.astream() loop, nothing here needs to re-apply deltas;
        # doing so would actively re-clobber `messages` (appended internally, not
        # overwritten) back down to just the latest delta.
        async for step in run_pipeline(state):
            for node_name, _delta in step.items():
                run.current_node = node_name
                run.products_found = len(state.get("trending_products", []))
                run.orders_placed = len(state.get("shopify_products_created", []))
                run.ad_spend_usd = state.get("total_ad_spend_usd", 0.0)
            if _kill_switch.is_active:
                run.status = RunStatus.KILLED
                trace_store.finish_run(thread_id, "killed")
                return
        run.status = RunStatus.COMPLETED
        trace_store.finish_run(thread_id, "completed")
        await asyncio.to_thread(save_all, trace_store)

        # Persist brand brief + design status back to store config so future
        # runs reuse them correctly instead of re-deriving store_designed from
        # "has a brand" (see cached_designed note above).
        if store_id and state.get("store_brand"):
            await asyncio.to_thread(update_store_brand, store_id, state["store_brand"])
        if store_id and state.get("store_designed"):
            await asyncio.to_thread(update_store_designed, store_id, True)

        run.result = {
            "trending_products": state.get("trending_products", []),
            "shopify_products_created": state.get("shopify_products_created", []),
            "campaign_ids": state.get("campaign_ids", []),
            "fulfilled_orders": state.get("fulfilled_orders", []),
            "summary": state.get("error") or "completed",
        }
    except Exception as exc:
        logger.exception("Agent run %s failed", thread_id)
        run.status = RunStatus.FAILED
        trace_store.finish_run(thread_id, "failed")
        await asyncio.to_thread(save_all, trace_store)
        run.error = str(exc)
        run.result = {
            "trending_products": state.get("trending_products", []),
            "shopify_products_created": state.get("shopify_products_created", []),
            "campaign_ids": state.get("campaign_ids", []),
            "fulfilled_orders": state.get("fulfilled_orders", []),
            "summary": state.get("error") or "completed",
        }


def _spawn_run(
    thread_id: str, task: str, operator: str, max_budget_usd: float, store_id: str | None = None
) -> None:
    """Create trace entry + _runs entry, then spawn background task."""
    trace_store.start_run(thread_id=thread_id, task=task, operator=operator)
    _runs[thread_id] = RunStatusResponse(thread_id=thread_id, status=RunStatus.PENDING)
    asyncio.create_task(_execute_graph(thread_id, task, operator, max_budget_usd, store_id))


@router.post(
    "/run",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger agent graph",
    description=(
        "Start a new multi-agent LangGraph run. "
        "Returns a thread_id to poll with GET /status/{thread_id}."
    ),
)
async def trigger_run(
    body: RunAgentRequest,
    operator: str = Depends(get_current_operator),
) -> AgentRunResponse:
    if _kill_switch.is_active:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kill-switch is active — all runs are halted.",
        )
    thread_id = body.thread_id or str(uuid.uuid4())
    _spawn_run(thread_id, body.task, operator, body.max_budget_usd, body.store_id)
    return AgentRunResponse(thread_id=thread_id, status=RunStatus.PENDING)


@router.get(
    "/status/{thread_id}",
    response_model=RunStatusResponse,
    summary="Poll agent run status",
)
async def get_run_status(thread_id: str) -> RunStatusResponse:
    run = _runs.get(thread_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id!r} not found")
    return run


@router.post(
    "/kill-switch",
    response_model=KillSwitchResponse,
    summary="Emergency stop",
    description="Immediately halts all running agent threads. Audit-logged.",
)
async def activate_kill_switch(
    body: KillSwitchRequest,
    operator: str = Depends(get_current_operator),
) -> KillSwitchResponse:
    stopped = _kill_switch.activate(reason=body.reason, operator=operator)
    killed_count = 0
    for run in _runs.values():
        if run.status == RunStatus.RUNNING:
            run.status = RunStatus.KILLED
            killed_count += 1
    return KillSwitchResponse(
        killed=True,
        threads_stopped=killed_count,
        message=f"Kill-switch activated by {operator}: {body.reason}",
    )


@router.post(
    "/tools/invoke",
    response_model=ToolCallResponse,
    summary="Invoke a single MCP tool directly (dev/test)",
)
async def invoke_tool(
    body: TestToolRequest,
    operator: str = Depends(get_current_operator),
) -> ToolCallResponse:
    import time
    from src.mcp_tools.server import invoke_tool as _invoke

    start = time.perf_counter()
    try:
        result = await _invoke(body.tool_name, body.arguments)
        duration = (time.perf_counter() - start) * 1000
        return ToolCallResponse(tool_name=body.tool_name, success=True, result=result, duration_ms=duration)
    except Exception as exc:
        duration = (time.perf_counter() - start) * 1000
        return ToolCallResponse(tool_name=body.tool_name, success=False, error=str(exc), duration_ms=duration)


# ── Trace / observability endpoints ──────────────────────────────────────────

@router.get(
    "/runs",
    summary="List all agent runs with token/timing summary",
)
async def list_runs() -> list[dict]:
    return [r.to_summary() for r in trace_store.list_runs()]


@router.get(
    "/runs/{thread_id}/trace",
    summary="Full trace: every LLM call with prompts, response, and token counts",
)
async def get_run_trace(thread_id: str) -> dict:
    run = trace_store.get_run(thread_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Trace for {thread_id!r} not found")
    return run.to_dict()


@router.get(
    "/runs/{thread_id}/logs",
    summary="All log entries for a run (no SSE — snapshot)",
)
async def get_run_logs(thread_id: str) -> list[dict]:
    run = trace_store.get_run(thread_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Trace for {thread_id!r} not found")
    return [e.to_dict() for e in run.logs]


@router.get(
    "/runs/{thread_id}/stream",
    summary="SSE stream of live log entries and LLM call completions",
    # No JWT dep — EventSource cannot set Authorization headers
)
async def stream_run(thread_id: str) -> StreamingResponse:
    async def generate():
        # Retry up to 3s for run to appear (handles very fast clients)
        run = None
        for _ in range(15):
            run = trace_store.get_run(thread_id)
            if run:
                break
            await asyncio.sleep(0.2)

        if not run:
            yield f"data: {json.dumps({'type': 'error', 'msg': 'Run not found'})}\n\n"
            return

        sent_logs = 0
        sent_calls = 0

        while True:
            # Flush new log entries
            for entry in run.logs[sent_logs:]:
                yield f"data: {json.dumps({'type': 'log', **entry.to_dict()})}\n\n"
                sent_logs += 1

            # Flush new LLM call completions (summary only — full trace via /trace)
            for call in run.llm_calls[sent_calls:]:
                yield f"data: {json.dumps({'type': 'llm_call', 'node': call.node, 'model': call.model, 'tokens': call.input_tokens + call.output_tokens, 'duration_ms': round(call.duration_ms), 'ts': call.timestamp, 'error': call.error})}\n\n"
                sent_calls += 1

            if run.status not in ("running", "pending"):
                yield f"data: {json.dumps({'type': 'done', 'status': run.status})}\n\n"
                return

            # Keepalive comment (prevents proxy timeout)
            yield ": keepalive\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Daemon mode endpoints ─────────────────────────────────────────────────────

@router.get("/daemon", summary="Get daemon (auto-run) config")
async def get_daemon() -> dict:
    return dict(_daemon)


@router.post("/daemon", summary="Update daemon (auto-run) config")
async def set_daemon(body: dict) -> dict:
    allowed = {"enabled", "interval_minutes", "task"}
    for k, v in body.items():
        if k in allowed:
            _daemon[k] = v
    return dict(_daemon)
