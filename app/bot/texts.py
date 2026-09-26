"""Persian UI texts for the Telegram bot (HTML parse mode).

All user-provided content MUST go through `esc()` before being embedded in
HTML-formatted messages.
"""

from __future__ import annotations

from html import escape

from app.utils.dates import fa_num, fmt_date, fmt_date_short

APP_NAME = "کلاس‌یار"

ROLE_FA = {
    "SUPER_ADMIN": "🛡 مدیر کل",
    "CONTRIBUTOR": "✍️ همکار تکالیف",
    "USER": "🎒 دانش‌آموز",
}

# ------------------------------------------------------------- reply menus
BTN_TODAY = "📚 تکالیف امروز"
BTN_UPCOMING = "📅 تکالیف آینده"
BTN_PAST = "🕘 تکالیف گذشته"
BTN_RANKING = "🏆 رتبه‌بندی"
BTN_MY_POINTS = "⭐ امتیاز من"
BTN_ADD_HW = "➕ ثبت تکلیف"
BTN_MANAGE_HW = "✏️ مدیریت تکالیف"
BTN_DELETE_HW = "🗑 حذف تکلیف"
BTN_ADMIN = "🛠 پنل مدیریت"

USER_MENU = [BTN_TODAY, BTN_UPCOMING, BTN_PAST, BTN_RANKING, BTN_MY_POINTS]
CONTRIBUTOR_MENU = [BTN_ADD_HW, BTN_MANAGE_HW, BTN_DELETE_HW] + USER_MENU
SUPER_ADMIN_MENU = CONTRIBUTOR_MENU + [BTN_ADMIN]

ALL_MENU_BUTTONS = set(SUPER_ADMIN_MENU)

SCOPE_FA = {"today": "📚 تکالیف امروز", "upcoming": "📅 تکالیف آینده", "past": "🕘 تکالیف گذشته"}

NO_HOMEWORK = "در این بخش تکلیفی ثبت نشده است. 🌱"


def esc(text) -> str:
    return escape(str(text if text is not None else ""))


def banned(reason: str | None) -> str:
    line = f"\nدلیل: {esc(reason)}" if reason else ""
    return (
        "🚫 متأسفانه شما از این ربات مسدود شده‌اید."
        f"{line}\nبرای پیگیری با مدیر کلاس تماس بگیرید."
    )


def welcome(user, class_name: str) -> str:
    role = ROLE_FA.get(user.role.value if hasattr(user.role, "value") else str(user.role), "؟")
    return (
        f"سلام {esc(user.full_name)} عزیز 👋\n\n"
        f"به ربات مدیریت تکالیف <b>{esc(class_name)}</b> خوش آمدی!\n"
        f"نقش شما: <b>{role}</b>\n\n"
        "از دکمه‌های منوی پایین استفاده کن. برای راهنما /help را بزن. 📚"
    )


def help_text(user) -> str:
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    lines = [
        "📖 <b>راهنمای ربات کلاس‌یار</b>\n",
        "📚 <b>تکالیف امروز</b> – تکالیف امروز کلاس را نشان می‌دهد.",
        "📅 <b>تکالیف آینده</b> – تکالیف روزهای پیش رو.",
        "🕘 <b>تکالیف گذشته</b> – آرشیو تکالیف قبلی.",
        "🏆 <b>رتبه‌بندی</b> – جدول امتیازات کلاس.",
        "⭐ <b>امتیاز من</b> – امتیاز، رتبه و استریک شما.",
    ]
    if role in ("CONTRIBUTOR", "SUPER_ADMIN"):
        lines += [
            "\n✍️ <b>امکانات همکاری شما:</b>",
            "➕ <b>ثبت تکلیف</b> – افزودن تکلیف جدید (درس، عنوان، تاریخ، پیوست).",
            "✏️ <b>مدیریت تکالیف</b> – ویرایش تکالیف ثبت‌شده.",
            "🗑 <b>حذف تکلیف</b> – حذف تکلیف‌های اشتباه.",
        ]
    if role == "SUPER_ADMIN":
        lines += [
            "\n🛡 <b>مدیریت:</b> از 🛠 پنل مدیریت می‌توانید کاربران، نقش‌ها، "
            "قوانین امتیازدهی، کلیدهای API و لاگ رویدادها را مدیریت کنید.",
        ]
    lines += [
        "\n🔑 دستور <code>/api</code> کد اتصال به پنل وب/API می‌دهد.",
        "❌ دستور <code>/cancel</code> هر عملیات جاری را لغو می‌کند.",
    ]
    return "\n".join(lines)


