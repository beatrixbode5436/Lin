import logging
import telebot

from bot.keyboards.license_kb import user_licenses_keyboard
from services.license_service import get_licenses_by_owner, get_license_by_id
from utils.helpers import calculate_remaining, format_datetime, paginate

logger = logging.getLogger(__name__)

_PER_PAGE = 5


def _build_licenses_page(
    licenses: list[dict],
    user_id: int,
    page: int,
) -> tuple[str, object, list[dict], int]:
    page_items, total_pages = paginate(licenses, page, _PER_PAGE)

    text = (
        f"📄 Found <b>{len(licenses)}</b> License(s)\n"
        f"👤 Telegram ID: <code>{user_id}</code>\n"
        f"📄 Page: {page} of {total_pages}\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )

    for i, lic in enumerate(page_items, start=(page - 1) * _PER_PAGE + 1):
        total_hours, time_str = calculate_remaining(lic["expires_at"])
        if not lic["is_active"]:
            status = "🔴 Disabled"
        elif total_hours <= 0:
            status = "❌ Expired"
        else:
            status = "✅ Active"

        text += (
            f"\n🔢 License #{i}\n"
            f"🤖 Bot: @{lic['bot_username']}\n"
            f"👤 Owner: @{lic['owner_username']}\n"
            f"📅 License Created: {format_datetime(lic['created_at'])[:10]}\n"
            f"⏳ License Expires: {format_datetime(lic['expires_at'])[:10]}\n"
            f"⌛ Remaining: {time_str}\n"
            f"🔖 Status: {status}\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

    kb = user_licenses_keyboard(page_items, page, total_pages)
    return text, kb, page_items, total_pages


def register_user_handlers(bot: telebot.TeleBot) -> None:

    @bot.message_handler(func=lambda m: m.text == "📋 لایسنس های من")
    def handle_my_licenses(message: telebot.types.Message) -> None:
        user_id = message.from_user.id
        licenses = get_licenses_by_owner(user_id)

        if not licenses:
            bot.send_message(message.chat.id, "❌ شما هیچ لایسنس ثبت‌شده‌ای ندارید.")
            return

        text, kb, _, _ = _build_licenses_page(licenses, user_id, 1)
        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("user_lic_page_"))
    def handle_user_page(call: telebot.types.CallbackQuery) -> None:
        page = int(call.data.split("_")[-1])
        user_id = call.from_user.id
        licenses = get_licenses_by_owner(user_id)

        if not licenses:
            bot.answer_callback_query(call.id, "❌ لایسنسی یافت نشد")
            return

        text, kb, _, _ = _build_licenses_page(licenses, user_id, page)
        try:
            bot.edit_message_text(
                text, call.message.chat.id, call.message.message_id,
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("user_lic_"))
    def handle_user_lic_detail(call: telebot.types.CallbackQuery) -> None:
        try:
            license_id = int(call.data.split("_")[-1])
        except (IndexError, ValueError):
            bot.answer_callback_query(call.id, "❌ خطا")
            return

        lic = get_license_by_id(license_id)
        if not lic or str(lic["owner_telegram_id"]) != str(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return

        total_hours, time_str = calculate_remaining(lic["expires_at"])
        if not lic["is_active"]:
            status = "🔴 Disabled"
        elif total_hours <= 0:
            status = "❌ Expired"
        else:
            status = "✅ Active"

        text = (
            f"🔍 <b>جزئیات لایسنس</b>\n\n"
            f"🤖 Bot: @{lic['bot_username']}\n"
            f"👤 Owner: @{lic['owner_username']}\n"
            f"📅 Created: {format_datetime(lic['created_at'])[:10]}\n"
            f"⏳ Expires: {format_datetime(lic['expires_at'])[:10]}\n"
            f"⌛ Remaining: {time_str}\n"
            f"🔖 Status: {status}"
        )

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data=f"user_lic_page_1"))

        try:
            bot.edit_message_text(
                text, call.message.chat.id, call.message.message_id,
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        bot.answer_callback_query(call.id)
