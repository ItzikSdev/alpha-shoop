"""Fulfillment Agent — places supplier orders and updates Shopify tracking."""
from __future__ import annotations
from langchain_core.messages import HumanMessage
from src.agents.state import AgentState
from src.mcp_tools.fulfillment import place_supplier_order, fulfill_shopify_order
from src.tracing.context import current_node


async def fulfillment_node(state: AgentState) -> dict:
    """LangGraph node: places CJ/AliExpress orders and pushes tracking to Shopify."""
    current_node.set("fulfillment_agent")
    fulfilled: list[str] = []

    for order in state.get("pending_orders", []):
        supplier_result = await place_supplier_order(
            product_id=order.get("product_id", ""),
            quantity=order.get("quantity", 1),
            shipping_address=order.get("shipping_address", {}),
            order_reference=order.get("shopify_order_id", ""),
        )

        tracking = supplier_result.get("tracking_number")
        if tracking:
            await fulfill_shopify_order(
                shopify_order_id=order.get("shopify_order_id", ""),
                tracking_number=tracking,
                carrier=supplier_result.get("carrier", "CJ Dropshipping"),
                tracking_url=f"https://t.17track.net/en#{tracking}",
            )
            fulfilled.append(order.get("shopify_order_id", ""))

    return {
        "fulfilled_orders": state.get("fulfilled_orders", []) + fulfilled,
        "messages": [HumanMessage(content=f"Fulfilled {len(fulfilled)} orders")],
    }
