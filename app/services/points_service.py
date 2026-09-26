"""Points & ranking service.

IMPORTANT – the point rules are NOT hard-coded. They live in the settings
table under key "point_rules" and can be changed at runtime by SUPER_ADMIN
via the REST API or the bot admin panel. The constants in settings_service
are bootstrap defaults only.

`users.points` is a cached total; `point_transactions` is the append-only
ledger (source of truth) so history, recalculation and audits stay possible.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import PointTransaction, User
from app.services import audit_service, settings_service
from app.utils.time import now_utc, today_local, utc_day_start_for_local_today, yesterday_local

logger = get_logger("points")


# ------------------------------------------------------------------ rules
async def get_rules(session: AsyncSession) -> dict:
    """Current point rules merged over defaults (forward compatible)."""
    stored = await settings_service.get_json(session, settings_service.POINT_RULES_KEY, None)
    if not isinstance(stored, dict):
        stored = {}

    defaults = settings_service.DEFAULT_POINT_RULES
    actions = dict(defaults["actions"])
    actions.update({k: v for k, v in (stored.get("actions") or {}).items() if v is not None})

    merged = {"enabled": stored.get("enabled", defaults["enabled"]), "actions": actions}
    return merged


async def set_rules(session: AsyncSession, rules: dict, actor: User | None = None,
                    source: str = "api") -> dict:
    """Persist new rules (full replace of the given structure)."""
    current = await get_rules(session)
    current["enabled"] = rules.get("enabled", current["enabled"])
    if "actions" in rules and isinstance(rules["actions"], dict):
        current["actions"] = {**current["actions"], **rules["actions"]}
    await settings_service.set_json(
        session, settings_service.POINT_RULES_KEY, current, actor, source
    )
    return current


# ----------------------------------------------------------------- awarding
async def _already_awarded_today(session: AsyncSession, user_id: int, reason: str) -> bool:
    day_start = utc_day_start_for_local_today()
    stmt = (
        select(func.count())
        .select_from(PointTransaction)
        .where(
            PointTransaction.user_id == user_id,
            PointTransaction.reason == reason,
            PointTransaction.created_at >= day_start,
        )
    )
    return (await session.scalar(stmt) or 0) > 0


async def award(
    session: AsyncSession,
    user: User,
    reason: str,
    *,
    meta: dict | None = None,
    awarded_by: int | None = None,
    description: str | None = None,
    once_per_day: bool = False,
    amount_override: int | None = None,
    at: datetime | None = None,
) -> PointTransaction | None:
    """Award points for `reason` according to the current rules.

    Returns the created transaction, or None when: rules disabled, unknown
    reason, zero configured amount, or (once_per_day) already awarded today.
    """
    rules = await get_rules(session)
    if not rules.get("enabled"):
        return None

    amount = amount_override
    if amount is None:
        amount = (rules["actions"] or {}).get(reason)
    if not amount or amount <= 0:
        return None

    if once_per_day and await _already_awarded_today(session, user.id, reason):
        return None

    tx = PointTransaction(
        user_id=user.id,
        amount=amount,
        reason=reason,
        description=description,
        meta=meta,
        awarded_by=awarded_by,
        created_at=at or now_utc(),
    )
    session.add(tx)
    user.points = (user.points or 0) + amount
    await session.flush()
    return tx


async def record_daily_activity(session: AsyncSession, user: User) -> dict:
    """Streak bookkeeping + first-activity-of-day bonus. Idempotent per local day."""
    today = today_local()
    if user.last_activity_date == today:
        return {"streak": user.streak_count, "changed": False}

    if user.last_activity_date == yesterday_local():
        user.streak_count = (user.streak_count or 0) + 1
    else:
        user.streak_count = 1
    user.last_activity_date = today

    await award(session, user, "first_daily_activity", meta={"streak": user.streak_count})

    # streak bonus: <streak_bonus> points per consecutive day, capped at <streak_bonus_max>
    rules = await get_rules(session)
    per_day = (rules["actions"] or {}).get("streak_bonus")
    cap = (rules["actions"] or {}).get("streak_bonus_max")
    if per_day and cap and user.streak_count >= 2:
        bonus = per_day * min(user.streak_count, cap)
        await award(
            session, user, "streak_bonus", amount_override=bonus,
            meta={"streak": user.streak_count},
        )
    return {"streak": user.streak_count, "changed": True}


async def award_view_homework(session: AsyncSession, user: User) -> None:
    """Called when a user views today's homework (bot or API)."""
    await record_daily_activity(session, user)
    await award(session, user, "view_homework_today", once_per_day=True)


