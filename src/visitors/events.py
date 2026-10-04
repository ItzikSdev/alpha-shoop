"""Live store visitors — shared by the public beacon service and the (private) API.

Privacy by design: NO IP address, NO name/email, nothing from checkout beyond "a purchase happened"
and its total. A visitor is Shopify's anonymous clientId, hashed; country comes from Cloudflare's
CF-IPCountry header; the traffic source is derived from the referrer / utm_source.
Records live in Redis under `vis:<id>` and expire on their own (TTL), so nothing accumulates.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from urllib.parse import parse_qs, urlparse

TTL_SECONDS = 900          # a visitor disappears 15 min after the last event
ACTIVE_WINDOW = 300        # "in the store now" = event within 5 min
PURCHASE_KEEP = 120        # a purchase stays celebrated for 2 min
STAGES = ("browsing", "product", "cart", "checkout", "purchased")
_RANK = {s: i for i, s in enumerate(STAGES)}
EVENT_STAGE = {
    "page_viewed": "browsing", "collection_viewed": "browsing", "search_submitted": "browsing",
    "product_viewed": "product", "product_added_to_cart": "cart", "cart_viewed": "cart",
    "checkout_started": "checkout", "checkout_contact_info_submitted": "checkout",
    "payment_info_submitted": "checkout", "checkout_completed": "purchased",
}
_SOURCES = (
    ("facebook", ("facebook", "fb.", "fbclid", "l.facebook", "m.facebook")),
    ("instagram", ("instagram", "ig.", "l.instagram")),
    ("tiktok", ("tiktok", "ttclid")),
    ("google", ("google.",)),
    ("youtube", ("youtube", "youtu.be")),
    ("pinterest", ("pinterest",)),
    ("email", ("mail.", "email", "klaviyo", "mailchimp")),
    ("bing", ("bing.",)),
)


def visitor_id(client_id: str) -> str:
    return hashlib.sha256(("alpha-visitor|" + client_id).encode()).hexdigest()[:12]


def source_of(referrer: str = "", page_url: str = "", utm_source: str = "") -> str:
    """facebook | instagram | tiktok | google | ... | direct | other — never a raw URL."""
    qs = parse_qs(urlparse(page_url or "").query)
    hay = " ".join([utm_source or "", (qs.get("utm_source") or [""])[0], referrer or "",
                    "fbclid" if "fbclid" in qs else "", "ttclid" if "ttclid" in qs else ""]).lower()
    if not hay.strip():
        return "direct"
    for name, needles in _SOURCES:
        if any(n in hay for n in needles):
            return name
    own = urlparse(page_url or "").netloc.lower()
    if referrer and own and own in referrer.lower():
        return "direct"
    return "other"


def clean_country(v: str) -> str:
    v = (v or "").strip().upper()
    return v if re.fullmatch(r"[A-Z]{2}", v) and v not in ("XX", "T1") else ""


def merge(prev: dict | None, ev: str, *, source: str, country: str, now: float, total: float | None = None) -> dict:
    """Fold one event into the visitor's record. Stage only moves forward."""
    stage = EVENT_STAGE.get(ev, "browsing")
    rec = dict(prev or {})
    first = not rec
    rec.setdefault("first_seen", now)
    rec["last_seen"] = now
    if first:
        rec["source"] = source
    elif rec.get("source") in (None, "", "direct", "other") and source not in ("direct", "other"):
        rec["source"] = source          # a later event revealed the real origin
    if country and not rec.get("country"):
        rec["country"] = country
    if _RANK[stage] >= _RANK.get(rec.get("stage", "browsing"), 0):
        rec["stage"] = stage
    if stage == "purchased":
        rec["purchased_at"] = now
        if total is not None:
            rec["total"] = round(float(total), 2)
    rec["events"] = int(rec.get("events", 0)) + 1
    return rec


def public_view(vid: str, rec: dict, now: float) -> dict | None:
    """What the dashboard sees. Hides stale visitors; keeps purchasers a little longer."""
    age = now - float(rec.get("last_seen", 0))
    bought = rec.get("stage") == "purchased"
    if age > (PURCHASE_KEEP if bought else ACTIVE_WINDOW):
        return None
    return {"id": vid, "first_seen": rec.get("first_seen"), "last_seen": rec.get("last_seen"),
            "stage": rec.get("stage", "browsing"), "source": rec.get("source", "direct"),
            "country": rec.get("country", ""), "total": rec.get("total")}


def dumps(rec: dict) -> str:
    return json.dumps(rec, separators=(",", ":"))


def now() -> float:
    return time.time()


# ---- daily results by traffic source (kept ~13 months; anonymous aggregates only) -------------
STATS_TTL = 400 * 86400


def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


async def count_progress(r, prev: dict | None, rec: dict, ts: float) -> None:
    """Bump Redis hash `visday:<YYYY-MM-DD>` fields `<source>|<metric>`.
    metrics: visits (new visit = no record in the last 15 min), then one per funnel stage the
    visit newly reached (product, cart, checkout, purchased), plus `revenue` on a purchase."""
    src = rec.get("source") or "direct"
    key = f"visday:{_day(ts)}"
    pipe = r.pipeline()
    if not prev:
        pipe.hincrby(key, f"{src}|visits", 1)
    old_stage = (prev or {}).get("stage", "browsing")
    new_stage = rec.get("stage", "browsing")
    if _RANK[new_stage] > _RANK.get(old_stage, 0):
        for st in STAGES[_RANK.get(old_stage, 0) + 1: _RANK[new_stage] + 1]:
            pipe.hincrby(key, f"{src}|{st}", 1)
        if new_stage == "purchased" and rec.get("total"):
            pipe.hincrbyfloat(key, f"{src}|revenue", float(rec["total"]))
    pipe.expire(key, STATS_TTL)
    await pipe.execute()


async def results(r, days: int = 7) -> dict:
    """{days, by_source:{src:{visits,product,cart,checkout,purchased,revenue}}, by_day:{...}, totals}."""
    days = max(1, min(int(days), 90))
    now_ts = time.time()
    by_source: dict[str, dict] = {}
    by_day: dict[str, dict] = {}
    for i in range(days):
        day = _day(now_ts - i * 86400)
        h = await r.hgetall(f"visday:{day}")
        for field, val in (h or {}).items():
            src, _, metric = field.partition("|")
            v = float(val)
            for bucket in (by_source.setdefault(src, {}), by_day.setdefault(day, {})):
                bucket[metric] = round(bucket.get(metric, 0) + v, 2)
    totals: dict[str, float] = {}
    for m in by_source.values():
        for k, v in m.items():
            totals[k] = round(totals.get(k, 0) + v, 2)
    return {"days": days, "by_source": by_source, "by_day": by_day, "totals": totals,
            "note": "visits = distinct 15-min visit sessions (anonymous); source from referrer/utm_source. "
                    "Counting started when the storefront VisitorBeacon + checkout pixel went live."}
