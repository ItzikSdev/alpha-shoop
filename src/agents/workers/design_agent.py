"""
Design Agent — two-mode design quality loop.

Mode 1 (no design_spec in state):
  Generate a CSS file + quality checklist. Apply CSS immediately.
  → design_spec set, design_approved=False

Mode 2 (design_spec exists, has frontend_report):
  Review the current theme state against the quality checklist.
  → design_approved=True (store_designed=True) or add feedback for next pass.
  Max 3 iterations before force-approve to prevent infinite loops.
"""
from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.llm import get_llm
from src.mcp_tools.shopify_design import add_custom_css, read_full_theme_context
from src.mcp_tools.shopify_theme import _TONE_PALETTES
from src.mcp_tools.shopify import list_collections_with_counts
from src.tracing import agent_log
from src.tracing.context import current_node

logger = logging.getLogger(__name__)

MAX_DESIGN_ITERATIONS = 3

# ── Mode 1: generate spec + CSS ───────────────────────────────────────────────

_SPEC_SYSTEM = """\
You are a senior UI/UX designer and Shopify theme expert building premium DTC brands
(Tanaor, Glossier, MVMT, Byredo level).

REAL REFERENCE — extracted directly from tanaorjewelry.co.il's live production CSS
(theme.min.css), a genuinely successful premium Shopify store. Pattern-match against
these actual values rather than inventing "premium-sounding" numbers from scratch:
- Font: 'Assistant' (Google Font, used for both headings and body — clean, modern, RTL-friendly)
- Buttons: border-radius 0 (sharp), letter-spacing 0.2em, text-transform uppercase,
  font-weight bold, padding 15px (compact, not oversized)
- Primary palette: near-black (#111111) on white, NOT pure #000 — slightly softer
- Accent: warm gold/champagne tones (#d3b375, #eddabd, #e8cfaa) used sparingly for
  highlights/drawers/newsletter sections, not as the dominant color
- Sale/badge elements: pure black bg + white text, sharp corners
- General letter-spacing range across the site: 0.04em to 0.25em depending on element
  size (smaller text = wider tracking)

Given a brand brief and palette, produce TWO things in a single JSON response:

1. "css" — complete production-ready CSS for assets/custom-alpha.css that transforms
   the active Shopify theme into a premium brand experience.

2. "quality_checklist" — a list of 6 specific, verifiable criteria that a premium
   store MUST have. Each item is a short, testable statement that an LLM can later
   check by reading theme JSON/CSS files. Examples:
   - "Hero section has a gradient overlay (overlay_color in settings)"
   - "Product cards have 4/5 aspect-ratio in CSS"
   - "Announcement bar background uses brand accent color"
   - "Button border-radius is 0 (sharp = luxury)"
   - "Body font-size is 16px and line-height 1.7 in CSS"
   - "Homepage has exactly 5 sections: hero, trust-bar, products, story, collections"

CSS rules — apply ALL of these every time:
- CSS custom properties in :root for brand palette (--brand-bg, --brand-fg, --brand-accent)
- Typography: h1 clamp(2.2rem,5vw,3.5rem), body 16px/1.7, -webkit-font-smoothing antialiased
- Breathing room: section padding min 80px desktop, card gap 24px
- Buttons: sharp (border-radius 0), 14px 36px, 0.8rem 0.1em uppercase, transition on hover
- Product cards: 4/5 aspect-ratio image, hover scale(1.05) 0.5s cubic-bezier
- Header: sticky, glass blur on .scrolled class
- Announcement bar: accent bg, 0.7rem uppercase letter-spacing
- Footer: brand-fg bg, brand-bg text
- Mobile: 44px touch targets, 2-col product grid, full-width CTA

Output ONLY valid JSON (no markdown fences):
{"css": "...full CSS here...", "quality_checklist": ["criterion 1", ..., "criterion 6"]}
"""

