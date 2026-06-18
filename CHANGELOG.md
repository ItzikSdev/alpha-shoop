# Changelog

Newest first. Each entry added by `/status` skill after completing a task.

---

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
