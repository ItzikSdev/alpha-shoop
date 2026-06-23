"""
Shopify Horizon Theme Customization.
Reads and writes theme assets to configure the store homepage, announcement bar,
brand colors, and navigation — all automatically from the brand brief.

Requires: read_themes, write_themes, read_online_store_navigation, write_online_store_navigation
"""
from __future__ import annotations
import json
import logging
import secrets
from .shopify import _shopify_rest, _shopify_gql, _shopify_creds
from src.config import get_settings

logger = logging.getLogger(__name__)

THEME_ID_CACHE: str | None = None


def clear_theme_id_cache() -> None:
    """Call this after installing a new theme so the next request fetches the fresh active theme."""
    global THEME_ID_CACHE
    THEME_ID_CACHE = None


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _active_theme_id() -> str | None:
    global THEME_ID_CACHE
    if THEME_ID_CACHE:
        return THEME_ID_CACHE
    try:
        data = await _shopify_rest("GET", "themes.json")
        for t in data.get("themes", []):
            if t.get("role") == "main":
                THEME_ID_CACHE = str(t["id"])
                return THEME_ID_CACHE
    except Exception as exc:
        logger.warning("themes.json: %s", exc)
    return None


async def _read_asset(theme_id: str, key: str) -> dict | str:
    """Fetch a theme asset. Returns parsed dict for JSON assets, raw string for Liquid."""
    data = await _shopify_rest(
        "GET",
        f"themes/{theme_id}/assets.json?asset%5Bkey%5D={key.replace('/', '%2F').replace('[', '%5B').replace(']', '%5D')}"
    )
    value = data.get("asset", {}).get("value", "")
    if key.endswith(".json"):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return value


async def _write_asset(theme_id: str, key: str, content: dict | str) -> bool:
    value = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content
    try:
        await _shopify_rest("PUT", f"themes/{theme_id}/assets.json", {
            "asset": {"key": key, "value": value}
        })
        return True
    except Exception as exc:
        logger.warning("write_asset %s: %s", key, exc)
        return False


def _uid(prefix: str = "") -> str:
    return (prefix + secrets.token_hex(4))[:12]


def _resolve_current_settings(settings: dict) -> dict:
    """
    Normalize settings_data.json's "current" field to always be a dict we can mutate.

    Shopify allows "current" to be either an inline settings object OR a string
    naming one of the "presets" entries. In the latter case we copy the named
    preset into an inline dict and write it back as "current" so downstream
    code (and Shopify) always sees a concrete settings object.
    """
    current = settings.get("current")
    if isinstance(current, dict):
        return current
    if isinstance(current, str):
        presets = settings.get("presets", {})
        current = dict(presets.get(current, {}))
    else:
        current = {}
    settings["current"] = current
    return current


# ── 1. Brand colors ───────────────────────────────────────────────────────────

_TONE_PALETTES = {
    "warm":        {"bg": "#FAF6F1", "fg": "#2C1810", "accent": "#C8956C"},
    "bold":        {"bg": "#FFFFFF", "fg": "#0A0A0A", "accent": "#0A0A0A"},
    "minimal":     {"bg": "#FFFFFF", "fg": "#111111", "accent": "#333333"},
    "playful":     {"bg": "#FFFEF0", "fg": "#1A1A1A", "accent": "#FF6B6B"},
    "trustworthy": {"bg": "#F5F9FF", "fg": "#1C2B3A", "accent": "#2C5F8A"},
}


