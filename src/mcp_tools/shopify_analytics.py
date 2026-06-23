"""Shopify Analytics — revenue, orders, and store health via Admin REST API."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from src.mcp_tools.shopify import _shopify_rest


async def get_sales_summary(days: int = 7) -> dict:
    """
    Fetch order count + revenue for the last N days.

    Returns:
        order_count, revenue_usd, period_days, status: "no_sales" | "low" | "healthy" | "unknown"
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        data = await _shopify_rest(
            "GET",
            f"orders.json?status=paid&created_at_min={since}&fields=id,total_price&limit=250",
        )
        orders = data.get("orders", [])
        order_count = len(orders)
        revenue = sum(float(o.get("total_price", 0)) for o in orders)

        if order_count == 0:
            health = "no_sales"
        elif revenue < 50:
            health = "low"
        else:
            health = "healthy"

        return {
            "order_count": order_count,
            "revenue_usd": round(revenue, 2),
            "period_days": days,
            "status": health,
        }
    except Exception as exc:
        return {
            "order_count": 0,
            "revenue_usd": 0.0,
            "period_days": days,
            "status": "unknown",
            "error": str(exc),
        }
