"""
Organizational state — the "living company" of agents, persisted in SQLite.

Mirrors the persistence pattern of `src/stores/__init__.py` exactly: a dataclass
per entity, an idempotent `init_org_tables()` with additive `ALTER TABLE`
migrations, and plain CRUD helpers. Stored in the same `traces.db` the rest of
the system already uses (TRACES_DB_PATH), so there is one data file to manage.

Three entities:
  - Agent   : a persistent employee persona (name, role, explicit skill, team,
              private memory/lessons, performance metrics).
  - Meeting : one company meeting — its context snapshot, the decisions it
              produced, and free-text notes (the "transcript" summary).
  - Company : singleton row holding treasury (derived from REAL Shopify
              revenue), headcount, OKRs, accumulated org-wide lessons, shared
              culture/values, and the autonomous daemon config.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

_DB_PATH = Path(os.environ.get("TRACES_DB_PATH", "./data/traces.db"))


class ConcurrencyError(Exception):
    """Raised when a save() targets a row whose version no longer matches —
    someone else wrote to it first. Callers should re-fetch and retry
    (see update_agent / update_company)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Agent:
    """A persistent employee. Rendered into an LLM persona at meeting time."""
    agent_id: str
    name: str
    role: str                          # CEO | CTO | HR | store_builder | ...
    skill: str                         # explicit free text: what this role does
    team: str = "leadership"
    model_role: str = "executive"      # get_llm() role → executive | standup
    status: str = "active"             # active | departed
    hired_at: str = field(default_factory=_now)
    hired_by: str = "founders"
    memory: dict = field(default_factory=dict)   # {"training": str, "lessons": [str], ...}
    perf: dict = field(default_factory=dict)      # {"decisions_made": int, "revenue_attributed": float}
    version: int = 0                   # optimistic-lock counter; 0 = not yet persisted

    def to_public(self) -> dict:
        """Shape consumed by the Company UI page."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "skill": self.skill,
            "team": self.team,
            "status": self.status,
            "hired_at": self.hired_at,
            "hired_by": self.hired_by,
            "lessons": self.memory.get("lessons", []),
            "training": self.memory.get("training", ""),
            "task": self.memory.get("assigned_task", ""),       # what they're working on now
            "last_result": self.memory.get("last_result", {}),  # outcome of their last action
            "perf": self.perf,
        }


@dataclass
class Meeting:
    """One company meeting and everything it produced."""
    meeting_id: str
    kind: str                          # standup | strategy | retro | teambuilding
    held_at: str = field(default_factory=_now)
    attendees: list = field(default_factory=list)   # [agent_id, ...]
    context_snapshot: dict = field(default_factory=dict)
    decisions: list = field(default_factory=list)   # [{"type": ..., ...}, ...]
    notes: str = ""                    # short discussion summary

    def to_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "kind": self.kind,
            "held_at": self.held_at,
            "attendees": self.attendees,
            "context_snapshot": self.context_snapshot,
            "decisions": self.decisions,
            "notes": self.notes,
        }


@dataclass
class Company:
    """Singleton company state."""
    company_id: str = "alpha"
    founded_at: str = field(default_factory=_now)
    headcount: int = 0
    treasury_usd: float = 0.0          # derived from REAL Shopify revenue
    goals: list = field(default_factory=list)        # OKRs, free text
    lessons: list = field(default_factory=list)      # org-wide accumulated lessons
    culture: dict = field(default_factory=dict)      # {"values": [...], "language": [...]}
    daemon: dict = field(default_factory=lambda: {
        "enabled": False,
        "interval_minutes": 60,
        "last_tick_at": None,
        "tick_count": 0,
    })
    version: int = 0                   # optimistic-lock counter; 0 = not yet persisted

    def to_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "founded_at": self.founded_at,
            "headcount": self.headcount,
            "treasury_usd": round(self.treasury_usd, 2),
            "goals": self.goals,
            "lessons": self.lessons,
            "culture": self.culture,
            "daemon": self.daemon,
        }


# ── Schema ────────────────────────────────────────────────────────────────────

def init_org_tables() -> None:
    with sqlite3.connect(_DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS org_agents (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                skill TEXT NOT NULL,
                team TEXT DEFAULT 'leadership',
                model_role TEXT DEFAULT 'executive',
                status TEXT DEFAULT 'active',
                hired_at TEXT NOT NULL,
                hired_by TEXT DEFAULT 'founders',
                memory TEXT DEFAULT '{}',
                perf TEXT DEFAULT '{}',
                version INTEGER DEFAULT 1
            )
        """)
        try:
            con.execute("ALTER TABLE org_agents ADD COLUMN version INTEGER DEFAULT 1")
        except Exception:
            pass
        con.execute("""
            CREATE TABLE IF NOT EXISTS org_meetings (
                meeting_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                held_at TEXT NOT NULL,
                attendees TEXT DEFAULT '[]',
                context_snapshot TEXT DEFAULT '{}',
                decisions TEXT DEFAULT '[]',
                notes TEXT DEFAULT ''
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS org_company (
                company_id TEXT PRIMARY KEY,
                founded_at TEXT NOT NULL,
                headcount INTEGER DEFAULT 0,
                treasury_usd REAL DEFAULT 0,
                goals TEXT DEFAULT '[]',
                lessons TEXT DEFAULT '[]',
                culture TEXT DEFAULT '{}',
                daemon TEXT DEFAULT '{}',
                version INTEGER DEFAULT 1
            )
        """)
        try:
            con.execute("ALTER TABLE org_company ADD COLUMN version INTEGER DEFAULT 1")
        except Exception:
            pass
        con.commit()


