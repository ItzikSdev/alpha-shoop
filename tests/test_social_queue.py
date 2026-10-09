"""Social MCP: approval gate, per-platform validation, honest status, inbox."""
from __future__ import annotations

import pytest

from src.social_mcp import meta, publish, queue, tiktok
from src.social_mcp import server as social_server


@pytest.fixture(autouse=True)
def _tmp_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "_PATH", tmp_path / "social_queue.json")


def test_platform_kind_validation():
    with pytest.raises(ValueError):
        queue.add_draft("instagram", "text", "hi")                 # IG has no text posts
    with pytest.raises(ValueError):
        queue.add_draft("tiktok", "video", "hi")                   # video needs media
    with pytest.raises(ValueError):
        queue.add_draft("facebook", "photo", "hi", media_url="http://x")  # must be https
    with pytest.raises(ValueError):
        queue.add_draft("myspace", "text", "hi")
    d = queue.add_draft("instagram", "reel", "hook", media_url="https://cdn.shopify.com/v.mp4")
    assert d["status"] == "pending" and d["platform"] == "instagram"


def test_decide_flow_and_feedback():
    d = queue.add_draft("facebook", "text", "hello")
    assert queue.decide(d["id"], "hold", "op")["status"] == "held"
    r = queue.decide(d["id"], "reject", "op", "too salesy")
    assert r["status"] == "rejected" and r["feedback"] == "too salesy"
    assert queue.decide(d["id"], "approve", "op") is None        # already decided
    assert queue.decide(d["id"], "bogus", "op") is None


@pytest.mark.asyncio
async def test_publish_refused_until_approved_and_routed_per_platform(monkeypatch):
    calls = []

    async def fake_ig(kind, caption, *, media_url, poll_seconds=180):
        calls.append(("ig", kind))
        return "ig_1"

    monkeypatch.setattr(publish.meta, "publish_instagram", fake_ig)
    d = queue.add_draft("instagram", "photo", "hi", media_url="https://cdn.shopify.com/a.jpg")
    r = await social_server.publish_approved(d["id"])
    assert r["ok"] is False and not calls
    queue.decide(d["id"], "approve", "op")
    r = await social_server.publish_approved(d["id"])
    assert r == {"ok": True, "platform": "instagram", "remote_id": "ig_1"} and calls == [("ig", "photo")]
    assert queue.get_draft(d["id"])["status"] == "published"


@pytest.mark.asyncio
async def test_failed_publish_stays_approved(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("graph says no")

    monkeypatch.setattr(publish.meta, "publish_facebook", boom)
    d = queue.add_draft("facebook", "text", "hello")
    queue.decide(d["id"], "approve", "op")
    r = await social_server.publish_approved(d["id"])
    assert r["ok"] is False
    assert queue.get_draft(d["id"])["status"] == "approved"
    assert "graph says no" in queue.get_draft(d["id"])["error"]


@pytest.mark.asyncio
async def test_status_names_missing_env_without_network(monkeypatch):
    for k in ("META_PAGE_ID", "FB_PAGE_ACCESS_TOKEN", "META_ACCESS_TOKEN", "META_ACCESS_TOKEN_ALPHA_FOR_BABY", "TIKTOK_CLIENT_KEY",
              "TIKTOK_CLIENT_SECRET", "TIKTOK_CONTENT_REDIRECT_URI", "TIKTOK_USER_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    s = await publish.all_status()
    assert s["facebook"]["ok"] is False and "META_PAGE_ID" in s["facebook"]["missing_env"]
    assert s["instagram"]["ok"] is False
    assert s["tiktok"]["ok"] is False and "TIKTOK_CLIENT_KEY" in s["tiktok"]["missing_env"]


def test_tiktok_login_needs_app_keys(monkeypatch):
    monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
    assert tiktok.login_url()["ok"] is False
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "ck")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "cs")
    monkeypatch.setenv("TIKTOK_CONTENT_REDIRECT_URI", "https://alpha-tech.live/tiktok/callback")
    r = tiktok.login_url()
    assert r["ok"] and "video.publish" in r["authorize_url"] and "cs" not in r["authorize_url"]


def test_server_exposes_no_approve_tool():
    assert not any("approve" in n and n != "publish_approved" for n in social_server.TOOL_NAMES)


def test_inbox_lists_pending_drafts_first(monkeypatch):
    from src.org import inbox
    queue.add_draft("facebook", "text", "first post")
    items = inbox.build_inbox()
    assert items and items[0]["kind"] == "social_draft" and items[0]["decide"] is True
