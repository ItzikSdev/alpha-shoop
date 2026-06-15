"""Tests: /api/v1/run, /api/v1/status, /api/v1/kill-switch"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_run_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/run", json={"task": "find trending products"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_accepts_valid_request(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/run",
        json={
            "task": "Find trending electronics products under $50 with 30% margin",
            "max_budget_usd": 100.0,
            "target_categories": ["electronics"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "thread_id" in body
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_run_rejects_short_task(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/run",
        json={"task": "short"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_run_rejects_budget_over_limit(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/run",
        json={"task": "find trending products for testing purposes now", "max_budget_usd": 9999},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_status_unknown_thread(client: AsyncClient):
    resp = await client.get("/api/v1/status/nonexistent-thread-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_then_poll_status(client: AsyncClient, auth_headers: dict):
    run_resp = await client.post(
        "/api/v1/run",
        json={"task": "Find trending home products with good margins for testing"},
        headers=auth_headers,
    )
    thread_id = run_resp.json()["thread_id"]

    status_resp = await client.get(f"/api/v1/status/{thread_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_kill_switch_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/kill-switch",
        json={"reason": "test emergency stop", "operator": "tester"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kill_switch_activates(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/kill-switch",
        json={"reason": "Spending limit exceeded in test", "operator": "test-operator"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["killed"] is True
