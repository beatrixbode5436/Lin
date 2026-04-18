import logging
import telebot

from config import CHANNEL_URL, ADMIN_IDS
from bot.keyboards.main_kb import main_menu_keyboard
from bot.states import clear_state
from services.license_service import get_licenses_by_owner
from services.settings_service import get_setting

logger = logging.getLogger(__name__)


def register_start_handlers(bot: telebot.TeleBot) -> None:

    @bot.message_handler(commands=["start"])
    def handle_start(message: telebot.types.Message) -> None:
        user_id = message.from_user.id
        clear_state(user_id)

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
            message.chat.id,
            full_text,
            reply_markup=main_menu_keyboard(user_id, has_licenses),
            parse_mode="HTML",
        )

    @bot.message_handler(commands=["cancel"])
    def handle_cancel(message: telebot.types.Message) -> None:
        clear_state(message.from_user.id)
        bot.send_message(
            message.chat.id,
            "❌ عملیات لغو شد.",
            reply_markup=main_menu_keyboard(
                message.from_user.id,
                bool(get_licenses_by_owner(message.from_user.id)),
            ),
        )

    @bot.message_handler(func=lambda m: m.text == "🛒 خرید اشتراک")
    def handle_subscription(message: telebot.types.Message) -> None:
        sub_text = get_setting(
            "subscription_text",
            "برای خرید اشتراک با @Emad_Habibnia در تماس باشید.",
        )
        bot.send_message(message.chat.id, sub_text, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "📢 کانال اطلاع رسانی")
    def handle_channel(message: telebot.types.Message) -> None:
        channel_url = get_setting("channel_url", CHANNEL_URL)
        bot.send_message(
            message.chat.id,
            f"📢 <b>کانال اطلاع رسانی ما:</b>\n{channel_url}",
            parse_mode="HTML",
        )
