import logging
import telebot

from config import ADMIN_IDS, API_BASE_URL
from bot.states import States, get_state, set_state, clear_state
from services.license_service import create_license, extend_license
from services.settings_service import set_setting, get_setting
from utils.helpers import sanitize_username, is_valid_telegram_id, format_datetime

logger = logging.getLogger(__name__)


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def register_state_handlers(bot: telebot.TeleBot) -> None:

    @bot.message_handler(func=lambda m: get_state(m.from_user.id)[0] is not None)
    def handle_state_message(message: telebot.types.Message) -> None:
        user_id = message.from_user.id
        state, data = get_state(user_id)

        # ── Edit subscription text ─────────────────────────────────────────
        if state == States.ADMIN_WAITING_SUBSCRIPTION_TEXT:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            set_setting("subscription_text", message.text)
            clear_state(user_id)
            bot.send_message(message.chat.id, "✅ متن خرید اشتراک با موفقیت ذخیره شد.")

        # ── Wizard step 1: bot username ────────────────────────────────────
        elif state == States.ADMIN_WAITING_BOT_USERNAME:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            bot_username = sanitize_username(message.text)
            if not bot_username:
                bot.send_message(message.chat.id, "❌ یوزرنیم نامعتبر است. دوباره وارد کنید:")
                return
            set_state(user_id, States.ADMIN_WAITING_OWNER_USERNAME, {"bot_username": bot_username})
            bot.send_message(
                message.chat.id,
                f"✅ Bot: <code>@{bot_username}</code>\n\n"
                "📍 مرحله <b>2 / 4</b>\n\n"
                "👤 یوزرنیم خریدار را وارد کنید:\n/cancel برای لغو",
                parse_mode="HTML",
            )

        # ── Wizard step 2: owner username ──────────────────────────────────
        elif state == States.ADMIN_WAITING_OWNER_USERNAME:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            owner_username = sanitize_username(message.text)
            if not owner_username:
                bot.send_message(message.chat.id, "❌ یوزرنیم نامعتبر است. دوباره وارد کنید:")
                return
            set_state(
                user_id,
                States.ADMIN_WAITING_OWNER_ID,
                {**data, "owner_username": owner_username},
            )
            bot.send_message(
                message.chat.id,
                f"✅ Owner: <code>@{owner_username}</code>\n\n"
                "📍 مرحله <b>3 / 4</b>\n\n"
                "🆔 آیدی تلگرام خریدار را وارد کنید:\n/cancel برای لغو",
                parse_mode="HTML",
            )

        # ── Wizard step 3: owner telegram ID ──────────────────────────────
        elif state == States.ADMIN_WAITING_OWNER_ID:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            owner_id_str = message.text.strip()
            if not is_valid_telegram_id(owner_id_str):
                bot.send_message(message.chat.id, "❌ آیدی نامعتبر. فقط عدد وارد کنید:")
                return
            set_state(
                user_id,
                States.ADMIN_WAITING_DURATION,
                {**data, "owner_telegram_id": int(owner_id_str)},
            )
            bot.send_message(
                message.chat.id,
                f"✅ ID: <code>{owner_id_str}</code>\n\n"
                "📍 مرحله <b>4 / 4</b>\n\n"
                "⏱ مدت لایسنس به <b>ساعت</b> را وارد کنید:\n"
                "<i>(مثال: 720 برای 30 روز)</i>\n\n/cancel برای لغو",
                parse_mode="HTML",
            )

        # ── Wizard step 4: duration ────────────────────────────────────────
        elif state == States.ADMIN_WAITING_DURATION:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            try:
                hours = int(message.text.strip())
                if hours <= 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ عدد صحیح مثبت وارد کنید:")
                return

            try:
                lic = create_license(
                    data["bot_username"],
                    data["owner_username"],
                    data["owner_telegram_id"],
                    hours,
                )
            except Exception as exc:
                logger.error("Error creating license: %s", exc)
                bot.send_message(message.chat.id, f"❌ خطا در ایجاد لایسنس: {exc}")
                clear_state(user_id)
                return

            clear_state(user_id)
            api_url = get_setting("api_base_url", API_BASE_URL)

            result_text = (
                "✅ <b>لایسنس با موفقیت ایجاد شد!</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🤖 Bot Username: @{lic['bot_username']}\n"
                f"👤 Owner Username: @{lic['owner_username']}\n"
                f"🆔 Owner Telegram ID: <code>{lic['owner_telegram_id']}</code>\n"
                f"🔑 API Key: <code>{lic['api_key']}</code>\n"
                f"📅 Expiry Date: {format_datetime(lic['expires_at'])}\n"
                f"🌐 API URL: <code>{api_url}</code>\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📤 <b>متن آماده برای مشتری:</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🔑 API Key لایسنس شما:\n<code>{lic['api_key']}</code>\n\n"
                f"🌐 API URL:\n<code>{api_url}</code>"
            )
            bot.send_message(message.chat.id, result_text, parse_mode="HTML")

        # ── Extend hours ───────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_EXTEND_HOURS:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            try:
                hours = int(message.text.strip())
                if hours <= 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ عدد صحیح مثبت وارد کنید:")
                return

            license_id = data.get("license_id")
            if not license_id:
                bot.send_message(message.chat.id, "❌ خطا. دوباره امتحان کنید.")
                clear_state(user_id)
                return

            updated = extend_license(license_id, hours)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ لایسنس <b>#{license_id}</b> به مدت <b>{hours}</b> ساعت تمدید شد.\n"
                    f"⏳ تاریخ انقضای جدید: <code>{format_datetime(updated['expires_at'])}</code>",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در تمدید لایسنس.")
