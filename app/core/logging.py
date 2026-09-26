"""Central logging configuration."""

from __future__ import annotations

import logging

from app.config import get_settings

FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=FMT, force=True)

    # Quieten noisy third-party loggers, keep our own at the configured level.
    for name, lvl in (
        ("aiogram.event", logging.WARNING),
        ("aiosqlite", logging.WARNING),
        ("sqlalchemy.engine", logging.WARNING),
        ("uvicorn.access", logging.INFO),
    ):
        logging.getLogger(name).setLevel(lvl)

    logging.getLogger("kelasyar").setLevel(level)


def get_logger(name: str = "kelasyar") -> logging.Logger:
    return logging.getLogger(f"kelasyar.{name}")
