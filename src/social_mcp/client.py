"""Real MCP client for our own social server (python -m src.social_mcp.server, stdio).

    async with SocialMCPClient() as s:
        r = await s.call("draft_post", {"platform": "instagram", ...})
"""
from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class SocialMCPClient:
    async def __aenter__(self) -> "SocialMCPClient":
        self._stack = AsyncExitStack()
        params = StdioServerParameters(command=sys.executable, args=["-m", "src.social_mcp.server"],
                                       env=dict(os.environ))  # our own server needs the META_/TIKTOK_ env
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    async def list_tools(self) -> list:
        return (await self._session.list_tools()).tools

    async def call(self, name: str, args: dict | None = None) -> dict:
        res = await self._session.call_tool(name, args or {})
        text = "".join(getattr(c, "text", "") for c in res.content)
        try:
            return json.loads(text)
        except Exception:
            return {"ok": not res.isError, "text": text}
