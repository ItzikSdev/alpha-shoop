"""
Organization API — inspect and drive the living company of agents.

  GET  /org           → company state + roster (for the Company UI page)
  GET  /org/meetings  → recent meetings with their decisions
  POST /org/tick      → run ONE full company cycle now (manual trigger)
  POST /org/daemon    → enable/disable + interval for the autonomous loop
  POST /org/hire      → manually hire an agent (override the revenue gate)

The org runs the SAME pipeline (`_spawn_run`) as everything else, so any store
builds it kicks off appear in GET /api/v1/runs alongside normal runs.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import re as _re

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.api.deps import get_current_operator
from src.org.conversation import agents_respond, two_way_enabled
from src.org.daemon import run_org_cycle
from src.org.models import (
    get_company,
    list_agents,
    list_meetings,
    new_agent,
    save_agent,
    update_agent,
    update_company,
)
from src.org.seed import seed_founding_team

router = APIRouter()


def _company_payload() -> dict:
    company = seed_founding_team()  # idempotent — guarantees a company + founders exist
    return {
        "company": company.to_dict(),
        "roster": [a.to_public() for a in list_agents(active_only=True)],
    }


@router.get("/org", summary="Company state + roster")
async def get_org() -> dict:
    return _company_payload()


@router.get("/org/meetings", summary="Recent meetings + decisions")
async def get_org_meetings(limit: int = 30) -> list[dict]:
    return [m.to_dict() for m in list_meetings(limit=limit)]


@router.post("/org/tick", summary="Run one company cycle now")
async def post_org_tick(body: dict | None = None) -> dict:
    kind = (body or {}).get("kind")  # optional: force standup/strategy/retro/teambuilding
    return await run_org_cycle(kind=kind)


@router.post("/org/unblock", summary="Human green-light: reset the doom-spiral lessons so the team resumes")
async def post_org_unblock() -> dict:
    from src.org.health import cancel_stuck_runs
    company = seed_founding_team()
    before = len(company.lessons)
    # The agents compounded an escalating negative narrative (re-wording the same
    # blocker each turn), so a phrase filter just plays whack-a-mole. A human
    # green-light RESETS the lessons to verified current reality instead.
    reset_lessons = [
        "✅ The store is LIVE and PROFITABLE-CAPABLE: first real paid order received "
        "($19.64). Funnel works end-to-end — products, PayPal, shipping, checkout. "
        "CJ is healthy. These problems are RESOLVED — do not re-flag them.",
        "MISSION: maximise real profit from this store, then reinvest it into "
        "opening MORE stores and hiring MORE agents. Growth is gated on real "
        "revenue — spend only what you've earned.",
        "FOCUS NOW: (1) make alphaforbaby convert better and look great — clean "
        "design, strong product pages/copy, enough quality products, trust/reviews; "
        "(2) grow sales consistently toward the next orders.",
        "RULE: every order needs the customer's phone + zip (collected at "
        "checkout). If an order is missing details, request them — don't guess.",
        "Be constructive and action-oriented. Build, improve, sell — don't loop on "
        "already-resolved blockers.",
    ]
    def _reset_lessons(c, reset_lessons: list = reset_lessons) -> None:
        c.lessons = list(reset_lessons)
    company = update_company(_reset_lessons)
    stuck = cancel_stuck_runs()
    return {
        "cleared_lessons": before,
        "stuck_cleared": stuck,
        "lessons_now": company.lessons,
    }


@router.post("/org/fulfill-latest", summary="Dropship the latest paid order via CJ. Dry-run unless {confirm:true}")
async def post_org_fulfill_latest(body: dict | None = None) -> dict:
    """Two-phase: with confirm=false (default) it RETURNS the order + shipping
    address + CJ mapping for review; with confirm=true it places the real CJ
    dropship order. The Shopify order webhook is only a placeholder, so this is
    the manual trigger for fulfillment until that's wired."""
    from sqlalchemy import select

    from src.db.engine import get_session
    from src.db.models import ProductMapping
    from src.mcp_tools.fulfillment import place_supplier_order
    from src.mcp_tools.shopify import _shopify_rest
    from src.stores import _current_store, list_stores

    confirm = bool((body or {}).get("confirm"))
    stores = list_stores()
    if not stores:
        return {"error": "no store configured"}
    _current_store.set(stores[0])

    data = await _shopify_rest("GET", "orders.json?status=any&limit=5")
    orders = data.get("orders", [])
    order = next((o for o in orders if o.get("financial_status") == "paid"), orders[0] if orders else None)
    if not order:
        return {"error": "no order found"}

    sa = order.get("shipping_address") or {}
    ov = (body or {}).get("ship_to") or {}  # caller can fill missing zip/phone
    # Take the country/province CODES straight from the Shopify order (ISO-2) —
    # never guess them from the country name.
    ship = {
        "name": ov.get("name") or sa.get("name") or f"{sa.get('first_name','')} {sa.get('last_name','')}".strip(),
        "address1": ov.get("address1") or sa.get("address1", ""),
        "city": ov.get("city") or sa.get("city", ""),
        "province": ov.get("province") or sa.get("province") or "",
        "country": ov.get("country") or sa.get("country", ""),
        "countryCode": ov.get("countryCode") or sa.get("country_code", ""),
        "provinceCode": ov.get("provinceCode") or sa.get("province_code", ""),
        "zip": ov.get("zip") or sa.get("zip") or "",
        "phone": ov.get("phone") or sa.get("phone") or order.get("phone") or "",
    }
    missing = [k for k in ("zip", "phone", "countryCode") if not ship.get(k)]

    items = []
    async with get_session() as session:
        for li in order.get("line_items", []):
            gid = f"gid://shopify/Product/{li.get('product_id')}"
            res = await session.execute(
                select(ProductMapping).where(ProductMapping.shopify_product_id == gid)
            )
            pm = res.scalar_one_or_none()
            items.append({
                "title": li.get("title"),
                "variant": li.get("variant_title"),
                "quantity": li.get("quantity", 1),
                "cj_vid": pm.supplier_sku if pm else None,
                "cj_pid": pm.supplier_product_id if pm else None,
            })

    out = {
        "order": order.get("name"),
        "order_id": order.get("id"),
        "total": order.get("total_price"),
        "ship_to": ship,
        "items": items,
        "confirmed": confirm,
    }
    out["missing_for_cj"] = missing
    if not confirm:
        out["note"] = "DRY RUN — review ship_to + items. Re-call with {\"confirm\": true} to place the real CJ order."
        return out
    if missing:
        out["error"] = f"CJ requires {missing} — pass them in ship_to and retry, e.g. {{\"confirm\":true,\"ship_to\":{{\"zip\":\"...\",\"phone\":\"...\"}}}}"
        return out

    placed = []
    for it in items:
        if not it["cj_vid"]:
            placed.append({"title": it["title"], "error": "no CJ mapping — cannot dropship"})
            continue
        r = await place_supplier_order(
            product_id=it["cj_vid"], quantity=it["quantity"],
            shipping_address=ship, order_reference=str(order.get("id")),
        )
        placed.append({"title": it["title"], **r})
    out["cj_orders"] = placed
    return out


