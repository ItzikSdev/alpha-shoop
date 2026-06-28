"""
Shopify OAuth self-heal — so a stale/rotated token (HTTP 401) recovers itself
instead of silently breaking the store for days.

Shopify's Admin API offline token is minted by an authorization_code flow that
REQUIRES a one-time human "Approve" click in the browser — there is no
client_credentials grant and a token cannot refresh itself headlessly (the same
deliberate limit as scope-escalation). So "the agents do it themselves" means:
detect the 401, surface a single one-click re-authorize URL to the channel, and
once the owner approves, the callback persists the fresh token to BOTH the .env
and every matching store row (one source of truth) — no agent stalls again.

Token precedence everywhere: a store row's token, else settings (.env).
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import urllib.parse
from pathlib import Path

import httpx

from src.config import get_settings

# Same scope set the one-shot get_shopify_token.py grants — includes read/write_themes.
SCOPES = (
    "write_products,read_products,write_inventory,read_inventory,write_orders,"
    "read_orders,write_fulfillments,read_fulfillments,read_themes,write_themes,"
    "read_content,write_content,read_online_store_navigation,"
    "write_online_store_navigation,read_script_tags,write_script_tags,"
    "read_metaobjects,write_metaobjects,read_publications,write_publications"
)
# The app's OAuth callback — must be in the app's allowed Redirect URLs.
REDIRECT_URI = os.environ.get("SHOPIFY_OAUTH_REDIRECT", "http://localhost:8000/shopify/callback")
_DB_PATH = Path(os.environ.get("TRACES_DB_PATH", "./data/traces.db"))
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def client_id() -> str:
    return os.environ.get("SHOPIFY_CLIENT_ID", "0dfe5685f422a744caa5effc1b88e304")


def build_authorize_url(shop: str = "", state: str = "") -> str:
    """The one-click re-authorize URL. The owner opens it, approves once, and the
    callback mints + persists a fresh token."""
    shop = shop or get_settings().shopify_store_domain
    state = state or secrets.token_hex(8)
    query = urllib.parse.urlencode(
        {
            "client_id": client_id(),
            "scope": SCOPES,
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "grant_options[]": "offline",
        },
        safe=",",
    )
    return f"https://{shop}/admin/oauth/authorize?{query}"


async def exchange_code_for_token(shop: str, code: str) -> str:
    """Finish OAuth: trade the auth `code` for an offline access token."""
    secret = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
    if not secret:
        raise RuntimeError("SHOPIFY_CLIENT_SECRET not set — needed to exchange the OAuth code")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            f"https://{shop}/admin/oauth/access_token",
            data={"client_id": client_id(), "client_secret": secret, "code": code},
        )
    r.raise_for_status()
    return r.json().get("access_token", "")


def persist_shopify_token(token: str, shop: str = "") -> dict:
    """Write the fresh token to .env AND every matching store row, so the store
    path (execute_shopify → stores[0]) and the .env fallback agree. Returns a
    summary of what was updated."""
    shop = shop or get_settings().shopify_store_domain
    out = {"env_updated": False, "store_rows_updated": 0}

    # 1. .env (create/replace the SHOPIFY_ACCESS_TOKEN line)
    try:
        lines = _ENV_PATH.read_text().splitlines() if _ENV_PATH.exists() else []
        found = False
        for i, ln in enumerate(lines):
            if ln.startswith("SHOPIFY_ACCESS_TOKEN="):
                lines[i] = f"SHOPIFY_ACCESS_TOKEN={token}"
                found = True
        if not found:
            lines.append(f"SHOPIFY_ACCESS_TOKEN={token}")
        _ENV_PATH.write_text("\n".join(lines) + "\n")
        out["env_updated"] = True
    except Exception as exc:
        out["env_error"] = str(exc)

    # 2. stores table — update the row(s) for this shop (best-effort; table may
    #    not exist in every environment).
    try:
        with sqlite3.connect(_DB_PATH) as con:
            cur = con.execute(
                "UPDATE stores SET shopify_access_token = ? WHERE shopify_domain = ?",
                (token, shop),
            )
            out["store_rows_updated"] = cur.rowcount
            con.commit()
    except Exception as exc:
        out["store_error"] = str(exc)

    # 3. drop the cached Settings so the new .env value is picked up immediately.
    try:
        get_settings.cache_clear()  # lru_cache on get_settings
    except Exception:
        pass
    return out


async def escalate_shopify_401(shop: str = "") -> str:
    """Agents call this when a Shopify call returns 401: post the one-click
    re-auth URL to the channel + record a blocker, so the fix surfaces itself
    instead of the store silently staying broken. Returns the authorize URL."""
    url = build_authorize_url(shop)
    try:
        from src.org.slack import post_to_slack
        await post_to_slack(
            ":lock: *Shopify token invalid (401).* I can't edit the store until it's "
            f"re-authorized. One click fixes it (approve once):\n{url}"
        )
    except Exception:
        pass
    try:
        from src.org.models import get_company, save_company
        company = get_company()
        if company:
            note = "⚠️ BLOCKER: Shopify token returned 401 — owner must re-authorize (one click)."
            if note not in company.lessons:
                company.lessons.append(note)
                company.lessons = company.lessons[-40:]
                save_company(company)
    except Exception:
        pass
    return url
