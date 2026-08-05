"""Stdio MCP server bridging OpenClaw to the rest of the roster — Ava (CEO), Nora
(Customer Support), and Milo (Fulfillment) — none of whom have a dedicated per-agent
REST surface the way Sol has /org/sol or Reel has /videos + /images. Their actions
already live in the roster-wide src/api/routes/org.py, so this bridge is a thin
httpx wrapper over THAT, parameterized by agent/role where it makes sense — same
shape as sol_bridge.py / video_bridge.py / image_bridge.py: no pipeline logic here,
every tool is a call into an existing FastAPI endpoint.

Run standalone (spawned by OpenClaw as a subprocess):
    python src/mcp_server/org_bridge.py
"""
from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8000/api/v1"

mcp = FastMCP("org-bridge")


async def _get(path: str, **params) -> dict | list:
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
async def org_state() -> dict:
    """Company state + full active roster (Ava, Sol, Reel, Nora, Milo) — names, roles,
    charters. Use this to look up an agent's exact `role` string before calling
    org_heartbeat."""
    return await _get("/org")


@mcp.tool()
async def org_heartbeat(role: str = "") -> dict:
    """Advance one agent's proactive turn right now (they act + narrate to Telegram),
    e.g. role='CEO' for Ava, 'Customer Support' for Nora, 'Fulfillment' for Milo.
    Omit role to advance whichever agent the org's own rotation picks next."""
    return await _post("/org/heartbeat", {"role": role} if role else {})


@mcp.tool()
async def org_respond(message: str, author: str = "You") -> dict:
    """Send a message into the org chat — EVERY active agent (Ava/Sol/Reel/Nora/Milo)
    replies in-persona, posted to Telegram. Use this to ask a specific agent
    something by addressing them by name/role in the message text itself."""
    return await _post("/org/respond", {"message": message, "author": author})


@mcp.tool()
async def org_tickets_list(status: str = "") -> dict:
    """List the agent ticket board (auto-assigned to Sol, with deadlines/priority).
    Filter by status (e.g. 'open') or omit for all."""
    return await _get("/org/tickets", **({"status": status} if status else {}))


@mcp.tool()
async def org_ticket_create(title: str, description: str = "", created_by: str = "Itzik") -> dict:
    """Open a new ticket for the team to work."""
    return await _post("/org/tickets", {"title": title, "description": description, "created_by": created_by})


@mcp.tool()
async def org_ticket_update(ticket_id: str, status: str = "", assignee: str = "", priority: str = "") -> dict:
    """Update a ticket's status/assignee/priority. Only non-empty fields are applied."""
    body = {k: v for k, v in {"status": status, "assignee": assignee, "priority": priority}.items() if v}
    return await _patch(f"/org/tickets/{ticket_id}", body)


@mcp.tool()
async def org_proposals_list(status: str = "pending") -> list[dict]:
    """Ava/Sol's pending Shopify action proposals awaiting the owner's approval gate."""
    return await _get("/org/proposals", status=status)


@mcp.tool()
async def org_proposal_approve(proposal_id: str) -> dict:
    """Approve a pending proposal — it EXECUTES the real Shopify action. NEVER call
    this yourself on the owner's behalf; only after the owner has explicitly said to
    approve this specific proposal."""
    return await _post(f"/org/proposals/{proposal_id}/approve", {})


@mcp.tool()
async def org_proposal_reject(proposal_id: str) -> dict:
    """Reject a pending proposal. Same rule as approve — only on explicit owner
    instruction, never inferred."""
    return await _post(f"/org/proposals/{proposal_id}/reject", {})


@mcp.tool()
async def org_fulfill_latest(confirm: bool = False) -> dict:
    """Milo's manual dropship trigger for the latest paid order. With confirm=false
    (default) this only RETURNS the order + shipping address + CJ mapping for
    review — nothing is placed. NEVER call with confirm=true yourself on the
    owner's behalf; only after the owner has explicitly said to place this real
    CJ order."""
    return await _post("/org/fulfill-latest", {"confirm": confirm})


@mcp.tool()
async def org_announce(message: str) -> dict:
    """Post a founder announcement — goes to Telegram and is recorded as a company
    lesson every agent acts on."""
    return await _post("/org/announce", {"message": message})


if __name__ == "__main__":
    mcp.run(transport="stdio")
