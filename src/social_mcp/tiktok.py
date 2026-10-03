"""TikTok ORGANIC posting (Content Posting API) + the account's own video stats.

Different from src/tiktok_mcp (Marketing API = ads reporting). This needs a TikTok
for Developers app (developers.tiktok.com) with Login Kit + Content Posting API
(Direct Post) and scopes user.info.basic, video.publish, video.list.

Env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_CONTENT_REDIRECT_URI;
after OAuth (login() -> owner approves -> complete_auth(code)):
TIKTOK_USER_ACCESS_TOKEN, TIKTOK_USER_REFRESH_TOKEN (persisted to .env).

Platform rules worth knowing (TikTok docs):
  - Until the app passes TikTok's audit, posts can only be PRIVATE (SELF_ONLY).
  - PULL_FROM_URL only works for a URL prefix/domain verified in the developer portal.
  - privacy_level must be one of creator_info's privacy_level_options.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlencode

import httpx

API = "https://open.tiktokapis.com/v2"
_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
_SCOPES = "user.info.basic,video.publish,video.list"
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class TikTokError(Exception):
    pass


def _env(k: str) -> str:
    return os.environ.get(k, "").strip()


def missing_env(for_posting: bool = True) -> list[str]:
    need = ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_CONTENT_REDIRECT_URI"]
    if for_posting:
        need.append("TIKTOK_USER_ACCESS_TOKEN")
    return [k for k in need if not _env(k)]


def _persist(**kv: str) -> None:
    lines = _ENV_PATH.read_text().splitlines() if _ENV_PATH.exists() else []
    for key, value in kv.items():
        prefix = f"{key}="
        for i, ln in enumerate(lines):
            if ln.startswith(prefix):
                lines[i] = f"{prefix}{value}"
                break
        else:
            lines.append(f"{prefix}{value}")
        os.environ[key] = value
    _ENV_PATH.write_text("\n".join(lines) + "\n")


def _check(r: httpx.Response) -> dict:
    try:
        j = r.json()
    except Exception:
        raise TikTokError(f"non-JSON response ({r.status_code})")
    err = j.get("error") if isinstance(j, dict) else None
    if isinstance(err, dict) and err.get("code") not in (None, "ok"):
        raise TikTokError(f"{err.get('code')}: {err.get('message', '')}"[:400])
    if isinstance(j, dict) and j.get("error_description"):
        raise TikTokError(j["error_description"][:400])
    return j


def _auth() -> dict:
    tok = _env("TIKTOK_USER_ACCESS_TOKEN")
    if not tok:
        raise TikTokError("TikTok not authorized yet — run tiktok_login, then tiktok_complete_auth")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}


# ── OAuth (owner does the consent click once) ────────────────────────────────

def login_url() -> dict:
    miss = missing_env(for_posting=False)
    if miss:
        return {"ok": False, "missing_env": miss}
    state = secrets.token_urlsafe(16)
    q = urlencode({"client_key": _env("TIKTOK_CLIENT_KEY"), "scope": _SCOPES, "response_type": "code",
                   "redirect_uri": _env("TIKTOK_CONTENT_REDIRECT_URI"), "state": state})
    return {"ok": True, "authorize_url": f"{_AUTH_URL}?{q}", "state": state,
            "next": "Open the URL, approve, copy the `code` query param from the redirect, call tiktok_complete_auth(code)."}


async def complete_auth(code: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        j = _check(await c.post(f"{API}/oauth/token/", data={
            "client_key": _env("TIKTOK_CLIENT_KEY"), "client_secret": _env("TIKTOK_CLIENT_SECRET"),
            "code": code, "grant_type": "authorization_code", "redirect_uri": _env("TIKTOK_CONTENT_REDIRECT_URI")},
            headers={"Content-Type": "application/x-www-form-urlencoded"}))
    _persist(TIKTOK_USER_ACCESS_TOKEN=j["access_token"], TIKTOK_USER_REFRESH_TOKEN=j.get("refresh_token", ""),
             TIKTOK_USER_OPEN_ID=j.get("open_id", ""))
    return {"ok": True, "scope": j.get("scope"), "expires_in": j.get("expires_in")}


async def refresh() -> dict:
    rt = _env("TIKTOK_USER_REFRESH_TOKEN")
    if not rt:
        raise TikTokError("no TIKTOK_USER_REFRESH_TOKEN — re-run tiktok_login")
    async with httpx.AsyncClient(timeout=30) as c:
        j = _check(await c.post(f"{API}/oauth/token/", data={
            "client_key": _env("TIKTOK_CLIENT_KEY"), "client_secret": _env("TIKTOK_CLIENT_SECRET"),
            "grant_type": "refresh_token", "refresh_token": rt},
            headers={"Content-Type": "application/x-www-form-urlencoded"}))
    _persist(TIKTOK_USER_ACCESS_TOKEN=j["access_token"], TIKTOK_USER_REFRESH_TOKEN=j.get("refresh_token", rt))
    return {"ok": True}


# ── Status / posting / reading ───────────────────────────────────────────────

async def creator_info() -> dict:
    async with httpx.AsyncClient(timeout=20) as c:
        j = _check(await c.post(f"{API}/post/publish/creator_info/query/", headers=_auth()))
    return j.get("data", {})


async def status() -> dict:
    out = {"platform": "tiktok", "missing_env": missing_env()}
    if out["missing_env"]:
        return {**out, "ok": False}
    try:
        info = await creator_info()
        out.update(ok=True, username=info.get("creator_username"), nickname=info.get("creator_nickname"),
                   privacy_options=info.get("privacy_level_options"),
                   max_video_seconds=info.get("max_video_post_duration_sec"))
    except Exception as e:
        out.update(ok=False, error=str(e)[:300])
    return out


async def publish_video(caption: str, video_url: str) -> str:
    """Direct Post from a public URL. Uses the most public privacy level the account
    allows (SELF_ONLY until TikTok audits the app). Returns publish_id."""
    info = await creator_info()
    opts = info.get("privacy_level_options") or ["SELF_ONLY"]
    privacy = next((p for p in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY") if p in opts), opts[0])
    body = {"post_info": {"title": caption[:2200], "privacy_level": privacy,
                          "disable_comment": bool(info.get("comment_disabled")),
                          "disable_duet": bool(info.get("duet_disabled")),
                          "disable_stitch": bool(info.get("stitch_disabled"))},
            "source_info": {"source": "PULL_FROM_URL", "video_url": video_url}}
    async with httpx.AsyncClient(timeout=60) as c:
        j = _check(await c.post(f"{API}/post/publish/video/init/", headers=_auth(), json=body))
    return j["data"]["publish_id"]


async def publish_status(publish_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as c:
        j = _check(await c.post(f"{API}/post/publish/status/fetch/", headers=_auth(), json={"publish_id": publish_id}))
    return j.get("data", {})


async def recent_videos(limit: int = 10) -> list[dict]:
    fields = "id,title,create_time,share_url,view_count,like_count,comment_count,share_count"
    async with httpx.AsyncClient(timeout=30) as c:
        j = _check(await c.post(f"{API}/video/list/?fields={fields}", headers=_auth(), json={"max_count": min(limit, 20)}))
    return [{"id": v.get("id"), "text": (v.get("title") or "")[:300], "created": v.get("create_time"),
             "url": v.get("share_url"), "views": v.get("view_count"), "likes": v.get("like_count"),
             "comments": v.get("comment_count"), "shares": v.get("share_count")}
            for v in j.get("data", {}).get("videos", [])]
