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
from src.api.routes import org as org_router
from src.api.routes import finance as finance_router
from src.api.routes import videos as videos_router
from src.api.routes import images as images_router
from src.api.routes.agents import _daemon, _spawn_run
from src.db.engine import create_tables
from src.org.daemon import org_tick
from src.org.models import init_org_tables
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


async def _org_daemon_loop() -> None:
    """Heartbeat for the living company: org_tick() self-gates on enabled +
    interval + anti-pileup + kill-switch, so calling it every 30s is cheap."""
    while True:
        await asyncio.sleep(30)
        try:
            await org_tick()
        except Exception:
            logger.exception("Org daemon tick failed")


async def _agent_heartbeat_loop() -> None:
    """Proactive heartbeat: one agent takes a turn on its own initiative each
    tick (works + speaks as itself). Self-gates on company.daemon.enabled +
    kill-switch, so this is what makes the team act without being prompted."""
    from src.org.heartbeat import agent_heartbeat

    interval = int(os.environ.get("ORG_HEARTBEAT_SECONDS", "60"))
    while True:
        await asyncio.sleep(interval)
        try:
            await agent_heartbeat()
        except Exception:
            logger.exception("Agent heartbeat failed")


async def _manager_checkin_loop() -> None:
    """Once a day the CEO posts a roster status + next-steps report to
    Telegram on her own (also triggerable any time via the /manager command).
    Checked every 30 min; maybe_run_daily_checkin self-gates on the real
    interval (persisted, so a restart doesn't reset the clock)."""
    from src.org.manager import maybe_run_daily_checkin

    while True:
        await asyncio.sleep(1800)
        try:
            await maybe_run_daily_checkin()
        except Exception:
            logger.exception("Manager daily check-in failed")


async def _ceo_report_loop() -> None:
    """Ava's daily CEO report (Revenue, TikTok ad spend/ROAS, bottlenecks,
    executed agent commands) — see src/telegram/ceo_report.py. Also
    triggerable any time via the /report Telegram command. Checked every 30
    min; maybe_run_daily_report self-gates on local calendar day + hour
    (default 21:00 Asia/Jerusalem, persisted so a restart doesn't double-fire)."""
    from src.telegram.ceo_report import maybe_run_daily_report

    while True:
        await asyncio.sleep(1800)
        try:
            await maybe_run_daily_report()
        except Exception:
            logger.exception("Daily CEO report failed")


async def _support_inbox_loop() -> None:
    """Nora polls the shared central support mailbox and answers customer
    emails per the 3 routing rules (src/mcp_tools/support_inbox.py). No-op
    until SUPPORT_GMAIL_CLIENT_ID/SECRET/REFRESH_TOKEN + RESEND_API_KEY are
    set — the Google account/forwarding isn't provisioned yet."""
    from src.mcp_tools.support_inbox import process_central_inbox, refresh_store_products_rag, support_inbox_enabled
    from src.org.models import Company, get_company, update_company
    from src.org.telegram import post_as
    from src.stores import list_stores
    from datetime import datetime, timezone

    interval = int(os.environ.get("SUPPORT_INBOX_POLL_SECONDS", "120"))
    rag_refresh_hours = float(os.environ.get("STORE_PRODUCTS_RAG_REFRESH_HOURS", "24"))
    while True:
        await asyncio.sleep(interval)
        if not support_inbox_enabled():
            continue
        try:
            results = await process_central_inbox()
            for r in results:
                if r.get("sent"):
                    await post_as("Nora", "Customer Support",
                                   f"✅ Replied to {r['customer']} ({r['store']})")
                elif r.get("error"):
                    await post_as("Nora", "Customer Support",
                                   f"⚠️ {r.get('customer', r['id'])}: {r['error']}")
        except Exception:
            logger.exception("Support inbox poll failed")

        # Keep her product-catalog RAG fresh — self-gated per store (same
        # persisted-timestamp pattern as the manager daily check-in) so this
        # doesn't hammer Shopify's API on every 2-minute poll tick.
        try:
            company = get_company()
            if company is not None:
                last_by_store = dict(company.daemon.get("store_products_rag_last_at", {}))
                now = datetime.now(timezone.utc)
                refreshed: dict[str, str] = {}
                for store in list_stores():
                    last = last_by_store.get(store.store_id)
                    if last:
                        elapsed_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
                        if elapsed_h < rag_refresh_hours:
                            continue
                    n = await refresh_store_products_rag(store)
                    refreshed[store.store_id] = now.isoformat()
                    logger.info("Refreshed store_products RAG for %s: %d products", store.store_id, n)
                if refreshed:
                    def _mark_refreshed(c: Company, refreshed: dict = refreshed) -> None:
                        last_by_store = c.daemon.setdefault("store_products_rag_last_at", {})
                        last_by_store.update(refreshed)
                        c.daemon["store_products_rag_last_at"] = last_by_store
                    update_company(_mark_refreshed)
        except Exception:
            logger.exception("store_products RAG refresh failed")


