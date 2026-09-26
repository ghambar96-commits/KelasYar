"""Homework viewing handlers – available to every (non-banned) user."""

from __future__ import annotations

import math
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts as T
from app.bot.filters import is_plain_text
from app.config import get_settings
from app.core.logging import get_logger
from app.models import User
from app.services import homework_service, points_service
from app.utils.dates import fa_num

logger = get_logger("bot.view")

router = Router(name="view")

PAGE_SIZE = 6

SCOPE_FUNCS = {
    "today": homework_service.today,
    "upcoming": homework_service.upcoming,
    "past": homework_service.past,
}


async def _render_scope(
    session: AsyncSession, user: User, scope: str, page: int = 0
) -> tuple[str, InlineKeyboardMarkup | None]:
    items, total = await SCOPE_FUNCS[scope](session, page=page + 1, page_size=PAGE_SIZE)
    pages = max(1, math.ceil(total / PAGE_SIZE))

    if not items:
        return T.NO_HOMEWORK, None

    text = T.render_hw_list(T.SCOPE_FA[scope], items, page * PAGE_SIZE, total)
    kb_rows: list[list[InlineKeyboardButton]] = []

    # attachment buttons for every displayed homework
    for hw in items:
        for att in hw.attachments[:4]:
            kb_rows.append(
                [InlineKeyboardButton(text=f"📎 {att.file_name[:38]}", callback_data=f"hwatt:{att.id}")]
            )
    nav = keyboards.pagination_row(f"hwpage:{scope}", page, pages)
    if nav:
        kb_rows.append(nav)

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None

    # gamification: viewing today's homework counts as the daily activity
    if scope == "today":
        try:
            await points_service.award_view_homework(session, user)
        except Exception:  # noqa: BLE001
            logger.exception("points award failed")
    return text, kb


async def _show(message_or_cb, session, user, scope):
    text, kb = await _render_scope(session, user, scope)
    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(text, reply_markup=kb)
    else:
        cb: CallbackQuery = message_or_cb
        try:
            await cb.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            await cb.message.answer(text, reply_markup=kb)  # type: ignore[union-attr]
        await cb.answer()


@router.message(F.text == T.BTN_TODAY)
async def btn_today(message: Message, user: User, session: AsyncSession):
    await _show(message, session, user, "today")


@router.message(F.text == T.BTN_UPCOMING)
async def btn_upcoming(message: Message, user: User, session: AsyncSession):
    await _show(message, session, user, "upcoming")


@router.message(F.text == T.BTN_PAST)
async def btn_past(message: Message, user: User, session: AsyncSession):
    await _show(message, session, user, "past")


@router.callback_query(F.data.startswith("hwpage:"))
async def cb_page(cb: CallbackQuery, user: User, session: AsyncSession):
    _, scope, page = cb.data.split(":")
    page = max(0, int(page))
    text, kb = await _render_scope(session, user, scope, page)
    try:
        await cb.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("hwatt:"))
async def cb_send_attachment(cb: CallbackQuery, user: User, session: AsyncSession, bot: Bot):
    att_id = int(cb.data.split(":")[1])
    try:
        att = await homework_service.get_attachment(session, att_id)
    except Exception:  # noqa: BLE001
        await cb.answer(T.EXPIRED, show_alert=True)
        return
    await cb.answer("در حال ارسال فایل…")

    settings = get_settings()
    path = Path(settings.upload_dir) / att.file_path
    caption = f"📎 {att.file_name} (تکلیف #{fa_num(att.homework_id)})"
    try:
        if att.telegram_file_id:
            await bot.send_document(cb.from_user.id, att.telegram_file_id, caption=caption)
        elif path.is_file():
            from aiogram.types import FSInputFile

            await bot.send_document(cb.from_user.id, FSInputFile(path), caption=caption)
        else:
            await cb.message.answer("⚠️ فایل یافت نشد.")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        logger.exception("failed to send attachment %s", att_id)


# ---------------------------------------------------------------- fallbacks
@router.message()
async def fallback(message: Message, user: User):
    if is_plain_text(message) or message.text:
        await message.answer(T.UNKNOWN)
