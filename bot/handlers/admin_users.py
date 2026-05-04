import logging
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, API_BASE_URL
from bot.keyboards.admin_kb import users_panel_keyboard, users_list_keyboard
from bot.states import States, get_state, set_state, clear_state
from services.license_service import (
    get_user_stats,
    get_all_users,
    search_users,
    get_licenses_by_owner,
)
from utils.helpers import calculate_remaining, format_datetime, shamsi_day_of_month
from datetime import datetime

logger = logging.getLogger(__name__)

_PER_PAGE = 10


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def _send_or_edit(bot: telebot.TeleBot, call, text: str, kb) -> None:
    try:
        bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")


def _users_panel_text(stats: dict) -> str:
    return (
        "👥 <b>مدیریت کاربران</b>\n\n"
        f"📊 تعداد کل کاربران: <b>{stats['total']}</b>\n"
        f"✅ دارندگان لاینسس: <b>{stats['licensed']}</b>\n"
        f"❌ بدون لاینسس: <b>{stats['unlicensed']}</b>\n\n"
        "یک فیلتر انتخاب کنید یا جستجو بزنید:"
    )


def _user_licenses_text(telegram_id: int, licenses: list[dict]) -> str:
    """Build the full licenses detail text for a user."""
    if not licenses:
        return f"👤 کاربر <code>{telegram_id}</code>\n\n❌ هیچ لاینسسی ندارد."

    # Find owner_username from first license
    uname = licenses[0].get("owner_username", "")
    header = (
        f"👤 <b>کاربر:</b> {'@' + uname if uname else ''} "
        f"[<code>{telegram_id}</code>]\n"
        f"🔑 تعداد لاینسس: <b>{len(licenses)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    lines = []
    for lic in licenses:
        total_hours, time_str = calculate_remaining(lic["expires_at"])
        if not lic["is_active"]:
            status = "🔴 غیرفعال"
        elif total_hours <= 0:
            status = "❌ منقضی"
        else:
            status = "✅ فعال"

        try:
            expiry_dt = datetime.fromisoformat(lic["expires_at"])
            gregorian_day = expiry_dt.day
            jalali_day = shamsi_day_of_month(expiry_dt)
        except Exception:
            gregorian_day = "؟"
            jalali_day = "؟"

        lines.append(
            f"🤖 Bot Username: @{lic['bot_username']}\n"
            f"👤 Owner Username: @{lic['owner_username']}\n"
            f"🆔 Owner Telegram ID: {lic['owner_telegram_id']}\n\n"
            f"🔑 API Key لایسنس شما:\n"
            f"<code>{lic['api_key']}</code>\n\n"
            f"🌐 API URL:\n"
            f"<code>{API_BASE_URL}/api/license/check</code>\n\n"
            f"📅 تاریخ تمدید:\n"
            f"• روز {gregorian_day} هر ماه میلادی\n"
            f"• روز {jalali_day} هر ماه شمسی\n\n"
            f"⌛ باقی‌مانده: {time_str}\n"
            f"🔖 وضعیت: {status}"
        )

    return header + "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(lines)


def _user_licenses_keyboard(telegram_id: int, licenses: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for lic in licenses:
        total_hours, time_str = calculate_remaining(lic["expires_at"])
        status = "✅" if lic["is_active"] and total_hours > 0 else "❌"
        kb.add(InlineKeyboardButton(
            f"{status} @{lic['bot_username']} | ⏳ {time_str}",
            callback_data=f"admin_lic_view_{lic['id']}",
        ))
    kb.add(InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="admin_users"))
    return kb


def register_admin_users_handlers(bot: telebot.TeleBot) -> None:

    # ── Panel entry ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_users")
    def handle_users_panel(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        stats = get_user_stats()
        _send_or_edit(bot, call, _users_panel_text(stats), users_panel_keyboard("all"))
        bot.answer_callback_query(call.id)

    # ── Filters ───────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_users_filter_"))
    def handle_users_filter(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        filter_mode = call.data.replace("admin_users_filter_", "")
        users, total = get_all_users(page=1, per_page=_PER_PAGE, filter_mode=filter_mode)
        total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)
        stats = get_user_stats()
        text = _users_panel_text(stats) + f"\n\n📋 نتایج: <b>{total}</b> کاربر"
        _send_or_edit(bot, call, text, users_list_keyboard(users, 1, total_pages, filter_mode))
        bot.answer_callback_query(call.id)

    # ── Pagination ────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_users_page_"))
    def handle_users_page(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        # format: admin_users_page_{filter_mode}_{page}
        parts = call.data.split("_")
        page = int(parts[-1])
        filter_mode = parts[-2]
        users, total = get_all_users(page=page, per_page=_PER_PAGE, filter_mode=filter_mode)
        total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)
        stats = get_user_stats()
        text = _users_panel_text(stats) + f"\n\n📋 نتایج: <b>{total}</b> کاربر"
        _send_or_edit(bot, call, text, users_list_keyboard(users, page, total_pages, filter_mode))
        bot.answer_callback_query(call.id)

    # ── Search ────────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_users_search")
    def handle_users_search_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        set_state(call.from_user.id, States.ADMIN_WAITING_USER_SEARCH, {})
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_users"))
        bot.send_message(
            call.message.chat.id,
            "🔍 <b>جستجوی کاربر</b>\n\n"
            "عبارت جستجو را وارد کنید:\n"
            "• آیدی عددی تلگرام\n"
            "• یوزرنیم (بدون @)\n"
            "• نام کاربری\n\n"
            "/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    @bot.message_handler(
        func=lambda m: get_state(m.from_user.id)[0] == States.ADMIN_WAITING_USER_SEARCH
    )
    def handle_users_search_query(message: telebot.types.Message) -> None:
        if not _is_admin(message.from_user.id):
            return
        if message.text and message.text.strip() == "/cancel":
            clear_state(message.from_user.id)
            stats = get_user_stats()
            bot.send_message(
                message.chat.id,
                _users_panel_text(stats),
                reply_markup=users_panel_keyboard("all"),
                parse_mode="HTML",
            )
            return

        query = message.text.strip() if message.text else ""
        if not query:
            bot.send_message(message.chat.id, "❌ عبارت جستجو نمی‌تواند خالی باشد.")
            return

        clear_state(message.from_user.id)
        users, total = search_users(query, page=1, per_page=_PER_PAGE)
        total_pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)

        if not users:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_users"))
            bot.send_message(
                message.chat.id,
                f"🔍 جستجو برای «{query}»\n\n❌ کاربری یافت نشد.",
                reply_markup=kb,
                parse_mode="HTML",
            )
            return

        text = f"🔍 نتایج جستجو: «{query}»\n📋 <b>{total}</b> کاربر یافت شد"
        bot.send_message(
            message.chat.id,
            text,
            reply_markup=users_list_keyboard(users, 1, total_pages, "search"),
            parse_mode="HTML",
        )

    # ── User detail ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_user_view_"))
    def handle_user_view(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        telegram_id = int(call.data.split("_")[-1])
        licenses = get_licenses_by_owner(telegram_id)
        text = _user_licenses_text(telegram_id, licenses)
        kb = _user_licenses_keyboard(telegram_id, licenses)
        _send_or_edit(bot, call, text, kb)
        bot.answer_callback_query(call.id)

    # ── noop (page indicator button) ──────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "noop")
    def handle_noop(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
