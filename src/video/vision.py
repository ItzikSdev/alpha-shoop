"""Person-detection + garment description for Reel's image pipeline, using a local
vision model (qwen3-vl via Ollama) — the only step in Reel's pipeline that needs
vision, since the rest of Reel's reasoning (qwen3, text-only) can't see pixels.

Also turns a garment description into a Wan2.2 prompt for the baby-outfit-swap
render (src/video/image_pipeline.py) — a plain qwen3 text call, same style as
`generate_ugc_script` in script_writer.py.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from src.config import get_settings

logger = logging.getLogger(__name__)


class RenderCheck(BaseModel):
    differs_meaningfully: bool = Field(
        description="True if the SECOND image shows a genuinely different camera angle, zoom, "
        "rotation, or rendering style compared to the FIRST (original) image — a real 3D/animated "
        "showcase effect. False if the second image looks essentially the same as the first "
        "(same angle/crop/pose, no visible render effect)."
    )
    reason: str = Field(description="One short sentence explaining the judgment.")


async def check_render_differs(original_path: Path, generated_path: Path, max_retries: int = 3) -> RenderCheck:
    """Reel's self-check before sending anything to Telegram: compares the
    original product photo against the generated still and judges whether the
    render actually did something visible, instead of trusting Wan2.2 output
    blindly. Catches the failure mode where a frame is grabbed too early in the
    clip and looks like an unchanged copy of the source photo."""
    settings = get_settings()
    original_b64 = base64.b64encode(Path(original_path).read_bytes()).decode("ascii")
    generated_b64 = base64.b64encode(Path(generated_path).read_bytes()).decode("ascii")

    system_prompt = (
        "You compare two product photos for quality control. The FIRST image is the original "
        "source photo. The SECOND image is meant to be a 3D-showcase render of it (rotated angle, "
        "zoomed, or otherwise dynamically re-rendered). Judge honestly whether the second image is "
        "actually visibly different from the first (real camera motion/angle/zoom change) or "
        "whether it just looks like the same photo again."
    )

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=300) as client:
        for attempt in range(1, max_retries + 1):
            try:
                r = await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json={
                        "model": settings.reel_vision_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": "First image (original), then second image (generated). Compare them.",
                                "images": [original_b64, generated_b64],
                            },
                        ],
                        "format": RenderCheck.model_json_schema(),
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                r.raise_for_status()
                content = r.json()["message"]["content"]
                return RenderCheck.model_validate_json(content)
            except Exception as e:
                last_error = e
                logger.warning("check_render_differs attempt %d/%d failed: %s", attempt, max_retries, e)

    raise RuntimeError(f"qwen3-vl render check failed after {max_retries} attempts: {last_error}")


class ImageAnalysis(BaseModel):
    has_adult_person: bool = Field(
        description="True if the photo shows an adult (or any human older than an infant/toddler) "
        "modeling/wearing the product. False for product-only shots (flat lay, ghost mannequin, "
        "on a hanger, or already a baby/infant wearing it)."
    )
    garment_description: str = Field(
        default="",
        description="If has_adult_person is true: a short, concrete description of the garment "
        "itself (type, color, pattern, notable details) — NOT the person. Empty string otherwise.",
    )


async def analyze_product_image(image_path: Path, max_retries: int = 3) -> ImageAnalysis:
    """One Ollama call to the local vision model (`settings.reel_vision_model`,
    default qwen3-vl:8b) — does this product photo show an adult person, and if so
    what does the garment look like. Retries on malformed output (cheap/local)."""
    settings = get_settings()
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")

    system_prompt = (
        "You inspect e-commerce product photos for a baby-clothing store. Look at the image and "
        "decide: does it show an adult (or any non-infant human) wearing/modeling the product, as "
        "opposed to a product-only shot (flat lay, hanger, ghost mannequin) or a baby/infant already "
        "wearing it? If an adult/older person is modeling it, describe the garment itself (type, "
        "color, pattern, material if visible) in one short sentence — never describe the person."
    )

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=300) as client:
        for attempt in range(1, max_retries + 1):
            try:
                r = await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json={
                        "model": settings.reel_vision_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": "Analyze this product photo.", "images": [image_b64]},
                        ],
                        "format": ImageAnalysis.model_json_schema(),
                        "stream": False,
                        "options": {"temperature": 0.2},
                    },
                )
                r.raise_for_status()
                content = r.json()["message"]["content"]
                return ImageAnalysis.model_validate_json(content)
            except Exception as e:  # malformed JSON, schema mismatch, Ollama unreachable, etc.
                last_error = e
                logger.warning("analyze_product_image attempt %d/%d failed: %s", attempt, max_retries, e)

    raise RuntimeError(f"qwen3-vl image analysis failed after {max_retries} attempts: {last_error}")


class AdImagePromptFields(BaseModel):
    scene_type: Literal["Storyboard panel", "Lifestyle hero shot", "Close-up transformation shot"] = Field(
        description="Pick exactly one, verbatim."
    )
    setting: str = Field(
        description="A complete noun phrase for the environment/background — e.g. 'a bright summer "
        "beach' or 'a sleek modern nursery'. Must stand alone grammatically, never a trailing "
        "adjective with nothing after it."
    )
    lighting_style: str = Field(
        description="A complete noun phrase for the lighting mood — e.g. 'vibrant cinematic sunlight' "
        "or 'a warm soft glow'."
    )
    emotion: str = Field(description="A short noun phrase for the emotional impact — e.g. 'pure joy' or 'refreshing relief'.")


_AD_IMAGE_TEMPLATE = """A professional high-end B2C commercial advertisement image for {product_name}.