async def _reel_image_scan_one_store(store) -> None:
    """One full pass over every active product in `store`: vision-checks its photos
    and kicks off either a baby-outfit-swap image (adult person detected) or a
    PRODUCT_3D_SHOWCASE video (no person) — reusing the existing generate routes
    in-process, same pattern src/org/conversation.py's `_agent_act_video` already
    uses. Skips products already done via RAG's has_baby_image flag or an existing
    pending/published ProductImage/ProductVideo row."""
    import tempfile
    from pathlib import Path

    import httpx
    from sqlalchemy import select

    from src.api.routes.images import _use_store as _use_store_i, post_generate_image
    from src.api.routes.videos import _use_store as _use_store_v, post_generate_video
    from src.db.engine import get_session
    from src.db.models import ProductImage, ProductVideo
    from src.mcp_tools.shopify import get_products_with_all_images
    from src.rag.index import get as rag_get
    from src.video.vision import analyze_product_image

    _use_store_i(store.store_id)
    products = await get_products_with_all_images()

    async with get_session() as session:
        done_images = set((await session.execute(
            select(ProductImage.shopify_product_id).where(
                ProductImage.store_id == store.store_id,
                ProductImage.status.in_(["pending_review", "approved", "published"]),
            )
        )).scalars().all())
        done_videos = set((await session.execute(
            select(ProductVideo.shopify_product_id).where(
                ProductVideo.store_id == store.store_id,
                ProductVideo.status.in_(["pending_review", "approved", "published"]),
            )
        )).scalars().all())

    for product in products:
        pid = product["id"]
        if pid in done_images or pid in done_videos:
            continue
        rag_row = await rag_get("store_products", pid)
        if rag_row and rag_row.get("has_baby_image") == "true":
            continue

        adult_image_url: str | None = None
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                for url in product["image_urls"]:
                    r = await client.get(url)
                    r.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=Path(url).suffix or ".jpg", delete=False) as f:
                        f.write(r.content)
                        tmp_path = Path(f.name)
                    try:
                        analysis = await analyze_product_image(tmp_path)
                    finally:
                        tmp_path.unlink(missing_ok=True)
                    if analysis.has_adult_person:
                        adult_image_url = url
                        break
        except Exception:
            logger.exception("Reel image scan: vision check failed for product %s", pid)
            continue

        try:
            if adult_image_url:
                await post_generate_image({
                    "store_id": store.store_id, "product_id": pid, "source_image_url": adult_image_url,
                })
            else:
                _use_store_v(store.store_id)
                await post_generate_video({
                    "store_id": store.store_id, "product_id": pid, "style": "PRODUCT_3D_SHOWCASE",
                })
        except Exception:
            logger.exception("Reel image scan: generate kickoff failed for product %s", pid)