def _contrast(hex_color: str) -> str:
    """Pick black or white text/label color for legibility against hex_color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#FFFFFF"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luma > 160 else "#FFFFFF"


async def apply_brand_colors(tone: str, theme_id: str) -> bool:
    pal = _TONE_PALETTES.get(tone.lower(), _TONE_PALETTES["warm"])
    settings = await _read_asset(theme_id, "config/settings_data.json")
    if not isinstance(settings, dict):
        return False
    current = _resolve_current_settings(settings)

    if isinstance(current.get("color_schemes"), dict):
        # Dawn-style: named schemes (scheme-1..N), each its own bg/text/button/shadow.
        # Override scheme-1 (the default light scheme most sections start on) with
        # the brand palette so the whole storefront picks it up without per-section edits.
        schemes = current["color_schemes"]
        contrast = _contrast(pal["accent"])
        schemes["scheme-1"] = {"settings": {
            "background": pal["bg"], "background_gradient": "",
            "text": pal["fg"], "button": pal["accent"], "button_label": contrast,
            "secondary_button_label": pal["fg"], "shadow": pal["fg"],
        }}
        current["buttons_radius"] = 0
        current["card_corner_radius"] = 2
    else:
        # Horizon-style: flat global palette.
        current["color_palette"] = {"background": pal["bg"], "foreground": pal["fg"]}
        current["button_border_radius_primary"] = 2
        current["button_border_radius_secondary"] = 2
        current["card_corner_radius"] = 2

    return await _write_asset(theme_id, "config/settings_data.json", settings)


# ── 2. Announcement bar ───────────────────────────────────────────────────────

async def set_announcement_bar(messages: list[str], theme_id: str, bg_color: str = "#1A1A1A") -> bool:
    """
    Replace the announcement bar blocks with trust-signal messages.
    messages: list of strings shown one at a time (auto-rotates).
    """
    header_group = await _read_asset(theme_id, "sections/header-group.json")
    if not isinstance(header_group, dict):
        return False

    sections = header_group.get("sections", {})
    ann_key = next(
        (k for k, v in sections.items() if v.get("type") in ("header-announcements", "announcement-bar")),
        None
    )
    if not ann_key:
        return False

    ann = sections[ann_key]
    is_dawn = ann.get("type") == "announcement-bar"

    blocks = {}
    order = []
    for msg in messages[:5]:
        bid = _uid("ann_")
        if is_dawn:
            blocks[bid] = {"type": "announcement", "settings": {"text": msg, "link": ""}}
        else:
            blocks[bid] = {
                "type": "_announcement",
                "settings": {
                    "text": msg,
                    "font": "var(--font-subheading--family)",
                    "font_size": "0.75rem",
                    "letter_spacing": "widest",
                    "case": "uppercase",
                },
                "blocks": {},
            }
        order.append(bid)

    ann["blocks"] = blocks
    ann["block_order"] = order

    if is_dawn:
        ann["settings"]["auto_rotate"] = len(messages) > 1
        ann["settings"]["change_slides_speed"] = 4
    else:
        ann["settings"]["background_color"] = bg_color
        ann["settings"]["speed"] = 4
        ann["settings"]["padding-block-start"] = 12
        ann["settings"]["padding-block-end"] = 12

    return await _write_asset(theme_id, "sections/header-group.json", header_group)


# ── 3. Homepage template ──────────────────────────────────────────────────────

async def _is_dawn_architecture(theme_id: str) -> bool:
    """Dawn/Online-Store-2.0-family themes ship sections/image-banner.liquid; Horizon doesn't."""
    asset = await _read_asset(theme_id, "sections/image-banner.liquid")
    return bool(asset)


async def build_homepage(brief: dict, theme_id: str) -> bool:
    """
    Rebuild the homepage with TANAOR-quality sections, using each theme family's
    actual native section types (Horizon and Dawn use entirely different schemas
    for the same concepts — hero vs image-banner, product-list vs featured-collection).
    """
    if await _is_dawn_architecture(theme_id):
        return await _build_homepage_dawn(brief, theme_id)
    return await _build_homepage_horizon(brief, theme_id)


