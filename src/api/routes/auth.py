"""Auth endpoints — issue JWT tokens for the Alpha Shoop API."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from jose import jwt
from src.config import get_settings

router = APIRouter()


class TokenRequest(BaseModel):
    operator: str = "dev-operator"
    password: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post(
    "/auth/token",
    response_model=TokenResponse,
    summary="Issue a JWT access token",
    description=(
        "In **development** mode any operator name is accepted without a password. "
        "Set `app_env=production` to require real credentials."
    ),
)
async def issue_token(body: TokenRequest) -> TokenResponse:
    settings = get_settings()

    if settings.is_production:
        # Placeholder: plug in real user-store check here before going live
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Production auth not configured — set up a user store first.",
        )

    if not body.operator.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="operator cannot be empty",
        )

    expire_minutes = settings.jwt_expire_minutes
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": body.operator.strip(),
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
    )
