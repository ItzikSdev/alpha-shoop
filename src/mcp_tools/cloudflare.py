"""
Cloudflare DNS — point a store's subdomain at Shopify so the store gets a real
branded domain (e.g. timeforbaby.alpha-tech.live → Shopify).

The owner's domain `alpha-tech.live` lives in Cloudflare. For a Shopify custom
subdomain you create a CNAME `<sub>` → `shops.myshopify.com`, DNS-only (NOT
proxied — Shopify must terminate SSL itself), then add the domain on the Shopify
side once. This module does the Cloudflare half.

Auth: settings.cloudflare_api_token (in .env). The zone is identified by
settings.cloudflare_zone_id — the current token can't LIST zones, so the Zone ID
(non-secret, on the domain's Overview page) must be set explicitly.
"""
from __future__ import annotations

import httpx

from src.config import get_settings

_API = "https://api.cloudflare.com/client/v4"
SHOPIFY_CNAME_TARGET = "shops.myshopify.com"


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_settings().cloudflare_api_token}",
            "Content-Type": "application/json"}


async def ensure_dns_cname(name: str, target: str = SHOPIFY_CNAME_TARGET, proxied: bool = False) -> dict:
    """Create or update a CNAME `name` → `target` in the configured zone (idempotent).

    `name` is the full hostname (e.g. "timeforbaby.alpha-tech.live"). Returns
    {"ok": bool, "action": "created"|"updated", "record_id": str, "name": str} or
    {"error": ...}. proxied=False (DNS-only) is correct for Shopify custom domains.
    """
    s = get_settings()
    if not s.cloudflare_api_token:
        return {"error": "cloudflare_api_token not set in .env"}
    if not s.cloudflare_zone_id:
        return {"error": "cloudflare_zone_id not set in .env (Zone ID from the domain's "
                         "Overview page — this token can't list zones to find it automatically)"}
    zone = s.cloudflare_zone_id
    body = {"type": "CNAME", "name": name, "content": target, "proxied": proxied, "ttl": 1}
    try:
        async with httpx.AsyncClient(timeout=20, headers=_headers()) as c:
            # Is there already a record for this name? → update it, don't duplicate.
            existing = await c.get(f"{_API}/zones/{zone}/dns_records", params={"name": name})
            rows = existing.json().get("result", []) if existing.status_code < 400 else []
            if rows:
                rid = rows[0]["id"]
                r = await c.put(f"{_API}/zones/{zone}/dns_records/{rid}", json=body)
                action = "updated"
            else:
                r = await c.post(f"{_API}/zones/{zone}/dns_records", json=body)
                action = "created"
        data = r.json()
        if not data.get("success"):
            return {"error": f"HTTP {r.status_code}: {str(data.get('errors'))[:200]}"}
        rec = data.get("result", {})
        return {"ok": True, "action": action, "record_id": rec.get("id", ""),
                "name": rec.get("name", name), "target": target, "proxied": proxied}
    except Exception as exc:
        return {"error": str(exc)}


async def point_subdomain_to_shopify(subdomain: str, root: str = "alpha-tech.live") -> dict:
    """Convenience: CNAME `<subdomain>.<root>` → Shopify (DNS-only). e.g.
    point_subdomain_to_shopify("timeforbaby") → timeforbaby.alpha-tech.live."""
    name = subdomain if "." in subdomain else f"{subdomain}.{root}"
    return await ensure_dns_cname(name, SHOPIFY_CNAME_TARGET, proxied=False)