def auth_code_text(code: str, minutes: int) -> str:
    return (
        "🔑 <b>کد اتصال شما:</b>\n\n"
        f"<code>{esc(code)}</code>\n\n"
        f"⏳ این کد تا <b>{fa_num(minutes)} دقیقه</b> معتبر است و فقط یک بار قابل استفاده است.\n"
        "برای ورود به پنل مدیریت وب، همین کد را در صفحه ورود وارد کنید؛ "
        "یا برای فراخوانی مستقیم API از آن در <code>POST /api/auth/exchange</code> استفاده کنید."
    )


CANCELLED = "❌ عملیات لغو شد."
UNKNOWN = "متوجه دستور شما نشدم 🤔\nاز منوی پایین استفاده کن یا /help را بزن."
EXPIRED = "⏳ این دکمه منقضی شده است؛ از منوی اصلی دوباره شروع کن."
SOMETHING_WRONG = "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کن."


# ------------------------------------------------------------ homework view
def render_homework(hw, *, with_author: bool = True) -> str:
    lines = [
        f"📘 <b>درس:</b> {esc(hw.subject)}",
        f"📝 <b>تکلیف:</b> {esc(hw.title)}",
    ]
    if hw.description:
        lines.append(f"📄 <b>توضیحات:</b> {esc(hw.description)}")
    lines.append(f"🗓 <b>تاریخ:</b> {fmt_date(hw.homework_date)}")
    if hw.due_date:
        lines.append(f"⏰ <b>مهلت انجام:</b> {fmt_date(hw.due_date)}")
    if hw.attachments:
        lines.append(f"📎 <b>پیوست:</b> {fa_num(len(hw.attachments))} فایل")
    if with_author:
        lines.append(f"👤 <b>ثبت‌کننده:</b> {esc(hw.author_name)}")
    return "\n".join(lines)


def render_hw_list(header: str, items: list, page: int, total: int) -> str:
    parts = [f"<b>{header}</b>"]
    if total > len(items):
        parts.append(f"(مجموع {fa_num(total)} تکلیف)\n")
    for idx, hw in enumerate(items, start=page + 1):
        parts.append(f"{fa_num(idx)}. " + render_homework(hw, with_author=False))
        parts.append("")
    return "\n".join(parts).strip()


# --------------------------------------------------------------- ranking
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def render_ranking(entries: list[dict]) -> str:
    if not entries:
        return "هنوز کسی امتیازی ندارد. اولین نفر باش! 🚀"
    lines = ["🏆 <b>رتبه‌بندی کلاس</b>\n"]
    for e in entries:
        medal = MEDALS.get(e["rank"], f"{fa_num(e['rank'])}.")
        user = e["user"]
        lines.append(
            f"{medal} {esc(user.display_name)} — "
            f"⭐ {fa_num(user.points)} امتیاز | 🔥 {fa_num(e['activities'])} فعالیت"
        )
    return "\n".join(lines)


def render_my_points(user, info: dict, history: list) -> str:
    lines = [
        "⭐ <b>امتیاز من</b>\n",
        f"⭐ امتیاز: <b>{fa_num(user.points)}</b>",
        f"🏅 رتبه: <b>{fa_num(info['rank'])}</b> از {fa_num(info['total_users'])}",
        f"🔥 استریک: <b>{fa_num(user.streak_count)}</b> روز",
        f"⚡ تعداد فعالیت‌ها: <b>{fa_num(info['activities'])}</b>",
    ]
    if history:
        lines.append("\n<b>آخرین امتیازها:</b>")
        for tx in history[:5]:
            sign = "+" if tx.amount >= 0 else ""
            desc = f" — {esc(tx.description)}" if tx.description else ""
            lines.append(f"• {sign}{fa_num(tx.amount)} {esc(tx.reason)}{desc}")
    return "\n".join(lines)


