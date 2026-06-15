"""Pydantic request models for all FastAPI endpoints."""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class RunAgentRequest(BaseModel):
    """Trigger the LangGraph multi-agent graph."""
    task: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Natural-language arbitrage task",
        examples=["Find trending electronics products under $50 with >30% margin"],
    )
    thread_id: Optional[str] = Field(
        None,
        description="Resume an existing LangGraph thread (leave blank to start new)",
    )
    max_budget_usd: float = Field(
        100.0,
        gt=0,
        le=500,
        description="Max total ad spend for this run (hard-capped by guardrail at $500/day)",
    )
    target_categories: list[str] = Field(
        default_factory=list,
        examples=[["electronics", "home-garden"]],
    )
    dry_run: bool = Field(False, description="Simulate without placing real orders")


class KillSwitchRequest(BaseModel):
    """Emergency stop — halts all active agent runs."""
    reason: str = Field(..., min_length=5)
    operator: str = Field(..., description="Operator name or email for audit log")


class ShopifyOrderWebhook(BaseModel):
    """Shopify order/create webhook payload (simplified)."""
    id: int
    email: str
    financial_status: str
    fulfillment_status: Optional[str] = None
    total_price: str
    currency: str = "USD"
    line_items: list[dict]
    shipping_address: Optional[dict] = None

    @field_validator("total_price")
    @classmethod
    def price_is_numeric(cls, v: str) -> str:
        if not re.match(r"^\d+(\.\d{1,2})?$", v):
            raise ValueError("total_price must be a numeric string")
        return v


class ShopifyPaymentWebhook(BaseModel):
    """Shopify payment webhook payload."""
    id: int
    order_id: int
    amount: str
    currency: str
    gateway: str
    status: str


class TestToolRequest(BaseModel):
    """Run a single MCP tool directly (for testing/dev)."""
    tool_name: str = Field(..., description="e.g. search_trending_products")
    arguments: dict = Field(default_factory=dict)