@router.post("/org/announce", summary="Founder announcement: post to Telegram + record as a company lesson the agents act on")
async def post_org_announce(body: dict) -> dict:
    from src.org.telegram import post_to_telegram
    message = (body or {}).get("message", "").strip()
    if not message:
        return {"note": "Provide a non-empty 'message'."}
    seed_founding_team()
    def _add_announcement(c, message: str = message) -> None:
        c.lessons.append(f"📣 Founder update: {message}")
        c.lessons = c.lessons[-40:]
    company = update_company(_add_announcement)
    await post_to_telegram(f":loudspeaker: *Itzik (Founder):* {message}")
    return {"posted": True, "lessons_now": company.lessons[-3:]}


@router.get("/org/proposals", summary="Grace's pending Shopify action proposals (the approval gate)")
async def get_proposals(status: str = "pending") -> list[dict]:
    from src.org.proposals import list_proposals
    return list_proposals(status=status)


@router.post("/org/proposals/{pid}/approve", summary="Approve a proposal → it executes on Shopify")
async def approve_proposal(pid: str) -> dict:
    from src.org.proposals import execute_shopify, get_proposal, set_proposal
    from src.org.telegram import post_as
    p = get_proposal(pid)
    if not p or p["status"] != "pending":
        return {"error": "not found or not pending"}
    pl = p["payload"]
    res = await execute_shopify(pl.get("method", "GET"), pl.get("path", ""), pl.get("body"))
    set_proposal(pid, "executed", json.dumps(res)[:1500] if isinstance(res, dict) else str(res))
    ok = res.get("ok") if isinstance(res, dict) else False
    await post_as(p["agent"], "Developer",
                  f"{'✅' if ok else '⚠️'} בוצע (אושר): {pl.get('method')} {pl.get('path')} → {res.get('status')}")
    return {"proposal": pid, "executed": True, "result": res}


