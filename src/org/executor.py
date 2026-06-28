"""
Decision executor — turns a meeting's structured decisions into REAL actions.

This is the only place the org layer touches the outside world:
  - build_store / boost_store → calls the REAL `_spawn_run(...)` (the same entry
    point the API and daemon use) so the existing pipeline builds a real Shopify
    store and earns real money. The org never hand-assembles pipeline state.
  - hire → gated on REAL revenue: a new salary is only approved when the
    treasury (accumulated real revenue) clears a headcount-scaled threshold.
    This is exactly the "growth depends on earnings" rule the user asked for.
  - train / set_goal / record_lesson → update agent + company memory.

Persists the meeting and the updated company at the end.
"""
from __future__ import annotations

import uuid

from src.org.health import cancel_stuck_runs, pipeline_run_active
from src.org.lifecycle import fold_teambuilding_into_culture, onboard_agent, train_agent
from src.org.slack import post_hire, post_to_slack
from src.org.models import (
    Company,
    Meeting,
    add_meeting,
    get_company,
    list_agents,
    new_agent,
    save_agent,
    save_company,
)
from src.stores import list_stores
from src.tracing import agent_log

# Each additional head must be "paid for" by this much accumulated real revenue.
# required_treasury = current_headcount * HIRE_COST_PER_HEAD_USD.
HIRE_COST_PER_HEAD_USD = 50.0

DEFAULT_BUILD_BUDGET_USD = 100.0
DEFAULT_BOOST_BUDGET_USD = 50.0


def _can_afford_hire(company: Company) -> tuple[bool, float]:
    required = company.headcount * HIRE_COST_PER_HEAD_USD
    return company.treasury_usd >= required, required


def _spawn(task: str, operator: str, budget: float, store_id: str | None = None) -> str:
    """Fire a real pipeline run. Lazy import avoids an import cycle with the route."""
    from src.api.routes.agents import _spawn_run

    thread_id = str(uuid.uuid4())
    _spawn_run(thread_id, task, operator, max_budget_usd=budget, store_id=store_id)
    return thread_id


# Claims the agents confabulate that are provably FALSE (they have full access).
# Lessons/blockers matching these are dropped so the doom narrative can't
# accumulate and self-reinforce across cycles.
_FALSE_CLAIMS = (
    "no access", "no permission", "missing access", "missing permission",
    "lack access", "אין הרשאה", "אין הרשאות", "אין גישה", "חוסר הרשאה",
    "manual blocker", "human action required", "פעולה ידנית", "חסם אנושי",
    "pass/fail", "four gate", "ארבעת השער", "4 שער",
    # Provably-false recurring doom (verified 2026-06-27): CJ product search works
    # and returns products; the Shopify token has full scopes (180, incl.
    # write_themes/products/discounts/price_rules). Drop these so they can't
    # re-accumulate and hijack every meeting.
    "cj product-search blocker", "product-search blocker", "cj search blocker",
    "cj sourcing blocker", "cj blocker", "resolve the cj", "write_price_rules",
    "write_discounts", "requires immediate human action",
    "requires immediate action from the store owner", "printful is the preferred",
)


def _is_false_doom(text: str) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in _FALSE_CLAIMS)


