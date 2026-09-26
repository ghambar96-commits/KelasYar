"""Ranking & personal points handlers."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts as T
from app.models import User
from app.services import points_service

router = Router(name="ranking")


@router.message(F.text == T.BTN_RANKING)
async def btn_ranking(message: Message, user: User, session: AsyncSession):
    entries = await points_service.ranking(session, limit=10)
    await message.answer(T.render_ranking(entries))


@router.message(F.text == T.BTN_MY_POINTS)
async def btn_my_points(message: Message, user: User, session: AsyncSession):
    info = await points_service.my_rank(session, user)
    history = await points_service.user_history(session, user, limit=5)
    await message.answer(T.render_my_points(user, info, history))
