"""Live visitors for the 3D office (private API; the public side is src/visitors/beacon_app.py).

  GET /visitors/live   anonymous visitors active in the last 5 min (+ purchases for 2 min):
                       {visitors:[{id, stage, source, country, first_seen, last_seen, total?}], counts}
"""
from __future__ import annotations

import json

import redis.asyncio as aioredis
from fastapi import APIRouter

from src.config import get_settings
from src.visitors import events as E

router = APIRouter()
_redis: aioredis.Redis | None = None


def _r() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


@router.get("/visitors/live", summary="Anonymous live store visitors (source, country, stage)")
async def visitors_live() -> dict:
    now = E.now()
    out: list[dict] = []
    try:
        r = _r()
        keys = [k async for k in r.scan_iter(match="vis:*", count=200)][:300]
        raws = await r.mget(keys) if keys else []
        for k, raw in zip(keys, raws):
            if not raw:
                continue
            v = E.public_view(k.split(":", 1)[1], json.loads(raw), now)
            if v:
                out.append(v)
    except Exception as exc:  # noqa: BLE001
        return {"visitors": [], "counts": {}, "error": str(exc)[:200]}
    out.sort(key=lambda v: v["first_seen"] or 0)
    counts: dict[str, int] = {}
    for v in out:
        counts[v["stage"]] = counts.get(v["stage"], 0) + 1
    return {"visitors": out, "counts": counts, "total": len(out)}


@router.get("/visitors/results", summary="Visitors / funnel / revenue by traffic source over N days")
async def visitors_results(days: int = 7) -> dict:
    try:
        return await E.results(_r(), days)
    except Exception as exc:  # noqa: BLE001
        return {"days": days, "by_source": {}, "by_day": {}, "totals": {}, "error": str(exc)[:200]}
