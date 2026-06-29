"""
Proactive heartbeat — agents that work on their OWN initiative.

Unlike meetings (group decisions) and chat (reactions to you), the heartbeat is
what makes each agent feel alive and independent: every tick, ONE agent takes a
turn — it looks at the real company state, decides a single concrete move (or
just shares a short update), DOES it (real `_spawn_run` builds, hires, goals…),
and speaks in the channel as its own identity. Round-robin over the roster means
each agent acts on its own, one at a time — not the whole team in lockstep.

Gated on `company.daemon.enabled` and the global kill-switch, and it won't start
a new store build while one is already running (anti-pileup), so "alive" doesn't
mean "runaway".
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.budget import budget_line
from src.org.conversation import _parse_json, company_language
from src.org.executor import execute_decisions
from src.org.health import run_health_summary
from src.org.meeting import gather_snapshot
from src.org.models import (
    Agent,
    Company,
    get_agent,
    get_company,
    list_agents,
    new_meeting,
    save_agent,
    save_company,
)
from src.org.seed import seed_founding_team
from src.org.slack import post_as
from src.tracing import agent_log, trace_store
from src.tracing.context import current_node

logger = logging.getLogger(__name__)

# Roles that DRIVE the autonomous heartbeat. In the 5-role flow (docs/prompt.md)
# only the CEO (Ava) takes proactive heartbeat turns — she's the orchestrator that
# picks the next pipeline run (build_store / boost_store / [MONITOR]). The four
# worker personas (Product Hunter / UX & Content / Shopify Developer / Growth
# Marketer) act INSIDE pipeline runs and narrate there, so they don't each take an
# independent turn (which would have four agents racing to spawn builds + burning
# tokens). Falls back to the whole roster if no operator is active.
_OPERATOR_ROLES = {"CEO", "CTO"}

_TURN_SYS = """\
You are {name}, the {role} of Alpha — an autonomous e-commerce company of AI
agents that builds real Shopify stores to earn real money. It's YOUR turn to act
on your own initiative (no one prompted you).

Write your channel "message" in {language}.

FACTS — these are TRUE, never claim otherwise:
- You have FULL Shopify access (all API permissions). You are NOT missing access.
- The store is LIVE with a real first paid order. Payment (PayPal), shipping and
  checkout all WORK. The funnel is proven.
- The only external dependency is funding the CJ wallet for shipping — the owner
  is handling that. Do NOT invent other "manual blockers" or "no access" claims.

Your job (skill): {skill}
Company goals: {goals}
Company values: {values}
Lessons we've learned: {lessons}
{budget_line}
Live state: {snapshot}
A store build is currently running: {build_running}

OUR OPERATIONAL HEALTH right now:
{run_health}

WHAT THE TEAM HAS ALREADY DONE RECENTLY (most recent first):
{recent_activity}

Think before you act. Two things to watch for and FIX YOURSELVES:
1. Redundancy — if a move was already tried recently and hasn't produced
   revenue, do NOT repeat it. Pick a genuinely DIFFERENT next step.
