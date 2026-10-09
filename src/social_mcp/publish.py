"""One place that turns an APPROVED draft into a live post (used by MCP + API)."""
from __future__ import annotations

from src.social_mcp import meta, queue, tiktok


async def publish_draft(draft_id: str) -> dict:
    d = queue.get_draft(draft_id)
    if not d:
        return {"ok": False, "error": "draft not found"}
    if d["status"] != "approved":
        return {"ok": False, "error": f"draft is '{d['status']}', not approved — a human must approve it first"}
    try:
        if d["platform"] == "facebook":
            rid = await meta.publish_facebook(d["kind"], d["message"], link=d["link"], media_url=d["media_url"])
        elif d["platform"] == "instagram":
            rid = await meta.publish_instagram(d["kind"], d["message"], media_url=d["media_url"])
        elif d["platform"] == "tiktok":
            rid = await tiktok.publish_video(d["message"], d["media_url"])
        else:
            return {"ok": False, "error": f"unknown platform {d['platform']}"}
    except Exception as e:  # noqa: BLE001
        queue.mark_failed(draft_id, str(e))
        return {"ok": False, "error": str(e)[:300]}
    queue.mark_published(draft_id, rid)
    return {"ok": True, "platform": d["platform"], "remote_id": rid}


async def all_status() -> dict:
    m = await meta.status()
    return {**m, "tiktok": await tiktok.status()}
