"""Database-backed authentication and authorization dependencies."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from app.services.auth_service import AuthService
from app.services.user_service import user_service


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """Return the active user from the latest database record."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization header",
        )

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format",
        )

    token_data = AuthService.verify_token(authorization.split(" ", 1)[1])
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = await user_service.get_user_by_username(token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "name": user.username,
        "is_admin": user.is_admin,
        "roles": ["admin"] if user.is_admin else ["user"],
        "preferences": user.preferences.model_dump() if user.preferences else {},
    }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require the latest database-backed user record to be an administrator."""
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
