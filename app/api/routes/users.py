"""Current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models import User
from app.schemas.points import PointTransactionOut
from app.schemas.user import UserOut
from app.services import points_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut, summary="پروفایل من")
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/me/points", summary="امتیاز، رتبه و تاریخچه امتیازهای من")
async def my_points(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rank = await points_service.my_rank(session, user)
    history = await points_service.user_history(session, user, limit=20)
    return {
        "points": user.points,
        "streak_count": user.streak_count,
        "rank": rank["rank"],
        "total_users": rank["total_users"],
        "activities": rank["activities"],
        "history": [PointTransactionOut.model_validate(tx) for tx in history],
    }
