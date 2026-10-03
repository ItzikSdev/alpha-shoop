"""
"Needs you" — everything waiting on a human decision, in one list.

Mirrors the inbox in the AI-office reference: each item says WHAT, FROM which
agent, WHY, and offers Approve / Hold / Send back / Instruct. Sources (all real,
nothing synthesized):
  - social drafts (pending | held)          src/social_mcp/queue.py
  - Shopify action proposals (pending)      src/org/proposals.py
  - capability gaps (missing key / tool)    src/org/capabilities.py
  - blockers agents flagged                 company.lessons "⚠️ BLOCKER:" entries
"""
from __future__ import annotations

from src.org.capabilities import all_capabilities


def build_inbox() -> list[dict]:
    items: list[dict] = []

    from src.social_mcp import queue
    for d in queue.list_drafts():
        if d["status"] not in ("pending", "held"):
            continue
        items.append({
            "id": f"social:{d['id']}", "kind": "social_draft", "decide": True,
            "title": f"{d['platform'].title()} {d['kind']}: {d['message'][:90]}",
            "agent": d.get("author") or "Lia", "context": d["platform"], "status": d["status"],
            "created_at": d["created_at"], "summary": d.get("rationale") or "",
            "body": d["message"], "media_url": d.get("media_url") or "", "link": d.get("link") or "",
            "error": d.get("error"),
        })

    try:
        from src.org.proposals import list_proposals
        for p in list_proposals(status="pending"):
            pl = p.get("payload") or {}
            items.append({
                "id": f"proposal:{p['id']}", "kind": "proposal", "decide": True,
                "title": f"Shopify {pl.get('method', '')} {pl.get('path', '')}".strip(),
                "agent": p.get("agent") or "", "context": "shopify", "status": "pending",
                "created_at": p.get("created_at"), "summary": p.get("reason") or "",
                "body": str(pl.get("body") or "")[:600], "media_url": "", "link": "", "error": None,
            })
    except Exception:  # noqa: BLE001 — a missing table must not hide the rest
        pass

    for c in all_capabilities():
        for nc in c["not_connected"]:
            items.append({
                "id": f"cap:{c['agent']}:{nc['tool']}", "kind": "connection", "decide": False,
                "title": f"{c['agent']} can't use {nc['tool']}", "agent": c["agent"],
                "context": "connection", "status": "missing", "created_at": None,
                "summary": "Missing: " + ", ".join(nc["missing_env"]), "body": "", "media_url": "",
                "link": "", "error": None,
            })
        for m in c["missing_tools"]:
            items.append({
                "id": f"need:{c['agent']}:{m['need']}", "kind": "missing_tool", "decide": False,
                "title": f"{c['agent']} has no tool for: {m['need']}", "agent": c["agent"],
                "context": "tooling", "status": "missing", "created_at": None,
                "summary": m["why"], "body": m["fix"], "media_url": "", "link": "", "error": None,
            })

    try:
        from src.org.models import get_company
        company = get_company()
        for i, lesson in enumerate((company.lessons if company else [])[-10:]):
            if str(lesson).startswith("⚠️ BLOCKER:"):
                items.append({
                    "id": f"blocker:{i}", "kind": "blocker", "decide": False,
                    "title": str(lesson)[len("⚠️ BLOCKER:"):].strip()[:140], "agent": "team",
                    "context": "blocker", "status": "flagged", "created_at": None,
                    "summary": "An agent flagged this as something only you can unblock.",
                    "body": "", "media_url": "", "link": "", "error": None,
                })
    except Exception:  # noqa: BLE001
        pass

    order = {"social_draft": 0, "proposal": 1, "blocker": 2, "missing_tool": 3, "connection": 4}
    items.sort(key=lambda x: (order.get(x["kind"], 9), x.get("created_at") or ""))
    return items
