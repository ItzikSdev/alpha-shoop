# src/social_mcp — organic social over REAL MCP

One local MCP server (`python -m src.social_mcp.server`, stdio) for the store's own
**Facebook Page**, **Instagram Business account** and **TikTok** account. Used by
**Lia (Social Media Manager)** through `src/org/social_agent.py` → `client.py`.

Not the same as `src/tiktok_mcp` (TikTok **Ads** reporting) or `src/mcp_tools/meta_ads.py` (paid ads).

## Approval gate
`draft_post` → **pending** → Itzik decides in platform-app **Needs you**
(Approve = publish now · Hold · Send back with feedback · Instruct) →
`publish_approved` works only on approved drafts. There is no agent-callable approve.

## Setup — Meta (Facebook + Instagram)
1. The Instagram account must be **Business/Creator** and **linked to the Facebook Page**.
2. In the Meta app (developers.facebook.com) get a token with:
   `pages_show_list, pages_manage_posts, pages_read_engagement, pages_read_user_content,
   instagram_basic, instagram_content_publish, instagram_manage_comments, instagram_manage_insights`.
   A long-lived **Page** token in `FB_PAGE_ACCESS_TOKEN` is best; otherwise it is derived from `META_ACCESS_TOKEN`.
3. `.env`: `META_PAGE_ID` (already set), optional `META_IG_USER_ID`, optional `META_GRAPH_VERSION`.
4. Check: `GET /api/v1/social/status` — names exactly what's missing, never prints a token.

Media must be at a **public https URL** (Shopify CDN works). IG allows 100 API posts / 24h.

## Setup — TikTok organic posting
1. developers.tiktok.com → create an app → add **Login Kit** + **Content Posting API (Direct Post)**,
   scopes `user.info.basic, video.publish, video.list`, a redirect URI on your domain.
2. Verify the domain/URL prefix your videos are served from (needed for `PULL_FROM_URL`).
3. `.env`: `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_CONTENT_REDIRECT_URI`.
4. Ask Lia (or call the MCP tool) `tiktok_login` → open the URL → approve → `tiktok_complete_auth(code)`.
   Tokens are written to `.env` (`TIKTOK_USER_ACCESS_TOKEN`, `TIKTOK_USER_REFRESH_TOKEN`).
5. Until TikTok **audits** the app, posts are **private (SELF_ONLY)** — that's TikTok's rule.

## Verified here vs not
- Verified: MCP round-trip over stdio, approval gate, per-platform validation, status naming missing env, Lia's tool loop (scripted model).
- NOT yet verified against live Meta/TikTok APIs (no tokens were used) — first real post should be a test on the real page.
