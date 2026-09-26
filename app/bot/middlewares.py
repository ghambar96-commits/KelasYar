"""Bot middlewares – one DB session & fresh user per update."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.core.logging import get_logger
from app.database import AsyncSessionLocal
from app.services import user_service

from . import texts as T

logger = get_logger("bot.middleware")


class UserSessionMiddleware(BaseMiddleware):
    """Outer middleware (runs before filters):

    1. opens a DB session for the whole update,
    2. resolves the user by numeric Telegram ID (auto-registers newcomers),
    3. blocks banned users,
    4. injects `session` + `user` into handler kwargs,
    5. commits/rolls back at the end (unit-of-work per update).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = getattr(event, "from_user", None)
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            user = await user_service.get_or_create(
                session,
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )

            if user.is_banned:
                if isinstance(event, Message):
                    await event.answer(T.banned(user.ban_reason))
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 شما مسدود شده‌اید.", show_alert=True)
                return

            data["session"] = session
            data["user"] = user
            try:
                result = await handler(event, data)
            except Exception:
                await session.rollback()
                raise
            else:
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.exception("commit failed after update")
            return result
