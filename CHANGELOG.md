# Changelog

Newest first. Each entry added by `/status` skill after completing a task.

---

## [2026-06-23 b] — Pivot storefronts to Shopify CLI Liquid themes (no gallery ZIPs, all native features)

Per user direction ("agent must use theme from shopify to use all features" →
https://shopify.dev/docs/api/shopify-cli/theme), pivoted the per-store local-dev +
deploy flow from headless Hydrogen to the **official Shopify CLI Liquid themes**
(`shopify theme pull/dev/push`), which give all native Shopify features (theme editor,
sections, app blocks, metafields, real-time dev). Starts from each store's **live theme**.

Feasibility verified live against lumibud-dev: `theme list`/`pull`/`push` authenticate
non-interactively with the store's **Admin API token** (via `SHOPIFY_CLI_THEME_TOKEN`).
`theme dev` is the one command that additionally needs a **Theme Access password**
(shptka_…) — surfaced in the UI as a one-time per-store credential.

Changes:
- `src/storefront/runner.py` — rewritten around `shopify theme`: `/pull` (live theme →
  stores/shopify/{slug}), `/run` (`theme dev` on a free port, real-time sync; requires a
  Theme Access password — returns a clear 400 if missing), `/deploy` (`theme push
  --unpublished --theme "<name>"` by default, or `--live --allow-live` when publish=true),
  `/stop`, `/logs`. Auth tokens are fetched server-to-server (admin token never hits the browser).
- `src/api/routes/stores.py` — new `GET /stores/{id}/theme-creds` (domain + admin token +
  Theme Access password + live theme id) for the runner; `theme_access_password` added to
  `StoreUpdateRequest`; list now returns `has_theme_password`.
- `src/stores/__init__.py` — `theme_access_password` column (migration) + getters/setters.
- `src/mcp_tools/theme_installer.py` — `install_free_theme` no longer downloads gallery
  GitHub ZIPs; it keeps the store's live theme (managed via the CLI). Old ZIP helpers retained, unused.
- `.github/workflows/storefront-theme.yml` — replaces the Oxygen workflow; `shopify theme
  push` on changes to stores/shopify/**, auth via `SHOPIFY_CLI_THEME_TOKEN` secret.
- docs-app: `storefrontClient.ts` + `StoresPage.tsx` rewired — Run in localhost = `theme dev`
  (captures the Theme Access password inline when needed), Upload to Shopify = `theme push`
  (admin token, no extra cred). `Architecture.tsx` diagram updated to the CLI theme layer.
- The earlier Hydrogen app was archived to `stores/shopify/_hydrogen-lumibud-dev/`.

Verified live: runner pulls the 362-file live Dawn theme; `theme push --unpublished`
returns an unpublished theme + preview URL; `theme dev` correctly demands a Theme Access
password. docs-app builds + all routes 200 on refresh.

Dependency: "Run in localhost" needs a Theme Access password (Theme Access app → shptka_…),
captured per-store in the UI. Deploy/CI work with the Admin token alone.

## [2026-06-23] — Per-store headless Hydrogen storefronts: local dev + 1-click Oxygen deploy from docs-app

Adds a full headless-storefront workflow driven from the docs-app **My Stores** page.
Built as two parallel subagent workstreams (backend/host + docs-app), then integrated.

Problem solved: each store can now get a React (Shopify Hydrogen) storefront, run it
locally, and deploy it to Oxygen — all from the dashboard. Also fixed docs-app navigation
(refresh used to reset to the home page; links had no real URLs).

Architecture: the API + docs-app run in Docker, but `npm run dev` / `shopify hydrogen
deploy` must run on the HOST. Split responsibilities:
- **Docker API** does Shopify-side work; **new host runner** does filesystem/process work;
  **docs-app** orchestrates both.

Backend/host:
- `src/stores/__init__.py` — `StoreConfig` + `stores` table gain `storefront_api_token`,
  `oxygen_deploy_token`, `storefront_slug` (migration via existing ALTER loop) +
  `update_store_storefront()` helper.
- `src/api/routes/stores.py` — `POST /stores/{id}/storefront/provision`: generates a
  Storefront API token (`storefrontAccessTokenCreate`) and publishes all custom
  collections to the Online Store publication (`publishablePublish`) — fixes the
  Storefront-API collection-visibility (404) issue. `StoreUpdateRequest` +
  list endpoint now carry `oxygen_deploy_token` / `storefront_slug` (localhost dev tool).
- `src/storefront/runner.py` — NEW standalone host FastAPI on 127.0.0.1:8788 (CORS for
  :3000/:5173). Endpoints: `/health`, `GET /storefronts`, scaffold / run / stop / deploy /
  logs. Scaffolds via the verified non-interactive `npm create @shopify/hydrogen` flags,
  writes `.env` from provision data, generates `app/styles/brand.css` from
  `_TONE_PALETTES`, tracks dev-server PIDs/ports (POSIX process-group kill).
- `Makefile` — `make storefront` runs the host runner. `.github/workflows/storefront-oxygen.yml`
  — subfolder-aware Oxygen deploy on push to `stores/shopify/**` (Node 22, repo secret
  `OXYGEN_DEPLOYMENT_TOKEN`).

docs-app:
- Converted from `useState` tabs to **react-router-dom** — real paths (`/stores`, `/agents`,
  …) and **refresh-safe** deep links (nginx fallback already existed). `App.tsx`,
  `Sidebar.tsx` (NavLink), `Overview.tsx` (useNavigate).
- `src/api/storefrontClient.ts` — talks to the host runner (:8788).
- `StoresPage.tsx` — per-store **Run in localhost** (provision → run → opens
  `localhost:<port>`), **Stop**, **Upload to Shopify** (Oxygen deploy with token capture),
  live status polling, and a paths/URLs block (folder, localhost, admin).
- `Architecture.tsx` — `SYSTEM_MERMAID` gains a Headless Storefront layer.

Verified live: provision returns a token + published 2 collections; runner run/stop cycles
the lumibud-dev storefront on :3001 (serves real products + Lumino theme); docs-app routes
all 200 on direct refresh; docs-app + storefront production builds pass.

Caveats: Oxygen deploy token must be created by the user (Shopify admin → Hydrogen channel)
— captured in the UI, can't be API-generated. Backend changes were `docker cp`'d + the api
container restarted; a `docker compose build api` bakes them in permanently. The runner is a
local-only dev tool (127.0.0.1); the Storefront token in the browser is read-only by design.

## [2026-06-22 16:30] — Fix CJ sourcing (keyword search + 1-QPS) + build out lumibud-dev (LED mood lighting)

Problem: a full [REBUILD] run on lumibud-dev (repointed from the old "Seedling & Co"
baby-clothing brand to "ambient LED mood lighting") branded + designed the store fine
but published **0 products**. Root cause found against the live CJ API:
- `search_trending_products` searched CJ by **categoryId only**, never by keyword. The
  LLM category resolver collapses every lighting term ("sunset lamp"/"galaxy projector")
  into one leaf ("LED Spotlights"), which returns the same 20 generic junk items
  (phone fill light, bicycle headlight, magnifier) — all rejected by the niche-gate.
- CJ's `product/list` actually supports a real keyword filter (`productNameEn`); the code
  never used it.
- CJ enforces a hard **1 request/sec** limit, so the 20-way parallel `asyncio.gather`
  detail fetch was throttled and dropped most candidates (only 1 survived).

Changes:
- `src/mcp_tools/sourcing.py` — added `_cj_get()`: a rate-limited (1.15s min interval,
  global lock) CJ GET that retries on the "Too Many Requests / QPS" error. `_fetch_detail`
  now uses it; detail fetches run **sequentially** (parallel gather tripped the throttle).
  `search_trending_products` now sends `productNameEn` (real keyword filter) instead of
  relying on categoryId, and caps detail lookups to 12 to bound latency.
- `src/agents/workers/trend_scraper.py` — when a brand exists, search by the store's
  **concrete product types** derived from niche+collections (`_get_niche_categories`)
  instead of the single abstract `product_category` (CJ names items by concrete type).
  Gate candidates against the broad `product_category` so any genuine on-niche type
  passes while clear filler is still rejected.

lumibud-dev result: 7 → curated to 6 on-niche ambient-lighting products published with
premium copy, images, .90 pricing + compare-at; brand "Lumino"; premium CSS applied &
design-approved; old baby collections/products/duplicate pages removed; About + Shipping
pages and nav repointed to LED content; homepage hero image + featured collection
repointed to the populated "Decorative Ambient Lamps" collection.

Caveats:
- Code edits were deployed into the running container via `docker cp` + `docker restart`
  (prod image has no source mount); a `docker compose build api` is needed to bake them in.
  Host source files ARE edited, so a rebuild will include them.
- Storefront is still **password-protected** (dev-store default) — must be disabled in
  Online Store → Preferences before it can actually sell. Currency/PayPlus also pending.
- CJ returned no true "galaxy/star projector" matches this run, so those two empty
  collections were deleted; catalog skews to decorative/ambient lamps + 1 LED strip kit.

---

## [2026-06-18] — Niche coherence: ONE category, curate + cap at 8 products

Problem: store had mixed, unrelated products (shoes + kitchen tools + electronics).
Goal: TANAOR-level coherence — one product type, everything fits, curated catalog.

Changes:
- `store_setup.py` brand brief now includes `product_category` — a single specific CJ search keyword that defines the ONLY product type the store sells
- `trend_scraper.py` now uses ONLY `product_category` (no multi-category spreading)
- `ecommerce.py` — 4-phase flow:
  1. **Curate**: list all Shopify products, LLM-validate each against `product_category`, delete off-niche ones
  2. **Cap**: count remaining — skip if already at 8 products
  3. **Validate**: for each new candidate, LLM yes/no fit check before publishing
  4. **Publish**: brand + copy + upload (unchanged quality)
- `shopify.py` — added `list_shopify_products()` and `delete_shopify_product()`
- Hard cap `_MAX_STORE_PRODUCTS = 8`

---

## [2026-06-18] — Add Design Agent (Senior UI/UX — premium CSS injection)

New `design_agent` node runs once after `store_setup`, before products are scraped.
Reads the brand brief + Horizon theme state, then uses an LLM with a detailed
senior-designer system prompt to generate production-grade custom CSS:
typography hierarchy, breathing room (80px+ padding), sharp-corner premium buttons,
product card image zoom on hover, glass-morphism sticky header, announcement bar,
footer, and mobile responsiveness.

CSS is written to `assets/custom-alpha.css` and auto-injected into `layout/theme.liquid`.

Files:
- `src/agents/workers/design_agent.py` — NEW node (`design_node`)
- `src/mcp_tools/shopify_design.py` — `add_custom_css()` + `read_theme_context()`
- `src/agents/state.py` — `store_designed: bool` field
- `src/agents/graph.py` — wired `design_agent` node + edge
- `src/agents/director.py` — routing rule: store_setup → design_agent → trend_scraper
- `docs-app/src/pages/RunsPage.tsx` — NODE_META entry (pink #EC4899, ✦ icon)

---

## [2026-06-18 12:30] — Fix navigation 403 — switch to GraphQL menuUpdate

`menus.json` REST endpoint removed in Shopify API 2024-07 → returned 403.
Replaced with GraphQL `menuCreate` / `menuUpdate` mutations.
Key findings: default menus (main-menu) cannot be deleted — must use `menuUpdate` in-place.
`menuUpdate` requires `title` as mandatory arg. `$items` must be non-nullable (`[MenuItemUpdateInput!]!`).
Items use `type: HTTP` with full `https://{domain}/...` URLs.
Tested live: menu now has 5 items (3 collections + About Us + Shipping & Returns). `userErrors: []`.
- Files: `src/mcp_tools/shopify_theme.py`

## [2026-06-18 10:00] — Architecture page zoom + fullscreen + diagram redesign

Rewrote `MermaidDiagram.tsx` to support real zoom (resizes the container div so the responsive SVG scales naturally, not CSS `zoom` magnifying-glass). Added fullscreen button via Fullscreen API. Added Ctrl+scroll support.
Redesigned both diagrams: `mcp.mmd` moved to `LR` layout (Client → Protocol Engine → Tools → External APIs, no bidirectional arrows). `SYSTEM_MERMAID` in `Architecture.tsx` moved to clean layered `TB` with `direction LR` inside subgraphs.
Fixed `mcp.mmd` text invisible on dark background — classDef fills were near-white (#f9fbfd); replaced with dark fills matching the dark theme.
- Files: `docs-app/src/components/MermaidDiagram.tsx`, `docs-app/src/pages/Architecture.tsx`, `docs-app/public/mcp.mmd`

## [2026-06-17 18:00] — Architecture page updated with new components

Added `store_setup` node, `shopify_theme.py` flow, JWT auth endpoint, niche-aware scraper, and observability layer to the Full System diagram in `Architecture.tsx`.
Updated description text to mention zoom capability.
- Files: `docs-app/src/pages/Architecture.tsx`

## [2026-06-17 17:30] — shopify_theme.py marquee block fix

Fixed `build_homepage()` marquee blocks: was using block type `_item` (wrong), corrected to `text`. Text content must be `<p>`-wrapped per Horizon schema. Replaced `media-with-content` (no blocks schema) with `custom-liquid` for brand story section — full HTML control.
- Files: `src/mcp_tools/shopify_theme.py`

## [2026-06-17 14:00] — shopify_theme.py — full Horizon theme customization

New file: `src/mcp_tools/shopify_theme.py`. Implements `full_store_setup(brief)` which orchestrates:
1. `apply_brand_colors` → `config/settings_data.json`
2. `set_announcement_bar` → `sections/header-group.json`
3. `build_homepage` → `templates/index.json` (hero → marquee → product-list → custom-liquid story → collection-list)
4. `setup_navigation` → `menus.json` REST (403 issue pending)
Tone palettes: warm, bold, minimal, playful, trustworthy.
- Files: `src/mcp_tools/shopify_theme.py` (new), `src/agents/workers/store_setup.py`

## [2026-06-17 12:00] — store_setup node expanded — TANAOR-quality brand brief

Rewrote `store_setup.py` brand brief prompt to require `differentiator` (specific, tangible, verifiable) and `announcement_bar` (pipe-separated trust signals). Added `_parse_json()` to strip LLM code fences — this fixed the infinite loop where empty brief caused director to re-route to store_setup endlessly.
- Files: `src/agents/workers/store_setup.py`

## [2026-06-17 11:30] — Niche-aware trend scraper

Rewrote `trend_scraper.py`: reads `store_brand` from state, uses LLM (Haiku) to translate niche + collections → 2–4 CJ category keywords. Searches each category separately, merges results, deduplicates. Previously scraper searched generic categories unrelated to the store.
- Files: `src/agents/workers/trend_scraper.py`

## [2026-06-17 11:00] — Product publishing fix + price cap

Added `_publish_product()` to `shopify.py`: calls REST `PUT /products/{id}.json` with `{"product": {"published": true}}` after every `productCreate`. GraphQL `status: ACTIVE` does not auto-publish to Online Store channel.
Added retail price cap: if `suggestSellPrice / supplierPrice > 3.0`, uses `supplierPrice * 2.5` instead. CJ was returning 6.9× markups.
Added `max_price_usd` filter to sourcing.
- Files: `src/mcp_tools/shopify.py`, `src/mcp_tools/sourcing.py`

## [2026-06-17 10:30] — JWT auth endpoint + frontend auto-token

New file: `src/api/routes/auth.py` — `POST /api/v1/auth/token`. In dev mode issues JWT freely (no password). Registered in `src/main.py`.
New file: `docs-app/src/api/client.ts` — `getToken()`, `apiFetch()`, `apiGet()`, `apiPost()`. Checks localStorage, auto-refreshes on expiry, injects `Authorization: Bearer` header.
New file: `run.sh` — shell script that auto-fetches token and polls run status.
Updated `RunsPage.tsx` to use `apiGet`/`apiPost`.
- Files: `src/api/routes/auth.py`, `src/main.py`, `docs-app/src/api/client.ts`, `docs-app/src/pages/RunsPage.tsx`, `run.sh`

## [2026-06-17 10:00] — Shopify app scopes expanded

Updated `shopify.app.toml` and `get_shopify_token.py` to add: `read_themes`, `write_themes`, `read/write_online_store_navigation`, `read/write_script_tags`, `read/write_metaobjects`, `read/write_publications`. Required for theme customization via Assets API.
- Files: `shopify.app.toml`, `get_shopify_token.py`

## [2026-06-17 09:00] — Director + ecommerce JSON code fence fix

Added `import re` and inline `re.sub` stripping of ` ```json ` fences in `director.py`. Added `_parse_json()` helper to `ecommerce.py`. LLM responses wrapped in code fences caused `json.loads()` to throw, returning empty dict and triggering infinite re-routing loops.
- Files: `src/agents/director.py`, `src/agents/workers/ecommerce.py`
