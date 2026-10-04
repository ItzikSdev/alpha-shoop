"""PUBLIC beacon — the only thing exposed to the internet for live visitors.

Receives events from our Shopify Custom Pixel and writes them to Redis. It has no other routes, no
database, no secrets except an anti-noise token, and it never reads anything back. Run it as its own
process/container (see docker-compose `beacon`) behind Cloudflare Tunnel; the private API reads Redis.

  POST /v   body = JSON (sent as text/plain to avoid a CORS preflight):
            {t: token, cid: shopify clientId, ev: event name, ref: referrer, url: page url,
             utm: utm_source, total: order total (only for checkout_completed)}
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response

from src.visitors import events as E

app = FastAPI(title="alpha visitor beacon", docs_url=None, redoc_url=None, openapi_url=None)
_redis: aioredis.Redis | None = None
_hits: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
MAX_BODY = 4096
RATE = 40  # events per minute per client id


def _r() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    return _redis


def _cors(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.options("/v")
async def preflight() -> Response:
    return _cors(Response(status_code=204))


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@app.post("/v")
async def beacon(request: Request) -> Response:
    raw = await request.body()
    if len(raw) > MAX_BODY:
        return _cors(Response(status_code=413))
    try:
        d = json.loads(raw or b"{}")
    except Exception:  # noqa: BLE001
        return _cors(Response(status_code=400))
    want = os.environ.get("VISITOR_BEACON_TOKEN", "")
    if not want or d.get("t") != want:
        return _cors(Response(status_code=403))
    cid = str(d.get("cid") or "")[:80]
    ev = str(d.get("ev") or "")[:60]
    if not cid or ev not in E.EVENT_STAGE:
        return _cors(Response(status_code=204))
    vid = E.visitor_id(cid)
    t = time.time()
    q = _hits[vid]
    while q and t - q[0] > 60:
        q.popleft()
    if len(q) >= RATE:
        return _cors(Response(status_code=429))
    q.append(t)
    r = _r()
    key = f"vis:{vid}"
    prev = await r.get(key)
    rec = E.merge(
        json.loads(prev) if prev else None, ev,
        source=E.source_of(str(d.get("ref") or "")[:300], str(d.get("url") or "")[:500], str(d.get("utm") or "")[:40]),
        country=E.clean_country(request.headers.get("cf-ipcountry", "")), now=t,
        total=d.get("total") if isinstance(d.get("total"), (int, float)) else None)
    await r.set(key, E.dumps(rec), ex=E.TTL_SECONDS)
    try:  # long-lived daily counters (results by traffic source) — never blocks the beacon
        await E.count_progress(r, json.loads(prev) if prev else None, rec, t)
    except Exception:  # noqa: BLE001
        pass
    return _cors(Response(status_code=204))
