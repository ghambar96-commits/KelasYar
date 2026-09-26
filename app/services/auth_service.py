"""Auth service – pairing codes (bot -> JWT) and hashed API keys."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AuthError, NotFoundError
from app.core.security import (
    create_access_token,
    generate_api_key,
    generate_auth_code,
    hash_api_key,
)
from app.models import ApiKey, AuthCode, User
from app.services import audit_service
from app.utils.time import now_utc


# ----------------------------------------------------------- pairing codes
async def issue_auth_code(session: AsyncSession, user: User) -> str:
    """Create a fresh one-time code for the user (previous ones invalidated)."""
    await session.execute(
        delete(AuthCode).where(AuthCode.user_id == user.id, AuthCode.used_at.is_(None))
    )
    settings = get_settings()
    code = generate_auth_code()
    session.add(
        AuthCode(
            user_id=user.id,
            code=code,
            expires_at=now_utc() + timedelta(minutes=settings.auth_code_ttl_minutes),
        )
    )
    await session.commit()
    return code


async def exchange_code(session: AsyncSession, code: str) -> User:
    """Validate a pairing code and return its user (one-time, expiring)."""
    code = (code or "").strip().upper()
    if not code:
        raise AuthError("کد وارد شده نامعتبر است.")

    row = await session.scalar(
        select(AuthCode).where(AuthCode.code == code, AuthCode.used_at.is_(None))
    )
    if row is None:
        raise AuthError("کد نامعتبر است یا قبلاً استفاده شده است.")
    if row.expires_at < now_utc():
        raise AuthError("کد منقضی شده است؛ از ربات کد جدید بگیرید (/api).")

    row.used_at = now_utc()
    user = await session.get(User, row.user_id)
    if user is None:
        raise AuthError("کاربر یافت نشد.")
    await session.commit()
    return user


def build_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    token = create_access_token(user.id, user.role.value)
    return token, settings.jwt_expire_days * 86400


# ---------------------------------------------------------------- API keys
async def create_api_key(session: AsyncSession, admin: User, name: str) -> tuple[ApiKey, str]:
    raw, prefix, digest = generate_api_key()
    key = ApiKey(name=name, key_prefix=prefix, key_hash=digest, owner_user_id=admin.id)
    session.add(key)
    await session.flush()
    await audit_service.log(session, admin, "api_key.create", "api_key", key.id, {"name": name})
    await session.commit()
    return key, raw


async def list_api_keys(session: AsyncSession) -> list[ApiKey]:
    stmt = select(ApiKey).order_by(ApiKey.id.desc())
    return list((await session.execute(stmt)).scalars().all())


async def revoke_api_key(session: AsyncSession, admin: User, key_id: int) -> None:
    key = await session.get(ApiKey, key_id)
    if key is None:
        raise NotFoundError("کلید یافت نشد.")
    await audit_service.log(session, admin, "api_key.revoke", "api_key", key.id, {"name": key.name})
    await session.delete(key)
    await session.commit()


async def user_by_api_key(session: AsyncSession, raw_key: str) -> User | None:
    """Resolve an X-API-Key header to its owner (hash lookup, never stored raw)."""
    if not raw_key:
        return None
    digest = hash_api_key(raw_key.strip())
    key = await session.scalar(
        select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.is_active.is_(True))
    )
    if key is None:
        return None
    key.last_used_at = now_utc()
    user = await session.get(User, key.owner_user_id)
    if user is None:
        return None
    await session.commit()
    return user
