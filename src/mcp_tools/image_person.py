"""Human-face detection for CJ product images — MediaPipe's BlazeFace detector
(a small, purpose-built face model, ~230KB, CPU-only), NOT a general vision/LLM
model. No Ollama/GPU memory involved (that approach got removed during a real
memory crisis on this machine, see git history around 2026-08-05).

First version used OpenCV's bundled Haar cascade — reliable-sounding but in
practice missed an obvious case (a laughing baby's face, clearly frontal, well
lit) that a human immediately spotted on the live store. Haar cascades are
known to be unreliable on young children's face proportions and open-mouth
expressions; BlazeFace (trained on a much broader/modern dataset) does not miss
that same image (confirmed: 94.9% confidence where Haar cascade returned zero
detections) — this replaces it entirely rather than layering a second detector
on top.
"""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import httpx
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from PIL import Image

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).resolve().parents[2] / "data/models/blaze_face_short_range.tflite"
_detector: vision.FaceDetector | None = None


def _get_detector() -> vision.FaceDetector:
    global _detector
    if _detector is None:
        base_options = mp_python.BaseOptions(model_asset_path=str(_MODEL_PATH))
        options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.5)
        _detector = vision.FaceDetector.create_from_options(options)
    return _detector


async def has_person(image_url: str) -> bool:
    """True if a human face is detected in the image. Fails soft (returns False
    — treat as product-only, don't block sourcing on a network hiccup or a
    photo the detector can't parse) rather than raising."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(image_url)
            r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=_np_from_pil(img))
        result = _get_detector().detect(mp_image)
        return len(result.detections) > 0
    except Exception as exc:
        logger.warning("has_person failed for %s: %s", image_url, exc)
        return False


def _np_from_pil(img: Image.Image):
    import numpy as np
    return np.array(img)


async def strip_person_images(image_urls: list[str]) -> list[str]:
    """Returns `image_urls` with any photo containing a human face removed —
    CJ listings often mix product-only shots with a model wearing the item;
    the store rule is product-only images. Never returns an empty list purely
    because every image tripped the detector on a borderline case that isn't
    actually a person — if filtering would remove EVERYTHING, keep the original
    list rather than leave the product with zero images (a human should look at
    an all-flagged product, but this function only screens, doesn't block)."""
    kept = []
    for url in image_urls:
        if not await has_person(url):
            kept.append(url)
    return kept if kept else image_urls
