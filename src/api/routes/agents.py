"""Agent execution endpoints — trigger and poll the LangGraph graph."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter()

# In-memory run store (replace with Redis/DB in production)
_runs: dict[str, RunStatusResponse] = {}
_kill_switch = KillSwitch()


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

    # Enqueue graph run (in production: ARQ task or asyncio background task)
    _runs[thread_id] = RunStatusResponse(thread_id=thread_id, status=RunStatus.PENDING)

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
    """
    Call any registered MCP tool by name for testing.
    In production this goes through the MCP server; here it's a direct call.
    """
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
