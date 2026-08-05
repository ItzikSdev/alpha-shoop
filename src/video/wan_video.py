"""Per-scene Wan2.2 image-to-video render, driven through the local ComfyUI API.

Loads the tracked workflow template (assets/comfyui_workflows/wan22_product_ad.json —
hand-converted to ComfyUI's API prompt format, validated against a live run), patches
in the scene's source image + prompt + a fresh seed, submits it, and polls until the
rendered mp4 lands in ComfyUI's output directory.

This is the primitive `src/video/pipeline.py` calls once per scene.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from pathlib import Path

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "assets/comfyui_workflows/wan22_product_ad.json"

# Node ids inside the template — see assets/comfyui_workflows/wan22_product_ad.json.
_NODE_LOAD_IMAGE = "58"
_NODE_TEXT_ENCODE = "16"
_NODE_EMPTY_EMBEDS = "78"
_NODE_IMAGE_SCALE = "71"
_NODE_SAMPLER = "27"
_NODE_SAVE_VIDEO = "93"
_NODE_VAE_ENCODE = "70"
_NODE_VAE_DECODE = "28"


class Wan2VideoError(RuntimeError):
    pass


def _comfyui_dir() -> Path:
    return Path(get_settings().comfyui_dir).expanduser()


async def _upload_image(client: httpx.AsyncClient, comfyui_url: str, image_path: Path) -> str:
    with image_path.open("rb") as f:
        files = {"image": (image_path.name, f, "image/png")}
        r = await client.post(f"{comfyui_url}/upload/image", files=files, data={"overwrite": "true"})
    r.raise_for_status()
    return r.json()["name"]


def _build_prompt(
    uploaded_image_name: str, positive_prompt: str, seed: int, width: int, height: int, num_frames: int, filename_prefix: str
) -> dict:
    workflow = json.loads(_TEMPLATE_PATH.read_text())
    workflow[_NODE_LOAD_IMAGE]["inputs"]["image"] = uploaded_image_name
    workflow[_NODE_TEXT_ENCODE]["inputs"]["positive_prompt"] = positive_prompt
    workflow[_NODE_EMPTY_EMBEDS]["inputs"]["width"] = width
    workflow[_NODE_EMPTY_EMBEDS]["inputs"]["height"] = height
    workflow[_NODE_EMPTY_EMBEDS]["inputs"]["num_frames"] = num_frames
    workflow[_NODE_IMAGE_SCALE]["inputs"]["width"] = width
    workflow[_NODE_IMAGE_SCALE]["inputs"]["height"] = height
    workflow[_NODE_SAMPLER]["inputs"]["seed"] = seed
    workflow[_NODE_SAVE_VIDEO]["inputs"]["filename_prefix"] = filename_prefix
    # Tiled VAE encode/decode: same output, processes in chunks instead of one big
    # allocation — the template defaults this to false, which OOM's the MPS backend
    # on this machine ("MPS backend out of memory... Tried to allocate 97.50 MiB on
    # shared pool" at WanVideoDecode, 27.14/27.20 GiB already in use). Always-on since
    # it costs a little speed for a lot of memory headroom, with no quality tradeoff.
    workflow[_NODE_VAE_ENCODE]["inputs"]["enable_vae_tiling"] = True
    workflow[_NODE_VAE_DECODE]["inputs"]["enable_vae_tiling"] = True
    return workflow


def _find_output_file(outputs: dict) -> tuple[str, str, str] | None:
    """Walk a /history outputs block for the first {filename, subfolder, type} entry —
    tolerant of the exact output key name (varies across ComfyUI/node versions)."""
    node_out = outputs.get(_NODE_SAVE_VIDEO, {})
    for entries in node_out.values():
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and "filename" in entry:
                    return entry["filename"], entry.get("subfolder", ""), entry.get("type", "output")
    return None


async def generate_scene_video(
    image_path: Path,
    prompt: str,
    *,
    width: int = 832,
    height: int = 480,
    num_frames: int = 81,
    seed: int | None = None,
    timeout_s: float = 2400,
    poll_interval_s: float = 4,
    max_retries: int = 2,
) -> Path:
    """Renders one Wan2.2 clip from a still image + prompt. Returns the path to the
    rendered mp4 on disk. Retries the whole submit-and-poll cycle on transient
    ComfyUI/network failures (a fresh random seed each retry)."""
    settings = get_settings()
    comfyui_url = settings.comfyui_url
    filename_prefix = f"scene_{uuid.uuid4().hex[:8]}"

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                uploaded_name = await _upload_image(client, comfyui_url, image_path)
                run_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
                prompt_graph = _build_prompt(
                    uploaded_name, prompt, run_seed, width, height, num_frames, filename_prefix
                )

                r = await client.post(f"{comfyui_url}/prompt", json={"prompt": prompt_graph})
                if r.status_code != 200:
                    raise Wan2VideoError(f"ComfyUI rejected the workflow: {r.status_code} {r.text[:500]}")
                prompt_id = r.json()["prompt_id"]

                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline:
                    hr = await client.get(f"{comfyui_url}/history/{prompt_id}")
                    hist = hr.json()
                    entry = hist.get(prompt_id)
                    if entry:
                        status = entry.get("status", {})
                        if status.get("status_str") == "error":
                            raise Wan2VideoError(f"ComfyUI generation failed: {status}")
                        outputs = entry.get("outputs", {})
                        found = _find_output_file(outputs)
                        if found:
                            filename, subfolder, ftype = found
                            base = _comfyui_dir() / ftype
                            return (base / subfolder / filename) if subfolder else (base / filename)
                    await asyncio.sleep(poll_interval_s)
                raise Wan2VideoError(f"Timed out after {timeout_s}s waiting for ComfyUI (prompt_id={prompt_id})")
        except Exception as e:
            last_error = e
            logger.warning("generate_scene_video attempt %d/%d failed: %s", attempt, max_retries, e)

    raise Wan2VideoError(f"Scene video generation failed after {max_retries} attempts: {last_error}")
