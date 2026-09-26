"""Attachment model – files (images/documents) attached to a homework item.

We store BOTH:
  - the local file on disk (served through the authenticated REST API), and
  - the Telegram file_id (lets the bot re-send the file instantly).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.utils.time import now_utc

if TYPE_CHECKING:  # pragma: no cover
    from app.models.homework import Homework


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    homework_id: Mapped[int] = mapped_column(
        ForeignKey("homeworks.id", ondelete="CASCADE"), index=True, nullable=False
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Telegram file_id for fast re-sending inside the bot (no re-upload needed).
    telegram_file_id: Mapped[Optional[str]] = mapped_column(String(255))

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, nullable=False
    )

    homework: Mapped["Homework"] = relationship(
        back_populates="attachments", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Attachment id={self.id} file={self.file_name!r}>"
