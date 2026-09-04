"""TikTok Ads — REAL Model Context Protocol client, talking to our own local
MCP server (src/tiktok_mcp/server.py, spawned as a stdio subprocess) which
wraps TikTok's documented Marketing API v1.3. See README.md for why this is
separate from src/mcp_tools/ (in-process REST registry, not real MCP)."""
from src.tiktok_mcp.client import (
    TikTokMCPClient,
    TikTokMCPError,
    login,
    complete_auth,
    auth_status,
    list_campaigns,
    get_ads_report,
    read_ads_export,
    ads_export_status,
    ping,
)

__all__ = [
    "TikTokMCPClient",
    "TikTokMCPError",
    "login",
    "complete_auth",
    "auth_status",
    "list_campaigns",
    "get_ads_report",
    "read_ads_export",
    "ads_export_status",
    "ping",
]
