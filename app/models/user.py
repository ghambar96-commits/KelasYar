"""User model – identity is ALWAYS the numeric Telegram User ID."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, Date, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import Role

if TYPE_CHECKING:  # pragma: no cover
    pass


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Numeric Telegram user id – up to 64 bits, never the (mutable!) username.
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    last_name: Mapped[Optional[str]] = mapped_column(String(128))

    role: Mapped[Role] = mapped_column(
        SAEnum(Role, native_enum=False, length=20),
        default=Role.USER,
        nullable=False,
        index=True,
    )

    # Gamification (cached total; point_transactions is the ledger/source of truth)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_date: Mapped[Optional[date]] = mapped_column(Date)

    # Moderation
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(String(255))

    # ---------------------------------------------------------------- helpers
    @property
    def full_name(self) -> str:
        parts = [self.first_name or "", self.last_name or ""]
        name = " ".join(p for p in parts if p).strip()
        return name or (f"@{self.username}" if self.username else f"user{self.id}")

    @property
    def display_name(self) -> str:
        name = self.full_name
        if self.username and f"@{self.username}" != name:
            return name
        return name

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} tg={self.telegram_id} role={self.role}>"
