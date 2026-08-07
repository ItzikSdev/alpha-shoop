"""Reel's Veo-based product-rotation video generator. Uses Google's Veo 3.1 Fast
model (same GEMINI_API_KEY as gemini_images.py) to turn a product's real/generated
photo into a short 360-degree rotation clip — no person, no text, just the product
turning. UNLIKE the free Gemini image pipeline, this is a REAL PAID call
(Veo 3.1 Fast: ~$0.10-0.12/second — see cost gate in src/api/routes/videos.py,
which requires an explicit owner approval BEFORE this function is ever called).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types

from src.video.image_pipeline import _download_image, _store_work_dir

logger = logging.getLogger(__name__)

_MODEL = "veo-3.1-fast-generate-preview"
_DURATION_SECONDS = 4  # Veo's minimum supported duration (3s was requested but isn't allowed — API rejects <4)
_RESOLUTION = "720p"   # cheapest supported tier
_ASPECT_RATIO = "16:9"

# Veo 3.1 Fast per-second pricing (720p) — see https://ai.google.dev/gemini-api/docs/pricing.
# Used only to show the owner an accurate cost estimate before they approve a render.
_PRICE_PER_SECOND_USD = 0.10
ESTIMATED_COST_USD = round(_PRICE_PER_SECOND_USD * _DURATION_SECONDS, 2)


class VeoVideoError(RuntimeError):
    """Raised on any Veo failure — the owner is NOT charged for failed generations
    (Google's billing only applies on success), so this is safe to retry."""


def _client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=key)


def _rotation_prompt(product_title: str) -> str:
    return (
        f"The camera slowly orbits 360 degrees around the {product_title}, showing "
        f"it from every angle: front, both sides, and back. Clean studio background, "
        f"soft even lighting, no person, no text, no logos, no watermark, smooth "
        f"continuous rotation, professional e-commerce product video."
    )


def _generate_sync(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    client = _client()
    op = client.models.generate_videos(
        model=_MODEL,
        prompt=prompt,
        image=types.Image(image_bytes=image_bytes, mime_type=mime_type),
        config=types.GenerateVideosConfig(
            duration_seconds=_DURATION_SECONDS,
            resolution=_RESOLUTION,
            aspect_ratio=_ASPECT_RATIO,
        ),
    )
    deadline = time.time() + 300
    while not op.done and time.time() < deadline:
        time.sleep(8)
        op = client.operations.get(op)
    if not op.done:
        raise VeoVideoError("Veo render timed out after 300s")
    if op.error:
        raise VeoVideoError(f"Veo render failed: {op.error}")
    videos = (op.result and op.result.generated_videos) or []
    if not videos:
        raise VeoVideoError("Veo returned no video (likely filtered)")
    video = videos[0].video
    if video.video_bytes:
        return video.video_bytes
    client.files.download(file=video)
    tmp = Path(f"/tmp/veo_{uuid.uuid4().hex[:8]}.mp4")
    video.save(str(tmp))
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    return data


@dataclass
class VeoVideoResult:
    video_path: Path
    source_path: Path


async def generate_rotation_video(
    product_title: str,
    source_image_url: str,
    store_slug: str,
    *,
    work_dir: Path | None = None,
) -> VeoVideoResult:
    """Downloads the reference product photo and calls Veo for a 4-second 360
    rotation clip. ONLY call this after the owner has explicitly approved the
    cost (see the awaiting_cost_approval gate in src/api/routes/videos.py) —
    this function itself has no cost gate of its own."""
    run_id = uuid.uuid4().hex[:8]
    work_dir = work_dir or _store_work_dir(store_slug, run_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("veo rotation %s: downloading source image for %r", run_id, product_title)
    image_path = await _download_image(source_image_url, work_dir / "source.png")
    image_bytes = image_path.read_bytes()
    mime_type = "image/png" if source_image_url.lower().split("?")[0].endswith(".png") else "image/jpeg"

    prompt = _rotation_prompt(product_title)
    logger.info("veo rotation %s: calling %s (PAID, ~$%.2f)", run_id, _MODEL, ESTIMATED_COST_USD)
    video_bytes = await asyncio.to_thread(_generate_sync, image_bytes, mime_type, prompt)

    from src.video.image_pipeline import store_generated_images_dir
    out_dir = store_generated_images_dir(store_slug).parent / "generated_videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    video_path = out_dir / f"{run_id}.mp4"
    video_path.write_bytes(video_bytes)

    logger.info("veo rotation %s: done -> %s", run_id, video_path)
    return VeoVideoResult(video_path=video_path, source_path=image_path)
