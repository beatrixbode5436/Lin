import logging
import os
import shutil
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, API_BASE_URL, DB_PATH
from bot.keyboards.admin_kb import (
    admin_panel_keyboard,
    licenses_panel_keyboard,
    license_detail_keyboard,
    license_time_management_keyboard,
    license_edit_keyboard,
    bots_panel_keyboard,
    backup_panel_keyboard,
)
from bot.states import States, get_state, set_state, clear_state
from services.license_service import (
    get_all_licenses,
    get_inactive_licenses,
    get_license_by_id,
    update_license_status,
    update_license_field,
    delete_license,
    rotate_api_key,
    adjust_license_hours,
    search_licenses,
    set_license_time,
)
from services.settings_service import get_setting, set_setting
from database.db import get_connection
from utils.helpers import calculate_remaining, format_datetime, shamsi_day_of_month
from datetime import datetime

logger = logging.getLogger(__name__)

_LICENSES_PER_PAGE = 10


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def _do_send_backup(bot: telebot.TeleBot, chat_id: int) -> None:
    """Send current DB file as a document to chat_id."""
    try:
        dest = get_setting("backup_dest", "")
        target = int(dest) if dest and dest.lstrip("-").isdigit() else (dest if dest else chat_id)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_copy = f"/tmp/license_backup_{ts}.db"
        shutil.copy2(DB_PATH, backup_copy)
        with open(backup_copy, "rb") as f:
            bot.send_document(target, f, caption=f"💾 بکاپ دیتابیس - {ts}")
        os.remove(backup_copy)
        if target != chat_id:
            bot.send_message(chat_id, f"✅ بکاپ به مقصد <code>{dest}</code> ارسال شد.", parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطا در ارسال بکاپ: {e}")


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

    @bot.callback_query_handler(func=lambda c: c.data in ("main_admin", "admin_back"))
    def handle_admin_panel(call: telebot.types.CallbackQuery) -> None:
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

    # ── Search licenses ───────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_lic_search")
    def handle_search_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        set_state(call.from_user.id, States.ADMIN_WAITING_SEARCH_QUERY, {})
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_licenses"))
        bot.send_message(
            call.message.chat.id,
            "🔍 <b>جستجوی لایسنس</b>\n\n"
            "عبارت جستجو را وارد کنید:\n"
            "• آیدی عددی لایسنس یا صاحب\n"
            "• یوزرنیم صاحب (بدون @)\n"
            "• یوزرنیم ربات (بدون @)\n\n"
            "/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_search_page_"))
    def handle_search_page(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        parts = call.data.split("_")
        page = int(parts[-1])
        _, state_data = get_state(call.from_user.id)
        query = state_data.get("search_query", "")
        if not query:
            bot.answer_callback_query(call.id, "❌ جستجو منقضی شده")
            return
        licenses, total = search_licenses(query, page, _LICENSES_PER_PAGE)
        total_pages = max(1, (total + _LICENSES_PER_PAGE - 1) // _LICENSES_PER_PAGE)
        _send_or_edit(
            bot, call,
            f"🔍 <b>نتایج جستجو: «{query}»</b>\n📊 تعداد: <b>{total}</b>  |  صفحه {page}/{total_pages}",
            licenses_panel_keyboard(licenses, page, total_pages, search_mode=True),
        )
        bot.answer_callback_query(call.id)

    # ── Page jump ─────────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_goto_page_"))
    def handle_goto_page_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        prefix = call.data[len("admin_lic_goto_page_"):]
        set_state(call.from_user.id, States.ADMIN_WAITING_PAGE_JUMP, {"prefix": prefix})
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 لغو", callback_data="admin_licenses"))
        bot.send_message(
            call.message.chat.id,
            "📄 شماره صفحه مورد نظر را وارد کنید:",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    # ── Inactive licenses list ────────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("admin_inactive_licenses_") or c.data.startswith("admin_inactive_lic_page_")
    )
    def handle_inactive_licenses(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return

        page = int(call.data.split("_")[-1])
        licenses, total = get_inactive_licenses(page, _LICENSES_PER_PAGE)
        total_pages = max(1, (total + _LICENSES_PER_PAGE - 1) // _LICENSES_PER_PAGE)
        text = (
            f"🔴 <b>لایسنس‌های غیرفعال</b>\n"
            f"📊 تعداد: <b>{total}</b>  |  صفحه {page}/{total_pages}"
        )
        _send_or_edit(
            bot, call, text,
            licenses_panel_keyboard(licenses, page, total_pages, inactive_mode=True),
        )
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
        _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id, bool(lic["is_active"])))
        bot.answer_callback_query(call.id)

    # ── Toggle activate/deactivate ────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_toggle_"))
    def handle_toggle(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        lic = get_license_by_id(license_id)
        if not lic:
            bot.answer_callback_query(call.id, "❌ لایسنس یافت نشد")
            return
        new_active = not bool(lic["is_active"])
        update_license_status(license_id, new_active)
        msg = "✅ لایسنس فعال شد" if new_active else "🔴 لایسنس غیرفعال شد"
        bot.answer_callback_query(call.id, msg)
        lic = get_license_by_id(license_id)
        if lic:
            _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id, bool(lic["is_active"])))

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
            _send_or_edit(bot, call, _license_detail_text(lic), license_detail_keyboard(license_id, bool(lic["is_active"])))

    # ── Time management ───────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_time_"))
    def handle_time_management(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        lic = get_license_by_id(license_id)
        if not lic:
            bot.answer_callback_query(call.id, "❌ لایسنس یافت نشد")
            return
        _, time_str = calculate_remaining(lic["expires_at"])
        _send_or_edit(
            bot, call,
            f"🕐 <b>مدیریت زمان لایسنس #{license_id}</b>\n\n"
            f"⌛ زمان باقی‌مانده: <b>{time_str}</b>\n\n"
            "یک گزینه انتخاب کنید:",
            license_time_management_keyboard(license_id),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_add_hours_"))
    def handle_add_hours_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_ADD_HOURS, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"➕ <b>اضافه کردن ساعت به لایسنس #{license_id}</b>\n\n"
            "⏱ تعداد ساعت را وارد کنید:\n<i>(مثال: 720 = 30 روز)</i>\n\n/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_sub_hours_"))
    def handle_sub_hours_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_SUB_HOURS, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"➖ <b>کم کردن ساعت از لایسنس #{license_id}</b>\n\n"
            "⏱ تعداد ساعت را وارد کنید:\n<i>(مثال: 24 = 1 روز)</i>\n\n/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_set_hours_"))
    def handle_set_hours_start(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_SET_HOURS, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"⏱ <b>ست کردن زمان دقیق لایسنس #{license_id}</b>\n\n"
            "تعداد ساعت از الان را وارد کنید:\n"
            "<i>(مثال: 720 = دقیقاً 30 روز از الان)</i>\n\n/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    # ── Edit fields ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_edit_") and not any(
        c.data.startswith(f"admin_lic_edit_{x}_") for x in ("oun", "oid", "bun")
    ))
    def handle_edit_menu(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        lic = get_license_by_id(license_id)
        if not lic:
            bot.answer_callback_query(call.id, "❌ لایسنس یافت نشد")
            return
        _send_or_edit(
            bot, call,
            f"✏️ <b>ویرایش لایسنس #{license_id}</b>\n\n"
            f"🤖 Bot: @{lic['bot_username']}\n"
            f"👤 Owner: @{lic['owner_username']}\n"
            f"🆔 ID: <code>{lic['owner_telegram_id']}</code>\n\n"
            "کدام فیلد را ویرایش می‌کنید؟",
            license_edit_keyboard(license_id),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_edit_oun_"))
    def handle_edit_owner_username(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_EDIT_OWNER_USERNAME, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"👤 <b>ویرایش یوزرنیم خریدار - لایسنس #{license_id}</b>\n\n"
            "یوزرنیم جدید را وارد کنید:\n/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_edit_oid_"))
    def handle_edit_owner_id(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_EDIT_OWNER_ID, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"🆔 <b>ویرایش آیدی عددی خریدار - لایسنس #{license_id}</b>\n\n"
            "آیدی عددی جدید را وارد کنید:\n/cancel برای لغو",
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin_lic_edit_bun_"))
    def handle_edit_bot_username(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        license_id = int(call.data.split("_")[-1])
        set_state(call.from_user.id, States.ADMIN_WAITING_EDIT_BOT_USERNAME, {"license_id": license_id})
        bot.send_message(
            call.message.chat.id,
            f"🤖 <b>ویرایش یوزرنیم ربات - لایسنس #{license_id}</b>\n\n"
            "یوزرنیم جدید ربات را وارد کنید:\n/cancel برای لغو",
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

        try:
            expiry_dt = datetime.fromisoformat(lic["expires_at"])
            gregorian_day = expiry_dt.day
            jalali_day = shamsi_day_of_month(expiry_dt)
        except Exception:
            gregorian_day = "؟"
            jalali_day = "؟"

        text = (
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
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # ── Backup panel ──────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_backup")
    def handle_backup_panel(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        interval = get_setting("backup_interval_hours", "0")
        dest = get_setting("backup_dest", "تنظیم نشده")
        _send_or_edit(
            bot, call,
            f"💾 <b>مدیریت بکاپ</b>\n\n"
            f"⏰ بازه خودکار: <b>{interval} ساعت</b> (0 = غیرفعال)\n"
            f"📬 مقصد: <code>{dest}</code>\n\n"
            "یک گزینه انتخاب کنید:",
            backup_panel_keyboard(),
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_backup_now")
    def handle_backup_now(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        bot.answer_callback_query(call.id, "⏳ در حال ارسال بکاپ...")
        _do_send_backup(bot, call.message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_backup_restore")
    def handle_backup_restore(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_backup"))
        bot.send_message(
            call.message.chat.id,
            "♻️ <b>بازیابی بکاپ</b>\n\n"
            "فایل بکاپ (db) را به عنوان Document ارسال کنید.\n\n/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=kb,
        )
        set_state(call.from_user.id, "admin_waiting_backup_file", {})
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_backup_set_interval")
    def handle_backup_set_interval(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        set_state(call.from_user.id, States.ADMIN_WAITING_BACKUP_INTERVAL, {})
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_backup"))
        bot.send_message(
            call.message.chat.id,
            "⏰ <b>بازه بکاپ خودکار</b>\n\n"
            "تعداد ساعت بین هر بکاپ را وارد کنید:\n"
            "<i>(0 برای غیرفعال کردن)</i>\n\n/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "admin_backup_set_dest")
    def handle_backup_set_dest(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        set_state(call.from_user.id, States.ADMIN_WAITING_BACKUP_DEST, {})
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_backup"))
        bot.send_message(
            call.message.chat.id,
            "📬 <b>مقصد بکاپ خودکار</b>\n\n"
            "آیدی عددی یا آدرس کانال مقصد را وارد کنید:\n"
            "<i>(مثال: @mychannel یا 123456789)</i>\n\n/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    # ── Document handler for backup restore ───────────────────────────────────

    @bot.message_handler(
        content_types=["document"],
        func=lambda m: get_state(m.from_user.id)[0] == "admin_waiting_backup_file",
    )
    def handle_backup_file(message: telebot.types.Message) -> None:
        if not _is_admin(message.from_user.id):
            clear_state(message.from_user.id)
            return
        clear_state(message.from_user.id)
        try:
            file_info = bot.get_file(message.document.file_id)
            file_bytes = bot.download_file(file_info.file_path)
            backup_path = DB_PATH + ".restore_backup"
            shutil.copy2(DB_PATH, backup_path)
            with open(DB_PATH, "wb") as f:
                f.write(file_bytes)
            bot.send_message(message.chat.id, "✅ بکاپ با موفقیت بازیابی شد. ربات را ریستارت کنید.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطا در بازیابی: {e}")


