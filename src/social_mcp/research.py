"""Lia's market research — learn how other stores post, keep the patterns, reuse them.

Sources (read-only, public information only):
  * ad_library_search  — Meta Ad Library API (https://www.facebook.com/ads/library/api). Needs the
    owner's one-time identity confirmation there; until then it returns exactly what to do.
    Commercial ads are only searchable for EU/UK delivery.
  * web_social_search  — Google (Serper) results for public Facebook/Instagram/TikTok posts and
    brand pages of other baby/toy stores.
What Lia keeps is PATTERNS (hook type, structure, CTA, why it works), never a copy of someone's
text — save_pattern stores a short paraphrase and a URL, and refuses long verbatim passages.
The playbook lives in data/social_playbook.json (override: SOCIAL_PLAYBOOK_PATH).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

GRAPH = "https://graph.facebook.com/v23.0"
_PATH = Path(os.environ.get("SOCIAL_PLAYBOOK_PATH",
                            Path(__file__).resolve().parents[2] / "data" / "social_playbook.json"))
EU_COUNTRIES = ["DE", "FR", "IT", "ES", "NL"]
MAX_NOTE = 400

HOOK_TYPES = ("question", "bold-claim", "problem-agitate", "demo-in-first-second", "social-proof",
              "curiosity-gap", "relatable-moment", "how-to", "before-after", "other")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> list[dict]:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _save(items: list[dict]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(_PATH)


def _token() -> str:
    for k in ("META_ACCESS_TOKEN_ALPHA_FOR_BABY", "META_ACCESS_TOKEN", "FB_PAGE_ACCESS_TOKEN"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return ""


async def ad_library_search(query: str, countries: list[str] | None = None, limit: int = 12,
                            active_only: bool = True) -> dict:
    """Ads other advertisers run now (page, copy, headline, start date, snapshot link)."""
    tok = _token()
    if not tok:
        return {"ok": False, "error": "no Meta token in env (META_ACCESS_TOKEN_ALPHA_FOR_BABY)"}
    params = {
        "search_terms": query[:100], "ad_reached_countries": json.dumps(countries or EU_COUNTRIES),
        "ad_active_status": "ACTIVE" if active_only else "ALL", "limit": str(max(1, min(limit, 25))),
        "fields": "id,page_name,ad_creative_bodies,ad_creative_link_titles,ad_creative_link_captions,"
                  "ad_delivery_start_time,publisher_platforms,ad_snapshot_url",
        "access_token": tok,
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{GRAPH}/ads_archive", params=params)
    data = r.json() if r.content else {}
    if r.status_code != 200:
        err = (data.get("error") or {})
        if err.get("error_subcode") == 2332002 or err.get("code") == 10:
            return {"ok": False, "needs_owner": True,
                    "error": "Meta Ad Library API not unlocked for this account yet",
                    "fix": "Owner: open facebook.com/ads/library/api, confirm identity (one time), then retry. "
                           "Meanwhile use web_social_search."}
        return {"ok": False, "error": str(err.get("message") or r.text)[:300]}
    ads = []
    for a in data.get("data", []):
        ads.append({
            "page": a.get("page_name"),
            "body": (a.get("ad_creative_bodies") or [""])[0][:500],
            "headline": (a.get("ad_creative_link_titles") or [""])[0][:150],
            "since": (a.get("ad_delivery_start_time") or "")[:10],
            "platforms": a.get("publisher_platforms"),
            "url": a.get("ad_snapshot_url"),
        })
    return {"ok": True, "count": len(ads), "ads": ads,
            "tip": "Ads running for weeks/months are the ones that make money — study those first."}


async def web_social_search(query: str, num: int = 8) -> dict:
    """Public web results (Google via Serper) for how other brands post — pages, posts, write-ups."""
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if not key:
        return {"ok": False, "error": "SERPER_API_KEY missing"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post("https://google.serper.dev/search", json={"q": query, "num": max(1, min(num, 10))},
                         headers={"X-API-KEY": key, "Content-Type": "application/json"})
    if r.status_code != 200:
        return {"ok": False, "error": f"serper {r.status_code}"}
    return {"ok": True, "results": [{"title": x.get("title"), "snippet": x.get("snippet"), "link": x.get("link")}
                                    for x in r.json().get("organic", [])[:num]]}


def save_pattern(source: str, brand: str, hook_type: str, hook_example: str, structure: str,
                 cta: str, why_it_works: str, url: str = "", platform: str = "", tags: list[str] | None = None) -> dict:
    """Store ONE learned pattern. hook_example is a short PARAPHRASE (<=140 chars), not a copy."""
    if len(hook_example) > 140 or len(structure) > MAX_NOTE or len(why_it_works) > MAX_NOTE:
        return {"ok": False, "error": "too long — paraphrase: hook_example<=140 chars, others<=400"}
    if not (brand and structure and why_it_works):
        return {"ok": False, "error": "brand, structure and why_it_works are required"}
    items = _load()
    dup = next((p for p in items if p["brand"].lower() == brand.lower()
                and p["hook_example"].lower() == hook_example.lower()), None)
    if dup:
        return {"ok": True, "duplicate": True, "id": dup["id"]}
    item = {"id": "pat_" + uuid.uuid4().hex[:8], "learned_at": _now(), "source": source, "brand": brand,
            "platform": platform, "hook_type": hook_type if hook_type in HOOK_TYPES else "other",
            "hook_example": hook_example, "structure": structure, "cta": cta, "why_it_works": why_it_works,
            "url": url, "tags": tags or []}
    items.append(item)
    _save(items[-300:])
    return {"ok": True, "id": item["id"], "total_patterns": len(items)}


def read_playbook(limit: int = 25, hook_type: str = "", platform: str = "") -> dict:
    """The learned patterns (newest first) + a summary of which hook types dominate."""
    items = _load()
    if hook_type:
        items = [p for p in items if p["hook_type"] == hook_type]
    if platform:
        items = [p for p in items if p.get("platform") in ("", platform)]
    counts: dict[str, int] = {}
    for p in items:
        counts[p["hook_type"]] = counts.get(p["hook_type"], 0) + 1
    return {"ok": True, "total": len(items), "hook_type_counts": counts,
            "patterns": list(reversed(items))[:limit],
            "how_to_use": "Adapt a PATTERN to our product with our own words and real product facts. "
                          "Never copy a competitor's text, name, or claims."}
