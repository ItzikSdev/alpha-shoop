"""
Shopify Free Theme Installer.

Selects the best free theme for the store's niche, installs it via Shopify API,
and downloads all theme files to stores/{store_name}/theme/ in the project.

Free themes are sourced from https://themes.shopify.com/collections/free-themes
and their open-source GitHub repositories.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import zipfile
from pathlib import Path

import httpx

from src.mcp_tools.shopify import _shopify_rest, _shopify_gql
from src.mcp_tools.shopify_theme import clear_theme_id_cache

logger = logging.getLogger(__name__)

# Root for local theme storage: <project>/stores/{store_name}/theme/
_STORES_DIR = Path(__file__).resolve().parents[2] / "stores"

# ── Free theme catalogue ──────────────────────────────────────────────────────
# All themes below are free on https://themes.shopify.com/collections/free-themes
# and open-source on GitHub. ZIP URLs point to the current main branch.

FREE_THEMES: dict[str, dict] = {
    "dawn": {
        "display_name": "Dawn",
        "github_zip": "https://github.com/Shopify/dawn/archive/refs/heads/main.zip",
        "description": "Shopify's reference theme — clean, minimal, versatile",
        "best_for": ["general", "electronics", "baby", "home", "tech", "toys", "accessories"],
    },
    "sense": {
        "display_name": "Sense",
        "github_zip": "https://github.com/Shopify/sense/archive/refs/heads/main.zip",
        "description": "Soft, elegant — ideal for beauty, wellness, and lifestyle",
        "best_for": ["beauty", "wellness", "skincare", "candles", "spa", "self-care"],
    },
    "craft": {
        "display_name": "Craft",
        "github_zip": "https://github.com/Shopify/craft/archive/refs/heads/main.zip",
        "description": "Artisan aesthetic — great for handmade and premium goods",
        "best_for": ["jewelry", "handmade", "artisan", "rings", "necklaces", "silver", "gold", "ceramics"],
    },
    "refresh": {
        "display_name": "Refresh",
        "github_zip": "https://github.com/Shopify/refresh-theme/archive/refs/heads/main.zip",
        "description": "Bold and contemporary — lifestyle and fashion brands",
        "best_for": ["fashion", "clothing", "apparel", "streetwear", "lifestyle", "home decor"],
    },
    "crave": {
        "display_name": "Crave",
        "github_zip": "https://github.com/Shopify/crave/archive/refs/heads/main.zip",
        "description": "High-contrast, food-forward design",
        "best_for": ["food", "beverages", "restaurant", "bakery", "coffee", "snacks", "nutrition"],
    },
    "colorblock": {
        "display_name": "Colorblock",
        "github_zip": "https://github.com/Shopify/colorblock/archive/refs/heads/main.zip",
        "description": "Playful, bold colour blocking",
        "best_for": ["kids", "toys", "baby", "playful", "colorful", "education"],
    },
    "origin": {
        "display_name": "Origin",
        "github_zip": "https://github.com/Shopify/origin/archive/refs/heads/main.zip",
        "description": "Editorial, editorial-first layout for visual brands",
        "best_for": ["photography", "art", "editorial", "premium", "luxury", "portfolio"],
    },
    "studio": {
        "display_name": "Studio",
        "github_zip": "https://github.com/Shopify/studio/archive/refs/heads/main.zip",
        "description": "Gallery-quality for creators and artists",
        "best_for": ["art", "prints", "photography", "creative", "design", "illustration"],
    },
}

# Niche keyword → theme key mapping for fast fallback (no LLM)
_NICHE_THEME_MAP: list[tuple[list[str], str]] = [
    (["jewelry", "ring", "necklace", "bracelet", "silver", "gold", "diamond"], "craft"),
    (["baby", "infant", "toddler", "newborn", "toy", "kids"], "dawn"),
    (["beauty", "skincare", "makeup", "cosmetics", "wellness", "spa"], "sense"),
    (["food", "coffee", "bakery", "snack", "nutrition", "beverage"], "crave"),
    (["fashion", "clothing", "apparel", "dress", "shoes", "streetwear"], "refresh"),
    (["art", "print", "photograph", "creative", "illustration"], "studio"),
    (["candle", "home decor", "furniture", "kitchen", "lifestyle"], "refresh"),
]


def pick_theme_for_niche(niche: str) -> str:
    """Return a theme key that best matches the store niche. Falls back to 'dawn'."""
    niche_lower = niche.lower()
    for keywords, theme_key in _NICHE_THEME_MAP:
        if any(kw in niche_lower for kw in keywords):
            return theme_key
    return "dawn"


async def _download_zip(url: str) -> bytes:
    """Download a ZIP file from a URL. Raises on HTTP errors."""
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


def _extract_theme_to_local(zip_bytes: bytes, store_name: str, theme_key: str) -> Path:
    """
    Extract a GitHub-format theme ZIP to stores/{store_name}/theme/.

    GitHub ZIPs have a wrapper folder (e.g. dawn-main/). We strip it.
    Returns the path to the extracted theme directory.
    """
    theme_dir = _STORES_DIR / store_name / "theme"
    theme_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members = zf.namelist()
        # GitHub ZIP: first component is always the wrapper dir (e.g. "dawn-main/")
        prefix = members[0].split("/")[0] + "/" if members else ""

        for member in members:
            if not member.endswith("/"):  # skip directory entries
                relative = member[len(prefix):]  # strip wrapper dir
                if not relative:
                    continue
                target = theme_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())

    # Write a metadata file so we know which theme is installed
    (theme_dir.parent / "theme_info.json").write_text(
        json.dumps({"theme_key": theme_key, "display_name": FREE_THEMES[theme_key]["display_name"]}, indent=2)
    )
    return theme_dir


async def _install_theme_on_shopify(theme_config: dict) -> str | None:
    """
    POST /themes.json with the GitHub ZIP URL.
    Returns the Shopify theme ID (numeric string) or None on failure.
    """
    try:
        result = await _shopify_rest(
            "POST",
            "themes.json",
            {
                "theme": {
                    "name": theme_config["display_name"],
                    "src": theme_config["github_zip"],
                    "role": "unpublished",  # install first, then publish after processing
                }
            },
        )
        theme = result.get("theme", {})
        theme_id = str(theme.get("id", ""))
        if theme_id:
            logger.info("Theme '%s' installed with ID %s", theme_config["display_name"], theme_id)
        return theme_id or None
    except Exception as exc:
        logger.error("Failed to install theme: %s", exc)
        return None


async def _wait_for_theme_ready(theme_id: str, timeout_s: int = 120) -> bool:
    """
    Poll GET /themes/{id}.json until processing is complete, then publish it as main theme.
    """
    for _ in range(timeout_s // 5):
        await asyncio.sleep(5)
        try:
            result = await _shopify_rest("GET", f"themes/{theme_id}.json")
            theme = result.get("theme", {})
            if not theme.get("processing", True):
                # Processing done — make it the active (main) theme
                await _shopify_rest("PUT", f"themes/{theme_id}.json", {
                    "theme": {"id": theme_id, "role": "main"}
                })
                return True
        except Exception:
            pass
    return False


async def _active_theme_name() -> str:
    try:
        result = await _shopify_rest("GET", "themes.json")
        main = next((t for t in result.get("themes", []) if t.get("role") == "main"), None)
        return main.get("name", "") if main else ""
    except Exception:
        return ""


async def install_free_theme(niche: str, store_name: str) -> dict:
    """Use the store's CURRENT Shopify theme — no gallery downloads.

    DEPRECATED behaviour change: we no longer download free themes from the Shopify
    theme gallery (GitHub ZIPs). Themes are now managed with the official **Shopify
    CLI** (`shopify theme pull` / `dev` / `push`) via the host Storefront Runner, so
    the store keeps all native theme features. This function simply reports the
    store's live theme and performs no install.

    The download helpers (`_download_zip`, `_extract_theme_to_local`,
    `_install_theme_on_shopify`) are retained only for backward compatibility and
    are intentionally unused.

    Returns: {success, theme_key, display_name, skipped, managed_by}
    """
    from src.tracing import agent_log

    active_name = await _active_theme_name()
    agent_log(
        f"Theme: keeping the store's live theme '{active_name or 'current'}' — gallery "
        f"downloads are disabled; manage the theme via the Shopify CLI (Run in localhost / "
        f"Upload to Shopify in the dashboard).",
        "info",
    )
    return {
        "success": True,
        "theme_key": "live",
        "display_name": active_name or "current theme",
        "skipped": True,
        "managed_by": "shopify-cli",
    }
