"""Meta routes (root info & health)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.utils.time import now_utc

settings = get_settings()

router = APIRouter(tags=["meta"])
api_router = APIRouter(tags=["meta"])


@router.get("/", include_in_schema=False)
async def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "admin_panel": "/admin",
        "health": "/health",
    }


@router.get("/health")
@api_router.get("/health")
async def health():
    return {"status": "ok", "time": now_utc().isoformat(), "version": settings.app_version}
