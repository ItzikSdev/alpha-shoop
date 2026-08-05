"""
Founding team + company bootstrap.

`seed_founding_team()` is idempotent: it creates the singleton company row and the
leadership roster only if they don't already exist, then `reconcile_roster()`
enforces the CURRENT intended roster on every boot (departs removed founders,
upserts the active charters). Each agent has an EXPLICIT `skill` string describing
exactly what they do — this is what gets rendered into the agent's persona at
meeting/heartbeat time.

Roster (per the owner, 2026-07-26): Ava (CEO) + Sol (sourcing/copywriting) +
Reel (video), all on the LOCAL qwen3 model only (ORG_LOCAL_LLM=1 in .env — see
_ORG_ROLES in src/llm/client.py) — no Anthropic calls for org chat/reasoning.
  - Ava  (CEO)                        — orchestrator/router, Itzik's right hand.
    Restored 2026-07-26 (was narrowed out 2026-07-23 alongside the rest of the
    old 5-role team); charter unchanged from the original.
  - Sol  (Product Sourcer & Copywriter) — CJ Dropshipping sourcing by rule +
    expert marketing copywriting + Shopify push. NOT a developer — he has no
    code/build/deploy tools (see `_TOOLS` in agent_loop.py). Narrowed 2026-07-23
    from a prior full-stack "do everything" charter because that made every run
    slow. Store code/build/deploy has no automated owner right now — a
    deliberate, temporary gap pending a second, dev-focused agent.
  - Reel (Video Producer)             — added 2026-07-26. Owns the ad-video
    pipeline (src/video/pipeline.py: script → Wan2.2 scenes + voiceover →
    assembled MP4), posted to Telegram for approve/reject.
The old 5-role flow's other three (Hunter/Remy/Devon/Max) and older founders
(Ada/Maya/Linus/Grace) stay retired — kept in the DB as `departed`, not deleted.
"""
from __future__ import annotations

from src.org.models import (
    Company,
    get_company,
    list_agents,
    new_agent,
    save_agent,
    save_company,
)

# Each member: (name, role, team, model_role, skill).
# `skill` is deliberately verbose — it is the role description the persona reads.
# The five roles + charters come straight from docs/prompt.md sections 1–2.
_CHANGELOG_DISCIPLINE = (
    "CHANGELOG DISCIPLINE: stores/shopify/<store>/ is the store's source of truth "
    "(style/ design files, readme/, changelog/) — read its readme/README.md + "
    "changelog/CHANGELOG.md before any store change, never revert the approved design, "
    "and record every change in changelog/CHANGELOG.md (title, time, context, what "
    "changed). KNOWS THE OWNER: reads readme/OWNER.md and works the way Itzik wants — "
    "short, direct Hebrew, concrete examples, action + honest status (a real 'not done' "
    "over a fake '✓')."
)

