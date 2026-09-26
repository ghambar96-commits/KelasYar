"""File helpers for attachment handling."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# characters that are safe to keep in a stored filename
_UNSAFE = re.compile(r"[^\w\.\-\u0600-\u06FF ]+", flags=re.UNICODE)


def sanitize_filename(name: str | None, fallback: str = "file") -> str:
    """Return a filesystem-safe filename (path separators & control chars removed)."""
    if not name:
        return fallback
    name = unicodedata.normalize("NFKC", str(name)).replace("\\", "_").replace("/", "_")
    name = _UNSAFE.sub("_", name).strip("._ ")
    return name[:120] or fallback


def human_size(num_bytes: int) -> str:
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
