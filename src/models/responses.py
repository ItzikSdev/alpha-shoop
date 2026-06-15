"""Pydantic response models for all FastAPI endpoints."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


class AgentRunResponse(BaseModel):
    """Returned when a new agent run is triggered."""
    thread_id: str = Field(..., description="LangGraph thread ID — use to poll status")
    status: RunStatus = RunStatus.PENDING
    message: str = "Agent graph started"


class RunStatusResponse(BaseModel):
    """Polling response for a running agent thread."""
    thread_id: str
    status: RunStatus
    current_node: Optional[str] = None
    products_found: int = 0
    orders_placed: int = 0
    ad_spend_usd: float = 0.0
    error: Optional[str] = None
    result: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    services: dict[str, str] = Field(
        default_factory=dict,
        description="Status of downstream services: database, redis, anthropic",
    )


class KillSwitchResponse(BaseModel):
    killed: bool
    threads_stopped: int
    message: str


class WebhookAck(BaseModel):
    received: bool = True
    order_id: Optional[int] = None
    queued_for: Optional[str] = None


class TrendingProduct(BaseModel):
    product_id: str
    title: str
    source: str
    price_supplier_usd: float
    estimated_price_shopify_usd: float
    margin_pct: float
    shipping_days: int
    trend_score: int = Field(ge=0, le=100)


class ToolCallResponse(BaseModel):
    """Response from a direct MCP tool invocation."""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
