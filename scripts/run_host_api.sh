#!/usr/bin/env bash
# Start the API directly on the host (not in Docker) with the correct environment.
#
# Why this script exists: most secrets/config (SLACK_BOT_TOKEN, TRACES_DB_PATH, etc.)
# are read via plain os.environ.get(...) in several modules (src/org/slack.py,
# src/org/tickets.py, src/stores/__init__.py, src/tracing/persist.py) — NOT through
# pydantic Settings' .env loading. A bare `uvicorn src.main:app` does NOT export
# .env into the process environment (no python-dotenv call anywhere), so anything
# read that way — Slack posting, the SQLite DB path — silently breaks. This bit
# twice in one session (2026-07-08): a restart with only 1-2 vars cherry-picked
# left Slack posting broken with no visible error.
#
# REDIS_URL and DATABASE_URL are overridden here because .env's values point at
# Docker Compose service hostnames ("redis", "postgres") that don't resolve from
# the host — only from inside the Docker network. Everything else in .env is
# loaded as-is.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
source .env
set +a

export REDIS_URL="${REDIS_URL_HOST_OVERRIDE:-redis://localhost:6379/0}"
unset DATABASE_URL   # host-run uses the SQLite path (TRACES_DB_PATH), not the Docker postgres host

exec .venv/bin/uvicorn src.main:app --host "${API_HOST:-127.0.0.1}" --port 8000
