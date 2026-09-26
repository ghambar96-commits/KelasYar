"""Custom aiogram filters (role guards + FSM-safe text predicate)."""

from __future__ import annotations

from aiogram.filters import Filter

from app.bot.texts import ALL_MENU_BUTTONS
from app.models import Role, role_at_least


class MinRole(Filter):
    """Allows the handler only for users at/above `minimum` role.

    The user object is resolved by UserSessionMiddleware BEFORE filters run
    (outer middleware), based on the numeric Telegram ID.
    """

    def __init__(self, minimum: Role):
        self.minimum = minimum

    async def __call__(self, event, data: dict) -> bool:
        user = data.get("user")
        return user is not None and role_at_least(user.role, self.minimum)


def is_plain_text(message: Message) -> bool:
    """FSM input guard: real text that is not a command or a menu button."""
    from aiogram.types import Message  # local import avoids circulars at module load

    text = (message.text or "").strip()
    return (
        isinstance(message, Message)
        and bool(text)
        and not text.startswith("/")
        and text not in ALL_MENU_BUTTONS
    )
