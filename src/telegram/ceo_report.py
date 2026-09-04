"""
Ava's Daily CEO Report — a concise, ROI-focused executive report posted to
Telegram, either on a schedule (see `maybe_run_daily_report`, wired into a
background loop in src/main.py, default 21:00 Israel time) or on demand via
the /report Telegram command (src/org/telegram.py's `_handle_report`).

Strict scope, per the four things an executive actually needs: Revenue,
TikTok Ad Spend/ROAS, Bottlenecks, Executed Agent Commands. Written by the
local Qwen3 14B model (src.graph.llm.get_graph_llm — the same local-only LLM
helper built for the graph-orchestration work, reused here so this report
never touches the Anthropic budget) using Ava's executive persona, in the
company's default language (Hebrew — see src.org.conversation.company_language).

Read-only: every data source below is a query (Shopify GET via
gather_snapshot, SQLite reads of Company/agent_runs, the static/manual
integrations_status() table). The ONLY write in this whole module is the
self-gating scheduler timestamp (Company.daemon["ceo_report_last_at"]),
via the existing optimistic-locked update_company() helper — the same
bookkeeping-only pattern src.org.manager already uses for its own daily
check-in gate. Nothing here touches Shopify, the proposal queue, or any
other core business state.

TikTok ads: real spend/impressions/clicks/CTR/conversions come from Kai's
TikTok Ads MCP client (src.tiktok_mcp, a REAL MCP server we wrote ourselves —
see that package's README) once TikTok OAuth is completed. Until then, this
module surfaces the honest src.mcp_tools.finance.integrations_status()
"tiktok" row instead of fabricating spend/ROAS numbers.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage

from src.org.conversation import company_language
from src.org.models import Company, get_company, update_company
from src.org.agent_runs import list_agent_runs
from src.graph.llm import get_graph_llm

logger = logging.getLogger(__name__)


def _tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("CEO_REPORT_TZ", "Asia/Jerusalem"))


def _today_start_iso() -> str:
    """UTC ISO timestamp for local midnight today — agent_runs.started_at is
    stored in UTC, so this lets us filter "today" by local calendar day."""
    now_local = datetime.now(_tz())
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc).isoformat()


async def _tiktok_status_line() -> str:
    """Real TikTok Ads spend/CTR/conversions (last 7 days) via Kai's MCP client
    if connected, else the honest not-connected status. Never fabricates a
    number — a fetch failure or missing auth just surfaces as plain text."""
    from datetime import timedelta
    from src.mcp_tools.finance import integrations_status

    tiktok_row = next((r for r in integrations_status() if r["key"] == "tiktok"), None)
    fallback = tiktok_row["detail"] if tiktok_row else "TikTok integration status unknown."
    if not (tiktok_row and tiktok_row["connected"]):
        return fallback
    try:
        from src import tiktok_mcp
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=7)
        report = await tiktok_mcp.get_ads_report(str(start), str(end))
    except Exception as exc:
        return f"{fallback} (live fetch failed: {exc})"
    if "error" in report:
        return f"{fallback} (live fetch failed: {report['error']})"
    rows = report.get("rows", [])
    if not rows:
        return f"No TikTok Ads data returned for {start} to {end}."
    m = rows[0].get("metrics", rows[0])
    parts = [f"{label} {m[key]}" for key, label in (
        ("spend", "Spend $"), ("impressions", "Impr."), ("clicks", "Clicks"),
        ("ctr", "CTR"), ("conversion", "Conv."), ("cost_per_conversion", "CPA $"),
    ) if key in m]
    return f"Last 7 days ({start} to {end}): " + ", ".join(parts)


async def compile_ceo_report_data() -> dict:
    """Gather today's real metrics. Read-only — no writes anywhere."""
    from src.org.meeting import gather_snapshot

    snapshot = await gather_snapshot()
    company = get_company()

    tiktok_status = await _tiktok_status_line()

    bottlenecks = [l for l in (company.lessons if company else []) if "BLOCKER" in l][-6:]

    today_start = _today_start_iso()
    commands_today = [r for r in list_agent_runs(limit=200) if r["started_at"] >= today_start]

    return {
        "stores": snapshot["stores"],
        "revenue_7d_total_usd": snapshot["revenue_7d_total_usd"],
        "tiktok_status": tiktok_status,
        "bottlenecks": bottlenecks,
        "agent_commands_today": commands_today,
    }