{scene_type}.

VISUAL STORY & ACTION: {subject}, in {setting}. The lighting is {lighting_style}. High energy, emotional impact, expressing {emotion}.

PRODUCT DETAILS: The product {product_name} is clearly visible, integrated naturally into the scene. High detail on product texture, material, and branding placement.

ART DIRECTION & STYLE: Hyper-realistic 8k photography, commercial advertising aesthetics, rich contrast, dynamic composition, cinematic depth of field, vivid colors. NO text, NO layout overlay, pure photographic base asset."""


async def build_ad_image_prompt(
    product_title: str, product_description: str, subject: str, max_retries: int = 3
) -> str:
    """Owner-provided commercial-ad prompt template — fills SCENE_TYPE/SETTING/
    LIGHTING_STYLE/EMOTION via one structured qwen3 call (flat 4-field schema,
    same safe shape as ImageAnalysis/RenderCheck — NOT the nested multi-scene
    VideoScript schema that hung this machine, see script_writer.py), then
    assembles the fixed template. `subject` is passed in verbatim by the caller
    (not LLM-chosen) so the hard "no human" rule for the 3D-showcase branch, or
    the exact baby+garment description for the baby-swap branch, is never left
    to chance."""
    settings = get_settings()
    system_prompt = (
        "You fill in fields for a commercial product-ad image prompt template, for a baby-products "
        "e-commerce brand (premium, warm, trustworthy — never garish). Given the product info and "
        "the fixed subject already in the scene, choose a scene_type, setting, lighting_style, and "
        "emotion. Each field is inserted AS-IS into a sentence, so each must be a short, complete, "
        "grammatical phrase on its own — never a single trailing adjective, never truncated.\n"
        "Example (for a different product, don't copy the content): "
        'scene_type="Lifestyle hero shot", setting="a sun-drenched nursery with linen curtains", '
        'lighting_style="a warm golden-hour glow", emotion="calm contentment".'
    )
    user_prompt = (
        f"Product title: {product_title}\n"
        f"Product description: {product_description or '(none provided)'}\n"
        f"Subject already in the scene: {subject}"
    )

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=300) as client:
        for attempt in range(1, max_retries + 1):
            try:
                r = await client.post(
                    f"{settings.ollama_url}/api/chat",
                    json={
                        "model": settings.video_script_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "format": AdImagePromptFields.model_json_schema(),
                        "stream": False,
                        "options": {"temperature": 0.7},
                    },
                )
                r.raise_for_status()
                content = r.json()["message"]["content"]
                fields = AdImagePromptFields.model_validate_json(content)
                return _AD_IMAGE_TEMPLATE.format(
                    product_name=product_title,
                    scene_type=fields.scene_type,
                    subject=subject,
                    setting=fields.setting,
                    lighting_style=fields.lighting_style,
                    emotion=fields.emotion,
                )
            except Exception as e:
                last_error = e
                logger.warning("build_ad_image_prompt attempt %d/%d failed: %s", attempt, max_retries, e)

    raise RuntimeError(f"qwen3 ad-image prompt generation failed after {max_retries} attempts: {last_error}")