@router.post("/org/proposals/{pid}/reject", summary="Reject a proposal")
async def reject_proposal(pid: str) -> dict:
    from src.org.proposals import set_proposal
    set_proposal(pid, "rejected")
    return {"proposal": pid, "rejected": True}


_TERMINALX_CSS = """\
/* Alpha — clean TerminalX-style storefront */
:root{--ink:#1a1a1a;--muted:#707070;--line:#ececec;--bg:#fff;--accent:#000;}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased;letter-spacing:.01em;}
.page-width,.container{max-width:1400px;margin:0 auto;}
h1,h2,.h1,.h2,.title{font-weight:600;letter-spacing:-.01em;}
header,.header{border-bottom:1px solid var(--line);}
.header__menu-item,.list-menu__item{text-transform:uppercase;font-size:.78rem;letter-spacing:.08em;font-weight:600;}
.card,.card-wrapper,.grid__item .card{border:none;box-shadow:none;}
.card__media img,.media img{border-radius:2px;}
.card-information,.card__content{padding:.7rem .2rem;}
.card__heading,.card-information__text{font-size:.92rem;font-weight:500;letter-spacing:0;}
.price{font-weight:600;color:var(--ink);}
.product-grid,.grid{gap:1.4rem 1rem;}
.button,button.button,.btn,.shopify-payment-button__button{border-radius:0!important;background:var(--accent)!important;color:#fff!important;text-transform:uppercase;letter-spacing:.06em;font-weight:600;font-size:.8rem;border:none;}
.button--secondary{background:#fff!important;color:var(--ink)!important;border:1px solid var(--ink)!important;}
a{text-decoration:none;}
.banner__box,.hero{background:#fafafa;}
footer,.footer{border-top:1px solid var(--line);background:#fafafa;}
.product__title h1{font-weight:600;letter-spacing:-.01em;}
"""


@router.post("/org/apply-design", summary="Apply a clean TerminalX-style design to the live theme")
async def apply_design() -> dict:
    import httpx
    from src.stores import list_stores
    stores = list_stores()
    if not stores:
        return {"error": "no store"}
    s = stores[0]
    base = f"https://{s.shopify_domain}/admin/api/2024-07"
    hdr = {"X-Shopify-Access-Token": s.shopify_access_token}
    async with httpx.AsyncClient(timeout=25, headers=hdr) as c:
        th = (await c.get(f"{base}/themes.json")).json().get("themes", [])
        main = next((t for t in th if t.get("role") == "main"), th[0] if th else None)
        if not main:
            return {"error": "no theme"}
        tid = main["id"]
        steps = {"theme": main.get("name")}
        # 1. write the CSS asset
        r1 = await c.put(f"{base}/themes/{tid}/assets.json",
                         json={"asset": {"key": "assets/custom-alpha.css", "value": _TERMINALX_CSS}})
        steps["css_written"] = r1.status_code < 400
        # 2. ensure theme.liquid links it
        lay = (await c.get(f"{base}/themes/{tid}/assets.json", params={"asset[key]": "layout/theme.liquid"})).json()
        liquid = lay.get("asset", {}).get("value", "")
        if liquid and "custom-alpha.css" not in liquid and "</head>" in liquid:
            link = "{{ 'custom-alpha.css' | asset_url | stylesheet_tag }}\n</head>"
            liquid = liquid.replace("</head>", link, 1)
            r2 = await c.put(f"{base}/themes/{tid}/assets.json",
                             json={"asset": {"key": "layout/theme.liquid", "value": liquid}})
            steps["linked_in_theme"] = r2.status_code < 400
        else:
            steps["linked_in_theme"] = "already linked" if "custom-alpha.css" in liquid else "no </head>"
    return steps


