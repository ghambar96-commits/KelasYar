"""Roles & role hierarchy used across the whole project."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    USER = "USER"
    CONTRIBUTOR = "CONTRIBUTOR"
    SUPER_ADMIN = "SUPER_ADMIN"


ROLE_LEVEL: dict[Role, int] = {
    Role.USER: 1,
    Role.CONTRIBUTOR: 2,
    Role.SUPER_ADMIN: 3,
}


def role_at_least(role: Role, minimum: Role) -> bool:
    return ROLE_LEVEL[role] >= ROLE_LEVEL[minimum]
