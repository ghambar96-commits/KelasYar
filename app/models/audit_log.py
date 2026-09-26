"""AuditLog – who did what, when, from where."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.time import now_utc


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # dotted action keys, e.g. "homework.create", "user.role_change", "user.ban"
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # where the action came from: "telegram" | "api" | "system"
    source: Mapped[str] = mapped_column(String(16), default="api", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, index=True, nullable=False
    )
