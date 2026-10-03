"""
Lia (Social Media Manager) — a real tool-using agent over the social MCP server.

Talks to src/social_mcp/server.py over REAL MCP (stdio, via SocialMCPClient) for
Facebook Page + Instagram Business + TikTok. Same loop shape as Sol's
run_sol_task (src/org/agent_loop.py): bind tools, iterate until the model stops
calling them, narrate to Telegram, record every step to agent_runs so the
platform-app shows it live.

Authority: Lia drafts posts and studies what performed; she can publish ONLY a
draft a human already approved. She cannot approve, and has no ads/spend tools.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.llm import get_llm

logger = logging.getLogger(__name__)

AGENT_NAME = "Lia"
AGENT_ROLE = "Social Media Manager"

_client: contextvars.ContextVar = contextvars.ContextVar("social_mcp_client", default=None)


async def _call(name: str, args: dict | None = None) -> dict:
    c = _client.get()
    if c is None:
        return {"ok": False, "error": "social MCP session not open"}
    return await c.call(name, args or {})


@tool
async def social_status() -> dict:
    """Which platforms are connected (facebook/instagram/tiktok), followers, and the EXACT
    missing env names for anything that isn't. Call this first."""
    return await _call("social_status")


@tool
async def recent_posts(platform: str, limit: int = 10) -> dict:
    """Our own recent posts on facebook|instagram|tiktok with engagement — learn what worked."""
    return await _call("recent_posts", {"platform": platform, "limit": limit})


@tool
async def read_comments(platform: str, post_id: str) -> dict:
    """Comments on one of our Facebook/Instagram posts."""
    return await _call("read_comments", {"platform": platform, "post_id": post_id})


@tool
async def post_insights(platform: str, post_id: str) -> dict:
    """Engagement numbers for one of our Facebook/Instagram posts."""
    return await _call("post_insights", {"platform": platform, "post_id": post_id})


@tool
async def list_drafts(status: str = "", platform: str = "") -> dict:
    """Our draft queue. ALWAYS read rejected drafts' `feedback` before drafting again."""
    return await _call("list_drafts", {"status": status, "platform": platform})


@tool
async def draft_post(platform: str, kind: str, message: str, media_url: str = "", link: str = "",
                     rationale: str = "") -> dict:
    """Queue a post for Itzik's approval (it does NOT go live). facebook: text|link|photo|reel;
    instagram: photo|reel; tiktok: video. media_url must be a PUBLIC https URL (e.g. a Shopify
    CDN image/video of the product). rationale = one line on why this post should work."""
    return await _call("draft_post", {"platform": platform, "kind": kind, "message": message,
                                      "media_url": media_url, "link": link, "author": AGENT_NAME,
                                      "rationale": rationale})


@tool
async def publish_approved(draft_id: str) -> dict:
    """Publish a draft Itzik APPROVED. Refused for anything else."""
    return await _call("publish_approved", {"draft_id": draft_id})


@tool
async def store_media(limit: int = 10) -> dict:
    """Live store products (title, description, every public image URL on Shopify's CDN) —
    the raw material for posts. Store link: https://alphaforbaby.com"""
    from src.mcp_tools.shopify import get_products_with_all_images
    items = await get_products_with_all_images()
    if not items:
        return {"ok": False, "error": "no live products with images returned (Shopify unreachable or empty)"}
    return {"ok": True, "products": [{**p, "description": (p.get("description") or "")[:400]} for p in items[:limit]]}


TOOLS = [social_status, recent_posts, read_comments, post_insights, list_drafts, draft_post,
         publish_approved, store_media]
TOOL_NAMES = [t.name for t in TOOLS]
_BY_NAME = {t.name: t for t in TOOLS}

_SYSTEM = """You are Lia, Social Media Manager at Alpha (alphaforbaby.com — baby products, sells globally, English content).
GOAL: bring REAL visitors to the store with organic content on Facebook, Instagram and TikTok. The store has zero sales; checkout works; traffic is the problem.
HOW YOU WORK:
1. social_status first. If a platform is not connected, say exactly which env/permission is missing and work on the connected ones.
2. Learn before you write: recent_posts (what got reactions/views), list_drafts (read Itzik's feedback on rejected drafts — never repeat a rejected idea).
3. Draft with draft_post: short scroll-stopping hook in the first line, one clear benefit, a call to action (comment/tag/link). Use real product media from store_media — never invent product claims, prices or reviews.
4. Everything you draft waits for Itzik's approval. publish_approved only for drafts already approved.
5. Finish with a short report: what you drafted (ids), what you learned from the numbers, what's blocked and why.
RULES: never post personal details of the owner; public contact is support@alphaforbaby.com only. No Harry-Potter-style or other trademarked themes. No fake urgency or fake scarcity."""


def _truncate(x, n: int = 6000) -> str:
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…(truncated)"


async def run_social_task(task: str, *, narrate: bool = True, max_steps: int = 16,
                          run_id: str | None = None) -> dict:
    from src.org.agent_runs import finish_run, insert_step, start_run
    from src.org.telegram import post_as
    from src.social_mcp.client import SocialMCPClient

    run_id = run_id or str(uuid.uuid4())

    async def say(text: str) -> None:
        if narrate and text:
            try:
                await post_as(AGENT_NAME, AGENT_ROLE, text)
            except Exception:  # noqa: BLE001
                pass

    async def step(kind: str, **kw) -> None:
        try:
            await asyncio.to_thread(insert_step, run_id, kind, **kw)
        except Exception:  # noqa: BLE001
            pass

    await asyncio.to_thread(start_run, run_id, AGENT_NAME, task, "alphaforbaby", None)
    await say(f"📣 On it — *{task}*")
    llm = get_llm("growth_marketer", temperature=0.5, max_tokens=3000, timeout=600).bind_tools(TOOLS)
    messages = [SystemMessage(content=_SYSTEM), HumanMessage(content=task)]
    final = ""
    try:
        async with SocialMCPClient() as client:
            _client.set(client)
            for _ in range(max_steps):
                resp: AIMessage = await llm.ainvoke(messages)
                messages.append(resp)
                calls = getattr(resp, "tool_calls", None) or []
                if not calls:
                    final = str(resp.content or "")
                    await asyncio.to_thread(finish_run, run_id, "done", final[:4000])
                    await say(final)
                    return {"run_id": run_id, "final": final}
                for call in calls:
                    fn = _BY_NAME.get(call["name"])
                    args = call.get("args") or {}
                    result = await fn.ainvoke(args) if fn else {"ok": False, "error": f"unknown tool {call['name']}"}
                    ok = not (isinstance(result, dict) and result.get("ok") is False)
                    await step("tool", tool_name=call["name"], args_json=_truncate(args, 1500),
                               result_json=_truncate(result, 3000), ok=ok)
                    messages.append(ToolMessage(content=_truncate(result), tool_call_id=call["id"]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Lia run failed: %s", exc)
        await asyncio.to_thread(finish_run, run_id, "error", str(exc)[:1500])
        await say(f"⚠️ I hit an error: {exc}"[:500])
        return {"run_id": run_id, "final": f"error: {exc}"}
    await asyncio.to_thread(finish_run, run_id, "max_steps", "max_steps reached")
    return {"run_id": run_id, "final": final or "(stopped at max_steps)"}
