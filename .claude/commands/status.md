# Alpha Shoop — Status & Next Steps

You are the project intelligence for **Alpha Shoop**.
When invoked, read the project state and report exactly where we stopped and what to do next.

## Step 1 — Read these files

Read all of them before responding:

**Changelog & architecture**
- `CHANGELOG.md` — source of truth for what's done (newest first)
- `docs/architecture.md` — system architecture, 3 diagrams, notes on what's stale
- `platform-app/public/mcp.mmd` — MCP layer diagram
- `platform-app/src/pages/Architecture.tsx` — full system diagram (SYSTEM_MERMAID constant)

**Agents & tech stack**
- `platform-app/src/pages/Agents.tsx` — all AI agents, their models and responsibilities
- `platform-app/src/pages/Technologies.tsx` — full tech stack

**Core source**
- `src/agents/orchestrator.py` — single deterministic pipeline (replaced director.py + graph.py)
- `src/agents/workers/store_setup.py`
- `src/mcp_tools/shopify_theme.py`
- `src/mcp_tools/shopify.py`
- `src/mcp_tools/sourcing.py`
- `src/api/routes/auth.py`

## Architecture: one orchestrator, not 7 routed agents

`src/agents/director.py` and `src/agents/graph.py` are **deleted**. The old design had
an LLM call after every single step just to decide which worker ran next — its
"routing rules" were almost entirely mechanical and it was the direct cause of a real
bug (trend_scraper returning 0 candidates got re-called identically 15+ times,
burning ~1.5M tokens, before a circuit breaker existed).

`src/agents/orchestrator.py::run_pipeline(state)` is now the single entry point — an
async generator yielding `{"node_name": delta}` after each step (same shape
`graph.astream()` used to produce, so `src/api/routes/agents.py` barely changed). It
reads the same task-tag convention as before (`[REBUILD]`, `[SETUP_ONLY]`,
`[MARKETING]`, `[MONITOR]`) and sequences the **unmodified** worker functions in
`src/agents/workers/*.py` with plain Python control flow:
store_setup → design loop (Mode 1/Mode 2, self-terminates by iteration 3) →
catalog-fill loop (stops at `_MAX_STORE_PRODUCTS` or on worker-set `error`) →
marketing (if tagged) → fulfillment (if pending_orders).

LLM call tracing (the "LLM Calls" tab in platform-app) used to work because LangGraph
propagated `config={"callbacks": [...]}` to every node automatically. Without the
graph, `src/llm/client.py::get_llm()` reads the active `TraceCallback` from a
contextvar (`src/tracing/context.py::current_trace_callback`, set once in
`_execute_graph`) instead — no per-worker changes needed.

Tests: `tests/test_orchestrator.py` replaces `tests/test_director.py`, mocking worker
functions directly instead of an LLM.

## Store & Agent Design Rules

These are the established standards the agents are built to follow. They live as
system prompts/logic in the files noted below — this section is a map of where to
look and why, not a substitute for reading the actual code before changing it.

**Visual style** (`design_agent.py` `_SPEC_SYSTEM`, `frontend_agent.py` `_FRONTEND_SYSTEM`):
- Palette is now black/white/yellow, pattern-matched from **terminalx.com's real
  production CSS** (fetched and grepped directly, not guessed): accent yellow is the
  verified `#FEFA03` (54 occurrences in their stylesheet — an earlier guess of
  `#FFE600` was wrong and got corrected). Red (`#C92527`) is form-validation only in
  their real CSS, never sale/promo — don't use red for badges.
- Typography: body font Arimo (real, free Google Font, confirmed in their CSS);
  headings use a bold condensed face — ITC Roswell is what they use but it's
  proprietary, so we substitute the free Google Font "Oswald".
- Buttons invert on hover (confirmed real behavior): black bg/white text ↔ yellow
  bg/black text.
- Structural rules — same as before: nav active link = accent underline (never bg
  fill), hero headline directly over the image with one accent-colored word,
  featured-collection heading left-aligned uppercase (never centered), dark footer
  with social/newsletter columns.
- **CSS specificity gotcha (verified live, cost real debugging time twice):** this
  theme loads component-specific stylesheets (`component-list-menu.css`,
  `section-image-banner.css`, `section-footer.css`) **after**
  `assets/custom-alpha.css` in `<head>`. Equal-specificity rules from Dawn's own
  CSS win on source order alone — nav/banner/footer/featured-collection overrides
  need `!important`, or they get silently ignored even though the file is correctly
  linked and served. Also verify selectors against the REAL rendered HTML, not
  assumed Dawn conventions (e.g. `.header__menu-item` is on the `<a>` itself, not a
  wrapping parent — `.header__menu-item > a` matches nothing).