# ------------------------------------------------------------- admin panel
def render_stats(stats: dict) -> str:
    users = stats.get("users", {})
    hw = stats.get("homework", {})
    by_role = users.get("by_role", {})
    role_lines = "\n".join(
        f"  • {ROLE_FA.get(role, role)}: {fa_num(count)}" for role, count in by_role.items()
    ) or "  —"
    subjects = "\n".join(
        f"  • {esc(s['subject'])}: {fa_num(s['count'])}"
        for s in stats.get("top_subjects", [])
    ) or "  —"
    return (
        "📊 <b>آمار سیستم</b>\n\n"
        f"👥 کاربران: <b>{fa_num(users.get('total', 0))}</b> "
        f"(مسدود: {fa_num(users.get('banned', 0))})\n"
        f"{role_lines}\n\n"
        f"📚 تکالیف: <b>{fa_num(hw.get('total', 0))}</b>\n"
        f"  • امروز: {fa_num(hw.get('today', 0))}\n"
        f"  • آینده: {fa_num(hw.get('upcoming', 0))}\n\n"
        f"📘 پرتکرارترین درس‌ها:\n{subjects}"
    )


def render_user_card(user) -> str:
    role = ROLE_FA.get(
        user.role.value if hasattr(user.role, "value") else str(user.role), "؟"
    )
    username = f"\n🔗 یوزرنیم: @{esc(user.username)}" if user.username else ""
    ban = (
        f"\n🚫 <b>مسدود شده</b>" + (f" (دلیل: {esc(user.ban_reason)})" if user.ban_reason else "")
        if user.is_banned
        else ""
    )
    return (
        f"👤 <b>{esc(user.full_name)}</b>\n"
        f"🆔 شناسه: <code>{user.id}</code> | تلگرام: <code>{user.telegram_id}</code>"
        f"{username}\n"
        f"🎭 نقش: {role}\n"
        f"⭐ امتیاز: {fa_num(user.points)} | 🔥 استریک: {fa_num(user.streak_count)} روز\n"
        f"📅 عضویت: {fmt_date_short(user.created_at.date())}"
        f"{ban}"
    )


RULES_FA = {
    "first_daily_activity": "اولین فعالیت روز",
    "streak_bonus": "پاداش استریک (به‌ازای هر روز)",
    "streak_bonus_max": "سقف روزهای پاداش استریک",
    "view_homework_today": "مشاهده تکالیف امروز",
    "create_homework": "ثبت تکلیف",
    "edit_homework": "ویرایش تکلیف",
    "add_attachment": "ارسال پیوست",
}


def render_rules(rules: dict) -> str:
    state = "✅ فعال" if rules.get("enabled") else "❌ غیرفعال"
    lines = [f"⚙️ <b>قوانین امتیازدهی</b> ({state})\n"]
    for key, value in (rules.get("actions") or {}).items():
        label = RULES_FA.get(key, key)
        lines.append(f"• {label}: <b>{fa_num(value)}</b>")
    lines.append(
        "\n💡 برای ویرایش، مقدار جدید را به شکل «کلید عدد» بفرست. "
        "مثلاً: <code>create_homework 10</code>"
    )
    return "\n".join(lines)


def render_log(entry: dict) -> str:
    details = ""
    if entry.get("details"):
        items = [f"{k}: {esc(str(v)[:60])}" for k, v in list(entry["details"].items())[:3]]
        details = "\n   ↳ " + " | ".join(items) if items else ""
    return (
        f"[<code>{entry['id']}</code>] {esc(entry['action'])} — {esc(entry['actor_name'])}"
        f" ({esc(entry['source'])}){details}"
    )
