"""
The meeting mechanism — the heart of the living company.

`hold_meeting(kind)` gathers a REAL snapshot of the company (live Shopify
revenue, store list, headcount, OKRs, accumulated lessons, shared culture),
renders every active agent as an LLM persona, and runs ONE LLM call in which the
leadership "discusses" and outputs a short summary + a list of structured
decisions. It does NOT execute them — that is `executor.execute_decisions`'s
job (clean separation).

Decision schema (the only types the executor understands):
  {"type": "build_store",  "niche": str, "budget_usd": float}
  {"type": "boost_store",  "store_id": str, "mode": "MARKETING"|"MONITOR"}
  {"type": "hire",         "role": str, "skill": str, "team": str, "model_role": str}
  {"type": "train",        "target_role": str, "topic": str}
  {"type": "set_goal",     "goal": str}
  {"type": "record_lesson","lesson": str}

Robust JSON parsing: this repo has a known history of LLMs wrapping JSON in
fences / prose, so a parse failure degrades safely to zero decisions rather than
crashing the autonomous loop (see orchestrator.py's token-burn history).
"""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_llm
from src.org.models import (
    Agent,
    Company,
    Meeting,
    get_company,
    list_agents,
    new_meeting,
)
from src.stores import _current_store, list_stores
from src.tracing import agent_log
from src.tracing.context import current_node

# How "creative" each meeting type is, and which get_llm role (model) it uses.
# standup/teambuilding are frequent + cheap → local Ollama via the "standup"
# role; strategy/retro are higher-stakes → "executive" (Sonnet). The toggle
# ORG_LOCAL_LLM=1 (read inside get_llm) can route everything local.
_KIND_LLM = {
    "standup":      ("standup",   0.5),
    "strategy":     ("executive", 0.6),
    "retro":        ("executive", 0.4),
    "teambuilding": ("standup",   0.8),
}

_MAX_DECISIONS = 8  # hard cap per meeting — a guardrail against runaway action lists


def _parse_json(text: str) -> dict:
    """Strip ``` fences / leading prose and load. Mirrors workers' _parse_json."""
    text = text.strip()
    # Grab the outermost {...} if the model added prose around it.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return json.loads(text.strip())


async def gather_snapshot() -> dict:
    """Build a REAL company snapshot — live revenue gates every growth decision."""
    from src.mcp_tools.shopify_analytics import get_sales_summary

    stores = list_stores()
    store_views: list[dict] = []
    total_revenue = 0.0
    for store in stores:
        if not store.active:
            continue
        # get_sales_summary reads the active-store context, so scope it per store.
        token = _current_store.set(store)
        try:
            health = await get_sales_summary(days=7)
        except Exception:
            health = {"revenue_usd": 0.0, "order_count": 0, "status": "unknown"}
        finally:
            _current_store.reset(token)
        total_revenue += float(health.get("revenue_usd", 0.0))
        store_views.append({
            "store_id": store.store_id,
            "name": store.name,
            "niche": store.niche,
            "revenue_7d_usd": health.get("revenue_usd", 0.0),
            "orders_7d": health.get("order_count", 0),
            "status": health.get("status", "unknown"),
        })

    return {
        "stores": store_views,
        "store_count": len(store_views),
        "revenue_7d_total_usd": round(total_revenue, 2),
    }


def _persona_block(agents: list[Agent]) -> str:
    lines = []
    for a in agents:
        lessons = a.memory.get("lessons", [])
        lesson_txt = f" | recent lessons: {'; '.join(lessons[-2:])}" if lessons else ""
        lines.append(f"- {a.name} ({a.role}, team={a.team}): {a.skill}{lesson_txt}")
    return "\n".join(lines)


_DECISION_SPEC = """\
Each decision is one JSON object. Allowed types (use only these):
- {"type":"build_store","niche":"<specific product niche>","budget_usd":<number>}
- {"type":"boost_store","store_id":"<id from the snapshot>","mode":"MARKETING"|"MONITOR"}
- {"type":"hire","role":"<title>","skill":"<one explicit sentence on exactly what they do>","team":"<team>","model_role":"executive|standup"}
- {"type":"train","target_role":"<existing role>","topic":"<what to teach/improve>"}
- {"type":"set_goal","goal":"<short OKR>"}
- {"type":"record_lesson","lesson":"<short reusable insight>"}
"""

