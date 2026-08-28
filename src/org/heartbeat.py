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
from src.org.conversation import _org_docs_context, _parse_json, company_language
from src.org.executor import execute_decisions
from src.org.health import run_health_summary
from src.org.meeting import gather_snapshot
from src.org.models import (
    Agent,
    Company,
    get_company,
    list_agents,
    new_meeting,
    save_company,
    update_agent,
)
from src.org.seed import seed_founding_team
from src.org.telegram import post_as
from src.tracing import agent_log, trace_store
from src.tracing.context import current_node, current_thread_id

logger = logging.getLogger(__name__)

# Which roles MANAGE (delegate work to others) vs DO (act in their own domain).
# Everyone on the roster takes proactive turns — that was the original design and
# it had been narrowed to the CEO alone, which left five of six agents unable to
# ever act on their own initiative. The old reason for narrowing it (four agents
# racing to spawn builds and burning Anthropic tokens) no longer applies: builds
# are serialised by `_build_running()`/`pipeline_run_active()`, and the whole
# roster runs on the local qwen3 model, so a turn costs nothing.
_MANAGER_ROLES = {"CEO", "CTO"}

# What a MANAGER may decide — note `assign`, the one that makes her a manager
# instead of a goal-generator.
_MANAGER_DECISIONS = """\
- {{"type":"assign","to":"<teammate's name>","task":"<one concrete, specific task>"}}
    THIS IS YOUR MAIN MOVE. You manage — you don't do the work yourself. The task
    runs for real the moment you decide it, so make it specific and doable
    ("Sol: source 5 newborn girl rompers from CJ and push the ones that pass"),
    never vague ("improve conversion"). Prefer this over everything else.
- {{"type":"boost_store","store_id":"<id from live state>","mode":"MARKETING"|"MONITOR"}}
- {{"type":"set_goal","goal":"<short OKR>"}}   (only if we genuinely lack one — see goals above)
- {{"type":"record_lesson","lesson":"<short insight>","target_role":"<optional: one teammate's name/role, if this is about them specifically>"}}
- {{"type":"cancel_stuck_runs"}}   (clean up hung runs)
- {{"type":"flag_blocker","issue":"<the root problem the team should route around>"}}"""

# What a WORKER may decide: do their own job. `do` runs through the same real
# execution path a message from Itzik would take (CJ sourcing, video render,
# TikTok report, ticket ops) — it is not roleplay.
_WORKER_DECISIONS = """\
- {{"type":"do","task":"<one concrete task in YOUR OWN domain, phrased as an instruction to yourself>"}}
    THIS IS YOUR MAIN MOVE. It actually EXECUTES with your real tools — so ask for
    something real and bounded ("source 5 baby boy jumpsuits from CJ and push the
    ones that pass the guards"), not a description of intent.
- {{"type":"ask","to":"<teammate's name>","task":"<what you need them to do, specifically>"}}
    When the next step needs a tool YOU don't have but a teammate does — look at
    what each teammate CAN RUN above and ask the one who actually owns it. This
    runs for real, so ask for something concrete ("Reel: render a rotation video
    for the Girls' Hip-Hug Dress"), not "can you help with video?".
- {{"type":"record_lesson","lesson":"<short insight worth the whole team knowing>","target_role":"<optional: one teammate's name/role, if this is about correcting them specifically>"}}
- {{"type":"flag_blocker","issue":"<something genuinely blocking you that a human must fix>"}}"""

# Nova's decision menu is deliberately narrower than every other worker's:
# no "do" (nothing to execute — the mandate is to watch, not build) and no "ask"
# (no ask_teammate/dispatch authority by charter — Ava owns routing, Nova
# only flags). create_ticket is how "flag drift, loudly" actually happens.
_NOVA_DECISIONS = """\
- {{"type":"do","task":"create_ticket: <what's drifting from sale #1, why it's off-target right now, and the concrete redirect>"}}
    THIS IS YOUR MAIN MOVE when you catch drift (new-product sourcing, new infra,
    new integrations, or any 'platform' work while sale #1 hasn't happened). Write
    the ticket with all three parts — what's happening, why it's off-target NOW,
    and the concrete redirect — not just "this seems off".
- {{"type":"record_lesson","lesson":"<what they did and what should happen instead>","target_role":"<the specific agent who drifted>"}}
    Use this ALONGSIDE the ticket, not instead of it, so the catch actually
    changes that agent's future behavior instead of repeating next week.
- {{"type":"flag_blocker","issue":"<something only a human can unblock — e.g. the USD merchant account status>"}}"""

_TURN_SYS = """\
You are {name}, the {role} of Alpha — an autonomous e-commerce company of AI
agents that builds real Shopify stores to earn real money. It's YOUR turn to act
on your own initiative (no one prompted you).

Write your channel "message" in {language}.

FACTS — these are TRUE, never claim otherwise:
- You have FULL Shopify access (all API permissions). You are NOT missing access.
- The store is LIVE but has ZERO sales to date. Checkout is blocked on the owner
  (MAX) opening a USD merchant account — until that lands, no order can complete,
  no matter how good the catalog/design/traffic is. That is the ONE blocker that
  matters right now; don't invent a different "manual blocker" or "no access"
  claim, and don't treat sourcing/design/infra work as more urgent than it.

Your job (skill): {skill}
Company goals: {goals}
Company values: {values}
Lessons we've learned: {lessons}
{budget_line}
Live state: {snapshot}
A store build is currently running: {build_running}

YOUR TEAMMATES (real people you work with — you can see what they're each doing):
{teammates}

WHAT THE TEAM HAS BEEN SAYING TO EACH OTHER (most recent last):
{team_chatter}

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

DO NOT restate a goal or a lesson we already hold (see the lists above) — that is
not a move, it's noise, and it will be dropped. If the only thing you can think of
is repeating something already written down, take a REAL action instead.

Allowed decision (pick the single best, or null to just share an update):
{decisions}

Output ONLY JSON: {{"message":"<your channel line, in the company's language>","decision":<one object or null>}}"""


