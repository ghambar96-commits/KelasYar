"""Attachment download/delete endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_contributor
from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.database import get_session
from app.models import User
from app.services import homework_service

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}/file", summary="دانلود فایل پیوست (احراز هویت لازم)")
async def download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    att = await homework_service.get_attachment(session, attachment_id)

    settings = get_settings()
    base = Path(settings.upload_dir).resolve()
    path = (base / att.file_path).resolve()
    # defense-in-depth: never serve anything outside UPLOAD_DIR
    if not str(path).startswith(str(base)) or not path.is_file():
        raise NotFoundError("فایل روی سرور یافت نشد.")

    return FileResponse(
        path,
        filename=att.file_name,
        media_type=att.mime_type or "application/octet-stream",
    )


@router.delete(
    "/{attachment_id}",
    status_code=204,
    summary="حذف پیوست (CONTRIBUTOR+)",
)
async def delete_attachment(
    attachment_id: int,
    user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_session),
):
    await homework_service.delete_attachment(session, attachment_id, user, source="api")
