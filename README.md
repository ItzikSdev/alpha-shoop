# Alpha Shoop

Autonomous Shopify store builder: one AI pipeline that brands a store, designs and
pushes a theme, sources on-niche products from CJ Dropshipping, lists them with
real-data-grounded copy, and (optionally) runs ads and fulfills orders — all
against the real Shopify Admin API.

## Architecture, in one line

A single deterministic orchestrator (`src/agents/orchestrator.py::run_pipeline`)
sequences 7 worker steps — Store Setup, Design, Frontend, Trend Scraper,
E-Commerce, Marketing, Fulfillment — via plain Python control flow. There's no LLM
router deciding what runs next; the steps themselves still call Claude (via a
LiteLLM proxy) for the genuinely creative parts: brand copy, design CSS,
niche-matching judgment calls. See [`docs/architecture.md`](docs/architecture.md)
for the full diagrams and [`.claude/commands/status.md`](.claude/commands/status.md)
for the live list of hard-won rules each agent follows.

## Quickstart

```bash
cp .env.example .env        # fill in real keys (see below)
make setup                  # python venv + platform-app npm install
make dev                     # API + LiteLLM + Postgres + Redis + platform-app, hot-reload
```

- API: `http://localhost:8000/docs`
- platform-app (store dashboard, live run logs): `http://localhost:5173`
- LiteLLM proxy UI: `http://localhost:4000/ui`

Run `make help` for the full command list (tests, MCP server, storefront runner, etc).

## What you need in `.env`

| Service | Why |
|---|---|
| `ANTHROPIC_API_KEY` | The actual model calls, via the LiteLLM proxy |
| `DATABASE_URL` / `REDIS_URL` | Postgres (product↔supplier mapping) + Redis (cache/queues) |
| `SHOPIFY_STORE_DOMAIN` / `SHOPIFY_ACCESS_TOKEN` | Default store credentials — real per-store credentials live in the `stores` table instead (multi-store support), set via `POST /api/v1/stores` |
| `CJ_EMAIL` / `CJ_API_KEY` | CJ Dropshipping sourcing — note: **hard 1000 requests/day quota**, resets at midnight on CJ's clock |
| `GOOGLE_ADS_*` | Marketing agent (optional — only used when a task includes `[MARKETING]`) |

## Running a store-building task

```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"task": "[REBUILD] Build a premium baby clothing store...", "store_id": "...", "max_budget_usd": 100}'
```

Task text supports tags that drive the pipeline directly (no LLM interpretation
needed): `[REBUILD]` / `[SETUP_ONLY]` (re-run brand+design from scratch),
`[PRODUCTS_ONLY]` (skip straight to sourcing), `[MARKETING]` (launch ad campaigns
after products are listed), `[MONITOR]` (health-check mode — sources more products
if there are none, launches marketing if there are sales but no recent revenue).

Poll `GET /api/v1/status/{thread_id}` or stream `GET /api/v1/runs/{thread_id}/stream`
for live logs — also visible in platform-app's Runs page.

## Tests

```bash
make test          # PYTHONPATH=. pytest tests/ -v
make test-cov       # with coverage report
```

## Project layout

```
src/
  agents/
    orchestrator.py     # the single pipeline entry point
    workers/            # the 7 step implementations (unchanged business logic)
  mcp_tools/             # Shopify Admin API, CJ Dropshipping, theme management, etc.
  api/routes/            # FastAPI routes (run trigger/status, stores CRUD, auth)
  stores/                # multi-store credential + brand-brief storage (SQLite)
platform-app/            # React dashboard — store management, live run logs, architecture viewer
docs/architecture.md     # generated from docs/architecture.drawio, with staleness notes
```
