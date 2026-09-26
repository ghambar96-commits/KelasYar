"""SUPER_ADMIN panel inside Telegram.

Every entry point is guarded by MinRole(SUPER_ADMIN); the service layer
re-checks permissions (defense in depth).
"""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts as T
from app.bot.filters import MinRole, is_plain_text
from app.core.exceptions import AppError
from app.models import Role, User
from app.services import (
    audit_service,
    auth_service,
    points_service,
    settings_service,
    user_service,
)
from app.utils.dates import fa_num

router = Router(name="admin")

USERS_PAGE_SIZE = 8
LOGS_PAGE_SIZE = 8


class AdminSearchUser(StatesGroup):
    query = State()


class AdminBan(StatesGroup):
    reason = State()


class AdminAdjust(StatesGroup):
    amount = State()
    reason = State()


class AdminRuleEdit(StatesGroup):
    value = State()


class AdminKeyName(StatesGroup):
    name = State()


# ---------------------------------------------------------------- menu
@router.message(MinRole(Role.SUPER_ADMIN), F.text == T.BTN_ADMIN)
@router.message(MinRole(Role.SUPER_ADMIN), Command("admin"))
async def admin_menu(message: Message):
    await message.answer("🛠 <b>پنل مدیریت</b>\nیک بخش را انتخاب کن:", reply_markup=keyboards.admin_menu_kb())


# ---------------------------------------------------------------- stats
@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:stats")
async def adm_stats(cb: CallbackQuery, session: AsyncSession):
    stats = await user_service.stats(session)
    await cb.message.edit_text(T.render_stats(stats), reply_markup=keyboards.admin_menu_kb())  # type: ignore[union-attr]
    await cb.answer()


# ---------------------------------------------------------------- users
async def _render_users_list(session: AsyncSession, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    users, total = await user_service.list_users(session, page=page + 1, page_size=USERS_PAGE_SIZE)
    pages = max(1, (total + USERS_PAGE_SIZE - 1) // USERS_PAGE_SIZE)
    rows = [
        [InlineKeyboardButton(
            text=f"👤 {u.display_name[:28]} — {T.ROLE_FA.get(u.role.value, u.role.value)[:12]}"
                 + (" 🚫" if u.is_banned else ""),
            callback_data=f"admview:{u.id}",
        )]
        for u in users
    ]
    nav = keyboards.pagination_row("adm:users", page, pages)
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔍 جستجوی کاربر", callback_data="adm:search")])
    return f"👥 <b>کاربران</b> (مجموع {fa_num(total)})", InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("adm:users:"))
async def adm_users(cb: CallbackQuery, session: AsyncSession):
    page = int(cb.data.split(":")[2]) if cb.data.count(":") == 2 else 0
    text, kb = await _render_users_list(session, max(0, page))
    try:
        await cb.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass
    await cb.answer()


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:search")
async def adm_search_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSearchUser.query)
    await cb.message.edit_text(  # type: ignore[union-attr]
        "🔍 شناسه تلگرام (عددی)، نام یا یوزرنیم کاربر را بفرست:"
    )
    await cb.answer()


@router.message(MinRole(Role.SUPER_ADMIN), AdminSearchUser.query, is_plain_text)
async def adm_search_apply(message: Message, state: FSMContext, session: AsyncSession):
    target = await user_service.search_user(session, message.text)
    await state.clear()
    if target is None:
        await message.answer("❌ کاربری یافت نشد.")
        return
    await message.answer(T.render_user_card(target), reply_markup=keyboards.user_card_kb(target))


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("admview:"))
async def adm_view_user(cb: CallbackQuery, session: AsyncSession):
    target = await user_service.get_by_id(session, int(cb.data.split(":")[1]))
    if target is None:
        await cb.answer("کاربر یافت نشد", show_alert=True)
        return
    await cb.message.edit_text(  # type: ignore[union-attr]
        T.render_user_card(target), reply_markup=keyboards.user_card_kb(target)
    )
    await cb.answer()


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("admrole:"))
async def adm_set_role(cb: CallbackQuery, session: AsyncSession, user: User):
    _, uid, role = cb.data.split(":")
    target = await user_service.get_by_id(session, int(uid))
    if target is None:
        await cb.answer("کاربر یافت نشد", show_alert=True)
        return
    try:
        await user_service.set_role(session, user, target, Role(role), source="telegram")
    except AppError as exc:
        await cb.answer(f"⚠️ {exc.message}", show_alert=True)
        return
    await cb.answer("✅ نقش تغییر کرد")
    await cb.message.edit_text(  # type: ignore[union-attr]
        T.render_user_card(target), reply_markup=keyboards.user_card_kb(target)
    )


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("admban:"))
async def adm_ban_start(cb: CallbackQuery, state: FSMContext):
    target = await user_service.get_by_id(session, int(cb.data.split(":")[1]))
    if target is None:
        await cb.answer("کاربر یافت نشد", show_alert=True)
        return
    await state.set_state(AdminBan.reason)
    await state.update_data(user_id=target.id)
    await cb.message.edit_text(  # type: ignore[union-attr]
        f"🚫 دلیل مسدود کردن {T.esc(target.full_name)} چیست؟\n(برای بدون دلیل /skip)"
    )
    await cb.answer()


