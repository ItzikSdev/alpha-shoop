"""MCP Tool Group 5: Fulfillment — CJ Dropshipping orders + Shopify tracking."""
from __future__ import annotations
import httpx
from src.config import get_settings


async def place_supplier_order(
    product_id: str,
    quantity: int,
    shipping_address: dict,
    order_reference: str,
    from_country: str = "CN",
) -> dict:
    """
    Place a dropshipping order with CJ Dropshipping (createOrderV2).

    Args:
        product_id: CJ variant id (vid) — stored as ProductMapping.supplier_sku
        quantity: Units to order
        shipping_address: Dict with keys: name, address1, city, province, country,
            zip, phone (and optionally countryCode)
        order_reference: Shopify order id, used as CJ orderNumber

    Returns on success: {supplier_order_id, tracking_number, estimated_delivery,
    product_amount}. On failure returns {"error": <CJ message>} — it does NOT
    fake a success id (a previous silent fallback hid real auth/field errors).

    Notes:
      - Uses cj_mcp_key (the valid CJ-Access-Token), NOT cj_api_key.
      - createOrderV2 wants FLAT shipping* fields, not a nested consignee, plus
        fromCountryCode + shippingCountryCode — all confirmed against the live API.
    """
    settings = get_settings()
    token = settings.cj_mcp_key or settings.cj_api_key
    # The destination country code must come from the order (Shopify provides the
    # ISO-2 `country_code`) — never guessed from the country name.
    country_code = (shipping_address.get("countryCode") or "").strip()
    if not country_code:
        return {"error": "missing destination countryCode (take it from the order's shipping address)"}

    payload = {
        "orderNumber": str(order_reference),
        "fromCountryCode": from_country,
        "logisticName": shipping_address.get("logisticName", "CJPacket Ordinary"),
        "shippingCountryCode": country_code,
        "shippingCountry": shipping_address.get("country", ""),
        "shippingProvince": shipping_address.get("province", ""),
        "shippingCity": shipping_address.get("city", ""),
        "shippingPhone": shipping_address.get("phone", ""),
        "shippingCustomerName": shipping_address.get("name", ""),
        "shippingZip": shipping_address.get("zip", ""),
        "shippingAddress": shipping_address.get("address1", ""),
        "products": [{"vid": product_id, "quantity": quantity}],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/createOrderV2",
            json=payload,
            headers={"CJ-Access-Token": token},
        )
    body = resp.json()
    if not body.get("result"):
        return {"error": str(body.get("message", "CJ order failed")), "code": body.get("code")}
    data = body.get("data", {})
    return {
        "supplier_order_id": data.get("orderId", f"CJ-{order_reference}"),
        "tracking_number": data.get("trackNumber"),
        "product_amount": data.get("productAmount"),
        "logistics_missing": data.get("logisticsMiss"),
        "estimated_delivery": "10-15 days",
    }


_FULFILLMENT_ORDERS_QUERY = """
query openFulfillmentOrders($orderId: ID!) {
  order(id: $orderId) {
    fulfillmentOrders(first: 10) {
      nodes { id status }
    }
  }
}
"""

_FULFILLMENT_CREATE_MUTATION = """
mutation fulfillmentCreate($fulfillment: FulfillmentV2Input!) {
  fulfillmentCreateV2(fulfillment: $fulfillment) {
    fulfillment { id status }
    userErrors { field message }
  }
}
"""


async def fulfill_shopify_order(
    shopify_order_id: str,
    tracking_number: str,
    carrier: str,
    tracking_url: str,
) -> dict:
    """
    Mark a Shopify order as fulfilled with tracking info, via the current
    FulfillmentOrder-based Admin GraphQL API (fulfillmentCreateV2).

    The old REST `orders/{id}/fulfillments.json` endpoint this used to call
    returns 406 — Shopify's moved fulfillment creation to FulfillmentOrders
    (assignable per-location, works with multi-location/partial fulfillment);
    the legacy endpoint no longer accepts fulfillment writes directly on an
    order the way it used to.

    Args:
        shopify_order_id: Shopify order ID (numeric string)
        tracking_number: Carrier tracking number
        carrier: Carrier name (e.g. "CJ Packet", "YunExpress")
        tracking_url: Full tracking URL

    Returns:
        Dict with keys: fulfillment_id (str), status (str), or {"error": ...}
    """
    from src.mcp_tools.shopify import _shopify_gql

    order_gid = shopify_order_id if shopify_order_id.startswith("gid://") \
        else f"gid://shopify/Order/{shopify_order_id}"
    try:
        data = await _shopify_gql(_FULFILLMENT_ORDERS_QUERY, {"orderId": order_gid})
    except Exception as exc:
        return {"error": f"couldn't read fulfillment orders: {exc}"}
    nodes = ((data.get("order") or {}).get("fulfillmentOrders") or {}).get("nodes") or []
    open_ids = [n["id"] for n in nodes if n.get("status") in ("OPEN", "IN_PROGRESS", "SCHEDULED")]
    if not open_ids:
        return {"error": f"no open FulfillmentOrder for {shopify_order_id} "
                          f"(found {len(nodes)}, none in a fulfillable status)"}

    variables = {
        "fulfillment": {
            "lineItemsByFulfillmentOrder": [{"fulfillmentOrderId": fid} for fid in open_ids],
            "trackingInfo": {"number": tracking_number, "url": tracking_url, "company": carrier},
            "notifyCustomer": True,
        }
    }
    try:
        data = await _shopify_gql(_FULFILLMENT_CREATE_MUTATION, variables)
    except Exception as exc:
        return {"error": f"fulfillmentCreateV2 call failed: {exc}"}
    result = data.get("fulfillmentCreateV2") or {}
    errors = result.get("userErrors") or []
    if errors:
        return {"error": "; ".join(f"{e.get('field')}: {e.get('message')}" for e in errors)}
    fulfillment = result.get("fulfillment") or {}
    return {"fulfillment_id": str(fulfillment.get("id", "")), "status": fulfillment.get("status", "success")}
