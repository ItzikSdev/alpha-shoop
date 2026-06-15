"""Tests: Shopify webhook endpoints."""
from __future__ import annotations
import hashlib
import hmac
import base64
import json
import pytest
from httpx import AsyncClient
from src.config import get_settings


def _shopify_sig(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


VALID_ORDER = {
    "id": 12345,
    "email": "customer@example.com",
    "financial_status": "paid",
    "total_price": "49.99",
    "currency": "USD",
    "line_items": [{"product_id": 111, "quantity": 1, "title": "Test Product"}],
}


@pytest.mark.asyncio
async def test_shopify_order_webhook_no_secret(client: AsyncClient, settings):
    """When no webhook secret is configured, HMAC check is skipped."""
    original = settings.shopify_webhook_secret
    settings.shopify_webhook_secret = ""

    body = json.dumps(VALID_ORDER).encode()
    resp = await client.post(
        "/webhook/shopify/order",
        content=body,
        headers={"Content-Type": "application/json", "X-Shopify-Hmac-Sha256": "dummy"},
    )
    assert resp.status_code == 200
    assert resp.json()["received"] is True

    settings.shopify_webhook_secret = original


@pytest.mark.asyncio
async def test_shopify_order_invalid_hmac(client: AsyncClient, settings):
    """When webhook secret is set, invalid HMAC returns 401."""
    settings.shopify_webhook_secret = "test-secret"
    body = json.dumps(VALID_ORDER).encode()

    resp = await client.post(
        "/webhook/shopify/order",
        content=body,
        headers={"Content-Type": "application/json", "X-Shopify-Hmac-Sha256": "bad-sig"},
    )
    assert resp.status_code == 401
    settings.shopify_webhook_secret = ""


@pytest.mark.asyncio
async def test_shopify_order_valid_hmac(client: AsyncClient, settings):
    settings.shopify_webhook_secret = "test-secret"
    body = json.dumps(VALID_ORDER).encode()
    sig = _shopify_sig(body, "test-secret")

    resp = await client.post(
        "/webhook/shopify/order",
        content=body,
        headers={"Content-Type": "application/json", "X-Shopify-Hmac-Sha256": sig},
    )
    assert resp.status_code == 200
    assert resp.json()["order_id"] == 12345
    settings.shopify_webhook_secret = ""


@pytest.mark.asyncio
async def test_shopify_order_over_limit_queued_for_review(client: AsyncClient, settings):
    """Orders above MAX_ORDER_VALUE are queued for manual review."""
    settings.shopify_webhook_secret = ""
    expensive_order = {**VALID_ORDER, "total_price": "999.99"}
    body = json.dumps(expensive_order).encode()

    resp = await client.post(
        "/webhook/shopify/order",
        content=body,
        headers={"Content-Type": "application/json", "X-Shopify-Hmac-Sha256": "dummy"},
    )
    assert resp.status_code == 200
    assert resp.json()["queued_for"] == "manual_review"