@router.message(MinRole(Role.SUPER_ADMIN), AdminBan.reason, Command("skip"))
async def adm_ban_apply_skip(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await _ban_apply(message, state, session, user, None)


@router.message(MinRole(Role.SUPER_ADMIN), AdminBan.reason, is_plain_text)
async def adm_ban_apply(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await _ban_apply(message, state, session, user, message.text.strip()[:255])


async def _ban_apply(message, state, session, user, reason):
    data = await state.get_data()
    target = await user_service.get_by_id(session, data["user_id"])
    await state.clear()
    if target is None:
        await message.answer("❌ کاربر یافت نشد.")
        return
    try:
        await user_service.ban(session, user, target, reason, source="telegram")
    except AppError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        f"🚫 {T.esc(target.full_name)} مسدود شد.", reply_markup=keyboards.user_card_kb(target)
    )


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("admunban:"))
async def adm_unban(cb: CallbackQuery, session: AsyncSession, user: User):
    target = await user_service.get_by_id(session, int(cb.data.split(":")[1]))
    if target is None:
        await cb.answer("کاربر یافت نشد", show_alert=True)
        return
    try:
        await user_service.unban(session, user, target, source="telegram")
    except AppError as exc:
        await cb.answer(f"⚠️ {exc.message}", show_alert=True)
        return
    await cb.answer("✅ مسدودیت برداشته شد")
    await cb.message.edit_text(  # type: ignore[union-attr]
        T.render_user_card(target), reply_markup=keyboards.user_card_kb(target)
    )


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("admadj:"))
async def adm_adjust_start(cb: CallbackQuery, state: FSMContext):
    target = await user_service.get_by_id(session, int(cb.data.split(":")[1]))
    if target is None:
        await cb.answer("کاربر یافت نشد", show_alert=True)
        return
    await state.set_state(AdminAdjust.amount)
    await state.update_data(user_id=target.id)
    await cb.message.edit_text(  # type: ignore[union-attr]
        f"🎯 مقدار امتیاز برای {T.esc(target.full_name)} را بنویس.\n"
        "مثال: <code>10</code> برای افزودن یا <code>-5</code> برای کاستن."
    )
    await cb.answer()


@router.message(MinRole(Role.SUPER_ADMIN), AdminAdjust.amount, is_plain_text)
async def adm_adjust_amount(message: Message, state: FSMContext):
    from app.utils.dates import normalize_digits

    raw = normalize_digits(message.text.strip()).replace("٫", "").replace(",", "")
    try:
        amount = int(raw)
    except ValueError:
        await message.answer("⚠️ فقط یک عدد صحیح بفرست (مثلاً 10 یا -5).")
        return
    if abs(amount) > 10000 or amount == 0:
        await message.answer("⚠️ عدد باید بین ۱- تا ۱۰۰۰۰ و غیرصفر باشد.")
        return
    await state.update_data(amount=amount)
    await state.set_state(AdminAdjust.reason)
    await message.answer("📝 دلیل این تغییر را بنویس (یا /skip):")


