"""
Monthly Anthropic token budget — the hard cap + live visibility the agents use
to self-regulate spending.

The user funds Claude tokens personally and set a HARD cap of $100/month. This
module sums month-to-date Claude cost from the trace store (every LLM call
records input/output tokens + model) and exposes:
  - budget_status()  → {spent, cap, remaining, near, over} for the agents to SEE
                        in their prompts and decide accordingly.
  - over_budget()    → when True, callers route to the FREE local Ollama model
                        so the company keeps running without exceeding the cap.

Depends only on src.tracing (NOT on src.llm or src.org) so src/llm/client.py can
import it for auto-fallback without an import cycle.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from src.tracing import trace_store

# Hard monthly cap (USD). Override with ORG_MONTHLY_TOKEN_CAP_USD.
MONTHLY_CAP_USD = float(os.environ.get("ORG_MONTHLY_TOKEN_CAP_USD", "100"))

# Claude pricing, USD per 1M tokens (input, output). Approximate published tiers
# — verify against current Anthropic pricing; tune via env if needed. Local
# Ollama is free ($0).
_PRICING = {
    "sonnet": (3.0, 15.0),   # claude-sonnet-4-6  (alpha/worker-smart, executive)
    "haiku": (1.0, 5.0),     # claude-haiku-4-5   (alpha/worker-fast)
}


def _price_for(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    if "haiku" in m or "worker-fast" in m:
        return _PRICING["haiku"]
    if "ollama" in m or "local" in m:
        return (0.0, 0.0)  # local model is free
    return _PRICING["sonnet"]  # sonnet / unknown → conservative


def _cost_since(predicate) -> float:
    total = 0.0
    for r in trace_store.list_runs():
        try:
            d = datetime.fromisoformat(r.started_at)
        except Exception:
            continue
        if not predicate(d):
            continue
        for c in r.llm_calls:
            pin, pout = _price_for(c.model)
            total += c.input_tokens / 1e6 * pin + c.output_tokens / 1e6 * pout
    return round(total, 4)


def monthly_claude_cost() -> float:
    """USD spent on Claude tokens so far this calendar month (UTC)."""
    now = datetime.now(timezone.utc)
    return _cost_since(lambda d: d.year == now.year and d.month == now.month)


def today_claude_cost() -> float:
    """USD spent on Claude tokens so far today (UTC)."""
    now = datetime.now(timezone.utc)
    return _cost_since(lambda d: d.date() == now.date())


# Spread the monthly cap across the month so it isn't blown in one day.
DAILY_CAP_USD = round(MONTHLY_CAP_USD / 30.0, 2)


def budget_status() -> dict:
    spent = monthly_claude_cost()
    remaining = max(MONTHLY_CAP_USD - spent, 0.0)
    return {
        "spent_usd": round(spent, 2),
        "cap_usd": MONTHLY_CAP_USD,
        "remaining_usd": round(remaining, 2),
        "near": spent >= MONTHLY_CAP_USD * 0.9,  # 90% — start conserving
        "over": spent >= MONTHLY_CAP_USD,
    }


def over_budget() -> bool:
    """True once EITHER the month's cap OR today's daily allowance is reached —
    callers then route to the free local model. The daily cap spreads the budget
    so it's never blown all at once."""
    return monthly_claude_cost() >= MONTHLY_CAP_USD or today_claude_cost() >= DAILY_CAP_USD


def budget_line() -> str:
    """One-line, agent-readable budget status for prompts."""
    s = budget_status()
    today = today_claude_cost()
    flag = ""
    if s["over"] or today >= DAILY_CAP_USD:
        flag = " — CAP REACHED, only free/local actions now"
    elif s["near"] or today >= DAILY_CAP_USD * 0.9:
        flag = " — running low, conserve Claude calls"
    return (f"Claude budget: today ${today:.2f}/${DAILY_CAP_USD:.2f} daily · "
            f"month ${s['spent_usd']}/${s['cap_usd']:.0f}{flag}.")
