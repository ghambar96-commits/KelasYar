"""User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models import Role

from .common import ORMModel


class UserOut(ORMModel):
    id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str = ""
    role: Role
    points: int
    streak_count: int
    is_banned: bool
    ban_reason: str | None = None
    created_at: datetime


class UserUpdateSelf(ORMModel):
    """Fields a user may change on their own profile (future use)."""

    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
