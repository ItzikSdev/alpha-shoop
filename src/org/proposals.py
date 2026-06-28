"""
Approval-gated action proposals — how Grace (the developer) gets FULL Shopify
access SAFELY.

Grace never calls Shopify directly. Instead she files a PROPOSAL (any Admin API
request: method + path + body). It sits 'pending' until YOU approve it; only then
does it execute with the store's full-access token. Reject and it's discarded.

So Grace effectively has full Shopify reach, but every real action passes through
your manual gate — exactly the security model the user asked for.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB = Path(os.environ.get("TRACES_DB_PATH", "./data/traces.db"))
_COLS = "id, agent, kind, payload, reason, status, result, created_at"


def init_proposals() -> None:
    with sqlite3.connect(_DB) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS org_proposals(
            id TEXT PRIMARY KEY, agent TEXT, kind TEXT, payload TEXT,
            reason TEXT, status TEXT DEFAULT 'pending', result TEXT DEFAULT '',
            created_at TEXT NOT NULL)""")


def _row(r: tuple) -> dict:
    return {"id": r[0], "agent": r[1], "kind": r[2], "payload": json.loads(r[3] or "{}"),
            "reason": r[4], "status": r[5], "result": r[6], "created_at": r[7]}


def create_proposal(agent: str, kind: str, payload: dict, reason: str) -> str:
    pid = "prop_" + uuid.uuid4().hex[:8]
    with sqlite3.connect(_DB) as c:
        c.execute(f"INSERT INTO org_proposals({_COLS}) VALUES (?,?,?,?,?,?,?,?)",
                  (pid, agent, kind, json.dumps(payload), reason, "pending", "",
                   datetime.now(timezone.utc).isoformat()))
    return pid


def list_proposals(status: str | None = None, limit: int = 50) -> list[dict]:
    q = f"SELECT {_COLS} FROM org_proposals"
    args: tuple = ()
    if status:
        q += " WHERE status = ?"
        args = (status,)
    q += " ORDER BY created_at DESC LIMIT ?"
    with sqlite3.connect(_DB) as c:
        rows = c.execute(q, args + (limit,)).fetchall()
    return [_row(r) for r in rows]


def get_proposal(pid: str) -> dict | None:
    with sqlite3.connect(_DB) as c:
        r = c.execute(f"SELECT {_COLS} FROM org_proposals WHERE id = ?", (pid,)).fetchone()
    return _row(r) if r else None


def set_proposal(pid: str, status: str, result: str = "") -> None:
    with sqlite3.connect(_DB) as c:
        c.execute("UPDATE org_proposals SET status = ?, result = ? WHERE id = ?",
                  (status, result[:2000], pid))


# ── Shopify executor (full access, runs ONLY after approval) ──────────────────

async def execute_shopify(method: str, path: str, body: dict | None) -> dict:
    """Run any Shopify Admin API call with the store's full-access token.

    Self-heals on 401 (a rotated/stale token): retries once with the freshest
    .env token, and if that also fails, escalates a one-click re-authorize link
    to the channel so the fix surfaces itself instead of silently breaking."""
    import httpx
    from src.config import get_settings
    from src.stores import list_stores
    try:
        stores = list_stores()
    except Exception:
        stores = []
    settings = get_settings()
    domain = stores[0].shopify_domain if stores else settings.shopify_store_domain
    if not domain:
        return {"error": "no store"}

    # Try the store-row token first, then the .env token — whichever is valid.
    candidates: list[str] = []
    if stores and stores[0].shopify_access_token:
        candidates.append(stores[0].shopify_access_token)
    if settings.shopify_access_token and settings.shopify_access_token not in candidates:
        candidates.append(settings.shopify_access_token)
    if not candidates:
        return {"error": "no shopify token configured"}

    # Normalize whatever path the (local-model) agent produced into a clean
    # relative path on the supported API version. Grace sometimes emits a full
    # URL, a leading "/admin/api/<ver>/", or an unsupported version — all of which
    # otherwise get double-prefixed and 404/406. Strip host + admin/api/<ver>.
    import re
    rel = re.sub(r"^https?://[^/]+/", "", path.strip())
    rel = re.sub(r"^/?admin/api/[^/]+/", "", rel).lstrip("/")
    url = f"https://{domain}/admin/api/2024-07/{rel}"
    last = None
    async with httpx.AsyncClient(timeout=25) as c:
        for token in candidates:
            r = await c.request(method.upper(), url,
                                headers={"X-Shopify-Access-Token": token},
                                json=body or None)
            last = r
            if r.status_code != 401:
                break
    if last is not None and last.status_code == 401:
        # Every available token is invalid → surface the one-click fix.
        try:
            from src.mcp_tools.shopify_auth import escalate_shopify_401
            reauth_url = await escalate_shopify_401(domain)
        except Exception:
            reauth_url = ""
        return {"status": 401, "ok": False, "error": "shopify token invalid (401)",
                "reauth_url": reauth_url, "body": last.text[:500]}
    return {"status": last.status_code, "ok": last.status_code < 400, "body": last.text[:1500]}
