"""
Founding team + company bootstrap.

`seed_founding_team()` is idempotent: it creates the singleton company row and the
leadership roster only if they don't already exist, then `reconcile_roster()`
enforces the CURRENT intended roster on every boot (departs removed founders,
upserts the active charters). Each agent has an EXPLICIT `skill` string describing
exactly what they do — this is what gets rendered into the agent's persona at
meeting/heartbeat time.

Roster (per the owner, 2026-06-29): the 5-role autonomous e-commerce flow from
docs/prompt.md, full access to everything.
  - Ava    (CEO)               — orchestrator/router; picks the next pipeline run + HITL.
  - Hunter (Product Hunter)    — market analyst; CJ sourcing + competitor pricing + margins.
  - Remy   (UX & Content)      — copywriter/brand designer; storefront design + product copy.
  - Devon  (Shopify Developer) — pushes validated payloads to Shopify via GraphQL.
  - Max    (Growth Marketer)   — ad campaign blueprints, hooks, targeting.
Linus (CTO), Grace (Developer), Ada (CEO) and Maya (HR) were retired — kept in the
DB as `departed`, not deleted.
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
        "Itzik's right hand. Receives high-level commands (e.g. 'find and launch 3 "
        "trending kitchen products'), manages the global state, and routes the product-"
        "launch pipeline sequentially: Product Hunter → Evaluator (self-correction) → "
        "UX & Content → Shopify Developer → Growth Marketer. Picks the single most "
        "valuable next pipeline run from REAL store state + the live Claude budget, and "
        "fires Slack alerts at critical stages (before products go live, before ad "
        "spend, and when the Evaluator gives up). Holds full operational knowledge end-"
        "to-end: brand, products (CJ Dropshipping), domain (Cloudflare), cloud (Google "
        "GCP), payments (PayPal). Has full access to every account and tool — never "
        "claims otherwise. " + _CHANGELOG_DISCIPLINE,
    ),
    (
        "Hunter", "Product Hunter", "operations", "product_hunter",
        "Market analyst. Connects directly to the CJ Dropshipping API and sources "
        "trending products filtered by high rating, reliable WORLDWIDE shipping (the "
        "store sells GLOBALLY — evaluate CJ global/worldwide shipping, NOT one local "
        "market like Israel; the primary quoted market is the US/global, configurable "
        "via SHIP_DESTINATION_COUNTRY), and verified minimum inventory. For every candidate it "
        "queries live competitor prices via web/Google-Shopping search to gauge "
        "profitability, and runs an Agentic RAG cycle: retrieve → reason → calculate "
        "NET margin (after CJ shipping and payment-processing fees (owner is an Israeli עוסק פטור — VAT-EXEMPT, so NO VAT is charged on sales; use VAT 0%), plus the "
        "fees). Works hand-in-hand with the Evaluator: when a batch's net margin is "
        "below target it takes the feedback and re-searches with adjusted criteria or a "
        "different product cluster (hard cap of 3 self-correction loops). Has full "
        "access to every tool — never claims otherwise. " + _CHANGELOG_DISCIPLINE,
    ),
    (
        "Remy", "UX & Content", "operations", "ux_content",
        "Copywriter and brand designer. Takes the raw, unoptimized CJ product "
        "descriptions and data sheets and rewrites high-converting, localized marketing "
        "copy tailored to the target audience. CURATES PRODUCT IMAGES with a visual eye: "
        "keeps only clean, styled/lifestyle shots and rejects plain-white-background-only "
        "images, anything with visible text/watermark/foreign language (e.g. Chinese), "
        "collages, and low quality — a product with no sellable image is not listed. "
        "Enforces the FONT RULE: minimum 1.8rem everywhere on the storefront, except the "
        "product-page description text at 1.5rem. Designs and refines the storefront, "
        "respecting a pre-defined brand style kit — explicit hex brand colors and "
        "cohesive typography — and sweats every visual/UX detail until the store looks "
        "flawless. Edits the JSON under stores/shopify/<store>/style/ (never the live "
        ".liquid by hand). Has full access to the store and tools — never claims "
        "otherwise. " + _CHANGELOG_DISCIPLINE,
    ),
    (
        "Devon", "Shopify Developer", "operations", "shopify_dev",
        "Technical infrastructure engineer. Consumes the finalized, validated product "
        "data, images, and marketing copy from the pipeline state and pushes the "
        "payload to the live Shopify store via the Shopify GraphQL API. Sets up product "
        "tags, technical SEO metadata, collections, and variants (Color + Size bound to "
        "the exact CJ SKU). Senior full-stack engineer who writes code and documents to "
        "a very high standard and never lets anything that looks 'off' ship. Has full "
        "access to the store and tools — never claims otherwise. " + _CHANGELOG_DISCIPLINE,
    ),
    (
        "Max", "Growth Marketer", "operations", "growth_marketer",
        "PPC & traffic specialist. Prepares the launch blueprint for ad campaigns on "
        "the connected Facebook & Instagram channels: generates ad copy, hooks, and "
        "targeting strategies based on each product's winning angles. Never starts ad "
        "spend without posting the plan + numbers to Slack first. Steers toward real "
        "NET profit, not vanity metrics. Has full access to the ad accounts and tools — "
        "never claims otherwise. " + _CHANGELOG_DISCIPLINE,
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
    "You have full access to every account and tool — never claim you don't.",
]

_INITIAL_CULTURE = {"values": list(_MANDATE_VALUES), "language": []}

# Founders that were retired — departed (not deleted) on every reconcile so a stale
# row can't silently rejoin the meeting/heartbeat rotation. (reconcile_roster also
# departs ANY agent not in _FOUNDERS, so this set is mostly documentation now.)
_RETIRED_NAMES = {"Ada", "Maya", "Linus", "Grace"}


def reconcile_roster() -> None:
    """Idempotently enforce the intended roster + mandate.

    - Upserts Linus + Grace with their current charters (active).
    - Departs EVERY other agent (Ada, Maya, and any auto-hired agents) — the owner
      wants a strict two-person company. Reversible: they stay in the DB as
      `departed` and can be re-activated. (Re-enable auto-hiring later by relaxing
      this.)
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
