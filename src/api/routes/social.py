"""Social (Facebook Page / Instagram / TikTok) draft queue + the HUMAN approval gate.

  GET  /social/status                     per-platform connectivity (missing env NAMES only)
  GET  /social/drafts?status=&platform=   the queue
  POST /social/drafts                     create a draft by hand
  POST /social/drafts/{id}/approve        human approves AND publishes now
  POST /social/drafts/{id}/hold           park it
  POST /social/drafts/{id}/reject         send back, with {"feedback": "..."} for Lia
  POST /social/drafts/{id}/publish        retry publishing an approved draft
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_operator
from src.social_mcp import publish, queue

router = APIRouter()


@router.get("/social/status", summary="Per-platform connectivity (no secrets)")
async def social_status(_op: str = Depends(get_current_operator)) -> dict:
    return await publish.all_status()


@router.get("/social/drafts", summary="Social draft queue")
async def social_drafts(status: str = "", platform: str = "", _op: str = Depends(get_current_operator)) -> list[dict]:
    return queue.list_drafts(status, platform)


@router.post("/social/drafts", summary="Create a draft by hand")
async def social_create(body: dict, op: str = Depends(get_current_operator)) -> dict:
    try:
        return queue.add_draft(body.get("platform", "facebook"), body.get("kind", "text"), body.get("message", ""),
                               link=body.get("link", ""), media_url=body.get("media_url", ""), author=op,
                               rationale=body.get("rationale", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))


async def decide_and_maybe_publish(draft_id: str, decision: str, by: str, feedback: str = "") -> dict:
    d = queue.decide(draft_id, decision, by, feedback)
    if not d:
        raise HTTPException(404, "draft not found or already decided")
    if decision == "approve":
        return {"draft": queue.get_draft(draft_id), "publish": await publish.publish_draft(draft_id)}
    return {"draft": d}


@router.post("/social/drafts/{draft_id}/approve", summary="Human approves → publishes now")
async def social_approve(draft_id: str, op: str = Depends(get_current_operator)) -> dict:
    return await decide_and_maybe_publish(draft_id, "approve", op)


@router.post("/social/drafts/{draft_id}/hold", summary="Human parks a draft")
async def social_hold(draft_id: str, op: str = Depends(get_current_operator)) -> dict:
    return await decide_and_maybe_publish(draft_id, "hold", op)


@router.post("/social/drafts/{draft_id}/reject", summary="Human sends a draft back with feedback")
async def social_reject(draft_id: str, body: dict | None = None, op: str = Depends(get_current_operator)) -> dict:
    return await decide_and_maybe_publish(draft_id, "reject", op, (body or {}).get("feedback", ""))


@router.post("/social/drafts/{draft_id}/publish", summary="Retry publishing an approved draft")
async def social_publish(draft_id: str, _op: str = Depends(get_current_operator)) -> dict:
    r = await publish.publish_draft(draft_id)
    if not r.get("ok"):
        raise HTTPException(409 if "not approved" in r.get("error", "") else 502, r.get("error"))
    return r
