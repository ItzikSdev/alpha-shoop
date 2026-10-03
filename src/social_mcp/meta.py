"""Meta Graph API — Facebook Page + its linked Instagram Business account.

Env: META_PAGE_ID, and FB_PAGE_ACCESS_TOKEN (preferred) or META_ACCESS_TOKEN (a
user/system-user token with pages_manage_posts, pages_read_engagement,
pages_read_user_content, instagram_basic, instagram_content_publish,
instagram_manage_comments, instagram_manage_insights — the Page token is derived
from it). Optional: META_IG_USER_ID (else read from the Page's
instagram_business_account), META_GRAPH_VERSION.

All media must sit at a PUBLIC https URL (Meta's servers fetch it).
"""
from __future__ import annotations

import asyncio
import os

import httpx

_VER = os.environ.get("META_GRAPH_VERSION", "v23.0")
GRAPH = f"https://graph.facebook.com/{_VER}"


class MetaError(Exception):
    pass


def page_id() -> str:
    return os.environ.get("META_PAGE_ID", "").strip()


def missing_env() -> list[str]:
    miss = []
    if not page_id():
        miss.append("META_PAGE_ID")
    if not (os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip() or os.environ.get("META_ACCESS_TOKEN", "").strip()):
        miss.append("FB_PAGE_ACCESS_TOKEN|META_ACCESS_TOKEN")
    return miss


def _check(r: httpx.Response) -> dict:
    try:
        j = r.json()
    except Exception:
        raise MetaError(f"non-JSON response ({r.status_code})")
    if isinstance(j, dict) and j.get("error"):
        raise MetaError(str(j["error"].get("message", j["error"]))[:400])
    return j


async def page_token(c: httpx.AsyncClient) -> str:
    tok = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    if tok:
        return tok
    user = os.environ.get("META_ACCESS_TOKEN", "").strip()
    if not user or not page_id():
        raise MetaError("missing " + ", ".join(missing_env()))
    j = _check(await c.get(f"{GRAPH}/{page_id()}", params={"fields": "access_token", "access_token": user}))
    if not j.get("access_token"):
        raise MetaError("could not derive a Page token (need pages_manage_posts and a Page admin role)")
    return j["access_token"]


async def ig_user_id(c: httpx.AsyncClient, tok: str) -> str:
    ig = os.environ.get("META_IG_USER_ID", "").strip()
    if ig:
        return ig
    j = _check(await c.get(f"{GRAPH}/{page_id()}", params={"fields": "instagram_business_account", "access_token": tok}))
    ig = (j.get("instagram_business_account") or {}).get("id", "")
    if not ig:
        raise MetaError("no Instagram Business account is linked to this Facebook Page")
    return ig


async def status() -> dict:
    """Facebook + Instagram connectivity. Never returns a token."""
    fb = {"platform": "facebook", "missing_env": missing_env(), "graph_version": _VER}
    ig = {"platform": "instagram", "missing_env": list(fb["missing_env"])}
    if fb["missing_env"]:
        return {"facebook": {**fb, "ok": False}, "instagram": {**ig, "ok": False}}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            tok = await page_token(c)
            j = _check(await c.get(f"{GRAPH}/{page_id()}", params={"fields": "name,followers_count,fan_count", "access_token": tok}))
            fb.update(ok=True, page_name=j.get("name"), followers=j.get("followers_count") or j.get("fan_count"))
            try:
                igid = await ig_user_id(c, tok)
                k = _check(await c.get(f"{GRAPH}/{igid}", params={"fields": "username,followers_count,media_count", "access_token": tok}))
                ig.update(ok=True, username=k.get("username"), followers=k.get("followers_count"), media_count=k.get("media_count"))
            except Exception as e:
                ig.update(ok=False, error=str(e)[:300])
    except Exception as e:
        fb.update(ok=False, error=str(e)[:300])
        ig.update(ok=False, error="facebook page not reachable")
    return {"facebook": fb, "instagram": ig}


# ── Publishing ───────────────────────────────────────────────────────────────