# ── The turn's ENVELOPE, enforced by the model's decoder ─────────────────────
# "Output ONLY JSON" above is a request, and qwen3 kept ignoring it: roughly half
# of every standup since 2026-08-09 landed as `No decisions (meeting output could
# not be parsed)` — 14 of 25 turns on 08-12, 11 of 25 on 08-11. The agents were
# deciding; the decision was thrown away on the way out because the JSON came
# wrapped in prose or truncated mid-object.
#
# A JSON-schema response_format makes the runtime constrain generation, so the
# content field cannot be anything but a parseable object (verified live against
# this proxy: 2,149 chars of qwen3 reasoning went to reasoning_content while
# content stayed valid JSON).
#
# NOTE WHAT IS *NOT* CONSTRAINED: `decision` is a free-form object. The schema
# fixes the envelope only — which decision to make, and everything in it, stays
# entirely the model's call. This is plumbing, not a decision table.
_TURN_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "agent_turn",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "decision": {"type": ["object", "null"]},
            },
            "required": ["message", "decision"],
        },
    },
}


def _teammates(agent: Agent) -> str:
    """The rest of the roster, what each is FOR, the tools each can actually
    RUN, and what they're on right now — so an agent can address a real
    colleague by name and know what that colleague is genuinely capable of,
    instead of acting as if it were alone in the company.

    Knowing the teammate's TOOLS (not just their job title) is the part that was
    missing: "route video questions to Reel" is useless without knowing Reel can
    run generate_video. See src/org/directory.py."""
    from src.org.directory import capability_directory
    return capability_directory(exclude=agent.name)


def _team_chatter(limit: int = 12) -> str:
    """Recent messages from the shared company feed — agents could not see each
    other talk at all before this (agent_feed.py was written to, and only ever
    read by the dashboard), which is a large part of why nobody ever responded
    to anybody."""
    try:
        from src.org.agent_feed import read_agent_messages
        msgs = read_agent_messages(60)[-limit:]
    except Exception:  # noqa: BLE001
        return "(no feed)"
    return "\n".join(f"- {m.get('name')}: {str(m.get('text', ''))[:160]}" for m in msgs) or "(quiet so far)"


# A run that has been "running" for longer than this is a zombie, not work in
# flight — a crashed/restarted process leaves its row behind forever. Two such
# rows (from 2026-07-15 and 2026-07-23) silently froze the WHOLE company for
# 25 days: sourcing never fired, no meeting ran, and the CEO was told a build
# was permanently in progress so her only legal move was set_goal. Never again:
# staleness must decay on its own, without a human noticing.
_ZOMBIE_RUN_MINUTES = 90.0


def _build_running() -> bool:
    """True only if a REAL store build/pipeline run is genuinely in flight.

    Org bookkeeping runs (`[ORG] ...` meetings/heartbeats) are not builds and
    must never gate one — same exclusion `health.pipeline_run_active()` makes."""
    from src.org.health import _age_minutes

    for r in trace_store.list_runs()[:10]:
        if r.status not in ("running", "pending"):
            continue
        if (r.task or "").startswith("[ORG]"):
            continue
        if _age_minutes(r.started_at) > _ZOMBIE_RUN_MINUTES:
            continue
        return True
    return False


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
- The homepage is built from `stores/shopify/alphaforbaby.alpha-tech.live/style/site.json`
  (sections: marquee, hero 7-image carousel, category tiles, product grid, social).
- The product page is built from `stores/shopify/alphaforbaby.alpha-tech.live/style/product.json`
  (its design_tokens.typography DRIVES the live font sizes).
- To change the design you change those JSON files, then re-render. NEVER fetch
  theme ids or build raw asset PUTs by hand — the tools resolve everything.

YOU HAVE FILE ACCESS to the templates under stores/ (read + write). To change the
design, EDIT the JSON and it re-renders. Output ONE of:
- "edit_design": {{"file":"shopify/alphaforbaby.alpha-tech.live/style/site.json","content":"<full new JSON>"}}
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
  "edit_design": null OR {{"file":"shopify/alphaforbaby.alpha-tech.live/style/site.json","content":"<full new JSON>"}},
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
        docs = read_store_docs("alphaforbaby")
        if docs.get("owner"):
            design += (
                "\n=== WHO YOU WORK FOR — UNDERSTAND ITZIK BEFORE YOU ACT ===\n"
                f"{docs['owner'][:1800]}\n"
            )
        if docs.get("claude") or docs.get("readme") or docs.get("changelog_recent"):
            design += (
                "\n=== STORE SOURCE OF TRUTH + BUILD GUIDE — READ BEFORE CHANGING ANYTHING ===\n"
                "stores/shopify/alphaforbaby.alpha-tech.live/ is the source of truth + template. "
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

    # RETIRED 2026-07-07: this used to write stores/shopify/alphaforbaby.alpha-tech.live/
    # style/*.json and re-render it via the Liquid-theme apply_site_design/
    # apply_product_design pipeline. That pipeline is dead — the live site is 100%
    # Hydrogen (stores/shopify/hydrogen-alphaforbaby/), which those functions don't
    # touch at all, and write_design_file was unrestricted across all of stores/ (the
    # exact boundary violation fixed in agent_loop.py the same day). Rather than let
    # this autonomous heartbeat keep writing to a dead path, it's now a no-op.
    if isinstance(edit, dict) and edit.get("file") and edit.get("content"):
        await post_as(agent.name, agent.role,
                      "⚠️ Design-edit via the legacy site.json pipeline is retired — "
                      "the live site is Hydrogen now. No file was written.")
        actions = ["edit_design retired (no-op)"]
        result_record.update(ok=False, status=410, action="edit_design",
                              detail="legacy site.json pipeline retired 2026-07-07")
        def _record_turn(a: Agent, result_record: dict = result_record) -> None:
            a.memory["turns_on_task"] = int(a.memory.get("turns_on_task", 0)) + 1
            a.memory["last_result"] = result_record
        update_agent(agent.agent_id, _record_turn)
        return {"agent": agent.name, "role": agent.role, "message": msg, "actions": actions, "result": result_record}

    # Design = JSON-driven. Grace renders site.json → live homepage AND posts the
    # full JSON spec to the channel so Linus + the owner SEE and control exactly
    # what was built (the owner's explicit request: visibility + a review trail).
    # RETIRED 2026-07-07 alongside edit_design above: apply_site_design() re-renders
    # the legacy Liquid-theme site.json, which is NOT what's live (Hydrogen is) — this
    # branch's broad keyword trigger (any task mentioning "design"/"theme"/"json"/the
    # store name) was firing it constantly for no live effect. wants_design is now
    # always False; design/CSS work happens via the sandboxed Sol tools in
    # agent_loop.py against stores/shopify/hydrogen-alphaforbaby/ instead.
    wants_design = False
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
                          f"🔐 Approval request [{pid}]: {method} {path} — {req.get('reason','')[:80]}\n"
                          f"Approve: POST /org/proposals/{pid}/approve")
            actions = [f"filed Shopify proposal {pid} (awaiting approval)"]
            result_record.update(status="pending_approval", action=f"{method} {path}",
                                 detail=f"proposal {pid} awaiting approval")
        else:
            res = await execute_shopify(method, path, rbody)
            set_proposal(pid, "executed", json.dumps(res)[:1500])
            ok = bool(res.get("ok"))
            await post_as(agent.name, agent.role,
                          f"{'✅' if ok else '⚠️'} Executed: {method} {path} → {res.get('status')}\n{str(res.get('body',''))[:200]}")
            actions = [f"executed {method} {path} → {res.get('status')}"]
            result_record.update(ok=ok, status=res.get("status"), action=f"{method} {path}",
                                 detail=(res.get("error") or str(res.get("body", ""))[:200]))

    # Persist the turn count + structured result on Grace (single save).
    def _record_turn(a: Agent, result_record: dict = result_record) -> None:
        a.memory["turns_on_task"] = int(a.memory.get("turns_on_task", 0)) + 1
        a.memory["last_result"] = result_record
    update_agent(agent.agent_id, _record_turn)

    return {"agent": agent.name, "role": agent.role, "message": msg,
            "actions": actions, "result": result_record}


