"""Product 360° rotation video: generate (Veo, paid) → Telegram review → approve/
reject → publish. The old scripted-ad pipeline (Wan2.2/ComfyUI, engine='wan_ad')
was retired 2026-08-20 — the owner deleted Wan2.2 (render quality wasn't good
enough). Only engine='veo_rotation' is supported now; POST /videos/generate
creates an awaiting_cost_approval row (no charge yet), a separate POST
/videos/{id}/approve-render fires the actual paid Veo call.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select

from src.db.engine import get_session
from src.db.models import ProductVideo
from src.stores import _current_store, get_store
from src.mcp_tools.shopify import get_products_for_video, attach_local_video_to_product
from src.org.telegram import post_video_as
from src.video.veo_video import VeoVideoError, ESTIMATED_COST_USD, generate_rotation_video

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


async def _run_veo_pipeline(video_id: str, store_id: str, store_slug: str, product_title: str, source_image_url: str) -> None:
    _use_store(store_id)
    try:
        result = await generate_rotation_video(
            product_title=product_title,
            source_image_url=source_image_url,
            store_slug=store_slug,
        )
        caption = (
            f"*{product_title}* — 360° rotation video ready for review (Veo, cost already spent: ~${ESTIMATED_COST_USD})\n"
            f"Tap ✅ or ❌ below, or use the dashboard's Videos page."
        )
        telegram_id = await post_video_as("Reel", "Video Producer", str(result.video_path), caption,
                                          review_id=video_id)

        async with get_session() as session:
            row = await session.get(ProductVideo, video_id)
            row.file_path = str(result.video_path)
            row.slack_ts = telegram_id
            row.status = "pending_review"
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
    except VeoVideoError as exc:
        # Google only bills on a SUCCESSFUL generation, so a VeoVideoError here means
        # no charge happened — safe to mark failed and let the owner retry.
        async with get_session() as session:
            row = await session.get(ProductVideo, video_id)
            row.status = "failed"
            row.error = f"Veo: {exc}"[:2000]
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
    except Exception as exc:
        logger.exception("veo pipeline failed for %s", video_id)
        async with get_session() as session:
            row = await session.get(ProductVideo, video_id)
            row.status = "failed"
            row.error = str(exc)[:2000]
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)


@router.post("/videos/generate", summary="Render a new 360° rotation video for one product (runs in the background, paid Veo API, requires a separate approve-render call before it actually charges anything). engine: 'veo_rotation' only — 'wan_ad' (the old scripted-ad pipeline) was retired 2026-08-20, Wan2.2/ComfyUI was deleted (owner decision, render quality)")
async def post_generate_video(body: dict) -> dict:
    store_id = body.get("store_id", "")
    product_id = body.get("product_id", "")
    engine = body.get("engine", "veo_rotation")
    if engine == "wan_ad":
        return {"error": "engine 'wan_ad' was retired 2026-08-20 — Wan2.2/ComfyUI was "
                          "deleted (owner decision, render quality). Use 'veo_rotation'."}
    if engine != "veo_rotation":
        return {"error": f"unknown engine {engine!r} — use 'veo_rotation'"}
    if not (store_id and product_id):
        return {"error": "missing 'store_id' or 'product_id'"}
    store = _use_store(store_id)
    if not store:
        return {"error": f"unknown store_id {store_id!r}"}

    products = await get_products_for_video()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return {"error": f"product {product_id!r} not found or has no image"}

    # Gate BEFORE a request ever reaches awaiting_cost_approval — Cozy Baby
    # Jumpsuit alone got 30 render requests over 3 weeks despite already
    # having a real published video since 2026-08-06, because nothing ever
    # checked "does this already clear the gate" before queuing another one.
    from src.mcp_tools.shopify import publish_blockers
    try:
        blockers = await publish_blockers(product_id)
    except Exception as exc:  # noqa: BLE001
        blockers = None  # a failed check must not silently allow a duplicate spend
    if blockers == []:
        return {"error": f"{product['title']!r} already clears the storefront gate "
                          "(real video + 3+ images) — no render needed. Refused before "
                          "queuing to avoid a duplicate billed request."}

    video_id = uuid.uuid4().hex

    # COST GATE: creates the row but does NOT call Veo yet — nothing here can
    # cost money. A separate, explicit POST /videos/{id}/approve-render call is
    # required before any paid API call happens.
    store_slug = store.storefront_slug or store.store_id
    async with get_session() as session:
        session.add(ProductVideo(
            id=video_id,
            store_id=store_id,
            shopify_product_id=product_id,
            product_title=product["title"],
            file_path="",
            script_json=json.dumps({
                "engine": "veo_rotation",
                "source_image_url": product["image_url"],
                "store_slug": store_slug,
            }),
            status="awaiting_cost_approval",
        ))
    return {
        "video_id": video_id,
        "status": "awaiting_cost_approval",
        "estimated_cost_usd": ESTIMATED_COST_USD,
        "note": f"Real money — call POST /videos/{video_id}/approve-render to actually render (~${ESTIMATED_COST_USD}, only charged on success).",
    }


@router.post("/videos/{video_id}/approve-render", summary="Owner confirms the cost — actually fires the paid Veo render for an awaiting_cost_approval video")
async def approve_video_render(video_id: str) -> dict:
    async with get_session() as session:
        row = await session.get(ProductVideo, video_id)
        if not row:
            return {"error": "not found"}
        if row.status != "awaiting_cost_approval":
            return {"error": f"video is {row.status!r}, not awaiting_cost_approval"}
        meta = json.loads(row.script_json or "{}")
        if meta.get("engine") != "veo_rotation":
            return {"error": "this video wasn't created via the veo_rotation cost gate"}
        row.status = "rendering"
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        store_id, product_title = row.store_id, row.product_title

    import asyncio
    asyncio.create_task(_run_veo_pipeline(video_id, store_id, meta["store_slug"], product_title, meta["source_image_url"]))
    return {"video_id": video_id, "status": "rendering", "note": f"Paid render started (~${ESTIMATED_COST_USD}, charged only if it succeeds)."}


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
        "video_url": f"/api/v1/videos/{r.id}/file" if r.file_path else "",
        "script": json.loads(r.script_json) if r.script_json else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.get("/videos/{video_id}/file", summary="Serve one video's rendered mp4")
async def get_video_file(video_id: str):
    async with get_session() as session:
        row = await session.get(ProductVideo, video_id)
    if not row or not row.file_path:
        return {"error": "not found"}
    path = Path(row.file_path)
    if not path.is_file():
        return {"error": "file missing on disk"}
    return FileResponse(path)


@router.post("/videos/{video_id}/approve", summary="Approve a pending video — Sol uploads it to Shopify + writes back to RAG")
async def approve_video(video_id: str) -> dict:
    async with get_session() as session:
        row = await session.get(ProductVideo, video_id)
        if not row:
            return {"error": "not found"}
        if row.status != "pending_review":
            return {"error": f"video is {row.status!r}, not pending_review"}

        if not _use_store(row.store_id):
            return {"error": f"unknown store_id {row.store_id!r}"}

        # Reel generates, Sol owns the actual Shopify push — matches the org's
        # division of labor (see src/org/seed.py's charters).
        ok = await attach_local_video_to_product(row.shopify_product_id, row.file_path, alt=row.product_title)
        row.status = "published" if ok else "approved"
        # Clear the error on success — see the matching note in images.py. A
        # stale failure message on a row that has since succeeded makes finished
        # work look outstanding, which is how "22 missing images" turned out to
        # be zero missing images.
        row.error = "" if ok else "Shopify upload failed — video approved but not attached; retry needed"
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        result = {"status": row.status, "error": row.error}

    if ok:
        from src.rag.index import get as rag_get, upsert as rag_upsert
        from src.mcp_tools.design_files import append_changelog
        # Read-merge-write: upsert() replaces the whole RAG hash, so fetch the
        # product's existing metadata first rather than clobbering title/price/etc.
        existing = await rag_get("store_products", row.shopify_product_id) or {}
        text = existing.get("text", row.product_title)
        metadata = {
            "store_id": existing.get("store_id", row.store_id),
            "product_id": row.shopify_product_id,
            "title": existing.get("title", row.product_title),
            "price": existing.get("price", ""),
            "handle": existing.get("handle", ""),
            "images": existing.get("images", ""),
            "has_baby_image": existing.get("has_baby_image", ""),
            "baby_image_url": existing.get("baby_image_url", ""),
            "garment_description": existing.get("garment_description", ""),
            "has_rotation_video": "true",
            "rotation_video_url": row.file_path,
        }
        await rag_upsert("store_products", row.shopify_product_id, text, metadata)
        try:
            append_changelog(
                title=f"Sol: uploaded {row.product_title!r} rotation video to Shopify + indexed in RAG",
                changed=f"Published video {video_id} (generated by Reel) to Shopify product {row.shopify_product_id} and updated the RAG entry.",
                by="Sol",
                context="Reel generates media, Sol pushes it live and indexes it — owner-approved via the Videos dashboard.",
            )
        except Exception:
            pass

    return result


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
