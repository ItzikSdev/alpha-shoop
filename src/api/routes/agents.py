"""Agent execution endpoints — trigger and poll the LangGraph graph."""
from __future__ import annotations
import asyncio
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from src.agents.graph import graph
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
from src.tracing import trace_store, TraceCallback, current_thread_id

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory run store (replace with Redis/DB in production)
_runs: dict[str, RunStatusResponse] = {}
_kill_switch = KillSwitch()


async def _execute_graph(thread_id: str, task: str, operator: str, max_budget_usd: float) -> None:
    """Background task: streams the LangGraph run, updating _runs live per node."""
    # Set context var so TraceCallback can find this thread's store entry
    current_thread_id.set(thread_id)
    trace_store.start_run(thread_id=thread_id, task=task, operator=operator)

    run = _runs[thread_id]
    run.status = RunStatus.RUNNING

    state: AgentState = {
        "task": task,
        "thread_id": thread_id,
        "operator": operator,
        "messages": [],
        "next_agent": None,
        "director_reasoning": None,
        "trending_products": [],
        "shopify_products_created": [],
        "campaign_ids": [],
        "total_ad_spend_usd": 0.0,
        "fulfilled_orders": [],
        "budget_remaining_usd": max_budget_usd,
        "kill_switch_triggered": False,
        "run_complete": False,
        "error": None,
    }
    try:
        callback = TraceCallback()
        async for step in graph.astream(
            state,
            config={"recursion_limit": 25, "callbacks": [callback]},
        ):
            for node_name, delta in step.items():
                state.update(delta)
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
        run.result = {
            "trending_products": state.get("trending_products", []),
            "shopify_products_created": state.get("shopify_products_created", []),
            "campaign_ids": state.get("campaign_ids", []),
            "fulfilled_orders": state.get("fulfilled_orders", []),
            "director_reasoning": state.get("director_reasoning", ""),
        }
    except Exception as exc:
        logger.exception("Agent run %s failed", thread_id)
        run.status = RunStatus.FAILED
        trace_store.finish_run(thread_id, "failed")
        run.error = str(exc)
        run.result = {
            "trending_products": state.get("trending_products", []),
            "shopify_products_created": state.get("shopify_products_created", []),
            "campaign_ids": state.get("campaign_ids", []),
            "fulfilled_orders": state.get("fulfilled_orders", []),
            "director_reasoning": state.get("director_reasoning", ""),
        }


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
    _runs[thread_id] = RunStatusResponse(thread_id=thread_id, status=RunStatus.PENDING)
    asyncio.create_task(_execute_graph(thread_id, body.task, operator, body.max_budget_usd))

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
