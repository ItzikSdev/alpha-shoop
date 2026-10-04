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


@tool
async def store_videos(limit: int = 20, query: str = "") -> dict:
    """Products that already have a video on the store (direct .mp4 + product page URL). We never
    generate videos — every reel starts from one of these."""
    return await _call("store_videos", {"limit": limit, "query": query})


@tool
async def reel_playbook() -> dict:
    """The proven reel formula (hook formulas, structure, caption, what to avoid). Read before make_reel."""
    return await _call("reel_playbook")


@tool
async def make_reel(video_url: str, hook: str, cta: str = "", start: float = 0.0, max_seconds: float = 15.0) -> dict:
    """Cut an existing store video into a vertical <=15s reel with a hook line on top (+ optional
    end CTA) and host it. Returns media_url — pass it to draft_post(kind='reel' for facebook/instagram,
    kind='video' for tiktok). Use `start` to skip a dull intro."""
    return await _call("make_reel", {"video_url": video_url, "hook": hook, "cta": cta, "start": start,
                                     "max_seconds": max_seconds})


@tool
async def ad_library_search(query: str, countries: list[str] | None = None, limit: int = 12) -> dict:
    """Meta Ad Library: ads other stores run NOW (copy, headline, running since). Long-running ads =
    proven. If the result says needs_owner, report it as a blocker and use web_social_search."""
    return await _call("ad_library_search", {"query": query, "countries": countries or [], "limit": limit})


@tool
async def web_social_search(query: str, num: int = 8) -> dict:
    """Public web results about how other baby/toy brands post on Facebook/Instagram/TikTok."""
    return await _call("web_social_search", {"query": query, "num": num})


@tool
async def save_pattern(source: str, brand: str, hook_type: str, hook_example: str, structure: str,
                       cta: str, why_it_works: str, url: str = "", platform: str = "") -> dict:
    """Keep ONE pattern you learned from another store's post. PARAPHRASE only: hook_example <=140
    chars (never a copy of their text), structure/why_it_works <=400. hook_type: question|bold-claim|
    problem-agitate|demo-in-first-second|social-proof|curiosity-gap|relatable-moment|how-to|before-after|other."""
    return await _call("save_pattern", {"source": source, "brand": brand, "hook_type": hook_type,
                                        "hook_example": hook_example, "structure": structure, "cta": cta,
                                        "why_it_works": why_it_works, "url": url, "platform": platform})


@tool
async def social_playbook(limit: int = 25, hook_type: str = "", platform: str = "") -> dict:
    """Everything learned from other stores so far (patterns by hook type). Read before every draft."""
    return await _call("social_playbook", {"limit": limit, "hook_type": hook_type, "platform": platform})


@tool
async def traffic_results(days: int = 7) -> dict:
    """YOUR SCORECARD. Real store results by traffic source over the last N days (default 7):
    visits, product views, add-to-carts, checkouts, purchases and revenue for facebook / instagram / tiktok /
    direct / other (from the live-visitor beacon), plus the posts you published in that window.
    Call it at the start of every round and judge your own work by it: visits and purchases, not likes."""
    out: dict = {"ok": True}
    try:
        import redis.asyncio as aioredis
        from src.config import get_settings
        from src.visitors import events as E
        r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        try:
            out["results"] = await E.results(r, days)
        finally:
            await r.aclose()
    except Exception as exc:  # noqa: BLE001
        out["results"] = {"error": str(exc)[:200]}
    try:
        from datetime import datetime, timedelta, timezone
        from src.social_mcp import queue as _sq
        cut = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
        posts = [d for d in _sq.list_drafts("published")
                 if d.get("published_at") and datetime.fromisoformat(d["published_at"]) >= cut]
        out["published_posts"] = [{"id": d["id"], "platform": d["platform"], "kind": d.get("kind"),
                                   "published_at": d["published_at"], "remote_id": d.get("remote_id"),
                                   "first_line": (d.get("message") or "")[:80]} for d in posts]
    except Exception as exc:  # noqa: BLE001
        out["published_posts"] = {"error": str(exc)[:200]}
    return out


TOOLS = [social_status, recent_posts, read_comments, post_insights, list_drafts, draft_post,
         publish_approved, store_media, store_videos, reel_playbook, make_reel,
         ad_library_search, web_social_search, save_pattern, social_playbook, traffic_results]
TOOL_NAMES = [t.name for t in TOOLS]
_BY_NAME = {t.name: t for t in TOOLS}

_SYSTEM = """You are Lia, Social Media Manager at Alpha (alphaforbaby.com — baby products, sells globally, English content).
GOAL: bring REAL visitors to the store with organic content on Facebook, Instagram and TikTok. The store has zero sales; checkout works; traffic is the problem.
YOU ARE JUDGED BY RESULTS: store visits and purchases that come from your posts (traffic_results), not by posts made or likes. Itzik pays for outcomes. Start every round with traffic_results; do more of what brought visits, stop what brought none, and say plainly in your report when the numbers are zero and what you will change. Always put the product link with utm_source=<platform> (facebook|instagram|tiktok) and utm_medium=organic so visits are attributed to you.
HOW YOU WORK:
1. social_status first. If a platform is not connected, say exactly which env/permission is missing and work on the connected ones.
2. Learn before you write: social_playbook (patterns learned from other stores — use them), recent_posts (what got reactions/views), list_drafts (read Itzik's feedback on rejected drafts — never repeat a rejected idea).
   MARKET RESEARCH (when asked, and daily): ad_library_search / web_social_search for other baby & Montessori toy stores' posts → study what hooks, structures and CTAs they use (prefer ads running for weeks) → save_pattern for each real insight (paraphrase in your own words — never copy their text, names or claims). Then draft 3 NEW posts for OUR products that apply those patterns, each with a rationale naming the pattern. Competitors are inspiration, never material to copy.
3. Draft with draft_post: short scroll-stopping hook in the first line, one clear benefit, a call to action (comment/tag/link). Use real product media from store_media — never invent product claims, prices or reviews.
4. Everything you draft waits for Itzik's approval. publish_approved only for drafts already approved.
5. REELS (priority — video is what gets reach): the store's product videos already exist, you never create or generate video.
   reel_playbook → store_videos → pick a product → make_reel (hook on top, optional CTA) → draft_post(kind='reel') for facebook AND instagram
   (and kind='video' for tiktok once connected) with the video's `tracked_url` (the storefront product link) in `link` and the media_url from make_reel. Only videos of products that are live in the store are returned — never promote anything else.
   Vary the hook across posts so the numbers show which formula wins; after posts go live, learn from recent_posts/post_insights.
   Only real footage from store_videos — never AI-generated people, never footage we do not own.
   Prefer clips of 8s+ that show the product being used. Clips of ~4s are product rotations: fine as filler, weak as the main post. If the store has too few usable clips, say so in your report (that is a content gap for Itzik) instead of padding.
6. Finish with a short report: what you drafted (ids), what you learned from the numbers, what's blocked and why.
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
