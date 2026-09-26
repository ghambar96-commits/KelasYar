"""Ranking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models import User
from app.schemas.ranking import MyRankingOut, RankingEntry
from app.services import points_service

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("", response_model=list[RankingEntry], summary="جدول رتبه‌بندی")
async def ranking(
    limit: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entries = await points_service.ranking(session, limit=limit)
    return [
        RankingEntry(
            rank=e["rank"],
            user_id=e["user"].id,
            display_name=e["user"].display_name,
            username=e["user"].username,
            points=e["user"].points,
            activities=e["activities"],
        )
        for e in entries
    ]


@router.get("/me", response_model=MyRankingOut, summary="رتبه و آمار من")
async def my_ranking(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await points_service.my_rank(session, user)
