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

from src.social_mcp import meta, publish, queue, reel, research, tiktok

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


@mcp.tool()
async def store_videos(limit: int = 20, query: str = "") -> dict:
    """Products that ALREADY have a video on the store (direct https .mp4 + the product page URL).
    We do not generate videos — reels are made from these. `query` = Shopify product search."""
    try:
        vids = await reel.list_store_videos(limit, query)
        if not vids:
            return {"ok": False, "error": "no product videos found on the store (or Shopify is unreachable)"}
        return {"ok": True, "videos": vids}
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def make_reel(video_url: str, hook: str, cta: str = "", start: float = 0.0,
                    max_seconds: float = 15.0) -> dict:
    """Turn one EXISTING store video into a vertical 9:16 reel (<=15s): hook text on top the whole
    time, optional CTA text in the last 3s, source audio removed. Uploads it to Shopify Files and
    returns `media_url` (public https) to pass to draft_post(kind='reel'/'video')."""
    try:
        return {"ok": True, **await reel.make_reel(video_url, hook, cta, start, max_seconds)}
    except Exception as e:  # noqa: BLE001
        return _err(e)


REEL_PLAYBOOK = {
    "source": "Studied a viral organic reel (~99K views) from another baby-product store, 2026-10.",
    "format": [
        "8-15 seconds, vertical 9:16, ONE continuous shot or two — real footage, no AI-made people.",
        "Show the product being used / put on / opened; the reveal or best moment lands in the last 2-3 seconds.",
        "Hook text sits at the top from the very first frame and stays on the whole video.",
    ],
    "hook_formulas": [
        "Don't let a [type]-loving mom see this 😍   (names the buyer + curiosity)",
        "POV: you found the [product] before everyone else",
        "Wait for the end 👀",
        "Every new mom needs to see this",
    ],
    "caption": "Two lines max. 'More info here ⬇️' + the product link (or 'link in bio'). 1-3 relevant hashtags.",
    "sound": "The viral reel used a trending in-app sound. The API cannot attach one — reels are rendered silent; "
             "when Itzik approves, he can add a trending sound in the app, or leave it silent.",
    "do_not": [
        "Copy another store's theme or any trademarked character/brand (the reference reel was Harry-Potter themed - do NOT).",
        "Invent reviews, prices, scarcity or 'going viral / low stock' claims.",
        "Use footage of children that we do not own or have permission for.",
    ],
    "measure": "After a post is live: recent_posts + post_insights; compare views/saves/shares per hook formula and keep what wins.",
}


@mcp.tool()
def reel_playbook() -> dict:
    """What makes the short product reels work (hook formulas, structure, caption, what to avoid). Read before make_reel."""
    return REEL_PLAYBOOK


@mcp.tool()
async def ad_library_search(query: str, countries: list[str] | None = None, limit: int = 12) -> dict:
    """Meta Ad Library: ads OTHER advertisers run right now (copy, headline, how long running).
    If it says needs_owner, the owner must unlock the API once — use web_social_search meanwhile."""
    try:
        return await research.ad_library_search(query, countries, limit)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
async def web_social_search(query: str, num: int = 8) -> dict:
    """Public web results on how other brands post (e.g. 'montessori toy brand facebook post hook')."""
    try:
        return await research.web_social_search(query, num)
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def save_pattern(source: str, brand: str, hook_type: str, hook_example: str, structure: str, cta: str,
                 why_it_works: str, url: str = "", platform: str = "", tags: list[str] | None = None) -> dict:
    """Keep ONE learned pattern in the playbook. Paraphrase — hook_example <=140 chars, never a copy.
    hook_type: question|bold-claim|problem-agitate|demo-in-first-second|social-proof|curiosity-gap|relatable-moment|how-to|before-after|other"""
    return research.save_pattern(source, brand, hook_type, hook_example, structure, cta, why_it_works,
                                 url, platform, tags)


@mcp.tool()
def social_playbook(limit: int = 25, hook_type: str = "", platform: str = "") -> dict:
    """Everything learned from other stores' posts so far. Read before every draft."""
    return research.read_playbook(limit, hook_type, platform)


TOOL_NAMES = ["social_status", "draft_post", "list_drafts", "publish_approved", "recent_posts",
              "read_comments", "post_insights", "tiktok_login", "tiktok_complete_auth", "tiktok_publish_status",
              "store_videos", "make_reel", "reel_playbook",
              "ad_library_search", "web_social_search", "save_pattern", "social_playbook"]

if __name__ == "__main__":
    mcp.run()
