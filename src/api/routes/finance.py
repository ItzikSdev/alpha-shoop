"""
Finance & operations insights for the dashboard.

  GET /finance/summary    → costs (fixed + dynamic) vs revenue → net, for the
                            money table at the top of the dashboard.
  GET /org/integrations   → what the team is connected to + status, so the
                            owner knows what to set up / re-auth.
  GET /org/messages       → the agents talking to each other (the local feed that
                            mirrors what they post to Slack).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_current_operator
from src.mcp_tools.finance import (
    costs_breakdown,
    facebook_instagram_status,
    finance_snapshot,
    integrations_status,
    max_connect_facebook_instagram,
)
from src.org.slack import read_agent_messages

router = APIRouter()


@router.get("/finance/budget", summary="Live Claude/org token budget — how many $ are left this month (the $100 cap)")
async def finance_budget() -> dict:
    """The agents' remaining org credits, live. No auth so the dashboard can poll it
    freely. `over` means the cap is hit → the team auto-falls back to the free local
    model (no overspend possible). `spent_by_agent` attributes month-to-date Claude
    cost to each role so you can see who's burning tokens."""
    from datetime import datetime, timezone
    from src.budget import (
        budget_status, today_claude_cost, claude_cost_by_node,
        DAILY_CAP_USD, MONTHLY_CAP_USD,
    )
    now = datetime.now(timezone.utc)
    status = budget_status()
    by_node = claude_cost_by_node(lambda d: d.year == now.year and d.month == now.month)
    # Collapse "agent:<role>" / node names to a clean {name: cost} map, biggest first.
    spent_by_agent = {
        (k.split(":", 1)[1] if k.startswith("agent:") else k): v["cost_usd"]
        for k, v in sorted(by_node.items(), key=lambda kv: kv[1]["cost_usd"], reverse=True)
    }
    return {
        **status,                                  # spent_usd, cap_usd, remaining_usd, near, over
        "monthly_cap_usd": MONTHLY_CAP_USD,
        "today_spent_usd": round(today_claude_cost(), 2),
        "daily_cap_usd": DAILY_CAP_USD,
        "spent_by_agent": spent_by_agent,
        "month": now.strftime("%Y-%m"),
        "at": now.isoformat(),
    }


@router.get("/finance/summary", summary="Costs (fixed + dynamic) vs revenue → net")
async def finance_summary(days: int = 30, _op: str = Depends(get_current_operator)) -> dict:
    snap = await finance_snapshot(days)
    return {
        "window_days": days,
        "costs": costs_breakdown(),          # the fixed/known cost table
        "revenue": snap["revenue"],          # real PayPal (or honest unavailable)
        "agent_cost": snap["agent_cost"],    # per-agent LLM spend (Ava/Hunter/Remy/Devon/Max)
        "ad_spend": snap["ad_spend"],
        "fixed_costs_window_usd": snap["fixed_costs_window_usd"],
        "net_usd": snap["net_usd"],
        "pending_data": snap["pending_data"],
        "at": snap["at"],
    }


@router.get("/org/integrations", summary="Connections the team uses + their status")
async def org_integrations(_op: str = Depends(get_current_operator)) -> dict:
    rows = integrations_status()
    # Enrich the Facebook & Instagram row with a REAL check against the store's
    # installed Shopify sales channels (not a flag).
    try:
        connected, detail = await facebook_instagram_status()
        for r in rows:
            if r["key"] == "facebook_instagram":
                r["connected"], r["detail"] = connected, detail
                break
    except Exception:
        pass
    return {
        "integrations": rows,
        "connected": sum(1 for r in rows if r["connected"]),
        "total": len(rows),
    }


@router.post("/org/connect/facebook", summary="Agent Max attempts the Facebook & Instagram connection (real check) and reports in Slack")
async def connect_facebook(_op: str = Depends(get_current_operator)) -> dict:
    return await max_connect_facebook_instagram()


@router.get("/org/messages", summary="Inter-agent message feed (Linus ↔ Grace etc.)")
async def org_messages(limit: int = 200, _op: str = Depends(get_current_operator)) -> dict:
    msgs = read_agent_messages(limit)
    return {"messages": msgs, "count": len(msgs)}
