"""Auth schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .user import UserOut


class AuthExchangeIn(BaseModel):
    """Pairing code obtained from the bot (/api command)."""

    code: str = Field(min_length=4, max_length=32)


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
