"""FastAPI application factory.

Single process runs BOTH the REST API and (optionally) the Telegram bot
polling loop on one asyncio event loop – they share the same service layer
and database.  They can also run as separate processes (see run.py flags).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.router import api_router
from app.api.routes.meta import router as meta_router
from app.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.rate_limit import RateLimitMiddleware
from app.database import AsyncSessionLocal, engine
from app.models import Base
from app.services import settings_service

settings = get_settings()
logger = logging.getLogger("kelasyar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.jwt_secret.strip():
        raise RuntimeError(
            "JWT_SECRET تنظیم نشده است. فایل .env.example را به .env کپی کرده و یک مقدار قوی بگذارید."
        )

    # dev convenience (production uses `alembic upgrade head`)
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # seed default settings (idempotent)
    async with AsyncSessionLocal() as session:
        await settings_service.ensure_defaults(session)

    for warning in settings.runtime_warnings():
        logger.warning(warning)

    # ---- Telegram bot (same event loop as the API) ------------------------
    bot_task: asyncio.Task | None = None
    if settings.bot_enabled_effective:
        from app.bot.bot import run_bot_forever

        bot_task = asyncio.create_task(run_bot_forever(), name="telegram-bot")
        logger.info("Telegram bot polling task started.")
    else:
        logger.warning("Bot disabled (no token or BOT_ENABLED=false) – running in API-only mode.")

    yield

    if bot_task is not None:
        bot_task.cancel()
        with suppress(asyncio.CancelledError):
            await bot_task
    await engine.dispose()
    logger.info("shutdown complete.")


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=(
            "API مدیریت تکالیف کلاس – مشترک بین ربات تلگرام، پنل مدیریت وب "
            "و کلاینت‌های موبایل.\n\n"
            "**احراز هویت:** کد یک‌بارمصرف را از ربات بگیرید (دستور /api) و در "
            "`POST /api/auth/exchange` به JWT تبدیل کنید."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS first (so the rate limiter wraps it and stays outermost),
    # CORS preflights are exempt from rate limiting inside the middleware.
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "detail": exc.message},
        )

    app.include_router(meta_router)  # "/" and "/health"
    app.include_router(api_router, prefix="/api")

    @app.get("/admin", include_in_schema=False)
    async def admin_panel():
        """Minimal built-in web admin panel (talks to the same REST API)."""
        return FileResponse(
            Path(__file__).parent / "static" / "admin.html",
            media_type="text/html",
        )

    return app


app = create_app()
