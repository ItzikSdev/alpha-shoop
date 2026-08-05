"""End-to-end UGC ad video pipeline: product → script (qwen3) → per-scene Wan2.2
clips + voiceover → assembled MP4.

This is the single entry point the API route / OpenClaw agent tools call.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import get_settings
from src.video.assembler import concat_scenes, mux_scene
from src.video.schemas import VideoScript, VideoStyle
from src.video.script_writer import generate_ugc_script
from src.video.tts import synthesize_voiceover
from src.video.wan_video import generate_scene_video

logger = logging.getLogger(__name__)


@dataclass
class VideoPipelineResult:
    video_path: Path
    script: VideoScript


async def _download_image(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


async def generate_product_ad(
    product_title: str,
    product_description: str,
    product_image_url: str,
    *,
    style: VideoStyle = "AVATAR_UGC",
    work_dir: Path | None = None,
) -> VideoPipelineResult:
    """Runs the full pipeline for one product and returns the path to the final MP4.
    `style` picks the format (see src/video/schemas.py): AVATAR_UGC (avatar talks to
    camera + benefit captions) or PRODUCT_3D_SHOWCASE (no face, rotating/macro product
    render + floating title cards).

    Raises on any stage failure — callers (the API route) decide how to surface that
    (e.g. skip Telegram posting, mark the DB row failed) rather than this function
    silently producing a partial/broken video.
    """
    settings = get_settings()
    run_id = uuid.uuid4().hex[:8]
    work_dir = work_dir or Path(settings.video_output_dir) / "_work" / run_id
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("video pipeline %s: writing %s script for %r", run_id, style, product_title)
    script = await generate_ugc_script(product_title, product_description, style=style)

    logger.info("video pipeline %s: downloading product image", run_id)
    image_path = await _download_image(product_image_url, work_dir / "product.png")

    scene_paths: list[Path] = []
    for scene in sorted(script.scenes, key=lambda s: s.order):
        logger.info("video pipeline %s: rendering scene %d", run_id, scene.order)
        num_frames = max(24, round(scene.duration_s * 24))
        raw_video = await generate_scene_video(image_path, scene.visual_prompt, num_frames=num_frames)

        audio_path = await synthesize_voiceover(scene.voiceover_line, work_dir / f"scene_{scene.order}_vo.wav")
        muxed_path = work_dir / f"scene_{scene.order}_muxed.mp4"
        await mux_scene(raw_video, audio_path, muxed_path)
        scene_paths.append(muxed_path)

    final_path = Path(settings.video_output_dir) / f"{run_id}.mp4"
    await concat_scenes(scene_paths, final_path)

    logger.info("video pipeline %s: done -> %s", run_id, final_path)
    return VideoPipelineResult(video_path=final_path, script=script)
