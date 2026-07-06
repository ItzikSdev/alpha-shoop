"""CJ Dropshipping — REAL Model Context Protocol client.

Distinct from `src/mcp_tools/` (an in-process REST-backed function registry that
only borrows the "mcp" name). This package speaks actual MCP (JSON-RPC 2.0 over
CJ's StreamableHTTP endpoint) and is the home for CJ capabilities the REST subset
doesn't expose: live inventory-by-country, shipment tracking, disputes, etc.
"""
from src.cj_mcp.client import (
    CJMCPClient,
    CJMCPError,
    CJMCPThrottled,
    get_product_inventory,
    get_tracking_info,
    search_products,
    ping,
)

__all__ = [
    "CJMCPClient",
    "CJMCPError",
    "CJMCPThrottled",
    "get_product_inventory",
    "get_tracking_info",
    "search_products",
    "ping",
]
