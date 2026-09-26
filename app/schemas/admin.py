"""Admin-facing schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .common import ORMModel

AssignableRole = Literal["USER", "CONTRIBUTOR"]  # SUPER_ADMIN is env-bootstrap only!


class RoleUpdateIn(BaseModel):
    role: AssignableRole


class BanIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ApiKeyOut(ORMModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None = None
    created_at: datetime


class ApiKeyCreatedOut(ApiKeyOut):
    key: str  # raw key – shown exactly ONCE at creation


class SettingOut(ORMModel):
    key: str
    value: Any
    description: str | None = None
    updated_at: datetime


class SettingUpdateIn(BaseModel):
    value: Any


class AuditLogOut(ORMModel):
    id: int
    actor_id: int | None = None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    details: dict | None = None
    source: str
    created_at: datetime