async def adjust(
    session: AsyncSession,
    admin: User,
    target: User,
    amount: int,
    note: str | None,
    source: str = "api",
) -> PointTransaction:
    """Manual +/- adjustment by SUPER_ADMIN (audited, negative allowed)."""
    tx = PointTransaction(
        user_id=target.id,
        amount=amount,
        reason="admin_adjustment",
        description=note,
        awarded_by=admin.id,
        meta={"admin_id": admin.id},
    )
    session.add(tx)
    target.points = (target.points or 0) + amount
    await audit_service.log(
        session, admin, "points.adjust", "user", target.id,
        {"amount": amount, "note": note, "new_total": target.points}, source=source,
    )
    await session.commit()
    logger.info("points of user %s adjusted by %s: %+d", target.id, admin.id, amount)
    return tx


# ------------------------------------------------------------------ queries
async def user_history(session: AsyncSession, user: User, limit: int = 20) -> list[PointTransaction]:
    stmt = (
        select(PointTransaction)
        .where(PointTransaction.user_id == user.id)
        .order_by(PointTransaction.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def user_activity_count(session: AsyncSession, user_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(PointTransaction)
        .where(PointTransaction.user_id == user_id)
    )
    return await session.scalar(stmt) or 0


async def ranking(session: AsyncSession, limit: int = 10) -> list[dict]:
    """Leaderboard: rank (ties share a rank), user, points, activity count."""
    acts = (
        select(PointTransaction.user_id.label("uid"), func.count().label("activities"))
        .group_by(PointTransaction.user_id)
        .subquery()
    )
    activities = func.coalesce(acts.c.activities, 0)
    stmt = (
        select(User, activities.label("activities"))
        .outerjoin(acts, acts.c.uid == User.id)
        .where(User.is_banned.is_(False))
        .order_by(User.points.desc(), activities.desc(), User.id)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()

    entries: list[dict] = []
    rank = 0
    prev: tuple | None = None
    for idx, (user, acts_count) in enumerate(rows, start=1):
        key = (user.points, acts_count)
        if key != prev:
            rank, prev = idx, key
        entries.append({"rank": rank, "user": user, "activities": acts_count})
    return entries


async def my_rank(session: AsyncSession, user: User) -> dict:
    activities = await user_activity_count(session, user.id)
    total = (
        await session.scalar(select(func.count()).select_from(User).where(User.is_banned.is_(False)))
        or 0
    )

    acts = (
        select(PointTransaction.user_id.label("uid"), func.count().label("activities"))
        .group_by(PointTransaction.user_id)
        .subquery()
    )
    others_acts = func.coalesce(acts.c.activities, 0)
    better_stmt = (
        select(func.count())
        .select_from(User)
        .outerjoin(acts, acts.c.uid == User.id)
        .where(User.is_banned.is_(False))
        .where(
            or_(
                User.points > user.points,
                and_(User.points == user.points, others_acts > activities),
                and_(User.points == user.points, others_acts == activities, User.id < user.id),
            )
        )
    )
    better = await session.scalar(better_stmt) or 0
    return {
        "rank": better + 1,
        "total_users": total,
        "activities": activities,
        "points": user.points,
        "streak_count": user.streak_count,
    }
