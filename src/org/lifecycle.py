"""
Organizational lifecycle — the three "company life" processes the user asked for:

  1. Onboarding / training  — a senior agent writes a tailored training memo for
     every new hire, and can upgrade a junior's skill over time. Agents teach
     each other.
  2. Continuous learning    — `run_retrospective()` closes the feedback loop:
     it measures the PREVIOUS meeting's decisions against the REAL revenue
     result now, writes the lesson to the company + the agents who decided, and
     bumps their performance. The lesson feeds the next meeting's prompt.
  3. Team-building / culture — folds team-building meeting outcomes into the
     shared company culture so every future meeting stays aligned.

Design choice: the retrospective is deterministic (no LLM call) — it runs every
tick, and a per-tick LLM call there would be pure token cost. Onboarding/train
use the cheap local model role ("standup") so growing the team is near-free.
"""
from __future__ import annotations

from src.llm import get_llm
from src.org.meeting import gather_snapshot
from src.org.models import (
    Agent,
    Company,
    Meeting,
    get_company,
    list_agents,
    list_meetings,
    save_agent,
    save_company,
)
from src.tracing import agent_log

_MAX_LESSONS = 40  # keep the company/agent lesson lists bounded


def _append_capped(lst: list, item, cap: int = _MAX_LESSONS) -> list:
    lst.append(item)
    return lst[-cap:]


# ── 1. Onboarding / training ──────────────────────────────────────────────────

async def onboard_agent(agent: Agent, mentor_name: str, company: Company) -> None:
    """A senior agent writes the new hire's first training memo (mutates agent)."""
    system = (
        f"You are {mentor_name}, a senior leader at Alpha (an autonomous e-commerce "
        "company). Write a SHORT onboarding memo (3-4 sentences) for a new hire so "
        "they can start contributing immediately. Be concrete and practical.\n"
        f"Company values: {company.culture.get('values', [])}\n"
        f"Current goals: {company.goals}"
    )
    user = (
        f"New hire — role: {agent.role}; team: {agent.team}.\n"
        f"Their job (skill): {agent.skill}\n"
        "Write their onboarding memo."
    )
    try:
        llm = get_llm("standup", temperature=0.5)
        from langchain_core.messages import HumanMessage, SystemMessage
        resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        memo = str(resp.content).strip()
    except Exception:
        memo = (
            f"Welcome to Alpha. As {agent.role} your job is: {agent.skill} "
            f"Live our values: {', '.join(company.culture.get('values', []))}."
        )
    agent.memory["training"] = memo
    agent.memory.setdefault("lessons", [])
    agent_log(f"🎓 Onboarded {agent.name} ({agent.role}) — mentor: {mentor_name}", "success")


async def train_agent(target_role: str, topic: str) -> str | None:
    """A senior agent trains an existing junior on a topic — upgrades their skill."""
    targets = [a for a in list_agents(active_only=True) if a.role == target_role]
    if not targets:
        agent_log(f"train: no active agent with role {target_role!r}", "warning")
        return None
    target = targets[0]
    lesson = f"Trained on '{topic}': apply it within your role."
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        llm = get_llm("standup", temperature=0.4)
        resp = await llm.ainvoke([
            SystemMessage(content=(
                "You are a senior mentor at Alpha. In ONE sentence, give a concrete, "
                "reusable skill upgrade for a teammate based on the training topic.")),
            HumanMessage(content=f"Role: {target.role}. Topic: {topic}."),
        ])
        lesson = str(resp.content).strip()[:300]
    except Exception:
        pass
    target.memory.setdefault("lessons", [])
    target.memory["lessons"] = _append_capped(target.memory["lessons"], lesson)
    save_agent(target)
    agent_log(f"🎓 {target.name} ({target.role}) trained on '{topic}'", "success")
    return lesson


# ── 2. Continuous learning (retrospective) ────────────────────────────────────

async def run_retrospective() -> str | None:
    """Measure the previous meeting's decisions against real revenue now.

    Deterministic: compares the revenue snapshot stored on the last meeting to a
    fresh one, writes a lesson to the company + the agents who attended, and
    bumps their perf. Returns the lesson (or None if there's nothing to review).
    """
    meetings = list_meetings(limit=1)
    if not meetings:
        return None
    last = meetings[0]
    prior_rev = float(last.context_snapshot.get("revenue_7d_total_usd", 0.0))

    snapshot = await gather_snapshot()
    now_rev = float(snapshot["revenue_7d_total_usd"])
    delta = round(now_rev - prior_rev, 2)

    actioned = [d.get("type") for d in last.decisions]
    verdict = "no change"
    if delta > 0:
        verdict = f"revenue up ${delta:.2f} — those moves are working"
    elif delta < 0:
        verdict = f"revenue down ${abs(delta):.2f} — reconsider that approach"

    if not actioned and delta == 0:
        return None

    lesson = (
        f"After [{', '.join(actioned) or 'no actions'}], 7-day revenue went "
        f"${prior_rev:.2f} → ${now_rev:.2f} ({verdict})."
    )

    company = get_company() or Company()
    # Treasury accrues from real revenue observed over the company's life.
    company.treasury_usd = round(company.treasury_usd + max(delta, 0.0), 2)
    company.lessons = _append_capped(company.lessons, lesson)
    save_company(company)

    # Credit/teach the agents who were in that meeting (mutual learning).
    attendee_ids = set(last.attendees)
    for a in list_agents(active_only=True):
        if a.agent_id in attendee_ids:
            a.memory.setdefault("lessons", [])
            a.memory["lessons"] = _append_capped(a.memory["lessons"], lesson)
            a.perf["decisions_reviewed"] = a.perf.get("decisions_reviewed", 0) + len(actioned)
            a.perf["revenue_attributed"] = round(
                a.perf.get("revenue_attributed", 0.0) + max(delta, 0.0), 2)
            save_agent(a)

    agent_log(f"🔁 Retrospective: {lesson}", "info")
    return lesson


# ── 3. Team-building / culture ────────────────────────────────────────────────

def fold_teambuilding_into_culture(meeting: Meeting) -> None:
    """Promote a team-building meeting's lessons into shared company culture."""
    if meeting.kind != "teambuilding":
        return
    company = get_company() or Company()
    values = company.culture.setdefault("values", [])
    for d in meeting.decisions:
        if d.get("type") in ("record_lesson", "set_goal"):
            text = d.get("lesson") or d.get("goal")
            if text and text not in values:
                values.append(text)
    company.culture["values"] = values[-12:]
    save_company(company)
    agent_log(f"🤝 Team-building folded into culture ({len(values)} values)", "success")
