"""
Live activity feed for the org's agents (any agent's tool-use loop, e.g. Sol's
`run_sol_task` in src/org/agent_loop.py) — backs the platform-app `/agents/live` page.
Stored in the shared SQLite (data/traces.db), same style as src/org/tickets.py: lazy
`CREATE TABLE IF NOT EXISTS` at the top of every write function, no lifespan wiring needed.

Generic across agents — every row is tagged with `agent_name` so a second agent's loop
(once one exists; today only Sol has a real tool-use loop, see src/org/seed.py for the
roster) can write to the SAME two tables with its own agent_name and show up alongside
Sol's runs, with no schema change.

Two tables:
  agent_runs  — one row per agent run (which agent, task, status, timestamps)
  agent_steps — one row per live event within a run (thought / tool_call / tool_result / status)
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

_DB = os.environ.get("TRACES_DB_PATH", "./data/traces.db")

RUN_STATUSES = ("running", "done", "error", "max_steps", "killed")
STEP_KINDS = ("status", "thought", "tool_call", "tool_result")


def init_agent_run_tables() -> None:
    with sqlite3.connect(_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY, agent_name TEXT NOT NULL, task TEXT NOT NULL,
                store_slug TEXT NOT NULL, ticket_id TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'running',
                started_at TEXT NOT NULL, finished_at TEXT, steps INTEGER DEFAULT 0,
                final_text TEXT DEFAULT ''
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS agent_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, seq INTEGER NOT NULL,
                kind TEXT NOT NULL, tool_name TEXT DEFAULT '', text TEXT DEFAULT '',
                args_json TEXT DEFAULT '', result_json TEXT DEFAULT '', ok INTEGER,
                ts TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_agent_steps_run ON agent_steps(run_id)")
        con.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_run(run_id: str, agent_name: str, task: str, store_slug: str, ticket_id: str | None = None) -> None:
    init_agent_run_tables()
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT INTO agent_runs (run_id, agent_name, task, store_slug, ticket_id, status, started_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (run_id, agent_name, task, store_slug, ticket_id or "", "running", _now()),
        )
        con.commit()


def finish_run(run_id: str, status: str, final_text: str = "") -> None:
    init_agent_run_tables()
    with sqlite3.connect(_DB) as con:
        con.execute(
            "UPDATE agent_runs SET status=?, finished_at=?, final_text=? WHERE run_id=?",
            (status, _now(), final_text[:4000], run_id),
        )
        con.commit()


def insert_step(run_id: str, kind: str, tool_name: str = "", text: str = "",
                 args_json: str = "", result_json: str = "", ok: bool | None = None) -> None:
    init_agent_run_tables()
    with sqlite3.connect(_DB) as con:
        seq = con.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM agent_steps WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        con.execute(
            "INSERT INTO agent_steps (run_id, seq, kind, tool_name, text, args_json, result_json, ok, ts)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, seq, kind, tool_name, text, args_json, result_json,
             None if ok is None else int(ok), _now()),
        )
        con.execute("UPDATE agent_runs SET steps = steps + 1 WHERE run_id=?", (run_id,))
        con.commit()


_RUN_COLS = ["run_id", "agent_name", "task", "store_slug", "ticket_id", "status",
             "started_at", "finished_at", "steps", "final_text"]
_STEP_COLS = ["id", "run_id", "seq", "kind", "tool_name", "text", "args_json", "result_json", "ok", "ts"]


def list_agent_runs(agent_name: str | None = None, limit: int = 50) -> list[dict]:
    init_agent_run_tables()
    q = f"SELECT {','.join(_RUN_COLS)} FROM agent_runs"
    args: tuple = ()
    if agent_name:
        q += " WHERE agent_name=?"
        args = (agent_name,)
    q += " ORDER BY started_at DESC LIMIT ?"
    args = args + (limit,)
    with sqlite3.connect(_DB) as con:
        rows = con.execute(q, args).fetchall()
    return [dict(zip(_RUN_COLS, r)) for r in rows]


def get_agent_run(run_id: str) -> dict | None:
    init_agent_run_tables()
    with sqlite3.connect(_DB) as con:
        run = con.execute(f"SELECT {','.join(_RUN_COLS)} FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
        if not run:
            return None
        steps = con.execute(
            f"SELECT {','.join(_STEP_COLS)} FROM agent_steps WHERE run_id=? ORDER BY seq", (run_id,)
        ).fetchall()
    d = dict(zip(_RUN_COLS, run))
    d["steps_detail"] = [dict(zip(_STEP_COLS, s)) for s in steps]
    return d


def steps_after(run_id: str, after_id: int) -> list[dict]:
    """New agent_steps rows for `run_id` with id > after_id, ordered by id — used by the SSE stream."""
    init_agent_run_tables()
    with sqlite3.connect(_DB) as con:
        rows = con.execute(
            f"SELECT {','.join(_STEP_COLS)} FROM agent_steps WHERE run_id=? AND id>? ORDER BY id",
            (run_id, after_id),
        ).fetchall()
    return [dict(zip(_STEP_COLS, r)) for r in rows]


def run_status(run_id: str) -> str | None:
    init_agent_run_tables()
    with sqlite3.connect(_DB) as con:
        row = con.execute("SELECT status FROM agent_runs WHERE run_id=?", (run_id,)).fetchone()
    return row[0] if row else None
