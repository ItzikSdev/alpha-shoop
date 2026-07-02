"""Finance ledger — the money history of a store: revenue vs cost over time.

Mirrors the changelog skill. A `finance/LEDGER.md` under the store holds periodic
snapshots (newest on top) that the operator (Linus) reads to steer toward profit.
A snapshot aggregates, from REAL sources where connected:

  - Revenue   : real PayPal transactions (money actually received).
  - Agent cost: per-agent Claude-token spend (Grace=agent:Developer,
                Linus=agent:CTO) from the trace store — $0 while they run on the
                free local model, so this also answers "what did Grace/Linus cost".
  - Ad spend  : Google Ads (placeholder until the real GAQL API is wired).
  - COGS      : supplier cost of products (from product_mappings) — informational.
  - Net       : revenue.net - (agent_cost + ad_spend) for the connected parts.

Sources that aren't connected/authorized are reported with a `status` ("ok",
"unavailable", "not_connected") and never faked, so the ledger is honest about
what's real. As each data pipe is fixed (PayPal re-auth, real Google Ads), the same
snapshot starts showing real numbers with no other change.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Org node → employee name, so LLM cost is attributed to the person.
# Map tracing nodes → the agent persona that owns them, so Claude spend is
# attributed per employee on the Finance page. Org heartbeat sets "agent:<role>";
# the pipeline workers set their node name (see workers/*.py current_node.set).
_NODE_TO_AGENT = {
    "agent:CEO": "Ava",
    "trend_scraper": "Hunter", "evaluator": "Hunter",
    "design_agent": "Remy", "frontend_agent": "Remy",
    "store_setup": "Devon", "ecommerce_manager": "Devon",
    "marketing_agent": "Max", "fulfillment_agent": "Devon",
    # legacy (departed agents) — keep so historical cost still attributes
    "agent:Developer": "Grace", "agent:CTO": "Linus",
}

# Approximate ILS→USD (≈ 1 USD / 3.7 ILS). Tune as needed; used to normalize the
# ₪-denominated costs into a single monthly-USD total.
_ILS_USD = 0.27

# The business's KNOWN recurring/one-time costs (owner-provided). Edit here to keep
# the finance table accurate. `period`: monthly | yearly | one_time | variable.
FIXED_COSTS = [
    {"name": "Claude models (LLM API)", "category": "AI", "amount": 100.0, "currency": "USD",
     "period": "monthly", "note": "Hard cap; agents fall back to free local Ollama when reached."},
    {"name": "Claude Code", "category": "AI / Dev", "amount": 20.0, "currency": "USD",
     "period": "monthly", "note": "Developer assistant subscription."},
    {"name": "Shopify (Basic)", "category": "Platform", "amount": 39.0, "currency": "USD",
     "period": "monthly", "note": "$1/mo for the first 3 months, then $39/mo."},
    {"name": "Domain (alpha-tech.live)", "category": "Domain", "amount": 10.0, "currency": "USD",
     "period": "yearly", "note": "Approx; annual registration."},
    {"name": "Google Cloud (GCP)", "category": "Cloud / Infra", "amount": 5.0, "currency": "ILS",
     "period": "monthly", "note": "Current low usage."},
    {"name": "PayPlus — API permission", "category": "Payments", "amount": 29.90, "currency": "ILS",
     "period": "monthly", "note": "Monthly API access fee."},
    {"name": "PayPlus — account setup", "category": "Payments", "amount": 250.0, "currency": "ILS",
     "period": "one_time", "note": "One-time account opening fee."},
    {"name": "PayPlus — transaction fees", "category": "Payments", "amount": 0.0, "currency": "ILS",
     "period": "variable", "note": "Per-transaction; scales with sales volume (see PayPlus quote)."},
    {"name": "עוסק פטור — annual business fee", "category": "Business / Legal", "amount": 1800.0, "currency": "ILS",
     "period": "yearly", "note": "Israel exempt-dealer (עוסק פטור) yearly cost (~₪150/mo)."},
    {"name": "Meta Ads — budget cap", "category": "Marketing", "amount": 50.0, "currency": "ILS",
     "period": "monthly", "note": "Ad-spend CEILING: 15 ₪ already in the Meta account + up to 50 ₪ from PayPal. HARD CAP — never spend more than 50 ₪ on ads right now."},
    {"name": "TikTok Ads — budget", "category": "Marketing", "amount": 70.0, "currency": "USD",
     "period": "one_time", "note": "Ad-spend budget added to the TikTok channel (via the Shopify TikTok app)."},
]


def _to_usd(amount: float, currency: str) -> float:
    return round(amount * (_ILS_USD if currency.upper() == "ILS" else 1.0), 2)


def _monthly_usd(item: dict) -> float:
    """Normalize a cost line to recurring USD/month (one_time + variable → 0)."""
    usd = _to_usd(item["amount"], item["currency"])
    if item["period"] == "monthly":
        return usd
    if item["period"] == "yearly":
        return round(usd / 12.0, 2)
    return 0.0  # one_time / variable aren't part of the monthly run-rate


def costs_breakdown() -> dict:
    """The fixed/known business costs as a table + normalized monthly-USD run-rate."""
    items = []
    for c in FIXED_COSTS:
        items.append({**c, "amount_usd": _to_usd(c["amount"], c["currency"]),
                      "monthly_usd": _monthly_usd(c)})
    monthly = round(sum(i["monthly_usd"] for i in items), 2)
    one_time = round(sum(i["amount_usd"] for i in items if i["period"] == "one_time"), 2)
    return {"items": items, "monthly_recurring_usd": monthly, "one_time_usd": one_time,
            "ils_usd_rate": _ILS_USD}


def integrations_status() -> list[dict]:
    """What the team is connected to + whether each is configured, so the owner
    knows what to set up / re-auth. `who` lists the agent persona(s) that use each
    connection. `connected` = credentials present (not a live health check, except
    notes from known issues like the PayPal 403)."""
    from src.config import get_settings
    s = get_settings()
    store = None
    try:
        from src.stores import list_stores
        store = next((st for st in list_stores() if st.active), None)
    except Exception:
        store = None

    def row(key, name, category, who, connected, detail):
        return {"key": key, "name": name, "category": category, "who": who,
                "connected": bool(connected), "detail": detail}

    shop_ok = bool((store and store.shopify_access_token) or s.shopify_access_token)
    paypal_ok = bool(s.paypal_client_id and s.paypal_secret)
    payplus_ok = bool(store and getattr(store, "payplus_api_key", ""))
    ALL = ["Ava", "Hunter", "Remy", "Devon", "Max"]
    return [
        row("shopify", "Shopify (storefront + admin)", "Platform", ["Devon", "Remy", "Ava"],
            shop_ok, "Store admin token present." if shop_ok else "No access token — re-auth via /org/shopify-reauth."),
        row("cj", "CJ Dropshipping (sourcing + fulfillment)", "Suppliers", ["Hunter", "Devon"],
            bool(s.cj_mcp_key or s.cj_api_key), "CJ token configured." if (s.cj_mcp_key or s.cj_api_key) else "No CJ token."),
        row("serper", "Serper (competitor price / market search)", "Market data", ["Hunter"],
            bool(getattr(s, "serper_api_key", "")), "Serper key present — live competitor pricing." if getattr(s, "serper_api_key", "") else "No Serper key — competitor pricing falls back."),
        row("facebook_instagram", "Facebook & Instagram", "Marketing", ["Max"],
            False,  # enriched by the REAL Shopify channel check in the /org/integrations route
            "Checking the store's sales channels…"),
        row("paypal", "PayPal (revenue reporting)", "Payments", ["Ava"],
            paypal_ok, "Credentials valid, but the app is MISSING the 'Transaction Search' permission (403 on reporting). Enable it in developer.paypal.com → Apps → Features." if paypal_ok else "No PayPal credentials."),
        row("payplus", "PayPlus (checkout payments)", "Payments", ["Ava"],
            payplus_ok, "PayPlus API key on the store." if payplus_ok else "No PayPlus key on the active store."),
        row("cloudflare", "Cloudflare (domain / DNS)", "Infra", ["Ava"],
            bool(s.cloudflare_api_token), "Cloudflare token present." if s.cloudflare_api_token else "No Cloudflare token."),
        row("google_ads", "Google Ads (paid traffic)", "Marketing", ["Max"],
            bool(s.google_ads_developer_token and s.google_ads_customer_id),
            "Configured." if (s.google_ads_developer_token and s.google_ads_customer_id) else "Not connected — ad-spend metrics are still mocked."),
        row("gcp", "Google Cloud (GCP)", "Cloud / Infra", ["Ava"],
            bool(s.google_application_credentials), "Service-account credentials set." if s.google_application_credentials else "No GCP credentials file."),
        row("claude", "Claude via LiteLLM (the agents' brain)", "AI", ALL,
            bool(s.litellm_proxy_url), f"Proxy {s.litellm_proxy_url}; CEO + Product Hunter on Sonnet, the rest on Haiku — all fall back to free local Ollama over the budget cap."),
        row("ollama", "Ollama (free local fallback + embeddings)", "AI", ALL,
            bool(s.ollama_url), f"Local model at {s.ollama_url} — $0. Two jobs: the budget-cap fallback brain for every agent, and product/store embeddings for RAG."),
    ]


async def facebook_instagram_status() -> tuple[bool, str]:
    """REAL check of the Facebook & Instagram connection against the store.

    `connected` is True once the Facebook & Instagram SALES CHANNEL is installed on
    the Shopify store (catalog → Meta Shop sync is live). Running paid ads via the
    Meta Marketing API is a separate credential, so the detail says honestly whether
    that token is present too. Best-effort — never raises."""
    from src.config import get_settings
    try:
        from src.mcp_tools.shopify import get_sales_channels
        channels = await get_sales_channels()
    except Exception:
        channels = []
    has_channel = any(("facebook" in c.lower() or "instagram" in c.lower() or "meta" in c.lower())
                      for c in channels)
    s = get_settings()
    has_ads_token = bool(getattr(s, "meta_access_token", "") or getattr(s, "facebook_access_token", ""))

    if has_channel:
        detail = ("Facebook & Instagram sales channel is installed — product catalog syncs to the "
                  "Meta Shop. " + ("Meta Marketing API token present — Max can launch ads."
                                   if has_ads_token else
                                   "Ads via the Marketing API still need a Meta access token + ad-account id "
                                   "(Max prepares the blueprint and posts before any spend)."))
        return True, detail
    if not channels:
        return False, "Couldn't read the store's sales channels (publications scope or token) — can't confirm the channel."
    return False, ("Facebook & Instagram sales channel not found on the store "
                   f"(channels: {', '.join(channels)}). Install it in the Shopify admin.")


async def max_connect_facebook_instagram() -> dict:
    """Agent Max ATTEMPTS the Facebook & Instagram connection, then reports in Slack
    as himself. The 'attempt' is the real Shopify channel verification above (we don't
    fake a success). Returns {connected, detail}."""
    from src.org.slack import post_as_role
    connected, detail = await facebook_instagram_status()
    if connected:
        msg = (":mega: ניסיתי להתחבר ל-Facebook & Instagram — ✅ הערוץ מותקן בחנות והקטלוג מסונכרן ל-Meta Shop. "
               + ("יש טוקן Marketing API, אני יכול להריץ מודעות. " if "token present" in detail else
                  "בשביל להריץ מודעות בתשלום אני עוד צריך טוקן Meta Marketing API + ad-account id. ")
               + "אעדכן כאן לפני כל הוצאה על מודעות.")
    else:
        msg = f":mega: ניסיתי להתחבר ל-Facebook & Instagram — ⚠️ עדיין לא מחובר. {detail}"
    try:
        await post_as_role("Growth Marketer", msg)
    except Exception:
        pass
    return {"connected": connected, "detail": detail}


async def _revenue(days: int) -> dict:
    """Real money received via PayPal over the window. Honest status on failure."""
    try:
        from src.mcp_tools.paypal import get_paypal_transactions
        r = await get_paypal_transactions(min(days, 31))
        if r.get("error"):
            return {"status": "unavailable", "error": str(r["error"])[:160],
                    "gross_usd": None, "net_usd": None}
        return {"status": "ok", "count": r.get("count", 0),
                "gross_usd": r.get("gross_usd", 0.0), "net_usd": r.get("net_usd", 0.0),
                "fee_usd": r.get("fee_usd", 0.0)}
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)[:160], "gross_usd": None, "net_usd": None}


def _agent_cost(days: int) -> dict:
    """Per-agent Claude spend from the trace store over the last `days`."""
    try:
        from src.budget import claude_cost_by_node
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        by_node = claude_cost_by_node(lambda d: d >= cutoff)
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)[:160], "total_usd": 0.0, "by_agent": {}}
    by_agent: dict[str, dict] = {}
    for node, e in by_node.items():
        name = _NODE_TO_AGENT.get(node, node)
        agg = by_agent.setdefault(name, {"cost_usd": 0.0, "calls": 0, "tokens": 0})
        agg["cost_usd"] = round(agg["cost_usd"] + e["cost_usd"], 4)
        agg["calls"] += e["calls"]
        agg["tokens"] += e["tokens"]
    total = round(sum(a["cost_usd"] for a in by_agent.values()), 4)
    # No traced calls at all → either idle or running on the free local model.
    note = "" if by_agent else "no traced LLM calls (agents idle or on free local model → ~$0)"
    return {"status": "ok", "total_usd": total, "by_agent": by_agent, "note": note}


def _ad_spend(days: int) -> dict:
    """Google Ads spend. The metrics tool is still a mock, so report not_connected
    rather than fake a number."""
    return {"status": "not_connected", "spend_usd": None,
            "note": "Google Ads metrics are still mocked; wire the real GAQL API to populate."}


async def finance_snapshot(days: int = 30, store_slug: str = "timeforbaby") -> dict:
    """Aggregate revenue vs cost for the window. Returns a structured dict with a
    `status` per source and a `net_usd` computed from the connected parts only."""
    revenue = await _revenue(days)
    agents = _agent_cost(days)
    ads = _ad_spend(days)
    costs = costs_breakdown()
    # Prorate the fixed monthly run-rate to this window so net is apples-to-apples.
    fixed_window = round(costs["monthly_recurring_usd"] * days / 30.0, 2)

    net = None
    if revenue.get("net_usd") is not None:
        spend = (agents.get("total_usd") or 0.0) + (ads.get("spend_usd") or 0.0) + fixed_window
        net = round(revenue["net_usd"] - spend, 2)

    return {
        "store": store_slug,
        "window_days": days,
        "at": datetime.now(timezone.utc).isoformat(),
        "revenue": revenue,
        "agent_cost": agents,
        "ad_spend": ads,
        "fixed_costs": costs,
        "fixed_costs_window_usd": fixed_window,
        "net_usd": net,
        # Surface exactly which pipes still need fixing so it's obvious in the ledger.
        "pending_data": [k for k, v in (("revenue", revenue), ("ad_spend", ads))
                         if v.get("status") != "ok"],
    }


def _summary_line(snap: dict) -> str:
    """One-line human summary (for Linus's prompt + the ledger heading)."""
    rev = snap["revenue"]
    rev_s = f"${rev['net_usd']:.2f} net" if rev.get("net_usd") is not None else f"n/a ({rev.get('status')})"
    ag = snap["agent_cost"]
    ag_s = f"${ag.get('total_usd', 0):.2f}"
    if ag.get("by_agent"):
        ag_s += " (" + ", ".join(f"{n} ${a['cost_usd']:.2f}" for n, a in ag["by_agent"].items()) + ")"
    ad = snap["ad_spend"]
    ad_s = f"${ad['spend_usd']:.2f}" if ad.get("spend_usd") is not None else ad.get("status", "n/a")
    fixed_s = f"${snap.get('fixed_costs_window_usd', 0):.2f}"
    net_s = f"${snap['net_usd']:.2f}" if snap.get("net_usd") is not None else "n/a (revenue not connected)"
    return (f"{snap['window_days']}d — revenue {rev_s} · agent cost {ag_s} · ad spend {ad_s} · "
            f"fixed costs {fixed_s} · NET {net_s}")


def _ledger_dir(store_slug: str):
    from src.mcp_tools.design_files import _store_dir
    return _store_dir(store_slug) / "finance"


def read_finance_ledger(store_slug: str = "timeforbaby", chars: int = 1600) -> dict:
    """Recent LEDGER.md tail for the operator to read."""
    f = _ledger_dir(store_slug) / "LEDGER.md"
    text = f.read_text(encoding="utf-8", errors="ignore") if f.exists() else ""
    return {"ledger_recent": text[:chars], "path": str(f)}


async def log_finance_snapshot(days: int = 30, store_slug: str = "timeforbaby",
                               once_per_day: bool = True) -> dict:
    """Compute a snapshot and prepend it to finance/LEDGER.md (newest on top). When
    `once_per_day`, skips if today's snapshot is already logged. Returns {ok, path,
    snapshot, summary} or {skipped}."""
    snap = await finance_snapshot(days, store_slug)
    summary = _summary_line(snap)
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Jerusalem")); tz = "Asia/Jerusalem"
    except Exception:
        now = datetime.now(timezone(timedelta(hours=3))); tz = "UTC+3"
    day = now.strftime("%Y-%m-%d")

    d = _ledger_dir(store_slug)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "LEDGER.md"
    existing = f.read_text(encoding="utf-8", errors="ignore") if f.exists() else ""
    if once_per_day and f"## {day} " in existing:
        return {"skipped": "today already logged", "path": str(f), "summary": summary}

    rev, ag, ad = snap["revenue"], snap["agent_cost"], snap["ad_spend"]
    by_agent = "; ".join(f"{n} ${a['cost_usd']:.2f} ({a['calls']} calls)" for n, a in ag.get("by_agent", {}).items()) or ag.get("note", "")
    entry = (
        f"## {day} {now.strftime('%H:%M')} ({tz}) — {summary}\n"
        f"**Window:** last {snap['window_days']} days\n"
        f"**Revenue (PayPal):** {('$%.2f gross / $%.2f net' % (rev['gross_usd'], rev['net_usd'])) if rev.get('net_usd') is not None else 'unavailable — ' + str(rev.get('error',''))[:80]}\n"
        f"**Agent LLM cost:** ${ag.get('total_usd',0):.2f} — {by_agent}\n"
        f"**Ad spend (Google Ads):** {('$%.2f' % ad['spend_usd']) if ad.get('spend_usd') is not None else 'not connected (mocked)'}\n"
        f"**Net:** {('$%.2f' % snap['net_usd']) if snap.get('net_usd') is not None else 'n/a until revenue is connected'}\n"
        + (f"**Pending data pipes:** {', '.join(snap['pending_data'])}\n" if snap.get("pending_data") else "")
        + "\n"
    )
    header = ("# TIMEFOR BABY — Finance Ledger\n\nRevenue vs cost over time, newest on "
              "top. Auto-snapshotted. Sources not yet connected are marked honestly "
              "(never faked). See ../readme/README.md.\n\n---\n\n")
    if existing:
        marker = "---\n\n"; idx = existing.find(marker)
        new = (existing[:idx + len(marker)] + entry + existing[idx + len(marker):]) if idx != -1 else existing.rstrip() + "\n\n" + entry
    else:
        new = header + entry
    f.write_text(new, encoding="utf-8")
    return {"ok": True, "path": str(f), "summary": summary, "snapshot": snap}