def _build_prompt(data: dict) -> str:
    stores_lines = "\n".join(
        f"- {s['name']}: revenue 7d ${s['revenue_7d_usd']:.2f}, orders 7d {s['orders_7d']} ({s['status']})"
        for s in data["stores"]
    ) or "(no active stores)"
    bottleneck_lines = "\n".join(f"- {b}" for b in data["bottlenecks"]) or "(none flagged)"
    commands_lines = "\n".join(
        f"- {r['agent_name']}: {r['task'][:90]} [{r['status']}, {r['steps']} steps]"
        for r in data["agent_commands_today"]
    ) or "(no agent runs recorded today)"
    return (
        "You are Ava, CEO of Alpha, an autonomous e-commerce company. Write TODAY's "
        "executive report for Itzik (the founder), sent over Telegram.\n"
        f"Write in {company_language()}. Be concise and ROI-focused — this is a phone "
        "read, not a memo. Short bullet-style lines, not prose paragraphs.\n"
        "STRICT SCOPE — cover exactly these four things, nothing else:\n"
        "1. Revenue (last 7 days, per store + total)\n"
        "2. TikTok Ad Spend / ROAS\n"
        "3. Bottlenecks (only the real, currently-flagged blockers below — never invent one)\n"
        "4. Executed Agent Commands (what the team actually ran today)\n"
        "Never invent numbers. If a metric isn't available, say so plainly instead of "
        "guessing or estimating.\n\n"
        f"REVENUE — last 7 days (real Shopify data):\n{stores_lines}\n"
        f"Total: ${data['revenue_7d_total_usd']:.2f}\n\n"
        f"TIKTOK ADS — real integration status:\n{data['tiktok_status']}\n\n"
        f"BOTTLENECKS — flagged blockers:\n{bottleneck_lines}\n\n"
        f"EXECUTED AGENT COMMANDS — today:\n{commands_lines}\n"
    )


def _fallback_report(data: dict) -> str:
    """Deterministic, non-LLM report — used if the local model can't be
    reached, so the report never just fails silently (same degrade-gracefully
    convention as src.org.manager.ceo_status_report)."""
    lines = ["📊 Daily CEO Report (fallback — model unreachable)", ""]
    lines.append(f"Revenue (7d): ${data['revenue_7d_total_usd']:.2f}")
    for s in data["stores"]:
        lines.append(f"  - {s['name']}: ${s['revenue_7d_usd']:.2f} ({s['orders_7d']} orders)")
    lines.append("")
    lines.append(f"TikTok: {data['tiktok_status']}")
    lines.append("")
    lines.append("Bottlenecks:")
    lines += [f"  - {b}" for b in data["bottlenecks"]] or ["  (none)"]
    lines.append("")
    lines.append("Agent commands today:")
    lines += [
        f"  - {r['agent_name']}: {r['task'][:80]} [{r['status']}]"
        for r in data["agent_commands_today"]
    ] or ["  (none)"]
    return "\n".join(lines)


async def generate_ceo_report() -> str:
    """Compile data + ask the local Qwen3 model to write it up as Ava.
    Falls back to a deterministic formatted report if the model call fails."""
    data = await compile_ceo_report_data()
    try:
        llm = get_graph_llm(temperature=0.3, max_tokens=900)
        resp = await llm.ainvoke([
            SystemMessage(content=_build_prompt(data)),
            HumanMessage(content="Write today's report now."),
        ])
        text = str(resp.content).strip()
        if text:
            return text
        logger.warning("CEO report: LLM call returned empty content — using fallback")
    except Exception as exc:
        logger.warning("CEO report: LLM call failed (%s) — using fallback", exc)
    return _fallback_report(data)


async def post_daily_ceo_report(label: str = "Daily CEO Report") -> dict:
    """Generate + post the report to Telegram as Ava. Used by both the
    scheduled loop and the on-demand /report command."""
    from src.org.telegram import post_as
    text = await generate_ceo_report()
    ok = await post_as("Ava", "CEO", f"📊 *{label}*\n{text}")
    return {"posted": bool(ok), "report": text}


def _last_report_local_date(company: Company | None):
    raw = company.daemon.get("ceo_report_last_at") if company else None
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(_tz()).date()
    except Exception:
        return None


async def maybe_run_daily_report(hour: int | None = None) -> None:
    """Self-gating: fires post_daily_ceo_report() at most once per local
    calendar day, only once local time has reached `hour` (default
    CEO_REPORT_HOUR, 21). Persisted on Company.daemon so a process restart
    doesn't double-fire — same pattern as src.org.manager.maybe_run_daily_checkin."""
    hour = hour if hour is not None else int(os.environ.get("CEO_REPORT_HOUR", "21"))
    now_local = datetime.now(_tz())
    if now_local.hour < hour:
        return  # not time yet today
    company = get_company()
    if not company:
        return
    if _last_report_local_date(company) == now_local.date():
        return  # already ran today
    await post_daily_ceo_report(label="Daily CEO Report")
    now_utc_iso = datetime.now(timezone.utc).isoformat()
    def _mark_reported(c: Company, now_utc_iso: str = now_utc_iso) -> None:
        c.daemon["ceo_report_last_at"] = now_utc_iso
    update_company(_mark_reported)