@router.message(MinRole(Role.SUPER_ADMIN), AdminAdjust.reason, Command("skip"))
async def adm_adjust_apply_skip(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await _adjust_apply(message, state, session, user, None)


@router.message(MinRole(Role.SUPER_ADMIN), AdminAdjust.reason, is_plain_text)
async def adm_adjust_apply(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await _adjust_apply(message, state, session, user, message.text.strip()[:255])


async def _adjust_apply(message, state, session, user, note):
    data = await state.get_data()
    target = await user_service.get_by_id(session, data["user_id"])
    await state.clear()
    if target is None:
        await message.answer("❌ کاربر یافت نشد.")
        return
    try:
        await points_service.adjust(session, user, target, data["amount"], note, source="telegram")
    except AppError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        f"✅ امتیاز {T.esc(target.full_name)} تغییر کرد.\n"
        f"⭐ امتیاز جدید: <b>{fa_num(target.points)}</b>",
        reply_markup=keyboards.user_card_kb(target),
    )


# ---------------------------------------------------------------- rules
@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:rules")
async def adm_rules(cb: CallbackQuery, session: AsyncSession):
    rules = await points_service.get_rules(session)
    await cb.message.edit_text(  # type: ignore[union-attr]
        T.render_rules(rules), reply_markup=keyboards.rules_kb(rules.get("enabled", True))
    )
    await cb.answer()


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:rules:toggle")
async def adm_rules_toggle(cb: CallbackQuery, session: AsyncSession, user: User):
    rules = await points_service.get_rules(session)
    rules["enabled"] = not rules.get("enabled", True)
    await points_service.set_rules(session, rules, actor=user, source="telegram")
    state_txt = "فعال ✅" if rules["enabled"] else "غیرفعال ❌"
    await cb.answer(f"سیستم امتیازدهی {state_txt} شد")
    await cb.message.edit_text(  # type: ignore[union-attr]
        T.render_rules(rules), reply_markup=keyboards.rules_kb(rules["enabled"])
    )


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:rules:edit")
async def adm_rules_edit(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    rules = await points_service.get_rules(session)
    keys = "\n".join(f"• <code>{k}</code> ({T.RULES_FA.get(k, k)}): {fa_num(v)}"
                     for k, v in (rules.get("actions") or {}).items())
    await state.set_state(AdminRuleEdit.value)
    await cb.message.edit_text(  # type: ignore[union-attr]
        "✏️ کلید و مقدار جدید را با فاصله بفرست:\n"
        "مثال: <code>create_homework 10</code>\n\n"
        f"کلیدهای فعلی:\n{keys}"
    )
    await cb.answer()


@router.message(MinRole(Role.SUPER_ADMIN), AdminRuleEdit.value, is_plain_text)
async def adm_rules_apply(message: Message, state: FSMContext, session: AsyncSession, user: User):
    from app.utils.dates import normalize_digits

    parts = normalize_digits(message.text.strip()).split()
    if len(parts) != 2 or not re.match(r"^[a-z][a-z0-9_]{1,48}$", parts[0]):
        await message.answer("⚠️ قالب درست نیست. مثال: <code>create_homework 10</code>")
        return
    key, raw_value = parts
    try:
        value = int(raw_value)
    except ValueError:
        await message.answer("⚠️ مقدار باید عدد باشد. مثال: <code>create_homework 10</code>")
        return
    if not 0 <= value <= 1000:
        await message.answer("⚠️ مقدار باید بین ۰ تا ۱۰۰۰ باشد.")
        return

    rules = await points_service.get_rules(session)
    rules["actions"][key] = value
    await points_service.set_rules(session, rules, actor=user, source="telegram")
    await state.clear()
    await message.answer(
        f"✅ قانون <code>{T.esc(key)}</code> = <b>{fa_num(value)}</b> ذخیره شد.",
        reply_markup=keyboards.admin_menu_kb(),
    )


# ---------------------------------------------------------------- logs
@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data.startswith("adm:logs:"))
async def adm_logs(cb: CallbackQuery, session: AsyncSession):
    page = max(0, int(cb.data.split(":")[2]))
    items, total = await audit_service.list_logs(session, page=page + 1, page_size=LOGS_PAGE_SIZE)
    pages = max(1, (total + LOGS_PAGE_SIZE - 1) // LOGS_PAGE_SIZE)
    if not items:
        text = "📜 رویدادی ثبت نشده است."
    else:
        text = "📜 <b>آخرین رویدادها</b>\n\n" + "\n\n".join(T.render_log(e) for e in items)
    nav = keyboards.pagination_row("adm:logs", page, pages)
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:menu")])
    try:
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass
    await cb.answer()


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:menu")
async def adm_back_to_menu(cb: CallbackQuery):
    await cb.message.edit_text("🛠 <b>پنل مدیریت</b>", reply_markup=keyboards.admin_menu_kb())  # type: ignore[union-attr]
    await cb.answer()


# ---------------------------------------------------------------- api keys
@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:keys")
async def adm_keys(cb: CallbackQuery, session: AsyncSession):
    keys = await auth_service.list_api_keys(session)
    if not keys:
        text = "🔑 کلید API فعالی وجود ندارد."
    else:
        lines = ["🔑 <b>کلیدهای API</b>\n"]
        for k in keys[:10]:
            used = fa_num(k.last_used_at.strftime("%Y-%m-%d")) if k.last_used_at else "—"
            lines.append(f"• <code>{T.esc(k.key_prefix)}…</code> ({T.esc(k.name)}) — آخرین استفاده: {used}")
        text = "\n".join(lines)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ کلید جدید", callback_data="adm:keys:new")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:menu")],
        ]
    )
    await cb.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await cb.answer()


@router.callback_query(MinRole(Role.SUPER_ADMIN), F.data == "adm:keys:new")
async def adm_key_new(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminKeyName.name)
    await cb.message.edit_text("🔑 نام کلید را بنویس (مثلاً: admin-panel):")  # type: ignore[union-attr]
    await cb.answer()


@router.message(MinRole(Role.SUPER_ADMIN), AdminKeyName.name, is_plain_text)
async def adm_key_create(message: Message, state: FSMContext, session: AsyncSession, user: User):
    name = message.text.strip()[:64]
    key, raw = await auth_service.create_api_key(session, user, name)
    await state.clear()
    await message.answer(
        "✅ کلید ساخته شد.\n\n"
        f"<code>{T.esc(raw)}</code>\n\n"
        "⚠️ این مقدار فقط همین یک بار نمایش داده می‌شود؛ آن را در جای امن نگه دار. "
        "برای فراخوانی API در هدر <code>X-API-Key</code> بگذارید."
    )
