"""Tests: MCP tool functions (direct calls, no external API)."""
import pytest
from src.mcp_tools import sourcing, market, ads, fulfillment
from src.mcp_tools.server import list_tools, invoke_tool


@pytest.mark.asyncio
async def test_search_trending_products_returns_list():
    products = await sourcing.search_trending_products(category="electronics", max_results=5)
    assert isinstance(products, list)
    assert len(products) <= 5


@pytest.mark.asyncio
async def test_search_trending_products_filters_by_margin():
    products = await sourcing.search_trending_products(category="electronics", max_results=20, min_margin=0.40)
    for p in products:
        assert p.get("margin_pct", 0) >= 0.40


@pytest.mark.asyncio
async def test_get_shipping_cost_returns_dict():
    result = await sourcing.get_shipping_cost("CJ000001", "US")
    assert "cost_usd" in result
    assert "estimated_days" in result
    assert "carrier" in result
    assert isinstance(result["cost_usd"], float)


@pytest.mark.asyncio
async def test_check_google_trends_structure():
    result = await market.check_google_trends("wireless earbuds")
    assert "trend_score" in result
    assert 0 <= result["trend_score"] <= 100
    assert isinstance(result["interest_over_time"], list)


@pytest.mark.asyncio
async def test_get_campaign_metrics_returns_numbers():
    result = await ads.get_campaign_metrics("camp_test", "LAST_7_DAYS")
    assert "impressions" in result
    assert "clicks" in result
    assert "spend_usd" in result
    assert "roas" in result


@pytest.mark.asyncio
async def test_server_list_tools_has_all_10():
    tools = list_tools()
    assert len(tools) == 10
    assert "search_trending_products" in tools
    assert "fulfill_shopify_order" in tools


@pytest.mark.asyncio
async def test_server_invoke_unknown_tool_raises():
    with pytest.raises(KeyError, match="Unknown tool"):
        await invoke_tool("does_not_exist", {})


@pytest.mark.asyncio
async def test_server_invoke_get_shipping_cost():
    result = await invoke_tool("get_shipping_cost", {"product_id": "CJ001", "destination_country": "US"})
    assert "cost_usd" in result
