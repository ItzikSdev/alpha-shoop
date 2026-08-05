"""Stdio MCP server bridging OpenClaw's video agent ("reel") to the baby-outfit-swap
image pipeline.

Same shape as video_bridge.py: every tool here is a thin call into the FastAPI
endpoints (`src/api/routes/images.py`) — this bridge never touches Ollama/ComfyUI/
Shopify/RAG directly, so the actual pipeline logic lives in one place.

Run standalone (spawned by OpenClaw as a subprocess):
    python src/mcp_server/image_bridge.py
"""
from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8000/api/v1"
DEFAULT_STORE = "alphaforbaby"

mcp = FastMCP("image-bridge")


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
async def image_list_candidates(store_id: str = DEFAULT_STORE) -> list[dict]:
    """Live products that don't have a baby-outfit image yet (pending/approved/
    published all count as 'already has one'). Each entry has id, title,
    description, image_urls — pick one of these + one of its image_urls before
    calling image_generate."""
    return await _get("/images/candidates", store_id=store_id)


@mcp.tool()
async def image_generate(product_id: str, source_image_url: str = "", store_id: str = DEFAULT_STORE) -> dict:
    """Kick off the pipeline (vision check -> garment description -> Wan2.2 render ->
    still frame) for one product. Returns immediately with an image_id — the render
    continues in the background; it posts an album (original + generated) to
    Telegram for review when it finishes, or on failure the DB row's status becomes
    'failed' with an error message (e.g. no adult person detected in that photo —
    route that product through video_generate's PRODUCT_3D_SHOWCASE style instead).
    source_image_url defaults to the product's primary photo if omitted."""
    body = {"store_id": store_id, "product_id": product_id}
    if source_image_url:
        body["source_image_url"] = source_image_url
    return await _post("/images/generate", body)


@mcp.tool()
async def image_list(store_id: str = DEFAULT_STORE, status: str = "") -> list[dict]:
    """List baby-outfit images and their status (rendering/pending_review/approved/
    rejected/published/failed). Filter by status to e.g. check on ones still
    pending review."""
    params = {"store_id": store_id}
    if status:
        params["status"] = status
    return await _get("/images", **params)


@mcp.tool()
async def image_approve(image_id: str) -> dict:
    """Approve a pending_review image — uploads it to Shopify as product media and
    writes back into RAG so future scans know this product is done. NEVER call this
    yourself on the owner's behalf; only call it after the owner has explicitly said
    to approve/publish this specific image."""
    return await _post(f"/images/{image_id}/approve", {})


@mcp.tool()
async def image_reject(image_id: str) -> dict:
    """Reject a pending_review image. Same rule as approve — only on explicit
    owner instruction, never inferred."""
    return await _post(f"/images/{image_id}/reject", {})


if __name__ == "__main__":
    mcp.run(transport="stdio")
