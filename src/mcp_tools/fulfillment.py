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


async def fulfill_shopify_order(
    shopify_order_id: str,
    tracking_number: str,
    carrier: str,
    tracking_url: str,
) -> dict:
    """
    Mark a Shopify order as fulfilled with tracking info.

    Args:
        shopify_order_id: Shopify order ID (numeric string)
        tracking_number: Carrier tracking number
        carrier: Carrier name (e.g. "CJ Packet", "YunExpress")
        tracking_url: Full tracking URL

    Returns:
        Dict with keys: fulfillment_id (str), status (str)
    """
    # Prefer the active store's own credentials (the .env defaults are often a
    # stale token); fall back to settings only if no store context is set.
    settings = get_settings()
    domain, token = settings.shopify_store_domain, settings.shopify_access_token
    try:
        from src.stores import _current_store
        store = _current_store.get(None)
        if store:
            domain, token = store.shopify_domain, store.shopify_access_token
    except Exception:
        pass
    url = f"https://{domain}/admin/api/2024-07/orders/{shopify_order_id}/fulfillments.json"
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            json={"fulfillment": {"tracking_number": tracking_number, "tracking_company": carrier, "tracking_url": tracking_url, "notify_customer": True}},
            headers={"X-Shopify-Access-Token": token},
        )
    if resp.status_code >= 400:
        return {"error": resp.text[:200], "status_code": resp.status_code}
    data = resp.json().get("fulfillment", {})
    return {"fulfillment_id": str(data.get("id", "")), "status": data.get("status", "success")}
