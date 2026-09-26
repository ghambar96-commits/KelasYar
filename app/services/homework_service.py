"""Homework service – CRUD + listing/scoping by date.

Contributors and SUPER_ADMINs may write; everyone may read.  All mutating
operations write an audit entry and award points according to the
runtime-editable rules stored in the settings table.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.models import Attachment, Homework, User
from app.schemas.homework import HomeworkCreate, HomeworkUpdate
from app.services import audit_service, points_service
from app.utils.time import now_utc, today_local

logger = get_logger("homework")


# --------------------------------------------------------------------- read
async def get(session: AsyncSession, homework_id: int, *, include_deleted: bool = False) -> Homework:
    hw = await session.get(Homework, homework_id)
    if hw is None or (hw.is_deleted and not include_deleted):
        raise NotFoundError("تکلیف مورد نظر یافت نشد.")
    return hw


async def list_homework(
    session: AsyncSession,
    *,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    subject: str | None = None,
    q: str | None = None,
    order: str = "desc",
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Homework], int]:
    stmt = select(Homework).where(Homework.deleted_at.is_(None))
    count_stmt = select(func.count()).select_from(Homework).where(Homework.deleted_at.is_(None))

    filters = []
    if date is not None:
        filters.append(Homework.homework_date == date)
    if date_from is not None:
        filters.append(Homework.homework_date >= date_from)
    if date_to is not None:
        filters.append(Homework.homework_date <= date_to)
    if subject:
        filters.append(func.lower(Homework.subject) == subject.strip().lower())
    if q:
        needle = f"%{q.strip().lower()}%"
        filters.append(
            or_(
                func.lower(Homework.title).like(needle),
                func.lower(Homework.description).like(needle),
                func.lower(Homework.subject).like(needle),
            )
        )
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    direction = Homework.homework_date.asc() if order == "asc" else Homework.homework_date.desc()
    stmt = stmt.order_by(direction, Homework.id.desc() if order != "asc" else Homework.id)

    total = await session.scalar(count_stmt) or 0
    items = (
        (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size)))
        .scalars()
        .unique()
        .all()
    )
    return list(items), total


async def today(session: AsyncSession, **kwargs) -> tuple[list[Homework], int]:
    return await list_homework(session, date=today_local(), order="asc", **kwargs)


async def upcoming(session: AsyncSession, **kwargs) -> tuple[list[Homework], int]:
    return await list_homework(
        session, date_from=today_local() + timedelta(days=1), order="asc", **kwargs
    )


async def past(session: AsyncSession, **kwargs) -> tuple[list[Homework], int]:
    return await list_homework(session, date_to=today_local() - __import__("datetime").timedelta(days=1), **kwargs)


async def subjects(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(Homework.subject, func.count())
            .where(Homework.deleted_at.is_(None))
            .group_by(Homework.subject)
            .order_by(func.count().desc())
        )
    ).all()
    return [{"subject": s, "count": c} for s, c in rows]


# -------------------------------------------------------------------- write
async def create(session: AsyncSession, data: HomeworkCreate, actor: User,
                 source: str = "api") -> Homework:
    hw = Homework(
        title=data.title.strip(),
        description=(data.description or "").strip() or None,
        subject=data.subject.strip(),
        homework_date=data.homework_date,
        due_date=data.due_date,
        created_by=actor.id,
        updated_by=actor.id,
    )
    session.add(hw)
    await session.flush()

    await audit_service.log(
        session, actor, "homework.create", "homework", hw.id,
        {"title": hw.title, "subject": hw.subject, "date": hw.homework_date.isoformat()},
        source=source,
    )
    await points_service.award(session, actor, "create_homework",
                               meta={"homework_id": hw.id})
    await session.commit()
    await session.refresh(hw)
    logger.info("homework #%s created by %s (%s)", hw.id, actor.id, source)
    return hw


async def update(session: AsyncSession, homework_id: int, data: HomeworkUpdate,
                 actor: User, source: str = "api") -> Homework:
    hw = await get(session, homework_id)

    changes: dict = {}
    for field in ("title", "description", "subject", "homework_date", "due_date"):
        value = getattr(data, field)
        if value is not None and value != getattr(hw, field):
            changes[field] = {"from": str(getattr(hw, field)), "to": str(value)}
            setattr(hw, field, value if field not in ("title", "subject") else value.strip())

    if not changes:
        raise BadRequestError("هیچ فیلدی برای ویرایش ارسال نشده است.")

    # cross-field validation (due_date can't precede homework_date)
    if hw.due_date is not None and hw.due_date < hw.homework_date:
        raise BadRequestError("مهلت انجام نمی‌تواند قبل از تاریخ تکلیف باشد.")

    hw.updated_by = actor.id
    await audit_service.log(
        session, actor, "homework.update", "homework", hw.id, {"changes": changes}, source=source
    )
    await points_service.award(session, actor, "edit_homework",
                               meta={"homework_id": hw.id, "fields": list(changes)})
    await session.commit()
    await session.refresh(hw)
    logger.info("homework #%s updated by %s: %s", hw.id, actor.id, list(changes))
    return hw


async def delete(session: AsyncSession, homework_id: int, actor: User,
                 source: str = "api") -> None:
    hw = await get(session, homework_id)
    hw.deleted_at = now_utc()
    hw.deleted_by = actor.id
    await audit_service.log(
        session, actor, "homework.delete", "homework", hw.id,
        {"title": hw.title, "subject": hw.subject}, source=source,
    )
    await session.commit()
    logger.info("homework #%s deleted by %s", hw.id, actor.id)


# --------------------------------------------------------------- attachments
async def add_attachment(
    session: AsyncSession,
    homework_id: int,
    actor: User,
    *,
    file_name: str,
    file_path: str,
    mime_type: str | None,
    file_size: int,
    telegram_file_id: str | None = None,
    source: str = "api",
) -> Attachment:
    hw = await get(session, homework_id)
    attachment = Attachment(
        homework_id=hw.id,
        file_name=file_name,
        file_path=file_path,
        mime_type=mime_type,
        file_size=file_size,
        telegram_file_id=telegram_file_id,
        created_by=actor.id,
    )
    session.add(attachment)
    await session.flush()
    await audit_service.log(
        session, actor, "homework.attachment_add", "homework", hw.id,
        {"attachment_id": attachment.id, "file_name": file_name}, source=source,
    )
    await points_service.award(session, actor, "add_attachment",
                               meta={"homework_id": hw.id, "attachment_id": attachment.id})
    await session.commit()
    return attachment


async def get_attachment(session: AsyncSession, attachment_id: int) -> Attachment:
    att = await session.get(Attachment, attachment_id)
    if att is None or att.homework is None or att.homework.is_deleted:
        raise NotFoundError("پیوست مورد نظر یافت نشد.")
    return att


async def delete_attachment(session: AsyncSession, attachment_id: int, actor: User,
                            source: str = "api") -> None:
    att = await get_attachment(session, attachment_id)
    await audit_service.log(
        session, actor, "homework.attachment_delete", "homework", att.homework_id,
        {"attachment_id": att.id, "file_name": att.file_name}, source=source,
    )
    await session.delete(att)
    await session.commit()
