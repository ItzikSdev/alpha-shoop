<!-- Level 18 of store-builder-trending-cj · status lives in ../store-builder-trending-cj.md (traffic lights) -->

# Level 18 — The platform around the store: 3D Office, alpha-beacon, Lia / organic social (v3.15)

Why this level exists: until v3.14 this skill only described the *store*
(products, pages, sourcing, ads). Since 2026-10-03 there is a second
system around it that already exists and must not be rebuilt or
re-researched: the agent team (`src/org`), the dashboard `platform-app`
with the **3D Office**, the live-visitor pipeline **alpha-beacon**, and
**Lia + the social MCP** for organic traffic. Read this before touching
any of them, before saying "we don't have X", and before proposing paid
ads (Itzik's current direction is organic only — see §5).

Repo root = `~/Documents/git/alpha-shoop`. Store code = `stores/shopify/hydrogen-alphaforbaby`.
Never print, copy or paste a token/secret from `.env`; this file lists key
**names** only.

## 1. What exists today (map)

| Piece | Where | State (2026-10-04) |
|---|---|---|
| Agent team: Ava, Sol, Reel, Nora, Milo, Kai, Nova, Lia | `src/org/` (seed.py = charters, daemon/heartbeat = 30-min ticks, capabilities.py = what each role needs, proposals.py = "Needs you" queue) | Running. Own Telegram bot per agent (`TELEGRAM_BOT_TOKEN_<NAME>`). |
| Dashboard | `platform-app/` (Vite/React, http://localhost:5173, pages in `src/pages/`) | Running locally. Pages incl. Agents, Company, Tickets, Runs, Finance, Stores, Videos, **Office**. |
| 3D Office | `platform-app/src/pages/Office.tsx`, `office/Scene.tsx` (React Three Fiber), `office/Panel.tsx`, `office/types.ts` → http://localhost:5173/office | Built, committed 2026-10-03 (`2441022`). Shows agents at desks + the **"Alpha for Baby" store building** with real visitors as figures. |
| alpha-beacon (live visitors) | `src/visitors/beacon_app.py`, `src/visitors/events.py`, `src/api/routes/visitors.py`; docker services `beacon`, `cloudflared` (profile `tunnel`) in `docker-compose.yml` | Backend live: `https://beacon.alpha-tech.live/v` via Cloudflare Tunnel `alpha-beacon`. **Storefront sender not deployed yet** (§3). |
| Lia + social MCP | `src/org/social_agent.py`, `src/social_mcp/` (README there), queue `data/social_queue.json`, playbook `data/social_playbook.json` | Facebook Page works. **Instagram not linked. TikTok not connected.** Drafts only. |
| Design lock | `src/org/design_lock.py` | On. Agents cannot write to a Shopify theme (Itzik, 2026-10-03). |

## 2. 3D Office (platform-app)

- Polls the private API every 4 s: agents, tasks, and `GET /api/v1/visitors/live`
  (no auth from localhost:8000). Rendering: agents at desks, a store
  building, a queue outside it, one **VisitorFigure** per live visitor, placed
  by funnel stage (see `EVENT_STAGE` in `src/visitors/events.py`).
- A visitor is anonymous: random id → hash, country/source/stage only. No
  name, email, IP, cart contents.
- Changing the scene = edit `office/Scene.tsx` / `types.ts`; the data
  contract is `visitors/live` → `{visitors, counts}`. Don't add a second
  polling path.
- If /office shows nobody, the first suspect is that **no events arrive**
  (§3), not the 3D code. Check Redis `vis:*` keys before touching the scene.

## 2b. Opening platform-app from the phone (home WiFi only)

- Cloudflare DNS (zone alpha-tech.live): **A `platform` → 10.100.102.23** (the Mac mini's LAN IP), **DNS only**, no proxy — added 2026-10-04 with Itzik's OK. Resolves to a private IP, so it works only on the home WiFi. URL: `http://platform.alpha-tech.live:5173`.
- Needs: Vite dev server running (`allowedHosts` in `platform-app/vite.config.ts`), API CORS regex in `src/main.py` includes the name; Mac should have a fixed IP (DHCP reservation) or the record breaks if the IP changes. Some routers block public DNS answers with private IPs (rebinding protection).
- The API on :8000 has no login — anyone on the home WiFi can use it.

## 3. alpha-beacon — how a real visit reaches the 3D store

```
shopper browser
  ├─ Hydrogen storefront (alphaforbaby.com):  app/components/VisitorBeacon.jsx   ── POST ─┐
  └─ Shopify checkout (checkout.alphaforbaby.com): custom pixel "Alpha live visitors" ── POST ─┤
                                                                                           ▼
        https://beacon.alpha-tech.live/v  (Cloudflare Tunnel "alpha-beacon" → docker `beacon` :8100)
                                                                                           ▼
        Redis  vis:<hash>  (TTL 900 s)  ←──  private API  GET /api/v1/visitors/live  ←── platform-app (4 s poll)
```

Facts that already cost time — do not rediscover:

- **Shopify Custom Pixels (Settings → Customer events) do NOT run on the
  Hydrogen/Oxygen storefront pages** (headless: no web-pixels sandbox,
  response header `powered-by: Shopify, Oxygen, Hydrogen`). They only
  run on Shopify-hosted **checkout**. So the pixel alone shows a visitor
  only once they reach checkout. Browsing is covered by `VisitorBeacon.jsx`.
- The pixel is "Alpha live visitors" (`.../settings/customer_events/pixels/custom/167182407`),
  status Connected, **Permission = "Not required"** (it was "Required" =
  waits for a consent banner; the store has **no cookie banner** and Itzik
  chose "no cookies / בלי עוגיות" on 2026-10-03). The warning "not
  subscribed to any events" in the editor is Shopify static analysis
  (subscriptions inside a loop) — ignore it. Source: `scripts/shopify_visitor_pixel.js`
  (placeholder token) / `.ready.js` (real token, gitignored — paste this one).
- **VisitorBeacon (storefront)**: `app/components/VisitorBeacon.jsx`,
  mounted in `app/root.jsx` right after `<MetaPixel/>` inside
  `Analytics.Provider`. Same `useAnalytics().subscribe` pattern as
  `MetaPixel.jsx`. Sends: page_viewed, collection_viewed,
  search_viewed→search_submitted, product_viewed, product_added_to_cart,
  cart_viewed. `fetch(..., {keepalive:true, mode:'no-cors', headers:{'Content-Type':'text/plain'}})`
  (text/plain avoids a CORS preflight). Visitor id = random per
  `sessionStorage['_av']` (no cookie, no PII, no cart contents; purchase
  is sent by the checkout pixel only). Inert if url/token are empty.
- **Config keys** in `app/theme.config.json`: `visitorBeaconUrl`,
  `visitorBeaconToken` (= `VISITOR_BEACON_TOKEN` from repo `.env`; an
  anti-noise token, not a secret of value, but still never paste it into chat).
  **CSP**: `https://beacon.alpha-tech.live` added to `connectSrc` in
  `app/entry.server.jsx` (`createContentSecurityPolicy` overrides REPLACE
  the defaults — when adding another host repeat the existing ones).
- **Beacon rules** (`beacon_app.py`): accepts only events in
  `EVENT_STAGE` (page_viewed, collection_viewed, search_submitted,
  product_viewed, product_added_to_cart, cart_viewed, checkout_started,
  checkout_contact_info_submitted, payment_info_submitted,
  checkout_completed); **204** ok, **403** wrong token, **429** >40 events/min
  per visitor. Cloudflare blocks the default `Python-urllib` User-Agent —
  set a UA when testing with Python. Only route is `POST /v`; no
  docs/openapi; nothing is read back.
- Infra keys in `.env` (names only): `VISITOR_BEACON_TOKEN`,
  `CLOUDFLARE_TUNNEL_TOKEN`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`,
  `REDIS_URL`. Start the tunnel: `docker compose --profile tunnel up -d cloudflared beacon`.
- **Status 2026-10-04**: VisitorBeacon code is written and syntax-checked but
  **uncommitted and not deployed** → real storefront visitors are still
  invisible. Deploy = commit + push to `alphaforbaby/production` (Oxygen),
  which needs Itzik's explicit go-ahead (Level 17: nothing is live until
  pushed and Oxygen shows a new deployment). **Verify after deploy**: open
  alphaforbaby.com from a phone (e.g. via Facebook), a figure appears in
  /office within ~10 s; or `GET /api/v1/visitors/live` shows `counts`.
- Not changed by this work: store design. VisitorBeacon renders `null`.

## 4. Lia (social) and the social MCP

- **Role**: organic social for the store's own Facebook Page, Instagram
  and TikTok. Goal (Itzik, 2026-10-03): **visitors without paid ads**.
  Code: `src/org/social_agent.py` (system prompt/rules), `src/social_mcp/`.
- **Tools**: social_status, recent_posts, read_comments, post_insights,
  list_drafts, draft_post, publish_approved, store_media, store_videos,
  reel_playbook, make_reel, ad_library_search, web_social_search,
  save_pattern, social_playbook.
- **Approval gate (hard)**: `draft_post` → *pending* → Itzik decides in
  platform-app **Needs you** (Approve = publish now · Hold · Send back ·
  Instruct) → `publish_approved` works only on approved drafts. No
  agent-callable approve. Never publish anything without it.
- **Video rule**: never generate video. Use videos that already exist on
  the store's products: `store_videos` → `make_reel` (crop 9:16, ≤15 s, hook
  line + CTA burned in, source audio removed, uploaded to Shopify Files —
  needs `write_files` scope → public `media_url`) → `draft_post`. Reel
  (the video agent) is *not* the one producing this; Lia owns the
  "take the product's store video and publish it" flow (Itzik, 2026-10-03).
  Today the store has **one** usable product video (Montessori egg).
- **make_reel needs `ffmpeg`/`ffprobe` + Pillow.** The API Docker image
  lacked ffmpeg → `Dockerfile` apt line now includes `ffmpeg` (comment
  there). Takes effect only after `docker compose build api && docker compose up -d api`
  (the `beacon` service shares the image). Until rebuilt, make_reel fails.
- **Daily research**: `_lia_research_tick` (24 h) in `src/org/heartbeat.py`
  (needs the daemon enabled); writes patterns to `data/social_playbook.json`.
- **Connection status** (`python -m src.social_mcp.connect status`, run in
  Itzik's own terminal — tokens never go through chat):
  - Facebook Page "ALPHA for BABY": connected (`META_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`).
  - **Instagram: NOT connected.** `META_IG_USER_ID` absent; Meta says "no
    Instagram Business account is linked to this Facebook Page"; the
    Business portfolio has no IG accounts. Itzik created the account but it
    is a plain personal one. Fix (his action, in the Instagram app/web):
    switch the account to a **Professional (Business/Creator)** account and
    connect it to the Facebook Page, then run `python -m src.social_mcp.connect meta`.
  - **TikTok: not connected** (`TIKTOK_APP_ID/SECRET` exist; no user token;
    Lia's `ROLE_NEEDS` in `capabilities.py` lists the TikTok keys).
  - Meta app "Alpha for Baby" (`META_APP_ID`); organic tokens are separate
    from `META_ACCESS_TOKEN*` (those are for paid ads/reporting).
- Distinct from `src/tiktok_mcp` (TikTok **Ads** reporting) and
  `src/mcp_tools/meta_ads.py` (paid ads) — don't confuse them.

## 4b. Results scorecard — agents are judged by traffic and sales (Itzik, 2026-10-04)

- **Mandate**: "everyone's job is getting real visitors to the store";
  success = visits and purchases by source, not activity. Written into
  `_MANDATE_GOALS` / `_MANDATE_VALUES` in `src/org/seed.py` (reaches every
  agent through company goals on reconcile). The stale "$50 Meta Ads
  campaign" goal is removed on reconcile.
- **Daily counters by source**: `beacon_app.py` → `events.count_progress`
  writes Redis hash `visday:<YYYY-MM-DD>` (`<source>|visits|product|cart|
  checkout|purchased|revenue`, kept 400 days; anonymous aggregates).
  Read with `GET /api/v1/visitors/results?days=7` or Lia's tool
  `traffic_results`. Counting starts only once the storefront VisitorBeacon
  is deployed (checkout pixel alone only sees checkouts).
- **Lia**: new tool `traffic_results` (`src/org/social_agent.py`, in
  catalog group "results"); her prompt/charter say she is judged by it,
  must start every round with it, use `utm_source=<platform>&utm_medium=organic`
  on every link, and report zeros honestly.
- **Posting cadence**: `_lia_post_tick` in `src/org/heartbeat.py` — a round
  every ~6 h (`lia_post_interval_hours`), skipped while >= 4 drafts wait
  for Itzik (`lia_max_pending`). Daily research tick unchanged. Drafts only.
- All of this needs an API restart to take effect; not tested against a
  live Redis (logic checked with a fake Redis).

## 5. Strategy change that overrides older text in this skill

- **2026-10-03 — Itzik: get visitors to the store without paid
  advertising.** The older goal text ("start selling through paid ads",
  Level 16's $5 ad test) is **on hold, not deleted**. Do not launch or
  budget any ad. Level 16 §6 "same video posted organically on TikTok /
  Instagram Reels / Facebook" is now the main path, run by Lia (§4).
- A stale company goal in the org DB still reads "Launch $50 Meta Ads
  campaign…" — not changed yet (needs Itzik's OK to edit).
- "Sol and the other org agents are no longer involved" (Level 17,
  2026-09-25) is **superseded for the platform**: the agents exist and run
  (Needs-you queue, Lia, Nora support etc.). Store *building* (theme/
  design/code) is still done by Claude (Cowork), not by agents — see §6.

## 6. Rules the platform enforces (don't fight them)

1. **Design lock** (`design_lock.py`): agent code paths cannot write to a
   Shopify theme (asset PUT/POST/DELETE, theme create/publish, theme
   GraphQL mutations, apply-design route). GET stays allowed. Lifted only
   deliberately with `ALLOW_THEME_CHANGES=on`. Itzik: "שלא ישנו עיצוב של חנות".
2. **Approval first** for anything outward-facing (posts, ads, price,
   publish). Read-only Shopify GETs need no approval; writes do.
3. Secrets stay in repo `.env`; never in chat, files in the skill, or
   committed code. (Telegram/Meta tokens were exposed in earlier chats —
   rotating them is an open item.)
4. Itzik writes Hebrew; reply in Hebrew, short, one decision at a time.

## 7. Open items (owner in brackets)

1. Deploy Hydrogen `VisitorBeacon` (commit + push `alphaforbaby/production`) [Itzik's go-ahead → Claude].
2. `docker compose build api && docker compose up -d api` for ffmpeg [Itzik, his terminal].
3. Link Instagram to the Facebook Page, then `connect meta` [Itzik].
4. Ask Lia to make the first reel from the Montessori egg video → approve in Needs you [Itzik].
5. Connect TikTok organic [Itzik].
6. Update stale paid-ads company goal [Itzik's OK].
7. Delete `.git/index.lock.stale-by-claude` (leftover from a blocked unlink) [Itzik].
8. Rotate exposed Telegram/Meta tokens [Itzik].
9. Pre-existing eslint note: `'context'` unused at `root.jsx` ~line 152 (not from this work).
10. Level 14 has no tests for any of this yet — a minimal one would assert
    `visitorBeaconUrl` is set, its host is in the CSP `connectSrc`, and
    `VisitorBeacon` is mounted in `root.jsx`.
