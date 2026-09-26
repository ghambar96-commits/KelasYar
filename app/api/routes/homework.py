"""Homework endpoints.

Read access: every authenticated user (USER included).
Write access: CONTRIBUTOR and above (RBAC enforced by dependencies AND
double-checked inside the service layer – defense in depth).
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_contributor
from app.config import get_settings
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.database import get_session
from app.models import User
from app.schemas.common import Page
from app.schemas.homework import (
    AttachmentOut,
    HomeworkCreate,
    HomeworkOut,
    HomeworkUpdate,
    SubjectOut,
)
from app.services import homework_service, points_service
from app.utils.files import sanitize_filename

logger = get_logger("api.homework")

router = APIRouter(prefix="/homework", tags=["homework"])

MAX_FILES_PER_REQUEST = 10


def _page_kwargs(page: int, page_size: int) -> dict:
    return {"page": page, "page_size": page_size}


async def _serialize_page(items, total: int, page: int, page_size: int) -> Page[HomeworkOut]:
    return Page[HomeworkOut].build(
        [HomeworkOut.from_homework(hw) for hw in items], total, page, page_size
    )


# ------------------------------------------------------------------ reads
@router.get("/today", response_model=Page[HomeworkOut], summary="تکالیف امروز")
async def homework_today(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await homework_service.today(session, page=1, page_size=50)
    response = await _serialize_page(items, total, 1, 50)

    # gamification side-effect (never fails the read itself)
    try:
        await points_service.award_view_homework(session, user)
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("failed to award view points")
        await session.rollback()
    return response


@router.get("/upcoming", response_model=Page[HomeworkOut], summary="تکالیف روزهای آینده")
async def homework_upcoming(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await homework_service.upcoming(session, **_page_kwargs(page, page_size))
    return await _serialize_page(items, total, page, page_size)


@router.get("/past", response_model=Page[HomeworkOut], summary="تکالیف روزهای گذشته")
async def homework_past(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await homework_service.past(session, **_page_kwargs(page, page_size))
    return await _serialize_page(items, total, page, page_size)


@router.get("/subjects", response_model=list[SubjectOut], summary="فهرست درس‌ها")
async def list_subjects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await homework_service.subjects(session)


@router.get("", response_model=Page[HomeworkOut], summary="فهرست تکالیف با فیلتر")
async def list_homework(
    date: date_type | None = Query(None, description="YYYY-MM-DD"),
    date_from: date_type | None = Query(None),
    date_to: date_type | None = Query(None),
    subject: str | None = Query(None, max_length=100),
    q: str | None = Query(None, max_length=100, description="جستجو در عنوان/توضیحات/درس"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    items, total = await homework_service.list_homework(
        session,
        date=date,
        date_from=date_from,
        date_to=date_to,
        subject=subject,
        q=q,
        order=order,
        **_page_kwargs(page, page_size),
    )
    return await _serialize_page(items, total, page, page_size)


@router.get("/{homework_id}", response_model=HomeworkOut, summary="جزئیات یک تکلیف")
async def get_homework(
    homework_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    hw = await homework_service.get(session, homework_id)
    return HomeworkOut.from_homework(hw)


# ----------------------------------------------------------------- writes
@router.post(
    "",
    response_model=HomeworkOut,
    status_code=status.HTTP_201_CREATED,
    summary="ثبت تکلیف جدید (نیازمند نقش CONTRIBUTOR+)",
)
async def create_homework(
    body: HomeworkCreate,
    user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_session),
):
    hw = await homework_service.create(session, body, user, source="api")
    return HomeworkOut.from_homework(hw)


@router.post(
    "/{homework_id}/attachments",
    response_model=list[AttachmentOut],
    status_code=status.HTTP_201_CREATED,
    summary="افزودن پیوست (فایل/عکس) به تکلیف (CONTRIBUTOR+)",
)
async def upload_attachments(
    homework_id: int,
    files: list[UploadFile] = File(..., description="یک یا چند فایل"),
    user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_session),
):
    if len(files) > MAX_FILES_PER_REQUEST:
        raise BadRequestError(f"حداکثر {MAX_FILES_PER_REQUEST} فایل در هر درخواست.")
    saved = []
    for upload in files:
        saved.append(await store_upload(session, homework_id, user, upload))
    return [AttachmentOut.from_attachment(a) for a in saved]


@router.put(
    "/{homework_id}",
    response_model=HomeworkOut,
    summary="ویرایش تکلیف (CONTRIBUTOR+)",
)
async def update_homework(
    homework_id: int,
    body: HomeworkUpdate,
    user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_session),
):
    hw = await homework_service.update(session, homework_id, body, user, source="api")
    return HomeworkOut.from_homework(hw)


@router.delete(
    "/{homework_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="حذف تکلیف (CONTRIBUTOR+)",
)
async def delete_homework(
    homework_id: int,
    user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_session),
):
    await homework_service.delete(session, homework_id, user, source="api")


# ------------------------------------------------------------------ helper
async def store_upload(
    session: AsyncSession, homework_id: int, actor: User, upload: UploadFile
) -> object:
    """Stream an UploadFile to disk (size-capped) and register it in the DB."""
    settings = get_settings()
    hw = await homework_service.get(session, homework_id)  # ensures it exists

    safe_name = sanitize_filename(upload.filename, fallback="file")
    stored_name = f"{uuid4().hex[:8]}_{safe_name}"
    dest_dir = Path(settings.upload_dir) / str(hw.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / stored_name

    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise BadRequestError(
                        f"حجم فایل «{safe_name}» بیشتر از {settings.max_upload_mb} مگابایت است."
                    )
                out.write(chunk)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    rel_path = str(dest.relative_to(Path(settings.upload_dir)))
    return await homework_service.add_attachment(
        session,
        hw.id,
        actor,
        file_name=safe_name,
        file_path=rel_path,
        mime_type=upload.content_type,
        file_size=size,
        source="api",
    )
