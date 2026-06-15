"""FastAPI application — entry point for the Alpha Shoop agent system."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.api.routes import health, agents, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: could initialise DB pool, Redis, LangSmith here
    yield
    # Shutdown: clean up connections


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

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(webhooks.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# In production, serve built React docs from /ui
_docs_dist = os.path.join(os.path.dirname(__file__), "..", "docs-app", "dist")
if os.path.isdir(_docs_dist):
    app.mount("/ui", StaticFiles(directory=_docs_dist, html=True), name="ui")
