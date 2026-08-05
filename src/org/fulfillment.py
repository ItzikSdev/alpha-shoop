"""
Automatic order fulfillment — Shopify order webhook -> CJ supplier order -> tracking
+ customer email.

Deterministic on the happy path (no LLM call): cheap, fast, predictable. Sol's
`cj_add_product` (src/org/agent_loop.py) already stores the CJ variant id directly as
the Shopify variant's `sku`, so an order line item's `sku` IS the CJ vid — no separate
product-mapping table is needed to fulfill it.

Only genuine exceptions (CJ order failure, an item with no sku, a bad address) escalate
to a ticket + Sol's own LLM reasoning loop (`run_sol_task`) instead of a scripted retry.
"""
from __future__ import annotations

import logging

from src.mcp_tools.email import send_email
from src.mcp_tools.fulfillment import fulfill_shopify_order, place_supplier_order
from src.models.requests import ShopifyOrderWebhook
from src.org.telegram import post_as
from src.org.tickets import open_ticket
from src.stores import StoreConfig, _current_store

logger = logging.getLogger(__name__)

AGENT_NAME = "Milo"
AGENT_ROLE = "Fulfillment"


async def _say(text: str) -> None:
    try:
        await post_as(AGENT_NAME, AGENT_ROLE, text)
    except Exception:  # noqa: BLE001
        pass  # never let Telegram narration break a real fulfillment


async def process_order(payload: ShopifyOrderWebhook, store: StoreConfig) -> dict:
    """Fulfill one Shopify order end to end. Sets `store` as the active store
    (ContextVar) for the duration so `place_supplier_order`/`fulfill_shopify_order`/
    `send_email` all use THIS store's supplier/Shopify/email credentials."""
    token = _current_store.set(store)
    await _say(f"📦 New order #{payload.id} ({store.name}) — placing with CJ Dropshipping…")
    try:
        address = payload.shipping_address or {}
        country_code = (address.get("country_code") or address.get("countryCode") or "").strip()
        shipping = {**address, "countryCode": country_code}

        results: list[dict] = []
        errors: list[str] = []
        for item in payload.line_items:
            sku = item.get("sku") or ""
            qty = int(item.get("quantity") or 1)
            if not sku:
                errors.append(f"line item {item.get('title', '?')!r} has no sku (not a CJ-sourced product?)")
                continue
            supplier_result = await place_supplier_order(
                product_id=sku, quantity=qty, shipping_address=shipping,
                order_reference=str(payload.id),
            )
            if supplier_result.get("error"):
                errors.append(f"sku {sku}: {supplier_result['error']}")
                continue
            results.append(supplier_result)

        if errors:
            await _escalate(payload, store, errors, fulfilled=len(results))
            return {"ok": False, "errors": errors, "fulfilled": len(results)}

        tracking = results[0].get("tracking_number") if results else None
        if tracking:
            await fulfill_shopify_order(
                shopify_order_id=str(payload.id), tracking_number=tracking,
                carrier="CJ Dropshipping", tracking_url=f"https://t.17track.net/en#{tracking}",
            )
        if store.support_email:
            await send_email(
                to=payload.email,
                subject=f"Your order #{payload.id} is on its way!",
                body=(
                    f"Hi,\n\nYour order #{payload.id} has been placed with our fulfillment partner"
                    + (f" — tracking number: {tracking}." if tracking else ".")
                    + f"\n\nThanks for shopping with us!\n{store.name} Support"
                ),
            )
        await _say(f"✅ Order #{payload.id} shipped — {len(results)} item(s)"
                    + (f", tracking {tracking}" if tracking else "") + ".")
        return {"ok": True, "fulfilled": len(results), "tracking": tracking}
    finally:
        _current_store.reset(token)


async def _escalate(payload: ShopifyOrderWebhook, store: StoreConfig, errors: list[str], fulfilled: int) -> None:
    """A fulfillment error is a real exception, not a retryable transient — open a
    ticket and hand the specific failure to Sol's LLM loop so it can investigate,
    retry with judgment, and email the customer about the delay if warranted."""
    desc = f"Order {payload.id} ({payload.email}) fulfillment error(s): " + "; ".join(errors)
    await _say(f"⚠️ Order #{payload.id} ({store.name}) hit a problem: {'; '.join(errors)[:300]} — opening a ticket for Sol to investigate.")
    open_ticket(
        title=f"Fulfillment failed for order {payload.id}",
        description=desc, source="order_failure", store_id=store.store_id,
        dedupe_key=f"order_failure_{payload.id}",
    )
    try:
        from src.org.agent_loop import run_sol_task
        await run_sol_task(
            f"Fulfillment failed for order {payload.id}: {'; '.join(errors)}. Investigate "
            "(check cj_product_inventory / search_local_catalog for the sku, retry "
            "place_supplier_order via shopify_admin if it looks transient) and post what you "
            f"find. If it can't be resolved quickly, flag that this order's customer "
            f"({payload.email}) needs a delay email — Milo/Nora will send it; you have no "
            "customer-email tool yourself.",
            store_slug=store.store_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not hand fulfillment failure for order %s to Sol: %s", payload.id, exc)
