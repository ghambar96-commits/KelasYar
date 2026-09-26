"""Application settings loaded from environment variables / .env file.

Every secret (bot token, JWT secret, database URL, ...) is read from the
environment – nothing sensitive is ever hard-coded.

List-typed values (SUPER_ADMIN_TELEGRAM_IDS, CORS_ORIGINS) are plain
comma-separated strings, e.g.  "11111111,22222222" (JSON arrays also work).
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_int_list(raw) -> list[int]:
    if isinstance(raw, (list, tuple)):
        return [int(x) for x in raw]
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):  # tolerate a JSON array
        try:
            return [int(x) for x in json.loads(text)]
        except (ValueError, TypeError):
            return []
    result: list[int] = []
    for item in text.split(","):
        item = item.strip()
        if item:
            try:
                result.append(int(item))
            except ValueError:
                continue
    return result


def _parse_str_list(raw) -> list[str]:
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return [str(x).strip() for x in json.loads(text) if str(x).strip()]
        except (ValueError, TypeError):
            return []
    return [item.strip() for item in text.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---------------------------------------------------------
    app_name: str = "KelasYar"
    app_version: str = "1.0.0"
    timezone: str = "Asia/Tehran"
    database_url: str = "sqlite+aiosqlite:///./kelasyar.db"
    upload_dir: str = "uploads"
    max_upload_mb: int = 20
    log_level: str = "INFO"
    auto_create_tables: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Telegram --------------------------------------------------------------
    telegram_bot_token: str = ""
    super_admin_telegram_ids: str = ""   # comma separated numeric IDs
    bot_enabled: bool = True

    # Proxy for networks where Telegram is blocked (e.g. Iran / Hiddify).
    # Empty URL + auto=true  ->  try direct first, then probe common local
    # proxy ports (Hiddify 12334, v2rayN 10808/10809, Clash 7890, ...).
    # Or set explicitly, e.g.  TELEGRAM_PROXY_URL="socks5://127.0.0.1:12334"
    telegram_proxy_url: str = ""
    telegram_proxy_auto: bool = True

    # --- Security ---------------------------------------------------------------
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7
    auth_code_ttl_minutes: int = 10

    # --- Rate limiting -----------------------------------------------------------
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # --- CORS ---------------------------------------------------------------------
    cors_origins: str = ""              # comma separated origins

    # ------------------------------------------------------------------ derived
    @property
    def super_admin_ids(self) -> list[int]:
        return _parse_int_list(self.super_admin_telegram_ids)

    @property
    def cors_origin_list(self) -> list[str]:
        return _parse_str_list(self.cors_origins)

    @property
    def bot_enabled_effective(self) -> bool:
        """Bot runs only when a token is configured and BOT_ENABLED is true."""
        return bool(self.telegram_bot_token.strip()) and self.bot_enabled

    def runtime_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.telegram_bot_token.strip():
            warnings.append(
                "TELEGRAM_BOT_TOKEN is empty – the bot will NOT start (API-only mode)."
            )
        if not self.super_admin_ids:
            warnings.append(
                "SUPER_ADMIN_TELEGRAM_IDS is empty – nobody can administer the system. "
                "Set it to your Telegram numeric ID."
            )
        if not self.jwt_secret.strip():
            warnings.append("JWT_SECRET is empty – the API will refuse to start.")
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