# ── Agents CRUD ───────────────────────────────────────────────────────────────

_AGENT_COLS = (
    "agent_id, name, role, skill, team, model_role, status, "
    "hired_at, hired_by, memory, perf, version"
)


def _row_to_agent(r: tuple) -> Agent:
    return Agent(
        agent_id=r[0], name=r[1], role=r[2], skill=r[3], team=r[4] or "leadership",
        model_role=r[5] or "executive", status=r[6] or "active",
        hired_at=r[7], hired_by=r[8] or "founders",
        memory=json.loads(r[9] or "{}"), perf=json.loads(r[10] or "{}"),
        version=int(r[11] or 1),
    )


def list_agents(active_only: bool = True) -> list[Agent]:
    q = f"SELECT {_AGENT_COLS} FROM org_agents"
    if active_only:
        q += " WHERE status = 'active'"
    q += " ORDER BY hired_at ASC"
    with sqlite3.connect(_DB_PATH) as con:
        rows = con.execute(q).fetchall()
    return [_row_to_agent(r) for r in rows]


def get_agent(agent_id: str) -> Agent | None:
    with sqlite3.connect(_DB_PATH) as con:
        row = con.execute(
            f"SELECT {_AGENT_COLS} FROM org_agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
    return _row_to_agent(row) if row else None


def save_agent(agent: Agent) -> None:
    """Insert (agent.version == 0 / row absent) or update with an optimistic
    version check. On update, raises ConcurrencyError if the stored version
    no longer matches `agent.version` (someone else wrote first) — the row is
    left untouched. On success, `agent.version` is bumped in place so the
    caller's object stays valid for a subsequent save."""
    with sqlite3.connect(_DB_PATH) as con:
        row = con.execute(
            "SELECT version FROM org_agents WHERE agent_id = ?", (agent.agent_id,)
        ).fetchone()
        if row is None:
            try:
                con.execute(
                    """INSERT INTO org_agents
                       (agent_id, name, role, skill, team, model_role, status,
                        hired_at, hired_by, memory, perf, version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        agent.agent_id, agent.name, agent.role, agent.skill, agent.team,
                        agent.model_role, agent.status, agent.hired_at, agent.hired_by,
                        json.dumps(agent.memory), json.dumps(agent.perf), 1,
                    ),
                )
            except sqlite3.IntegrityError as e:
                raise ConcurrencyError(
                    f"Agent {agent.agent_id} was created concurrently"
                ) from e
            agent.version = 1
        else:
            new_version = agent.version + 1
            cur = con.execute(
                """UPDATE org_agents SET
                       name = ?, role = ?, skill = ?, team = ?, model_role = ?, status = ?,
                       hired_at = ?, hired_by = ?, memory = ?, perf = ?, version = ?
                   WHERE agent_id = ? AND version = ?""",
                (
                    agent.name, agent.role, agent.skill, agent.team, agent.model_role,
                    agent.status, agent.hired_at, agent.hired_by,
                    json.dumps(agent.memory), json.dumps(agent.perf), new_version,
                    agent.agent_id, agent.version,
                ),
            )
            if cur.rowcount == 0:
                raise ConcurrencyError(
                    f"Agent {agent.agent_id} was modified concurrently "
                    f"(expected version {agent.version}, stored version is {row[0]})"
                )
            agent.version = new_version
        con.commit()


def new_agent(name: str, role: str, skill: str, team: str = "leadership",
              model_role: str = "executive", hired_by: str = "founders") -> Agent:
    """Factory: a fresh Agent with a generated id (not yet persisted)."""
    return Agent(
        agent_id=_new_id("agent"), name=name, role=role, skill=skill,
        team=team, model_role=model_role, hired_by=hired_by,
    )


def update_agent(agent_id: str, mutate: Callable[[Agent], None], max_retries: int = 5) -> Agent:
    """Read-modify-write an Agent safely under optimistic locking: re-fetches
    the latest row, applies `mutate` to it, and saves — retrying from a fresh
    read if a concurrent writer won the race in between."""
    for attempt in range(max_retries):
        agent = get_agent(agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        mutate(agent)
        try:
            save_agent(agent)
            return agent
        except ConcurrencyError:
            if attempt == max_retries - 1:
                raise
    raise ConcurrencyError(f"Agent {agent_id} update failed after {max_retries} retries")


# ── Meetings CRUD ─────────────────────────────────────────────────────────────

_MEETING_COLS = (
    "meeting_id, kind, held_at, attendees, context_snapshot, decisions, notes"
)


def _row_to_meeting(r: tuple) -> Meeting:
    return Meeting(
        meeting_id=r[0], kind=r[1], held_at=r[2],
        attendees=json.loads(r[3] or "[]"),
        context_snapshot=json.loads(r[4] or "{}"),
        decisions=json.loads(r[5] or "[]"),
        notes=r[6] or "",
    )


def new_meeting(kind: str) -> Meeting:
    return Meeting(meeting_id=_new_id("mtg"), kind=kind)


def add_meeting(meeting: Meeting) -> None:
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            """INSERT OR REPLACE INTO org_meetings
               (meeting_id, kind, held_at, attendees, context_snapshot, decisions, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                meeting.meeting_id, meeting.kind, meeting.held_at,
                json.dumps(meeting.attendees), json.dumps(meeting.context_snapshot),
                json.dumps(meeting.decisions), meeting.notes,
            ),
        )
        con.commit()


def list_meetings(limit: int = 50) -> list[Meeting]:
    with sqlite3.connect(_DB_PATH) as con:
        rows = con.execute(
            f"SELECT {_MEETING_COLS} FROM org_meetings ORDER BY held_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_meeting(r) for r in rows]


# ── Company (singleton) ───────────────────────────────────────────────────────

_COMPANY_COLS = (
    "company_id, founded_at, headcount, treasury_usd, goals, lessons, culture, daemon, version"
)


def _row_to_company(r: tuple) -> Company:
    c = Company(
        company_id=r[0], founded_at=r[1], headcount=int(r[2] or 0),
        treasury_usd=float(r[3] or 0),
        goals=json.loads(r[4] or "[]"), lessons=json.loads(r[5] or "[]"),
        culture=json.loads(r[6] or "{}"),
        version=int(r[8] or 1),
    )
    daemon = json.loads(r[7] or "{}")
    if daemon:
        c.daemon = {**c.daemon, **daemon}
    return c


def get_company() -> Company | None:
    with sqlite3.connect(_DB_PATH) as con:
        row = con.execute(
            f"SELECT {_COMPANY_COLS} FROM org_company WHERE company_id = 'alpha'"
        ).fetchone()
    return _row_to_company(row) if row else None


def save_company(company: Company) -> None:
    """Insert (company.version == 0 / row absent) or update with an optimistic
    version check. On update, raises ConcurrencyError if the stored version
    no longer matches `company.version` (someone else wrote first) — the row
    is left untouched. On success, `company.version` is bumped in place."""
    with sqlite3.connect(_DB_PATH) as con:
        row = con.execute(
            "SELECT version FROM org_company WHERE company_id = ?", (company.company_id,)
        ).fetchone()
        if row is None:
            try:
                con.execute(
                    """INSERT INTO org_company
                       (company_id, founded_at, headcount, treasury_usd, goals, lessons,
                        culture, daemon, version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        company.company_id, company.founded_at, company.headcount,
                        company.treasury_usd, json.dumps(company.goals),
                        json.dumps(company.lessons), json.dumps(company.culture),
                        json.dumps(company.daemon), 1,
                    ),
                )
            except sqlite3.IntegrityError as e:
                raise ConcurrencyError(
                    f"Company {company.company_id} was created concurrently"
                ) from e
            company.version = 1
        else:
            new_version = company.version + 1
            cur = con.execute(
                """UPDATE org_company SET
                       founded_at = ?, headcount = ?, treasury_usd = ?, goals = ?,
                       lessons = ?, culture = ?, daemon = ?, version = ?
                   WHERE company_id = ? AND version = ?""",
                (
                    company.founded_at, company.headcount, company.treasury_usd,
                    json.dumps(company.goals), json.dumps(company.lessons),
                    json.dumps(company.culture), json.dumps(company.daemon), new_version,
                    company.company_id, company.version,
                ),
            )
            if cur.rowcount == 0:
                raise ConcurrencyError(
                    f"Company {company.company_id} was modified concurrently "
                    f"(expected version {company.version}, stored version is {row[0]})"
                )
            company.version = new_version
        con.commit()


def update_company(mutate: Callable[[Company], None], max_retries: int = 5) -> Company:
    """Read-modify-write the singleton Company safely under optimistic
    locking: re-fetches the latest row, applies `mutate`, and saves —
    retrying from a fresh read if a concurrent writer won the race."""
    for attempt in range(max_retries):
        company = get_company() or Company()
        mutate(company)
        try:
            save_company(company)
            return company
        except ConcurrencyError:
            if attempt == max_retries - 1:
                raise
    raise ConcurrencyError(f"Company update failed after {max_retries} retries")