async def _reel_image_scan_loop() -> None:
    """Reel's per-store product scan: every ~settings.reel_image_scan_hours, one full
    pass over every active product (see _reel_image_scan_one_store), then a break
    until the next pass. Same persisted-timestamp gating pattern as the support
    inbox's RAG refresh (src/main.py's _support_inbox_loop)."""
    from datetime import datetime, timezone

    from src.config import get_settings
    from src.org.models import Company, get_company, update_company
    from src.stores import list_stores

    settings = get_settings()
    while True:
        await asyncio.sleep(1800)  # check every 30 min whether any store's window has elapsed
        if not settings.reel_image_scan_enabled:
            continue  # paused — see reel_image_scan_enabled in src/config.py
        try:
            company = get_company()
            if company is None:
                continue
            last_by_store = dict(company.daemon.get("reel_image_scan_last_at", {}))
            now = datetime.now(timezone.utc)
            scanned: dict[str, str] = {}
            for store in list_stores():
                last = last_by_store.get(store.store_id)
                if last:
                    elapsed_h = (now - datetime.fromisoformat(last)).total_seconds() / 3600
                    if elapsed_h < settings.reel_image_scan_hours:
                        continue
                await _reel_image_scan_one_store(store)
                scanned[store.store_id] = now.isoformat()
            if scanned:
                def _mark_scanned(c: Company, scanned: dict = scanned) -> None:
                    last_by_store = c.daemon.setdefault("reel_image_scan_last_at", {})
                    last_by_store.update(scanned)
                    c.daemon["reel_image_scan_last_at"] = last_by_store
                update_company(_mark_scanned)
        except Exception:
            logger.exception("Reel image scan loop failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(init_stores_table)
    await asyncio.to_thread(init_org_tables)
    from src.org.proposals import init_proposals
    await asyncio.to_thread(init_proposals)
    await create_tables()  # product_mappings etc — was previously only created by a manual Makefile step
    n = await asyncio.to_thread(load_all, trace_store)
    logger.info("Loaded %d persisted runs from SQLite", n)

    # Draw the org into the knowledge graph (FalkorDB, browsable at :3002) so it
    # shows the WHOLE company from boot — every agent and the tools each can use.
    # Previously the only writer was Sol's tool loop, so the graph contained one
    # agent and looked like the company was one person. Best-effort by design.
    try:
        from src.graph.knowledge_graph import seed_org_graph
        from src.org.seed import seed_founding_team
        from src.org.models import list_agents
        from src.org.tool_catalog import all_tool_names
        await asyncio.to_thread(seed_founding_team)
        members = [(a.name, a.role) for a in list_agents(active_only=True)]
        await seed_org_graph(members, all_tool_names())
        logger.info("Seeded knowledge graph with %d agents", len(members))
    except Exception:
        logger.exception("Knowledge-graph seed failed (non-fatal)")
    checkpoint_task = asyncio.create_task(_checkpoint_loop())
    daemon_task = asyncio.create_task(_daemon_loop())
    org_daemon_task = asyncio.create_task(_org_daemon_loop())
    heartbeat_task = asyncio.create_task(_agent_heartbeat_loop())
    manager_task = asyncio.create_task(_manager_checkin_loop())
    ceo_report_task = asyncio.create_task(_ceo_report_loop())
    support_inbox_task = asyncio.create_task(_support_inbox_loop())
    reel_image_scan_task = asyncio.create_task(_reel_image_scan_loop())
    from src.org.telegram import start_telegram_bot, stop_telegram_bot
    telegram_app = await start_telegram_bot()  # None (no-op) unless TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_USER_ID are set
    yield
    # Shutdown: final checkpoint, cancel loops
    checkpoint_task.cancel()
    daemon_task.cancel()
    org_daemon_task.cancel()
    heartbeat_task.cancel()
    manager_task.cancel()
    ceo_report_task.cancel()
    support_inbox_task.cancel()
    reel_image_scan_task.cancel()
    await stop_telegram_bot(telegram_app)
    await asyncio.to_thread(save_all, trace_store)


app = FastAPI(
    title="Alpha Shoop — Autonomous Arbitrage System",
    description=(
        "A self-managing org of AI agents (Ava·Sol·Reel·Nora·Milo·Kai) that runs "
        "real Shopify stores end to end, chatting over Telegram and driven by a "
        "60s heartbeat loop — see /org for the live roster.\n\n"
        "- **Ava** (CEO): routing, daily reports, meeting decisions\n"
        "- **Sol**: CJ Dropshipping sourcing + copywriting + Shopify product push\n"
        "- **Reel**: ad-video pipeline (local Wan2.2/ComfyUI), Telegram approval gate\n"
        "- **Nora**: central support-inbox, replies across every store\n"
        "- **Milo**: fulfillment — places supplier orders, attaches tracking\n"
        "- **Kai**: read-only TikTok Ads reporting (real MCP server)\n\n"
        "Most agents run on a local qwen3 model via LiteLLM, auto-falling back "
        "there for everyone once the monthly Anthropic budget cap is hit. A "
        "legacy deterministic pipeline (src/agents/orchestrator.py) still exists "
        "underneath for full store builds, entered via org `build_store`/"
        "`boost_store` decisions.\n\n"
        "Hard guardrails: MAX_AD_SPEND=$500/day · MAX_ORDER_VALUE=$200"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000", "http://localhost:8081"],
    # Also allow the dashboard served from a LAN IP (so a phone on the same Wi-Fi
    # can reach the API at http://<mac-lan-ip>:8000). Covers the common private
    # ranges on the dev ports; tighten/remove for production.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):(5173|3000|8000|8081)",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(agents_router.router, prefix="/api/v1", tags=["Agents"])
app.include_router(stores_router.router, prefix="/api/v1", tags=["Stores"])
app.include_router(org_router.router, prefix="/api/v1", tags=["Organization"])
app.include_router(finance_router.router, prefix="/api/v1", tags=["Finance"])
app.include_router(videos_router.router, prefix="/api/v1", tags=["Videos"])
app.include_router(images_router.router, prefix="/api/v1", tags=["Images"])
app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# In production, serve built React docs from /ui
_docs_dist = os.path.join(os.path.dirname(__file__), "..", "platform-app", "dist")
if os.path.isdir(_docs_dist):
    app.mount("/ui", StaticFiles(directory=_docs_dist, html=True), name="ui")

# Rendered ad videos (src/video/pipeline.py) — served so Slack/the dashboard can
# link/play them without going through the API.
_videos_dir = os.path.join(os.path.dirname(__file__), "..", "data", "videos")
os.makedirs(_videos_dir, exist_ok=True)
app.mount("/media/videos", StaticFiles(directory=_videos_dir), name="videos")
