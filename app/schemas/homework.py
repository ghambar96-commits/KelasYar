"""Homework & attachment schemas (input validation + output shapes)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class HomeworkBase(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="عنوان/متن تکلیف")
    description: str | None = Field(default=None, max_length=4000)
    subject: str = Field(min_length=1, max_length=100, description="نام درس")
    homework_date: date = Field(description="تاریخ تکلیف (میلادی ISO)")
    due_date: date | None = Field(default=None, description="مهلت انجام (اختیاری)")

    @model_validator(mode="after")
    def _dates_are_consistent(self):
        if self.due_date is not None and self.due_date < self.homework_date:
            raise ValueError("due_date نمی‌تواند قبل از homework_date باشد.")
        return self


class HomeworkCreate(HomeworkBase):
    pass


class HomeworkUpdate(BaseModel):
    """Partial update – only provided fields change (description='' clears it)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    subject: str | None = Field(default=None, min_length=1, max_length=100)
    homework_date: date | None = None
    due_date: date | None = None


class AttachmentOut(ORMModel):
    id: int
    homework_id: int
    file_name: str
    mime_type: str | None = None
    file_size: int
    telegram_available: bool = False
    url: str = ""

    @classmethod
    def from_attachment(cls, att) -> "AttachmentOut":
        return cls(
            id=att.id,
            homework_id=att.homework_id,
            file_name=att.file_name,
            mime_type=att.mime_type,
            file_size=att.file_size,
            telegram_available=bool(att.telegram_file_id),
            url=f"/api/attachments/{att.id}/file",
        )


class HomeworkOut(ORMModel):
    id: int
    title: str
    description: str | None = None
    subject: str
    homework_date: date
    due_date: date | None = None
    author_id: int
    author_name: str
    attachments: list[AttachmentOut] = []
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_homework(cls, hw) -> "HomeworkOut":
        return cls(
            id=hw.id,
            title=hw.title,
            description=hw.description,
            subject=hw.subject,
            homework_date=hw.homework_date,
            due_date=hw.due_date,
            author_id=hw.created_by,
            author_name=hw.author_name,
            attachments=[AttachmentOut.from_attachment(a) for a in hw.attachments],
            created_at=hw.created_at,
            updated_at=hw.updated_at,
        )


class SubjectOut(BaseModel):
    subject: str
    count: int