_KIND_FOCUS = {
    "standup": "A short daily standup. Focus on concrete operational moves for "
               "TODAY: build or boost a store, or note a quick lesson. Keep it tight.",
    "strategy": "A strategy meeting. Set OKRs, decide growth, and propose hires "
                "ONLY if real revenue can justify another salary.",
    "retro": "A retrospective. Reflect on what worked vs the real numbers and "
             "record lessons. Prefer record_lesson and set_goal over new spending.",
    "teambuilding": "A team-building / culture session. Align on shared values and "
                    "language. Prefer record_lesson; you may set_goal. Avoid spending.",
}


def _build_prompt(kind: str, company: Company, agents: list[Agent], snapshot: dict) -> tuple[str, str]:
    affordability = (
        f"Treasury (real, accumulated revenue): ${company.treasury_usd:.2f}. "
        f"Last 7-day revenue across all stores: ${snapshot['revenue_7d_total_usd']:.2f}. "
        f"Headcount: {company.headcount}. "
        "Hard rule: do NOT propose a 'hire' unless real revenue clearly justifies "
        "another salary — the company spends only what it earns."
    )
    system = (
        "You are the collective leadership of Alpha, an autonomous e-commerce "
        "company whose agents build and run real Shopify stores to earn real money.\n\n"
        "VERIFIED FACTS — these are TRUE, never claim or 'flag' otherwise:\n"
        "- CJ product search WORKS (it returns real products + freight quotes). There "
        "is NO 'CJ product-search blocker'. Do NOT propose, record, or escalate one.\n"
        "- The Shopify token is valid with FULL scopes (incl. write_themes, "
        "write_products, write_discounts, write_price_rules). There is NO scope/401 "
        "blocker. The store theme is editable RIGHT NOW.\n"
        "- The store already has products. The bottleneck to revenue is DESIGN quality "
        "+ CONVERSION + TRAFFIC, not sourcing. Prefer boost_store/design work over "
        "re-sourcing, and never re-litigate solved blockers.\n\n"
        f"MEETING TYPE: {kind} — {_KIND_FOCUS.get(kind, '')}\n\n"
        "THE TEAM (each persona, their explicit skill, and what they've learned):\n"
        f"{_persona_block(agents)}\n\n"
        f"COMPANY CULTURE / VALUES: {company.culture.get('values', [])}\n"
        f"CURRENT GOALS (OKRs): {company.goals}\n"
        f"ACCUMULATED LESSONS: {company.lessons[-5:]}\n\n"
        f"FINANCES: {affordability}\n\n"
        "Hold the meeting as this leadership team, then output a decision plan.\n\n"
        f"{_DECISION_SPEC}\n"
        f"Output ONLY a JSON object: "
        f'{{"summary":"2-4 sentence discussion summary","decisions":[ ... up to {_MAX_DECISIONS} ... ]}}'
    )
    user = (
        "LIVE SNAPSHOT:\n"
        f"{json.dumps(snapshot, indent=2)}\n\n"
        "Run the meeting now and produce the JSON decision plan."
    )
    return system, user


async def hold_meeting(kind: str = "strategy") -> Meeting:
    """Run one meeting → a Meeting with structured decisions (not yet executed)."""
    current_node.set(f"meeting:{kind}")

    company = get_company() or Company()
    agents = list_agents(active_only=True)
    meeting = new_meeting(kind)
    meeting.attendees = [a.agent_id for a in agents]

    agent_log(f"📋 Holding {kind} meeting — {len(agents)} attendee(s)", "action")

    snapshot = await gather_snapshot()
    meeting.context_snapshot = snapshot
    agent_log(
        f"Snapshot: {snapshot['store_count']} store(s), "
        f"${snapshot['revenue_7d_total_usd']:.2f} revenue (7d), "
        f"treasury ${company.treasury_usd:.2f}",
        "info",
    )

    role, temp = _KIND_LLM.get(kind, ("executive", 0.5))
    system, user = _build_prompt(kind, company, agents, snapshot)

    try:
        llm = get_llm(role, temperature=temp)
        response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        parsed = _parse_json(str(response.content))
    except Exception as exc:  # parse failure or LLM error → degrade safely
        agent_log(f"Meeting produced no parseable plan ({exc}) — 0 decisions", "warning")
        meeting.notes = "No decisions (meeting output could not be parsed)."
        return meeting

    meeting.notes = str(parsed.get("summary", ""))[:1000]
    decisions = parsed.get("decisions", [])
    if isinstance(decisions, list):
        meeting.decisions = decisions[:_MAX_DECISIONS]

    agent_log(f"🧠 {meeting.notes}", "info")
    agent_log(f"Decisions reached: {len(meeting.decisions)}", "success")
    for d in meeting.decisions:
        agent_log(f"  → {d.get('type')}: {json.dumps({k: v for k, v in d.items() if k != 'type'})}", "info")

    return meeting