@router.get("/org/shopify-scopes", summary="What scopes does our stored token ACTUALLY have")
async def get_shopify_scopes() -> dict:
    import httpx
    from src.stores import list_stores
    stores = list_stores()
    if not stores:
        return {"error": "no store configured"}
    s = stores[0]
    url = f"https://{s.shopify_domain}/admin/oauth/access_scopes.json"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(url, headers={"X-Shopify-Access-Token": s.shopify_access_token})
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}", "body": r.text[:200]}
        scopes = [x.get("handle") for x in r.json().get("access_scopes", [])]
        want = ["write_orders", "read_orders", "write_products",
                "write_merchant_managed_fulfillment_orders", "write_fulfillments"]
        return {"store": s.name, "total_scopes": len(scopes),
                "has": {w: (w in scopes) for w in want}, "all_scopes": sorted(scopes)}
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/org/rename", summary="Rename an agent (by current name or role)")
async def post_org_rename(body: dict) -> dict:
    match = (body.get("match") or "").strip().lower()
    new_name = (body.get("new_name") or "").strip()
    if not (match and new_name):
        return {"note": "Provide 'match' (current name or role) and 'new_name'."}
    def _rename(agent, new_name: str = new_name) -> None:
        agent.name = new_name
    for a in list_agents(active_only=True):
        if a.name.lower() == match or a.role.lower() == match:
            old = a.name
            update_agent(a.agent_id, _rename)
            return {"renamed": f"{old} → {new_name}", "role": a.role}
    return {"note": f"no active agent matching {match!r}"}


@router.post("/org/heartbeat", summary="Advance one agent's proactive turn now (works + posts to Telegram)")
async def post_org_heartbeat(body: dict | None = None) -> dict:
    from src.org.heartbeat import agent_heartbeat, run_specific
    role = (body or {}).get("role")
    result = await (run_specific(role) if role else agent_heartbeat())
    return result or {"note": "no turn (gate skipped it, or role not found)"}


@router.post("/org/assign", summary="Linus (CTO) assigns a task to an agent (flows through the CTO)")
async def post_org_assign(body: dict) -> dict:
    from src.org.telegram import post_as
    role = (body.get("role") or "Developer")
    task = (body.get("task") or "").strip()
    by = body.get("by", "Linus")
    def _assign_task(agent, task: str = task) -> None:
        agent.memory["assigned_task"] = task
    for a in list_agents(active_only=True):
        if a.role.lower() == role.lower():
            update_agent(a.agent_id, _assign_task)
            await post_as(by, "CTO", f"📋 {a.name}, משימה חדשה ממני: {task}")
            return {"assigned_to": a.name, "task": task}
    return {"error": f"no active agent with role {role!r}"}


@router.post("/org/sol", summary="Run Sol autonomously on a task (CJ sourcing + copywriting + Shopify push; narrates to Telegram)")
async def post_org_sol(body: dict) -> dict:
    """Fire Sol's tool-use loop in the background and return immediately with a run_id.
    Body: {task, store_slug?, max_steps?, ticket_id?, max_minutes?}. Requires the litellm proxy up.
    `max_minutes` (0 = no cap, only max_steps) matters for scheduled/cron-triggered runs —
    this endpoint returns immediately, so a caller's own timeout never bounds the real loop.
    Everything is narrated to Telegram as Sol AND recorded live to agent_runs/agent_steps —
    watch it (and any other agent's runs) at GET /org/agents/runs/{run_id}/stream, used by
    the platform-app `/agents/live` live activity page."""
    from src.org.agent_loop import run_sol_task
    task = (body.get("task") or "").strip()
    if not task:
        return {"error": "missing 'task'"}
    run_id = str(uuid.uuid4())
    asyncio.create_task(run_sol_task(
        task,
        store_slug=body.get("store_slug", "alphaforbaby"),
        max_steps=int(body.get("max_steps", 25)),
        run_id=run_id,
        ticket_id=body.get("ticket_id"),
        max_minutes=float(body.get("max_minutes", 0)),
    ))
    return {"run_id": run_id, "status": "running"}


@router.get("/org/agents/tools", summary="Tool catalog grouped for the live activity diagram (all agents, or ?agent=Name)")
async def get_agent_tools(agent: str = "") -> dict:
    from src.org.tool_catalog import AGENT_TOOL_GROUPS, tool_groups_for
    if agent:
        return {"groups": {agent: tool_groups_for(agent)}}
    return {"groups": AGENT_TOOL_GROUPS}


