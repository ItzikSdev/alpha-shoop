"""Reel's Gemini-based image generator — a second image pipeline alongside the
Wan2.2 baby-outfit-swap in image_pipeline.py. Uses Google's gemini-2.5-flash-image
model (Google AI Studio free tier, GEMINI_API_KEY in .env) to turn a product's real
photo + title/description into a finished PHOTO (no text/headline/callouts baked
in — those belong in Shopify/ad-platform copy, not burned into the image itself),
in one of two styles: 'lifestyle' (a baby wearing/using the product) or
'3d_showcase' (a stylized 3D product-only render, no person).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path

from google import genai
from google.genai import types

from src.video.image_pipeline import (
    ImagePipelineResult,
    _download_image,
    _store_work_dir,
    store_generated_images_dir,
)

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash-image"


class GeminiImageError(RuntimeError):
    """Raised when Gemini doesn't return an image part (e.g. safety refusal)."""


def _client() -> genai.Client:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=key)


_STYLE_PROMPTS = {
    "lifestyle": (
        "Create a polished, photorealistic commercial product PHOTOGRAPH (not a graphic, not "
        "an ad layout) for a baby-clothing product called \"{title}\". Use the attached photo "
        "as the exact reference for the garment itself — keep its real color, pattern and "
        "design unchanged, do not invent a different product.\n"
        "Show a happy baby (not a toddler or older child) actually wearing the product, in a "
        "warm, bright, natural lifestyle setting (soft home or outdoor light, candid pose). "
        "Presented in the best possible light — flattering angle, genuine smile, clean "
        "uncluttered background.\n"
        "ABSOLUTELY NO text, headline, logo, watermark, price, badge, or any overlay of any "
        "kind anywhere in the image — this must look like a real, unedited photograph."
    ),
    "3d_showcase": (
        "Create a polished, professional 3D-rendered product showcase image for a baby-"
        "clothing product called \"{title}\". Use the attached photo as the exact reference for "
        "the garment itself — keep its real color, pattern and design unchanged, do not invent "
        "a different product.\n"
        "Render ONLY the product itself (no person, no face, no mannequin) as an elegant "
        "stylized 3D render — soft studio lighting, subtle shadows/reflections, a clean "
        "minimal background, dynamic flattering angle that shows the garment's shape and "
        "texture clearly, as if for a premium e-commerce product page.\n"
        "ABSOLUTELY NO text, headline, logo, watermark, price, badge, or any overlay of any "
        "kind anywhere in the image."
    ),
}


def _build_prompt(product_title: str, product_description: str, style: str, extra_notes: str) -> str:
    template = _STYLE_PROMPTS.get(style, _STYLE_PROMPTS["lifestyle"])
    base = template.format(title=product_title)
    return f"{base}\nProduct context: {product_description[:600]}\n{extra_notes}".strip()


def _generate_sync(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    client = _client()
    resp = client.models.generate_content(
        model=_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )
    candidates = resp.candidates or []
    if not candidates or not candidates[0].content or not candidates[0].content.parts:
        raise GeminiImageError("Gemini returned no content (likely a safety refusal)")
    for part in candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            return part.inline_data.data
    text = "".join(p.text or "" for p in candidates[0].content.parts)
    raise GeminiImageError(f"Gemini returned no image part — text response: {text[:300]!r}")


async def generate_gemini_ad_image(
    product_title: str,
    product_description: str,
    source_image_url: str,
    store_slug: str,
    *,
    style: str = "lifestyle",
    extra_notes: str = "",
    work_dir: Path | None = None,
) -> ImagePipelineResult:
    """Downloads the product's real photo, sends it + a text-free photo/render prompt
    to Gemini (style='lifestyle': baby wearing it; style='3d_showcase': product-only
    3D render), and saves the returned image next to the Wan2.2 pipeline's outputs
    (same store_generated_images_dir) so it flows through the SAME review/approve/
    reject path (src/api/routes/images.py) — nothing here uploads to Shopify
    directly, the owner still approves before it goes live."""
    if style not in _STYLE_PROMPTS:
        style = "lifestyle"
    run_id = uuid.uuid4().hex[:8]
    work_dir = work_dir or _store_work_dir(store_slug, run_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("gemini image %s (%s): downloading source image for %r", run_id, style, product_title)
    image_path = await _download_image(source_image_url, work_dir / "source.png")
    image_bytes = image_path.read_bytes()
    mime_type = "image/png" if source_image_url.lower().split("?")[0].endswith(".png") else "image/jpeg"

    prompt = _build_prompt(product_title, product_description, style, extra_notes)
    logger.info("gemini image %s (%s): calling %s", run_id, style, _MODEL)
    result_bytes = await asyncio.to_thread(_generate_sync, image_bytes, mime_type, prompt)

    still_path = store_generated_images_dir(store_slug) / f"{run_id}.png"
    still_path.parent.mkdir(parents=True, exist_ok=True)
    still_path.write_bytes(result_bytes)

    label = "Gemini 3D showcase" if style == "3d_showcase" else "Gemini baby-lifestyle photo"
    logger.info("gemini image %s (%s): done -> %s", run_id, style, still_path)
    return ImagePipelineResult(
        image_path=still_path, source_path=image_path, garment_description=label
    )
