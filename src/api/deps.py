"""FastAPI dependencies: JWT auth, settings injection."""
from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from src.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


async def get_current_operator(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    """Decode JWT and return operator name. Raises 401 if invalid."""
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm])
        operator: str = payload.get("sub", "")
        if not operator:
            raise JWTError("empty sub")
        return operator
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc
