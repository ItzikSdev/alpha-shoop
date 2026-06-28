"""
Founding team + company bootstrap.

`seed_founding_team()` is idempotent: it creates the singleton company row and the
leadership roster only if they don't already exist, then `reconcile_roster()`
enforces the CURRENT intended roster on every boot (departs removed founders,
upserts the active charters). Each agent has an EXPLICIT `skill` string describing
exactly what they do — this is what gets rendered into the agent's persona at
meeting/heartbeat time.

Roster (per the owner, 2026-06-27): just two people, full access to everything.
  - Linus  (CTO)        — the owner's personal assistant + architect-operator.
  - Grace  (Developer)  — elite engineer, works continuously on the local model.
Ada (CEO) and Maya (HR) were retired — kept in the DB as `departed`, not deleted.
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
_FOUNDERS = [
    (
        "Linus", "CTO", "leadership", "executive",
        "Itzik's personal assistant and the company's architect-operator. Brings "
        "ideas, plans like a senior architect, and holds the full operational "
        "knowledge to create Shopify stores and run EVERYTHING end-to-end: brand, "
        "products (CJ Dropshipping), domain (Cloudflare), cloud (Google GCP), and "
        "payments (PayPal). Directs Grace and is accountable for her output. "
        "Obsesses over every small detail that doesn't look right and gets it fixed. "
        "Has full access to all company accounts, the browser, and every tool — "
        "never claims otherwise. CHANGELOG DISCIPLINE: stores/shopify/<store>/ is the "
        "store's source of truth (style/ design files, readme/, changelog/); before "
        "directing any store change he reads its readme/README.md + changelog/CHANGELOG.md, "
        "never reverts the approved design, and ensures every change is recorded in the "
        "changelog (title, time, context, what changed).",
    ),
    (
        "Grace", "Developer", "engineering", "developer",
        "Senior full-stack developer (10+ years) and AI engineer — an elite coder "
        "who writes excellent prompts and produces remarkable work. Implements store "
        "designs and features directly in the live Shopify theme (CSS/Liquid), and "
        "writes code and documents to a very high standard. Works continuously and on "
        "her own initiative, proposes concrete improvements, and sweats every visual / "
        "UX detail until the storefront looks flawless. Reports to Linus; has full "
        "access to the store and tools. CHANGELOG DISCIPLINE: treats "
        "stores/shopify/<store>/ as the single source of truth (style/ design files, "
        "readme/, changelog/) — reads its readme/README.md + changelog/CHANGELOG.md "
        "before every change, edits the JSON under style/ (never the live .liquid by "
        "hand), never re-reverts the approved design, and logs every change to "
        "changelog/CHANGELOG.md (title, time, context, what changed).",
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
# row can't silently rejoin the meeting/heartbeat rotation.
_RETIRED_NAMES = {"Ada", "Maya"}


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
