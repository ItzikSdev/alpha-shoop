"""Director Agent — routes to the correct worker via the LiteLLM proxy."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.state import AgentState
from src.config import get_settings
from src.llm import get_llm
from src.tracing.context import current_node

_SYSTEM_PROMPT = """\
You are the Director Agent in an autonomous e-commerce arbitrage system.
Your job is to analyse the current state and decide which worker to invoke next.

Workers available:
- trend_scraper    : Find trending products on CJ/AliExpress
- ecommerce_manager: Create and manage Shopify products
- marketing_agent  : Launch Google/Meta ad campaigns
- fulfillment_agent: Place supplier orders and update tracking
- END              : The task is complete, stop the graph

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
        f"Products found: {len(state.get('trending_products', []))}\n"
        f"Shopify products created: {len(state.get('shopify_products_created', []))}\n"
        f"Campaign IDs: {state.get('campaign_ids', [])}\n"
        f"Fulfilled orders: {len(state.get('fulfilled_orders', []))}\n"
        f"Budget remaining: ${state.get('budget_remaining_usd', 0):.2f}\n"
        f"Last error: {state.get('error') or 'none'}\n"
    )

    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=context)])
    parsed = json.loads(str(response.content))

    return {
        "next_agent": parsed["next"],
        "director_reasoning": parsed.get("reasoning", ""),
        "messages": [response],
    }


def route_director(state: AgentState) -> str:
    """Conditional edge: maps next_agent to the correct LangGraph node."""
    return state.get("next_agent", "END")
