import secrets
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def admin_auth_dependency() -> Callable:
    settings = get_settings()

    def verify_admin_key(x_api_key: str = Header(default="")) -> None:
        if x_api_key != settings.admin_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid admin api key",
            )

    return Depends(verify_admin_key)