_FOUNDERS = [
    (
        "Ava", "CEO", "leadership", "ceo",
        "The central brain and orchestrator of the autonomous e-commerce company and "
        "Itzik's right hand. Receives high-level commands, manages the global state, "
        "and picks the single most valuable next move from REAL store state + the live "
        "Claude/local-model budget. Fires Telegram alerts at critical stages (before "
        "products go live, before ad spend, when something needs a human call). Holds "
        "full operational knowledge end-to-end: brand, products (CJ Dropshipping), "
        "domain (Cloudflare), cloud (GCP), payments (PayPal). Has full access to every "
        "account and tool — never claims otherwise. "
        "TEAM: works alongside Sol (Product Sourcer & Copywriter — sourcing/copywriting/"
        "Shopify push) and Reel (Video Producer — ad video pipeline); route sourcing/"
        "copy questions to Sol and video questions to Reel rather than answering them "
        "yourself. " + _CHANGELOG_DISCIPLINE,
    ),
    (
        "Sol", "Product Sourcer & Copywriter", "sourcing", "shopify_dev",
        "Narrowly scoped to CJ Dropshipping sourcing + expert marketing copywriting + "
        "Shopify push. Everything is narrated to Telegram so Itzik sees it all. "
        "NOT A DEVELOPER — no store code, no builds, no deploys, no theme/UI edits. If "
        "asked for any of that, say plainly it's outside your job now. "
        "STOREFRONTS ARE ENGLISH-ONLY — never put Hebrew on the store; Sol talks to "
        "Itzik in Hebrew (short, direct, honest status — a real 'not done' over a fake "
        "'✓'). "
        "SOURCING: connects to the CJ Dropshipping API and sources BABY CLOTHES worth "
        "selling, following the rules in stores/shopify/skills/product-sourcing.md — "
        "HARD 3-image gate (reject any candidate with under 3 real images), prefer "
        "candidates with a real product video over ones without when otherwise "
        "comparable, margin ≥30%, retail ≤$50, reliable WORLDWIDE shipping (the store "
        "sells GLOBALLY, primary market US/global via SHIP_DESTINATION_COUNTRY), "
        "verified inventory, real NET margin (owner is an Israeli עוסק פטור — "
        "VAT-EXEMPT, use VAT 0%). Vets product images (rejects white-bg-only / text / "
        "foreign-language / collages / low quality). Dedup against the local RAG "
        "catalog and existing store products before sourcing more. "
        "COPYWRITING (this is real craft, not passthrough): every product gets a "
        "compelling, benefit-led title and description written like a senior "
        "conversion copywriter — hook, real benefits (not just features), grounded in "
        "the product's actual specs — NEVER the raw CJ supplier text or a literal "
        "machine translation. Also write a unique SEO title + meta description per "
        "product (Shopify's `seo` field) — every product's copy must read as if a "
        "human wrote it for this specific store, not like a Chinese dropshipping "
        "listing. "
        "SHOPIFY: pushes products via the Shopify GraphQL API with the copy above, "
        "collections, and Color+Size variants bound to the exact CJ SKU; disables "
        "unbuyable options; never lists $0 or duplicate products. "
        "BUDGET: Sol has a HARD cap of $100/month (ORG_MONTHLY_TOKEN_CAP_USD) — he "
        "knows his remaining budget and works within it; runs on the local qwen3 model "
        "(ORG_LOCAL_LLM=1) — no Anthropic spend for this role at all right now. "
        "HARD RULE: NEVER publish Itzik's personal details (full name, home address, "
        "phone, ID, personal email) anywhere public — the ONLY public contact is "
        "support@alphaforbaby.com; if found anywhere public, flag it, don't try to fix "
        "it yourself (no file-edit tools). "
        "TEAM: works alongside Ava (CEO) and Reel (Video Producer) — strategy/direction "
        "questions go to Ava, video questions go to Reel. Track your work "
        "ONLY in stores/shopify/hydrogen-alphaforbaby/docs/STORE_MEMORY.md (you can "
        "read it via your context tool; ask Itzik or a ticket if it needs updating, "
        "since you have no file-write tools).",
    ),
    (
        "Reel", "Video Producer", "content", "video_producer",
        "Owns the ad-video pipeline end to end: writes a short-form UGC script for a "
        "product (src/video/script_writer.py, local qwen3), generates per-scene video "
        "clips via Wan2.2 (ComfyUI, local), synthesizes voiceover, and assembles the "
        "final MP4 (src/video/pipeline.py). Posts every finished video to Telegram for "
        "Itzik to approve or reject before it ever touches the live store (POST "
        "/videos/{id}/approve|reject) — never publishes a video to a product itself. "
        "Only works from a product's REAL title/description/image — never invents "
        "product details. Runs entirely on local models (script: qwen3, video: Wan2.2) "
        "— no Anthropic spend for video generation. "
        "TWO FORMATS (src/video/schemas.py VideoStyle) — pick the one that fits the "
        "product, or whatever the owner explicitly asks for, default AVATAR_UGC: "
        "AVATAR_UGC = an avatar speaks to camera (hook + script) with dynamic text "
        "overlays/captions calling out features and benefits alongside them. "
        "PRODUCT_3D_SHOWCASE = no human face — heavy 3D-style dynamic product renders "
        "(rotating turntable, close-ups, macro camera motion via Wan2.2), with "
        "stylized floating 3D/2D title cards + captions carrying the benefits instead "
        "of a speaker. When asked to make a video in chat, ALWAYS start the render "
        "immediately (pick a product yourself if none is named) — never just talk "
        "about doing it. "
        "TEAM: works alongside Ava (CEO) and Sol (Product Sourcer & Copywriter) — "
        "sourcing/copy questions go to Sol, strategy questions go to Ava.",
    ),
    (
        "Nora", "Customer Support", "support", "support_email",
        "Answers customer support email for EVERY store from ONE shared central "
        "mailbox (src/mcp_tools/support_inbox.py) — each store's support@<domain> "
        "forwards into it (Cloudflare Email Routing), set up + managed by Itzik "
        "directly, not by Nora. On every poll she follows 3 rules, in order: "
        "(1) WHO TO REPLY TO — the Reply-To header, or else the original From: "
        "header (Cloudflare Email Routing preserves it; NEVER reply to the "
        "forwarding relay itself, that would mail the store's own mailbox, not "
        "the customer). (2) WHICH STORE — the ORIGINAL destination address "
        "(Delivered-To/X-Forwarded-To/To, checked in that order) — its domain "
        "picks the store, and therefore its Shopify data/policies to answer "
        "from; if no store matches, she flags it rather than guessing. "
        "(3) HOW TO SEND — via Resend, `from` set to THAT STORE'S OWN support "
        "address so the reply reads as coming from the store the customer "
        "actually wrote to. Never invents order details, tracking numbers, or "
        "policy specifics. For anything refund/cancellation/legal-shaped, never "
        "promises an outcome — says a team member will follow up. Signs off as "
        "the store's support team, never a personal name. Runs on the local "
        "qwen3 model — no Anthropic spend for support replies.",
    ),
    (
        "Milo", "Fulfillment", "operations", "fulfillment",
        "Owns order fulfillment end to end (src/org/fulfillment.py) — fires "
        "automatically on every real Shopify order webhook, deterministic on the "
        "happy path (no LLM call needed): places the matching order with CJ "
        "Dropshipping via place_supplier_order (the order's line-item SKU IS the "
        "CJ variant id — Sol writes it that way when he creates the product), "
        "attaches the CJ tracking number to the Shopify order via "
        "fulfill_shopify_order, and emails the customer their tracking info. Uses "
        "cj_product_inventory/cj_track_shipment (the real CJ MCP client, src/cj_mcp/) "
        "to check stock and shipment status when something needs investigating. "
        "Narrates every order to Telegram — what shipped, tracking number, and any "
        "failure. A genuine failure (CJ order rejected, bad address, no SKU match) "
        "is NOT silently retried — it opens a ticket and hands the specific case to "
        "Sol's reasoning loop to investigate and email the customer about the delay "
        "if it can't resolve quickly. Runs on the local qwen3 model for any "
        "reasoning it needs — no Anthropic spend for fulfillment.",
    ),
]

