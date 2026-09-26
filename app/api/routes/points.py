"""Point-rules endpoints (view: everyone, change: SUPER_ADMIN)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_super_admin
from app.database import get_session
from app.models import User
from app.schemas.points import PointRules
from app.services import points_service

router = APIRouter(prefix="/points", tags=["points"])


@router.get("/rules", response_model=PointRules, summary="قوانین فعلی امتیازدهی")
async def get_rules(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await points_service.get_rules(session)


@router.put(
    "/rules",
    response_model=PointRules,
    summary="تغییر قوانین امتیازدهی (فقط SUPER_ADMIN)",
)
async def put_rules(
    body: PointRules,
    user: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_session),
):
    return await points_service.set_rules(
        session, body.model_dump(), actor=user, source="api"
    )
