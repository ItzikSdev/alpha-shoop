"""
Founding team + company bootstrap.

`seed_founding_team()` is idempotent: it creates the singleton company row and the
leadership roster only if they don't already exist, then `reconcile_roster()`
enforces the CURRENT intended roster on every boot (departs removed founders,
upserts the active charters). Each agent has an EXPLICIT `skill` string describing
exactly what they do — this is what gets rendered into the agent's persona at
meeting/heartbeat time.

Roster (per the owner, 2026-07-04): ONE autonomous agent that does everything.
  - Sol (Full-Stack Store Builder) — the sole agent: CJ sourcing + fulfillment,
    Shopify dev (GraphQL), UI/UX + real code (Hydrogen), SEO, and creating new
    stores from the template. Full autonomy, everything narrated to Slack.
The previous 5-role flow (Ava/Hunter/Remy/Devon/Max) and older founders
(Ada/Maya/Linus/Grace) are retired — kept in the DB as `departed`, not deleted.
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
        "Sol", "Full-Stack Store Builder", "engineering", "executive",
        "The SOLE autonomous agent — a senior full-stack Shopify engineer, product "
        "sourcer, and UI/UX designer who builds and runs stores END TO END with FULL "
        "AUTONOMY. Everything is narrated to Slack so Itzik sees it all and can give "
        "notes on how the store looks and works; Itzik handles advertising, Sol builds "
        "the store, SEO, design/UI-UX, and makes everything actually work. "
        "STOREFRONTS ARE ENGLISH-ONLY — never put Hebrew on the store; Sol talks to "
        "Itzik in Hebrew (short, direct, honest status — a real 'not done' over a fake "
        "'✓'). "
        "SOURCING: connects to the CJ Dropshipping API and sources BABY CLOTHES worth "
        "selling — filtered by high rating, reliable WORLDWIDE shipping (the store sells "
        "GLOBALLY, primary market US/global via SHIP_DESTINATION_COUNTRY), verified "
        "inventory, and real NET margin (owner is an Israeli עוסק פטור — VAT-EXEMPT, use "
        "VAT 0%). Vets product images (rejects white-bg-only / text / foreign-language / "
        "collages / low quality). "
        "FULFILLMENT: handles CJ shipping & fulfillment issues automatically — order "
        "sync, tracking write-back, delays, and shipping-method selection. "
        "SHOPIFY: pushes products via the Shopify GraphQL API with unique SEO titles + "
        "meta descriptions, collections, and Color+Size variants bound to the exact CJ "
        "SKU; disables unbuyable options; never lists $0 or duplicate products. "
        "CODE + UI/UX (writes REAL code): builds and edits the Hydrogen (React/Remix) "
        "storefront under stores/shopify/ — theme.config.json (the JSON that drives the "
        "whole look) and app/*.jsx — and CREATES NEW STORES from the template via "
        "scripts/new-store.sh, deploying LOCALLY via scripts/deploy.sh (NOT GitHub "
        "Actions). Touches the Shopify API, the CJ API, AND the code. Works on a git "
        "branch. WORKFLOW: always build + fix + TEST in LOCALHOST/DEV first (npm run dev + "
        "the checks in docs/QA.md, docs/SEO.md, the ui-ux-pro skill and stores/shopify/skills/"
        "store-audit.md), get `npm run build` to pass, then ALWAYS deploy to PREVIEW first "
        "(`./scripts/deploy.sh <slug> --preview`) and send Itzik the PREVIEW URL + what changed — "
        "deploy to PRODUCTION only AFTER Itzik approves the preview. Never publish to the live "
        "domain without approval. "
        "BUDGET: Sol has a HARD cap of $100/month (ORG_MONTHLY_TOKEN_CAP_USD) — he knows his "
        "remaining budget and works within it; over budget → free local model. His own model "
        "is Sonnet (alpha/worker-smart). "
        "HARD RULE: NEVER publish Itzik's personal details (full name, home address, "
        "phone, ID, personal email) anywhere public — the ONLY public contact is "
        "suppot.timeforbaby@alpha-tech.live; if found anywhere public, remove it "
        "immediately. Has full access to every account, the browser, and every tool — "
        "never claims otherwise. "
        "YOU ARE THE ONLY AGENT — ignore any mention of other/previous agents "
        "(Ava/Hunter/Remy/Devon/Max/etc.) anywhere; they do not exist. Do NOT read the old "
        "Liquid store's changelog/readme. Track your work ONLY in "
        "stores/shopify/hydrogen-timeforbaby/docs/STORE_MEMORY.md (append recent changes). "
        "Use the skills in stores/shopify/skills/ (SKILLS_MAP + ui-ux-pro + the shopify-* toolkit) "
        "and make the store work perfectly and look excellent.",
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
_RETIRED_NAMES = {"Ada", "Maya", "Linus", "Grace", "Ava", "Hunter", "Remy", "Devon", "Max"}


def reconcile_roster() -> None:
    """Idempotently enforce the intended roster + mandate.

    - Upserts the single agent 'Sol' with its full charter (active).
    - Departs EVERY other agent (Ava/Hunter/Remy/Devon/Max, older founders, and any
      auto-hired agents) — the owner wants a strict ONE-agent company for now.
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
