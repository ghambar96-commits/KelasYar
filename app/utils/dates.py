"""Date parsing & formatting for Iranian users.

- Accepts "امروز / فردا / دیروز", Gregorian ISO dates (2025-09-23) and
  Jalali dates (1404-07-01) with `-` or `/` separators, Persian or ASCII digits.
- Renders dates as Jalali with Persian digits + weekday name.
"""

from __future__ import annotations

from datetime import date, timedelta

try:  # jdatetime is a hard dependency, but degrade gracefully if missing
    import jdatetime
    HAS_JDATETIME = True
except ImportError:  # pragma: no cover
    jdatetime = None
    HAS_JDATETIME = False

from app.utils.time import today_local

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_TO_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

WEEKDAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]

# Jalali weekday() -> 0 = Saturday (jdatetime convention matches WEEKDAYS_FA)


def fa_num(value) -> str:
    """Convert numbers/strings to Persian digits for display."""
    return str(value).translate(_FA_DIGITS)


def normalize_digits(text: str) -> str:
    """Convert Persian/Arabic digits to ASCII for parsing."""
    return text.translate(_TO_ASCII)


def _weekday_fa(d: date) -> str:
    if HAS_JDATETIME:
        return WEEKDAYS_FA[jdatetime.date.fromgregorian(date=d).weekday()]
    return ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"][d.weekday()]


def fmt_date(d: date | None) -> str:
    """e.g. 1404-07-01 -> '۱۴۰۴/۰۷/۰۱ (یکشنبه)' (falls back to ISO)."""
    if d is None:
        return "—"
    if HAS_JDATETIME:
        jd = jdatetime.date.fromgregorian(date=d)
        return f"{fa_num(jd.strftime('%Y/%m/%d'))} ({_weekday_fa(d)})"
    return d.isoformat()


def fmt_date_short(d: date | None) -> str:
    if d is None:
        return "—"
    if HAS_JDATETIME:
        return fa_num(jdatetime.date.fromgregorian(date=d).strftime("%Y/%m/%d"))
    return d.isoformat()


def parse_flexible_date(text: str | None) -> date | None:
    """Parse user-supplied date text; returns None when unparseable.

    Accepted forms (Persian or ASCII digits):
      امروز / امروز / فردا / دیروز / ديروز
      2025-09-23 | 2025/09/23 | 2025.09.23   (Gregorian)
      1404-07-01 | 1404/07/01                (Jalali – auto-detected by year)
    """
    if not text:
        return None

    raw = normalize_digits(text.strip()).lower()
    keywords = {
        "امروز": today_local(),
        "today": today_local(),
        "فردا": today_local() + timedelta(days=1),
        "tomorrow": today_local() + timedelta(days=1),
        "دیروز": today_local() - timedelta(days=1),
        "ديروز": today_local() - timedelta(days=1),
        "yesterday": today_local() - timedelta(days=1),
    }
    if raw in keywords:
        return keywords[raw]

    normalized = raw.replace("/", "-").replace(".", "-")
    parts = [p for p in normalized.split("-") if p]
    if len(parts) != 3:
        return None

    try:
        y, m, d = (int(p) for p in parts)
    except ValueError:
        return None

    # Jalali years are 1300..1500 – convert to Gregorian.
    if 1300 <= y <= 1500:
        if not HAS_JDATETIME:  # pragma: no cover
            return None
        try:
            return jdatetime.date(y, m, d).togregorian()
        except ValueError:
            return None

    try:
        result = date(y, m, d)
    except ValueError:
        return None

    # Sanity window for a school agenda.
    if not (2000 <= y <= 2100):
        return None
    return result