async def _build_homepage_dawn(brief: dict, theme_id: str) -> bool:
    """Dawn-native homepage: image-banner (hero) → featured-collection → custom-liquid (story) → collection-list."""
    index = await _read_asset(theme_id, "templates/index.json")
    if not isinstance(index, dict):
        return False

    store_name = brief.get("store_name", "Our Store")
    tagline = brief.get("tagline", "")
    differentiator = brief.get("differentiator", "")
    about_us = brief.get("about_us", "")
    collections = brief.get("collections", [])
    tone = brief.get("tone", "warm")
    pal = _TONE_PALETTES.get(tone.lower(), _TONE_PALETTES["warm"])
    about_short = about_us.split("\n\n")[0] if about_us else differentiator
    first_collection_handle = (
        collections[0].lower().replace(" ", "-").replace("&", "and") if collections else "all"
    )

    hero_id = "hero_main"
    featured_id = "featured_products"
    story_id = "story_brand"
    collection_list_id = "collections_browse"

    sections = {
        hero_id: {
            "type": "image-banner",
            "blocks": {
                "heading": {"type": "heading", "settings": {"heading": tagline, "heading_size": "h0"}},
                "text": {"type": "text", "settings": {"text": differentiator, "text_style": "subtitle"}},
                "buttons": {
                    "type": "buttons",
                    "settings": {
                        "button_label_1": "Shop Now",
                        "button_link_1": f"shopify://collections/{first_collection_handle}",
                        "button_style_secondary_1": False,
                    },
                },
            },
            "block_order": ["heading", "text", "buttons"],
            "settings": {
                "image_height": "large",
                "color_scheme": "scheme-1",
                "image_overlay_opacity": 30,
                "show_text_box": True,
                "desktop_content_position": "middle-center",
                "desktop_content_alignment": "center",
            },
        },
        featured_id: {
            "type": "featured-collection",
            "blocks": {},
            "settings": {
                "collection": first_collection_handle,
                "products_to_show": 4,
                "columns_desktop": 4,
                "title": "Best Sellers",
                "heading_size": "h1",
                "color_scheme": "scheme-1",
            },
        },
        story_id: {
            "type": "custom-liquid",
            "blocks": {},
            "settings": {
                "liquid": (
                    f'<div style="max-width:1100px;margin:0 auto;padding:80px 32px;'
                    f'display:flex;gap:60px;align-items:center;flex-wrap:wrap;">'
                    f'<div style="flex:1;min-width:280px;">'
                    f'<p style="font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:{pal["accent"]};margin-bottom:12px;">Our Story</p>'
                    f'<h2 style="font-size:2rem;font-weight:700;line-height:1.2;margin-bottom:20px;">Why {store_name}?</h2>'
                    f'<p style="font-size:1rem;line-height:1.7;color:#666;margin-bottom:28px;">{about_short}</p>'
                    f'<a href="/pages/about-us" style="display:inline-block;padding:12px 28px;'
                    f'border:1.5px solid {pal["fg"]};color:{pal["fg"]};text-decoration:none;'
                    f'font-size:0.8rem;letter-spacing:0.08em;text-transform:uppercase;font-weight:600;">'
                    f'Learn More</a></div>'
                    f'<div style="flex:1;min-width:280px;aspect-ratio:4/5;background:{pal["bg"]};'
                    f'border-radius:2px;border:1px solid #eee;"></div></div>'
                ),
            },
        },
        collection_list_id: {
            "type": "collection-list",
            "blocks": {},
            "settings": {
                "title": "Shop by Category",
                "heading_size": "h1",
                "columns_desktop": min(len(collections), 4) if collections else 3,
                "color_scheme": "scheme-1",
            },
        },
    }

    index["sections"] = sections
    index["order"] = [hero_id, featured_id, story_id, collection_list_id]
    return await _write_asset(theme_id, "templates/index.json", index)