async def publish_facebook(kind: str, message: str, *, link: str = "", media_url: str = "") -> str:
    async with httpx.AsyncClient(timeout=120) as c:
        tok = await page_token(c)
        pid = page_id()
        if kind in {"text", "link"}:
            data = {"message": message, "access_token": tok}
            if kind == "link":
                data["link"] = link
            return _check(await c.post(f"{GRAPH}/{pid}/feed", data=data))["id"]
        if kind == "photo":
            j = _check(await c.post(f"{GRAPH}/{pid}/photos", data={"url": media_url, "caption": message, "access_token": tok}))
            return j.get("post_id") or j["id"]
        if kind == "reel":
            start = _check(await c.post(f"{GRAPH}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}))
            vid, upload_url = start["video_id"], start["upload_url"]
            _check(await c.post(upload_url, headers={"Authorization": f"OAuth {tok}", "file_url": media_url}))
            fin = _check(await c.post(f"{GRAPH}/{pid}/video_reels", data={
                "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                "description": message, "access_token": tok}))
            if fin.get("success") is False:
                raise MetaError("reel finish phase did not report success")
            return vid
    raise MetaError(f"unsupported facebook kind {kind}")


async def publish_instagram(kind: str, caption: str, *, media_url: str, poll_seconds: int = 180) -> str:
    async with httpx.AsyncClient(timeout=60) as c:
        tok = await page_token(c)
        igid = await ig_user_id(c, tok)
        data = {"caption": caption, "access_token": tok}
        if kind == "photo":
            data["image_url"] = media_url
        elif kind == "reel":
            data.update(media_type="REELS", video_url=media_url)
        else:
            raise MetaError(f"unsupported instagram kind {kind}")
        container = _check(await c.post(f"{GRAPH}/{igid}/media", data=data))["id"]
        # Video containers process asynchronously; images are usually FINISHED at once.
        waited = 0
        while True:
            st = _check(await c.get(f"{GRAPH}/{container}", params={"fields": "status_code,status", "access_token": tok}))
            code = st.get("status_code")
            if code in (None, "FINISHED"):
                break
            if code in ("ERROR", "EXPIRED"):
                raise MetaError(f"instagram container {code}: {st.get('status', '')}"[:300])
            if waited >= poll_seconds:
                raise MetaError("instagram container still processing — retry publish later")
            await asyncio.sleep(5)
            waited += 5
        return _check(await c.post(f"{GRAPH}/{igid}/media_publish", data={"creation_id": container, "access_token": tok}))["id"]


# ── Reading (learning from what actually worked) ─────────────────────────────

async def recent_posts(platform: str, limit: int = 10) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await page_token(c)
        if platform == "facebook":
            j = _check(await c.get(f"{GRAPH}/{page_id()}/posts", params={
                "fields": "id,message,created_time,permalink_url,shares,reactions.summary(true).limit(0),comments.summary(true).limit(0)",
                "limit": limit, "access_token": tok}))
            return [{"id": p["id"], "text": (p.get("message") or "")[:300], "created": p.get("created_time"),
                     "url": p.get("permalink_url"),
                     "reactions": p.get("reactions", {}).get("summary", {}).get("total_count"),
                     "comments": p.get("comments", {}).get("summary", {}).get("total_count"),
                     "shares": (p.get("shares") or {}).get("count", 0)} for p in j.get("data", [])]
        igid = await ig_user_id(c, tok)
        j = _check(await c.get(f"{GRAPH}/{igid}/media", params={
            "fields": "id,caption,media_type,timestamp,permalink,like_count,comments_count",
            "limit": limit, "access_token": tok}))
        return [{"id": m["id"], "text": (m.get("caption") or "")[:300], "type": m.get("media_type"),
                 "created": m.get("timestamp"), "url": m.get("permalink"),
                 "likes": m.get("like_count"), "comments": m.get("comments_count")} for m in j.get("data", [])]


async def comments(platform: str, object_id: str, limit: int = 25) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await page_token(c)
        fields = "id,message,created_time,from" if platform == "facebook" else "id,text,timestamp,username"
        j = _check(await c.get(f"{GRAPH}/{object_id}/comments", params={"fields": fields, "limit": limit, "access_token": tok}))
    out = []
    for x in j.get("data", []):
        out.append({"id": x["id"], "text": x.get("message") or x.get("text", ""),
                    "created": x.get("created_time") or x.get("timestamp"),
                    "author": (x.get("from") or {}).get("name") or x.get("username")})
    return out


async def insights(platform: str, object_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await page_token(c)
        if platform == "facebook":
            j = _check(await c.get(f"{GRAPH}/{object_id}", params={
                "fields": "reactions.summary(true).limit(0),comments.summary(true).limit(0),shares", "access_token": tok}))
            return {"reactions": j.get("reactions", {}).get("summary", {}).get("total_count"),
                    "comments": j.get("comments", {}).get("summary", {}).get("total_count"),
                    "shares": (j.get("shares") or {}).get("count", 0)}
        j = _check(await c.get(f"{GRAPH}/{object_id}", params={"fields": "like_count,comments_count,media_type", "access_token": tok}))
        out = {"likes": j.get("like_count"), "comments": j.get("comments_count")}
        try:  # reach/views need instagram_manage_insights; report honestly if absent
            k = _check(await c.get(f"{GRAPH}/{object_id}/insights", params={"metric": "reach,views", "access_token": tok}))
            for m in k.get("data", []):
                out[m["name"]] = (m.get("values") or [{}])[0].get("value")
        except MetaError as e:
            out["insights_error"] = str(e)[:200]
        return out
