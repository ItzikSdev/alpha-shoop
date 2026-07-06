"""Real MCP client for CJ Dropshipping's official MCP server.

This is a GENUINE Model Context Protocol client (JSON-RPC 2.0 over CJ's
StreamableHTTP transport) — unlike src/mcp_tools/, which is an in-process Python
function registry that calls CJ's REST API and only borrows the "mcp" name.

    Endpoint : https://developers.cjdropshipping.cn/mcp/<token>   (StreamableHTTP)
    Auth     : the CJ access-token JWT embedded in the URL path (settings.cj_mcp_key)
    Transport: HTTP POST, responses streamed as Server-Sent Events (text/event-stream)

Why this exists (vs. the REST calls in src/mcp_tools/sourcing.py): the MCP server
exposes capabilities the REST subset we use does NOT — most usefully live
inventory-by-country (`get_product_inventory`) and shipment tracking
(`get_tracking_info`). It hits the same CJ backend, so it is NOT a richer source
of product *detail* (REST product/query already returns 55 fields); its value is
these extra operations.

Rate limits: CJ throttles the MCP endpoint hard ("Too Many Requests, one ip limit
3 users") and enforces ~1 QPS. Calls are serialised behind a lock with a minimum
interval and retried on the throttle message, mirroring the REST client's policy.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

# Base of the remote MCP server. The token is appended as the final path segment.
# Override with CJ_MCP_URL if CJ moves the endpoint. NOTE: the working host is the
# .cn domain — the .com host returns 405 for the MCP path (verified live).
_MCP_BASE = os.environ.get("CJ_MCP_URL", "https://developers.cjdropshipping.cn/mcp")

_MIN_INTERVAL = 1.2  # seconds between MCP calls (CJ ~1 QPS + IP-user cap)
_LOCK = asyncio.Lock()
_LAST_CALL = 0.0

_PROTOCOL_VERSION = "2024-11-05"


class CJMCPError(Exception):
    """A CJ MCP call failed (transport error, JSON-RPC error, or tool error)."""


class CJMCPThrottled(CJMCPError):
    """CJ's per-IP/QPS throttle tripped ('Too Many Requests, one ip limit 3 users').
    Retrying after a short backoff can succeed — distinct from a hard failure."""


def _endpoint() -> str:
    token = get_settings().cj_mcp_key
    if not token:
        raise CJMCPError("cj_mcp_key is not set — no CJ MCP token to authenticate with")
    return f"{_MCP_BASE}/{token}"


def _parse_sse(text: str) -> dict | None:
    """CJ streams JSON-RPC replies as SSE: lines of `data: {json}`. Return the
    first parseable data payload, or None."""
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[len("data:"):].strip())
            except json.JSONDecodeError:
                continue
    return None


class CJMCPClient:
    """A single MCP session against CJ's server. Use as an async context manager:

        async with CJMCPClient() as cj:
            data = await cj.call("get_product_inventory", {"pid": pid, "countryCode": "US"})
    """

    def __init__(self, timeout: float = 30.0):
        self._url = _endpoint()
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }

    async def __aenter__(self) -> "CJMCPClient":
        self._client = httpx.AsyncClient(timeout=self._timeout, follow_redirects=True)
        await self._initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _post(self, payload: dict) -> httpx.Response:
        """Rate-limited JSON-RPC POST (serialised, min-interval spaced)."""
        global _LAST_CALL
        assert self._client is not None
        async with _LOCK:
            wait = _MIN_INTERVAL - (time.monotonic() - _LAST_CALL)
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await self._client.post(self._url, json=payload, headers=self._headers)
            _LAST_CALL = time.monotonic()
        return resp

    async def _initialize(self) -> None:
        resp = await self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "alpha-shoop", "version": "0.1"},
            },
        })
        # CJ returns a session id to thread through subsequent calls.
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
        if sid:
            self._session_id = sid
            self._headers["Mcp-Session-Id"] = sid
        data = _parse_sse(resp.text) or _safe_json(resp.text)
        if not data or "result" not in data:
            raise CJMCPError(f"MCP initialize failed: HTTP {resp.status_code} {resp.text[:200]}")
        # Per spec, tell the server we're ready before issuing tool calls.
        await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def list_tools(self) -> list[dict]:
        resp = await self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        data = _parse_sse(resp.text) or _safe_json(resp.text) or {}
        return data.get("result", {}).get("tools", [])

    async def call(self, tool: str, arguments: dict | None = None, retries: int = 3) -> object:
        """Invoke an MCP tool and return its parsed result.

        CJ wraps tool output in the MCP content envelope (`content[0].text`); that
        text is usually a JSON string, which we decode. Throttle replies are
        retried with backoff; a genuine tool error raises CJMCPError.
        """
        for attempt in range(retries):
            resp = await self._post({
                "jsonrpc": "2.0", "id": 9, "method": "tools/call",
                "params": {"name": tool, "arguments": arguments or {}},
            })
            data = _parse_sse(resp.text) or _safe_json(resp.text)
            if not data:
                raise CJMCPError(f"{tool}: unparseable MCP response: {resp.text[:200]}")
            if "error" in data:
                raise CJMCPError(f"{tool}: JSON-RPC error {data['error']}")
            result = data.get("result", {})
            texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
            blob = "\n".join(texts)
            # CJ signals throttling in the tool text, not as an HTTP status.
            if "Too Many Requests" in blob or "one ip limit" in blob:
                if attempt < retries - 1:
                    await asyncio.sleep(_MIN_INTERVAL * (attempt + 2))
                    continue
                raise CJMCPThrottled(blob.strip()[:200])
            return _safe_json(blob) if blob else result
        raise CJMCPThrottled(f"{tool}: throttled after {retries} attempts")


def _safe_json(text: str) -> object:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


# ── High-level convenience helpers (the NEW data REST doesn't give us) ──────────

async def get_product_inventory(pid: str, country_code: str = "US") -> object:
    """Live warehouse stock for a product in a destination country — not available
    via the REST subset we use. Returns CJ's inventory payload (per-variant/warehouse)."""
    async with CJMCPClient() as cj:
        return await cj.call("get_product_inventory", {"pid": pid, "countryCode": country_code})


async def get_tracking_info(track_numbers: list[str] | str) -> object:
    """Live shipment tracking for one or more tracking numbers."""
    nums = track_numbers if isinstance(track_numbers, str) else ",".join(track_numbers)
    async with CJMCPClient() as cj:
        return await cj.call("get_tracking_info", {"trackNumbers": nums})


async def search_products(keyword: str, page_num: int = 1, page_size: int = 10) -> object:
    """Catalog search via MCP (CJ tool `query_sku_detail_page`). Same backend as the
    REST product/list — provided for parity / MCP-only workflows."""
    async with CJMCPClient() as cj:
        return await cj.call("query_sku_detail_page",
                             {"keyword": keyword, "pageNum": page_num, "pageSize": page_size})


async def ping() -> list[str]:
    """Connectivity check: initialize + tools/list. Returns the tool names."""
    async with CJMCPClient() as cj:
        return [t["name"] for t in await cj.list_tools()]
