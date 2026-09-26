"""Time helpers – all timestamps are stored in naive UTC."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def now_utc() -> datetime:
    """Current UTC time as a naive datetime (DB convention of this project)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def today_local() -> date:
    """"Today" according to the configured school timezone, not the server clock."""
    return datetime.now(local_tz()).date()


def utc_day_start_for_local_today() -> datetime:
    """UTC timestamp of the local midnight – used for once-per-day point rules."""
    now_local = datetime.now(local_tz())
    local_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def yesterday_local() -> date:
    return today_local() - timedelta(days=1)
