"""Contributor flows: add homework (FSM), edit & delete homework.

Access: CONTRIBUTOR and above (MinRole filter on every entry point).
"""

from __future__ import annotations

import math
import shutil
import time
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts as T
from app.bot.filters import MinRole, is_plain_text
from app.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models import Role, User
from app.schemas.homework import HomeworkCreate, HomeworkUpdate
from app.services import homework_service
from app.utils.dates import fa_num, fmt_date, parse_flexible_date
from app.utils.files import sanitize_filename

logger = get_logger("bot.manage")

router = Router(name="manage")

MAX_FILES = 5
MANAGE_PAGE_SIZE = 8


class AddHomework(StatesGroup):
    subject = State()
    title = State()
    description = State()
    homework_date = State()
    due_date = State()
    attachments = State()
    confirm = State()


class EditHomework(StatesGroup):
    value = State()


# =========================================================== add flow
@router.message(Command("add_homework"))
@router.message(MinRole(Role.CONTRIBUTOR), F.text == T.BTN_ADD_HW)
async def start_add(message: Message, state: FSMContext, user: User):
    await state.set_state(AddHomework.subject)
    await state.set_data({"files": []})
    await message.answer(
        "➕ <b>ثبت تکلیف جدید</b>\n\n"
        "۱️⃣ نام درس را بنویس (مثلاً: <b>ریاضی</b>)\n\n"
        "برای لغو هر مرحله /cancel را بزن."
    )


@router.message(AddHomework.subject, is_plain_text)
async def add_subject(message: Message, state: FSMContext):
    subject = message.text.strip()[:100]
    await state.update_data(subject=subject)
    await state.set_state(AddHomework.title)
    await message.answer(
        f"📘 درس: <b>{T.esc(subject)}</b>\n\n"
        "۲️⃣ عنوان/متن تکلیف را بنویس.\n"
        "مثال: صفحه ۴۵، سوال‌های ۱ تا ۱۰"
    )


@router.message(AddHomework.title, is_plain_text)
async def add_title(message: Message, state: FSMContext):
    title = message.text.strip()[:200]
    await state.update_data(title=title)
    await state.set_state(AddHomework.description)
    await message.answer(
        "۳️⃣ توضیحات بیشتر داری؟ بنویس؛ نداری <b>/skip</b> را بفرست."
    )


@router.message(AddHomework.description, Command("skip"))
async def add_description_skip(message: Message, state: FSMContext):
    await state.update_data(description=None)
    await _ask_date(state, message)


@router.message(AddHomework.description, is_plain_text)
async def add_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip()[:4000])
    await _ask_date(state, message)


async def _ask_date(state: FSMContext, message: Message):
    await state.set_state(AddHomework.homework_date)
    await message.answer(
        "۴️⃣ تاریخ تکلیف برای چه روزی است؟\n\n"
        "• <b>امروز</b> یا <b>فردا</b> بنویس، یا\n"
        "• تاریخ شمسی مثل <code>1404-07-01</code>\n"
        "• یا میلادی مثل <code>2025-09-23</code>"
    )


@router.message(AddHomework.homework_date, is_plain_text)
async def add_date(message: Message, state: FSMContext):
    parsed = parse_flexible_date(message.text)
    if parsed is None:
        await message.answer("⚠️ تاریخ را متوجه نشدم. مثال‌ها:\nامروز | فردا | 1404-07-01 | 2025-09-23")
        return
    await state.update_data(homework_date=parsed)
    await state.set_state(AddHomework.due_date)
    await message.answer(
        f"🗓 تاریخ: <b>{fmt_date(parsed)}</b>\n\n"
        "۵️⃣ مهلت انجام هم دارد؟ (اختیاری)\n"
        "تاریخ بفرست یا <b>/skip</b> برای بدون مهلت."
    )


@router.message(AddHomework.due_date, Command("skip"))
async def add_due_skip(message: Message, state: FSMContext):
    await state.update_data(due_date=None)
    await _ask_attachments(state, message)


