"""Common commands: /start /menu /help /api /cancel."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts as T
from app.config import get_settings
from app.models import User
from app.services import auth_service, settings_service

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, session: AsyncSession, state: FSMContext):
    await state.clear()
    class_name = await settings_service.get_class_name(session)
    await message.answer(
        T.welcome(user, class_name),
        reply_markup=keyboards.main_menu(user.role),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, user: User, state: FSMContext):
    await state.clear()
    await message.answer("منوی اصلی 👇", reply_markup=keyboards.main_menu(user.role))


@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    await message.answer(T.help_text(user))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, user: User, state: FSMContext):
    await state.clear()
    await message.answer(T.CANCELLED, reply_markup=keyboards.main_menu(user.role))


@router.message(Command("api"))
async def cmd_api(message: Message, user: User, session: AsyncSession):
    code = await auth_service.issue_auth_code(session, user)
    settings = get_settings()
    await message.answer(T.auth_code_text(code, settings.auth_code_ttl_minutes))
