"""Health & readiness endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from src.models.responses import HealthResponse
from src.config import Settings, get_settings
import importlib.metadata

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Returns status of the API and all downstream services.",
)
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    try:
        version = importlib.metadata.version("fastapi")
    except Exception:
        version = "unknown"

    # Real implementation would ping each service
    services: dict[str, str] = {
        "database": "unchecked",
        "redis": "unchecked",
        "anthropic": "unchecked" if not settings.anthropic_api_key else "configured",
    }

    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.app_env,
        services=services,
    )
