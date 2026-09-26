"""Audit logging service – every important action leaves a trail."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def log(
    session: AsyncSession,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    details: dict | None = None,
    source: str = "api",
) -> AuditLog:
    """Append an audit entry (committed together with the owning operation)."""
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details,
        source=source,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_logs(
    session: AsyncSession,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Return (entries_with_actor_name, total)."""
    stmt = select(AuditLog, User.first_name, User.last_name, User.username).outerjoin(
        User, AuditLog.actor_user_id == User.id
    )
    count_stmt = select(func.count()).select_from(AuditLog)

    filters = []
    if action:
        filters.append(AuditLog.action.like(f"{action}%"))
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if actor_id:
        filters.append(AuditLog.actor_user_id == actor_id)
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    total = await session.scalar(count_stmt) or 0
    rows = (
        await session.execute(
            stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    items = []
    for entry, first, last, username in rows:
        actor_name = None
        if first or last:
            actor_name = " ".join(p for p in (first, last) if p)
        elif username:
            actor_name = f"@{username}"
        elif entry.actor_user_id:
            actor_name = f"user#{entry.actor_user_id}"
        items.append(
            {
                "id": entry.id,
                "actor_id": entry.actor_user_id,
                "actor_name": actor_name or "system",
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "details": entry.details,
                "source": entry.source,
                "created_at": entry.created_at,
            }
        )
    return items, total
