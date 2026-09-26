"""Tokens & secrets helpers.

- JWT access tokens for the REST API (sub = numeric user id).
- One-time pairing codes issued by the Telegram bot.
- Hashed API keys for machine clients (future Admin Panel backend).

The JWT carries the role only as metadata – on every request the role is
re-read from the database, so bans / role changes take effect immediately.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import get_settings

# Unambiguous alphabet (no 0/O/1/I) for pairing codes.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_auth_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def generate_api_key() -> tuple[str, str, str]:
    """Return (raw_key, prefix, sha256_hash). The hash is what we store."""
    raw = "cb_" + secrets.token_hex(24)
    return raw, raw[:11], hash_api_key(raw)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,  # informational only – DB is authoritative
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_expire_days),
        "jti": secrets.token_hex(8),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    """Return the user id encoded in the token, or None if invalid/expired."""
    settings = get_settings()
    try:
        payload = pyjwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return int(payload["sub"])
    except (pyjwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def generate_jwt_secret() -> str:  # handy for docs/scripts
    return secrets.token_urlsafe(48)
