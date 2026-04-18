import logging
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, API_BASE_URL
from bot.keyboards.admin_kb import (
    admin_panel_keyboard,
    licenses_panel_keyboard,
    license_detail_keyboard,
    bots_panel_keyboard,
)
from bot.states import States, get_state, set_state, clear_state
from services.license_service import (
    get_all_licenses,
    get_license_by_id,
    update_license_status,
    delete_license,
    rotate_api_key,
)
from services.settings_service import get_setting, set_setting
from database.db import get_connection
from utils.helpers import calculate_remaining, format_datetime

logger = logging.getLogger(__name__)

_LICENSES_PER_PAGE = 10


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def _license_detail_text(lic: dict) -> str:
    total_hours, time_str = calculate_remaining(lic["expires_at"])
    if not lic["is_active"]:
        status_icon = "🔴 غیرفعال"
    elif total_hours <= 0:
        status_icon = "❌ منقضی"
    else:
        status_icon = "✅ فعال"

    return (
        f"🔍 <b>جزئیات لایسنس #{lic['id']}</b>\n\n"
        f"🤖 Bot Username: @{lic['bot_username']}\n"
        f"👤 Owner Username: @{lic['owner_username']}\n"
        f"🆔 Owner Telegram ID: <code>{lic['owner_telegram_id']}</code>\n"
        f"🔑 API Key: <code>{lic['api_key']}</code>\n"
        f"🖥 Machine ID: {lic['machine_id'] or '⬜ ثبت نشده'}\n"
        f"🌐 Server IP: {lic['server_ip'] or '⬜ ثبت نشده'}\n"
        f"📅 Created: {format_datetime(lic['created_at'])}\n"
        f"⏳ Expires: {format_datetime(lic['expires_at'])}\n"
        f"⌛ Remaining: {time_str}\n"
        f"🔖 Status: {status_icon}"
    )


def _send_or_edit(bot: telebot.TeleBot, call, text: str, kb) -> None:
    try:
        bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id,
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")