@router.get("/org/agents/runs", summary="Recent agent runs across the org (for the live activity page's run picker)")
async def get_agent_runs(agent: str = "", limit: int = 50) -> list[dict]:
    from src.org.agent_runs import list_agent_runs
    return list_agent_runs(agent_name=agent or None, limit=limit)


@router.get("/org/agents/runs/{run_id}", summary="One agent run's full step history (snapshot, no SSE)")
async def get_agent_run_detail(run_id: str) -> dict:
    from src.org.agent_runs import get_agent_run
    run = get_agent_run(run_id)
    if not run:
        return {"error": f"run {run_id!r} not found"}
    return run


@router.get(
    "/org/agents/runs/{run_id}/stream",
    summary="SSE stream of live agent steps (thought/tool_call/tool_result) for one run",
    # No JWT dep — EventSource cannot set Authorization headers
)
async def stream_agent_run(run_id: str) -> StreamingResponse:
    from src.org.agent_runs import steps_after, run_status

    async def generate():
        status = None
        for _ in range(15):
            status = await asyncio.to_thread(run_status, run_id)
            if status:
                break
            await asyncio.sleep(0.2)
        if not status:
            yield f"data: {json.dumps({'type': 'error', 'msg': 'Run not found'})}\n\n"
            return

        last_id = 0
        while True:
            new_steps = await asyncio.to_thread(steps_after, run_id, last_id)
            for step in new_steps:
                last_id = step["id"]
                yield f"data: {json.dumps({'type': 'step', **step})}\n\n"

            status = await asyncio.to_thread(run_status, run_id)
            if status not in ("running", None):
                yield f"data: {json.dumps({'type': 'done', 'status': status})}\n\n"
                return

            yield ": keepalive\n\n"
            await asyncio.sleep(0.4)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/org/shopify-reauth", summary="Get the one-click URL to re-authorize Shopify (fixes a 401 token)")
async def get_shopify_reauth(shop: str = "") -> dict:
    from src.mcp_tools.shopify_auth import build_authorize_url
    return {"authorize_url": build_authorize_url(shop),
            "note": "Open this URL, click Approve once. The token is then refreshed automatically."}


@router.get("/shopify/callback", summary="Shopify OAuth callback — exchanges the code and persists a fresh token")
async def shopify_oauth_callback(code: str = "", shop: str = "", state: str = "") -> dict:
    from src.mcp_tools.shopify_auth import exchange_code_for_token, persist_shopify_token
    if not (code and shop):
        return {"error": "missing code or shop"}
    try:
        token = await exchange_code_for_token(shop, code)
    except Exception as exc:
        return {"error": f"token exchange failed: {exc}"}
    if not token:
        return {"error": "no access_token returned"}
    result = persist_shopify_token(token, shop)
    return {"ok": True, "shop": shop, "persisted": result,
            "note": "Fresh Shopify token saved to .env + store record. Agents can edit the store now."}


@router.post("/org/delegate", summary="Linus picks Grace's next concrete store task now (force-rotates)")
async def post_org_delegate(body: dict | None = None) -> dict:
    from src.org.delegation import linus_delegates
    force = bool((body or {}).get("force", True))
    result = await linus_delegates(force=force)
    return result or {"note": "Grace is mid-task — pass {\"force\": true} to rotate her now."}


@router.post("/org/respond", summary="Every agent replies in-persona to a message (posts to Telegram)")
async def post_org_respond(body: dict) -> dict:
    seed_founding_team()
    message = (body or {}).get("message", "").strip()
    author = (body or {}).get("author", "You")
    if not message:
        return {"replies": [], "note": "Provide a non-empty 'message'."}
    replies = await agents_respond(message, author=author)
    return {"replies": replies}


@router.post("/org/slack/poll", summary="[legacy no-op] Telegram delivers messages live; nothing left to poll")
async def post_org_slack_poll() -> dict:
    return {
        "replies": [],
        "note": "Two-way chat moved from Slack (poll-based) to Telegram (push-based) — "
                "src/org/telegram.py's bot answers each message the moment it arrives, "
                "so there's nothing to poll anymore. Use POST /org/respond to trigger a "
                "reply manually, or check two_way_enabled(): " + str(two_way_enabled()),
    }


@router.get("/org/daemon", summary="Get org daemon config")
async def get_org_daemon() -> dict:
    company = seed_founding_team()
    return company.daemon


