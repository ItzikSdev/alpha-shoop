"""
SQLAlchemy 2.0 ORM models.

`product_mappings` is the critical cross-reference table:
  Shopify Order Webhook arrives → look up supplier_product_id + supplier_sku
  → place the dropshipping order automatically.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductMapping(Base):
    """
    One row per Shopify product listed through the arbitrage pipeline.

    Lifecycle:
      1. Created by create_shopify_product MCP tool after Shopify API call.
      2. google_campaign_id updated by create_google_campaign MCP tool.
      3. Read by the fulfillment_agent when a Shopify Order Webhook fires.
    """

    __tablename__ = "product_mappings"

    # ── Primary key ───────────────────────────────────────────────────────────
    shopify_product_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Shopify product GID, e.g. gid://shopify/Product/123",
    )

    # ── Which store this belongs to (this system runs multiple stores) ────────
    store_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Our internal store UUID — which Shopify store/credentials to use",
    )

    # ── Supplier cross-reference ──────────────────────────────────────────────
    supplier_product_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="CJ Dropshipping product PID",
    )
    supplier_sku: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="CJ variant SKU used when placing the supplier order",
    )

    # ── Financials ─────────────────────────────────────────────────────────────
    cost_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Supplier cost in USD at time of listing",
    )
    retail_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Shopify selling price in USD",
    )

    # ── Ads ───────────────────────────────────────────────────────────────────
    google_campaign_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        comment="Google Ads campaign ID (empty until marketing_agent runs)",
    )

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"ProductMapping("
            f"shopify={self.shopify_product_id!r}, "
            f"supplier={self.supplier_product_id!r}, "
            f"margin={self._margin_pct():.1f}%)"
        )

    def _margin_pct(self) -> float:
        if not self.retail_price or self.retail_price == 0:
            return 0.0
        return float((self.retail_price - self.cost_price) / self.retail_price * 100)