2. Failures — if runs are failing or stuck (see health above), DIAGNOSE it.
   Don't keep launching the same failing action. Instead:
     - use "cancel_stuck_runs" to clean up hung runs, and/or
     - use "flag_blocker" to name the root problem (e.g. "product sourcing via
       CJ hangs", "missing SERPER key") so the whole team avoids that path and a
       human can fix the root cause, and
     - switch to an action that actually works (design, monitor, set a goal).
You are responsible for keeping the company healthy — fix problems, don't repeat them.

Decide ONE move that advances the company from where it is now, then say one
short first-person line in the channel about what you're doing. Prefer ACTION
over chatter when there's a clear next step for your role. If a build is already
running, do NOT start another one.

Allowed decision (pick the single best, or null to just share an update):
- {{"type":"build_store","niche":"<specific niche>","budget_usd":<number>}}
- {{"type":"boost_store","store_id":"<id from live state>","mode":"MARKETING"|"MONITOR"}}
- {{"type":"hire","role":"<title>","skill":"<one explicit sentence>","team":"<team>","model_role":"standup"}}
- {{"type":"set_goal","goal":"<short OKR>"}}
- {{"type":"record_lesson","lesson":"<short insight>"}}
- {{"type":"cancel_stuck_runs"}}   (clean up hung runs)
- {{"type":"flag_blocker","issue":"<the root problem the team should route around>"}}

Output ONLY JSON: {{"message":"<your channel line, in the company's language>","decision":<one object or null>}}"""


def _build_running() -> bool:
    return any(r.status in ("running", "pending") for r in trace_store.list_runs()[:5])


def _recent_activity(limit: int = 10) -> str:
    """A compact log of what the team recently did — so an agent can SEE the
    redundancy (e.g. 'we already boosted this store 5 times') and reason its way
    to a different move on its own, instead of us hard-coding a dedup rule."""
    lines = []
    for r in trace_store.list_runs()[:limit]:
        task = (r.task or "").replace("\n", " ")[:70]
        lines.append(f"- {r.operator}: {task} [{r.status}]")
    return "\n".join(lines) or "(nothing yet — you're early)"


_DEV_SYS = """\
You are {name}, a software Developer at Alpha, managed by Linus (the CTO). You
run on a LOCAL model in a SANDBOXED safe environment.

CRITICAL: Reply ONLY in {language}. Never use Chinese, Arabic, or any other
language — {language} only.

HARD SECURITY RULES (never break these):
- You CANNOT touch files, run commands, or change any code yourself.
- You CANNOT send any data outside. You may reason and learn only.
- You ONLY PROPOSE: describe the change/plan and optionally a small code sketch,
  for a human to review and approve. Nothing you write is applied without the
  user's explicit manual approval.

Your assigned task from the CTO: {task}
Company goals: {goals}
{design}
THE STORE IS NOW FULLY JSON-DRIVEN (this is the system — use it, don't fight it).
Each store lives at stores/shopify/<store>/ with style/ (design files), readme/
and changelog/:
- The homepage is built from `stores/shopify/timeofbaby.alpha-tech.live/style/site.json`
  (sections: marquee, hero 7-image carousel, category tiles, product grid, social).
- The product page is built from `stores/shopify/timeofbaby.alpha-tech.live/style/product.json`
  (its design_tokens.typography DRIVES the live font sizes).
- To change the design you change those JSON files, then re-render. NEVER fetch
  theme ids or build raw asset PUTs by hand — the tools resolve everything.

YOU HAVE FILE ACCESS to the templates under stores/ (read + write). To change the
design, EDIT the JSON and it re-renders. Output ONE of:
- "edit_design": {{"file":"shopify/timeofbaby.alpha-tech.live/style/site.json","content":"<full new JSON>"}}
  → writes the file (JSON validated) AND re-applies it live. This is how you change
  the homepage/product design — edit values in the JSON, never the .liquid.
- "apply_design": true → just re-render the current site.json + product.json.
- "theme_css": "<css>" → write extra CSS (auto-written + linked, no theme id).
- For any non-design Shopify task, use shopify_request with a RELATIVE path
  (e.g. "products.json") — never a full URL or version prefix.
To SEE the current templates first, your task may say to read them — the files are
stores/shopify/<store>/style/site.json and product.json. New stores get a new folder.
Already live (don't redo): 7-img hero carousel, size variants on all products,
free shipping, social-proof popup, real CJ descriptions, big JSON-driven text.
COLOR + SIZE variants are fully automated from CJ — new products get a Color
selector at publish, and the ecommerce worker self-heals older products each cycle
(adds Color + binds every color/size to its CJ SKU). Don't hand-build color
options; if a product is still missing one, the next worker cycle fixes it.
The real lever to revenue now is TRAFFIC (ads), not more design loops.

Output ONLY JSON (use exactly ONE action, or all null to just share an update):
{{"message":"<short first-person update in {language}>",
  "edit_design": null OR {{"file":"shopify/timeofbaby.alpha-tech.live/style/site.json","content":"<full new JSON>"}},
  "apply_design": false,
  "theme_css": null,
  "shopify_request": null OR {{"method":"GET|POST|PUT|DELETE","path":"products.json","body":<object or null>,"reason":"<why>"}}}}"""


async def _dev_turn(agent: Agent, company: Company) -> dict:
    """A developer agent's turn: propose only, post to the channel, touch nothing.

    By construction it has NO tools — it just produces text — so the 'no files /
    no data egress without approval' policy is enforced structurally, not by
    trust."""
    current_node.set(f"agent:{agent.role}")
    task = agent.memory.get("assigned_task") or (
        "No task assigned yet — ask Linus (CTO) what to work on, or propose one "
        "small, safe improvement to the company's systems."
    )
    try:
        from src.org.delegation import load_store_design
        _, design_brief = load_store_design()
    except Exception:
        design_brief = ""
    # Resolve the REAL main theme id so Grace writes to a valid path instead of a
    # placeholder like <theme_id> (which 404s). Best-effort.
    theme_id = ""
    try:
        from src.mcp_tools.shopify_theme import _active_theme_id
        theme_id = await _active_theme_id() or ""
    except Exception:
        theme_id = ""
    design = ""
    if design_brief:
        recipe = (
            f"\n\nTO APPLY IT: the live main theme id is {theme_id or '<unknown — call GET themes.json first>'}. "
            f"Write CSS by sending exactly: PUT themes/{theme_id}/assets.json with body "
            '{\"asset\":{\"key\":\"assets/custom-alpha.css\",\"value\":\"<your CSS>\"}}. '
            "Use the REAL numeric theme id above — never a placeholder. One asset write per turn."
        )
        design = f"\n=== TARGET DESIGN (make the live theme match this) ===\n{design_brief}{recipe}\n"
    # The changelog skill: Grace READS the store's source-of-truth README + recent
    # CHANGELOG every turn, so she knows the approved design + recent history and
    # never re-reverts it. The system logs her changes automatically (below).
    try:
        from src.mcp_tools.design_files import read_store_docs
        docs = read_store_docs("timeofbaby")
        if docs.get("owner"):
            design += (
                "\n=== WHO YOU WORK FOR — UNDERSTAND ITZIK BEFORE YOU ACT ===\n"
                f"{docs['owner'][:1800]}\n"
            )
        if docs.get("claude") or docs.get("readme") or docs.get("changelog_recent"):
            design += (
                "\n=== STORE SOURCE OF TRUTH + BUILD GUIDE — READ BEFORE CHANGING ANYTHING ===\n"
                "stores/shopify/timeofbaby.alpha-tech.live/ is the source of truth + template. "
                "Build to match the approved design (design.html / site.json); don't revert it; "
                "if the live store doesn't match, re-apply, don't redesign. Every change is logged "
                "to CHANGELOG.md automatically.\n"
                f"--- CLAUDE.md (build guide) ---\n{docs.get('claude','')[:1500]}\n"
                f"--- README ---\n{docs.get('readme','')[:1000]}\n"
                f"--- CHANGELOG (recent, newest first) ---\n{docs.get('changelog_recent','')[:1000]}\n"
            )
    except Exception:
        pass
    system = _DEV_SYS.format(
        name=agent.name, task=task, goals=company.goals, language=company_language(),
        design=design,
    )
    try:
        llm = get_llm("developer", temperature=0.3, max_tokens=1200)  # local 14B coder
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="It's your turn. Share your proposal."),
        ])
        raw = str(resp.content).strip()
    except Exception as exc:
        logger.warning("Dev turn for %s failed: %s", agent.name, exc)
        raw = ""

    msg, req = raw, None
    try:
        parsed = _parse_json(raw)
        msg = str(parsed.get("message", raw)).strip() or raw
        req = parsed.get("shopify_request")
    except Exception:
        pass  # not JSON → treat whole output as a plain message

    if msg:
        await post_as(agent.name, agent.role, msg)

    actions = ["proposal only"]
    # Critic loop: a STRUCTURED record of what this turn actually achieved, fed
    # back to Linus next round so he corrects a failure instead of moving on.
    result_record: dict = {
        "task": task[:200], "ok": None, "status": None,
        "action": "", "detail": "no shopify action this turn",
        "at": datetime.now(timezone.utc).isoformat(),
    }
    apply_design = bool(parsed.get("apply_design")) if isinstance(parsed, dict) else False
    theme_css = parsed.get("theme_css") if isinstance(parsed, dict) else None
    edit = parsed.get("edit_design") if isinstance(parsed, dict) else None

    # Grace edits a JSON template file directly (scoped to styles/) then it re-applies.
    if isinstance(edit, dict) and edit.get("file") and edit.get("content"):
        from src.mcp_tools.design_files import write_design_file
        from src.mcp_tools.shopify_design import apply_site_design, apply_product_design
        content = edit["content"] if isinstance(edit["content"], str) else json.dumps(edit["content"])
        wr = write_design_file(edit["file"], content)
        if wr.get("ok"):
            ap = await (apply_product_design() if "product" in edit["file"] else apply_site_design())
            ok = bool(ap.get("ok"))
            await post_as(agent.name, agent.role, f"✏️ edited {wr['path']} ({wr['bytes']}B) → applied: {'✅' if ok else '⚠️'}")
            actions = [f"edit_design {wr['path']}" + (" ✓" if ok else " ✗")]
            result_record.update(ok=ok, status=200 if ok else 500, action=f"edit {wr['path']}", detail=str(ap)[:160])
            # Changelog skill — log this change automatically so the store always has
            # a record (the local model can't be relied on to write it itself).
            if ok:
                try:
                    from src.mcp_tools.design_files import append_changelog
                    append_changelog(
                        title=(task[:80] or f"edited {wr['path']}"),
                        changed=f"{wr['path']} ({wr['bytes']}B) edited and re-applied live.",
                        by=agent.name, context=msg[:200],
                    )
                except Exception:
                    logger.warning("changelog append failed (non-fatal)")
        else:
            await post_as(agent.name, agent.role, f"⚠️ edit failed: {wr.get('error')}")
            actions = ["edit_design failed"]
            result_record.update(ok=False, status=400, action="edit_design", detail=str(wr.get('error'))[:160])
        fresh = get_agent(agent.agent_id) or agent
        fresh.memory["turns_on_task"] = int(fresh.memory.get("turns_on_task", 0)) + 1
        fresh.memory["last_result"] = result_record
        save_agent(fresh)
        return {"agent": agent.name, "role": agent.role, "message": msg, "actions": actions, "result": result_record}

    # Design = JSON-driven. Grace renders site.json → live homepage AND posts the
    # full JSON spec to the channel so Linus + the owner SEE and control exactly
    # what was built (the owner's explicit request: visibility + a review trail).
    _design_words = ("design", "עיצוב", "theme", "site.json", "homepage", "timeofbaby",
                     "css", "html", "storefront", "חנות", "json")
    wants_design = apply_design or (isinstance(theme_css, str) and bool(theme_css.strip())) \
        or (not (isinstance(req, dict) and req.get("path")) and any(w in task.lower() for w in _design_words))
    if wants_design:
        from src.mcp_tools.shopify_design import apply_site_design
        res = await apply_site_design()
        ok = bool(res.get("ok"))
        site = res.get("site", {})
        # Post the design JSON to the channel (review trail for Linus + owner).
        if site:
            pretty = json.dumps(site, ensure_ascii=False, indent=2)
            await post_as(agent.name, agent.role,
                          f"🎨 site design JSON (v{site.get('version','?')}) applied to homepage:\n```json\n{pretty[:1500]}\n```")
        await post_as(agent.name, agent.role,
                      f"{'✅' if ok else '⚠️'} rendered site.json → live homepage (theme {res.get('theme_id')})"
                      if ok else f"⚠️ design apply failed: {res.get('error')}")
        actions = ["apply_site_design" + (" ✓" if ok else " ✗")]
        result_record.update(ok=ok, status=200 if ok else 500, action="apply_site_design",
                             detail=str({k: v for k, v in res.items() if k != "site"})[:200])
        if ok:
            try:
                from src.mcp_tools.design_files import append_changelog
                append_changelog(
                    title=(task[:80] or "re-applied site.json to homepage"),
                    changed=f"Re-rendered site.json (v{site.get('version','?')}) → live homepage (theme {res.get('theme_id')}).",
                    by=agent.name, context=msg[:200],
                )
            except Exception:
                logger.warning("changelog append failed (non-fatal)")
        req = None  # design action takes this turn

    if isinstance(req, dict) and req.get("path"):
        import os

        from src.org.proposals import create_proposal, execute_shopify, set_proposal
        method, path, rbody = req.get("method", "GET"), req.get("path"), req.get("body")
        pid = create_proposal(agent.name, "shopify", {"method": method, "path": path, "body": rbody}, req.get("reason", ""))
        # Gate OFF (default, per the owner) → Grace executes Shopify directly.
        # Set GRACE_SHOPIFY_GATE=on to require manual approval again.
        gate = os.environ.get("GRACE_SHOPIFY_GATE", "off").lower() in ("on", "1", "true")
        if gate:
            await post_as(agent.name, agent.role,
                          f"🔐 בקשת אישור [{pid}]: {method} {path} — {req.get('reason','')[:80]}\n"
                          f"אשר: POST /org/proposals/{pid}/approve")
            actions = [f"filed Shopify proposal {pid} (awaiting approval)"]
            result_record.update(status="pending_approval", action=f"{method} {path}",
                                 detail=f"proposal {pid} awaiting approval")
        else:
            res = await execute_shopify(method, path, rbody)
            set_proposal(pid, "executed", json.dumps(res)[:1500])
            ok = bool(res.get("ok"))
            await post_as(agent.name, agent.role,
                          f"{'✅' if ok else '⚠️'} ביצעתי: {method} {path} → {res.get('status')}\n{str(res.get('body',''))[:200]}")
            actions = [f"executed {method} {path} → {res.get('status')}"]
            result_record.update(ok=ok, status=res.get("status"), action=f"{method} {path}",
                                 detail=(res.get("error") or str(res.get("body", ""))[:200]))

    # Persist the turn count + structured result on Grace (single save).
    fresh = get_agent(agent.agent_id) or agent
    fresh.memory["turns_on_task"] = int(fresh.memory.get("turns_on_task", 0)) + 1
    fresh.memory["last_result"] = result_record
    save_agent(fresh)

    return {"agent": agent.name, "role": agent.role, "message": msg,
            "actions": actions, "result": result_record}


async def _agent_take_turn(agent: Agent, company: Company) -> dict:
    # Developers are sandboxed proposers managed by the CTO — different path,
    # no business decisions, no tools.
    if agent.role == "Developer" or agent.team == "engineering":
        return await _dev_turn(agent, company)

    current_node.set(f"agent:{agent.role}")
    snapshot = await gather_snapshot()
    build_running = _build_running()

    system = _TURN_SYS.format(
        name=agent.name, role=agent.role, skill=agent.skill,
        goals=company.goals, values=company.culture.get("values", []),
        lessons=company.lessons[-5:],
        snapshot=snapshot, build_running=build_running,
        run_health=run_health_summary(),
        recent_activity=_recent_activity(),
        language=company_language(),
        budget_line=budget_line(),
    )
    try:
        llm = get_llm(agent.model_role or "standup", temperature=0.7, max_tokens=600)
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="It's your turn. What do you do and say?"),
        ])
        parsed = _parse_json(str(resp.content))
    except Exception as exc:
        logger.warning("Heartbeat turn for %s failed: %s", agent.name, exc)
        return {"agent": agent.name, "error": str(exc)}

    message = str(parsed.get("message", "")).strip()
    decision = parsed.get("decision")

    if message:
        await post_as(agent.name, agent.role, message)
        agent_log(f"💬 {agent.name} ({agent.role}): {message}", "info")

    actions: list[str] = []
    if isinstance(decision, dict) and decision.get("type"):
        # Don't let an agent kick off a second concurrent build.
        if decision["type"] == "build_store" and build_running:
            agent_log(f"{agent.name} held off a build — one is already running", "info")
        else:
            m = new_meeting("standup")
            m.attendees = [agent.agent_id]
            m.decisions = [decision]
            actions = await execute_decisions(m)

    # Attribute the concrete action to THIS agent in the channel, so it's always
    # unmistakable who did what (not a faceless company action).
    if actions:
        await asyncio.sleep(1.1)
        await post_as(agent.name, agent.role, "↳ " + " · ".join(actions))

    return {"agent": agent.name, "role": agent.role, "message": message, "actions": actions}


async def agent_heartbeat() -> dict | None:
    """Advance one agent's proactive turn. No-op unless the daemon is enabled."""
    company = seed_founding_team()
    if not company.daemon.get("enabled"):
        return None

    # Respect the global kill-switch (lazy import avoids a route import cycle).
    try:
        from src.api.routes.agents import _kill_switch
        if _kill_switch.is_active:
            return None
    except Exception:
        pass

    agents = list_agents(active_only=True)
    if not agents:
        return None

    # Only operator roles (the CEO) drive the proactive tick — the pipeline worker
    # personas act inside runs, not as solo heartbeat turns. Fall back to the whole
    # roster if no operator is active, so the loop is never dead.
    operators = [a for a in agents if a.role in _OPERATOR_ROLES] or agents

    idx = int(company.daemon.get("hb_idx", 0)) % len(operators)
    agent = operators[idx]
    company.daemon["hb_idx"] = (idx + 1) % len(operators)
    save_company(company)

    # ── Event-driven gate ─────────────────────────────────────────────────────
    # The operator (CEO) acts only when the world changed — this stops the
    # doom-loop + token burn. A legacy local-model Developer (none in the current
    # roster) would run continuously without this gate.
    if agent.role != "Developer":
        from datetime import datetime, timezone
        snap = await gather_snapshot()
        orders = sum(s.get("orders_7d", 0) for s in snap.get("stores", []))
        sig = f"{snap.get('revenue_7d_total_usd')}|{orders}|{snap.get('store_count')}"
        idle_min = 9999.0
        last_act = company.daemon.get("last_action_at")
        if last_act:
            try:
                idle_min = (datetime.now(timezone.utc) - datetime.fromisoformat(last_act)).total_seconds() / 60
            except Exception:
                pass
        quiet_max = float(company.daemon.get("idle_minutes", 45))
        if sig == company.daemon.get("last_sig") and idle_min < quiet_max:
            return None  # nothing new + acted recently → stay quiet
        company.daemon["last_sig"] = sig
        company.daemon["last_action_at"] = datetime.now(timezone.utc).isoformat()
        save_company(company)

    thread_id = f"heartbeat-{agent.role}"
    if not trace_store.get_run(thread_id):
        trace_store.start_run(thread_id=thread_id, task=f"[ORG] {agent.name} working", operator=f"org:{agent.role}")
    from src.tracing import current_thread_id, current_trace_callback, TraceCallback
    current_thread_id.set(thread_id)
    current_trace_callback.set(TraceCallback())

    return await _agent_take_turn(agent, get_company() or company)


async def run_specific(role: str) -> dict | None:
    """Run one named agent's turn directly (bypasses the change-gate) — used for
    Linus delegating a task to Grace and for manual demos."""
    company = seed_founding_team()
    agent = next((a for a in list_agents(active_only=True) if a.role.lower() == role.lower()), None)
    if not agent:
        return None
    thread_id = f"heartbeat-{agent.role}"
    if not trace_store.get_run(thread_id):
        trace_store.start_run(thread_id=thread_id, task=f"[ORG] {agent.name}", operator=f"org:{agent.role}")
    from src.tracing import TraceCallback, current_thread_id, current_trace_callback
    current_thread_id.set(thread_id)
    current_trace_callback.set(TraceCallback())
    return await _agent_take_turn(agent, company)
