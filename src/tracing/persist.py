"""SQLite persistence for run traces — survives container restarts."""
from __future__ import annotations
import logging
import sqlite3
from pathlib import Path

from .store import LLMCallTrace, LogEntry, RunTrace, TraceStore

DB_PATH = Path("/app/data/traces.db")
logger = logging.getLogger(__name__)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            thread_id  TEXT PRIMARY KEY,
            task       TEXT NOT NULL,
            operator   TEXT NOT NULL,
            status     TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id  TEXT NOT NULL,
            ts         TEXT NOT NULL,
            node       TEXT NOT NULL,
            msg        TEXT NOT NULL,
            level      TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS llm_calls (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id          TEXT NOT NULL,
            call_order         INTEGER NOT NULL,
            node               TEXT NOT NULL,
            model              TEXT NOT NULL,
            system_prompt      TEXT,
            user_prompt        TEXT,
            response           TEXT,
            input_tokens       INTEGER DEFAULT 0,
            output_tokens      INTEGER DEFAULT 0,
            cache_read_tokens  INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            duration_ms        REAL DEFAULT 0,
            timestamp          TEXT NOT NULL,
            error              TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_logs_thread ON logs(thread_id);
        CREATE INDEX IF NOT EXISTS idx_calls_thread ON llm_calls(thread_id);
        """)


def save_all(store: TraceStore) -> None:
    """Checkpoint all in-memory runs to SQLite (upsert, only new entries)."""
    runs = store.list_runs()
    if not runs:
        return
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.execute("PRAGMA journal_mode=WAL")
            for run in runs:
                con.execute(
                    "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)",
                    (run.thread_id, run.task, run.operator,
                     run.status, run.started_at, run.finished_at),
                )
                # Only insert rows that don't exist yet (count-based offset)
                existing_logs = con.execute(
                    "SELECT COUNT(*) FROM logs WHERE thread_id=?", (run.thread_id,)
                ).fetchone()[0]
                for entry in run.logs[existing_logs:]:
                    con.execute(
                        "INSERT INTO logs (thread_id,ts,node,msg,level) VALUES (?,?,?,?,?)",
                        (run.thread_id, entry.ts, entry.node, entry.msg, entry.level),
                    )
                existing_calls = con.execute(
                    "SELECT COUNT(*) FROM llm_calls WHERE thread_id=?", (run.thread_id,)
                ).fetchone()[0]
                for call in run.llm_calls[existing_calls:]:
                    con.execute("""
                        INSERT INTO llm_calls
                        (thread_id,call_order,node,model,system_prompt,user_prompt,response,
                         input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,
                         duration_ms,timestamp,error)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        run.thread_id, call.id, call.node, call.model,
                        call.system_prompt, call.user_prompt, call.response,
                        call.input_tokens, call.output_tokens,
                        call.cache_read_tokens, call.cache_write_tokens,
                        call.duration_ms, call.timestamp, call.error,
                    ))
    except Exception as exc:
        logger.warning("Checkpoint failed: %s", exc)


def load_all(store: TraceStore) -> int:
    """Load all persisted runs from SQLite into the in-memory TraceStore."""
    if not DB_PATH.exists():
        return 0
    loaded = 0
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.row_factory = sqlite3.Row
            for row in con.execute("SELECT * FROM runs ORDER BY started_at").fetchall():
                run = RunTrace(
                    thread_id=row["thread_id"],
                    task=row["task"],
                    operator=row["operator"],
                    status=row["status"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                )
                for lr in con.execute(
                    "SELECT ts,node,msg,level FROM logs WHERE thread_id=? ORDER BY id",
                    (row["thread_id"],),
                ).fetchall():
                    run.logs.append(LogEntry(**dict(lr)))

                for cr in con.execute(
                    "SELECT * FROM llm_calls WHERE thread_id=? ORDER BY id",
                    (row["thread_id"],),
                ).fetchall():
                    d = dict(cr)
                    call = LLMCallTrace(
                        id=d["call_order"],
                        node=d["node"], model=d["model"],
                        system_prompt=d["system_prompt"] or "",
                        user_prompt=d["user_prompt"] or "",
                        response=d["response"] or "",
                        input_tokens=d["input_tokens"],
                        output_tokens=d["output_tokens"],
                        cache_read_tokens=d["cache_read_tokens"],
                        cache_write_tokens=d["cache_write_tokens"],
                        duration_ms=d["duration_ms"],
                        timestamp=d["timestamp"],
                        error=d["error"],
                    )
                    run.llm_calls.append(call)
                    run._call_counter = max(run._call_counter, d["call_order"])

                store._runs[row["thread_id"]] = run
                loaded += 1
    except Exception as exc:
        logger.warning("Load from DB failed: %s", exc)
    return loaded
