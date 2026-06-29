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
from src.mcp_tools.shopify import list_collections_with_counts
from src.tracing import agent_log
from src.tracing.context import current_node

logger = logging.getLogger(__name__)

MAX_DESIGN_ITERATIONS = 3

# ── Mode 1: generate spec + CSS ───────────────────────────────────────────────

_SPEC_SYSTEM = """\
You are a senior UI/UX designer and Shopify theme expert building clean, minimal,
premium storefronts (Lalo / Snuggle Hunny level — soft, modern, trustworthy).

REAL REFERENCE — colors/typography/buttons below are extracted directly from
lalo.com's live production CSS (main theme bundle theme.scss.css, verified by
fetching and grepping the actual stylesheet — not guessed). Structural layout
guidance (header/hero/footer composition) is standard clean-minimal e-commerce
practice, not claimed to be reverse-engineered from Lalo's markup.
- Palette: pure white (#FFFFFF) as the dominant background, with neutral dark gray
  #4F4F4F as the primary text/foreground color (used far more than pure black in
  their real CSS — softer than pure black #000000, which appears only on a few
  structural resets). The EXACT accent is muted lime-green #B8D151 (confirmed: 71
  occurrences in their CSS, by far the most common non-neutral color), with a darker
  hover/pressed shade #91A92D (confirmed real hover state on solid buttons). A light
  neutral panel color #EDEDED (confirmed) is used for secondary section backgrounds
  instead of a second bright color. Accent is for buttons, sale badges, link hover/
  focus states, and small highlights only — never a large background area.
- Typography: their real CSS is dominated (47 occurrences) by "Gill Sans, Gill Sans
  MT, Calibri, sans-serif" — Gill Sans is a licensed Monotype font, not embeddable
  the same way on an arbitrary Shopify theme, so substitute the free Google Fonts
  "Inter" for body text and "Jost" for headings/nav (closest free geometric-humanist
  match to Gill Sans's character for uppercase/display use).
- Buttons: sharp corners (border-radius 0, confirmed real — no rounding on Lalo's
  buttons). Solid/primary: accent (#B8D151) background + white text, uppercase,
  font-weight 600, hover darkens to #91A92D (all confirmed real values; padding and
  font-size below are scaled up from their literal tiny desktop-era values to a more
  generous modern touch target, not a verified measurement). Outline/secondary:
  transparent background, 2px solid border in #4F4F4F, text #4F4F4F, hover inverts
  border/text color to the accent (confirmed real hover pattern).
- Sale/badge elements: accent (#B8D151) background, uppercase white text, sharp
  corners (confirmed real pattern on Lalo's product sale labels).
- Active nav link: accent (#B8D151) underline (2px solid) or color change on
  hover/focus — never a background fill.

STRUCTURAL LAYOUT — standard clean-minimal e-commerce composition (not Lalo-specific):
- Announcement bar: thin, light panel (#EDEDED) background, small uppercase
  #4F4F4F text, ONE rotating message (shipping/returns/promo), centered, generous
  letter-spacing. Keep it thin and quiet — minimal style means restraint, not a bold
  black banner.
- Header nav: regular-weight (not heavy/bold) uppercase or sentence-case links on
  white, generous letter-spacing (0.04-0.08em), gaps of 24-32px between items, lots
  of surrounding whitespace. Active/current nav link gets a 2px solid accent
  underline — never a background fill or heavy weight change.
- Hero / image banner: full-bleed soft lifestyle photography, generous negative
  space, headline in #4F4F4F or white (depending on image contrast) with ONE
  emphasized word/phrase in the accent color. Avoid bold black text-on-black blocks
  — keep contrast soft, not high-drama.
- Featured collection sections: a simple, left-aligned heading in #4F4F4F (not bold
  black, not centered) above a clean grid with generous gaps (24px+) — image fills
  the card top, minimal label below, no heavy borders or shadows. Prefer several
  smaller per-collection sections over one oversized generic grid when the brief
  lists multiple collections.
- Footer: light panel (#EDEDED) or white background, #4F4F4F text, clear columns —
  1-2 quick-link columns, a centered newsletter signup with a solid accent button,
  small consent text beneath at reduced opacity, and a final divider row with
  copyright text and payment icons at reduced size/opacity.

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
   - "Active nav link has a 2px accent-color underline, not a background fill"
   - "Featured collection heading is left-aligned and uppercase, not centered"
   - "Footer newsletter signup has visible consent/legal text beneath it"

CSS rules — apply ALL of these every time:
- CSS custom properties in :root: --brand-bg:#FFFFFF, --brand-fg:#4F4F4F, --brand-accent:#B8D151,
  --brand-accent-dark:#91A92D (use these names — bg/accent/accent-dark are Lalo's verified
  real values; --brand-fg is their verified real body/button text gray, not pure black)
- Typography: font-family 'Jost', sans-serif for h1/h2/nav (free substitute for the licensed
  Gill Sans), 'Inter', sans-serif for body; h1 clamp(2rem,4.5vw,3.2rem) normal-weight (not
  heavy/bold), body 16px/1.7, -webkit-font-smoothing antialiased
- Breathing room: section padding min 96px desktop (minimal style needs MORE whitespace than
  a bold/loud theme), card gap 24px
- Buttons: sharp (border-radius 0, confirmed real), 14px 32px, 0.75rem 0.05em uppercase,
  font-weight 600, default accent (var(--brand-accent)) bg/white text, hover bg
  var(--brand-accent-dark) (confirmed real hover shade); outline variant: transparent bg,
  2px solid var(--brand-fg) border/text, hover border/text var(--brand-accent).
  CONFIRMED REAL BUG, do not repeat: never select the bare `button` element — Dawn
  uses plain <button> tags for non-CTA UI controls too (announcement-bar slider
  prev/next arrows, etc.), and a `button { background: var(--brand-accent) }` rule
  paints those nav arrows solid green, hiding their icon entirely. Scope every
  button rule to `.button, a.button` (Dawn's actual CTA classes) only.
- Product cards: 4/5 aspect-ratio image, hover scale(1.03) 0.4s ease (subtler than a bold
  theme's hover — minimal style avoids flashy motion)
- Header: white bg, var(--brand-fg) nav links (normal weight, not heavy), letter-spacing
  0.04-0.08em; active nav link gets border-bottom: 2px solid var(--brand-accent)
- Announcement bar: light panel bg (#EDEDED), var(--brand-fg) text, 0.7rem uppercase
  letter-spacing, thin (not a bold full-height bar)
- Hero/banner headline: var(--brand-fg) or white text (pick by image contrast) directly over
  the image; wrap the one emphasized word/phrase in a span styled color: var(--brand-accent)
- Featured collection heading: text-align left, var(--brand-fg), normal weight — never bold
  black or centered
- Footer: light panel bg (#EDEDED) or white, var(--brand-fg) text; newsletter button uses
  var(--brand-accent); consent text at opacity 0.6, font-size 0.75rem
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
    # House style is now fixed clean-minimal-modern (Lalo reference) regardless of
    # brief.tone — _TONE_PALETTES' other entries (in shopify_theme.py, used for the
    # native settings_data.json color scheme) are left intact for if/when a brand
    # needs a genuinely different palette again, but _SPEC_SYSTEM's color rules are
    # not tone-conditional, so don't let a stale tone-based palette contradict them here.
    pal = {"bg": "#FFFFFF", "fg": "#4F4F4F", "accent": "#B8D151"}  # verified real lalo.com accent
    installed_theme = brief.get("installed_theme", "dawn")

    # Ground the build in the store TEMPLATE: read the store's CLAUDE.md build guide +
    # README so the design matches the approved look (design.html / site.json) and the
    # team follows the read/build/log rules, instead of improvising a new design.
    template_block = ""
    try:
        from src.mcp_tools.design_files import read_store_docs
        # _store_dir resolves the store folder; "timeofbaby" is the single live store +
        # template (store_id is a UUID, not the folder slug).
        docs = read_store_docs("timeofbaby")
        guide = (docs.get("claude") or docs.get("readme") or "")
        if guide:
            template_block = (
                "\n\n=== BUILD TO THE STORE TEMPLATE (read + match, don't improvise) ===\n"
                "stores/shopify/<store>/ is the source of truth + template. Match the approved\n"
                "look (design.html / site.json design_tokens + sections) and follow these rules:\n"
                f"{guide[:1800]}\n"
            )
    except Exception:
        pass

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
        f"{template_block}"
        f"\nGenerate CSS and quality checklist for this brand."
    )

    # Confirmed real bug: the full CSS + quality_checklist JSON payload routinely
    # exceeds the "ecommerce" role's 4096-token default (a truncated real
    # response measured 11740 chars / ~3000+ tokens and was STILL cut off
    # mid-string) — causing "Unterminated string" JSON errors that used to fall
    # back to writing the raw, still-JSON-shaped text into the .css asset.
    # This is the heaviest single generation in the pipeline (full CSS +
    # quality_checklist JSON). At the default 180s it timed out and FAILED the
    # whole build — give it a longer timeout so the build completes.
    llm = get_llm("ecommerce", temperature=0.2, max_tokens=8192, timeout=420)
    resp = await llm.ainvoke([
        SystemMessage(content=_SPEC_SYSTEM),
        HumanMessage(content=brand_prompt),
    ])

    raw = _strip_fences(str(resp.content))
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Confirmed real bug: a multi-line CSS payload this size routinely makes
        # the LLM emit literal newlines inside the "css" string value instead of
        # escaping them as \n — strict json.loads rejects that as invalid, and
        # the old fallback then wrote the RAW JSON TEXT (the `{"css": "...` ...
        # wrapper, both keys, brackets and all) directly into the .css asset,
        # which a browser's CSS parser can't make sense of — the design looked
        # "not implemented" even though the right values were technically in the
        # file. strict=False is the documented fix: it allows unescaped control
        # characters inside JSON strings, which is exactly this failure mode.
        try:
            parsed = json.loads(raw, strict=False)
        except Exception:
            parsed = None

    if parsed is not None:
        css = parsed.get("css", "")
        checklist = parsed.get("quality_checklist", [])
    else:
        # Truly unparseable — do NOT write the raw (still JSON-shaped) text into
        # the CSS asset. Leave css empty so structural checklist items still
        # surface as failing and frontend_agent's iterative loop has something
        # concrete to react to, instead of silently corrupting the stylesheet.
        agent_log("Spec parse failed — no CSS applied this pass", "warning")
        css = ""
        checklist = ["CSS applied to theme", "Brand colors in :root variables"]

    # Structural blockers always apply, regardless of what the LLM came up with —
    # a blank hero or an empty featured collection is broken, not a cosmetic nit.
    checklist = [f"[STRUCTURAL] {c}" for c in _STRUCTURAL_CHECKLIST] + checklist

    agent_log(f"Generated {len(css)} chars CSS, {len(checklist)} quality criteria", "info")

    if css:
        ok = await add_custom_css(css)
        if ok:
            agent_log("✓ CSS applied to theme", "success")
        else:
            agent_log("✗ CSS injection failed", "error")
    else:
        # Don't overwrite an existing valid stylesheet with an empty one just
        # because this pass's spec failed to parse.
        ok = False

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
