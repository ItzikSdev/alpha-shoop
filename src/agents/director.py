"""Director Agent — routes to the correct worker via the LiteLLM proxy."""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.tracing import agent_log
from src.tracing.context import current_node

_SYSTEM_PROMPT = """\
You are the Director Agent in an autonomous e-commerce arbitrage system.
Your job is to analyse the current state and decide which worker to invoke next.

Workers available:
- store_setup      : Brand the store — generate identity, create About Us and policy pages (run ONCE, before any products are listed)
- trend_scraper    : Find trending products on CJ/AliExpress
- ecommerce_manager: Create and manage Shopify products with premium branding and copy
- marketing_agent  : Launch Google/Meta ad campaigns
- fulfillment_agent: Place supplier orders and update tracking
- END              : The task is complete, stop the graph

ROUTING RULES:
1. If store_brand is null/missing → route to store_setup first (always, before anything else)
2. After store_setup → route to trend_scraper
3. After products found → route to ecommerce_manager
4. After products listed → route to marketing_agent
5. If any worker reports an unrecoverable error → route to END

Current limits (HARD guardrails, never override):
- Max daily ad spend: ${max_ad_spend_daily} USD
- Max single order: ${max_order_value} USD

If the last worker reported an error, do not call that same worker again
expecting a different result — route to END and report the failure instead.

Respond with ONLY a JSON object: {{"next": "<worker_name>", "reasoning": "<one sentence>"}}
"""


async def director_node(state: AgentState) -> dict:
    """LangGraph node: Director decides the next worker to call."""
    current_node.set("director")
    if state.get("kill_switch_triggered"):
        return {"next_agent": "END", "director_reasoning": "Kill-switch is active."}

    settings = get_settings()
    llm = get_llm("director", temperature=0.0)

    system = _SYSTEM_PROMPT.format(
        max_ad_spend_daily=settings.max_ad_spend_daily_usd,
        max_order_value=settings.max_order_value_usd,
    )
    context = (
        f"Task: {state['task']}\n"
        f"Store brand set: {'yes — ' + state['store_brand'].get('store_name','?') if state.get('store_brand') else 'NO — must run store_setup first'}\n"
        f"Products found: {len(state.get('trending_products', []))}\n"
        f"Shopify products created: {len(state.get('shopify_products_created', []))}\n"
        f"Campaign IDs: {state.get('campaign_ids', [])}\n"
        f"Fulfilled orders: {len(state.get('fulfilled_orders', []))}\n"
        f"Budget remaining: ${state.get('budget_remaining_usd', 0):.2f}\n"
        f"Last error: {state.get('error') or 'none'}\n"
    )

    agent_log("Deciding next step...", "info")
    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=context)])
    raw = str(response.content).strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    parsed = json.loads(raw.strip())

    next_node = parsed["next"]
    reasoning = parsed.get("reasoning", "")
    agent_log(f"→ {next_node}  ({reasoning})", "action")

    return {
        "next_agent": next_node,
        "director_reasoning": reasoning,
        "messages": [response],
    }


def route_director(state: AgentState) -> str:
    """Conditional edge: maps next_agent to the correct LangGraph node."""
    return state.get("next_agent", "END")
