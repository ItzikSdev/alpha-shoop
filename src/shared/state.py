"""
SharedArbitrageState — the single source of truth that flows through
every LangGraph node in one product execution pipeline.

Usage with StateGraph:
    from langgraph.graph import StateGraph
    graph = StateGraph(SharedArbitrageState)
"""
from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field


class SharedArbitrageState(BaseModel):
    """
    Pydantic v2 model used as the LangGraph state for a single arbitrage pipeline run.

    Each node returns a dict with ONLY the fields it populates; LangGraph merges
    them into the existing state via model_copy(update=node_result).

    The `messages` field uses the add_messages reducer — LangGraph appends to it
    instead of replacing, giving a full audit trail of agent reasoning.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ── Sourcing ──────────────────────────────────────────────────────────────
    # Populated by: trend_scraper node
    target_keyword: str = ""
    supplier_product_id: str = ""
    supplier_price: float = 0.0
    supplier_sku: str = ""
    product_images: list[str] = Field(default_factory=list)

    # ── Market Validation ─────────────────────────────────────────────────────
    # Populated by: market_validator node
    estimated_market_price: float = 0.0
    arbitrage_margin_approved: bool = False

    # ── Store & Ads ────────────────────────────────────────────────────────────
    # Populated by: ecommerce_manager node + marketing_agent node
    shopify_product_id: str = ""
    final_retail_price: float = 0.0
    store_url: str = ""
    google_campaign_id: str = ""

    # ── Pipeline control ──────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    error: Optional[str] = None
    pipeline_complete: bool = False

    # ── Computed helpers ───────────────────────────────────────────────────────

    @property
    def gross_margin_pct(self) -> float:
        """Gross margin % based on final retail vs supplier price."""
        if self.final_retail_price <= 0 or self.supplier_price <= 0:
            return 0.0
        return round(
            (self.final_retail_price - self.supplier_price) / self.final_retail_price * 100,
            2,
        )

    @property
    def is_ready_for_fulfillment(self) -> bool:
        """True when the pipeline has all data needed to fulfill an order."""
        return bool(
            self.shopify_product_id
            and self.supplier_product_id
            and self.supplier_sku
            and self.supplier_price > 0
        )