@router.message(AddHomework.due_date, is_plain_text)
async def add_due(message: Message, state: FSMContext):
    parsed = parse_flexible_date(message.text)
    if parsed is None:
        await message.answer("⚠️ تاریخ نامعتبر است؛ دوباره بنویس یا /skip بزن.")
        return
    data = await state.get_data()
    if parsed < data["homework_date"]:
        await message.answer("⚠️ مهلت انجام نمی‌تواند قبل از تاریخ تکلیف باشد. دوباره بفرست یا /skip.")
        return
    await state.update_data(due_date=parsed)
    await _ask_attachments(state, message)


async def _ask_attachments(state: FSMContext, message: Message):
    await state.set_state(AddHomework.attachments)
    await message.answer(
        "۶️⃣ اگر عکس یا فایلی (مثل عکس صفحه کتاب یا جزوه) برای این تکلیف داری همین‌جا بفرست.\n"
        f"می‌توانی تا <b>{fa_num(MAX_FILES)}</b> فایل بفرستی.\n\n"
        "وقتی تمام شد <b>/done</b>، و اگر فایلی نداری <b>/skip</b> را بزن."
    )


@router.message(AddHomework.attachments, F.photo | F.document)
async def add_file(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    files: list[dict] = data.get("files", [])
    if len(files) >= MAX_FILES:
        await message.answer(f"⚠️ حداکثر {fa_num(MAX_FILES)} فایل مجاز است. /done یا /skip را بزن.")
        return

    if message.photo:
        obj, tg_file_id = message.photo[-1], message.photo[-1].file_id
        name, mime = f"photo_{len(files) + 1}.jpg", "image/jpeg"
    else:
        obj, tg_file_id = message.document, message.document.file_id
        name = sanitize_filename(message.document.file_name, f"file_{len(files) + 1}")
        mime = message.document.mime_type

    settings = get_settings()
    inbox = Path(settings.upload_dir) / "_inbox" / f"{message.from_user.id}_{int(time.time())}"
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / f"{uuid4().hex[:6]}_{name}"
    try:
        await bot.download(obj, destination=dest)
    except Exception:  # noqa: BLE001
        logger.exception("file download failed")
        await message.answer("⚠️ دانلود فایل ناموفق بود. دوباره تلاش کن یا /skip بزن.")
        return

    files.append(
        {
            "path": str(dest),
            "name": name,
            "mime": mime,
            "size": dest.stat().st_size if dest.exists() else 0,
            "file_id": tg_file_id,
        }
    )
    await state.update_data(files=files)
    await message.answer(
        f"✅ فایل «{T.esc(name)}» اضافه شد ({fa_num(len(files))}/{fa_num(MAX_FILES)}).\n"
        "فایل دیگری داری؟ بعد از اتمام <b>/done</b> را بزن."
    )


@router.message(AddHomework.attachments, Command("done"))
@router.message(AddHomework.attachments, Command("skip"))
async def finish_files(message: Message, state: FSMContext):
    await _show_preview(state, message)


async def _show_preview(state: FSMContext, message: Message):
    await state.set_state(AddHomework.confirm)
    data = await state.get_data()
    files = data.get("files", [])
    text = (
        "📋 <b>پیش‌نمایش تکلیف</b>\n\n"
        f"📘 درس: {T.esc(data['subject'])}\n"
        f"📝 تکلیف: {T.esc(data['title'])}\n"
    )
    if data.get("description"):
        text += f"📄 توضیحات: {T.esc(data['description'])}\n"
    text += f"🗓 تاریخ: {fmt_date(data['homework_date'])}\n"
    if data.get("due_date"):
        text += f"⏰ مهلت: {fmt_date(data['due_date'])}\n"
    text += f"📎 پیوست: {fa_num(len(files))} فایل\n\n"
    text += "ثبت نهایی شود؟"
    await message.answer(
        text,
        reply_markup=keyboards.confirm_kb("hmsave", "hmabort", yes_text="✅ ثبت نهایی"),
    )


@router.callback_query(AddHomework.confirm, F.data == "hmsave")
async def save_homework(cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    try:
        hw = await homework_service.create(
            session,
            HomeworkCreate(
                title=data["title"],
                description=data.get("description"),
                subject=data["subject"],
                homework_date=data["homework_date"],
                due_date=data.get("due_date"),
            ),
            user,
            source="telegram",
        )
        # move collected files from inbox into the homework folder
        settings = get_settings()
        for f in data.get("files", []):
            src = Path(f["path"])
            if not src.is_file():
                continue
            dest_dir = Path(settings.upload_dir) / str(hw.id)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            shutil.move(str(src), str(dest))
            rel = str(dest.relative_to(Path(settings.upload_dir)))
            await homework_service.add_attachment(
                session,
                hw.id,
                user,
                file_name=f["name"],
                file_path=rel,
                mime_type=f["mime"],
                file_size=f["size"],
                telegram_file_id=f["file_id"],
                source="telegram",
            )
    except AppError as exc:
        await state.clear()
        await cb.message.edit_text(f"⚠️ {T.esc(exc.message)}")  # type: ignore[union-attr]
        await cb.answer()
        return
    finally:
        # clean leftover inbox files on abort too
        inbox_root = Path(get_settings().upload_dir) / "_inbox"
        if inbox_root.is_dir():
            for child in inbox_root.glob(f"{user.id}_*"):
                shutil.rmtree(child, ignore_errors=True)

    await state.clear()
    rules_points = ""
    await cb.message.edit_text(  # type: ignore[union-attr]
        f"✅ تکلیف با شناسه <b>{fa_num(hw.id)}</b> ثبت شد! {rules_points}\n"
        f"⭐ امتیاز فعلی شما: <b>{fa_num(user.points)}</b>"
    )
    await cb.answer("ثبت شد ✅")


@router.callback_query(AddHomework.confirm, F.data == "hmabort")
async def abort_homework(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    for f in data.get("files", []):
        Path(f["path"]).unlink(missing_ok=True)
    await state.clear()
    await cb.message.edit_text(T.CANCELLED)  # type: ignore[union-attr]
    await cb.answer()


# ====================================================== manage (list/edit)
async def _render_manage_list(
    session: AsyncSession, mode: str, page: int = 0
) -> tuple[str, InlineKeyboardMarkup]:
    items, total = await homework_service.list_homework(
        session, page=page + 1, page_size=MANAGE_PAGE_SIZE
    )
    pages = max(1, math.ceil(total / MANAGE_PAGE_SIZE))
    if not items:
        return "تکلیفی برای مدیریت وجود ندارد. اول با ➕ ثبت تکلیف یکی بساز!", keyboards.back_home_kb()

    prefix = "hmdel:" if mode == "delete" else "hmedit:"
    rows = [
        [
            InlineKeyboardButton(
                text=f"📘 {hw.subject} — {hw.homework_date.strftime('%Y-%m-%d')} | {hw.title[:30]}",
                callback_data=f"{prefix}{hw.id}",
            )
        ]
        for hw in items
    ]
    nav = keyboards.pagination_row(f"hmlist:{mode}", page, pages)
    if nav:
        rows.append(nav)
    title = "🗑 تکلیف را برای حذف انتخاب کن:" if mode == "delete" else "✏️ تکلیف را برای ویرایش انتخاب کن:"
    return title, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(MinRole(Role.CONTRIBUTOR), F.text == T.BTN_MANAGE_HW)
async def btn_manage(message: Message, session: AsyncSession):
    text, kb = await _render_manage_list(session, "edit")
    await message.answer(text, reply_markup=kb)


@router.message(MinRole(Role.CONTRIBUTOR), F.text == T.BTN_DELETE_HW)
async def btn_delete(message: Message, session: AsyncSession):
    text, kb = await _render_manage_list(session, "delete")
    await message.answer(text, reply_markup=kb)


@router.callback_query(MinRole(Role.CONTRIBUTOR), F.data.startswith("hmlist:"))
async def cb_manage_page(cb: CallbackQuery, session: AsyncSession):
    _, mode, page = cb.data.split(":")
    text, kb = await _render_manage_list(session, mode, max(0, int(page)))
    try:
        await cb.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass
    await cb.answer()


@router.callback_query(MinRole(Role.CONTRIBUTOR), F.data.startswith("hmedit:"))
async def cb_edit_menu(cb: CallbackQuery, session: AsyncSession):
    hw = await homework_service.get(session, int(cb.data.split(":")[1]))
    await cb.message.edit_text(  # type: ignore[union-attr]
        T.render_homework(hw), reply_markup=keyboards.edit_menu_kb(hw.id)
    )
    await cb.answer()


EDIT_PROMPTS = {
    "title": "✏️ عنوان جدید تکلیف را بنویس:",
    "description": "📝 توضیحات جدید را بنویس (برای خالی کردن /skip):",
    "subject": "📘 نام درس جدید را بنویس:",
    "homework_date": "📅 تاریخ جدید تکلیف را بفرست (امروز/فردا/1404-07-01/2025-09-23):",
    "due_date": "⏰ مهلت جدید را بفرست (برای حذف مهلت /skip):",
}


@router.callback_query(MinRole(Role.CONTRIBUTOR), F.data.startswith("hme:"))
async def cb_edit_field(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    _, field, hw_id = cb.data.split(":")
    hw = await homework_service.get(session, int(hw_id))
    await state.set_state(EditHomework.value)
    await state.update_data(field=field, homework_id=hw.id)
    await cb.message.edit_text(  # type: ignore[union-attr]
        f"{T.render_homework(hw)}\n\n{EDIT_PROMPTS[field]}"
    )
    await cb.answer()


@router.message(EditHomework.value, Command("skip"))
async def apply_edit_skip(message: Message, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    if data["field"] in ("description", "due_date"):
        await _apply_edit(message, state, session, user, None)
    else:
        await message.answer("⚠️ این فیلد نمی‌تواند خالی باشد؛ مقدار را بنویس یا /cancel.")


@router.message(EditHomework.value, is_plain_text)
async def apply_edit(message: Message, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    field = data["field"]
    value = message.text.strip()

    if field in ("homework_date", "due_date"):
        parsed = parse_flexible_date(value)
        if parsed is None:
            await message.answer("⚠️ تاریخ نامعتبر است؛ دوباره بنویس یا /cancel.")
            return
        value = parsed
    elif field == "title":
        value = value[:200]
    elif field == "subject":
        value = value[:100]
    else:
        value = value[:4000]

    await _apply_edit(message, state, session, user, value)


async def _apply_edit(message, state, session, user, value):
    data = await state.get_data()
    try:
        hw = await homework_service.update(
            session,
            data["homework_id"],
            HomeworkUpdate(**{data["field"]: value}),
            user,
            source="telegram",
        )
    except AppError as exc:
        await message.answer(f"⚠️ {T.esc(exc.message)}")
        return
    await state.clear()
    await message.answer(
        f"✅ ذخیره شد:\n\n{T.render_homework(hw)}",
        reply_markup=keyboards.back_home_kb(),
    )


# ========================================================== delete flow
@router.callback_query(MinRole(Role.CONTRIBUTOR), F.data.startswith("hmdel:"))
async def cb_delete_confirm(cb: CallbackQuery, session: AsyncSession):
    hw = await homework_service.get(session, int(cb.data.split(":")[1]))
    await cb.message.edit_text(  # type: ignore[union-attr]
        f"⚠️ این تکلیف حذف شود؟\n\n{T.render_homework(hw)}",
        reply_markup=keyboards.confirm_kb(
            f"hmdelc:{hw.id}", "hmlist:delete:0", yes_text="🗑 بله، حذف کن"
        ),
    )
    await cb.answer()


@router.callback_query(MinRole(Role.CONTRIBUTOR), F.data.startswith("hmdelc:"))
async def cb_delete_execute(cb: CallbackQuery, session: AsyncSession, user: User):
    hw_id = int(cb.data.split(":")[1])
    try:
        await homework_service.delete(session, hw_id, user, source="telegram")
    except AppError as exc:
        await cb.answer(f"⚠️ {exc.message}", show_alert=True)
        return
    await cb.message.edit_text(f"🗑 تکلیف <b>{fa_num(hw_id)}</b> حذف شد.")  # type: ignore[union-attr]
    await cb.answer("حذف شد")
