"""
Frontend Agent — implements the design spec produced by design_agent Mode 1.

Reads the current theme state, reads the design_spec + iteration_feedback,
asks the LLM what targeted changes to make, then applies them via Shopify API:
  - Enhanced CSS additions to assets/custom-alpha.css
  - Theme settings updates (config/settings_data.json)
  - Homepage section structure improvements (templates/index.json)

After each pass, sets frontend_report (summary of what changed) and increments
design_iterations so design_agent Mode 2 can review the result.
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify_design import add_custom_css, read_full_theme_context
from src.mcp_tools.shopify_theme import (
    _active_theme_id,
    _read_asset,
    _write_asset,
    _resolve_current_settings,
    _TONE_PALETTES,
)
from src.mcp_tools.shopify import upload_hero_image_from_product, best_populated_collection_with_count
from src.tracing import agent_log
from src.tracing.context import current_node

logger = logging.getLogger(__name__)

_FRONTEND_SYSTEM = """\
You are a senior Shopify frontend developer implementing a design spec.

STRUCTURAL STYLE GOALS — when a checklist item touches the nav, hero/banner, featured
collection, or footer, implement it toward the house style: clean minimal modern,
white/neutral-gray with a muted lime-green accent (lalo.com reference, --brand-accent
is the verified real #B8D151, --brand-fg is the verified real #4F4F4F, not a guess):
- Nav: normal-weight (not heavy/bold) links, generous letter-spacing and whitespace;
  active link = 2px solid border-bottom in var(--brand-accent), never a background fill.
- Hero/banner: headline text directly over the image, one emphasized word/phrase
  wrapped in a span colored var(--brand-accent). Favor soft contrast over high-drama.
- Featured collection: heading left-aligned, var(--brand-fg), normal weight — never
  bold black or centered.
- Footer: newsletter consent/legal text present, small and at reduced opacity.

CSS SPECIFICITY WARNING — verified live: this theme loads component-specific
stylesheets (component-list-menu.css, section-image-banner.css, section-footer.css,
etc.) AFTER assets/custom-alpha.css in <head>. Equal-specificity rules from those
files beat ours on source order alone. Always add !important to nav/banner/
featured-collection/footer override declarations (font-transform, letter-spacing,
border-bottom, background-color, color) — without it, the rule is silently ignored
even though the CSS file is correctly linked and served. Also verify selectors
against REAL rendered class names, not assumed Dawn conventions — e.g. Dawn applies
.header__menu-item directly to the <a>, not to a wrapping parent, so a selector like
".header__menu-item > a" matches nothing.

You will receive:
1. The design quality checklist (what must be true)
2. Specific feedback from the design reviewer (what's currently failing)
3. Current theme CSS (first 3000 chars)
4. Current theme settings (relevant keys)
5. Current homepage section order

Your job: produce targeted changes to fix the failing criteria.

Output ONLY valid JSON (no markdown fences):
{
  "css_additions": "additional CSS rules to append to custom-alpha.css (empty string if none needed)",
  "settings_updates": {
    "button_border_radius_primary": 0,
    "card_corner_radius": 2
  },
  "changes_summary": "2-3 sentence summary of what you changed and why"
}

Rules:
- css_additions must be valid CSS (no fences, no comments about what it is)
- settings_updates must use valid Shopify theme setting keys
- Only include what is needed to fix failing criteria — don't change things that are already working
- If a criterion is about CSS → fix it in css_additions
- If a criterion is about theme settings → fix it in settings_updates
- changes_summary must be specific: "Added 4/5 aspect-ratio to product card images via CSS,
  set button border-radius to 0 in settings, added sticky header blur effect"
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    return text.strip()


async def frontend_node(state: AgentState) -> dict:
    current_node.set("frontend_agent")

    design_spec = state.get("design_spec")
    if not design_spec:
        agent_log("No design spec — skipping frontend pass", "warning")
        return {"frontend_report": "No spec to implement.", "design_iterations": 1}

    iterations = state.get("design_iterations", 0)
    agent_log(f"Frontend implementation pass #{iterations + 1}...", "action")

    checklist = design_spec.get("quality_checklist", [])
    feedback = design_spec.get("iteration_feedback", [])
    pal = design_spec.get("palette", _TONE_PALETTES["warm"])

    # Read current theme state
    theme_ctx = await read_full_theme_context()
    theme_id = theme_ctx.get("theme_id")

    if not theme_id:
        return {
            "frontend_report": "Could not read theme ID — skipping.",
            "design_iterations": iterations + 1,
        }

    current_settings = theme_ctx.get("settings_summary", {}).get("current", {})
    current_sections = theme_ctx.get("homepage_sections", [])
    current_css = theme_ctx.get("css_preview", "")[:3000]
    section_settings = theme_ctx.get("section_settings", {})
    changes_made: list[str] = []

    # ── Phase 0: deterministic structural fixes ──────────────────────────────
    # These are factual, not creative — code does them directly instead of
    # asking an LLM to guess at image URLs or collection handles.
    index = await _read_asset(theme_id, "templates/index.json")
    if isinstance(index, dict):
        sections = index.get("sections", {})
        index_changed = False

        hero = next((s for s in sections.values() if s.get("type") in ("hero", "image-banner")), None)
        if hero and not hero.get("settings", {}).get("image"):
            agent_log("Hero has no background image — uploading one from an existing product...", "action")
            image_ref = await upload_hero_image_from_product()
            if image_ref:
                hero.setdefault("settings", {})["image"] = image_ref
                index_changed = True
                changes_made.append("Set hero background image")
                agent_log("✓ Hero image set", "success")
            else:
                agent_log("✗ No product image available yet to use as hero", "warning")

        featured = next((s for s in sections.values() if s.get("type") in ("product-list", "featured-collection")), None)
        if featured:
            current_handle = featured.get("settings", {}).get("collection", "")
            populated_handle, populated_count = await best_populated_collection_with_count()
            if populated_handle and populated_handle != current_handle:
                featured.setdefault("settings", {})["collection"] = populated_handle
                index_changed = True
                changes_made.append(f"Pointed featured collection at '{populated_handle}' (has products)")
                agent_log(f"✓ Featured collection repointed to '{populated_handle}'", "success")
            # Dawn fills any slots beyond the real product count with fake $19.99
            # placeholder products — cap products_to_show so visitors never see those.
            # Shopify enforces products_to_show >= 2 (schema min), so with only 1 real
            # product some placeholder filler is unavoidable until more products are added.
            target_show = max(populated_count, 2)
            if populated_count and featured["settings"].get("products_to_show", 0) > target_show:
                featured["settings"]["products_to_show"] = target_show
                index_changed = True
                changes_made.append(f"Capped products_to_show to {target_show} (minimize Dawn placeholder fillers)")
                agent_log(f"✓ products_to_show capped to {target_show}", "success")

        if index_changed:
            await _write_asset(theme_id, "templates/index.json", index)

    # Build prompt
    feedback_block = (
        "\n\nFeedback from design reviewer (specific issues to fix):\n"
        + "\n".join(f"- {f}" for f in feedback)
        if feedback else "\n\n(First pass — implement the full checklist)"
    )

    implementation_prompt = (
        f"Quality checklist:\n"
        + "\n".join(f"- {c}" for c in checklist)
        + feedback_block
        + f"\n\nCurrent CSS (first 3000 chars):\n{current_css}"
        + f"\n\nCurrent settings keys present: {list(current_settings.keys())[:20]}"
        + f"\n\nCurrent homepage sections order: {current_sections}"
        + f"\n\nBrand palette: bg={pal.get('bg')} fg={pal.get('fg')} accent={pal.get('accent')}"
    )

    llm = get_llm("ecommerce", temperature=0.1)
    resp = await llm.ainvoke([
        SystemMessage(content=_FRONTEND_SYSTEM),
        HumanMessage(content=implementation_prompt),
    ])

    try:
        result = json.loads(_strip_fences(str(resp.content)))
    except Exception as exc:
        logger.warning("Frontend agent parse failed: %s", exc)
        report = (
            f"Cosmetic LLM pass failed to parse, but structural fixes applied: {'; '.join(changes_made)}"
            if changes_made else "Implementation parse failed — no changes made."
        )
        return {"frontend_report": report, "design_iterations": iterations + 1}

    # 1. Apply CSS additions
    css_additions = result.get("css_additions", "").strip()
    if css_additions and len(css_additions) > 20:
        agent_log(f"Applying {len(css_additions)} chars additional CSS...", "action")
        # Append to existing custom CSS
        existing_css = await _read_asset(theme_id, "assets/custom-alpha.css")
        if isinstance(existing_css, str) and existing_css.strip():
            combined = existing_css.rstrip() + "\n\n/* Frontend agent pass " + str(iterations + 1) + " */\n" + css_additions
        else:
            combined = css_additions
        ok = await add_custom_css(combined)
        if ok:
            changes_made.append(f"CSS additions applied ({len(css_additions)} chars)")
            agent_log("✓ CSS additions applied", "success")

    # 2. Apply settings updates
    settings_updates = result.get("settings_updates", {})
    if settings_updates:
        try:
            settings_data = await _read_asset(theme_id, "config/settings_data.json")
            if isinstance(settings_data, dict):
                current = _resolve_current_settings(settings_data)
                # Confirmed real bug: despite the prompt's example showing only
                # flat scalars (button_border_radius_primary, card_corner_radius),
                # the LLM sometimes emits nested color_scheme-shaped dicts with
                # hallucinated key names (colors_solid_button_labels, "button-label"
                # with hyphens, etc.) that don't match this theme's real schema —
                # Shopify rejects the whole write with a 422, silently no-opping
                # every legit scalar change in the same batch. Brand colors are
                # already handled deterministically by apply_brand_colors() with
                # real key names, so this path only needs to accept scalars that
                # already exist in `current` — anything introducing a new nested
                # structure is almost certainly a hallucinated schema guess.
                safe_updates = {
                    k: v for k, v in settings_updates.items()
                    if k in current and not isinstance(v, dict)
                }
                dropped = set(settings_updates) - set(safe_updates)
                if dropped:
                    agent_log(f"Dropped unsafe/unknown settings keys: {sorted(dropped)}", "warning")
                if safe_updates:
                    agent_log(f"Applying {len(safe_updates)} theme setting updates...", "action")
                    current.update(safe_updates)
                    ok = await _write_asset(theme_id, "config/settings_data.json", settings_data)
                    if ok:
                        changes_made.append(f"Settings updated: {list(safe_updates.keys())}")
                        agent_log(f"✓ Settings updated: {list(safe_updates.keys())}", "success")
        except Exception as exc:
            logger.warning("Settings update failed: %s", exc)

    summary = result.get("changes_summary", "Frontend pass complete.")
    if changes_made:
        report = f"Pass {iterations + 1}: {summary} | Applied: {'; '.join(changes_made)}"
    else:
        report = f"Pass {iterations + 1}: No changes were necessary — {summary}"

    agent_log(f"Frontend pass complete: {summary}", "success")

    return {
        "frontend_report": report,
        "design_iterations": iterations + 1,
        "messages": [HumanMessage(content=report)],
    }
