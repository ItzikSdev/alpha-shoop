"""Stdio MCP server bridging external chat clients (OpenClaw) to Sol.

Sol is the sole autonomous agent (`src/org/seed.py`) that owns the alphaforbaby
Hydrogen storefront end to end. This bridge never touches store files itself —
every tool here is a thin call into Sol's own existing FastAPI endpoints
(`src/api/routes/org.py`), so Sol remains the only thing that edits store code.

Run standalone (spawned by OpenClaw as a subprocess):
    python src/mcp_server/sol_bridge.py
"""
from __future__ import annotations

from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8000/api/v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
STORE_MEMORY_PATH = REPO_ROOT / "stores/shopify/hydrogen-alphaforbaby/docs/STORE_MEMORY.md"

mcp = FastMCP("sol-bridge")


async def _get(path: str, **params) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{API_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API_BASE}{path}", json=body)
        r.raise_for_status()
        return r.json()


async def _patch(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(f"{API_BASE}{path}", json=body)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def sol_run_task(
    task: str, store_slug: str = "alphaforbaby", max_steps: int = 25,
    ticket_id: str | None = None, max_minutes: float = 0,
) -> dict:
    """Fire Sol's tool-use loop on a task (CJ sourcing + copywriting + Shopify push). Returns
    a run_id immediately — the run itself continues in the background and narrates to Slack.
    `max_minutes` (0 = no cap) is the real wall-clock budget for scheduled/cron-triggered runs —
    since this tool returns immediately, a cron job's own timeout never bounds the real work;
    pass max_minutes to actually cap it (e.g. 30 for a "30 minutes every 2 hours" schedule)."""
    body = {"task": task, "store_slug": store_slug, "max_steps": max_steps}
    if ticket_id:
        body["ticket_id"] = ticket_id
    if max_minutes:
        body["max_minutes"] = max_minutes
    return await _post("/org/sol", body)


@mcp.tool()
async def sol_get_run(run_id: str) -> dict:
    """Full step history and status of one of Sol's runs."""
    return await _get(f"/org/agents/runs/{run_id}")


@mcp.tool()
async def sol_list_runs(limit: int = 20) -> list[dict]:
    """Sol's most recent runs, newest first."""
    return await _get("/org/agents/runs", agent="Sol", limit=limit)


@mcp.tool()
async def list_all_agent_runs(limit: int = 20) -> list[dict]:
    """Recent runs across EVERY agent, not just Sol — for a manager/monitor checking
    on multiple agents' scheduled work, not a specific one."""
    return await _get("/org/agents/runs", limit=limit)


@mcp.tool()
async def sol_list_tickets(status: str | None = None) -> dict:
    """The agent ticket board (auto-assigned to Sol). Optionally filter by status
    (e.g. 'open', 'doing', 'done')."""
    params = {"status": status} if status else {}
    return await _get("/org/tickets", **params)


@mcp.tool()
async def sol_create_ticket(title: str, description: str, store_id: str = "alphaforbaby") -> dict:
    """Open a new ticket for Sol (auto-assigned with a priority + SLA deadline)."""
    return await _post("/org/tickets", {"title": title, "description": description, "store_id": store_id})


@mcp.tool()
async def sol_update_ticket(ticket_id: str, **fields) -> dict:
    """Update a ticket's status/assignee/priority/due date."""
    return await _patch(f"/org/tickets/{ticket_id}", fields)


@mcp.tool()
def sol_get_context() -> str:
    """Sol's real charter (who he is, what he owns, his rules) plus the tail of his
    live store memory — call this to ground yourself in who Sol actually is before
    answering questions about him or the store, instead of guessing."""
    from src.org.seed import _FOUNDERS

    charter = next((f[4] for f in _FOUNDERS if f[0] == "Sol"), "Sol's charter not found in src/org/seed.py")

    memory_tail = "STORE_MEMORY.md not found."
    if STORE_MEMORY_PATH.exists():
        lines = STORE_MEMORY_PATH.read_text().splitlines()
        memory_tail = "\n".join(lines[-80:])

    return (
        "# Sol's charter (src/org/seed.py)\n"
        f"{charter}\n\n"
        "# Sol's current store memory (docs/STORE_MEMORY.md, tail)\n"
        f"{memory_tail}"
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
