"""Telegram keyboards (reply menus + inline builders)."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.models import Role
from app.bot import texts as T

MENU_ROW_WIDTH = 2


def main_menu(role: Role) -> ReplyKeyboardMarkup:
    if role == Role.SUPER_ADMIN:
        buttons = T.SUPER_ADMIN_MENU
    elif role == Role.CONTRIBUTOR:
        buttons = T.CONTRIBUTOR_MENU
    else:
        buttons = T.USER_MENU
    rows = [
        [KeyboardButton(text=b) for b in buttons[i : i + MENU_ROW_WIDTH]]
        for i in range(0, len(buttons), MENU_ROW_WIDTH)
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="از منوی پایین انتخاب کن…",
    )


def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 منوی اصلی", callback_data="noop")]]
    )


def pagination_row(prefix: str, page: int, pages: int) -> list[InlineKeyboardButton]:
    if pages <= 1:
        return []
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"{prefix}:{page + 1}"))
    return row


def homework_list_kb(
    *,
    items: list,
    scope: str,
    page: int,
    pages: int,
    detail_prefix: str,
) -> InlineKeyboardMarkup:
    """Inline keyboard for homework lists (manage/delete pickers)."""
    rows: list[list[InlineKeyboardButton]] = []
    for hw in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📘 {hw.subject} — {hw.homework_date.strftime('%Y-%m-%d')}",
                    callback_data=f"{detail_prefix}{hw.id}",
                )
            ]
        )
    nav = pagination_row(f"hwpage:{scope}" if detail_prefix.startswith("hm") else f"hw:{scope}", page, pages)
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def attachments_kb(items: list) -> InlineKeyboardMarkup | None:
    if not items:
        return None
    rows = [
        [InlineKeyboardButton(text=f"📎 {a.file_name[:40]}", callback_data=f"hwatt:{a.id}")]
        for a in items[:10]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(yes_cb: str, no_cb: str, yes_text: str = "✅ تأیید", no_text: str = "❌ انصراف") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=yes_text, callback_data=yes_cb),
                InlineKeyboardButton(text=no_text, callback_data=no_cb),
            ]
        ]
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 آمار", callback_data="adm:stats"),
                InlineKeyboardButton(text="👥 کاربران", callback_data="adm:users:0"),
            ],
            [
                InlineKeyboardButton(text="⚙️ قوانین امتیاز", callback_data="adm:rules"),
                InlineKeyboardButton(text="📜 لاگ رویداد", callback_data="adm:logs:0"),
            ],
            [InlineKeyboardButton(text="🔑 کلیدهای API", callback_data="adm:keys")],
        ]
    )


def user_card_kb(target) -> InlineKeyboardMarkup:
    from app.models import Role as R

    rows: list[list[InlineKeyboardButton]] = []
    if target.role == R.USER:
        rows.append(
            [InlineKeyboardButton(text="⬆️ ارتقا به همکار تکالیف", callback_data=f"admrole:{target.id}:CONTRIBUTOR")]
        )
    elif target.role == R.CONTRIBUTOR:
        rows.append(
            [InlineKeyboardButton(text="⬇️ تبدیل به دانش‌آموز", callback_data=f"admrole:{target.id}:USER")]
        )
    if target.is_banned:
        rows.append([InlineKeyboardButton(text="✅ رفع مسدودیت", callback_data=f"admunban:{target.id}")])
    elif target.role != R.SUPER_ADMIN:
        rows.append([InlineKeyboardButton(text="🚫 مسدود کردن", callback_data=f"admban:{target.id}")])
    rows.append(
        [InlineKeyboardButton(text="🎯 تغییر امتیاز", callback_data=f"admadj:{target.id}")]
    )
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:users:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rules_kb(enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ غیرفعال کردن امتیازدهی" if enabled else "✅ فعال کردن امتیازدهی"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="adm:rules:toggle")],
            [InlineKeyboardButton(text="✏️ ویرایش مقدار", callback_data="adm:rules:edit")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:menu")],
        ]
    )


def edit_menu_kb(homework_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ عنوان", callback_data=f"hme:title:{homework_id}"),
                InlineKeyboardButton(text="📝 توضیحات", callback_data=f"hme:description:{homework_id}"),
            ],
            [
                InlineKeyboardButton(text="📘 درس", callback_data=f"hme:subject:{homework_id}"),
                InlineKeyboardButton(text="📅 تاریخ", callback_data=f"hme:homework_date:{homework_id}"),
            ],
            [
                InlineKeyboardButton(text="⏰ مهلت", callback_data=f"hme:due_date:{homework_id}"),
                InlineKeyboardButton(text="🗑 حذف تکلیف", callback_data=f"hmdel:{homework_id}"),
            ],
            [InlineKeyboardButton(text="🔙 بازگشت به فهرست", callback_data="hmlist:edit:0")],
        ]
    )