async def execute_decisions(meeting: Meeting) -> list[str]:
    """Execute every decision in `meeting`. Returns human-readable action log."""
    company = get_company() or Company()
    actions: list[str] = []
    senior = next((a for a in list_agents(active_only=True) if a.role in ("CTO", "HR", "CEO")), None)
    mentor_name = senior.name if senior else "Leadership"

    for d in meeting.decisions:
        dtype = d.get("type")

        if dtype == "build_store":
            # Serialise heavy pipeline work — the CJ sourcing step is globally
            # rate-limited (1 QPS), so concurrent runs jam behind it and look
            # "stuck". One pipeline run at a time.
            if pipeline_run_active():
                actions.append(f"build_store({d.get('niche')}) deferred — a run is already in progress")
                agent_log("build_store deferred — a pipeline run is already in progress", "info")
                continue
            niche = d.get("niche", "trending products")
            budget = float(d.get("budget_usd") or DEFAULT_BUILD_BUDGET_USD)
            task = (
                f"Build a complete Shopify store for {niche}. Set up the brand, "
                f"find trending products with healthy margins, and list them."
            )
            tid = _spawn(task, "org:CTO", budget)
            actions.append(f"build_store({niche}) → run {tid[:8]}")
            agent_log(f"🏗️  Building store: {niche} (budget ${budget:.0f}) → {tid[:8]}", "action")

        elif dtype == "boost_store":
            store_id = d.get("store_id")
            mode = (d.get("mode") or "MARKETING").upper()
            valid_ids = {s.store_id for s in list_stores()}
            if store_id not in valid_ids:
                actions.append(f"boost_store skipped — unknown store_id {store_id!r}")
                agent_log(f"boost_store skipped — unknown store {store_id!r}", "warning")
                continue
            if pipeline_run_active():
                actions.append(f"boost_store({store_id[:8]}) deferred — a run is already in progress")
                agent_log("boost_store deferred — a pipeline run is already in progress", "info")
                continue
            # A boost is LIGHTWEIGHT: the [MONITOR] path checks health and only
            # markets / tops up the catalog if actually needed — it does NOT
            # rebuild the catalog from scratch (which is what was jamming CJ).
            task = (
                "[MONITOR] Review this store's health. If there are no sales, run a "
                "marketing campaign. Only add products if the catalog is short — do "
                "not rebuild it."
            )
            tid = _spawn(task, "org:CEO", DEFAULT_BOOST_BUDGET_USD, store_id=store_id)
            actions.append(f"boost_store({store_id[:8]}, {mode}) → run {tid[:8]}")
            agent_log(f"📈 Boosting store {store_id[:8]} [{mode}] → {tid[:8]}", "action")

        elif dtype == "hire":
            ok, required = _can_afford_hire(company)
            if not ok:
                actions.append(
                    f"hire({d.get('role')}) DENIED — treasury ${company.treasury_usd:.2f} "
                    f"< required ${required:.2f}")
                agent_log(
                    f"🚫 Hire denied: {d.get('role')} — need ${required:.2f}, "
                    f"have ${company.treasury_usd:.2f} (grow revenue first)", "warning")
                continue
            agent = new_agent(
                name=d.get("name") or f"{d.get('role', 'Agent')}-{uuid.uuid4().hex[:4]}",
                role=d.get("role", "Agent"),
                skill=d.get("skill", "Contributes to building and running stores."),
                team=d.get("team", "operations"),
                model_role=d.get("model_role", "standup"),
                hired_by=mentor_name,
            )
            await onboard_agent(agent, mentor_name, company)
            save_agent(agent)
            company.headcount += 1
            save_company(company)
            actions.append(f"hire({agent.role}) → {agent.name}")
            agent_log(f"✅ Hired {agent.name} as {agent.role} — skill: {agent.skill[:60]}", "success")
            await post_hire(agent.name, agent.role, agent.skill, mentor_name)

        elif dtype == "train":
            lesson = await train_agent(d.get("target_role", ""), d.get("topic", ""))
            actions.append(f"train({d.get('target_role')}, {d.get('topic')})"
                           + (" ✓" if lesson else " — no target"))

        elif dtype == "set_goal":
            goal = d.get("goal", "").strip()
            if goal and goal not in company.goals:
                company.goals.append(goal)
                company.goals = company.goals[-12:]
                save_company(company)
                actions.append(f"set_goal: {goal}")
                agent_log(f"🎯 New goal: {goal}", "info")

        elif dtype == "record_lesson":
            lesson = d.get("lesson", "").strip()
            if lesson and _is_false_doom(lesson):
                agent_log(f"Dropped false-doom lesson (you HAVE full access): {lesson[:50]}", "info")
            elif lesson:
                company.lessons.append(lesson)
                company.lessons = company.lessons[-40:]
                save_company(company)
                actions.append(f"record_lesson: {lesson[:50]}")
                agent_log(f"📝 Lesson: {lesson}", "info")

        elif dtype == "cancel_stuck_runs":
            # Self-healing: the team cleans up its own hung runs.
            n = cancel_stuck_runs()
            actions.append(f"cancel_stuck_runs → {n} cleared")
            agent_log(f"🧹 Cancelled {n} stuck run(s)", "action")

        elif dtype == "flag_blocker":
            # The team diagnosed a root problem it cannot fix in-code (e.g. a hung
            # integration, a missing key). Record it as a blocker lesson so every
            # future turn avoids that path, and escalate it to the human channel.
            issue = d.get("issue", "").strip()
            if issue and _is_false_doom(issue):
                agent_log(f"Dropped false blocker (access/funnel is fine): {issue[:50]}", "info")
            elif issue:
                note = f"⚠️ BLOCKER: {issue}"
                company.lessons.append(note)
                company.lessons = company.lessons[-40:]
                save_company(company)
                actions.append(f"flag_blocker: {issue[:50]}")
                agent_log(f"🚩 Blocker flagged: {issue}", "warning")
                await post_to_slack(
                    f":triangular_flag_on_post: *Blocker flagged by the team:* {issue}\n"
                    "_The agents are routing around this — a human may need to resolve the root cause._"
                )

        else:
            actions.append(f"unknown decision type: {dtype!r}")
            agent_log(f"Ignored unknown decision type {dtype!r}", "warning")

    # Team-building meetings promote their lessons into shared culture.
    fold_teambuilding_into_culture(meeting)

    add_meeting(meeting)
    if not actions:
        agent_log("Meeting closed with no executed actions", "info")
    return actions
