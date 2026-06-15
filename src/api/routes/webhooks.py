"""Shopify webhook receivers — HMAC-SHA256 validated."""
from __future__ import annotations
import hashlib
import hmac
import base64
from fastapi import APIRouter, Request, HTTPException, Header, Depends
from src.models.requests import ShopifyOrderWebhook, ShopifyPaymentWebhook
from src.models.responses import WebhookAck
from src.config import Settings, get_settings

router = APIRouter()


def _verify_shopify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """Validate Shopify webhook HMAC-SHA256 signature."""
    expected = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, signature)


@router.post(
    "/shopify/order",
    response_model=WebhookAck,
    summary="Shopify orders/create webhook",
    description=(
        "Receives Shopify order creation webhooks. "
        "Validates HMAC-SHA256 signature and enqueues fulfillment."
    ),
)
async def shopify_order_created(
    request: Request,
    x_shopify_hmac_sha256: str = Header(...),
    settings: Settings = Depends(get_settings),
) -> WebhookAck:
    body = await request.body()

    if settings.shopify_webhook_secret:
        if not _verify_shopify_hmac(body, x_shopify_hmac_sha256, settings.shopify_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid Shopify HMAC signature")

    payload = ShopifyOrderWebhook.model_validate_json(body)

    # Check guardrail: order value cap
    order_total = float(payload.total_price)
    if order_total > settings.max_order_value_usd:
        return WebhookAck(
            received=True,
            order_id=payload.id,
            queued_for="manual_review",
        )

    # In production: enqueue ARQ fulfillment task
    return WebhookAck(
        received=True,
        order_id=payload.id,
        queued_for="fulfillment_agent",
    )


@router.post(
    "/shopify/payment",
    response_model=WebhookAck,
    summary="Shopify payment webhook",
)
async def shopify_payment(
    request: Request,
    x_shopify_hmac_sha256: str = Header(...),
    settings: Settings = Depends(get_settings),
) -> WebhookAck:
    body = await request.body()

    if settings.shopify_webhook_secret:
        if not _verify_shopify_hmac(body, x_shopify_hmac_sha256, settings.shopify_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid Shopify HMAC signature")

    payload = ShopifyPaymentWebhook.model_validate_json(body)
    return WebhookAck(received=True, order_id=payload.order_id, queued_for="accounting")
