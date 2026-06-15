"""Shared pytest fixtures."""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt
from src.main import app
from src.config import get_settings


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def auth_token(settings) -> str:
    """Generate a valid JWT for authenticated endpoint tests."""
    return jwt.encode(
        {"sub": "test-operator", "exp": 9999999999},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


@pytest.fixture
def auth_headers(auth_token) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