@router.post("/org/daemon", summary="Enable/disable the autonomous org loop")
async def set_org_daemon(body: dict) -> dict:
    seed_founding_team()
    def _apply_daemon_config(c, body: dict = body) -> None:
        for k in ("enabled", "interval_minutes"):
            if k in body:
                c.daemon[k] = body[k]
    company = update_company(_apply_daemon_config)
    return company.daemon


@router.post("/org/hire", summary="Manually hire an agent (bypasses revenue gate)")
async def post_org_hire(body: dict, operator: str = Depends(get_current_operator)) -> dict:
    seed_founding_team()
    agent = new_agent(
        name=body.get("name") or body.get("role", "Agent"),
        role=body.get("role", "Agent"),
        skill=body.get("skill", "Contributes to building and running stores."),
        team=body.get("team", "operations"),
        model_role=body.get("model_role", "standup"),
        hired_by=operator,
    )
    save_agent(agent)
    update_company(lambda c: setattr(c, "headcount", c.headcount + 1))
    return agent.to_public()


# ── Agent ticket board (Jira-style) ──────────────────────────────────────────
from dataclasses import asdict as _asdict
from src.org.tickets import (
    list_tickets as _list_tickets, open_ticket as _open_ticket,
    update_ticket as _update_ticket, scan_and_open_tickets as _scan_tickets,
)


@router.get("/org/tickets", summary="Agent ticket board — all tickets (auto-assigned to Sol, with deadlines)")
async def get_tickets(status: str | None = None) -> dict:
    from src.stores import list_stores
    stores = {s.store_id: s for s in list_stores()}
    ts = _list_tickets(status)
    for t in ts:
        s = stores.get(t.get("store_id"))
        slug = (s.storefront_slug or s.store_id) if s else ""
        t["store_name"] = s.name if s else (t.get("store_id") or "")
        t["store_url"] = f"https://{slug}.alpha-tech.live" if slug else ""
    return {"tickets": ts}


@router.post("/org/tickets", summary="Open a ticket (auto-assigned to Sol with priority + deadline)")
async def create_ticket(body: dict) -> dict:
    t = _open_ticket(
        title=body.get("title", ""), description=body.get("description", ""),
        source=body.get("source", "chat"), created_by=body.get("created_by", "Itzik"),
    )
    return {"ticket": _asdict(t) if t else None}


@router.patch("/org/tickets/{ticket_id}", summary="Update a ticket (status/assignee/priority/due)")
async def patch_ticket(ticket_id: str, body: dict) -> dict:
    return {"ok": _update_ticket(ticket_id, **body)}


@router.post("/org/tickets/scan", summary="Run a quality scan → agents open tickets for real problems")
async def scan_tickets() -> dict:
    return {"opened": await _scan_tickets()}


@router.get(
    "/org/rag",
    summary="Browse a live RAG corpus (cj_catalog | playbook) — metadata only, no raw vector bytes",
)
async def get_rag_corpus(corpus: str = "cj_catalog", limit: int = 100) -> dict:
    from src.rag.index import list_all
    entries = await list_all(corpus, limit=limit)
    return {"corpus": corpus, "count": len(entries), "entries": entries}


# ── Live DB browser (SQLite — the single shared traces.db) — read-only ──────
# Postgres was dropped from this system; SQLite is the actual system of
# record (org agents, stores, traces, tickets, product mappings all live in
# one file). Table names are always validated against sqlite_master before
# being interpolated into SQL, so this stays injection-safe despite the
# f-string (no other value is ever attacker-controlled).

async def _live_table_names(conn) -> set[str]:
    from sqlalchemy import text
    result = await conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    )
    return {row[0] for row in result.fetchall()}


# Columns holding secrets (Shopify/PayPlus/CJ tokens, email creds, the
# per-store `integrations` JSON blob with nested ad-platform API keys, ...).
# /org/stores already redacts these to booleans (has_payplus, ...) for the
# Stores page — this raw table browser must match that, not bypass it.
_SENSITIVE_COLUMN_HINTS = ("token", "secret", "password", "credentials", "integrations")


def _redact_row(row: dict[str, str | None]) -> dict[str, str | None]:
    return {
        col: ("***redacted***" if val and any(h in col.lower() for h in _SENSITIVE_COLUMN_HINTS) else val)
        for col, val in row.items()
    }


