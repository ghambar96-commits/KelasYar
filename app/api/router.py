"""API router aggregation – everything lives under /api."""

from fastapi import APIRouter

from app.api.routes import admin, auth, homework, attachments, meta, points, ranking, users

api_router = APIRouter()
api_router.include_router(meta.api_router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(homework.router)
api_router.include_router(attachments.router)
api_router.include_router(ranking.router)
api_router.include_router(points.router)
api_router.include_router(admin.router)
