"""Tests for the announcement-bar fix.

The store's announcement bar is the site.json marquee (rendered by apply_site_design),
NOT a stock Dawn/Horizon theme section. So `set_announcement_bar` used to return False
on every build_store run — which the agents wrongly flagged as a build-breaking "bug".
It now returns True (a deliberate no-op) when the theme has no stock announcement
section, so build_store no longer reports a phantom failure.
"""
import pytest

from src.mcp_tools import shopify_theme


@pytest.mark.asyncio
async def test_no_stock_header_group_is_graceful_noop(monkeypatch):
    async def _fake_read_asset(theme_id, path):
        return None  # JSON-driven store: no stock header-group.json
    monkeypatch.setattr(shopify_theme, "_read_asset", _fake_read_asset)
    ok = await shopify_theme.set_announcement_bar(["FREE SHIPPING"], "tid")
    assert ok is True  # graceful no-op, NOT a failure


@pytest.mark.asyncio
async def test_no_announcement_section_is_graceful_noop(monkeypatch):
    async def _fake_read_asset(theme_id, path):
        # A header group exists but has no announcement-type section.
        return {"sections": {"header": {"type": "header"}}, "order": ["header"]}
    monkeypatch.setattr(shopify_theme, "_read_asset", _fake_read_asset)
    ok = await shopify_theme.set_announcement_bar(["FREE SHIPPING"], "tid")
    assert ok is True


@pytest.mark.asyncio
async def test_marquee_renders_as_the_real_announcement_bar():
    from src.mcp_tools.shopify_design import render_site_design
    site = {"sections": [{
        "id": "announcement_marquee", "type": "marquee",
        "items": ["FREE SHIPPING OVER $50", "30-DAY RETURNS"],
    }]}
    html = render_site_design(site)
    assert "tob-ann" in html
    assert "FREE SHIPPING OVER $50" in html
