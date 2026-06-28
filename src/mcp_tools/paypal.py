"""
PayPal (REST API) — read-only money signals for the agents.

Lets Linus/Grace see REAL payment data (recent transactions + account balance) so
profitability reasoning is grounded in money actually received, not just Shopify's
order view. Read-only by design: no payouts, no refunds, no money movement — the
tools only GET. Credentials come from .env (paypal_client_id / paypal_secret);
never hardcode them. Live vs sandbox is controlled by settings.paypal_live.

Requires the PayPal app to have "Transaction Search" enabled (App → Features).
If it isn't, PayPal returns a clear permission error, surfaced as {"error": ...}.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from src.config import get_settings


def _base() -> str:
    return "https://api-m.paypal.com" if get_settings().paypal_live else "https://api-m.sandbox.paypal.com"


async def _token(client: httpx.AsyncClient) -> str:
    s = get_settings()
    resp = await client.post(
        f"{_base()}/v1/oauth2/token",
        auth=(s.paypal_client_id, s.paypal_secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def get_paypal_transactions(days: int = 30, page_size: int = 100) -> dict:
    """
    Recent PayPal transactions over the last `days` (max 31 per PayPal's window).

    Returns {count, gross_usd, net_usd, fee_usd, currency, transactions:[...]} or
    {"error": ...}. Each transaction: {id, date, status, gross, fee, net, currency,
    payer_email}. Read-only.
    """
    s = get_settings()
    if not (s.paypal_client_id and s.paypal_secret):
        return {"error": "PayPal credentials not set in .env"}
    days = max(1, min(days, 31))  # Transaction Search allows at most ~31d per call
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    params = {
        "start_date": start.strftime("%Y-%m-%dT%H:%M:%S-0000"),
        "end_date": end.strftime("%Y-%m-%dT%H:%M:%S-0000"),
        "fields": "all",
        "page_size": page_size,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await _token(client)
            resp = await client.get(
                f"{_base()}/v1/reporting/transactions",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        body = resp.json()
    except Exception as exc:
        return {"error": str(exc)}

    txns, gross, net, fee, currency = [], 0.0, 0.0, 0.0, "USD"
    for d in body.get("transaction_details", []) or []:
        info = d.get("transaction_info", {})
        amt = float(info.get("transaction_amount", {}).get("value", 0) or 0)
        f = float(info.get("fee_amount", {}).get("value", 0) or 0)
        currency = info.get("transaction_amount", {}).get("currency_code", currency)
        gross += amt
        fee += f
        net += amt + f  # PayPal fee is negative
        txns.append({
            "id": info.get("transaction_id", ""),
            "date": info.get("transaction_initiation_date", ""),
            "status": info.get("transaction_status", ""),
            "gross": amt,
            "fee": f,
            "net": round(amt + f, 2),
            "currency": currency,
            "payer_email": d.get("payer_info", {}).get("email_address", ""),
        })
    return {
        "count": len(txns),
        "gross_usd": round(gross, 2),
        "fee_usd": round(fee, 2),
        "net_usd": round(net, 2),
        "currency": currency,
        "days": days,
        "transactions": txns,
    }


async def get_paypal_balance() -> dict:
    """Current PayPal account balance(s). Returns {balances:[{currency, value}]} or
    {"error": ...}. Read-only."""
    s = get_settings()
    if not (s.paypal_client_id and s.paypal_secret):
        return {"error": "PayPal credentials not set in .env"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            token = await _token(client)
            resp = await client.get(
                f"{_base()}/v1/reporting/balances",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        body = resp.json()
    except Exception as exc:
        return {"error": str(exc)}

    balances = [
        {
            "currency": b.get("currency", ""),
            "value": float(b.get("total_balance", {}).get("value", 0) or 0),
        }
        for b in body.get("balances", []) or []
    ]
    return {"balances": balances, "as_of": body.get("as_of_time", "")}
