# HANDOFF — ALPHA FOR BABY Hydrogen store + Sol agent (2026-07-05)

## What exists
- **Hydrogen storefront** (React/React-Router, Oxygen) at `stores/shopify/hydrogen-alphaforbaby/`.
  JSON-driven template: `app/theme.config.json` controls the whole look + content. Products +
  policies come LIVE from Shopify. Live domain: **https://alphaforbaby.alpha-tech.live** (Oxygen).
- **Multi-store template + LOCAL CI/CD** (no GitHub Actions): `store-profiles/<slug>/`
  (`theme.config.json` + git-ignored `store.env` with the Oxygen deploy token).
  Deploy: `./scripts/deploy.sh alphaforbaby` (production = `--env-branch main`, `CI=1`).
  New store: `./scripts/new-store.sh <slug>`.
- **Sol** — the single autonomous agent (`src/org/agent_loop.py`, roster in `src/org/seed.py`).
  Model: **Opus** (`alpha/director`, "builder" tier); over-budget → free local. Budget cap $100/mo.
  Tools: read/write/**edit**_store_file (code, sandboxed to `stores/`), **shell** (allow-listed
  build/deploy/git; secrets blocked), **shopify_admin** (Admin GraphQL — token injected server-side;
  fix collections/dedupe/prices/SEO), cj_search_products, shopify_list_products. Vision: reads Slack
  screenshots. Persistent memory: `docs/STORE_MEMORY.md` (injected into his prompt).
  Docs/skills he uses: `docs/{AGENT_WORKFLOW,QA,SEO,CI_CD,STORE_MEMORY}.md`,
  `stores/shopify/skills/{SKILLS_MAP,ui-ux-pro,store-audit}.md` + `.claude/skills/shopify-*` (toolkit).

## How to run Sol
1. Docker Desktop up → `make run` brings up litellm proxy (:4000) + redis + ollama (Docker).
2. Run the API ON THE HOST (Docker's api container lacks Node/CLI + the live repo):
   ```bash
   set -a; source .env; set +a
   export LITELLM_PROXY_URL=http://localhost:4000 REDIS_URL=redis://localhost:6379/0 \
     OLLAMA_URL=http://localhost:11434 DATABASE_URL="sqlite+aiosqlite:///$PWD/data/app.db" \
     TRACES_DB_PATH="$PWD/data/traces.db" PATH="/opt/homebrew/bin:$PATH"
   .venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000
   ```
   (Docker `api` must be stopped: `docker compose stop api`.)
3. Talk to Sol in the Slack channel, OR trigger: `POST /api/v1/org/sol {"task":"…","max_steps":30}`.

## Open issues / next tasks (do in a FRESH session for quality)
1. **Product categorization by VISION** — Sol classifies by TEXT and misses image-obvious cases
   (a pink/bow romper with a neutral title stays in Baby Boys). Build: fetch each product's image →
   Opus vision → boys/girls/unisex → `shopify_admin` collectionAdd/Remove. (Collections are MANUAL.)
2. **Sol reliability / self-testing** — he sometimes wandered / hit step limits (mitigated: Opus,
   edit_store_file, 40 steps, cleared stale lessons). Add real self-verification (build + a headless
   check) before he reports "done".
3. **Auto-screenshot to Slack on change** — needs a headless browser (Playwright) + Slack file upload.
4. **Product QA rules** now required: min 2 images/product, no similar/dup images, no duplicate product.

## Security / owner TODO
- 🔴 **Rotate `SHOPIFY_ACCESS_TOKEN`** — Sol leaked it to Slack once (now blocked in the shell tool).
- **Enable a payment provider** (Settings → Payments) — checkout currently bounces to home without one.
- **Terms of Service** — created in Shopify; fill the business registration fields (no fake address).

## Recent fixes (live)
- Cart/hamburger were dead → caused by `Analytics.Provider` consent crash → **disabled the privacy
  banner** (`root.jsx withPrivacyBanner:false`) + checkoutDomain fallback. Deployed.
- Nav = hamburger + desktop nav; local CSP-safe hero/tile images; brand page titles (not "Hydrogen |").
- Repo: github.com/ItzikSdev/alpha-shoop, branch `hydrogen-storefront`.
