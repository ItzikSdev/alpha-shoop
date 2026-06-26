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

from fastapi import APIRouter, Depends

from src.api.deps import get_current_operator
from src.org.conversation import agents_respond, fetch_and_respond, two_way_enabled
from src.org.daemon import run_org_cycle
from src.org.models import (
    get_company,
    list_agents,
    list_meetings,
    new_agent,
    save_agent,
    save_company,
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
    company.lessons = [
        "✅ The store is LIVE and PROFITABLE-CAPABLE: first real paid order received "
        "($19.64). Funnel works end-to-end — products, PayPal, shipping, checkout. "
        "CJ is healthy. These problems are RESOLVED — do not re-flag them.",
        "MISSION: maximise real profit from this store, then reinvest it into "
        "opening MORE stores and hiring MORE agents. Growth is gated on real "
        "revenue — spend only what you've earned.",
        "FOCUS NOW: (1) make timeofbaby convert better and look great — clean "
        "design, strong product pages/copy, enough quality products, trust/reviews; "
        "(2) grow sales consistently toward the next orders.",
        "RULE: every order needs the customer's phone + zip (collected at "
        "checkout). If an order is missing details, request them — don't guess.",
        "Be constructive and action-oriented. Build, improve, sell — don't loop on "
        "already-resolved blockers.",
    ]
    save_company(company)
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


@router.post("/org/announce", summary="Founder announcement: post to Slack + record as a company lesson the agents act on")
async def post_org_announce(body: dict) -> dict:
    from src.org.slack import post_to_slack
    message = (body or {}).get("message", "").strip()
    if not message:
        return {"note": "Provide a non-empty 'message'."}
    company = seed_founding_team()
    company.lessons.append(f"📣 Founder update: {message}")
    company.lessons = company.lessons[-40:]
    save_company(company)
    await post_to_slack(f":loudspeaker: *Itzik (Founder):* {message}")
    return {"posted": True, "lessons_now": company.lessons[-3:]}


@router.get("/org/proposals", summary="Grace's pending Shopify action proposals (the approval gate)")
async def get_proposals(status: str = "pending") -> list[dict]:
    from src.org.proposals import list_proposals
    return list_proposals(status=status)


@router.post("/org/proposals/{pid}/approve", summary="Approve a proposal → it executes on Shopify")
async def approve_proposal(pid: str) -> dict:
    from src.org.proposals import execute_shopify, get_proposal, set_proposal
    from src.org.slack import post_as
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
    for a in list_agents(active_only=True):
        if a.name.lower() == match or a.role.lower() == match:
            old = a.name
            a.name = new_name
            save_agent(a)
            return {"renamed": f"{old} → {new_name}", "role": a.role}
    return {"note": f"no active agent matching {match!r}"}


@router.post("/org/heartbeat", summary="Advance one agent's proactive turn now (works + posts to Slack)")
async def post_org_heartbeat(body: dict | None = None) -> dict:
    from src.org.heartbeat import agent_heartbeat, run_specific
    role = (body or {}).get("role")
    result = await (run_specific(role) if role else agent_heartbeat())
    return result or {"note": "no turn (gate skipped it, or role not found)"}


@router.post("/org/assign", summary="Linus (CTO) assigns a task to an agent (flows through the CTO)")
async def post_org_assign(body: dict) -> dict:
    from src.org.slack import post_as
    role = (body.get("role") or "Developer")
    task = (body.get("task") or "").strip()
    by = body.get("by", "Linus")
    for a in list_agents(active_only=True):
        if a.role.lower() == role.lower():
            a.memory["assigned_task"] = task
            save_agent(a)
            await post_as(by, "CTO", f"📋 {a.name}, משימה חדשה ממני: {task}")
            return {"assigned_to": a.name, "task": task}
    return {"error": f"no active agent with role {role!r}"}


@router.post("/org/respond", summary="Every agent replies in-persona to a message (posts to Slack)")
async def post_org_respond(body: dict) -> dict:
    seed_founding_team()
    message = (body or {}).get("message", "").strip()
    author = (body or {}).get("author", "You")
    if not message:
        return {"replies": [], "note": "Provide a non-empty 'message'."}
    replies = await agents_respond(message, author=author)
    return {"replies": replies}


@router.post("/org/slack/poll", summary="Read the latest Slack message and have agents answer it")
async def post_org_slack_poll() -> dict:
    if not two_way_enabled():
        return {
            "replies": [],
            "note": "Two-way reading needs SLACK_BOT_TOKEN + SLACK_CHANNEL in .env "
                    "(a webhook can only post). Until then use POST /org/respond.",
        }
    return {"replies": await fetch_and_respond()}


@router.get("/org/daemon", summary="Get org daemon config")
async def get_org_daemon() -> dict:
    company = seed_founding_team()
    return company.daemon


@router.post("/org/daemon", summary="Enable/disable the autonomous org loop")
async def set_org_daemon(body: dict) -> dict:
    company = seed_founding_team()
    for k in ("enabled", "interval_minutes"):
        if k in body:
            company.daemon[k] = body[k]
    save_company(company)
    return company.daemon


@router.post("/org/hire", summary="Manually hire an agent (bypasses revenue gate)")
async def post_org_hire(body: dict, operator: str = Depends(get_current_operator)) -> dict:
    company = seed_founding_team()
    agent = new_agent(
        name=body.get("name") or body.get("role", "Agent"),
        role=body.get("role", "Agent"),
        skill=body.get("skill", "Contributes to building and running stores."),
        team=body.get("team", "operations"),
        model_role=body.get("model_role", "standup"),
        hired_by=operator,
    )
    save_agent(agent)
    company.headcount += 1
    save_company(company)
    return agent.to_public()