async def _agent_take_turn(agent: Agent, company: Company) -> dict:
    # Sol is a real tool-using agent (src/org/agent_loop.py's run_sol_task), not the
    # old sandboxed "propose only, no tools" persona _dev_turn was built for — his
    # actual heartbeat work (sourcing, email) already ran in _sourcing_tick/
    # _poll_inboxes above, both of which narrate to Telegram themselves. Skip the
    # legacy JSON-proposal roleplay for him entirely (no separate LLM call, no
    # confusing double narration).
    if agent.name == "Sol":
        return {"agent": agent.name, "role": agent.role, "message": "", "actions": []}

    # Developers are sandboxed proposers managed by the CTO — different path,
    # no business decisions, no tools.
    if agent.role == "Developer" or agent.team == "engineering":
        return await _dev_turn(agent, company)

    # Self-sufficient, not dependent on the caller having already set these:
    # both the rotation branch and run_specific() DO set current_thread_id
    # before calling here, but relying on caller discipline is exactly how the
    # cross-agent thread attribution leak happened elsewhere in this file.
    current_thread_id.set(f"heartbeat-{agent.role}")
    current_node.set(f"agent:{agent.role}")
    snapshot = await gather_snapshot()
    build_running = _build_running()

    is_manager = agent.role in _MANAGER_ROLES
    system = _TURN_SYS.format(
        name=agent.name, role=agent.role, skill=agent.skill,
        goals=company.goals, values=company.culture.get("values", []),
        lessons=company.lessons[-5:],
        snapshot=snapshot, build_running=build_running,
        run_health=run_health_summary(),
        recent_activity=_recent_activity(),
        language=company_language(),
        budget_line=budget_line(),
        teammates=_teammates(agent),
        team_chatter=_team_chatter(),
        decisions=(_NOVA_DECISIONS if agent.role == "Nova"
                   else _MANAGER_DECISIONS if is_manager else _WORKER_DECISIONS),
    )
    # qwen3 is a REASONING model: it spends tokens inside a <think> block before
    # answering. At max_tokens=600 it routinely burned the ENTIRE budget thinking
    # and returned an empty string (`out=600, response=''` all over llm_calls) —
    # measured at ~50% of calls on the CEO's long prompt, so half of every CEO
    # turn since this loop was written was silently lost, which is a large part of
    # why the company looked idle. `/no_think` turns the thinking off: picking one
    # JSON action from a fixed menu doesn't need chain-of-thought, and without it
    # a turn is both far faster and can't run out of budget mid-thought.
    # An explicit short timeout matters too — the client default is 180s with an
    # internal retry, so a stuck call blocked the whole heartbeat for ~6 minutes.
    parsed = None
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            # 240s, not 90s: a turn measured at ~200s+ on this local model when the
            # prompt is cold (28s just to read a 5k-token prompt) and qwen3 thinks
            # before answering. At 90s the call was killed mid-thought and the turn
            # was recorded as a failure — the timeout was manufacturing the very
            # "agent produced nothing" outcome it was meant to bound.
            llm = get_llm(agent.model_role or "standup", temperature=0.7,
                          max_tokens=1200, timeout=240)
            # First attempt asks the decoder to guarantee the envelope; the retry
            # drops it, so a provider that doesn't support response_format degrades
            # to exactly today's behaviour instead of failing outright.
            call = llm.bind(response_format=_TURN_RESPONSE_FORMAT) if attempt == 0 else llm
            resp = await call.ainvoke([
                SystemMessage(content=system),
                HumanMessage(content="It's your turn. What do you do and say? /no_think"),
            ])
            raw = str(resp.content).strip()
            if not raw:
                raise ValueError("model returned an empty response")
            parsed = _parse_json(raw)
            break
        except Exception as exc:
            logger.warning("Heartbeat turn for %s failed (attempt %d/2): %s",
                           agent.name, attempt + 1, exc)
            last_exc = exc
    if parsed is None:
        # Both attempts produced nothing parseable — a genuinely SILENT turn:
        # no message, no decision, nothing anyone would ever see. Previously
        # this just returned an error dict to the caller, which logs nothing
        # itself (post_as/agent_log below only fire once `parsed` is real) —
        # indistinguishable from the daemon simply not firing that tick at all.
        # Make it loud instead: a ticket means a silent agent shows up on the
        # board even if nobody's watching Telegram at 3am, deduped per-agent so
        # a string of silent ticks doesn't spam one ticket per tick.
        agent_log(f"🔇 {agent.name} ({agent.role}): heartbeat turn produced no "
                  f"parseable output after 2 attempts (last error: {last_exc})", "warning")
        try:
            from src.org.tickets import open_ticket
            open_ticket(
                f"{agent.name}'s heartbeat turn went silent",
                f"{agent.name} ({agent.role})'s heartbeat turn produced no parseable "
                f"output after 2 attempts — the local model returned an empty or "
                f"unparseable response both times. Last error: {last_exc}. This is a "
                "model/prompt reliability issue, not a decision the agent made — "
                "nothing was said and nothing was done this turn.",
                source="silent_turn", created_by="system",
                dedupe_key=f"silent_turn:{agent.name}",
            )
        except Exception:  # noqa: BLE001
            pass
        return {"agent": agent.name, "error": str(last_exc)}

    message = str(parsed.get("message", "")).strip()
    decision = parsed.get("decision")

    if message:
        await post_as(agent.name, agent.role, message)
        agent_log(f"💬 {agent.name} ({agent.role}): {message}", "info")

    actions: list[str] = []
    if isinstance(decision, dict) and decision.get("type") in ("create_ticket", "close_ticket"):
        # A menu deviation seen live on Nova's 2026-08-20 tick: her own decision
        # menu specifies {"type":"do","task":"create_ticket: ..."} (the "do" then
        # dispatches to _agent_act_ops's ticket classifier, which actually opens
        # it) — but she collapsed it to a bare {"type":"create_ticket",...}
        # instead. execute_decisions has no handler for that dtype, so it fell
        # into "unknown decision type" and got silently dropped: she NARRATED
        # opening a ticket and none ever opened. Neither side was strictly wrong
        # (the menu text is correct; execute_decisions' dtype list matches every
        # OTHER agent's "do"-wrapped pattern) — this normalizes the deviation
        # into the real dispatch instead of adding a redundant standalone
        # dtype, so it recovers regardless of which field names the model used.
        orig_type = decision["type"]
        title = str(decision.get("title") or decision.get("ticket_title") or "").strip()
        detail = str(decision.get("description") or decision.get("issue")
                     or decision.get("reason") or "").strip()
        task_text = f"{orig_type}: " + (
            f"{title} — {detail}" if title and detail else title or detail or message[:200]
        )
        decision = {"type": "do", "task": task_text}
        agent_log(f"{agent.name} sent a bare {orig_type!r} decision — "
                  "normalized into a 'do' dispatch instead of dropping it", "info")

    if isinstance(decision, dict) and decision.get("type"):
        # Don't let an agent kick off a second concurrent build.
        if decision["type"] == "build_store" and build_running:
            agent_log(f"{agent.name} held off a build — one is already running", "info")
        elif decision["type"] == "ask":
            # Worker → worker. Peer delegation, not just CEO → worker: an agent
            # that needs a tool it doesn't own can now reach the teammate who
            # does, which is the collaboration the knowledge graph showed was
            # entirely missing (no edges between agents at all).
            who = str(decision.get("to") or "").strip()
            task = str(decision.get("task") or "").strip()
            if who and task:
                from src.org.conversation import dispatch_to_agent
                actions = [await dispatch_to_agent(who, task, requested_by=agent.name)]
            else:
                agent_log(f"{agent.name} returned an 'ask' missing 'to' or 'task'", "warning")

        elif decision["type"] == "do":
            # A worker doing their OWN job: runs through the same real handlers a
            # Telegram message from Itzik would hit (Sol's CJ tool loop, Reel's
            # render, Kai's TikTok report, ticket ops) — not a roleplayed update.
            task = str(decision.get("task") or "").strip()
            if task:
                from src.org.conversation import dispatch_to_agent
                actions = [await dispatch_to_agent(task=task, name=agent.name,
                                                   requested_by="self-directed")]
            else:
                agent_log(f"{agent.name} returned a 'do' with no task", "warning")
        else:
            m = new_meeting("standup")
            m.attendees = [agent.agent_id]
            m.decisions = [decision]
            actions = await execute_decisions(m)

    # Record the turn in the knowledge graph — this is what gives EVERY agent a
    # presence there, not just the one whose loop happened to call a tool.
    try:
        from src.graph.knowledge_graph import log_agent_turn
        act = (decision or {}).get("type") if isinstance(decision, dict) else None
        await log_agent_turn(agent.name, act or "spoke", detail=message[:200])
    except Exception:  # noqa: BLE001
        pass

    # Attribute the concrete action to THIS agent in the channel, so it's always
    # unmistakable who did what (not a faceless company action).
    if actions:
        await asyncio.sleep(1.1)
        await post_as(agent.name, agent.role, "↳ " + " · ".join(actions))

    return {"agent": agent.name, "role": agent.role, "message": message, "actions": actions}


