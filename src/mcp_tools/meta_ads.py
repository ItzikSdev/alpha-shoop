"""
Meta (Facebook / Instagram) ad launcher — Marketing API.

Creates a real traffic campaign → ad set → creative → ad from a store product,
all **PAUSED** and capped at a LIFETIME budget (default ₪50) so nothing spends
until the owner un-pauses it. This is what makes Max actually launch ads instead
of only writing plans. Needs META_ACCESS_TOKEN (with ads_management + pages_manage_ads),
META_AD_ACCOUNT_ID (act_…), META_PAGE_ID.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import httpx

GRAPH = "https://graph.facebook.com/v19.0"


async def _post(client: httpx.AsyncClient, path: str, data: dict, token: str) -> dict:
    data = {**data, "access_token": token}
    r = await client.post(f"{GRAPH}/{path}", data=data)
    j = r.json()
    if isinstance(j, dict) and j.get("error"):
        raise RuntimeError(f"{path} → {j['error'].get('message')}")
    return j


async def create_paused_ad(
    product_title: str, product_url: str, image_url: str,
    *, lifetime_ils: float = 50.0, countries: list[str] | None = None,
    token: str | None = None, ad_account: str | None = None, page_id: str | None = None,
) -> dict:
    """Create a PAUSED traffic ad for one product. Returns the created ids. Nothing
    spends until it's un-paused; total is hard-capped by the lifetime budget."""
    token = token or os.environ["META_ACCESS_TOKEN"]
    acct = ad_account or os.environ["META_AD_ACCOUNT_ID"]
    page = page_id or os.environ.get("META_PAGE_ID", "1269650886222329")
    countries = countries or ["US", "IL", "GB", "CA", "AU"]
    end_time = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    async with httpx.AsyncClient(timeout=40) as c:
        camp = await _post(c, f"{acct}/campaigns", {
            "name": f"TIMEFOR BABY — {product_title[:40]}", "objective": "OUTCOME_TRAFFIC",
            "status": "PAUSED", "special_ad_categories": "[]",
            "is_adset_budget_sharing_enabled": "false"}, token)
        adset = await _post(c, f"{acct}/adsets", {
            "name": f"{product_title[:40]} — traffic", "campaign_id": camp["id"],
            "lifetime_budget": int(round(lifetime_ils * 100)), "end_time": end_time,
            "billing_event": "IMPRESSIONS", "optimization_goal": "LINK_CLICKS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": json.dumps({"geo_locations": {"countries": countries}}),
            "status": "PAUSED"}, token)
        creative = await _post(c, f"{acct}/adcreatives", {
            "name": f"{product_title[:40]} creative",
            "object_story_spec": json.dumps({"page_id": page, "link_data": {
                "message": f"{product_title} — premium organic cotton, gentle on the smallest skin. Free worldwide shipping.",
                "link": product_url, "name": product_title, "picture": image_url,
                "call_to_action": {"type": "SHOP_NOW", "value": {"link": product_url}}}})}, token)
        ad = await _post(c, f"{acct}/ads", {
            "name": f"{product_title[:40]} ad", "adset_id": adset["id"],
            "creative": json.dumps({"creative_id": creative["id"]}), "status": "PAUSED"}, token)
    return {"campaign": camp["id"], "adset": adset["id"], "creative": creative["id"],
            "ad": ad["id"], "lifetime_ils": lifetime_ils, "countries": countries}
