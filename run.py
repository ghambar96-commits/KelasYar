#!/usr/bin/env python3
"""KelasYar launcher.

Usage:
    python run.py                 # migrations + API + Telegram bot
    python run.py --api-only      # REST API only (bot runs elsewhere / not at all)
    python run.py --bot-only      # only the Telegram bot
    python run.py --no-migrate    # skip `alembic upgrade head`
    python run.py --setup         # only create/patch .env, then exit
    python run.py --port 9000     # custom API port
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path


def bootstrap_env() -> list[str]:
    """Ensure .env exists and JWT_SECRET is filled (generate a strong random)."""
    notes: list[str] = []
    env_path = Path(".env")
    example = Path(".env.example")

    if not env_path.exists() and example.exists():
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        notes.append("created .env from .env.example")

    if env_path.exists():
        text = env_path.read_text(encoding="utf-8")
        changed = False
        if 'JWT_SECRET=""' in text:
            text = text.replace('JWT_SECRET=""', f'JWT_SECRET="{secrets.token_urlsafe(48)}"')
            changed = True
        if changed:
            env_path.write_text(text, encoding="utf-8")
            notes.append("generated a random JWT_SECRET")
    return notes


def run_migrations() -> bool:
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        print("[warn] alembic is not installed – skipping migrations")
        return False
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] alembic upgrade failed: {exc}")
        print("       (if the DB is already initialized you can ignore this,")
        print("        or run with --no-migrate)")
        return False


async def _run_bot_only() -> None:
    from app.bot.bot import run_bot_forever

    await run_bot_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="KelasYar – class homework manager")
    parser.add_argument("--api-only", action="store_true", help="run the REST API without the bot")
    parser.add_argument("--bot-only", action="store_true", help="run only the Telegram bot")
    parser.add_argument("--no-migrate", action="store_true", help="skip database migrations")
    parser.add_argument("--setup", action="store_true", help="only create/patch .env and exit")
    parser.add_argument("--host", default=None, help="API host (default: API_HOST env)")
    parser.add_argument("--port", type=int, default=None, help="API port (default: API_PORT env)")
    args = parser.parse_args()

    # Make sure we run from the project root (alembic.ini & .env live there).
    os.chdir(Path(__file__).parent)

    for note in bootstrap_env():
        print(f"[setup] {note}")

    if args.setup:
        print("[setup] done – now edit .env (bot token, SUPER_ADMIN_TELEGRAM_IDS)")
        return 0

    if not args.no_migrate:
        run_migrations()

    if args.bot_only:
        asyncio.run(_run_bot_only())
        return 0

    if args.api_only:
        # actual environment variables take precedence over the .env file
        os.environ["BOT_ENABLED"] = "false"

    import uvicorn

    from app.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
