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

    # Scraper results
    trending_products: list[dict]        # raw product candidates

    # Sourcing loop: ecommerce_manager rejects off-niche candidates and asks
    # trend_scraper to retry with adjusted search terms (max 3 attempts)
    sourcing_attempts: int                # how many scrape→validate passes have run
    sourcing_feedback: Optional[str]      # why the last batch was rejected, for the next search
    search_category_used: Optional[str]   # the (possibly relaxed) term trend_scraper actually searched —
                                           # ecommerce_manager validates against this, not the raw brief text

    # Evaluator self-correction loop (docs/prompt.md §2): the Evaluator node scores
    # each candidate's NET margin (after 18% VAT + payment fees, via src/agents/pricing.py)
    # and, if the best batch is below target, increments loop_counter and routes back to
    # the Product Hunter (trend_scraper). Hard cap max_loops=3 → workflow_status="failed".
    loop_counter: int                     # how many Evaluator → Hunter self-correction loops have run
    pricing_calc: Optional[dict]          # last Evaluator verdict: best/threshold/approved candidates
    workflow_status: Optional[str]        # running | approved | failed

    # E-commerce results
    shopify_products_created: list[str]  # Shopify product IDs

    # Marketing results
    campaign_ids: list[str]
    total_ad_spend_usd: float

    # Fulfillment results
    fulfilled_orders: list[str]

    # Multi-store: which store this run targets (None = use env config)
    store_id: Optional[str]

    # Store branding (set once by store_setup node)
    store_brand: Optional[dict]

    # Design loop
    store_designed: bool           # True once design_agent approves the result
    design_spec: Optional[dict]    # Quality checklist + CSS produced by design_agent Mode 1
    design_iterations: int         # How many frontend_agent passes have run
    design_approved: bool          # design_agent approved the implementation
    frontend_report: Optional[str] # Summary of what frontend_agent last changed

    # Store health: revenue + sales data fetched at run start (for director routing)
    store_health: Optional[dict]

    # Agentic RAG: store description knowledge relevant to this task, fetched once at run start
    store_knowledge: Optional[list]

    # Guardrails
    budget_remaining_usd: float
    kill_switch_triggered: bool
    run_complete: bool
    error: Optional[str]
