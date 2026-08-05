"""Turns a product (title + description) into a structured UGC video script using
qwen3 running locally in Ollama — no Claude/Anthropic tokens spent on this step.

Uses Ollama's native structured-output support (`format` = JSON schema) so the
model's response is guaranteed to parse into `VideoScript`, rather than asking it
to "please respond in JSON" and hoping.
"""
from __future__ import annotations

import logging

import httpx

from src.config import get_settings
from src.video.schemas import VideoScript, VideoStyle

logger = logging.getLogger(__name__)

_BASE_RULES = """
Rules:
- 2 to 4 scenes total. Keep it tight — this is a ~10-20 second ad, not a documentary.
- The hook (first scene) must grab attention in the first sentence — a relatable problem, a bold \
claim, or a surprising visual. No generic "check this out".
- voiceover_line is what a real parent would say about this product, conversational, not corporate.
- text_overlay is the short on-screen caption for that scene (a benefit callout or title-card word) \
— empty string if the scene has none. Never repeat the voiceover_line verbatim as the overlay.
- Never invent product claims not implied by the title/description (no fake certifications, \
medical claims, or specs you weren't given).
- Respond only in English, regardless of the input language. Set "style" to the exact value given below.
"""

_STYLE_PROMPTS: dict[VideoStyle, str] = {
    "AVATAR_UGC": (
        "You are a UGC (user-generated-content style) ad scriptwriter for a baby-products "
        "e-commerce store, writing for the AVATAR_UGC format: an AI avatar speaks directly to "
        "camera for the hook + script, like a real parent recommending the product to camera.\n"
        "- visual_prompt: describe the avatar (a parent) speaking to camera, holding/using the "
        "product, camera motion (e.g. \"slow push in\", \"gentle pan left\"), lighting — plain "
        "English, one paragraph, framed as a talking-head shot with the product in frame.\n"
        "- text_overlay: a punchy feature/benefit caption that appears alongside the avatar while "
        "they talk (e.g. \"100% organic cotton\", \"Machine washable\")." + _BASE_RULES
    ),
    "PRODUCT_3D_SHOWCASE": (
        "You are a cinematic product-showcase scriptwriter for a baby-products e-commerce store, "
        "writing for the PRODUCT_3D_SHOWCASE format: NO human face — the product itself is the "
        "star, shot like a 3D/CGI product render (rotating turntable, macro close-ups, dramatic "
        "camera moves), benefits carried entirely by on-screen titles, not a speaker.\n"
        "- visual_prompt: describe a rotating or macro camera move on the product ALONE (e.g. "
        "\"slow 360-degree turntable rotation\", \"macro close-up push-in on the fabric texture\", "
        "\"product floating and rotating against a soft gradient background\") — plain English, one "
        "paragraph, NEVER include a person/face.\n"
        "- text_overlay: a short, bold, floating title-card style line naming ONE benefit for this "
        "scene (e.g. \"BREATHABLE\", \"SOFT-TOUCH FABRIC\") — this carries the persuasion since "
        "there's no speaker; never leave it empty for this style." + _BASE_RULES
    ),
}


async def generate_ugc_script(
    product_title: str, product_description: str = "", style: VideoStyle = "AVATAR_UGC",
    max_retries: int = 3,
) -> VideoScript:
    """Calls local Ollama (qwen3) for a structured `VideoScript` in the given
    `style` (AVATAR_UGC or PRODUCT_3D_SHOWCASE — see src/video/schemas.py).
    Retries on malformed output — cheap and local, so a few extra attempts cost
    nothing."""
    settings = get_settings()
    system_prompt = _STYLE_PROMPTS.get(style, _STYLE_PROMPTS["AVATAR_UGC"])
    user_prompt = (
        f"Product title: {product_title}\n"
        f"Product description: {product_description or '(none provided)'}\n"
        f"style: {style}\n\n"
        "Write the ad script now."
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
                        "format": VideoScript.model_json_schema(),
                        "stream": False,
                        "options": {"temperature": 0.7},
                    },
                )
                r.raise_for_status()
                content = r.json()["message"]["content"]
                return VideoScript.model_validate_json(content)
            except Exception as e:  # malformed JSON, schema mismatch, Ollama unreachable, etc.
                last_error = e
                logger.warning("generate_ugc_script attempt %d/%d failed: %s", attempt, max_retries, e)

    raise RuntimeError(f"qwen3 script generation failed after {max_retries} attempts: {last_error}")
