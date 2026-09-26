"""Declarative base & shared mixins."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.time import now_utc


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """created_at / updated_at maintained by the ORM (UTC, naive)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, onupdate=now_utc, nullable=False
    )
