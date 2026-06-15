"""Tests: GET /api/v1/health"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body
    assert "services" in body


@pytest.mark.asyncio
async def test_health_services_dict(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    services = resp.json()["services"]
    assert isinstance(services, dict)
    assert "database" in services
    assert "redis" in services
