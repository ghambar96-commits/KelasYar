"""Points / point-rules schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .common import ORMModel

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,48}$")


class PointRules(BaseModel):
    """Runtime-editable point rules.

    `actions` maps a reason key -> point value. Existing keys can be changed
    and NEW keys can be introduced without any code change.
    """

    enabled: bool = True
    actions: dict[str, int] = Field(default_factory=dict)

    @field_validator("actions")
    @classmethod
    def _validate_actions(cls, value: dict[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        for key, amount in value.items():
            if not _KEY_RE.match(key):
                raise ValueError(f"کلید نامعتبر: {key!r} (باید حروف کوچک انگلیسی/زیرخط باشد)")
            amount = int(amount)
            if not 0 <= amount <= 1000:
                raise ValueError(f"مقدار {key} باید بین ۰ تا ۱۰۰۰ باشد")
            cleaned[key] = amount
        return cleaned


class AdjustPointsIn(BaseModel):
    amount: int
    note: str | None = Field(default=None, max_length=255)

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: int) -> int:
        if value == 0:
            raise ValueError("amount نمی‌تواند صفر باشد")
        if abs(value) > 10000:
            raise ValueError("amount باید بین -۱۰۰۰۰ و ۱۰۰۰۰ باشد")
        return value


class PointTransactionOut(ORMModel):
    id: int
    amount: int
    reason: str
    description: str | None = None
    created_at: datetime
