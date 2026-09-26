"""User service – identity, roles, moderation, listing, stats."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestError, PermissionDeniedError
from app.core.logging import get_logger
from app.models import Homework, Role, User, role_at_least
from app.services import audit_service
from app.utils.time import today_local

logger = get_logger("users")


# ----------------------------------------------------------------- identity
async def get_or_create(session: AsyncSession, *, telegram_id: int, username: str | None,
                        first_name: str | None, last_name: str | None) -> User:
    """Find or register a user by numeric Telegram ID (never by username)."""
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))

    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=Role.USER,
        )
        session.add(user)
        await session.flush()
        await audit_service.log(
            session, None, "user.register", "user", user.id,
            {"telegram_id": telegram_id, "username": username}, source="telegram",
        )
        logger.info("new user registered: tg=%s", telegram_id)

    else:
        # keep cached Telegram profile fields up to date (username CAN change)
        if username != user.username or first_name != user.first_name or last_name != user.last_name:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name

    # SUPER_ADMIN bootstrap: only the IDs whitelisted in the environment.
    settings = get_settings()
    if telegram_id in settings.super_admin_ids and user.role != Role.SUPER_ADMIN:
        old = user.role
        user.role = Role.SUPER_ADMIN
        await audit_service.log(
            session, user, "user.role_bootstrap", "user", user.id,
            {"from": old.value, "to": Role.SUPER_ADMIN.value,
             "via": "SUPER_ADMIN_TELEGRAM_IDS"}, source="telegram",
        )
        logger.info("user tg=%s bootstrapped as SUPER_ADMIN", telegram_id)

    return user


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


# ------------------------------------------------------------------ roles
async def set_role(session: AsyncSession, actor: User, target: User, new_role: Role,
                   source: str = "api") -> User:
    if not role_at_least(actor.role, Role.SUPER_ADMIN):
        raise PermissionDeniedError("فقط مدیر کل می‌تواند نقش کاربران را تغییر دهد.")
    if new_role == Role.SUPER_ADMIN:
        raise BadRequestError(
            "نقش SUPER_ADMIN فقط از طریق متغیر محیطی SUPER_ADMIN_TELEGRAM_IDS تعیین می‌شود."
        )
    if target.role == Role.SUPER_ADMIN:
        raise BadRequestError("نقش مدیر کل قابل تغییر نیست.")
    if target.id == actor.id:
        raise BadRequestError("شما نمی‌توانید نقش خودتان را تغییر دهید.")
    if target.role == new_role:
        raise BadRequestError(f"نقش این کاربر از قبل {new_role.value} است.")

    old_role = target.role
    target.role = new_role
    await audit_service.log(
        session, actor, "user.role_change", "user", target.id,
        {"from": old_role.value, "to": new_role.value, "target_telegram_id": target.telegram_id},
        source=source,
    )
    await session.commit()
    logger.info("role of user %s changed %s -> %s by %s", target.id, old_role, new_role, actor.id)
    return target


# -------------------------------------------------------------- moderation
async def ban(session: AsyncSession, actor: User, target: User, reason: str | None = None,
              source: str = "api") -> User:
    if not role_at_least(actor.role, Role.SUPER_ADMIN):
        raise PermissionDeniedError("فقط مدیر کل می‌تواند کاربران را مسدود کند.")
    if target.role == Role.SUPER_ADMIN or target.id == actor.id:
        raise BadRequestError("مدیر کل را نمی‌توان مسدود کرد.")
    if target.is_banned:
        raise BadRequestError("این کاربر قبلاً مسدود شده است.")

    target.is_banned = True
    target.ban_reason = reason
    await audit_service.log(
        session, actor, "user.ban", "user", target.id,
        {"reason": reason, "target_telegram_id": target.telegram_id}, source=source,
    )
    await session.commit()
    logger.info("user %s banned by %s (%s)", target.id, actor.id, reason)
    return target


async def unban(session: AsyncSession, actor: User, target: User, source: str = "api") -> User:
    if not role_at_least(actor.role, Role.SUPER_ADMIN):
        raise PermissionDeniedError("فقط مدیر کل می‌تواند مسدودیت کاربران را بردارد.")
    if not target.is_banned:
        raise BadRequestError("این کاربر مسدود نیست.")

    target.is_banned = False
    target.ban_reason = None
    await audit_service.log(
        session, actor, "user.unban", "user", target.id, {}, source=source
    )
    await session.commit()
    return target


# ------------------------------------------------------------------ queries
async def list_users(
    session: AsyncSession,
    *,
    q: str | None = None,
    role: Role | None = None,
    banned: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[User], int]:
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)

    filters = []
    if q:
        needle = f"%{q.strip().lstrip('@').lower()}%"
        conditions = [
            func.lower(User.username).like(needle),
            func.lower(User.first_name).like(needle),
            func.lower(User.last_name).like(needle),
        ]
        if q.strip().isdigit():
            conditions.append(User.telegram_id == int(q.strip()))
        filters.append(or_(*conditions))
    if role is not None:
        filters.append(User.role == role)
    if banned is not None:
        filters.append(User.is_banned == banned)

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    total = await session.scalar(count_stmt) or 0
    users = (
        (await session.execute(
            stmt.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
        ))
        .scalars()
        .all()
    )
    return list(users), total


async def search_user(session: AsyncSession, query: str) -> User | None:
    """Single-user lookup for the bot admin panel (ID / telegram-id / username)."""
    query = query.strip()
    if query.isdigit():
        user = await get_by_telegram_id(session, int(query))
        if user:
            return user
        return await get_by_id(session, int(query))
    users, _ = await list_users(session, q=query, page=1, page_size=1)
    return users[0] if users else None


# ------------------------------------------------------------------- stats
async def stats(session: AsyncSession) -> dict:
    today = today_local()

    users_total = await session.scalar(select(func.count()).select_from(User)) or 0
    banned = await session.scalar(
        select(func.count()).select_from(User).where(User.is_banned.is_(True))
    ) or 0
    by_role = dict(
        (await session.execute(select(User.role, func.count()).group_by(User.role))).all()
    )
    homework_total = await session.scalar(select(func.count()).select_from(Homework)
                                         .where(Homework.deleted_at.is_(None))) or 0
    homework_today = await session.scalar(
        select(func.count()).select_from(Homework)
        .where(Homework.deleted_at.is_(None), Homework.homework_date == today)
    ) or 0
    homework_upcoming = await session.scalar(
        select(func.count()).select_from(Homework)
        .where(Homework.deleted_at.is_(None), Homework.homework_date > today)
    ) or 0
    top_subjects = [
        {"subject": subject, "count": count}
        for subject, count in (
            await session.execute(
                select(Homework.subject, func.count())
                .where(Homework.deleted_at.is_(None))
                .group_by(Homework.subject)
                .order_by(func.count().desc())
                .limit(5)
            )
        ).all()
    ]

    return {
        "users": {
            "total": users_total,
            "banned": banned,
            "by_role": {role.value if hasattr(role, "value") else str(role): count
                        for role, count in by_role.items()},
        },
        "homework": {
            "total": homework_total,
            "today": homework_today,
            "upcoming": homework_upcoming,
        },
        "top_subjects": top_subjects,
    }