@router.get("/org/db/tables", summary="List live SQLite tables + row counts — read-only DB browser")
async def list_db_tables() -> dict:
    from sqlalchemy import text
    from src.db.engine import engine
    async with engine.connect() as conn:
        names = sorted(await _live_table_names(conn))
        tables = []
        for name in names:
            count = await conn.execute(text(f'SELECT COUNT(*) FROM "{name}"'))
            tables.append({"name": name, "count": count.scalar()})
    return {"tables": tables}


@router.get("/org/db/tables/{table}", summary="Browse rows of one live SQLite table (read-only, paginated)")
async def get_db_table(table: str, limit: int = 100, offset: int = 0) -> dict:
    from sqlalchemy import text
    from src.db.engine import engine
    async with engine.connect() as conn:
        if table not in await _live_table_names(conn):
            return {"table": table, "columns": [], "rows": [], "count": 0, "error": "unknown table"}
        total = (await conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))).scalar()
        result = await conn.execute(
            text(f'SELECT * FROM "{table}" LIMIT :limit OFFSET :offset'),
            {"limit": limit, "offset": offset},
        )
        columns = list(result.keys())
        rows = [
            _redact_row({col: (str(val) if val is not None else None) for col, val in zip(columns, row)})
            for row in result.fetchall()
        ]
    return {"table": table, "columns": columns, "rows": rows, "count": total}


# ── Live DB browser (Redis — raw keyspace, not just the curated RAG view) ───
# src/rag/index.py's list_all() only returns the two curated RAG corpora.
# This browses the whole keyspace as-is, for debugging what's actually in
# Redis. Vector bytes are always redacted (decode_responses=True would crash
# trying to UTF-8-decode them).

_REDIS_VECTOR_FIELD = "vector"


@router.get("/org/redis/keys", summary="Scan the live Redis keyspace (raw keys, any prefix) — read-only")
async def list_redis_keys(pattern: str = "*", limit: int = 200) -> dict:
    import redis.asyncio as aredis

    from src.config import get_settings
    client = aredis.from_url(get_settings().redis_url, decode_responses=True)
    out = []
    try:
        async for key in client.scan_iter(match=pattern, count=100):
            if len(out) >= limit:
                break
            out.append({"key": key, "type": await client.type(key), "ttl": await client.ttl(key)})
    finally:
        await client.aclose()
    return {"pattern": pattern, "count": len(out), "keys": out}


@router.get("/org/redis/keys/{key:path}", summary="Read one live Redis key's value — read-only, vector bytes redacted")
async def get_redis_key(key: str) -> dict:
    import redis.asyncio as aredis

    from src.config import get_settings
    client = aredis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        key_type = await client.type(key)
        ttl = await client.ttl(key)
        value: object = None
        if key_type == "string":
            value = await client.get(key)
        elif key_type == "hash":
            fields = [f for f in await client.hkeys(key) if f != _REDIS_VECTOR_FIELD]
            values = await client.hmget(key, fields) if fields else []
            value = dict(zip(fields, values))
            if await client.hexists(key, _REDIS_VECTOR_FIELD):
                value[_REDIS_VECTOR_FIELD] = "<binary vector, redacted>"
        elif key_type == "list":
            value = await client.lrange(key, 0, 200)
        elif key_type == "set":
            value = list(await client.smembers(key))
        elif key_type == "zset":
            value = await client.zrange(key, 0, 200, withscores=True)
        elif key_type != "none":
            value = f"<unsupported type: {key_type}>"
    finally:
        await client.aclose()
    return {"key": key, "type": key_type, "ttl": ttl, "value": value}


@router.get("/org/graph", summary="The company knowledge graph (FalkorDB) as nodes + edges for the dashboard")
async def get_org_graph(limit: int = 500) -> dict:
    """Agents, the tools they can use, and what they actually did — the same
    data the FalkorDB browser shows on :3002, served in a shape the dashboard
    can render directly so the graph lives inside the platform app.

    Read-only. Returns {"nodes": [...], "edges": [...], "available": bool};
    `available: false` (rather than an error) when FalkorDB isn't running, so
    the page can show a clear "graph offline" state instead of breaking.
    """
    import asyncio as _asyncio

    def _query() -> dict:
        from src.graph.knowledge_graph import _get_graph
        graph = _get_graph()
        if graph is None:
            return {"available": False, "nodes": [], "edges": [],
                    "note": "FalkorDB isn't reachable — start the `falkordb` service (docker compose up falkordb)."}
        nodes_res = graph.query(
            "MATCH (n) RETURN id(n), labels(n)[0], n.name, n.key, n.role LIMIT $limit",
            params={"limit": limit},
        )
        nodes = [
            {"id": r[0], "type": r[1] or "Node", "name": r[2] or r[3] or str(r[0]), "role": r[4]}
            for r in nodes_res.result_set
        ]
        edges_res = graph.query(
            "MATCH (a)-[e]->(b) RETURN id(a), id(b), type(e), e.ok, e.task, e.detail LIMIT $limit",
            params={"limit": limit},
        )
        edges = [
            {"source": r[0], "target": r[1], "type": r[2], "ok": r[3],
             "label": r[4] or r[5] or ""}
            for r in edges_res.result_set
        ]
        return {"available": True, "nodes": nodes, "edges": edges}

    try:
        return await _asyncio.to_thread(_query)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "nodes": [], "edges": [], "note": f"graph query failed: {exc}"}


