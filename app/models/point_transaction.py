"""PointTransaction – an append-only ledger of every point change.

`users.points` is just a cached total; this table is the source of truth,
which makes rule changes / audits / recalculations possible later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.time import now_utc


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # may be negative
    reason: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    # set when a SUPER_ADMIN manually adjusts someone's points
    awarded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_utc, index=True, nullable=False
    )
