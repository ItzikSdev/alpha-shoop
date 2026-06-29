"""
Net-margin model — the single source of truth for product profitability.

The CJ sourcing tool only computes a GROSS margin `(retail - supplier) / retail`
(see src/mcp_tools/sourcing.py). The autonomous pipeline's Evaluator needs the
REAL net margin the owner cares about, which folds in the two costs that gross
margin ignores (per docs/prompt.md §2):

  - a strict 18% VAT on the sale, and
  - standard payment-processing fees (2.9% + $0.30, the typical Shopify/Stripe tier).

Retail is treated as the VAT-INCLUSIVE price the customer actually pays, so the
seller's recognised revenue is `retail / (1 + VAT)` and the processor takes its
fee on the gross amount charged. Everything is a pure function of three numbers —
no network, no LLM — so it is cheap to call per candidate and trivially testable.

Tune the rates via env without touching code:
  VAT_RATE (default 0.18), PAYMENT_FEE_PCT (0.029), PAYMENT_FEE_FIXED_USD (0.30).
"""
from __future__ import annotations

import os

VAT_RATE = float(os.environ.get("VAT_RATE", "0.18"))
PAYMENT_FEE_PCT = float(os.environ.get("PAYMENT_FEE_PCT", "0.029"))
PAYMENT_FEE_FIXED_USD = float(os.environ.get("PAYMENT_FEE_FIXED_USD", "0.30"))


def compute_net_margin(
    retail_usd: float,
    supplier_usd: float,
    shipping_usd: float = 0.0,
) -> dict:
    """Net profit + margin for one product after VAT, supplier, shipping, fees.

    Args:
        retail_usd:   VAT-inclusive price the customer pays (Shopify list price).
        supplier_usd: CJ supplier (cost-of-goods) price.
        shipping_usd: CJ shipping cost to the destination.

    Returns a dict with the headline numbers plus a `breakdown` so the Evaluator
    can post a transparent table to Slack:
        {
          "net_profit_usd": float,
          "net_margin_pct": float,   # net_profit / retail, rounded to 4dp
          "breakdown": {revenue_ex_vat, vat, supplier, shipping, payment_fee},
        }
    """
    retail = max(float(retail_usd or 0.0), 0.0)
    supplier = max(float(supplier_usd or 0.0), 0.0)
    shipping = max(float(shipping_usd or 0.0), 0.0)

    if retail <= 0.0:
        return {
            "net_profit_usd": 0.0,
            "net_margin_pct": 0.0,
            "breakdown": {
                "revenue_ex_vat": 0.0, "vat": 0.0, "supplier": supplier,
                "shipping": shipping, "payment_fee": 0.0,
            },
        }

    revenue_ex_vat = retail / (1.0 + VAT_RATE)
    vat = retail - revenue_ex_vat
    payment_fee = retail * PAYMENT_FEE_PCT + PAYMENT_FEE_FIXED_USD

    net_profit = revenue_ex_vat - supplier - shipping - payment_fee
    net_margin_pct = net_profit / retail

    return {
        "net_profit_usd": round(net_profit, 2),
        "net_margin_pct": round(net_margin_pct, 4),
        "breakdown": {
            "revenue_ex_vat": round(revenue_ex_vat, 2),
            "vat": round(vat, 2),
            "supplier": round(supplier, 2),
            "shipping": round(shipping, 2),
            "payment_fee": round(payment_fee, 2),
        },
    }


def annotate_candidate(candidate: dict) -> dict:
    """Return a shallow copy of a CJ candidate with net-margin fields attached.

    Reads the keys the sourcing/scraper steps already produce:
      estimated_price_shopify_usd (retail), price_supplier_usd, shipping_cost_usd.
    """
    calc = compute_net_margin(
        retail_usd=candidate.get("estimated_price_shopify_usd", 0.0),
        supplier_usd=candidate.get("price_supplier_usd", 0.0),
        shipping_usd=candidate.get("shipping_cost_usd", 0.0),
    )
    return {
        **candidate,
        "net_margin_pct": calc["net_margin_pct"],
        "net_profit_usd": calc["net_profit_usd"],
        "net_margin_breakdown": calc["breakdown"],
    }
