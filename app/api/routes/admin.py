"""Admin endpoints – every route requires SUPER_ADMIN (router-level RBAC)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_super_admin
from app.core.exceptions import NotFoundError
from app.database import get_session
from app.models import Role, Setting, User
from app.schemas.admin import (
    ApiKeyCreatedOut,
    ApiKeyCreateIn,
    ApiKeyOut,
    AuditLogOut,
    BanIn,
    RoleUpdateIn,
    SettingOut,
    SettingUpdateIn,
)
from app.schemas.common import Page
from app.schemas.points import AdjustPointsIn
from app.schemas.user import UserOut
from app.services import audit_service, auth_service, points_service, user_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_super_admin)],
)


async def _get_target(session: AsyncSession, user_id: int) -> User:
    target = await user_service.get_by_id(session, user_id)
    if target is None:
        raise NotFoundError("کاربر یافت نشد.")
    return target


# ------------------------------------------------------------------ users
@router.get("/users", response_model=Page[UserOut], summary="فهرست کاربران")
async def list_users(
    q: str | None = Query(None, max_length=100, description="جستجو: نام/یوزرنیم/Telegram ID"),
    role: Role | None = Query(None),
    banned: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    users, total = await user_service.list_users(
        session, q=q, role=role, banned=banned, page=page, page_size=page_size
    )
    return Page[UserOut].build(users, total, page, page_size)


@router.get("/users/{user_id}", response_model=UserOut, summary="جزئیات یک کاربر")
async def get_user(
    user_id: int,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    return await _get_target(session, user_id)


@router.put("/users/{user_id}/role", response_model=UserOut, summary="تغییر نقش (USER <-> CONTRIBUTOR)")
async def set_role(
    user_id: int,
    body: RoleUpdateIn,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await _get_target(session, user_id)
    await user_service.set_role(session, admin, target, Role(body.role), source="api")
    await session.refresh(target)
    return target


@router.post("/users/{user_id}/ban", response_model=UserOut, summary="مسدود کردن کاربر")
async def ban_user(
    user_id: int,
    body: BanIn,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await _get_target(session, user_id)
    await user_service.ban(session, admin, target, body.reason, source="api")
    await session.refresh(target)
    return target


@router.post("/users/{user_id}/unban", response_model=UserOut, summary="رفع مسدودیت")
async def unban_user(
    user_id: int,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await _get_target(session, user_id)
    await user_service.unban(session, admin, target, source="api")
    await session.refresh(target)
    return target


@router.post(
    "/users/{user_id}/points/adjust",
    response_model=UserOut,
    summary="افزودن/کاستن امتیاز به‌صورت دستی",
)
async def adjust_points(
    user_id: int,
    body: AdjustPointsIn,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await _get_target(session, user_id)
    await points_service.adjust(session, admin, target, body.amount, body.note, source="api")
    await session.refresh(target)
    return target


# ------------------------------------------------------------------ stats
@router.get("/stats", summary="آمار کلی سیستم")
async def stats(
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.stats(session)


# -------------------------------------------------------------- audit logs
@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="لاگ رویدادها")
async def audit_logs(
    action: str | None = Query(None, max_length=64, description="پیشوند اکشن مثل homework."),
    entity_type: str | None = Query(None, max_length=32),
    actor_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    items, total = await audit_service.list_logs(
        session,
        action=action,
        entity_type=entity_type,
        actor_id=actor_id,
        page=page,
        page_size=page_size,
    )
    return Page[AuditLogOut].build(items, total, page, page_size)


# ---------------------------------------------------------------- settings
@router.get("/settings", response_model=list[SettingOut], summary="تنظیمات سیستم")
async def list_settings(
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(select(Setting).order_by(Setting.key))).scalars().all()
    return list(rows)


@router.put("/settings/{key}", response_model=SettingOut, summary="به‌روزرسانی یک تنظیم")
async def update_setting(
    key: str = Path(..., pattern=r"^[a-z][a-z0-9_]{0,63}$"),
    body: SettingUpdateIn = ...,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    from app.services import settings_service

    if key == settings_service.POINT_RULES_KEY:
        raise HTTPException(
            status_code=400,
            detail="قوانین امتیاز را از طریق PUT /api/points/rules تغییر دهید.",
        )
    await settings_service.set_json(session, key, body.value, actor=admin, source="api")
    row = await session.get(Setting, key)
    if row is None:
        raise NotFoundError("تنظیم یافت نشد.")
    return row


# ---------------------------------------------------------------- api keys
@router.get("/api-keys", response_model=list[ApiKeyOut], summary="فهرست کلیدهای API")
async def list_api_keys(
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    keys = await auth_service.list_api_keys(session)
    return list(keys)


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedOut,
    status_code=status.HTTP_201_CREATED,
    summary="ساخت کلید API جدید (مقدار خام فقط یک بار نمایش داده می‌شود)",
)
async def create_api_key(
    body: ApiKeyCreateIn,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    key, raw = await auth_service.create_api_key(session, admin, body.name)
    out = ApiKeyCreatedOut.model_validate({**ApiKeyOut.model_validate(key).model_dump(), "key": raw})
    return out


@router.delete("/api-keys/{key_id}", status_code=204, summary="ابطال کلید API")
async def revoke_api_key(
    key_id: int,
    admin: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    await auth_service.revoke_api_key(session, admin, key_id)
