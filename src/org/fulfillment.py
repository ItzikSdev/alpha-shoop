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

from datetime import datetime, timezone

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
        # fulfill_shopify_order's return value used to be discarded too — the
        # false-success pattern fixed in Reel's video classifier. The CJ order
        # itself (the expensive, hard-to-undo part) already succeeded above, so
        # a failure here isn't escalated to Sol as a fulfillment failure — it's
        # reported honestly instead of silently hidden behind a green checkmark.
        warnings: list[str] = []
        email_confirmed: bool | None = False
        if tracking:
            fulfill_started_at = datetime.now(timezone.utc).isoformat()
            fres = await fulfill_shopify_order(
                shopify_order_id=str(payload.id), tracking_number=tracking,
                carrier="CJ Dropshipping", tracking_url=f"https://t.17track.net/en#{tracking}",
            )
            if fres.get("error"):
                warnings.append(f"tracking NOT attached to the Shopify order: {fres['error']}")
            else:
                email_confirmed = await _verify_shipping_email(payload, fulfill_started_at)

        if store.support_email and not email_confirmed:
            # Milo has no working email path of his own (no Gmail OAuth set up,
            # and none is planned — see docs/sol_integrations_rag_fulfillment_email.md).
            # Nora's Resend-based path (src/mcp_tools/support_inbox.py, already
            # live for support replies) is the fallback for the WHOLE system now,
            # not just customer-initiated replies. Called directly rather than
            # via dispatch_to_agent — Nora has no dispatch_to_agent handler
            # wired (deliberately untouched), so routing through it would just
            # produce a chat reply from her generic fallback, not a real send —
            # exactly the narrated-but-not-executed trap this whole day was
            # about avoiding.
            nres = await _fallback_email_via_nora(payload, store, tracking)
            await _log_nora_fallback_edge(payload)
            if nres.get("error"):
                warnings.append(f"customer email NOT sent (Shopify unconfirmed, Nora "
                                f"fallback also failed): {nres['error']}")
            else:
                await _say(f"📧 Order #{payload.id}: Shopify's own shipping email wasn't "
                          "confirmed sent — Nora sent the update instead.")

        if warnings:
            desc = (f"Order {payload.id} ({payload.email}) — CJ supplier order placed "
                     f"successfully, but: " + "; ".join(warnings))
            await _say(f"⚠️ Order #{payload.id} placed with CJ, but {'; '.join(warnings)} "
                        "— opening a ticket.")
            open_ticket(
                title=f"Order {payload.id} shipped but needs follow-up",
                description=desc, source="order_partial_failure", store_id=store.store_id,
                dedupe_key=f"order_partial_{payload.id}",
            )
            return {"ok": True, "fulfilled": len(results), "tracking": tracking, "warnings": warnings}

        await _say(f"✅ Order #{payload.id} shipped — {len(results)} item(s)"
                    + (f", tracking {tracking}" if tracking else "") + ".")
        return {"ok": True, "fulfilled": len(results), "tracking": tracking}
    finally:
        _current_store.reset(token)


async def _verify_shipping_email(payload: ShopifyOrderWebhook, since_iso: str) -> bool | None:
    """Check Shopify's own Order.events timeline for a confirmed mail_sent
    shipping-notification event (see shopify.check_shipping_email_sent's
    docstring for what this can and can't actually confirm — send-accepted,
    not delivered/not-bounced; Shopify exposes nothing for the latter).
    Logs a real EXECUTED edge either way so the check itself is visible in
    the knowledge graph, not just in logs/tickets."""
    from src.graph.knowledge_graph import log_tool_execution
    from src.mcp_tools.shopify import check_shipping_email_sent

    confirmed = await check_shipping_email_sent(str(payload.id), since_iso)
    await log_tool_execution(
        AGENT_NAME, "shopify_email_delivery_check", ok=bool(confirmed),
        detail=f"order {payload.id}: {'confirmed sent' if confirmed else 'not confirmed' if confirmed is False else 'check inconclusive'}",
    )
    return confirmed


async def _fallback_email_via_nora(payload: ShopifyOrderWebhook, store: StoreConfig, tracking: str | None) -> dict:
    """Nora's real, working send path (Resend — see support_inbox.py's Rule 3),
    called directly rather than through dispatch_to_agent (see the caller's
    comment for why). Same email content process_order used to send itself."""
    from src.mcp_tools.support_inbox import send_reply_via_resend

    body = (
        f"Hi,\n\nYour order #{payload.id} has been placed with our fulfillment partner"
        + (f" — tracking number: {tracking}." if tracking else ".")
        + f"\n\nThanks for shopping with us!\n{store.name} Support"
    )
    return await send_reply_via_resend(
        from_addr=store.support_email, to_addr=payload.email,
        subject=f"Your order #{payload.id} is on its way!", body=body,
        store_name=store.name, store_slug=store.store_id,
    )


async def _log_nora_fallback_edge(payload: ShopifyOrderWebhook) -> None:
    """(Milo)-[:ASSIGNED]->(Nora) in the knowledge graph — same fix applied to
    Sol's delegation logging earlier: the ask must be visible in the graph
    even though this is a direct function call, not a dispatch_to_agent hop,
    so Nova's gap-detection (or any future check) can see the order->email
    lifecycle without another full investigation."""
    try:
        from src.graph.knowledge_graph import log_delegation
        await log_delegation(AGENT_NAME, "Nora",
                             f"Send shipping/order update for order {payload.id} — "
                             "Shopify's own notification wasn't confirmed sent")
    except Exception:  # noqa: BLE001
        pass


async def _escalate(payload: ShopifyOrderWebhook, store: StoreConfig, errors: list[str], fulfilled: int) -> None:
    """A fulfillment error is a real exception, not a retryable transient — open a
    ticket and hand the specific failure to Sol's LLM loop so it can investigate,
    retry with judgment, and email the customer about the delay if warranted."""
    desc = f"Order {payload.id} ({payload.email}) fulfillment error(s): " + "; ".join(errors)
    from src.org.telegram import post_escalation
    await post_escalation(
        AGENT_NAME, AGENT_ROLE,
        f"Order #{payload.id} ({store.name}) hit a problem: {'; '.join(errors)[:300]} — "
        "opening a ticket for Sol to investigate.",
    )
    ticket = open_ticket(
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
            # Without this, update_ticket(..., "doing") never fired: open_ticket()'s
            # return was discarded and the ticket sat in 'todo' even while Sol worked it.
            ticket_id=ticket.id if ticket else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not hand fulfillment failure for order %s to Sol: %s", payload.id, exc)
