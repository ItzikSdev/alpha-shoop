"""Reel rendering from an existing clip + the MCP tools (Shopify/network mocked)."""
import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from src.social_mcp import reel

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _clip(path: Path, seconds: int) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=size=1280x720:rate=24:duration={seconds}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(path)], check=True)
    return path


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return {"lines": out.split()}


def test_render_vertical_with_silent_audio_and_cta(tmp_path):
    src = _clip(tmp_path / "s.mp4", 20)
    info = asyncio.run(reel.render_reel(src, tmp_path / "o.mp4", hook="Wait for the end 👀", cta="Link below ⬇️"))
    assert info["width"] == 1080 and info["height"] == 1920
    assert 14.5 <= info["duration_s"] <= 15.2          # capped at 15s
    lines = _probe(tmp_path / "o.mp4")["lines"]
    assert "video,1080,1920" in lines and "audio" in lines


def test_short_clip_is_looped_up(tmp_path):
    src = _clip(tmp_path / "s.mp4", 3)
    info = asyncio.run(reel.render_reel(src, tmp_path / "o.mp4", hook="POV: bath time"))
    assert info["looped"] and info["duration_s"] >= 5.5


def test_make_reel_requires_hook_and_https(tmp_path):
    with pytest.raises(reel.ReelError):
        asyncio.run(reel.make_reel("http://x/y.mp4", "hook"))
    with pytest.raises(reel.ReelError):
        asyncio.run(reel.make_reel("https://x/y.mp4", "  "))


def test_list_store_videos_picks_mp4_and_skips_images(monkeypatch):
    async def fake_gql(q, v):
        return {"products": {"nodes": [{"id": "gid://p/1", "title": "Tub", "handle": "tub", "status": "ACTIVE",
                                        "onlineStoreUrl": "https://shop.example.com/products/tub", "media": {"nodes": [
            {"mediaContentType": "IMAGE"},
            {"mediaContentType": "VIDEO", "alt": "demo", "duration": 8000, "sources": [
                {"url": "https://cdn/x_480.mp4", "mimeType": "video/mp4", "height": 480, "width": 270},
                {"url": "https://cdn/x_1080.mp4", "mimeType": "video/mp4", "height": 1080, "width": 608},
                {"url": "https://cdn/x.m3u8", "mimeType": "application/x-mpegURL", "height": 1080, "width": 608}]}]}},
            {"id": "gid://p/2", "title": "No video", "handle": "nv", "status": "ACTIVE", "media": {"nodes": []}},
            {"id": "gid://p/3", "title": "Draft", "handle": "d", "status": "DRAFT", "onlineStoreUrl": None, "media": {"nodes": [
                {"mediaContentType": "VIDEO", "sources": [{"url": "https://cdn/d.mp4", "mimeType": "video/mp4", "height": 720, "width": 404}]}]}},
            {"id": "gid://p/4", "title": "Unpublished", "handle": "u", "status": "ACTIVE", "onlineStoreUrl": None, "media": {"nodes": [
                {"mediaContentType": "VIDEO", "sources": [{"url": "https://cdn/u.mp4", "mimeType": "video/mp4", "height": 720, "width": 404}]}]}}]}}
    import src.mcp_tools.shopify as sh
    monkeypatch.setattr(sh, "_shopify_gql", fake_gql)
    vids = asyncio.run(reel.list_store_videos())
    assert [v["product_title"] for v in vids] == ["Tub"]        # draft + unpublished products excluded
    assert vids[0]["video_url"] == "https://cdn/x_1080.mp4"
    assert vids[0]["product_url"] == "https://alphaforbaby.com/products/tub"
    assert "utm_campaign=reel" in vids[0]["tracked_url"]


def test_playbook_forbids_trademarked_themes():
    from src.social_mcp.server import REEL_PLAYBOOK
    assert any("trademark" in x.lower() for x in REEL_PLAYBOOK["do_not"])