async def _build_homepage_horizon(brief: dict, theme_id: str) -> bool:
    """
    Rebuild the homepage template with TANAOR-quality sections:
      1. Hero — brand tagline + CTA
      2. Marquee — scrolling trust signals
      3. Product list — featured collection (Best Sellers)
      4. Media with content — brand differentiator story
      5. Collection list — browse all collections
    """
    index = await _read_asset(theme_id, "templates/index.json")
    if not isinstance(index, dict):
        return False

    store_name = brief.get("store_name", "Our Store")
    tagline = brief.get("tagline", "")
    differentiator = brief.get("differentiator", "")
    about_us = brief.get("about_us", "")
    announcement = brief.get("announcement_bar", "")
    collections = brief.get("collections", [])
    tone = brief.get("tone", "warm")
    pal = _TONE_PALETTES.get(tone.lower(), _TONE_PALETTES["warm"])

    first_collection_handle = (
        collections[0].lower().replace(" ", "-").replace("&", "and") if collections else "all"
    )

    # Trust signal messages for marquee
    trust_msgs = [m.strip() for m in announcement.split("|") if m.strip()]
    if not trust_msgs:
        trust_msgs = ["Free Shipping on All Orders", "30-Day Hassle-Free Returns", differentiator[:60]]
    marquee_text = "  ✦  ".join(trust_msgs + trust_msgs)  # double for seamless loop

    # About us short version (first paragraph only)
    about_short = about_us.split("\n\n")[0] if about_us else differentiator

    # ── Build new section definitions ─────────────────────────────────────────

    hero_id = "hero_main"
    hero_text_id = _uid("txt_")
    hero_sub_id = _uid("sub_")
    hero_btn_id = _uid("btn_")

    marquee_id = "marquee_trust"

    product_list_id = "products_featured"

    story_id = "story_brand"
    story_text_id = _uid("stxt_")
    story_head_id = _uid("shed_")
    story_body_id = _uid("sbdy_")

    collection_list_id = "collections_browse"

    sections = {
        # ── Hero ──────────────────────────────────────────────────────────────
        hero_id: {
            "type": "hero",
            "blocks": {
                hero_text_id: {
                    "type": "text",
                    "settings": {
                        "text": f"<p>{tagline}</p>",
                        "text_color": "#FFFFFF",
                        "width": "fit-content",
                        "max_width": "narrow",
                        "alignment": "left",
                        "type_preset": "h1",
                        "font": "var(--font-heading--family)",
                        "font_size": "3rem",
                        "line_height": "display-tight",
                        "letter_spacing": "heading-normal",
                        "case": "none",
                        "wrap": "pretty",
                        "background": False,
                    },
                    "blocks": {},
                },
                hero_sub_id: {
                    "type": "text",
                    "settings": {
                        "text": f"<p>{differentiator}</p>",
                        "text_color": "rgba(255,255,255,0.85)",
                        "width": "fit-content",
                        "max_width": "narrow",
                        "alignment": "left",
                        "type_preset": "h4",
                        "font": "var(--font-body--family)",
                        "font_size": "1rem",
                        "line_height": "body-loose",
                        "letter_spacing": "normal",
                        "case": "none",
                        "wrap": "pretty",
                        "background": False,
                    },
                    "blocks": {},
                },
                hero_btn_id: {
                    "type": "button",
                    "settings": {
                        "label": "Shop Now",
                        "link": f"shopify://collections/{first_collection_handle}",
                        "open_in_new_tab": False,
                        "style_class": "button-custom",
                        "custom_button_background": "#FFFFFF",
                        "custom_button_text": pal["fg"],
                        "custom_button_border": "#FFFFFF",
                        "width": "fit-content",
                        "width_mobile": "fit-content",
                    },
                    "blocks": {},
                },
            },
            "block_order": [hero_text_id, hero_sub_id, hero_btn_id],
            "settings": {
                "media_type_1": "image",
                "stack_media_on_mobile": False,
                "content_direction": "column",
                "horizontal_alignment_flex_direction_column": "flex-start",
                "vertical_alignment_flex_direction_column": "flex-end",
                "gap": 20,
                "section_width": "full-width",
                "section_height": "large",
                "background_color": pal["fg"],
                "toggle_overlay": True,
                "overlay_color": "#00000055",
                "overlay_style": "gradient",
                "gradient_direction": "to top",
                "padding-block-start": 0,
                "padding-block-end": 60,
                "padding-inline-start": 40,
                "padding-inline-end": 40,
            },
        },

        # ── Marquee (trust signals) — block type is 'text', content needs <p> wrap
        marquee_id: {
            "type": "marquee",
            "blocks": {},  # filled below
            "block_order": [],
            "settings": {
                "movement_direction": "left",
                "background_color": pal["accent"],
                "padding-block-start": 12,
                "padding-block-end": 12,
            },
        },

        # ── Featured products ─────────────────────────────────────────────────
        product_list_id: {
            "type": "product-list",
            "blocks": {},
            "settings": {
                "collection": first_collection_handle,
                "layout_type": "grid",
                "carousel_on_mobile": True,
                "max_products": 4,
                "columns": 4,
                "columns_mobile": 2,
                "section_width": "page-width",
                "heading": "Best Sellers",
                "heading_font": "var(--font-heading--family)",
                "heading_size": "h2",
                "show_view_all": True,
                "view_all_label": "View All",
                "background_color": "rgba(0,0,0,0)",
                "padding-block-start": 60,
                "padding-block-end": 60,
            },
        },

        # ── Brand story via custom-liquid (full HTML control) ────────────────
        story_id: {
            "type": "custom-liquid",
            "blocks": {},
            "settings": {
                "liquid": (
                    f'<div style="max-width:1100px;margin:0 auto;padding:80px 32px;'
                    f'display:flex;gap:60px;align-items:center;flex-wrap:wrap;">'
                    f'<div style="flex:1;min-width:280px;">'
                    f'<p style="font-size:0.75rem;letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:{pal["accent"]};margin-bottom:12px;">Our Story</p>'
                    f'<h2 style="font-size:2rem;font-weight:700;line-height:1.2;margin-bottom:20px;">Why {store_name}?</h2>'
                    f'<p style="font-size:1rem;line-height:1.7;color:#666;margin-bottom:28px;">{about_short}</p>'
                    f'<a href="/pages/about-us" style="display:inline-block;padding:12px 28px;'
                    f'border:1.5px solid {pal["fg"]};color:{pal["fg"]};text-decoration:none;'
                    f'font-size:0.8rem;letter-spacing:0.08em;text-transform:uppercase;font-weight:600;">'
                    f'Learn More</a></div>'
                    f'<div style="flex:1;min-width:280px;aspect-ratio:4/5;background:{pal["bg"]};'
                    f'border-radius:2px;border:1px solid #eee;"></div></div>'
                ),
            },
        },

        # ── Browse collections ────────────────────────────────────────────────
        collection_list_id: {
            "type": "collection-list",
            "blocks": {},
            "settings": {
                "heading": "Shop by Category",
                "heading_font": "var(--font-heading--family)",
                "heading_size": "h2",
                "layout_type": "grid",
                "columns": min(len(collections), 4) if collections else 3,
                "columns_mobile": 2,
                "section_width": "page-width",
                "background_color": "rgba(0,0,0,0)",
                "image_aspect_ratio": "3 / 4",
                "image_border_radius": 2,
                "padding-block-start": 60,
                "padding-block-end": 80,
            },
        },
    }

    # Populate marquee blocks — type 'text', content must be <p>-wrapped
    mq_block_id = _uid("mq_")
    sections[marquee_id]["blocks"] = {
        mq_block_id: {
            "type": "text",
            "settings": {"text": f"<p>{marquee_text}</p>"},
            "blocks": {},
        }
    }
    sections[marquee_id]["block_order"] = [mq_block_id]

    index["sections"] = sections
    index["order"] = [hero_id, marquee_id, product_list_id, story_id, collection_list_id]

    return await _write_asset(theme_id, "templates/index.json", index)