# Rotated so a standing sourcing loop doesn't hammer the same keyword forever —
# CJ's free-text search is noisy per-keyword (docs/PRODUCT_UPLOAD_PIPELINE.md), so
# variety here also surfaces different candidates across cycles.
_SOURCING_KEYWORDS = [
    "newborn girl romper", "newborn boy onesie", "baby girl dress", "infant pajama set",
    "baby boy jumpsuit", "toddler girl outfit", "infant swaddle blanket", "baby bib set",
]


def _system_memory_ok(min_pct: float = 15.0) -> tuple[bool, str]:
    """Guard against firing a heavy local-LLM cycle (qwen3:14b loads ~11GB) when
    the host machine is already memory-starved. Confirmed 2026-07-09: the Mac
    mini running this loop hard-froze — 11GB resident in a stuck llama-server
    process plus everyday Chrome/VS Code/VM usage left under 150MB free out of
    ~24GB total. Parses `vm_stat`/`sysctl` directly (no psutil dependency)."""
    try:
        import re
        import subprocess
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        page_size = int(re.search(r"page size of (\d+)", vm).group(1))
        stats = dict(re.findall(r"Pages (\w[\w ]*\w):\s+(\d+)\.", vm))
        free = int(stats.get("free", 0)) * page_size
        inactive = int(stats.get("inactive", 0)) * page_size
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout.strip())
        avail_pct = (free + inactive) / total * 100
        if avail_pct < min_pct:
            return False, f"only {avail_pct:.1f}% memory available (need >={min_pct}%) — skipping this cycle"
        return True, f"{avail_pct:.1f}% memory available"
    except Exception as exc:  # noqa: BLE001
        return True, f"memory check failed ({exc}) — proceeding anyway"  # fail open, don't block forever on a parsing bug


