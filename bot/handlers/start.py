import logging
import telebot
from telebot.types import ReplyKeyboardRemove

from config import CHANNEL_URL, ADMIN_IDS
from bot.keyboards.main_kb import main_menu_keyboard
from bot.states import clear_state
from services.license_service import get_licenses_by_owner
from services.settings_service import get_setting

logger = logging.getLogger(__name__)


def _send_main_menu(bot: telebot.TeleBot, chat_id: int, user_id: int) -> None:
    licenses = get_licenses_by_owner(user_id)
    has_licenses = bool(licenses)
    start_text = get_setting(
        "start_text",
        "🎯 به مرکز مدیریت لایسنس خوش آمدید!\n\nاز این ربات می‌توانید وضعیت لایسنس ربات‌های خود را مشاهده کنید.",
    )
    full_text = (
        "<b>🎯 مرکز مدیریت لایسنس</b>\n\n"
        f"{start_text}\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    bot.send_message(
        chat_id,
        full_text,
        reply_markup=main_menu_keyboard(user_id, has_licenses),
        parse_mode="HTML",
    )


def register_start_handlers(bot: telebot.TeleBot) -> None:

    @bot.message_handler(commands=["start"])
    def handle_start(message: telebot.types.Message) -> None:
        user_id = message.from_user.id
        clear_state(user_id)
        # Remove any existing reply keyboard, then send inline menu
        bot.send_message(message.chat.id, ".", reply_markup=ReplyKeyboardRemove())
        try:
            bot.delete_message(message.chat.id, message.message_id + 1)
        except Exception:
            pass
        _send_main_menu(bot, message.chat.id, user_id)

    @bot.message_handler(commands=["cancel"])
    def handle_cancel(message: telebot.types.Message) -> None:
        clear_state(message.from_user.id)
        bot.send_message(message.chat.id, "❌ عملیات لغو شد.")
        _send_main_menu(bot, message.chat.id, message.from_user.id)

    # ── Main menu callbacks ───────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "main_menu")
    def handle_back_main_menu(call: telebot.types.CallbackQuery) -> None:
        licenses = get_licenses_by_owner(call.from_user.id)
        has_licenses = bool(licenses)
        start_text = get_setting(
            "start_text",
            "🎯 به مرکز مدیریت لایسنس خوش آمدید!\n\nاز این ربات می‌توانید وضعیت لایسنس ربات‌های خود را مشاهده کنید.",
        )
        full_text = (
            "<b>🎯 مرکز مدیریت لایسنس</b>\n\n"
            f"{start_text}\n\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
        )
        try:
            bot.edit_message_text(
                full_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=main_menu_keyboard(call.from_user.id, has_licenses),
                parse_mode="HTML",
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                full_text,
                reply_markup=main_menu_keyboard(call.from_user.id, has_licenses),
                parse_mode="HTML",
            )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "main_buy")
    def handle_subscription(call: telebot.types.CallbackQuery) -> None:
        sub_text = get_setting(
            "subscription_text",
            "برای خرید اشتراک با @Emad_Habibnia در تماس باشید.",
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, sub_text, parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "main_channel")
    def handle_channel(call: telebot.types.CallbackQuery) -> None:
        channel_url = get_setting("channel_url", CHANNEL_URL)
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📢 <b>کانال اطلاع رسانی ما:</b>\n{channel_url}",
            parse_mode="HTML",
        )