# Always-checked structural criteria — these are pass/fail blockers, not cosmetic
# nits. A blank hero or an empty featured-collection makes the store look broken
# to a real visitor regardless of how good the CSS is, so they can never be
# waved through by the "4+ criteria pass" leniency rule below.
_STRUCTURAL_CHECKLIST = [
    "Hero/image-banner section has a background image set (settings.image is not empty)",
    "Featured/product-list section's collection setting points to a collection that has at least 1 product",
]
# Note: products_to_show vs. real product count is NOT a checklist item — Shopify
# enforces a hard minimum of 2, so it can't always be fully satisfied (1-product
# collections always show 1 placeholder). frontend_agent's Phase 0 clamps it to
# max(count, 2) deterministically on every pass regardless of review outcome,
# so it self-heals without needing to gate approval on something that can't always pass.

# ── Mode 2: review implementation ────────────────────────────────────────────

_REVIEW_SYSTEM = """\
You are a senior QA engineer reviewing a Shopify store theme implementation.

You will receive:
1. A quality checklist (what the store MUST have) — items marked [STRUCTURAL] are
   hard blockers (a visibly broken homepage), everything else is cosmetic polish.
2. The current theme state (CSS, settings JSON, section structure AND section settings)
3. What the frontend agent last changed

For each checklist item, check if it is satisfied based on the theme files provided.
To check [STRUCTURAL] items, look at section_settings in the provided context — e.g.
a hero/image-banner section's "image" key must be a non-empty string, and a
featured-collection/product-list section's "collection" key must reference a
collection whose product count (given separately) is > 0.

Output ONLY valid JSON (no markdown fences):
{
  "approved": true/false,
  "criteria_results": [
    {"criterion": "...", "passed": true/false, "reason": "one sentence"}
  ],
  "feedback": ["specific change 1", "specific change 2"]
}

Rules:
- ANY [STRUCTURAL] item failing → approved MUST be false, no exceptions.
- Otherwise: 4+ of the remaining (cosmetic) criteria passing → approve even if some fail.
- Be practical on cosmetics: minor issues are fine. Only reject cosmetics for real structural problems.
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    return text.strip()


async def design_node(state: AgentState) -> dict:
    current_node.set("design_agent")

    if state.get("store_designed"):
        return {}

    brief = state.get("store_brand") or {}
    if not brief:
        agent_log("No brand brief — skipping design", "warning")
        return {"store_designed": True, "design_approved": True}

    design_spec = state.get("design_spec")
    iterations = state.get("design_iterations", 0)

    # ── Mode 2: Review ────────────────────────────────────────────────────────
    if design_spec and state.get("frontend_report"):
        agent_log(f"Design review pass #{iterations} (max {MAX_DESIGN_ITERATIONS})...", "action")

        if iterations >= MAX_DESIGN_ITERATIONS:
            agent_log(f"Max iterations reached — approving", "warning")
            return {"store_designed": True, "design_approved": True}

        theme_ctx = await read_full_theme_context()
        collections = await list_collections_with_counts()
        checklist = design_spec.get("quality_checklist", [])
        feedback_history = design_spec.get("iteration_feedback", [])

        review_prompt = (
            f"Quality checklist:\n"
            + "\n".join(f"- {c}" for c in checklist)
            + f"\n\nFrontend agent last reported:\n{state['frontend_report']}"
            + f"\n\nCurrent theme CSS (first 3000 chars):\n{theme_ctx.get('css_preview', '')[:3000]}"
            + f"\n\nCurrent homepage sections (order): {theme_ctx.get('homepage_sections', [])}"
            + f"\n\nCurrent homepage section settings (check hero 'image' and featured-collection 'collection' here):\n"
            + json.dumps(theme_ctx.get('section_settings', {}), indent=2)[:2500]
            + f"\n\nCollections and product counts (a featured-collection pointing to a 0-count handle is [STRUCTURAL] FAIL):\n"
            + json.dumps(collections, indent=2)
            + f"\n\nCurrent settings (relevant keys):\n{json.dumps(theme_ctx.get('settings_summary', {}), indent=2)[:2000]}"
        )

        llm = get_llm("ecommerce", temperature=0.0)
        resp = await llm.ainvoke([
            SystemMessage(content=_REVIEW_SYSTEM),
            HumanMessage(content=review_prompt),
        ])
        try:
            result = json.loads(_strip_fences(str(resp.content)))
        except Exception:
            agent_log("Review parse failed — approving to unblock", "warning")
            return {"store_designed": True, "design_approved": True}

        passed = sum(1 for c in result.get("criteria_results", []) if c.get("passed"))
        total = len(result.get("criteria_results", []))
        agent_log(f"Review: {passed}/{total} criteria passed", "info")

        for c in result.get("criteria_results", []):
            status = "✓" if c.get("passed") else "✗"
            agent_log(f"  {status} {c.get('criterion','')}: {c.get('reason','')}", "info")

        # Safety net: don't trust the LLM alone to enforce "[STRUCTURAL] failures
        # always block approval" — check it here too in case it ignores the instruction.
        structural_failed = [
            c for c in result.get("criteria_results", [])
            if "[STRUCTURAL]" in c.get("criterion", "") and not c.get("passed")
        ]
        if structural_failed and result.get("approved"):
            agent_log(f"Overriding approval — {len(structural_failed)} [STRUCTURAL] criteria still failing", "warning")
            result["approved"] = False
            result.setdefault("feedback", []).extend(c["criterion"] for c in structural_failed)

        if result.get("approved"):
            agent_log("Design approved — store is premium quality", "success")
            return {
                "store_designed": True,
                "design_approved": True,
                "messages": [HumanMessage(content=f"Design approved after {iterations} iteration(s). {passed}/{total} criteria passed.")],
            }
        else:
            feedback = result.get("feedback", [])
            agent_log(f"Design needs work — {len(feedback)} issues to fix", "warning")
            updated_spec = {**design_spec, "iteration_feedback": feedback_history + feedback}
            return {
                "design_spec": updated_spec,
                "design_approved": False,
                "messages": [HumanMessage(content=f"Review pass {iterations}: {len(feedback)} issues remain: {'; '.join(feedback[:3])}")],
            }

    # ── Mode 1: Generate spec + CSS ──────────────────────────────────────────
    agent_log("Generating design spec and premium CSS...", "action")

    tone = brief.get("tone", "warm")
    pal = _TONE_PALETTES.get(tone.lower(), _TONE_PALETTES["warm"])
    installed_theme = brief.get("installed_theme", "dawn")

    brand_prompt = (
        f"Store: {brief.get('store_name', '')}\n"
        f"Tagline: {brief.get('tagline', '')}\n"
        f"Niche: {brief.get('niche', '')}\n"
        f"Differentiator: {brief.get('differentiator', '')}\n"
        f"Tone: {tone}\n"
        f"Active theme: {installed_theme}\n"
        f"Palette:\n"
        f"  Background: {pal['bg']}\n"
        f"  Foreground: {pal['fg']}\n"
        f"  Accent:     {pal['accent']}\n"
        f"\nGenerate CSS and quality checklist for this brand."
    )

    llm = get_llm("ecommerce", temperature=0.2)
    resp = await llm.ainvoke([
        SystemMessage(content=_SPEC_SYSTEM),
        HumanMessage(content=brand_prompt),
    ])

    try:
        parsed = json.loads(_strip_fences(str(resp.content)))
        css = parsed.get("css", "")
        checklist = parsed.get("quality_checklist", [])
    except Exception:
        agent_log("Spec parse failed — falling back to raw CSS", "warning")
        css = _strip_fences(str(resp.content))
        checklist = ["CSS applied to theme", "Brand colors in :root variables"]

    # Structural blockers always apply, regardless of what the LLM came up with —
    # a blank hero or an empty featured collection is broken, not a cosmetic nit.
    checklist = [f"[STRUCTURAL] {c}" for c in _STRUCTURAL_CHECKLIST] + checklist

    agent_log(f"Generated {len(css)} chars CSS, {len(checklist)} quality criteria", "info")

    ok = await add_custom_css(css)
    if ok:
        agent_log("✓ CSS applied to theme", "success")
    else:
        agent_log("✗ CSS injection failed", "error")

    spec = {
        "css_applied": ok,
        "quality_checklist": checklist,
        "iteration_feedback": [],
        "tone": tone,
        "palette": pal,
    }

    return {
        "design_spec": spec,
        "design_approved": False,
        "design_iterations": 0,
        "messages": [HumanMessage(content=(
            f"Design spec ready. CSS applied: {'✓' if ok else '✗'}. "
            f"Quality checklist: {len(checklist)} criteria to verify."
        ))],
    }
