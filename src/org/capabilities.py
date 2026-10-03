"""
Per-agent capability check — "does each agent actually have what it needs?"

Two kinds of gap, both reported, never guessed:
  1. not_connected — a tool the agent HAS (src/org/tool_catalog.py) whose
     credentials/connection are missing from the environment.
  2. missing_tool  — something the agent's ROLE needs to do its job that NO
     tool provides yet (ROLE_NEEDS below). These are human-reviewed code
     changes; agents can only report them, never create tools.

Used by GET /api/v1/org/capabilities (platform-app 3D office "needs you" badge)
and injected into each agent's heartbeat prompt so a blocked agent says exactly
which key/tool is missing instead of inventing a vague blocker.
Only env var NAMES are ever reported — never values.
"""
from __future__ import annotations

import os

from src.org.tool_catalog import AGENT_TOOL_GROUPS

_SHOPIFY = ["SHOPIFY_ACCESS_TOKEN", "SHOPIFY_STORE_DOMAIN"]
_TIKTOK = ["TIKTOK_ACCESS_TOKEN", "TIKTOK_ADVERTISER_ID"]
_META = ["META_PAGE_ID", "FB_PAGE_ACCESS_TOKEN|META_ACCESS_TOKEN"]
_GMAIL = ["SUPPORT_GMAIL_CLIENT_ID", "SUPPORT_GMAIL_CLIENT_SECRET", "SUPPORT_GMAIL_REFRESH_TOKEN"]

# tool name -> env vars that must ALL be set for it to work. Tools not listed
# need no external credential (internal DB/logic).
TOOL_ENV: dict[str, list[str]] = {
    **{t: _SHOPIFY for t in ("shopify_list_products", "shopify_admin", "shopify_publish_products",
                             "fulfill_shopify_order", "get_sales_summary")},
    **{t: ["CJ_API_KEY"] for t in ("cj_search_products", "cj_add_product", "cj_product_inventory",
                                   "cj_track_shipment", "cj_stock_sweep", "place_supplier_order")},
    **{t: ["REDIS_URL"] for t in ("search_local_catalog", "rag_ingest", "search_playbook",
                                  "refresh_playbook", "search_store_products_rag")},
    "generate_rotation_video": ["GCP_PROJECT_ID"],
    "generate_image": ["GEMINI_API_KEY"],
    **{t: _GMAIL for t in ("process_central_inbox", "check_inbox", "mark_email_handled")},
    "send_email": ["RESEND_API_KEY"],
    "send_customer_email": ["RESEND_API_KEY"],
    "tiktok_ads_login": ["TIKTOK_APP_ID", "TIKTOK_APP_SECRET"],
    "tiktok_ads_complete_auth": ["TIKTOK_APP_ID", "TIKTOK_APP_SECRET"],
    "get_ads_report": _TIKTOK,
    "list_campaigns": _TIKTOK,
    "get_clarity_report": ["CLARITY_API_TOKEN"],
    "search_web": ["SERPER_API_KEY"],
    # Lia's social tools — Meta covers Facebook + Instagram; TikTok organic posting is a
    # SEPARATE developer app from the TikTok Ads one (see src/social_mcp/README.md).
    **{t: _META for t in ("social_status", "recent_posts", "read_comments", "post_insights",
                          "publish_approved")},
    "store_media": _SHOPIFY,
    "search_market_prices": ["SERPER_API_KEY"],
}

# What each ROLE needs that no tool covers yet. Edit as the company changes.
ROLE_NEEDS: dict[str, list[dict]] = {
    "Kai": [{
        "need": "Meta (Facebook/Instagram) Ads reporting",
        "why": "Meta is the ad platform actually used; Kai only has TikTok reporting tools.",
        "fix": "Add a read-only Meta Ads insights tool (META_ACCESS_TOKEN + META_AD_ACCOUNT_ID already exist).",
    }],
    "Lia": [{
        "need": "TikTok organic posting",
        "why": "Needs a TikTok for Developers app (Content Posting API) + one-time owner OAuth.",
        "fix": "Set TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET / TIKTOK_CONTENT_REDIRECT_URI, then run tiktok_login.",
        "requires_env": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_USER_ACCESS_TOKEN"],
    }],
    "Sol": [{
        "need": "Fresh store-building patterns (training loop)",
        "why": "agents-training/ (the loop that fed the store_building_patterns corpus) was removed from the repo; the corpus no longer grows.",
        "fix": "Restore the training pipeline or retire search_training_patterns.",
    }],
}


def _set(k: str) -> bool:
    return bool(os.environ.get(k, "").strip())


def _missing(keys: list[str]) -> list[str]:
    """`A|B` means either one is enough."""
    return [k for k in keys if not any(_set(alt) for alt in k.split("|"))]


def agent_capabilities(name: str) -> dict:
    tools = [t for group in AGENT_TOOL_GROUPS.get(name, {}).values() for t in group]
    connected, not_connected = [], []
    for t in tools:
        miss = _missing(TOOL_ENV.get(t, []))
        (not_connected.append({"tool": t, "missing_env": miss}) if miss else connected.append(t))
    # A role need with `requires_env` disappears once those keys are all set.
    missing_tools = [m for m in ROLE_NEEDS.get(name, [])
                     if not m.get("requires_env") or _missing(m["requires_env"])]
    return {"agent": name, "ok": not not_connected and not missing_tools,
            "connected": connected, "not_connected": not_connected, "missing_tools": missing_tools}


def all_capabilities() -> list[dict]:
    names = list(dict.fromkeys([*AGENT_TOOL_GROUPS, *ROLE_NEEDS]))
    return [agent_capabilities(n) for n in names]


def capability_prompt_line(name: str) -> str:
    """Short block for the agent's own prompt: what works, what doesn't, how to say so."""
    c = agent_capabilities(name)
    if c["ok"]:
        return "YOUR CONNECTIONS: every tool you have is connected."
    lines = ["YOUR CONNECTIONS — gaps you must NOT work around silently:"]
    for nc in c["not_connected"]:
        why = ", ".join(nc["missing_env"]) or nc.get("error", "live check failed")
        lines.append(f"- tool `{nc['tool']}` is NOT connected ({why})")
    for m in c["missing_tools"]:
        lines.append(f"- you have NO tool for: {m['need']} ({m['why']})")
    lines.append('If a task you want to do needs one of these, use flag_blocker and name the exact '
                 'tool/key that is missing so the founder can fix it. Never pretend a missing tool worked.')
    return "\n".join(lines)


async def with_live_checks(caps: list[dict], timeout: float = 8.0) -> list[dict]:
    """Env presence isn't enough — a key can be set but expired/revoked. Run the cheap,
    read-only social status check and mark Lia's platforms that are configured but
    failing live (e.g. an expired Meta token). Network trouble never breaks the list."""
    import asyncio
    try:
        from src.social_mcp.publish import all_status
        st = await asyncio.wait_for(all_status(), timeout)
    except Exception:  # noqa: BLE001
        return caps
    for c in caps:
        if c["agent"] != "Lia":
            continue
        for platform, info in st.items():
            if not info.get("ok") and not info.get("missing_env") and info.get("error"):
                c["not_connected"].append({"tool": f"{platform} (live check)", "missing_env": [],
                                           "error": str(info["error"])[:200]})
                c["ok"] = False
    return caps
