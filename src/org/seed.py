"""
Founding team + company bootstrap.

`seed_founding_team()` is idempotent: it creates the initial leadership (CEO,
CTO, HR) and the singleton company row only if they don't already exist. Each
founder has an EXPLICIT `skill` string describing exactly what their role does
in the company — this is what the user asked for ("each employee has a skill
written explicitly stating their role") and what gets rendered into the agent's
persona at meeting time.
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

# Each founder: (name, role, team, model_role, skill).
# `skill` is deliberately verbose — it is the role description the persona reads.
_FOUNDERS = [
    (
        "Ada", "CEO", "leadership", "executive",
        "Sets company strategy and OKRs. Decides which stores to build and when "
        "to grow headcount. Balances spending against REAL Shopify revenue — never "
        "grows faster than the money allows. Chairs strategy meetings.",
    ),
    (
        "Linus", "CTO", "leadership", "executive",
        "Owns how the company builds stores through the agent pipeline. Translates "
        "strategy into concrete build/boost decisions (niches, budgets, marketing). "
        "Trains and onboards newly hired technical agents (writes their first "
        "training memo and upgrades their skills over time).",
    ),
    (
        "Maya", "HR", "people", "executive",
        "Recruits new agents ONLY when revenue justifies another salary. For every "
        "hire, writes a precise role title + explicit skill description. Runs "
        "onboarding, team-building, and keeps the company culture/values coherent "
        "as the team grows.",
    ),
]

_INITIAL_GOALS = [
    "Launch the first store and reach its first paid order.",
    "Reach $50+ weekly revenue so the company can afford its first new hire.",
]

_INITIAL_CULTURE = {
    "values": [
        "Spend only what real revenue earns.",
        "Every decision is measured against its real result.",
        "Teach the next agent what you learned.",
    ],
    "language": [],
}


def seed_founding_team() -> Company:
    """Create founders + company if absent. Idempotent. Returns the Company."""
    company = get_company()
    if company is None:
        company = Company(goals=list(_INITIAL_GOALS), culture=dict(_INITIAL_CULTURE))
        # Start the company ALIVE: the proactive heartbeat + meeting cycles run
        # from boot so agents work on their own initiative. Stop anytime via the
        # "Stop 24/7" button (POST /org/daemon {"enabled": false}) or the global
        # kill-switch.
        company.daemon["enabled"] = True
        save_company(company)

    existing = list_agents(active_only=False)
    if not existing:
        for name, role, team, model_role, skill in _FOUNDERS:
            agent = new_agent(
                name=name, role=role, skill=skill, team=team,
                model_role=model_role, hired_by="founders",
            )
            agent.memory["training"] = (
                f"You are a founder of Alpha. As {role}, your charter is: {skill}"
            )
            save_agent(agent)
        # Headcount reflects the founders we just created.
        company.headcount = len(_FOUNDERS)
        save_company(company)

    return company
