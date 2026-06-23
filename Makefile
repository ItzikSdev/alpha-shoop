SHELL := /bin/bash
ROOT  := $(shell pwd)
VENV  := $(ROOT)/.venv
PY    := $(VENV)/bin/python
PIP   := $(VENV)/bin/pip
UV    := $(VENV)/bin/uvicorn
PT    := $(VENV)/bin/pytest

.PHONY: dev run stop restart logs ps migrate \
        setup install proxy proxy-stop proxy-logs \
        test test-cov test-file test-watch \
        mcp mcp-test mcp-config storefront \
        docs docs-build open-api open-docs \
        push secrets clean help

# ── Docker Compose ─────────────────────────────────────────────────────────────

## Bring up ALL services with hot-reload  (API + LiteLLM + Postgres + Redis + Docs)
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

## Bring up ALL services detached (production-like)
run:
	docker compose up -d --build
	@echo ""
	@echo "  API    → http://localhost:8000"
	@echo "  Docs   → http://localhost:3000"
	@echo "  LiteLLM→ http://localhost:4000/ui"
	@echo ""

## Stop and remove all containers
stop:
	docker compose down
	@echo "✓ All containers stopped"

## Restart one service: make restart svc=api
restart:
	docker compose restart $(svc)

## Tail logs (all services or one: make logs svc=api)
logs:
	docker compose logs -f $(svc)

## Show container status
ps:
	docker compose ps

## Run DB migrations inside the running api container
migrate:
	docker compose exec api python -c \
	  "import asyncio; from src.db.engine import create_tables; asyncio.run(create_tables())"
	@echo "✓ product_mappings table ready"

# ── Local Python setup (no Docker) ────────────────────────────────────────────

setup: venv
	@echo "→ Installing Python + Node deps..."
	$(PIP) install --prefer-binary -r requirements.txt -q
	cd docs-app && npm install --silent
	@echo "✓ Ready. Copy .env.example → .env and fill in keys."

venv:
	@[ -d $(VENV) ] || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q

# ── LiteLLM Proxy (standalone, for local dev without full Docker stack) ────────

proxy:
	@echo "→ Starting LiteLLM proxy (Docker) on http://localhost:4000"
	@docker rm -f litellm-proxy 2>/dev/null || true
	@export $$(grep -v '^#' .env | grep -v '^$$' | xargs) 2>/dev/null; \
	docker run -d \
	  --name litellm-proxy \
	  -p 4000:4000 \
	  -e ANTHROPIC_API_KEY=$$ANTHROPIC_API_KEY \
	  -e LITELLM_MASTER_KEY=$${LITELLM_MASTER_KEY:-alpha-shoop-local} \
	  -v $(ROOT)/litellm_config.yaml:/app/config.yaml:ro \
	  ghcr.io/berriai/litellm:main-stable \
	  --config /app/config.yaml
	@echo "✓ Proxy running — logs: make proxy-logs"

proxy-stop:
	docker stop litellm-proxy && docker rm litellm-proxy

proxy-logs:
	docker logs -f litellm-proxy

# ── Tests ──────────────────────────────────────────────────────────────────────

test:
	PYTHONPATH=$(ROOT) $(PT) tests/ -v

test-cov:
	PYTHONPATH=$(ROOT) $(PT) tests/ -v \
	  --cov=src --cov-report=term-missing --cov-report=html:htmlcov
	@echo "✓ htmlcov/index.html"

test-file:
	PYTHONPATH=$(ROOT) $(PT) $(FILE) -v

test-watch:
	PYTHONPATH=$(ROOT) $(VENV)/bin/ptw tests/ -- -v

# ── MCP Server ─────────────────────────────────────────────────────────────────

mcp:
	PYTHONPATH=$(ROOT) $(PY) $(ROOT)/mcp_server.py

mcp-test:
	PYTHONPATH=$(ROOT) $(PY) $(ROOT)/test_mcp_tools.py

## Run the host-side Hydrogen storefront runner (NOT Docker) on 127.0.0.1:8788
storefront:
	PYTHONPATH=$(ROOT) $(UV) src.storefront.runner:app --host 127.0.0.1 --port 8788 --reload

mcp-config:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════╗"
	@echo "║  claude_desktop_config.json  ─  paste this block:   ║"
	@echo "╚══════════════════════════════════════════════════════╝"
	@$(PY) -c "\
import json, os; \
root = '$(ROOT)'; \
cfg = {'mcpServers': {'alpha-shoop': {'command': f'{root}/.venv/bin/python', 'args': [f'{root}/mcp_server.py'], 'env': {'SHOPIFY_STORE_DOMAIN': os.getenv('SHOPIFY_STORE_DOMAIN',''), 'SHOPIFY_ACCESS_TOKEN': os.getenv('SHOPIFY_ACCESS_TOKEN',''), 'CJ_EMAIL': os.getenv('CJ_EMAIL',''), 'CJ_API_KEY': os.getenv('CJ_API_KEY',''), 'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY','')}}}}; \
print(json.dumps(cfg, indent=2))"
	@echo ""
	@echo "→ Restart Claude Desktop after saving."
	@echo ""

# ── React Docs ─────────────────────────────────────────────────────────────────

docs:
	cd docs-app && npm run dev

docs-build:
	cd docs-app && npm run build
	@echo "✓ docs-app/dist"

open-api:
	open http://localhost:8000/docs

open-docs:
	open http://localhost:5173

# ── GitHub ─────────────────────────────────────────────────────────────────────

## Push current branch to GitHub
push:
	git push origin $(shell git rev-parse --abbrev-ref HEAD)

# ── GCP ────────────────────────────────────────────────────────────────────────

## Fetch secrets from GCP Secret Manager → .env
secrets:
	bash scripts/fetch-gcp-secrets.sh

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	rm -rf $(VENV) docs-app/node_modules docs-app/dist htmlcov .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	docker compose down -v 2>/dev/null || true

# ── Help ───────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Alpha Shoop — commands"
	@echo ""
	@echo "  Docker Compose:"
	@echo "    make dev           All services with hot-reload (recommended)"
	@echo "    make run           All services detached (prod-like)"
	@echo "    make stop          Stop all containers"
	@echo "    make logs svc=api  Tail logs"
	@echo "    make ps            Show container status"
	@echo "    make migrate       Run DB migrations"
	@echo ""
	@echo "  Local (no Docker):"
	@echo "    make setup         Install Python + Node deps"
	@echo "    make proxy         Start LiteLLM proxy (Docker)"
	@echo "    make mcp-test      Smoke-test MCP tools"
	@echo "    make mcp-config    Print Claude Desktop config"
	@echo "    make storefront    Run host Hydrogen storefront runner (127.0.0.1:8788)"
	@echo "    make test          Run pytest"
	@echo ""
	@echo "  GitHub / GCP:"
	@echo "    make push          Push to GitHub"
	@echo "    make secrets       Fetch secrets from GCP Secret Manager"
	@echo ""

.DEFAULT_GOAL := help
