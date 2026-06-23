"""FastAPI application — entry point for the Alpha Shoop agent system."""
from __future__ import annotations
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.api.routes import health, agents as agents_router, webhooks, auth
from src.api.routes import stores as stores_router
from src.api.routes.agents import _daemon, _spawn_run
from src.stores import init_stores_table, list_stores
from src.tracing import trace_store
from src.tracing.persist import init_db, load_all, save_all

logger = logging.getLogger(__name__)


async def _checkpoint_loop() -> None:
    """Save all in-memory traces to SQLite every 5 seconds."""
    while True:
        await asyncio.sleep(5)
        await asyncio.to_thread(save_all, trace_store)


async def _daemon_loop() -> None:
    """Auto-run loop: fires health-monitoring runs for each active store when interval elapses."""
    import uuid
    from datetime import datetime, timezone, timedelta

    while True:
        await asyncio.sleep(30)
        if not _daemon.get("enabled"):
            continue

        interval_min = int(_daemon.get("interval_minutes", 60))
        last = _daemon.get("last_started_at")

        now = datetime.now(timezone.utc)
        if last:
            since = (now - datetime.fromisoformat(last)).total_seconds() / 60
            if since < interval_min:
                next_run = datetime.fromisoformat(last) + timedelta(minutes=interval_min)
                _daemon["next_run_at"] = next_run.isoformat()
                continue

        # Don't pile up runs
        active = any(r.status in ("running", "pending") for r in trace_store.list_runs()[:3])
        if active:
            continue

        stores = list_stores()
        if stores:
            # Fire one monitoring run per active store
            for store in stores:
                if not store.active:
                    continue
                monitor_task = (
                    "[MONITOR] Check store health and sales. "
                    "If no sales in the last 7 days, launch a marketing campaign. "
                    "If revenue is healthy, ensure we have enough products listed."
                )
                thread_id = str(uuid.uuid4())
                logger.info("Daemon: monitoring store %s (%s)", store.name, thread_id)
                _spawn_run(thread_id, monitor_task, "daemon", max_budget_usd=50.0, store_id=store.store_id)
        else:
            # No stores configured — fall back to default build task
            task_text = _daemon.get("task", "Build a store for trending products.")
            thread_id = str(uuid.uuid4())
            logger.info("Daemon: starting auto-run %s (no stores configured)", thread_id)
            _spawn_run(thread_id, task_text, "daemon", max_budget_usd=100.0)

        _daemon["last_started_at"] = now.isoformat()
        _daemon["next_run_at"] = (now + timedelta(minutes=interval_min)).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(init_stores_table)
    n = await asyncio.to_thread(load_all, trace_store)
    logger.info("Loaded %d persisted runs from SQLite", n)
    checkpoint_task = asyncio.create_task(_checkpoint_loop())
    daemon_task = asyncio.create_task(_daemon_loop())
    yield
    # Shutdown: final checkpoint, cancel loops
    checkpoint_task.cancel()
    daemon_task.cancel()
    await asyncio.to_thread(save_all, trace_store)


app = FastAPI(
    title="Alpha Shoop — Autonomous Arbitrage System",
    description=(
        "Multi-agent e-commerce arbitrage powered by **LangGraph** + **Claude**.\n\n"
        "- **Director Agent**: Claude Opus — routes tasks to workers\n"
        "- **Trend Scraper**: Claude Haiku — CJ Dropshipping + AliExpress\n"
        "- **E-commerce Manager**: Claude Sonnet — Shopify Admin GraphQL\n"
        "- **Marketing Agent**: Claude Sonnet — Google Ads + Meta Ads\n"
        "- **Fulfillment Agent**: Claude Haiku — order placement + tracking\n\n"
        "Hard guardrails: MAX_AD_SPEND=$500/day · MAX_ORDER_VALUE=$200"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(agents_router.router, prefix="/api/v1", tags=["Agents"])
app.include_router(stores_router.router, prefix="/api/v1", tags=["Stores"])
app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# In production, serve built React docs from /ui
_docs_dist = os.path.join(os.path.dirname(__file__), "..", "docs-app", "dist")
if os.path.isdir(_docs_dist):
    app.mount("/ui", StaticFiles(directory=_docs_dist, html=True), name="ui")
