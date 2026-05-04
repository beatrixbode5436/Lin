import logging
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS
from bot.keyboards.admin_kb import forward_panel_keyboard
from bot.states import States, get_state, set_state, clear_state
from services.license_service import (
    get_all_user_telegram_ids,
    get_licensed_user_telegram_ids,
    get_unlicensed_user_telegram_ids,
)

logger = logging.getLogger(__name__)

_FORWARD_TARGET_KEY = "forward_target"  # stored in state data


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


def _do_broadcast(
    bot: telebot.TeleBot,
    admin_chat_id: int,
    target_ids: list[int],
    from_chat_id: int,
    message_id: int,
) -> None:
    """Forward a message to all target_ids and report results."""
    sent = 0
    failed = 0
    for uid in target_ids:
        try:
            bot.forward_message(uid, from_chat_id, message_id)
            sent += 1
            time.sleep(0.05)  # Avoid flood
        except Exception as exc:
            logger.warning("Forward to %s failed: %s", uid, exc)
            failed += 1

    bot.send_message(
        admin_chat_id,
        f"✅ <b>فوروارد کامل شد</b>\n\n"
        f"📤 ارسال شد: <b>{sent}</b>\n"
        f"❌ ناموفق: <b>{failed}</b>",
        parse_mode="HTML",
    )


def register_admin_forward_handlers(bot: telebot.TeleBot) -> None:

    # ── Panel entry ───────────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "admin_forward")
    def handle_forward_panel(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return
        _send_or_edit(
            bot, call,
            "📢 <b>ارسال پیام همگانی</b>\n\n"
            "پیام برای چه کسانی ارسال شود؟",
            forward_panel_keyboard(),
        )
        bot.answer_callback_query(call.id)

    # ── Target selection ──────────────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data in (
        "admin_fwd_all", "admin_fwd_licensed", "admin_fwd_unlicensed"
    ))
    def handle_forward_target(call: telebot.types.CallbackQuery) -> None:
        if not _is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ دسترسی ندارید")
            return

        target_map = {
            "admin_fwd_all":        ("همه کاربران",           "all"),
            "admin_fwd_licensed":   ("دارندگان لاینسس",       "licensed"),
            "admin_fwd_unlicensed": ("کاربران بدون لاینسس",   "unlicensed"),
        }
        label, target = target_map[call.data]

        set_state(call.from_user.id, States.ADMIN_WAITING_FORWARD_MSG, {"target": target})

        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 لغو", callback_data="admin_forward"))

        bot.send_message(
            call.message.chat.id,
            f"📢 <b>ارسال برای: {label}</b>\n\n"
            "پیامی که می‌خواهید فوروارد شود را ارسال کنید.\n"
            "<i>(هر نوع پیام: متن، عکس، ویدیو، ...)</i>\n\n"
            "/cancel برای لغو",
            parse_mode="HTML",
            reply_markup=kb,
        )
        bot.answer_callback_query(call.id)

    # ── Message capture and broadcast ─────────────────────────────────────────

    @bot.message_handler(
        content_types=["text", "photo", "video", "document", "audio", "voice", "sticker", "animation"],
        func=lambda m: get_state(m.from_user.id)[0] == States.ADMIN_WAITING_FORWARD_MSG,
    )
    def handle_forward_message(message: telebot.types.Message) -> None:
        if not _is_admin(message.from_user.id):
            return

        state, data = get_state(message.from_user.id)
        target = data.get("target", "all")

        if message.text and message.text.strip() == "/cancel":
            clear_state(message.from_user.id)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_forward"))
            bot.send_message(message.chat.id, "❌ ارسال لغو شد.", reply_markup=kb)
            return

        clear_state(message.from_user.id)

        target_label_map = {
            "all":        "همه کاربران",
            "licensed":   "دارندگان لاینسس",
            "unlicensed": "کاربران بدون لاینسس",
        }
        label = target_label_map.get(target, target)

        if target == "all":
            ids = get_all_user_telegram_ids()
        elif target == "licensed":
            ids = get_licensed_user_telegram_ids()
        else:
            ids = get_unlicensed_user_telegram_ids()

        if not ids:
            bot.send_message(message.chat.id, f"❌ هیچ کاربری در گروه «{label}» یافت نشد.")
            return

        bot.send_message(
            message.chat.id,
            f"⏳ <b>در حال ارسال به {len(ids)} کاربر ({label})...</b>",
            parse_mode="HTML",
        )

        _do_broadcast(bot, message.chat.id, ids, message.chat.id, message.message_id)
