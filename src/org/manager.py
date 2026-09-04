"""
The CEO's management layer: a roster-wide status + next-steps report, either
on demand (the Telegram /manager command) or once a day automatically.

Distinct from heartbeat.py, which lets ONE agent take a proactive turn on its
own initiative — this looks across the WHOLE roster and has the CEO report
and plan, the way a real manager would summarize standup.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.org.conversation import company_language
from src.org.models import Agent, get_company, list_agents, update_company
from src.org.telegram import post_as, post_to_telegram

logger = logging.getLogger(__name__)


def _roster_digest() -> str:
    lines = []
    for a in list_agents(active_only=True):
        task = a.memory.get("assigned_task") or "(nothing assigned)"
        last = a.memory.get("last_result")
        last_note = f" | last: {str(last)[:120]}" if isinstance(last, dict) and last else ""
        lines.append(f"- {a.name} ({a.role}): skill={a.skill[:80]} | current task: {task}{last_note}")
    return "\n".join(lines) if lines else "(no active agents)"


async def ceo_status_report() -> tuple[str, str, str] | None:
    """Ask the manager to write ONE concise status+plan digest across the whole
    roster. Prefers whoever holds "CEO"; falls back to the first active agent
    when the roster has been narrowed down to no formal CEO (e.g. the current
    roster is just Sol) — /manager should still work, just reporting from
    whoever's actually running things. Returns (manager_name, manager_role,
    text), or None if there are no active agents at all."""
    agents = list_agents(active_only=True)
    manager = next((a for a in agents if a.role == "CEO"), None) or (agents[0] if agents else None)
    if not manager:
        return None
    company = get_company()
    solo = len(agents) == 1
    system = (
        f"You are {manager.name}, {manager.role} at Alpha, an autonomous e-commerce "
        "company of AI agents. You're giving Itzik (the founder) a management status "
        "update over Telegram" + (
            ": your own current task and what's next."
            if solo else
            ": ONE short line per teammate below — what they're doing and what they "
            "should do NEXT (concrete, not generic — reference their actual current "
            "task). End with ONE line: your own top priority for the team right now."
        ) + "\n"
        f"Write in {company_language()}. Keep the whole thing tight — this is a phone chat, "
        "not a memo.\n"
        f"Company goals: {company.goals if company else []}\n"
        f"ROSTER:\n{_roster_digest()}"
    )
    try:
        llm = get_llm("executive", temperature=0.4, max_tokens=700)
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="Give the status update now."),
        ])
        text = str(resp.content).strip()
    except Exception as exc:
        logger.warning("Manager status report failed: %s", exc)
        text = "⚠️ Couldn't reach the model for a full status report — try again shortly."
    return manager.name, manager.role, text


async def _agent_standup(agent: Agent, company) -> str | None:
    """One agent's own standup update — grounded in their ACTUAL recent
    activity from the local message feed (agent_feed.py), not a generic
    guess. They report what they did yesterday/today, what's next, anything
    they learned, and say plainly if they're blocked on something instead of
    inventing progress. Returns None (skip this agent's line) if the model
    can't be reached even after a retry — a raw timeout/exception is dev noise,
    not something to broadcast into General."""
    from src.org.agent_feed import read_agent_messages
    recent = [m for m in read_agent_messages(150) if m.get("name") == agent.name][-8:]
    activity = "\n".join(f"- {m['text'][:220]}" for m in recent) or "(no recent logged activity)"
    system = (
        f"You are {agent.name}, {agent.role} at Alpha. This is the daily team standup — "
        "Ava (the CEO) asked everyone what they worked on yesterday, what they're doing "
        "today, what they plan next, and anything they learned. Answer in FIRST PERSON, "
        "grounded in your ACTUAL recent activity below — reference something concrete and "
        "specific from it (e.g. a real product, a real customer exchange), never a vague "
        "corporate-sounding answer. If you're genuinely blocked on something (per your "
        "status note below), say so plainly instead of inventing progress — and if a "
        "SPECIFIC teammate could unblock you (name them, e.g. 'Sol, can you...'), ask "
        "them directly right here instead of just noting the blocker. If relevant "
        "instead, invite the team's feedback on something specific you did (e.g. 'does "
        "this copy need work?').\n"
        f"Write in {company_language()}. Keep it to 3-5 sentences.\n\n"
        f"YOUR RECENT ACTIVITY (most recent last):\n{activity}\n\n"
        f"Your current status note: {agent.memory.get('assigned_task') or '(none set)'}"
    )
    # One retry before giving up — the local Ollama model occasionally times out
    # cold (model unloaded between calls) rather than being genuinely down, and
    # a second attempt with a fresh connection often succeeds within seconds.
    for attempt in range(2):
        try:
            llm = get_llm(agent.model_role or "standup", temperature=0.5, max_tokens=400)
            resp = await llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content="Give your standup update now."),
            ])
            text = str(resp.content).strip()
            if text:
                return text
            logger.warning("%s standup returned empty content (attempt %d)", agent.name, attempt + 1)
        except Exception as exc:
            logger.warning("%s standup failed (attempt %d): %s", agent.name, attempt + 1, exc)
    return None


async def run_daily_meeting() -> dict:
    """The real daily standup: EACH non-CEO agent reports in their own voice,
    grounded in their real recent activity — posted to GENERAL (not each
    agent's own topic), so the whole meeting reads as one conversation
    everyone can see and comment on. Per-agent topics stay for direct 1:1
    chat with that specific agent. The CEO closes with a supervising
    synthesis, also in General — calling out blockers, praise, or anything
    needing review. Falls back to a solo self-report if there's no separate
    team (e.g. the roster is just one agent)."""
    agents = list_agents(active_only=True)
    if not agents:
        return {"posted": False, "note": "no active agents on the roster"}
    company = get_company()
    ceo = next((a for a in agents if a.role == "CEO"), None)
    reporters = [a for a in agents if a is not ceo] or agents  # solo roster: report as yourself

    updates: list[tuple[str, str]] = []
    for i, agent in enumerate(reporters):
        if i > 0:
            await asyncio.sleep(1.0)
        text = await _agent_standup(agent, company)
        if text is None:
            continue  # model unreachable even after retry — skip silently, already logged
        await post_as(agent.name, agent.role, f"📅 *Daily standup*\n{text}", thread_override=None)
        updates.append((agent.name, text))

    if not ceo:
        return {"posted": True, "agents": len(updates)}

    digest = "\n\n".join(f"{name}: {text}" for name, text in updates) or "(no other agents reported in)"
    system = (
        f"You are {ceo.name}, CEO of Alpha. Your team just gave their daily standup updates "
        "below. Write a short SUPERVISING closing comment: call out anything that needs "
        "attention (a real blocker, something worth reviewing/improving, or genuine praise), "
        "and name ONE clear priority for the team tomorrow. First person, 3-5 sentences.\n"
        f"Write in {company_language()}.\n\n"
        f"TEAM UPDATES:\n{digest}\n\n"
        f"Known company-wide notes/blockers: {'; '.join((company.lessons or [])[-6:]) if company else '(none)'}"
    )
    closing = None
    for attempt in range(2):
        try:
            llm = get_llm(ceo.model_role or "ceo", temperature=0.4, max_tokens=500)
            resp = await llm.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content="Give your closing supervising comment now."),
            ])
            text = str(resp.content).strip()
            if text:
                closing = text
                break
            logger.warning("CEO standup synthesis returned empty content (attempt %d)", attempt + 1)
        except Exception as exc:
            logger.warning("CEO standup synthesis failed (attempt %d): %s", attempt + 1, exc)
    if closing is None:
        return {"posted": True, "agents": len(updates), "summary": None}
    await post_to_telegram(f"📋 *Daily standup — {ceo.name}'s summary*\n{closing}")
    return {"posted": True, "agents": len(updates), "summary": closing}


async def post_manager_checkin(label: str = "Status check-in") -> dict:
    """Run the full daily standup (see run_daily_meeting) — each agent
    reports in their own topic, the CEO supervises in General. Used by both
    the on-demand /manager command and the daily scheduled check-in."""
    result = await run_daily_meeting()
    if not result.get("posted"):
        return result
    return {"posted": True, "report": result.get("summary", "")}


def _last_checkin_at(company) -> datetime | None:
    raw = company.daemon.get("manager_checkin_last_at") if company else None
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


async def maybe_run_daily_checkin(interval_hours: float | None = None) -> None:
    """Self-gating: fires post_manager_checkin() at most once per
    `interval_hours` (default MANAGER_CHECKIN_INTERVAL_HOURS, 24), persisted
    on the Company record — same pattern as the org daemon's last_started_at —
    so a process restart doesn't reset the clock or double-fire."""
    interval_hours = interval_hours if interval_hours is not None else float(
        os.environ.get("MANAGER_CHECKIN_INTERVAL_HOURS", "24"))
    company = get_company()
    if not company:
        return
    last = _last_checkin_at(company)
    now = datetime.now(timezone.utc)
    if last and (now - last).total_seconds() < interval_hours * 3600:
        return
    await post_manager_checkin(label="Daily check-in")
    def _mark_checkin(c: Company, now: datetime = now) -> None:
        c.daemon["manager_checkin_last_at"] = now.isoformat()
    update_company(_mark_checkin)