# Cypher clauses that mutate. The graph browser is a READ-ONLY window onto the
# company's own observability data: a typo'd DELETE in the query box would wipe
# real history, so writes are rejected outright rather than trusted to the user.
_CYPHER_WRITE_RE = _re.compile(
    r"\b(create|merge|delete|detach|set|remove|drop|foreach|load\s+csv|"
    r"call\s*\{|call\s+db\.|call\s+dbms\.|call\s+algo\.)\b",
    _re.IGNORECASE,
)


@router.post("/org/graph/query", summary="Run a READ-ONLY Cypher query against the knowledge graph")
async def post_org_graph_query(body: dict) -> dict:
    """Ad-hoc Cypher, same as the FalkorDB browser's query box, but restricted to
    reads. Returns both a tabular result (`columns`/`rows`) and, when the query
    returns nodes/relationships, a `nodes`/`edges` graph the page can draw.

    Rejects any mutating clause (CREATE/MERGE/DELETE/SET/REMOVE/DROP/CALL …) —
    this endpoint exists to inspect the company, never to edit it.
    """
    import asyncio as _asyncio

    query = str(body.get("query") or "").strip()
    if not query:
        return {"error": "empty query"}
    if _CYPHER_WRITE_RE.search(query):
        return {"error": "read-only: CREATE/MERGE/DELETE/SET/REMOVE/DROP/CALL are not allowed here"}
    limit = int(body.get("limit") or 1000)

    def _run() -> dict:
        from src.graph.knowledge_graph import _get_graph
        graph = _get_graph()
        if graph is None:
            return {"available": False, "error": "FalkorDB isn't reachable"}
        res = graph.query(query, params={"limit": limit})

        nodes: dict[int, dict] = {}
        edges: list[dict] = []

        def _absorb(value: object) -> object:
            """Pull any Node/Edge out of a result cell into the graph payload,
            and render it as something JSON-serialisable for the table."""
            # falkordb returns Node/Edge objects; detect them structurally so we
            # don't depend on the client's class paths.
            if hasattr(value, "labels") and hasattr(value, "properties"):
                nid = int(getattr(value, "id", 0))
                props = dict(getattr(value, "properties", {}) or {})
                labels = list(getattr(value, "labels", []) or [])
                nodes[nid] = {
                    "id": nid,
                    "type": labels[0] if labels else "Node",
                    "name": props.get("name") or props.get("key") or str(nid),
                    "role": props.get("role"),
                    "props": props,
                }
                return nodes[nid]["name"]
            if hasattr(value, "relation") and hasattr(value, "src_node"):
                props = dict(getattr(value, "properties", {}) or {})
                edges.append({
                    "source": int(getattr(value, "src_node", 0)),
                    "target": int(getattr(value, "dest_node", 0)),
                    "type": str(getattr(value, "relation", "REL")),
                    "ok": props.get("ok"),
                    "label": props.get("task") or props.get("detail") or "",
                })
                return str(getattr(value, "relation", "REL"))
            if isinstance(value, list):
                return [_absorb(v) for v in value]
            return value

        rows = [[_absorb(cell) for cell in row] for row in res.result_set]
        return {
            "available": True,
            "columns": list(res.header and [h[1] for h in res.header] or []),
            "rows": rows,
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    try:
        return await _asyncio.to_thread(_run)
    except Exception as exc:  # noqa: BLE001
        return {"available": True, "error": f"{type(exc).__name__}: {exc}"}
