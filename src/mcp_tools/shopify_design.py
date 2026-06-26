"""
Shopify Design Tools — injects custom CSS and reads theme context for the design agent.
Writes to assets/custom-alpha.css and patches layout/theme.liquid to load it.
"""
from __future__ import annotations
import logging
from .shopify_theme import _active_theme_id, _read_asset, _write_asset, _resolve_current_settings

logger = logging.getLogger(__name__)

_CSS_LINK_TAG = "{{ 'custom-alpha.css' | asset_url | stylesheet_tag }}"


async def add_custom_css(css: str, theme_id: str | None = None) -> bool:
    """Write CSS to assets/custom-alpha.css and inject <link> into layout/theme.liquid."""
    tid = theme_id or await _active_theme_id()
    if not tid:
        return False

    # Write the CSS asset
    ok_css = await _write_asset(tid, "assets/custom-alpha.css", css)
    if not ok_css:
        logger.warning("Failed to write custom-alpha.css")
        return False

    # Inject into theme.liquid if not already there
    liquid = await _read_asset(tid, "layout/theme.liquid")
    if isinstance(liquid, str) and _CSS_LINK_TAG not in liquid:
        patched = liquid.replace("</head>", f"  {_CSS_LINK_TAG}\n</head>", 1)
        if "</head>" not in liquid:
            # Fallback: append at end
            patched = liquid + f"\n{_CSS_LINK_TAG}\n"
        ok_liquid = await _write_asset(tid, "layout/theme.liquid", patched)
        if not ok_liquid:
            logger.warning("Failed to patch theme.liquid")
            return False

    return True


async def read_theme_context(theme_id: str | None = None) -> dict:
    """Read key theme assets to give the design LLM context on current state."""
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {}
    settings = await _read_asset(tid, "config/settings_data.json")
    index = await _read_asset(tid, "templates/index.json")
    return {
        "theme_id": tid,
        "settings_summary": {
            "current": (_resolve_current_settings(settings) if isinstance(settings, dict) else {}),
        },
        "homepage_sections": list(index.get("order", [])) if isinstance(index, dict) else [],
    }


async def read_full_theme_context(theme_id: str | None = None) -> dict:
    """Extended theme context for design review — includes CSS preview and section details."""
    tid = theme_id or await _active_theme_id()
    if not tid:
        return {}
    settings = await _read_asset(tid, "config/settings_data.json")
    index = await _read_asset(tid, "templates/index.json")
    css = await _read_asset(tid, "assets/custom-alpha.css")

    sections = index.get("sections", {}) if isinstance(index, dict) else {}
    section_types = {k: v.get("type", "?") for k, v in sections.items()} if sections else {}
    # Settings detail per section — lets the reviewer catch structural gaps a CSS
    # diff can't show: a hero with no background image, a featured-collection
    # pointing at an empty collection, etc.
    section_settings = {k: v.get("settings", {}) for k, v in sections.items()} if sections else {}

    return {
        "theme_id": tid,
        "settings_summary": {
            "current": (_resolve_current_settings(settings) if isinstance(settings, dict) else {}),
        },
        "homepage_sections": list(index.get("order", [])) if isinstance(index, dict) else [],
        "section_types": section_types,
        "section_settings": section_settings,
        "css_preview": css if isinstance(css, str) else "",
    }