- `full_store_setup()` (in `shopify_theme.py`) **replaces** `templates/index.json`
  wholesale with its own generic section names — if you've hand-built custom
  homepage sections (trust bar, category grid, a set banner image) and then call
  `full_store_setup`, it silently wipes them. Re-apply custom sections (and the
  banner `image` setting) AFTER calling it, not before.

**Product catalog** (`ecommerce.py`, `trend_scraper.py`, `orchestrator.py`):
- `_MAX_STORE_PRODUCTS = 30` — hard cap, curated not crowded.
- The catalog-fill loop (now `orchestrator.py::_catalog_fill_loop`, previously a
  director routing rule) keeps calling trend_scraper → ecommerce_manager across
  multiple batches until the cap or an `error` — one batch only yields ~10-15.
- **CJ search priority**: `category_id` (real CJ leaf, from `resolve_category()`) now
  beats free-text keyword search by default in `search_trending_products` — verified
  empirically for baby apparel: category_id alone returned 9/10 genuine items vs
  mostly junk via keyword search. This was flipped FROM keyword-priority, which was
  right for a *different* niche (ambient lighting, where the LLM category resolver
  kept collapsing distinct keywords into the same wrong leaf). If a new niche's
  results look generic/repetitive, check whether `resolve_category()` is actually
  picking distinct, accurate leaves for it before assuming this priority still holds.
- Sourcing keywords must be CONCRETE garment types ("baby onesie"), never generic
  category labels ("baby clothing"). See `_CATEGORY_SYSTEM`/`_RELAX_SYSTEM`.
- Niche-fit check (`_fits_niche`/`_FIT_SYSTEM`) judges PRODUCT TYPE only — ignores
  marketing adjectives in `product_category` like "premium"/"organic". Keep
  `product_category` itself free of those adjectives too.
- **CJ result pages must advance** (`search_trending_products(page_num=...)`,
  computed in `trend_scraper.py` from the store's REAL live product count via
  `list_shopify_products()`, not from `already_created` which resets every run) —
  without this, repeated rounds against the same category always re-request page 1,
  which dedup then filters down to zero "new" candidates.
