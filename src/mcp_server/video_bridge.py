"""Stdio MCP server bridging OpenClaw's video agent ("reel") to the ad-video pipeline.

Same shape as sol_bridge.py: every tool here is a thin call into the FastAPI
endpoints (`src/api/routes/videos.py`) — this bridge never touches ComfyUI, Slack,
or Shopify directly, so the actual pipeline logic lives in one place.

Run standalone (spawned by OpenClaw as a subprocess):
    python src/mcp_server/video_bridge.py
"""
from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8000/api/v1"
DEFAULT_STORE = "alphaforbaby"

mcp = FastMCP("video-bridge")


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


@mcp.tool()
async def video_list_candidates(store_id: str = DEFAULT_STORE) -> list[dict]:
    """Live products that don't have an ad video yet (pending/approved/published all
    count as 'already has one'). Each entry has id, title, description, image_url —
    pick one of these before calling video_generate."""
    return await _get("/videos/candidates", store_id=store_id)


@mcp.tool()
async def video_generate(product_id: str, store_id: str = DEFAULT_STORE) -> dict:
    """Kick off the full pipeline (qwen3 script -> Wan2.2 scenes -> voiceover ->
    assembly) for one product. Returns immediately with a video_id — the render
    itself can take a long time (see wan_video.py's timing notes) and continues in
    the background; it posts to Slack for review when it finishes, or on failure
    the DB row's status becomes 'failed' with an error message."""
    return await _post("/videos/generate", {"store_id": store_id, "product_id": product_id})


@mcp.tool()
async def video_list(store_id: str = DEFAULT_STORE, status: str = "") -> list[dict]:
    """List ad videos and their status (rendering/pending_review/approved/rejected/
    published/failed). Filter by status to e.g. check on ones still pending review."""
    params = {"store_id": store_id}
    if status:
        params["status"] = status
    return await _get("/videos", **params)


@mcp.tool()
async def video_approve(video_id: str) -> dict:
    """Approve a pending_review video — uploads it to Shopify as product media.
    NEVER call this yourself on the owner's behalf; only call it after the owner has
    explicitly said to approve/publish this specific video."""
    return await _post(f"/videos/{video_id}/approve", {})


@mcp.tool()
async def video_reject(video_id: str) -> dict:
    """Reject a pending_review video. Same rule as approve — only on explicit
    owner instruction, never inferred."""
    return await _post(f"/videos/{video_id}/reject", {})


if __name__ == "__main__":
    mcp.run(transport="stdio")