def register_admin_handlers(bot: telebot.TeleBot) -> None:

    # ── Panel entry ───────────────────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "⚙️ پنل مدیریت")
    def handle_admin_panel(message: telebot.types.Message) -> None:
        if not _is_admin(message.from_user.id):
            bot.send_message(message.chat.id, "❌ شما دسترسی ندارید.")
            return
        bot.send_message(
            message.chat.id,
            "⚙️ <b>پنل مدیریت</b>\n\nیکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML",
        )

    @bot.callback_query_handler(func=lambda c: c.data == "admin_back")
    def handle_admin_back(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        _send_or_edit(
            bot, call,
            "⚙️ <b>پنل مدیریت</b>\n\nیکی از گزینه‌ها را انتخاب کنید:",
            admin_panel_keyboard(),
        )
        bot.answer_callback_query(call.id)

    # ── Subscription text edit ────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_set_sub_text")
    def handle_set_sub_text(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        current = get_setting("subscription_text", "")
        set_state(call.from_user.id, States.ADMIN_WAITING_SUBSCRIPTION_TEXT)
        bot.send_message(
            call.message.chat.id,
            f"📝 <b>متن فعلی خرید اشتراک:</b>\n\n{current}\n\n"
            "✏️ <b>متن جدید را ارسال کنید</b> (یا /cancel برای لغو):",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    # ── Licenses list ─────────────────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data == "admin_licenses" or c.data.startswith("admin_lic_page_")
    )
    def handle_admin_licenses(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return

        page = 1
        if call.data.startswith("admin_lic_page_"):
            page = int(call.data.split("_")[-1])

        licenses, total = get_all_licenses(page, _LICENSES_PER_PAGE)
        total_pages = max(1, (total + _LICENSES_PER_PAGE - 1) // _LICENSES_PER_PAGE)
        text = (
            f"📋 <b>مدیریت لایسنس‌ها</b>\n"
            f"📊 تعداد کل: <b>{total}</b>  |  صفحه {page}/{total_pages}"
        )
        _send_or_edit(bot, call, text, licenses_panel_keyboard(licenses, page, total_pages))
        bot.answer_callback_query(call.id)

    # ── Add license wizard (start) ────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_add_license")
    def handle_add_license_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        set_state(call.from_user.id, States.ADMIN_WAITING_BOT_USERNAME, {})
        bot.send_message(
            call.message.chat.id,
            "➕ <b>افزودن لایسنس جدید</b>\n\n"
            "📍 مرحله <b>1 / 4</b>\n\n"
            "🤖 یوزرنیم ربات را وارد کنید:\n"
            "<i>(مثال: @mybot یا mybot)</i>\n\n"
            "/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    # ── License detail view ───────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_view_"))
    def handle_license_view(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        lic = get_license_by_id(license_id)
        if not lic:
            bot.answer_callback_query(call.id, "❌ لایسنس یافت نشد")
            return
        _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id))
        bot.answer_callback_query(call.id)

    # ── Disable ───────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_dis_"))
    def handle_disable(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        update_license_status(license_id, False, "disabled")
        bot.answer_callback_query(call.id, "✅ لایسنس غیرفعال شد")
        lic = get_license_by_id(license_id)
        if lic:
            _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id))

    # ── Enable ────────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_ena_"))
    def handle_enable(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        update_license_status(license_id, True, "active")
        bot.answer_callback_query(call.id, "✅ لایسنس فعال شد")
        lic = get_license_by_id(license_id)
        if lic:
            _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id))

    # ── Delete (confirm) ──────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_del_"))
    def handle_delete_confirm(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        kb = InlineKeyboardMarkup()
        kb.row(
            InlineKeyboardButton("✅ بله، حذف شود",  callback_data=f"admin_lic_cdel_{license_id}"),
            InlineKeyboardButton("❌ لغو",            callback_data=f"admin_lic_view_{license_id}"),
        )
        _send_or_edit(
            bot, call,
            f"⚠️ آیا مطمئن هستید که لایسنس <b>#{license_id}</b> حذف شود؟\n"
            "این عمل غیرقابل بازگشت است.",
            kb,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_cdel_"))
    def handle_delete_execute(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        delete_license(license_id)
        bot.answer_callback_query(call.id, "🗑 لایسنس حذف شد")
        licenses, total = get_all_licenses(1, _LICENSES_PER_PAGE)
        total_pages = max(1, (total + _LICENSES_PER_PAGE - 1) // _LICENSES_PER_PAGE)
        _send_or_edit(
            bot, call,
            f"📋 <b>مدیریت لایسنس‌ها</b>\n📊 تعداد کل: <b>{total}</b>",
            licenses_panel_keyboard(licenses, 1, total_pages),
        )

    # ── Rotate API Key ────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_rot_"))
    def handle_rotate(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        rotate_api_key(license_id)
        bot.answer_callback_query(call.id, "🔑 API Key جدید تولید شد")
        lic = get_license_by_id(license_id)
        if lic:
            _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id))

    # ── Extend (start wizard) ─────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_ext_"))
    def handle_extend_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_EXTEND_HOURS, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"🔁 <b>تمدید لایسنس #{license_id}</b>\n\n"
            "⏱ تعداد ساعت برای تمدید را وارد کنید:\n"
            "<i>(مثال: 720 = 30 روز)</i>\n\n/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    # ── Activation text ───────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_act_"))
    def handle_activation_text(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        lic = get_license_by_id(license_id)
        if not lic:
            bot.answer_callback_query(call.id, "❌ لایسنس یافت نشد")
            return

        api_url = get_setting("api_base_url", API_BASE_URL)
        text = (
            "📤 <b>متن آماده برای مشتری:</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 <b>API Key لایسنس شما:</b>\n"
            f"<code>{lic['api_key']}</code>\n\n"
            f"🌐 <b>API URL:</b>\n"
            f"<code>{api_url}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "برای فعال‌سازی ربات، این API Key را در تنظیمات ربات خود وارد کنید."
        )
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # ── Bots panel ────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_bots")
    def handle_admin_bots(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return

        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT bot_username,
                       COUNT(*) AS total,
                       SUM(CASE WHEN is_active = 1 AND expires_at > datetime('now') THEN 1 ELSE 0 END) AS active
                FROM licenses
                GROUP BY bot_username
                ORDER BY bot_username
                """
            ).fetchall()
        finally:
            conn.close()

        bots = [dict(r) for r in rows]
        text = f"🤖 <b>مدیریت ربات‌ها</b>\nتعداد ربات‌های ثبت‌شده: <b>{len(bots)}</b>"
        _send_or_edit(bot, call, text, bots_panel_keyboard(bots))
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_bot_view_"))
    def handle_bot_view(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return

        bot_username = call.data[len("admin_bot_view_"):]
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM licenses WHERE bot_username = ? ORDER BY created_at DESC",
                (bot_username,),
            ).fetchall()
        finally:
            conn.close()

        licenses = [dict(r) for r in rows]
        total_pages = max(1, (len(licenses) + _LICENSES_PER_PAGE - 1) // _LICENSES_PER_PAGE)
        _send_or_edit(
            bot, call,
            f"🤖 <b>لایسنس‌های @{bot_username}</b>\nتعداد: {len(licenses)}",
            licenses_panel_keyboard(licenses[:_LICENSES_PER_PAGE], 1, total_pages),
        )
        bot.answer_callback_query(call.id)
