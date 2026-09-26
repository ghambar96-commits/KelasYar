"""FastAPI dependencies: authentication & role-based authorization.

Two interchangeable credential types:
  1. Authorization: Bearer <JWT>   – obtained by exchanging a bot-issued code
  2. X-API-Key: <raw key>          – machine clients (e.g. future admin panel)

In both cases the user (and their CURRENT role / ban status) is re-read from
the database on every request – a demoted or banned token stops working
immediately.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_session
from app.models import Role, User, role_at_least
from app.services import auth_service

bearer_scheme = HTTPBearer(auto_error=False, description="JWT از POST /api/auth/exchange")


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    user: User | None = None

    api_key = request.headers.get("x-api-key")
    if api_key:
        user = await auth_service.user_by_api_key(session, api_key)
    elif credentials is not None:
        user_id = decode_access_token(credentials.credentials)
        if user_id is not None:
            user = await session.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="احراز هویت نشده‌اید.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="حساب شما مسدود شده است.")
    return user


def require_at_least(minimum: Role):
    """Dependency factory enforcing a minimum role (RBAC)."""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if not role_at_least(user.role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="برای این عملیات دسترسی لازم را ندارید.",
            )
        return user

    return dependency


require_contributor = require_at_least(Role.CONTRIBUTOR)
require_super_admin = require_at_least(Role.SUPER_ADMIN)
