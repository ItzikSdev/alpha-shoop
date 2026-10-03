"""Social media MCP server (stdio) — Facebook Page, Instagram Business, TikTok.

Tools (what the social agent gets):
    social_status()                      what's connected on each platform (+ exact missing env names)
    draft_post(platform, kind, ...)      queue a draft for human approval — NEVER publishes
    list_drafts(status, platform)        the queue, incl. the human's feedback on sent-back drafts
    publish_approved(draft_id)           publish ONLY a human-approved draft
    recent_posts(platform, limit)        the page's own recent posts with engagement (learn what works)
    read_comments(platform, post_id)     comments on a post (FB/IG)
    post_insights(platform, post_id)     engagement numbers for one post
    tiktok_login / tiktok_complete_auth  one-time OAuth for organic TikTok posting
    tiktok_publish_status(publish_id)    TikTok processing state of a post

No approve tool on purpose: approval is a human action (platform-app "Needs you"
or POST /api/v1/social/drafts/{id}/approve).
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.social_mcp import meta, publish, queue, tiktok

mcp = FastMCP("social")


def _err(e: Exception) -> dict:
    return {"ok": False, "error": str(e)[:300]}


@mcp.tool()
async def social_status() -> dict:
    """Per platform: ok/not, account name, followers, and EXACT missing env names (never values)."""
    return await publish.all_status()


@mcp.tool()
def draft_post(platform: str, kind: str, message: str, link: str = "", media_url: str = "",
               author: str = "Lia", rationale: str = "") -> dict:
    """Queue a post for human approval. platform/kind: facebook: text|link|photo|reel;
    instagram: photo|reel; tiktok: video. Media must be a PUBLIC https URL.
    `rationale` = why this post, in one line (the human sees it when deciding)."""
    try:
        return {"ok": True, "draft": queue.add_draft(platform, kind, message, link=link, media_url=media_url,
                                                    author=author, rationale=rationale)}
    except ValueError as e:
        return _err(e)


@mcp.tool()
def list_drafts(status: str = "", platform: str = "") -> dict:
    """Drafts filtered by status (pending|held|approved|rejected|published) and/or platform.
    Rejected drafts carry the human's `feedback` — read it before drafting again."""
    return {"drafts": queue.list_drafts(status, platform)}


@mcp.tool()
async def publish_approved(draft_id: str) -> dict:
    """Publish a draft. Refused unless a human approved it."""
    return await publish.publish_draft(draft_id)


@mcp.tool()
async def recent_posts(platform: str, limit: int = 10) -> dict:
    """The page's own recent posts with engagement — facebook | instagram | tiktok."""
    try:
        posts = await (tiktok.recent_videos(limit) if platform == "tiktok" else meta.recent_posts(platform, limit))
        return {"ok": True, "posts": posts}
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def read_comments(platform: str, post_id: str, limit: int = 25) -> dict:
    """Comments on one Facebook/Instagram post (TikTok has no organic comments API)."""
    if platform == "tiktok":
        return {"ok": False, "error": "TikTok's public API has no comments endpoint for organic posts"}
    try:
        return {"ok": True, "comments": await meta.comments(platform, post_id, limit)}
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def post_insights(platform: str, post_id: str) -> dict:
    """Engagement for one published Facebook/Instagram post (TikTok: use recent_posts)."""
    try:
        return {"ok": True, **await meta.insights(platform, post_id)}
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def tiktok_login() -> dict:
    """Step 1 of TikTok OAuth: returns the URL the OWNER opens to approve posting."""
    return tiktok.login_url()


@mcp.tool()
async def tiktok_complete_auth(code: str) -> dict:
    """Step 2 of TikTok OAuth: exchange the `code` from the redirect URL; persists tokens to .env."""
    try:
        return await tiktok.complete_auth(code)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def tiktok_publish_status(publish_id: str) -> dict:
    """TikTok processing state for a publish_id returned by publish_approved."""
    try:
        return {"ok": True, **await tiktok.publish_status(publish_id)}
    except Exception as e:  # noqa: BLE001
        return _err(e)


TOOL_NAMES = ["social_status", "draft_post", "list_drafts", "publish_approved", "recent_posts",
              "read_comments", "post_insights", "tiktok_login", "tiktok_complete_auth", "tiktok_publish_status"]

if __name__ == "__main__":
    mcp.run()
