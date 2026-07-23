"""
Editable cost line items — the owner can add/edit/delete rows from the Finance
page (a real spreadsheet, not a hand-edited Python list). Seeded once from the
previous hardcoded FIXED_COSTS table so nothing already tracked gets lost; after
that, this table (not the Python list) is the source of truth.
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

_DB = os.environ.get("TRACES_DB_PATH", "./data/traces.db")

_VALID_PERIODS = ("monthly", "yearly", "one_time", "variable")


@dataclass
class CostItem:
    id: str
    name: str
    category: str = ""
    amount: float = 0.0
    currency: str = "USD"
    period: str = "monthly"
    note: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def init_costs_table() -> None:
    with sqlite3.connect(_DB) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS finance_costs (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT DEFAULT '',
                amount REAL DEFAULT 0, currency TEXT DEFAULT 'USD',
                period TEXT DEFAULT 'monthly', note TEXT DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        con.commit()


def _seed_if_empty() -> None:
    """One-time migration from the old hardcoded FIXED_COSTS list, so switching
    to an editable table doesn't silently drop what was already tracked."""
    init_costs_table()
    with sqlite3.connect(_DB) as con:
        count = con.execute("SELECT COUNT(*) FROM finance_costs").fetchone()[0]
        if count > 0:
            return
        from src.mcp_tools.finance import FIXED_COSTS
        now = datetime.now(timezone.utc).isoformat()
        for c in FIXED_COSTS:
            con.execute(
                "INSERT INTO finance_costs (id,name,category,amount,currency,period,note,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), c["name"], c.get("category", ""), c.get("amount", 0.0),
                 c.get("currency", "USD"), c.get("period", "monthly"), c.get("note", ""), now, now),
            )
        con.commit()


def list_costs() -> list[CostItem]:
    _seed_if_empty()
    with sqlite3.connect(_DB) as con:
        rows = con.execute(
            "SELECT id,name,category,amount,currency,period,note,created_at,updated_at "
            "FROM finance_costs ORDER BY created_at"
        ).fetchall()
    return [CostItem(*r) for r in rows]


def create_cost(name: str, category: str = "", amount: float = 0.0, currency: str = "USD",
                period: str = "monthly", note: str = "") -> CostItem:
    init_costs_table()
    if period not in _VALID_PERIODS:
        period = "monthly"
    now = datetime.now(timezone.utc).isoformat()
    item = CostItem(id=str(uuid.uuid4()), name=name, category=category, amount=amount,
                     currency=currency, period=period, note=note, created_at=now, updated_at=now)
    with sqlite3.connect(_DB) as con:
        con.execute(
            "INSERT INTO finance_costs (id,name,category,amount,currency,period,note,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (item.id, item.name, item.category, item.amount, item.currency, item.period, item.note,
             item.created_at, item.updated_at),
        )
        con.commit()
    return item


def update_cost(cost_id: str, **fields) -> bool:
    """Edit any subset of {name, category, amount, currency, period, note} on one row."""
    allowed = {"name", "category", "amount", "currency", "period", "note"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if "period" in updates and updates["period"] not in _VALID_PERIODS:
        updates["period"] = "monthly"
    if not updates:
        return False
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with sqlite3.connect(_DB) as con:
        cur = con.execute(
            f"UPDATE finance_costs SET {set_clause} WHERE id = ?",
            (*updates.values(), cost_id),
        )
        con.commit()
    return cur.rowcount > 0


def delete_cost(cost_id: str) -> bool:
    with sqlite3.connect(_DB) as con:
        cur = con.execute("DELETE FROM finance_costs WHERE id = ?", (cost_id,))
        con.commit()
    return cur.rowcount > 0
