"""LangGraph AgentState — the shared state TypedDict passed between all nodes."""
from __future__ import annotations
from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Central state object flowing through the LangGraph StateGraph.
    Every agent node reads from and writes to this state.
    """
    # Core task
    task: str
    thread_id: str
    operator: str

    # LangGraph message accumulator (append-only via add_messages reducer)
    messages: Annotated[list, add_messages]

    # Director routing
    next_agent: Optional[str]            # which worker to call next
    director_reasoning: Optional[str]    # chain-of-thought from director

    # Scraper results
    trending_products: list[dict]        # raw product candidates

    # E-commerce results
    shopify_products_created: list[str]  # Shopify product IDs

    # Marketing results
    campaign_ids: list[str]
    total_ad_spend_usd: float

    # Fulfillment results
    fulfilled_orders: list[str]

    # Guardrails
    budget_remaining_usd: float
    kill_switch_triggered: bool
    run_complete: bool
    error: Optional[str]
