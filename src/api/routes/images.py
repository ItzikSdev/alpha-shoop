"""Reel's baby-outfit-swap image pipeline: generate → Telegram review (album:
original + generated) → approve/reject → publish + RAG write-back.

Mirrors the shape of src/api/routes/videos.py — POST /images/generate kicks off
the pipeline as a background task and returns immediately with an id.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select

from src.db.engine import get_session
from src.db.models import ProductImage
from src.stores import _current_store, get_store
from src.mcp_tools.shopify import get_products_with_all_images, attach_local_image_to_product
from src.org.telegram import post_photo_group_as
from src.rag.index import get as rag_get, upsert as rag_upsert
from src.video.image_pipeline import NoAdultPersonError, generate_baby_outfit_image, store_generated_images_dir
from src.video.gemini_images import GeminiImageError, generate_gemini_ad_image

logger = logging.getLogger(__name__)
router = APIRouter()


def _use_store(store_id: str):
    store = get_store(store_id)
    if store:
        _current_store.set(store)
    return store


@router.get("/images/candidates", summary="Live products eligible for a new baby-outfit image")
async def get_image_candidates(store_id: str) -> list[dict]:
    store = _use_store(store_id)
    if not store:
        return []
    products = await get_products_with_all_images()

    async with get_session() as session:
        rows = (await session.execute(
            select(ProductImage.shopify_product_id).where(
                ProductImage.store_id == store_id,
                ProductImage.status.in_(["pending_review", "approved", "published"]),
            )
        )).scalars().all()
    already_has_image = set(rows)
    return [p for p in products if p["id"] not in already_has_image]


async def _run_pipeline(image_id: str, store_id: str, store_slug: str, product: dict, source_image_url: str, engine: str = "baby_swap", style: str = "lifestyle") -> None:
    _use_store(store_id)
    try:
        if engine == "gemini":
            result = await generate_gemini_ad_image(
                product_title=product["title"],
                product_description=product.get("description", ""),
                source_image_url=source_image_url,
                store_slug=store_slug,
                style=style,
            )
            kind = "3D showcase render" if style == "3d_showcase" else "baby-lifestyle photo"
            caption = (
                f"*{product['title']}* — Gemini {kind} ready for review\n"
                f"Original vs generated — tap ✅ or ❌ below."
            )
        else:
            result = await generate_baby_outfit_image(
                product_title=product["title"],
                product_description=product.get("description", ""),
                source_image_url=source_image_url,
                store_slug=store_slug,
            )
            caption = (
                f"*{product['title']}* — baby-outfit image ready for review\n"
                f"Garment: {result.garment_description}\n"
                f"Original vs generated — tap ✅ or ❌ below."
            )
        telegram_message_id = await post_photo_group_as(
            "Reel", "Video Producer", [str(result.source_path), str(result.image_path)], caption,
            review_id=image_id,
        )

        async with get_session() as session:
            row = await session.get(ProductImage, image_id)
            row.file_path = str(result.image_path)
            row.garment_description = result.garment_description
            row.telegram_message_id = telegram_message_id
            row.status = "pending_review"
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
    except NoAdultPersonError:
        async with get_session() as session:
            row = await session.get(ProductImage, image_id)
            row.status = "failed"
            row.error = "no adult person detected — route this product through the PRODUCT_3D_SHOWCASE video branch instead"
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
    except GeminiImageError as exc:
        async with get_session() as session:
            row = await session.get(ProductImage, image_id)
            row.status = "failed"
            row.error = f"Gemini: {exc}"[:2000]
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
    except Exception as exc:
        logger.exception("image pipeline failed for %s", image_id)
        async with get_session() as session:
            row = await session.get(ProductImage, image_id)
            row.status = "failed"
            row.error = str(exc)[:2000]
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)


@router.post("/images/generate", summary="Render a new product image for one product (runs in the background). engine: 'baby_swap' (Wan2.2) or 'gemini' (default — text-free photo/render); style (gemini only): 'lifestyle' (default, baby wearing it) or '3d_showcase' (product-only 3D render)")
async def post_generate_image(body: dict) -> dict:
    store_id = body.get("store_id", "")
    product_id = body.get("product_id", "")
    source_image_url = body.get("source_image_url", "")
    engine = body.get("engine", "gemini")
    style = body.get("style", "lifestyle")
    if engine not in ("baby_swap", "gemini"):
        return {"error": f"unknown engine {engine!r} — use 'baby_swap' or 'gemini'"}
    if style not in ("lifestyle", "3d_showcase"):
        return {"error": f"unknown style {style!r} — use 'lifestyle' or '3d_showcase'"}
    if not (store_id and product_id):
        return {"error": "missing 'store_id' or 'product_id'"}
    store = _use_store(store_id)
    if not store:
        return {"error": f"unknown store_id {store_id!r}"}

    products = await get_products_with_all_images()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return {"error": f"product {product_id!r} not found or has no images"}
    if not source_image_url:
        source_image_url = product["image_urls"][0]
    elif source_image_url not in product["image_urls"]:
        return {"error": f"source_image_url not among product {product_id!r}'s images"}

    image_id = uuid.uuid4().hex
    async with get_session() as session:
        session.add(ProductImage(
            id=image_id,
            store_id=store_id,
            shopify_product_id=product_id,
            product_title=product["title"],
            source_image_url=source_image_url,
            file_path="",
            status="rendering",
        ))

    store_slug = store.storefront_slug or store.store_id
    import asyncio
    asyncio.create_task(_run_pipeline(image_id, store_id, store_slug, product, source_image_url, engine=engine, style=style))
    return {"image_id": image_id, "status": "rendering"}


@router.get("/images", summary="List baby-outfit images (for the dashboard's Images page)")
async def list_images(store_id: str = "", status: str = "") -> list[dict]:
    async with get_session() as session:
        stmt = select(ProductImage).order_by(ProductImage.created_at.desc())
        if store_id:
            stmt = stmt.where(ProductImage.store_id == store_id)
        if status:
            stmt = stmt.where(ProductImage.status == status)
        rows = (await session.execute(stmt)).scalars().all()

    return [{
        "id": r.id,
        "store_id": r.store_id,
        "shopify_product_id": r.shopify_product_id,
        "product_title": r.product_title,
        "source_image_url": r.source_image_url,
        "status": r.status,
        "error": r.error,
        "garment_description": r.garment_description,
        "image_url": f"/api/v1/images/media/{r.store_id}/{Path(r.file_path).name}" if r.file_path else "",
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


@router.get("/images/media/{store_id}/{filename}", summary="Serve one generated baby-outfit image file")
async def get_image_media(store_id: str, filename: str):
    store = get_store(store_id)
    if not store:
        return {"error": f"unknown store_id {store_id!r}"}
    store_slug = store.storefront_slug or store.store_id
    base = store_generated_images_dir(store_slug).resolve()
    path = (base / filename).resolve()
    try:
        path.relative_to(base)  # reject path traversal (../..)
    except ValueError:
        return {"error": "invalid filename"}
    if not path.is_file():
        return {"error": "not found"}
    return FileResponse(path)


@router.post("/images/{image_id}/approve", summary="Approve a pending image — Sol uploads it to Shopify + writes back to RAG")
async def approve_image(image_id: str) -> dict:
    async with get_session() as session:
        row = await session.get(ProductImage, image_id)
        if not row:
            return {"error": "not found"}
        if row.status != "pending_review":
            return {"error": f"image is {row.status!r}, not pending_review"}

        if not _use_store(row.store_id):
            return {"error": f"unknown store_id {row.store_id!r}"}

        # Reel generates, Sol owns the actual Shopify push — matches the org's
        # division of labor (see src/org/seed.py's charters).
        ok = await attach_local_image_to_product(row.shopify_product_id, row.file_path, alt=row.product_title)
        row.status = "published" if ok else "approved"
        # Clear the error on success. Without this the message from an earlier
        # failed attempt survived the retry that fixed it, leaving 22 rows reading
        # `published` AND "upload failed — retry needed" at the same time. Agents
        # and humans both read these fields to decide what still needs doing, so a
        # stale error means real work gets re-queued and real successes look broken.
        row.error = "" if ok else "Shopify upload failed — image approved but not attached; retry needed"
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        result = {"status": row.status, "error": row.error}

    if ok:
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
            "has_baby_image": "true",
            "baby_image_url": row.file_path,
            "garment_description": row.garment_description,
        }
        await rag_upsert("store_products", row.shopify_product_id, text, metadata)
        try:
            from src.mcp_tools.design_files import append_changelog
            append_changelog(
                title=f"Sol: uploaded {row.product_title!r} image to Shopify + indexed in RAG",
                changed=f"Published image {image_id} (generated by Reel) to Shopify product {row.shopify_product_id} and updated the RAG entry.",
                by="Sol",
                context="Reel generates media, Sol pushes it live and indexes it — owner-approved via the Images dashboard.",
            )
        except Exception:
            pass

    return result


@router.post("/images/{image_id}/reject", summary="Reject a pending image")
async def reject_image(image_id: str) -> dict:
    async with get_session() as session:
        row = await session.get(ProductImage, image_id)
        if not row:
            return {"error": "not found"}
        row.status = "rejected"
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
        return {"status": row.status}


@router.post("/media/repost-pending", summary="Re-post every pending_review image/video to Telegram WITH ✅/❌ buttons")
async def repost_pending_media(body: dict | None = None) -> dict:
    """Send every item still awaiting review back to Telegram, this time with
    working approve/reject buttons.

    Needed because media posted BEFORE the review buttons existed (or before a
    bot restart) sits in `pending_review` with no way to decide it from
    Telegram — which is exactly how nine finished videos went unapproved and
    never reached the store. Idempotent: only touches `pending_review` rows,
    and updates each row's stored Telegram message id to the new post.
    """
    from src.db.models import ProductVideo
    from src.org.telegram import post_video_as

    body = body or {}
    store_id = body.get("store_id", "")
    posted: list[dict] = []
    skipped: list[dict] = []

    async with get_session() as session:
        img_q = select(ProductImage).where(ProductImage.status == "pending_review")
        vid_q = select(ProductVideo).where(ProductVideo.status == "pending_review")
        if store_id:
            img_q = img_q.where(ProductImage.store_id == store_id)
            vid_q = vid_q.where(ProductVideo.store_id == store_id)
        images = list((await session.execute(img_q)).scalars())
        videos = list((await session.execute(vid_q)).scalars())

    for row in images:
        if not row.file_path or not Path(row.file_path).is_file():
            skipped.append({"kind": "image", "id": row.id, "title": row.product_title,
                            "reason": "generated file is missing on disk"})
            continue
        # Post the generated image on its own — the original source file from the
        # first (side-by-side) post is often long gone.
        msg_id = await post_photo_group_as(
            "Reel", "Video Producer", [row.file_path],
            f"*{row.product_title}* — image awaiting your review\nTap ✅ or ❌ below.",
            review_id=row.id,
        )
        if msg_id:
            async with get_session() as session:
                fresh = await session.get(ProductImage, row.id)
                fresh.telegram_message_id = msg_id
                session.add(fresh)
            posted.append({"kind": "image", "id": row.id, "title": row.product_title})
        else:
            skipped.append({"kind": "image", "id": row.id, "title": row.product_title,
                            "reason": "Telegram upload failed"})

    for row in videos:
        if not row.file_path or not Path(row.file_path).is_file():
            skipped.append({"kind": "video", "id": row.id, "title": row.product_title,
                            "reason": "rendered file is missing on disk"})
            continue
        msg_id = await post_video_as(
            "Reel", "Video Producer", row.file_path,
            f"*{row.product_title}* — video awaiting your review\nTap ✅ or ❌ below.",
            review_id=row.id,
        )
        if msg_id:
            async with get_session() as session:
                fresh = await session.get(ProductVideo, row.id)
                fresh.slack_ts = msg_id
                session.add(fresh)
            posted.append({"kind": "video", "id": row.id, "title": row.product_title})
        else:
            skipped.append({"kind": "video", "id": row.id, "title": row.product_title,
                            "reason": "Telegram upload failed"})

    return {"posted": len(posted), "skipped": len(skipped), "items": posted, "problems": skipped}


@router.post("/media/retry-attach", summary="Re-run the Shopify attach for any approved media whose upload failed")
async def retry_attach_media(body: dict | None = None) -> dict:
    """Push media that was approved but never made it onto the product.

    The approve handlers write "…retry needed" when `attach_local_*_to_product`
    fails, but nothing ever performed that retry — the row just sat there
    (mislabelled `published`) and the product stayed without its image/video.
    This is that retry: for every row with a real file on disk that Shopify
    doesn't actually have, attach it again and clear the error on success.
    """
    from src.db.models import ProductVideo
    from src.mcp_tools.shopify import attach_local_video_to_product

    body = body or {}
    store_id = body.get("store_id", "")
    fixed: list[dict] = []
    failed: list[dict] = []

    async with get_session() as session:
        img_q = select(ProductImage).where(ProductImage.error != "")
        vid_q = select(ProductVideo).where(ProductVideo.error != "")
        if store_id:
            img_q = img_q.where(ProductImage.store_id == store_id)
            vid_q = vid_q.where(ProductVideo.store_id == store_id)
        images = [r for r in (await session.execute(img_q)).scalars()
                  if "not attached" in (r.error or "")]
        videos = [r for r in (await session.execute(vid_q)).scalars()
                  if "not attached" in (r.error or "")]

    for row, kind in [(r, "image") for r in images] + [(r, "video") for r in videos]:
        if not row.file_path or not Path(row.file_path).is_file():
            failed.append({"kind": kind, "id": row.id, "title": row.product_title,
                           "reason": "file no longer on disk — must be regenerated"})
            continue
        if not _use_store(row.store_id):
            failed.append({"kind": kind, "id": row.id, "title": row.product_title,
                           "reason": f"unknown store {row.store_id!r}"})
            continue
        try:
            if kind == "image":
                ok = await attach_local_image_to_product(
                    row.shopify_product_id, row.file_path, alt=row.product_title)
            else:
                ok = await attach_local_video_to_product(
                    row.shopify_product_id, row.file_path, alt=row.product_title)
        except Exception as exc:  # noqa: BLE001
            logger.exception("retry-attach failed for %s %s", kind, row.id)
            ok, exc_note = False, str(exc)[:200]
        else:
            exc_note = ""

        model = ProductImage if kind == "image" else ProductVideo
        async with get_session() as session:
            fresh = await session.get(model, row.id)
            if ok:
                fresh.status, fresh.error = "published", ""
            fresh.updated_at = datetime.now(timezone.utc)
            session.add(fresh)
        (fixed if ok else failed).append(
            {"kind": kind, "id": row.id, "title": row.product_title}
            | ({} if ok else {"reason": exc_note or "Shopify still rejected the upload"})
        )

    return {"attached": len(fixed), "still_failing": len(failed),
            "fixed": fixed, "problems": failed}