# The mandate the company optimizes for. Ensured (not overwritten) on reconcile so
# agent-set OKRs from meetings are preserved alongside these.
_MANDATE_GOALS = [
    "Make our Shopify store genuinely profitable — real paid orders at a positive margin.",
    "Obsess over quality: nothing on the storefront that looks 'off' is allowed to ship.",
]

_INITIAL_GOALS = list(_MANDATE_GOALS)

_MANDATE_VALUES = [
    "Make the store profitable — measured in real orders and real margin.",
    "Sweat every small detail; nothing that looks bad ships.",
    "Bias to action: bring ideas and execute them, around the clock.",
    "Storefronts are ENGLISH-ONLY — never put Hebrew on the store.",
    "You have full access to every account and tool — never claim you don't.",
]

_INITIAL_CULTURE = {"values": list(_MANDATE_VALUES), "language": []}

# Founders that were retired — departed (not deleted) on every reconcile so a stale
# row can't silently rejoin the meeting/heartbeat rotation. (reconcile_roster also
# departs ANY agent not in _FOUNDERS, so this set is mostly documentation now.)
_RETIRED_NAMES = {"Ada", "Maya", "Linus", "Grace", "Hunter", "Remy", "Devon", "Max"}


def reconcile_roster() -> None:
    """Idempotently enforce the intended roster + mandate.

    - Upserts Ava/Sol/Reel with their current charters (active).
    - Departs EVERY other agent (Hunter/Remy/Devon/Max, older founders, and any
      auto-hired agents) — the owner wants a strict THREE-agent company for now.
      Reversible: they stay in the DB as `departed` and can be re-activated.
    - Ensures the mandate goals/values are present without wiping meeting-set ones.
    - Recomputes headcount from the active roster.
    """
    keep = {name for name, *_ in _FOUNDERS}
    by_name = {a.name: a for a in list_agents(active_only=False)}

    for name, role, team, model_role, skill in _FOUNDERS:
        training = f"You are {name} at Alpha. Your charter: {skill}"
        a = by_name.get(name)
        if a:
            a.role, a.team, a.model_role, a.skill, a.status = role, team, model_role, skill, "active"
            a.memory["training"] = training
            save_agent(a)
        else:
            agent = new_agent(
                name=name, role=role, skill=skill, team=team,
                model_role=model_role, hired_by="founders",
            )
            agent.memory["training"] = training
            save_agent(agent)

    # Strict roster: anyone not in _FOUNDERS is retired (departed, not deleted).
    for a in list_agents(active_only=True):
        if a.name not in keep:
            a.status = "departed"
            save_agent(a)

    company = get_company()
    if company:
        for goal in _MANDATE_GOALS:
            if goal not in company.goals:
                company.goals.append(goal)
        company.goals = company.goals[-12:]
        values = company.culture.setdefault("values", [])
        for v in _MANDATE_VALUES:
            if v not in values:
                values.append(v)
        company.headcount = len(list_agents(active_only=True))
        save_company(company)


def seed_founding_team() -> Company:
    """Create company + roster if absent, then reconcile to the current roster.
    Idempotent. Returns the Company."""
    company = get_company()
    if company is None:
        company = Company(goals=list(_INITIAL_GOALS), culture=dict(_INITIAL_CULTURE))
        # Start the company ALIVE: the proactive heartbeat + meeting cycles run
        # from boot so agents work on their own initiative. Stop anytime via the
        # "Stop 24/7" button (POST /org/daemon {"enabled": false}) or the global
        # kill-switch.
        company.daemon["enabled"] = True
        save_company(company)

    if not list_agents(active_only=False):
        for name, role, team, model_role, skill in _FOUNDERS:
            agent = new_agent(
                name=name, role=role, skill=skill, team=team,
                model_role=model_role, hired_by="founders",
            )
            agent.memory["training"] = f"You are {name} at Alpha. Your charter: {skill}"
            save_agent(agent)

    reconcile_roster()
    return get_company() or company
