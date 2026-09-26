"""Homework model – multiple homework items per day are supported."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.attachment import Attachment
    from app.models.user import User


class Homework(TimestampMixin, Base):
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    homework_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)

    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )

    # Soft delete – keeps history & audit references intact.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )

    author: Mapped["User"] = relationship(
        foreign_keys=[created_by], lazy="joined"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="homework",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Attachment.id",
    )

    __table_args__ = (
        CheckConstraint(
            "due_date IS NULL OR due_date >= homework_date",
            name="ck_homework_due_gte_homework_date",
        ),
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def author_name(self) -> str:
        return self.author.full_name if self.author else "—"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Homework id={self.id} subject={self.subject!r} date={self.homework_date}>"
