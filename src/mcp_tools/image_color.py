"""Product image dominant-color detection — plain pixel analysis (Pillow), no AI
model, no Ollama/GPU involved. Used to catch gender-miscategorized products
(e.g. a pink outfit filed under "Baby Boys" just because CJ's own listing title
said "Boys") before Sol lists them.
"""
from __future__ import annotations

import colorsys
import logging
from io import BytesIO

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

# (label, hue-degree range) — tuned for baby-apparel photos: mostly solid/pastel
# garments shot on a plain backdrop.
_COLOR_BUCKETS = [
    ("red", (0, 10)), ("orange", (10, 30)), ("yellow", (30, 50)),
    ("green", (50, 150)), ("blue", (150, 200)), ("purple", (200, 270)),
    ("pink", (270, 330)), ("red", (330, 360)),
]


def _rgb_to_label(r: int, g: int, b: int) -> str:
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue_deg = h * 360
    if v < 0.2:
        return "black"
    if s < 0.12:
        return "white" if v > 0.85 else "gray"
    if s < 0.25 and v > 0.7:
        return "beige"
    # Red-family hues (0-20 / 340-360) at LOW-to-MODERATE saturation read as
    # salmon/coral/rose/pink to the eye, not "red" — true red is both saturated
    # AND fairly dark/vivid (e.g. crimson ~s=0.9,v=0.86). Checked against a real
    # photo: a salmon-pink baby jumpsuit measured s=0.36, v=0.78 — high enough
    # saturation to miss a naive s<0.25 cutoff, but clearly "pink" to a human.
    if (hue_deg < 20 or hue_deg >= 340) and s < 0.65:
        return "pink"
    for label, (lo, hi) in _COLOR_BUCKETS:
        if lo <= hue_deg < hi:
            return label
    return "neutral"


async def dominant_color(image_url: str, sample_size: int = 150) -> dict:
    """Downloads the image and returns its dominant color as a human label + RGB.

    Uses PALETTE QUANTIZATION (Image.quantize), not raw-pixel frequency counting
    — a first version counted exact (r,g,b) tuples directly, which fails badly on
    real JPEG photos: texture/noise/compression means no single exact pixel value
    repeats often, so a flat, low-noise background region (a plain rug, a wall)
    wins purely by having less variation, even when the actual garment is the
    visually obvious subject (confirmed on a real product photo: a salmon-pink
    ribbed jumpsuit shot on a wood table with a white rug + pink flowers behind
    it — raw pixel counting picked the rug as "white"; quantization correctly
    finds pink as the dominant palette color). Background/backdrop colors (near-
    white, near-black, wood-tan) are also explicitly excluded from the palette
    ranking, not just relied on to lose by count, since a busy lifestyle photo's
    backdrop can otherwise still out-mass a smaller garment region.

    Fails soft — never blocks a product creation on a network hiccup or bad
    image."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(image_url)
            r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img = img.resize((sample_size, sample_size))

        palette_img = img.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
        palette = palette_img.getpalette()[: 12 * 3]
        color_counts = palette_img.getcolors()  # [(count, palette_index), ...]

        candidates = []
        for count, idx in color_counts:
            r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
            label = _rgb_to_label(r, g, b)
            if label in ("white", "black", "gray", "beige"):
                continue  # likely backdrop, not the product
            candidates.append((count, r, g, b, label))

        if not candidates:
            # Everything quantized to backdrop-like colors (e.g. a true white-on-
            # white flat lay) — fall back to the single most common palette color.
            count, idx = max(color_counts, key=lambda c: c[0])
            r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
            return {"label": _rgb_to_label(r, g, b), "rgb": (r, g, b)}

        _count, r, g, b, label = max(candidates, key=lambda c: c[0])
        return {"label": label, "rgb": (r, g, b)}
    except Exception as exc:
        logger.warning("dominant_color failed for %s: %s", image_url, exc)
        return {"label": "unknown", "rgb": None}


# Per Sol (Product Sourcer & Copywriter) — asked directly 2026-08-05 "what colors
# should NEVER be filed under Baby Boys / Baby Girls": pink/purple not for Boys,
# blue/green not for Girls. Not an editorial stance in general, just this store's
# convention per its own sourcing agent. Neutral/unknown colors never trigger a
# mismatch (nothing reliable to correct against).
_GIRL_CODED = {"pink", "purple"}
_BOY_CODED = {"blue", "green"}


def collection_mismatch(collection: str, color_label: str) -> str | None:
    """Given the collection a product is about to be filed under and its detected
    dominant color, returns a suggested REPLACEMENT collection name if they
    clash (e.g. a pink product headed for 'Baby Boys'), else None."""
    c = (collection or "").lower()
    if "boys" in c and color_label in _GIRL_CODED:
        return collection.replace("Boys", "Girls") if "Boys" in collection else "Baby Girls"
    if "girls" in c and color_label in _BOY_CODED:
        return collection.replace("Girls", "Boys") if "Girls" in collection else "Baby Boys"
    return None