# Owner's cap (set 2026-08-09): stop sourcing once the store has this many LIVE
# products. Sourcing is otherwise an open-ended loop that would keep growing the
# catalog forever. Override per-company via daemon["product_cap"].
_DEFAULT_PRODUCT_CAP = 30


async def _live_product_count(store_slug: str) -> int | None:
    """How many ACTIVE products the store has right now, straight from Shopify
    (the authoritative source — the local RAG copy can lag). None if it can't be
    determined, so callers fail OPEN rather than silently halting sourcing on a
    transient API error."""
    try:
        from src.stores import list_stores, _current_store
        from src.mcp_tools.shopify import _shopify_gql
        store = next((s for s in list_stores() if s.store_id == store_slug), None)
        if store is None:
            return None
        token = _current_store.set(store)
        try:
            r = await _shopify_gql('{ productsCount(query: "status:active") { count } }', {})
        finally:
            _current_store.reset(token)
        return int(r["productsCount"]["count"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Couldn't count live products for %s: %s", store_slug, exc)
        return None


async def _sourcing_tick(company: Company) -> None:
    """Sol's real 24/7 sourcing loop: every `sourcing_interval_minutes` (default 45),
    source + evaluate ONE small batch of CJ candidates so the catalog and local RAG
    (search_local_catalog) grow on their own between sessions, without you having to
    prompt Sol each time. Small bounded batch keeps a single cycle's spend small —
    the existing $100/month cap fallback (get_llm) still applies underneath.

    This is a CODE-LEVEL cron, not an LLM decision — Sol's charter saying "don't
    manufacture new-product work right now" has no power over it, because the
    charter only ever reaches the model's own judgment calls, and this tick
    dispatches unconditionally on a timer regardless of what he'd choose himself.
    That's exactly how "Lace Trimmed Korean-style Floral-print Dress for Baby
    Girls" got sourced on 2026-08-17 despite the charter already saying not to:
    this loop doesn't read the charter at all. Paused 2026-08-17 (daemon
    "sourcing_paused") per Nova's mandate — single store, zero sales,
    checkout blocked on the USD merchant account — until sale #1 lands. Resume by
    clearing company.daemon["sourcing_paused"] once that's no longer true."""
    if company.daemon.get("sourcing_paused"):
        return
    interval = int(company.daemon.get("sourcing_interval_minutes", 45))
    last = company.daemon.get("last_sourcing_run_at")
    if last:
        try:
            since_min = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
            if since_min < interval:
                return
        except Exception:
            pass
    if _build_running():
        return  # don't compete with an active build/deploy
    # Memory guard is intentionally NOT gated by/saved into last_sourcing_run_at —
    # it re-checks every tick (cheap) and fires as soon as memory recovers, rather
    # than waiting out a full interval on top of the memory being tight.
    mem_ok, mem_detail = _system_memory_ok()
    if not mem_ok:
        logger.warning("Sourcing tick skipped: %s", mem_detail)
        return

    # Owner's hard cap: stop sourcing at N live products. Checked here (not left
    # to Sol's judgement) so it holds even when the model decides otherwise.
    # A count of None means Shopify didn't answer — fail OPEN and keep sourcing
    # rather than halting the catalog on a transient API blip.
    cap = int(company.daemon.get("product_cap", _DEFAULT_PRODUCT_CAP))
    live = await _live_product_count("alphaforbaby")
    if live is not None and live >= cap:
        logger.info("Sourcing tick skipped: %d live products >= cap of %d", live, cap)
        return

    idx = int(company.daemon.get("sourcing_kw_idx", 0)) % len(_SOURCING_KEYWORDS)
    keyword = _SOURCING_KEYWORDS[idx]
    company.daemon["sourcing_kw_idx"] = (idx + 1) % len(_SOURCING_KEYWORDS)
    company.daemon["last_sourcing_run_at"] = datetime.now(timezone.utc).isoformat()
    save_company(company)

    from src.org.agent_loop import run_sol_task
    try:
        remaining = (cap - live) if live is not None else None
        budget_note = (
            f"The store has {live} live products and the owner's cap is {cap}, so add AT MOST "
            f"{remaining} more this cycle and then stop. "
            if remaining is not None else ""
        )
        await run_sol_task(
            f'Autonomous sourcing cycle: search CJ for "{keyword}" — try search_local_catalog '
            "first so you don't re-evaluate a known reject. Evaluate up to 8 candidates and "
            "cj_add_product any that pass the guards (pick whichever collection fits: Baby "
            "Girls / Baby Boys / Unisex). Stop after ~8 candidates evaluated even if none pass "
            f"— this is a small bounded batch, not an open-ended search. {budget_note}",
            store_slug="alphaforbaby", max_steps=18,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Autonomous sourcing tick failed: %s", exc)


async def _stock_watch_tick(company: Company) -> None:
    """Owner's standing rule: out of stock at CJ ⇒ remove the product immediately.

    Runs DAILY (owner's cadence, 2026-08-09 — override with
    daemon["stock_check_interval_hours"]). Nothing else verifies supplier
    availability after a product goes live: the Shopify-side audit is blind here
    because every CJ dropship variant has inventory tracking off. The sweep is a
    few hundred CJ calls at ~1 QPS, so daily is also the right cost/QPS trade —
    a discontinued item is off the store within 24h.
    See src/org/stock_watch.py for the fail-closed safety rules."""
    interval_h = float(company.daemon.get("stock_check_interval_hours", 24))
    last = company.daemon.get("cj_stock_checked_at")
    if last:
        try:
            since_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
            if since_h < interval_h:
                return
        except Exception:
            pass
    if _build_running():
        return
    mem_ok, mem_detail = _system_memory_ok()
    if not mem_ok:
        logger.warning("Stock watch skipped: %s", mem_detail)
        return

    from src.org.stock_watch import check_store_stock
    try:
        report = await check_store_stock("alphaforbaby", remove=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stock watch failed: %s", exc)
        return
    if report.get("error"):
        logger.warning("Stock watch error: %s", report["error"])
        return
    logger.info("CJ stock watch: %s in stock, %s unknown, %s out, removed %s",
                report.get("in_stock"), report.get("unknown"),
                len(report.get("out_of_stock") or []), report.get("removed"))



# Substrings that mark a ticket as originating from _sourcing_tick's own work
# (its task text is always 'Autonomous sourcing cycle: search CJ for "<kw>"...',
# and the failure tickets filed about it describe the same thing in prose) — NOT
# a broad "mentions CJ/products" filter, which would also catch legitimate
# existing-product fixes Sol is still supposed to do while paused.
_SOURCING_TICKET_MARKERS = (
    "sourcing cycle", "autonomous sourcing", "cj_add_product",
    "source new product", "sourcing rules", "cj_search_products",
)


def _is_sourcing_ticket(ticket: dict) -> bool:
    text = f"{ticket.get('title', '')} {ticket.get('description', '')}".lower()
    return any(marker in text for marker in _SOURCING_TICKET_MARKERS)


async def _ticket_tick(company: Company) -> None:
    """Drain the ticket backlog: every `ticket_check_interval_minutes` (default 15),
    pick the single highest-priority 'todo' ticket assigned to Sol (the only agent
    with a real tool loop that can actually WORK a ticket) and run it for real.

    Without this, tickets only ever got OPENED, never WORKED: update_ticket(...,
    "doing") already existed inside run_sol_task, but nothing that auto-triggers a
    run (heartbeat's own sourcing/inbox ticks, chat dispatch, fulfillment failures)
    ever passed it a ticket_id — so the board was write-only. list_tickets() already
    orders by priority then due_at, so the first 'todo' row IS the right one to work
    next.

    This was the side door around `sourcing_paused`: pausing _sourcing_tick itself
    stops NEW "Autonomous sourcing cycle" tickets from being filed, but did nothing
    about the backlog of ones already open from before the pause — this tick would
    keep popping them off the queue and running them through Sol's real tool loop
    every 15 minutes regardless of the flag. Filter them out while paused instead
    of just skipping the head of the queue, so a legitimate non-sourcing ticket
    behind them still gets worked."""
    interval = int(company.daemon.get("ticket_check_interval_minutes", 15))
    last = company.daemon.get("last_ticket_check_at")
    if last:
        try:
            since_min = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
            if since_min < interval:
                return
        except Exception:
            pass
    if _build_running():
        return  # don't compete with an active build/deploy
    mem_ok, mem_detail = _system_memory_ok()
    if not mem_ok:
        logger.warning("Ticket tick skipped: %s", mem_detail)
        return

    company.daemon["last_ticket_check_at"] = datetime.now(timezone.utc).isoformat()
    save_company(company)

    from src.org.tickets import list_tickets
    todo = [t for t in list_tickets(status="todo") if t.get("assignee") == "Sol"]
    if company.daemon.get("sourcing_paused"):
        before = len(todo)
        todo = [t for t in todo if not _is_sourcing_ticket(t)]
        skipped = before - len(todo)
        if skipped:
            logger.info("Ticket tick: skipped %d sourcing-flavored ticket(s) — sourcing paused", skipped)
    if not todo:
        return
    ticket = todo[0]

    # Explicitly re-scope tracing to Sol before this call — without it, Sol's
    # ticket-working LLM calls inherited whatever current_thread_id/current_node
    # was last set by an unrelated prior tick (confirmed via llm_calls: Sol's
    # ticket-working prompts were showing up filed under other agents' threads).
    from src.tracing import current_node, current_thread_id
    current_thread_id.set("heartbeat-Product Sourcer & Copywriter")
    current_node.set("agent:Product Sourcer & Copywriter")

    from src.org.agent_loop import run_sol_task
    try:
        await run_sol_task(
            f"Ticket {ticket['id']} ({ticket['priority']}): {ticket['title']}. {ticket['description']}".strip(),
            store_slug=ticket.get("store_id") or "alphaforbaby",
            ticket_id=ticket["id"], max_steps=20,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ticket tick failed for %s: %s", ticket["id"], exc)


# Daily, not urgent-frequency — a media gap sits there until Sol works the
# ticket regardless of whether we notice it in an hour or in 12.
_MEDIA_SWEEP_INTERVAL_HOURS = 24.0

# The dedupe_key open_ticket checks — ONE catalog-wide ticket at a time. A
# second sweep while the first ticket is still open (todo/doing/blocked)
# no-ops rather than piling up a duplicate; this intentionally does NOT
# refresh the description with a fresher list mid-flight (matches Nova's
# gap-ticket dedupe: same key, same no-op-if-already-open behavior).
_MEDIA_SWEEP_DEDUPE_KEY = "media_sweep:catalog_gaps"


async def _media_sweep_tick(company: Company) -> None:
    """Code-driven catalog-completeness sweep — same pattern as _sourcing_tick/
    _ticket_tick: a deterministic cron, not an agent's spontaneous initiative.

    This exists because Reel's heartbeat turns were narrating "rendering a
    video for X" days in a row (real `logs` entries) with ZERO corresponding
    product_videos rows or knowledge-graph EXECUTED/ASSIGNED edges — the
    message field described an action the decision field never actually
    committed to. Nothing was checking the catalog for real gaps between
    Reel's remarks, so a product could sit unpublished-or-half-published
    indefinitely unless Itzik happened to notice and ask. This tick removes
    that dependency on an LLM noticing its own inaction.

    Checks media_blockers() ONLY (images + real 360° video, excluding CJ's
    supplier:: clip) — no stock_blockers() CJ round-trip, so this is a single
    cheap Shopify read, not a rate-limited operation.

    Deliberately NOT gated on sourcing_paused: that flag exists to stop NEW
    product sourcing during the pre-first-sale phase (see _sourcing_tick) —
    fixing media on products ALREADY in the catalog is completeness work
    Sol's charter already permits while paused, the same category
    _ticket_tick already carves out non-sourcing tickets for."""
    interval_h = float(company.daemon.get("media_sweep_interval_hours", _MEDIA_SWEEP_INTERVAL_HOURS))
    last = company.daemon.get("media_sweep_checked_at")
    if last:
        try:
            since_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
            if since_h < interval_h:
                return
        except Exception:
            pass
    company.daemon["media_sweep_checked_at"] = datetime.now(timezone.utc).isoformat()
    save_company(company)

    from src.mcp_tools.shopify import scan_media_gaps
    try:
        gaps = await scan_media_gaps()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Media sweep failed: %s", exc)
        return
    if not gaps:
        return

    from src.org.tickets import open_ticket
    lines = [f"- {g['title']} ({g['id']}): {', '.join(g['blockers'])}" for g in gaps]
    title = f"Products missing required media ({len(gaps)})"
    description = (
        "Daily catalog media sweep (media_blockers() against every ACTIVE product) "
        f"found {len(gaps)} product(s) not meeting the storefront gate (3 images + a "
        "real 360° video — CJ's own supplier clip doesn't count):\n\n" + "\n".join(lines)
    )
    t = open_ticket(title, description, source="media_sweep", created_by="system",
                    dedupe_key=_MEDIA_SWEEP_DEDUPE_KEY)
    if t:
        agent_log(f"🎬 Media sweep: opened {t.id} — {len(gaps)} product(s) missing media", "info")


# Poll-based stand-in for a Shopify order webhook: this backend has no public
# HTTPS URL yet (host-run on 127.0.0.1:8000, no tunnel/reverse-proxy/DNS —
# confirmed via `webhookSubscriptions { nodes }` returning empty on the live
# store), so `webhookSubscriptionCreate` would register a URL Shopify can
# never reach. 4h default, not near-real-time: order volume is zero right
# now, so poll latency doesn't matter — company.daemon["order_poll_interval_hours"]
# makes it easy to shorten once real orders start arriving regularly. Revisit
# an actual webhook once this backend has a real public address.
_ORDER_POLL_INTERVAL_HOURS = 4.0
_MAX_PROCESSED_ORDER_IDS = 500


async def _order_poll_tick(company: Company) -> None:
    """Picks up unfulfilled orders and runs them through the SAME process_order()
    a real webhook would call. Tracks processed order ids in company.daemon so
    an order is only ever handed to process_order() once, regardless of
    outcome — process_order can place a REAL paid CJ order, so this must never
    blindly retry an order that's still unfulfilled after a failure (that's
    what the order_failure ticket + Sol's investigation are for)."""
    interval_h = float(company.daemon.get("order_poll_interval_hours", _ORDER_POLL_INTERVAL_HOURS))
    last = company.daemon.get("order_poll_checked_at")
    if last:
        try:
            since_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
            if since_h < interval_h:
                return
        except Exception:
            pass
    company.daemon["order_poll_checked_at"] = datetime.now(timezone.utc).isoformat()
    save_company(company)

    from src.config import get_settings
    from src.mcp_tools.shopify import list_unfulfilled_orders
    from src.models.requests import ShopifyOrderWebhook
    from src.org.fulfillment import process_order
    from src.stores import list_stores

    try:
        orders = await list_unfulfilled_orders()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Order poll: couldn't list orders: %s", exc)
        return
    if not orders:
        return

    store = next(iter(list_stores()), None)
    if not store:
        return
    processed = set(company.daemon.get("fulfillment_processed_order_ids", []))
    settings = get_settings()
    new_ids: list[int] = []

    for raw in orders:
        if raw["id"] in processed:
            continue
        new_ids.append(raw["id"])
        try:
            order_total = float(raw["total_price"] or 0)
        except Exception:
            order_total = 0.0
        if order_total > settings.max_order_value_usd:
            agent_log(f"Order {raw['id']} (${order_total:.2f}) exceeds max_order_value_usd "
                      f"(${settings.max_order_value_usd}) — manual review, not auto-fulfilled", "warning")
            continue
        try:
            payload = ShopifyOrderWebhook(**raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Order poll: bad payload for order %s: %s", raw["id"], exc)
            continue
        try:
            await process_order(payload, store)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Order poll: process_order failed for order %s: %s", raw["id"], exc)

    if new_ids:
        company.daemon["fulfillment_processed_order_ids"] = (list(processed) + new_ids)[-_MAX_PROCESSED_ORDER_IDS:]
        save_company(company)


# Weekly, not the per-tick round robin every other agent gets — Nova's own
# charter says "weekly, not daily" and a charter alone doesn't enforce a cadence
# (see _sourcing_tick's docstring: only code does). Excluded from `rotation` in
# agent_heartbeat below so it doesn't ALSO take a turn there on top of this.
_NOVA_CHECK_HOURS = 168.0  # 7 days

# Thresholds for what counts as a real gap vs. noise (see
# knowledge_graph.find_capability_gaps' docstring for what each measures).
_GAP_MIN_ATTEMPTS = 2       # "frequently" attempting a tool with no CAN_USE edge
_GAP_MIN_FAIL_COUNT = 3     # "recurring" failure on a tool the agent DOES have
_GAP_STALE_HOURS = 24.0     # a delegation with no follow-up in a day, on a
                            # continuously-running org, is a real signal


async def _nova_graph_gap_scan(company: Company) -> None:
    """Nova's other weekly move, alongside her normal persona turn: a READ-ONLY
    FalkorDB scan for capability gaps (knowledge_graph.find_capability_gaps) —
    an agent stuck without a tool it keeps trying to use, a tool it DOES have
    that keeps failing, or a delegation nobody ever followed up on.

    The graph query is deterministic/mechanical (real counts, not a guess); an
    LLM call then judges which candidates are worth a ticket, grounded in the
    same docs/DECISIONS_LOG.md + docs/VISION_ROADMAP.md context _agent_act_nova
    uses in chat, so a gap already being worked or explicitly deferred doesn't
    get re-flagged. Diagnosis + create_ticket ONLY: this never writes to the
    graph's CAN_USE edges, never registers a tool, and the ticket it opens is a
    recommendation for Itzik to review — not something Nova (or any agent)
    acts on itself. Building the actual fix stays a human-reviewed, Claude-Code
    -deployed change, same as every other code change today."""
    from src.graph.knowledge_graph import find_capability_gaps
    from src.org.tickets import open_ticket

    candidates = await find_capability_gaps(
        min_attempts=_GAP_MIN_ATTEMPTS, min_fail_count=_GAP_MIN_FAIL_COUNT,
        stale_hours=_GAP_STALE_HOURS,
    )
    if not candidates:
        return

    # This runs BEFORE run_specific("Nova") in _nova_tick, so without an
    # explicit reset here the grounding call below would inherit whatever
    # thread was left ambient from the prior tick's rotation pick.
    current_thread_id.set("heartbeat-Nova")
    current_node.set("agent:Nova")

    system = (
        "You are Nova, the oversight agent at Alpha. Below is REAL evidence pulled "
        "from the org's own knowledge graph (FalkorDB) — never invented. For each "
        "numbered candidate, decide whether it's a genuine capability gap worth a "
        "ticket for Itzik (the owner) to review.\n\n"
        f"{_org_docs_context()}\n\n"
        "Use the docs above to avoid re-flagging something DECISIONS_LOG already "
        "shows was tried/fixed today, or proposing anything on VISION_ROADMAP's "
        "explicitly out-of-scope/deferred list as urgent.\n"
        "You have NO tool-creation or code-write capability, and nothing you output "
        "here should imply otherwise — each ticket is a diagnosis + recommendation "
        "for a human to act on, never an action you take yourself.\n"
        'Output ONLY JSON: {"tickets":[{"index":<candidate index>,"title":"<short '
        'title>","description":"<what is missing, which agent needs it, why — cite '
        'the graph evidence>"}]} — empty list if none of the candidates hold up."'
    )
    candidate_text = "\n".join(f"[{i}] {c['evidence']}" for i, c in enumerate(candidates))
    try:
        llm = get_llm("advisor", temperature=0.1, max_tokens=1200)
        resp = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=f"Candidates:\n{candidate_text}\n\n/no_think"),
        ])
        proposed = (_parse_json(str(resp.content)) or {}).get("tickets") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nova graph-gap grounding call failed: %s", exc)
        return

    for item in proposed:
        try:
            cand = candidates[int(item.get("index"))]
        except Exception:
            continue
        title = str(item.get("title") or cand["evidence"][:80]).strip()
        description = str(item.get("description") or cand["evidence"]).strip()
        # open_ticket's own dedupe_key check (src/org/tickets.py) is the real
        # duplicate guard — a re-scan next week that finds the same still-open
        # gap silently no-ops instead of piling up repeat tickets.
        t = open_ticket(title, description, source="nova_graph_scan",
                        created_by="Nova", dedupe_key=cand["dedupe_key"])
        if t:
            agent_log(f"🔎 Nova filed a capability-gap ticket: {t.title}", "info")


async def _nova_tick(company: Company) -> None:
    interval_h = float(company.daemon.get("nova_check_interval_hours", _NOVA_CHECK_HOURS))
    last = company.daemon.get("nova_checked_at")
    if last:
        try:
            since_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
            if since_h < interval_h:
                return
        except Exception:
            pass
    company.daemon["nova_checked_at"] = datetime.now(timezone.utc).isoformat()
    save_company(company)
    try:
        await _nova_graph_gap_scan(company)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nova graph-gap scan failed: %s", exc)
    try:
        await run_specific("Nova")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nova weekly check failed: %s", exc)


async def agent_heartbeat() -> dict | None:
    """Advance one agent's proactive turn. No-op unless the daemon is enabled."""
    company = seed_founding_team()
    if not company.daemon.get("enabled"):
        return None

    # Support-inbox polling lives ONLY in src/main.py::_support_inbox_loop (Nora's
    # process_central_inbox, on its own timer) — heartbeat used to run a second,
    # competing poller here (_poll_inboxes) that bypassed Nora entirely and handed
    # emails to Sol via a send_customer_email tool he no longer has. Removed
    # 2026-08-14; see docs/HANDOFF for the root-cause writeup.
    await _sourcing_tick(company)
    await _stock_watch_tick(company)
    await _ticket_tick(company)
    await _media_sweep_tick(company)
    await _order_poll_tick(company)
    await _nova_tick(company)

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

    # EVERY active agent takes proactive turns, round-robin — one per tick. Sol is
    # excluded — his real work already ran in _sourcing_tick/_poll_inboxes above,
    # so he's skipped here rather than burning a turn on a no-op. Nova is
    # excluded too — it runs on its own weekly cadence via _nova_tick above,
    # not the general per-tick rotation (that's the whole point of "weekly, not
    # daily": if it were in this rotation it'd take a turn as often as everyone
    # else, same as if the cadence had only ever been charter text).
    rotation = [a for a in agents if a.name not in ("Sol", "Nova")] or agents

    idx = int(company.daemon.get("hb_idx", 0)) % len(rotation)
    agent = rotation[idx]

    # ── Event-driven gate ─────────────────────────────────────────────────────
    # Agents act when the world changed, or after a quiet stretch — this is what
    # stops a doom-loop of constant chatter. NOTE the gate is checked BEFORE the
    # rotation index advances: advancing first (as it used to) meant a skipped
    # tick still burned that agent's slot, so with the gate open only ~1 tick in
    # 90 the same one or two agents got picked and the rest effectively never ran.
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

    company.daemon["hb_idx"] = (idx + 1) % len(rotation)
    save_company(company)

    thread_id = f"heartbeat-{agent.role}"
    if not trace_store.get_run(thread_id):
        trace_store.start_run(thread_id=thread_id, task=f"[ORG] {agent.name} working", operator=f"org:{agent.role}")
    from src.tracing import current_thread_id, current_trace_callback, TraceCallback
    current_thread_id.set(thread_id)
    current_trace_callback.set(TraceCallback())

    # ALWAYS close the run. This was the zombie factory: the run was started and
    # never finished, so a crash (or just the next boot) left it "running"
    # forever — `heartbeat-Product Sourcer & Copywriter` sat that way from
    # 2026-07-23 and froze sourcing, meetings and the CEO's whole action menu.
    try:
        return await _agent_take_turn(agent, get_company() or company)
    finally:
        try:
            trace_store.finish_run(thread_id, "completed")
        except Exception:  # noqa: BLE001
            pass


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
    try:
        return await _agent_take_turn(agent, company)
    finally:
        try:
            trace_store.finish_run(thread_id, "completed")  # never leave a zombie
        except Exception:  # noqa: BLE001
            pass
