"""Structured output contract for the UGC video script step (qwen3 via Ollama).

`VideoScript.model_json_schema()` is passed to Ollama's `format` parameter so the
model is constrained to emit valid JSON matching this shape — no prompt-and-hope.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# AVATAR_UGC: an AI avatar speaks to camera (hook + script), text overlays explain
#   features/benefits alongside them.
# PRODUCT_3D_SHOWCASE: no human face — rotating/macro product renders (Wan2.2 camera
#   motion does the work), floating 3D/2D title cards + captions carry the benefits.
VideoStyle = Literal["AVATAR_UGC", "PRODUCT_3D_SHOWCASE"]


class VideoScene(BaseModel):
    order: int = Field(description="0-indexed position of this scene in the video")
    voiceover_line: str = Field(description="One or two spoken sentences for this scene's voiceover")
    visual_prompt: str = Field(
        description="Wan2.2 text-to-video prompt for this scene: subject, product placement, "
        "camera motion, lighting. English, single paragraph, no camera jargon abbreviations."
    )
    text_overlay: str = Field(
        default="",
        description="On-screen caption/title-card text for this scene (short, e.g. a benefit "
        "callout like 'Machine washable' or a title-card word). '' if this scene has none.",
    )
    duration_s: float = Field(default=4.0, ge=2.0, le=8.0, description="Target scene length in seconds")


class VideoScript(BaseModel):
    style: VideoStyle = "AVATAR_UGC"
    product_name: str
    hook: str = Field(description="The opening line — must grab attention in the first scene")
    scenes: list[VideoScene] = Field(min_length=2, max_length=5)
    cta: str = Field(description="Closing call-to-action line, e.g. 'Shop now, link in bio'")
