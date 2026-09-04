"""Real MCP client for our own TikTok Ads MCP server (src/tiktok_mcp/server.py).

Distinct from `src/mcp_tools/` (an in-process REST-backed function registry
that only borrows the "mcp" name) — this speaks actual Model Context Protocol
(JSON-RPC over stdio) to a locally-spawned subprocess. Same honesty convention
as `src/cj_mcp/` (which speaks real MCP to CJ's remote server instead of a
local one — see that package's README for the fuller "REST vs MCP" writeup).
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TikTokMCPError(Exception):
    """A TikTok Ads MCP call failed."""


class TikTokMCPClient:
    """A single MCP session against our local TikTok Ads server:

        async with TikTokMCPClient() as tt:
            report = await tt.call("get_ads_report", {"start_date": "...", "end_date": "..."})
    """

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "TikTokMCPClient":
        self._stack = AsyncExitStack()
        # The MCP SDK spawns subprocesses with a security-restricted default env
        # (PATH/HOME/etc only) unless `env` is given explicitly — pass the full
        # parent environment through since this is OUR OWN local server, not a
        # third-party one, and it needs TIKTOK_APP_ID/SECRET/ACCESS_TOKEN.
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "src.tiktok_mcp.server"], env=dict(os.environ),
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self._session = None

    async def list_tools(self) -> list[str]:
        assert self._session is not None
        result = await self._session.list_tools()
        return [t.name for t in result.tools]

    async def call(self, tool: str, arguments: dict | None = None) -> object:
        assert self._session is not None
        result = await self._session.call_tool(tool, arguments or {})
        texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        blob = "\n".join(texts)
        parsed = _safe_json(blob) if blob else None
        if result.isError:
            raise TikTokMCPError(f"{tool}: {parsed if parsed is not None else blob}")
        return parsed


def _safe_json(text: str) -> object:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


# ── High-level convenience helpers (what agent_loop/conversation.py call) ──────

async def login() -> dict:
    """Start OAuth — returns the authorize URL to open in a browser."""
    async with TikTokMCPClient() as tt:
        return await tt.call("tiktok_ads_login")


async def complete_auth(auth_code: str) -> dict:
    """Finish OAuth with the `auth_code` copied from the redirect URL."""
    async with TikTokMCPClient() as tt:
        return await tt.call("tiktok_ads_complete_auth", {"auth_code": auth_code})


async def auth_status() -> dict:
    async with TikTokMCPClient() as tt:
        return await tt.call("tiktok_ads_auth_status")


async def list_campaigns(advertiser_id: str = "") -> dict:
    async with TikTokMCPClient() as tt:
        return await tt.call("list_campaigns", {"advertiser_id": advertiser_id})


async def get_ads_report(start_date: str, end_date: str, advertiser_id: str = "") -> dict:
    async with TikTokMCPClient() as tt:
        return await tt.call("get_ads_report", {
            "start_date": start_date, "end_date": end_date, "advertiser_id": advertiser_id,
        })


async def read_ads_export(filename: str = "") -> dict:
    """Real numbers from a report exported by hand out of Ads Manager — the
    fallback while the Developer app is still pending approval."""
    async with TikTokMCPClient() as tt:
        return await tt.call("read_ads_export", {"filename": filename})


async def ads_export_status() -> dict:
    async with TikTokMCPClient() as tt:
        return await tt.call("ads_export_status")


async def ping() -> list[str]:
    """Connectivity check: spawn the server + list its tool names."""
    async with TikTokMCPClient() as tt:
        return await tt.list_tools()
