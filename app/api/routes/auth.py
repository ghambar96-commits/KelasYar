"""Auth endpoints (public: code -> JWT exchange)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.auth import AuthExchangeIn, AuthOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/exchange",
    response_model=AuthOut,
    summary="تبدیل کد یک‌بارمصرف ربات به توکن JWT",
)
async def exchange_code(body: AuthExchangeIn, session: AsyncSession = Depends(get_session)):
    user = await auth_service.exchange_code(session, body.code)
    token, expires_in = auth_service.build_token(user)
    return AuthOut(access_token=token, expires_in=expires_in, user=user)
