"""Product ad video pipeline: generate → Slack review → approve/reject → publish.

Mirrors the shape of /org/sol in src/api/routes/org.py — POST /videos/generate
kicks off the pipeline as a background task and returns immediately with an id;
the render itself (script → per-scene Wan2.2 + voiceover → assembly) can take a
long time (see src/video/wan_video.py's timing notes), so callers never block on it.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select

from src.db.engine import get_session
from src.db.models import ProductVideo
from src.stores import _current_store, get_store
from src.mcp_tools.shopify import get_products_for_video, attach_local_video_to_product
from src.org.telegram import post_video_as
from src.video.pipeline import generate_product_ad
from src.video.schemas import VideoStyle

logger = logging.getLogger(__name__)
router = APIRouter()


def _use_store(store_id: str):
    store = get_store(store_id)
    if store:
        _current_store.set(store)
    return store


@router.get("/videos/candidates", summary="Live products eligible for a new ad video")
async def get_video_candidates(store_id: str) -> list[dict]:
    if not _use_store(store_id):
        return []
    products = await get_products_for_video()

    async with get_session() as session:
        rows = (await session.execute(
            select(ProductVideo.shopify_product_id).where(
                ProductVideo.store_id == store_id,
                ProductVideo.status.in_(["pending_review", "approved", "published"]),
            )
        )).scalars().all()
    already_has_video = set(rows)
    return [p for p in products if p["id"] not in already_has_video]


async def _run_pipeline(video_id: str, store_id: str, product: dict, style: VideoStyle = "AVATAR_UGC") -> None:
    _use_store(store_id)
    try:
        result = await generate_product_ad(
            product_title=product["title"],
            product_description=product.get("description", ""),
            product_image_url=product["image_url"],
            style=style,
        )
        caption = (
            f"*{product['title']}* — {style.replace('_', ' ').title()} ad ready for review\n"
            f"Hook: {result.script.hook}\n"
            f"Reply here to approve/reject, or use the dashboard's Videos page."
        )
        slack_ts = await post_video_as("Reel", "Video Producer", str(result.video_path), caption)

        async with get_session() as session:
            row = await session.get(ProductVideo, video_id)
            row.file_path = str(result.video_path)
            row.script_json = result.script.model_dump_json()
            row.slack_ts = slack_ts
            row.status = "pending_review"
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
    except Exception as exc:
        logger.exception("video pipeline failed for %s", video_id)
        async with get_session() as session:
            row = await session.get(ProductVideo, video_id)
            row.status = "failed"
            row.error = str(exc)[:2000]
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)


@router.post("/videos/generate", summary="Render a new ad video for one product (runs in the background)")
async def post_generate_video(body: dict) -> dict:
    store_id = body.get("store_id", "")
    product_id = body.get("product_id", "")
    style: VideoStyle = body.get("style") or "AVATAR_UGC"
    if style not in ("AVATAR_UGC", "PRODUCT_3D_SHOWCASE"):
        return {"error": f"unknown style {style!r} — use AVATAR_UGC or PRODUCT_3D_SHOWCASE"}
    if not (store_id and product_id):
        return {"error": "missing 'store_id' or 'product_id'"}
    if not _use_store(store_id):
        return {"error": f"unknown store_id {store_id!r}"}

    products = await get_products_for_video()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return {"error": f"product {product_id!r} not found or has no image"}

    video_id = uuid.uuid4().hex
    async with get_session() as session:
        session.add(ProductVideo(
            id=video_id,
            store_id=store_id,
            shopify_product_id=product_id,
            product_title=product["title"],
            file_path="",
            status="rendering",
        ))

    import asyncio
    asyncio.create_task(_run_pipeline(video_id, store_id, product, style=style))
    return {"video_id": video_id, "status": "rendering"}


@router.get("/videos", summary="List ad videos (for the dashboard's Videos page)")
async def list_videos(store_id: str = "", status: str = "") -> list[dict]:
    async with get_session() as session:
        stmt = select(ProductVideo).order_by(ProductVideo.created_at.desc())
        if store_id:
            stmt = stmt.where(ProductVideo.store_id == store_id)
        if status:
            stmt = stmt.where(ProductVideo.status == status)
        rows = (await session.execute(stmt)).scalars().all()

    return [{
        "id": r.id,
        "store_id": r.store_id,
        "shopify_product_id": r.shopify_product_id,
        "product_title": r.product_title,
        "status": r.status,
        "error": r.error,
        "video_url": f"/media/videos/{Path(r.file_path).name}" if r.file_path else "",
        "script": json.loads(r.script_json) if r.script_json else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.post("/videos/{video_id}/approve", summary="Approve a pending video — uploads it to Shopify as product media")
async def approve_video(video_id: str) -> dict:
    async with get_session() as session:
        row = await session.get(ProductVideo, video_id)
        if not row:
            return {"error": "not found"}
        if row.status != "pending_review":
            return {"error": f"video is {row.status!r}, not pending_review"}

        if not _use_store(row.store_id):
            return {"error": f"unknown store_id {row.store_id!r}"}

        ok = await attach_local_video_to_product(row.shopify_product_id, row.file_path, alt=row.product_title)
        row.status = "published" if ok else "approved"
        if not ok:
            row.error = "Shopify upload failed — video approved but not attached; retry needed"
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        return {"status": row.status, "error": row.error}


@router.post("/videos/{video_id}/reject", summary="Reject a pending video")
async def reject_video(video_id: str) -> dict:
    async with get_session() as session:
        row = await session.get(ProductVideo, video_id)
        if not row:
            return {"error": "not found"}
        row.status = "rejected"
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        return {"status": row.status}
