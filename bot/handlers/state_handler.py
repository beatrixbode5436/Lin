import logging
import telebot
from datetime import datetime

from config import ADMIN_IDS, API_BASE_URL
from bot.states import States, get_state, set_state, clear_state
from services.license_service import (
    create_license,
    adjust_license_hours,
    set_license_time,
    update_license_field,
    get_license_by_id,
    search_licenses,
    get_all_licenses,
)
from services.settings_service import set_setting, get_setting
from bot.keyboards.admin_kb import licenses_panel_keyboard
from utils.helpers import sanitize_username, is_valid_telegram_id, format_datetime, shamsi_day_of_month

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

            try:
                expiry_dt = datetime.fromisoformat(lic["expires_at"])
                gregorian_day = expiry_dt.day
                jalali_day = shamsi_day_of_month(expiry_dt)
            except Exception:
                gregorian_day = "؟"
                jalali_day = "؟"

            result_text = (
                "✅ <b>لایسنس با موفقیت ایجاد شد!</b>\n\n"
                "🔑 اطلاعات لایسنس شما به شرح زیر می‌باشد.\n\n"
                "برای فعال‌سازی لایسنس، لطفاً وارد پنل مدیریت شوید و از بخش «🔐 فعال‌سازی لایسنس» اطلاعات زیر را ارسال نمایید تا لایسنس ربات شما فعال گردد.\n\n"
                "⚠️ همچنین لطفاً حتماً ربات مدیریت لایسنس زیر را نیز استارت کنید:\n"
                "@license_Seamless_BOT\n\n"
                f"🤖 Bot Username: @{lic['bot_username']}\n"
                f"👤 Owner Username: @{lic['owner_username']}\n"
                f"🆔 Owner Telegram ID: {lic['owner_telegram_id']}\n\n"
                f"🔑 API Key لایسنس شما:\n"
                f"<code>{lic['api_key']}</code>\n\n"
                f"🌐 API URL:\n"
                f"<code>http://209.50.228.1:5000/api/license</code>\n\n"
                f"📅 تاریخ تمدید:\n"
                f"• روز {gregorian_day} هر ماه میلادی\n"
                f"• روز {jalali_day} هر ماه شمسی"
            )
            bot.send_message(message.chat.id, result_text, parse_mode="HTML")

        # ── Add hours ──────────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_ADD_HOURS:
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

            updated = adjust_license_hours(license_id, hours)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ <b>{hours}</b> ساعت به لایسنس <b>#{license_id}</b> اضافه شد.\n"
                    f"⏳ تاریخ انقضای جدید: <code>{format_datetime(updated['expires_at'])}</code>",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در بروزرسانی لایسنس.")

        # ── Subtract hours ─────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_SUB_HOURS:
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

            updated = adjust_license_hours(license_id, -hours)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ <b>{hours}</b> ساعت از لایسنس <b>#{license_id}</b> کم شد.\n"
                    f"⏳ تاریخ انقضای جدید: <code>{format_datetime(updated['expires_at'])}</code>",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در بروزرسانی لایسنس.")

        # ── Edit owner username ────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_EDIT_OWNER_USERNAME:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            new_val = sanitize_username(message.text)
            if not new_val:
                bot.send_message(message.chat.id, "❌ یوزرنیم نامعتبر است. دوباره وارد کنید:")
                return
            license_id = data.get("license_id")
            updated = update_license_field(license_id, "owner_username", new_val)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ یوزرنیم خریدار به <code>@{new_val}</code> تغییر یافت.",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در ویرایش.")

        # ── Edit owner telegram ID ─────────────────────────────────────────
        elif state == States.ADMIN_WAITING_EDIT_OWNER_ID:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            val = message.text.strip()
            if not is_valid_telegram_id(val):
                bot.send_message(message.chat.id, "❌ آیدی نامعتبر. فقط عدد وارد کنید:")
                return
            license_id = data.get("license_id")
            updated = update_license_field(license_id, "owner_telegram_id", val)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ آیدی عددی خریدار به <code>{val}</code> تغییر یافت.",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در ویرایش.")

        # ── Edit bot username ──────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_EDIT_BOT_USERNAME:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            new_val = sanitize_username(message.text)
            if not new_val:
                bot.send_message(message.chat.id, "❌ یوزرنیم نامعتبر است. دوباره وارد کنید:")
                return
            license_id = data.get("license_id")
            updated = update_license_field(license_id, "bot_username", new_val)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ یوزرنیم ربات به <code>@{new_val}</code> تغییر یافت.",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در ویرایش.")

        # ── Search licenses ────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_SEARCH_QUERY:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            query = message.text.strip()
            if not query:
                bot.send_message(message.chat.id, "❌ عبارت جستجو نمی‌تواند خالی باشد.")
                return
            set_state(user_id, States.ADMIN_WAITING_SEARCH_QUERY, {"search_query": query})
            licenses, total = search_licenses(query, 1, 10)
            total_pages = max(1, (total + 10 - 1) // 10)
            bot.send_message(
                message.chat.id,
                f"🔍 <b>نتایج جستجو: «{query}»</b>\n📊 تعداد: <b>{total}</b>  |  صفحه 1/{total_pages}",
                parse_mode="HTML",
                reply_markup=licenses_panel_keyboard(licenses, 1, total_pages, search_mode=True),
            )

        # ── Set exact time ─────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_SET_HOURS:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            try:
                hours = int(message.text.strip())
                if hours < 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ عدد صحیح غیر منفی وارد کنید:")
                return
            license_id = data.get("license_id")
            if not license_id:
                bot.send_message(message.chat.id, "❌ خطا. دوباره امتحان کنید.")
                clear_state(user_id)
                return
            updated = set_license_time(license_id, hours)
            clear_state(user_id)
            if updated:
                bot.send_message(
                    message.chat.id,
                    f"✅ زمان لایسنس <b>#{license_id}</b> به <b>{hours}</b> ساعت از الان ست شد.\n"
                    f"⏳ تاریخ انقضای جدید: <code>{format_datetime(updated['expires_at'])}</code>",
                    parse_mode="HTML",
                )
            else:
                bot.send_message(message.chat.id, "❌ خطا در بروزرسانی لایسنس.")

        # ── Page jump ──────────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_PAGE_JUMP:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            try:
                page = int(message.text.strip())
                if page < 1:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ عدد صفحه معتبر وارد کنید:")
                return
            clear_state(user_id)
            licenses, total = get_all_licenses(page, 10)
            total_pages = max(1, (total + 10 - 1) // 10)
            page = min(page, total_pages)
            licenses, total = get_all_licenses(page, 10)
            bot.send_message(
                message.chat.id,
                f"📋 <b>مدیریت لایسنس‌ها</b>\n📊 تعداد کل: <b>{total}</b>  |  صفحه {page}/{total_pages}",
                parse_mode="HTML",
                reply_markup=licenses_panel_keyboard(licenses, page, total_pages),
            )

        # ── Backup interval ────────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_BACKUP_INTERVAL:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            try:
                hours = int(message.text.strip())
                if hours < 0:
                    raise ValueError
            except ValueError:
                bot.send_message(message.chat.id, "❌ عدد صحیح غیر منفی وارد کنید:")
                return
            set_setting("backup_interval_hours", str(hours))
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ بازه بکاپ خودکار به <b>{hours}</b> ساعت تنظیم شد." if hours > 0
                else "✅ بکاپ خودکار غیرفعال شد.",
                parse_mode="HTML",
            )

        # ── Backup destination ─────────────────────────────────────────────
        elif state == States.ADMIN_WAITING_BACKUP_DEST:
            if not _is_admin(user_id):
                clear_state(user_id)
                return
            dest = message.text.strip()
            set_setting("backup_dest", dest)
            clear_state(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ مقصد بکاپ به <code>{dest}</code> تنظیم شد.",
                parse_mode="HTML",
            )
