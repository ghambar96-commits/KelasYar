"""Key/Value settings table (JSON values).

Holds runtime-editable configuration such as point rules or the class name –
so SUPER_ADMIN can change behaviour WITHOUT code changes or redeploys.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.time import now_utc


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    updated_by: Mapped[Optional[int]] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, onupdate=now_utc, nullable=False
    )
