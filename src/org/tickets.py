"""
Agent ticket board — a lightweight Jira for the team.

Agents OPEN tickets from the problems they hit (quality scans, a problem you raise
in chat, or a run failure), the CEO (Ava) AUTO-ASSIGNS each one to the right agent
with a priority and a **due date/time** they must meet, and the team works the
board (Todo → Doing → Blocked → Done). Stored in the shared SQLite (data/traces.db).
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone

_DB = os.environ.get("TRACES_DB_PATH", "./data/traces.db")

STATUSES = ("todo", "doing", "blocked", "done")
# priority → how long the agent has to fix it (the auto deadline).
_SLA_HOURS = {"critical": 4, "high": 24, "medium": 72, "low": 168}


@dataclass
class Ticket:
    id: str
    title: str
    description: str
    created_by: str
    assignee: str
    status: str
    priority: str
    source: str          # quality_scan | chat | run_failure
    due_at: str
    created_at: str
    updated_at: str
    store_id: str = ""
    meta: dict = field(default_factory=dict)


def init_tickets_table() -> None:
    with sqlite3.connect(_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
                created_by TEXT DEFAULT 'system', assignee TEXT DEFAULT '',
                status TEXT DEFAULT 'todo', priority TEXT DEFAULT 'medium',
                source TEXT DEFAULT 'chat', due_at TEXT DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                store_id TEXT DEFAULT '', meta TEXT DEFAULT '{}',
                dedupe_key TEXT DEFAULT ''
            )
        """)
        con.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Ava (CEO): route + prioritize + set the deadline ─────────────────────────
# Keyword → (assignee role-name, priority). First match wins; default = Ava/medium.
_ROUTING = [
    (("duplicate", "dupe", "$0", "price", "variant", "shopify", "theme", "checkout", "seo", "meta", "handle"), "Devon", "high"),
    (("image", "photo", "white background", "chinese", "logo", "favicon", "design", "font", "layout", "mobile", "copy", "hero", "nav"), "Remy", "high"),
    (("cj", "source", "sourcing", "product", "margin", "supplier", "catalog"), "Hunter", "high"),
    (("ad", "campaign", "traffic", "facebook", "instagram", "tiktok", "marketing"), "Max", "medium"),
    (("run failed", "run_failure", "build failed", "crash", "error", "broken", "down"), "Devon", "critical"),
]


def ava_assign(title: str, description: str, source: str) -> tuple[str, str, str]:
    """Ava routes the ticket: returns (assignee, priority, due_at_iso)."""
    text = f"{title} {description} {source}".lower()
    assignee, priority = "Ava", "medium"
    for keys, who, prio in _ROUTING:
        if any(k in text for k in keys):
            assignee, priority = who, prio
            break
    if source == "run_failure":
        priority = "critical"
    due = _now() + timedelta(hours=_SLA_HOURS.get(priority, 72))
    return assignee, priority, due.isoformat()


def open_ticket(title: str, description: str = "", source: str = "chat",
                created_by: str = "system", store_id: str = "timeforbaby",
                dedupe_key: str = "") -> Ticket | None:
    """Open a ticket — Ava auto-assigns owner + priority + deadline. If a dedupe_key
    is given and an OPEN ticket with it already exists, no duplicate is created."""
    init_tickets_table()
    key = dedupe_key or title.strip().lower()
    with sqlite3.connect(_DB) as con:
        exists = con.execute(
            "SELECT id FROM tickets WHERE dedupe_key=? AND status!='done'", (key,)
        ).fetchone()
        if exists:
            return None
    assignee, priority, due = ava_assign(title, description, source)
    now = _now().isoformat()
    t = Ticket(id="TKT-" + uuid.uuid4().hex[:8], title=title[:200], description=description,
               created_by=created_by, assignee=assignee, status="todo", priority=priority,
               source=source, due_at=due, created_at=now, updated_at=now, store_id=store_id)
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT INTO tickets (id,title,description,created_by,assignee,status,priority,source,due_at,created_at,updated_at,store_id,meta,dedupe_key)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (t.id, t.title, t.description, t.created_by, t.assignee, t.status, t.priority,
             t.source, t.due_at, t.created_at, t.updated_at, t.store_id, "{}", key),
        )
        con.commit()
    return t


def list_tickets(status: str | None = None, limit: int = 200) -> list[dict]:
    init_tickets_table()
    q = "SELECT id,title,description,created_by,assignee,status,priority,source,due_at,created_at,updated_at,store_id FROM tickets"
    args: tuple = ()
    if status:
        q += " WHERE status=?"; args = (status,)
    q += " ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_at LIMIT ?"
    args = args + (limit,)
    cols = ["id", "title", "description", "created_by", "assignee", "status", "priority", "source", "due_at", "created_at", "updated_at", "store_id"]
    with sqlite3.connect(_DB) as con:
        rows = con.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        d["overdue"] = bool(d["due_at"] and d["status"] != "done" and d["due_at"] < _now().isoformat())
        out.append(d)
    return out


def update_ticket(ticket_id: str, **fields) -> bool:
    allowed = {"status", "assignee", "priority", "due_at", "title", "description"}
    upd = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not upd:
        return False
    upd["updated_at"] = _now().isoformat()
    sets = ", ".join(f"{k}=?" for k in upd)
    with sqlite3.connect(_DB) as con:
        cur = con.execute(f"UPDATE tickets SET {sets} WHERE id=?", (*upd.values(), ticket_id))
        con.commit()
    return cur.rowcount > 0


async def scan_and_open_tickets(store_id: str = "timeforbaby") -> list[dict]:
    """Quality scan → open a ticket for each real problem found on the live store
    (duplicates, $0-priced products, bad/no-image products). Reuses the existing
    dry-run checks. Idempotent via dedupe_key. Returns the tickets opened."""
    from src.stores import get_store, _current_store
    _current_store.set(get_store(store_id))
    opened: list[Ticket] = []
    try:
        from src.mcp_tools.shopify import dedupe_products, fix_zero_prices, cleanup_bad_products
        dup = await dedupe_products(dry_run=True)
        if dup.get("duplicate_count", 0) > 0:
            t = open_ticket(f"Remove {dup['duplicate_count']} duplicate product(s)",
                            "Quality scan found duplicate products (same CJ item listed more than once).",
                            source="quality_scan", created_by="Devon", store_id=store_id, dedupe_key="scan:duplicates")
            if t: opened.append(t)
        zero = await fix_zero_prices(dry_run=True)
        if zero.get("repriced", 0) or zero.get("deleted", 0):
            n = zero.get("repriced", 0) + zero.get("deleted", 0)
            t = open_ticket(f"Fix {n} product(s) priced $0",
                            "Quality scan found products with $0-priced variants.",
                            source="quality_scan", created_by="Devon", store_id=store_id, dedupe_key="scan:zero_price")
            if t: opened.append(t)
        bad = await cleanup_bad_products(dry_run=True)
        if bad.get("bad_count", 0) > 0:
            t = open_ticket(f"Remove {bad['bad_count']} product(s) with no image / bad title",
                            "Quality scan found products with no image or a foreign-language title.",
                            source="quality_scan", created_by="Remy", store_id=store_id, dedupe_key="scan:bad_products")
            if t: opened.append(t)
    except Exception as exc:
        open_ticket("Quality scan failed", f"scan_and_open_tickets error: {exc}",
                    source="run_failure", created_by="system", store_id=store_id, dedupe_key="scan:error")
    return [asdict(t) for t in opened]
