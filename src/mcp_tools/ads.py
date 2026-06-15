"""MCP Tool Group 4: Ads — Google Ads API v17."""
from __future__ import annotations
import httpx
from src.config import get_settings


async def create_google_campaign(
    campaign_name: str,
    daily_budget_usd: float,
    keywords: list[str],
    target_countries: list[str],
) -> dict:
    """
    Create a Google Ads search campaign.

    Args:
        campaign_name: Unique campaign name (max 255 chars)
        daily_budget_usd: Daily budget in USD (guardrail: max $500/day total)
        keywords: List of target keywords
        target_countries: List of ISO country codes

    Returns:
        Dict with keys: campaign_id (str), status (str), resource_name (str)
    """
    settings = get_settings()
    # Real: use google-ads Python client library
    # from google.ads.googleads.client import GoogleAdsClient
    # For now return a deterministic mock
    cid = f"camp_{campaign_name.lower().replace(' ', '_')[:20]}"
    return {
        "campaign_id": cid,
        "status": "ENABLED",
        "resource_name": f"customers/{settings.google_ads_customer_id}/campaigns/{cid}",
    }


async def get_campaign_metrics(
    campaign_id: str,
    date_range: str = "LAST_7_DAYS",
) -> dict:
    """
    Retrieve performance metrics for a Google Ads campaign.

    Args:
        campaign_id: Google Ads campaign ID
        date_range: GAQL date range string (LAST_7_DAYS, LAST_30_DAYS, etc.)

    Returns:
        Dict with keys: impressions, clicks, spend_usd, conversions, roas
    """
    # Real: GAQL query via GoogleAdsService.search_stream
    return {
        "impressions": 1250,
        "clicks": 87,
        "spend_usd": 23.40,
        "conversions": 3,
        "roas": 4.2,
    }