- **`CJQuotaExceeded`** (`sourcing.py`) must propagate as a hard `error`, never get
  silently swallowed into "0 candidates" — that swallow is exactly what caused the
  15+-repeat infinite loop mentioned above. The daily quota is 1000 requests/account,
  resets at midnight (CJ's clock, timezone not confirmed). A run stuck at
  `products_found: 0` with no error is the symptom — check for a raw 429 with
  `"daily request limit"` before assuming a code bug.
- Real supplier specs (`description` field from CJ's `product/query`, parsed by
  `ecommerce.py::_extract_real_specs`) ground the AI-written product copy — fabric,
  fit, set contents are real, not invented.

**Product variants** (`sourcing.py` `_build_supplier_variants`, `shopify.py`
`create_shopify_product`):
- Size labels are parsed from the supplier's OWN stated age↔height correspondence in
  the real `description` text (`_parse_height_age_map`, regex for "6m/59cm" style
  lines) — NOT a hardcoded cm→age band table. An earlier hardcoded table was
  confirmed WRONG against real data (claimed 59cm="0-3M", supplier's own text for
  that exact product said 59cm="6m"). Falls back to bare "59cm" (no invented age
  label) when the description doesn't state a correspondence.
- Color is NOT extracted — CJ's real structured field for it was never confirmed.
  Don't add color matching via regex/text guessing.
- `create_shopify_product`'s `variants` param creates a real Shopify "Size" option +
  per-variant pricing (`productOptionsCreate` with `variantStrategy: CREATE`, then
  `productVariantsBulkUpdate`).
- Every variant's `inventoryItem.id` must be fetched and stocked via
  `update_inventory` — without this, inventory tracking defaults to 0 and Add to
  Cart doesn't work, regardless of variants.
- Video support exists (`create_shopify_product(video_url=...)`,
  `productCreateMedia`) but is rare in this CJ catalog slice — checked 10+ products,
  all had `productVideo: null`. Wired in as a non-fatal follow-up call, not bundled
  into the main product-create mutation.

**Collections must be explicitly published** (`shopify.py::create_collection`):
new collections do NOT default to visible on the storefront — confirmed live
(`published_at: None`, 404 on the storefront despite having products). Publish via
REST `PUT custom_collections/{id}.json {"published": true}` right after creation.

**Shopify plan tiers are a hard, real constraint** — verified directly against the
API, not assumed:
- **Starter plan** blocks: collection creation (`collectionCreate` returns an
  explicit "store must not be on the Starter or Retail plans" error), theme
  installation ("Theme creation is not allowed for your shop's plan"), and theme
  asset editing (402 "This shop's plan does not have access to this feature").
  Products and navigation menus DO work on Starter. None of this is fixable in code
  — the store needs Basic plan or higher.
- Store currency and the legal "Store name" (Settings → General) are both
  admin-only, not API-writable (`PUT shop.json` → 406) — ask the operator to change
  these manually if they're wrong.

**Theme management** (`theme_installer.py`, `storefront/runner.py`):
- Shopify's REST "install theme from remote ZIP URL" endpoint is broken for our
  custom app (confirmed via raw request with a verified-correct payload — Shopify
  rejects the `src` field outright with `"is empty"` regardless). Don't re-attempt
  that path.
- The working path: clone Dawn's real open-source repo locally into
  `stores/shopify/{slug}/`, then push via the Storefront Runner's `/deploy`
  endpoint (`shopify theme push`), which Shopify's CLI auth flow still supports.
- Only Dawn is genuinely open-source on GitHub — the other 7 entries in
  `theme_installer.py`'s `FREE_THEMES` catalogue point to repos that don't exist.
- `shopify theme dev` (local hot-reload preview) needs a **Theme Access app**
  password (`shptka_...`, separate from the Admin token) — required for the
  dev/hot-reload channel specifically, regardless of whether the storefront itself
  is password-protected.
- Images with extreme aspect ratios can 504 through Shopify's resize-transform CDN
  proxy (`store.myshopify.com/cdn/shop/files/...?width=N`) while the SAME file loads
  fine via the generic `cdn.shopify.com/s/files/...` URL — pad/reshape to a more
  standard ratio (e.g. via `sips -p`) rather than fighting the proxy.

**Shopify Admin API access**: getting a working `shpat_` token differs by app type.
A Partners/CLI-managed app (`shopify app dev`) uses OAuth (Client ID/Secret), not a
static reveal-once token — if the store's Shopify version has deprecated the legacy
"Create custom app" flow (Settings → Apps → App development shows only "Build apps
in Dev Dashboard"), you can still get a usable offline token by doing the OAuth
authorization-code exchange directly: build the `/admin/oauth/authorize` URL with the
app's real Client ID + the scopes from its `shopify.app.toml`, catch the `code` via a
local HTTP listener on the configured `redirect_uri`, then POST it + the Client
Secret to `/admin/oauth/access_token`. No CLI, no installed app project needed beyond
the `shopify.app.toml` that already has the Client ID.

**Third-party Shopify apps are never agent-installable**: there's no Admin API for
silently installing another vendor's app (Judge.me, Klaviyo, ReConvert, etc.) — each
requires a human to click "Install" + grant OAuth/billing consent, by deliberate
Shopify design. `store_setup.py::_RECOMMENDED_APPS` surfaces these as a checklist in
the run summary instead of pretending to automate them. What IS implemented natively:
a storewide welcome discount code (`shopify.py::create_welcome_discount`, via the
real Discounts API — needs both `customerSelection` AND `customerGets` set, the
mutation 400s with an unhelpful error otherwise).

Be skeptical of "Shopify now has MCP for X" claims before building anything on them
— checked directly against the real Admin GraphQL schema (zero MCP-related
queries/mutations) and the claimed `https://{shop}.myshopify.com/api/mcp` endpoint
(404). Verify against the live API before trusting a research summary, however
confident it reads.

## Step 2 — Report

Structure your response exactly like this:

### Completed (last session)
Pull from CHANGELOG — last 3–5 entries, one line each.

### Open issues
Each with severity:
- 🔴 blocking — pipeline can't run
- 🟡 important — pipeline runs but output is wrong/incomplete  
- 🟢 nice-to-have

### Recommended next step
One task. Name the exact files and functions to change.

### Backlog
Everything else, ordered by impact.

## Step 3 — After completing any task

Append to the **top** of `CHANGELOG.md` (below the `# Changelog` header):

```
## [YYYY-MM-DD HH:MM] — Title

What was done, which files changed, what problem it solved, any caveats.
```
