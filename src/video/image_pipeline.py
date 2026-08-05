"""Reel's image pipelines: baby-outfit-swap (adult-in-photo -> baby wearing the
same outfit) and 3D-showcase (no person -> dynamic product-only render), both
built on the owner-provided commercial-ad prompt template (build_ad_image_prompt
in vision.py) -> Wan2.2 render -> still frame, with a self-check before either
result is ever sent anywhere.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.mcp_tools.design_files import _store_dir
from src.video.assembler import extract_still_frame
from src.video.vision import (
    ImageAnalysis,
    analyze_product_image,
    build_ad_image_prompt,
    check_render_differs,
)
from src.video.wan_video import generate_scene_video

logger = logging.getLogger(__name__)


@dataclass
class ImagePipelineResult:
    image_path: Path
    source_path: Path
    garment_description: str


class NoAdultPersonError(RuntimeError):
    """Raised when the source image doesn't show an adult person — caller should
    route that product through the PRODUCT_3D_SHOWCASE video branch instead."""


class RenderQualityError(RuntimeError):
    """Raised when Reel's own self-check (check_render_differs) never finds the
    render visibly different from the source photo, even after retrying at later
    points in the clip — never silently send a near-identical image."""


_WAN_FPS = 24  # matches the ~3.4s/81-frame clip noted in assembler.py's mux_scene docstring


async def _download_image(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def _store_work_dir(store_slug: str, run_id: str) -> Path:
    """stores/shopify/<slug>/generated_images/_work/<run_id> — scratch space for the
    intermediate source-image download, never served. Generated media is per-store
    data (like style/readme/changelog), never a shared global folder."""
    return _store_dir(store_slug) / "generated_images" / "_work" / run_id


def store_generated_images_dir(store_slug: str) -> Path:
    """stores/shopify/<slug>/generated_images/ — where FINAL baby-outfit stills are
    saved (flat, `<run_id>.png`), and what src/api/routes/images.py's media-serving
    route resolves filenames against."""
    return _store_dir(store_slug) / "generated_images"


async def generate_baby_outfit_image(
    product_title: str,
    product_description: str,
    source_image_url: str,
    store_slug: str,
    *,
    work_dir: Path | None = None,
) -> ImagePipelineResult:
    """Runs the baby-outfit-swap pipeline for one product image. Raises
    NoAdultPersonError if the vision check finds no adult person in the photo (the
    caller should generate a PRODUCT_3D_SHOWCASE video for that product instead).
    Raises on any other stage failure — the caller decides how to surface that
    (e.g. mark the DB row failed) rather than this function silently producing a
    partial/broken image."""
    run_id = uuid.uuid4().hex[:8]
    work_dir = work_dir or _store_work_dir(store_slug, run_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("image pipeline %s: downloading source image for %r", run_id, product_title)
    image_path = await _download_image(source_image_url, work_dir / "source.png")

    logger.info("image pipeline %s: running vision check", run_id)
    analysis: ImageAnalysis = await analyze_product_image(image_path)
    if not analysis.has_adult_person:
        raise NoAdultPersonError(f"no adult person detected in {source_image_url!r}")

    logger.info("image pipeline %s: garment=%r", run_id, analysis.garment_description)
    subject = f"a baby (not a toddler or older child) wearing {analysis.garment_description}"
    visual_prompt = await build_ad_image_prompt(product_title, product_description, subject)

    logger.info("image pipeline %s: rendering via Wan2.2", run_id)
    num_frames = 25  # ~1s at _WAN_FPS — kept short for speed; tiled VAE (wan_video.py) avoids OOM regardless
    raw_video = await generate_scene_video(image_path, visual_prompt, num_frames=num_frames)
    duration_s = num_frames / _WAN_FPS

    # Self-check before ever sending anything: require BOTH (1) the still looks
    # visibly different from the source photo (not an early, near-copy frame) AND
    # (2) it no longer shows an adult person — the closest proxy we have for "the
    # swap actually happened" versus Wan2.2 just rotating the same adult photo.
    candidate_fractions = [0.90, 0.70, 0.50]
    last_reason = "n/a"
    still_path = store_generated_images_dir(store_slug) / f"{run_id}.png"
    for i, frac in enumerate(candidate_fractions, start=1):
        await extract_still_frame(raw_video, still_path, timestamp_s=duration_s * frac)
        render_check = await check_render_differs(image_path, still_path)
        result_check = await analyze_product_image(still_path)
        ok = render_check.differs_meaningfully and not result_check.has_adult_person
        logger.info(
            "image pipeline %s: check attempt %d/%d (t=%.2fs) -> differs=%s adult_still_present=%s",
            run_id, i, len(candidate_fractions), duration_s * frac,
            render_check.differs_meaningfully, result_check.has_adult_person,
        )
        last_reason = render_check.reason if not render_check.differs_meaningfully else "still shows an adult person, not a baby"
        if ok:
            break
    else:
        raise RenderQualityError(
            f"generated still never passed the baby-swap self-check after "
            f"{len(candidate_fractions)} attempts — last reason: {last_reason}"
        )

    logger.info("image pipeline %s: done -> %s", run_id, still_path)
    return ImagePipelineResult(
        image_path=still_path, source_path=image_path, garment_description=analysis.garment_description
    )


async def generate_3d_showcase_image(
    product_title: str,
    product_description: str,
    source_image_url: str,
    store_slug: str,
    *,
    work_dir: Path | None = None,
) -> ImagePipelineResult:
    """The no-adult-person branch, as a single STILL IMAGE rather than a full
    scripted video: no voiceover, no multi-scene JSON script (that's what was
    hanging — see build_3d_showcase_prompt's docstring), just one Wan2.2 prompt
    + the REAL product photo (properly image-conditioned this time — unlike
    generate_baby_outfit_image, there's no subject to swap out, so Wan2.2 is used
    exactly as designed: animate the actual photo, don't replace it)."""
    run_id = uuid.uuid4().hex[:8]
    work_dir = work_dir or _store_work_dir(store_slug, run_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("3D-showcase image pipeline %s: downloading source image for %r", run_id, product_title)
    image_path = await _download_image(source_image_url, work_dir / "source.png")

    logger.info("3D-showcase image pipeline %s: building prompt", run_id)
    subject = "the product itself, elegantly presented — no human or face anywhere in frame"
    visual_prompt = await build_ad_image_prompt(product_title, product_description, subject)

    logger.info("3D-showcase image pipeline %s: rendering via Wan2.2", run_id)
    num_frames = 25  # ~1s at _WAN_FPS — kept short for speed; tiled VAE (wan_video.py) avoids OOM regardless
    raw_video = await generate_scene_video(image_path, visual_prompt, num_frames=num_frames)
    duration_s = num_frames / _WAN_FPS

    # Self-check before ever sending anything: Wan2.2 motion is subtle early in a
    # clip (conditions frame 0 on the source photo, ramps up from there), so a
    # frame grabbed too early looks like the original. Try progressively later
    # timestamps (cheap — no re-render, just re-extract from the same clip) until
    # qwen3-vl confirms a visible difference; never silently return a near-copy.
    candidate_fractions = [0.90, 0.70, 0.50]
    last_check = None
    still_path = store_generated_images_dir(store_slug) / f"{run_id}.png"
    for i, frac in enumerate(candidate_fractions, start=1):
        await extract_still_frame(raw_video, still_path, timestamp_s=duration_s * frac)
        last_check = await check_render_differs(image_path, still_path)
        logger.info(
            "3D-showcase image pipeline %s: check attempt %d/%d (t=%.2fs) -> differs=%s (%s)",
            run_id, i, len(candidate_fractions), duration_s * frac,
            last_check.differs_meaningfully, last_check.reason,
        )
        if last_check.differs_meaningfully:
            break
    else:
        raise RenderQualityError(
            f"generated still never looked visibly different from the source photo after "
            f"{len(candidate_fractions)} attempts — last reason: {last_check.reason if last_check else 'n/a'}"
        )

    logger.info("3D-showcase image pipeline %s: done -> %s", run_id, still_path)
    return ImagePipelineResult(image_path=still_path, source_path=image_path, garment_description="")
