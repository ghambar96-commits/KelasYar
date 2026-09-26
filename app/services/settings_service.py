"""Settings service – runtime-editable configuration stored in the DB.

Point rules live here (key: "point_rules").  The defaults below are only a
bootstrap: SUPER_ADMIN can change every value at runtime through the API or
the bot, and new rule keys can be added without touching the code.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Setting, User
from app.services import audit_service

logger = get_logger("settings")

POINT_RULES_KEY = "point_rules"
CLASS_NAME_KEY = "class_name"

# Bootstrap defaults – the DB copy is authoritative once seeded.
DEFAULT_POINT_RULES: dict[str, Any] = {
    "enabled": True,
    "actions": {
        "first_daily_activity": 2,   # first interaction of the day
        "streak_bonus": 1,           # extra points per consecutive day
        "streak_bonus_max": 10,      # cap of the streak multiplier
        "view_homework_today": 1,    # viewing today's homework (once/day)
        "create_homework": 5,        # contributor registers a homework
        "edit_homework": 2,          # contributor edits a homework
        "add_attachment": 1,         # contributor attaches a file
    },
}

DEFAULT_SETTINGS: dict[str, dict] = {
    POINT_RULES_KEY: {
        "value": DEFAULT_POINT_RULES,
        "description": "امتیازدهی – مقدار امتیاز هر فعالیت (قابل تغییر توسط مدیر)",
    },
    CLASS_NAME_KEY: {
        "value": "کلاس ما",
        "description": "نام کلاس که در پیام‌های ربات نمایش داده می‌شود",
    },
}


async def ensure_defaults(session: AsyncSession) -> None:
    """Insert any missing setting rows (idempotent, runs at startup)."""
    for key, spec in DEFAULT_SETTINGS.items():
        existing = await session.scalar(select(Setting).where(Setting.key == key))
        if existing is None:
            session.add(
                Setting(
                    key=key,
                    value=spec["value"],
                    description=spec["description"],
                )
            )
    await session.commit()


async def get_json(session: AsyncSession, key: str, default: Any = None) -> Any:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        return default
    return row.value


async def set_json(
    session: AsyncSession,
    key: str,
    value: Any,
    actor: User | None = None,
    source: str = "api",
) -> None:
    row = await session.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        row = Setting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    row.updated_by = actor.id if actor else None
    await audit_service.log(
        session, actor, "settings.update", "setting", key, {"new_value": value}, source=source
    )
    await session.commit()
    logger.info("setting %s updated by %s", key, actor.id if actor else "system")


async def get_class_name(session: AsyncSession) -> str:
    value = await get_json(session, CLASS_NAME_KEY, "کلاس ما")
    return str(value) if value else "کلاس ما"