# ── 4. Navigation menu ────────────────────────────────────────────────────────

_GQL_GET_MENUS = """
{ menus(first: 10) { nodes { id handle } } }
"""

_GQL_MENU_CREATE = """
mutation menuCreate($title: String!, $handle: String!, $items: [MenuItemCreateInput!]!) {
  menuCreate(title: $title, handle: $handle, items: $items) {
    menu { id handle }
    userErrors { field message }
  }
}
"""

_GQL_MENU_UPDATE = """
mutation menuUpdate($id: ID!, $title: String!, $items: [MenuItemUpdateInput!]!) {
  menuUpdate(id: $id, title: $title, items: $items) {
    menu { id handle }
    userErrors { field message }
  }
}
"""


_GQL_LIST_COLLECTIONS = """
{ collections(first: 50) { nodes { title handle } } }
"""


async def setup_navigation(store_name: str, collections: list[str]) -> bool:
    """
    Rebuild the main-menu via GraphQL (REST menus.json removed in API 2024-07).
    Default Shopify menus cannot be deleted — we update them in-place instead.

    Only links to collections/pages that ACTUALLY exist in the store — `collections`
    is the brief's wishlist, not a guarantee; linking to a not-yet-created collection
    produces a broken 404 nav link, so we verify against the real store state first.
    """
    domain, _ = _shopify_creds()

    try:
        existing_collections = await _shopify_gql(_GQL_LIST_COLLECTIONS, {})
        real_handles = {
            c["handle"] for c in existing_collections.get("collections", {}).get("nodes", [])
        }
    except Exception:
        real_handles = set()

    nav_items = []
    for coll in collections:
        handle = coll.lower().replace(" ", "-").replace("&", "and").replace("/", "-")
        if handle in real_handles:
            nav_items.append({
                "title": coll,
                "type": "HTTP",
                "url": f"https://{domain}/collections/{handle}",
            })

    try:
        existing_pages = await _shopify_rest("GET", "pages.json")
        page_handles = {p.get("handle", "") for p in existing_pages.get("pages", [])}
    except Exception:
        page_handles = set()

    for title, handle in [("About Us", "about-us"), ("Shipping & Returns", "shipping-returns")]:
        if handle in page_handles:
            nav_items.append({"title": title, "type": "HTTP", "url": f"https://{domain}/pages/{handle}"})

    if not nav_items:
        logger.warning("No real collections/pages found yet — skipping nav rebuild to avoid an empty menu")
        return False

    try:
        data = await _shopify_gql(_GQL_GET_MENUS, {})
        menus = data.get("menus", {}).get("nodes", [])
        main = next((m for m in menus if m.get("handle") in ("main-menu", "frontend-navigation")), None)

        if main:
            # Update in-place — items without id replace all existing items
            result = await _shopify_gql(_GQL_MENU_UPDATE, {"id": main["id"], "title": "Main Menu", "items": nav_items})
            errors = result.get("menuUpdate", {}).get("userErrors", [])
        else:
            result = await _shopify_gql(_GQL_MENU_CREATE, {
                "title": "Main Menu",
                "handle": "main-menu",
                "items": nav_items,
            })
            errors = result.get("menuCreate", {}).get("userErrors", [])

        if errors:
            logger.warning("Navigation userErrors: %s", errors)
            return False
        return True
    except Exception as exc:
        logger.warning("Navigation failed (GQL): %s", exc)
        return False


# ── 5. Master entry point ─────────────────────────────────────────────────────

async def full_store_setup(brief: dict) -> dict[str, bool]:
    """
    Apply all theme customizations from the brand brief in one call.
    Returns a dict of what succeeded.
    """
    results: dict[str, bool] = {}
    theme_id = await _active_theme_id()
    if not theme_id:
        return {"theme_found": False}
    results["theme_found"] = True

    tone = brief.get("tone", "warm")
    pal = _TONE_PALETTES.get(tone.lower(), _TONE_PALETTES["warm"])

    # Trust signals for announcement bar
    raw = brief.get("announcement_bar", "")
    messages = [m.strip() for m in raw.split("|") if m.strip()]
    if not messages:
        messages = [
            "Free Shipping on All Orders",
            "30-Day Hassle-Free Returns",
            brief.get("differentiator", "")[:60],
        ]

    results["colors"]       = await apply_brand_colors(tone, theme_id)
    results["announcement"] = await set_announcement_bar(messages, theme_id, bg_color=pal["accent"])
    results["homepage"]     = await build_homepage(brief, theme_id)
    results["navigation"]   = await setup_navigation(
        brief.get("store_name", ""), brief.get("collections", [])
    )

    logger.info("full_store_setup: %s", results)
    return results
