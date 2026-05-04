import time
import logging
import telebot
from datetime import datetime

from config import BOT_TOKEN, NOTIFICATION_INTERVAL, AUTO_DEACTIVATE_HOURS
from services.license_service import (
    get_expired_licenses_for_notification,
    get_licenses_to_auto_deactivate,
    update_last_notified,
    update_license_status,
    get_expiry_notify_text,
)
from database.db import get_connection

logger = logging.getLogger(__name__)


def _get_sender_bot() -> telebot.TeleBot:
    """Create a send-only bot instance (no polling)."""
    return telebot.TeleBot(BOT_TOKEN, threaded=False)


def send_notifications() -> None:
    licenses = get_expired_licenses_for_notification()
    if not licenses:
        return

    bot = _get_sender_bot()
    notify_text = get_expiry_notify_text()

    for lic in licenses:
        try:
            bot.send_message(
                lic["owner_telegram_id"],
                notify_text,
            )
            update_last_notified(lic["id"])

            # Log the notification
            conn = get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO notifications_log (license_id, owner_telegram_id, message)
                    VALUES (?, ?, ?)
                    """,
                    (lic["id"], lic["owner_telegram_id"], notify_text),
                )
                conn.commit()
            finally:
                conn.close()

            logger.info(
                "Notification sent to %s for license #%s",
                lic["owner_telegram_id"],
                lic["id"],
            )
        except Exception as exc:
            logger.error(
                "Failed to notify owner %s for license #%s: %s",
                lic["owner_telegram_id"],
                lic["id"],
                exc,
            )


def run_auto_deactivations() -> None:
    """Permanently deactivate licenses that have been expired for AUTO_DEACTIVATE_HOURS hours."""
    licenses = get_licenses_to_auto_deactivate(hours=AUTO_DEACTIVATE_HOURS)
    if not licenses:
        return

    bot = _get_sender_bot()

    for lic in licenses:
        try:
            update_license_status(lic["id"], is_active=False, status="expired")
            text = (
                f"🔴 ربات <b>@{lic['bot_username']}</b> غیرفعال شد\n\n"
                f"لایسنس شما بیش از {AUTO_DEACTIVATE_HOURS} ساعت است که منقضی شده "
                f"و به همین دلیل ربات به‌طور کامل غیرفعال گردید.\n\n"
                f"🔄 برای تمدید و فعال‌سازی مجدد با پشتیبانی در تماس باشید."
            )
            bot.send_message(lic["owner_telegram_id"], text, parse_mode="HTML")

            conn = get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO notifications_log (license_id, owner_telegram_id, message)
                    VALUES (?, ?, ?)
                    """,
                    (lic["id"], lic["owner_telegram_id"], text),
                )
                conn.commit()
            finally:
                conn.close()

            logger.info(
                "Auto-deactivated license #%s (bot=%s, owner=%s) after %sh expiry",
                lic["id"],
                lic["bot_username"],
                lic["owner_telegram_id"],
                AUTO_DEACTIVATE_HOURS,
            )
        except Exception as exc:
            logger.error(
                "Failed to auto-deactivate license #%s: %s",
                lic["id"],
                exc,
            )


def start_notification_scheduler() -> None:
    logger.info(
        "Notification scheduler started (interval=%ss, auto_deactivate_after=%sh)",
        NOTIFICATION_INTERVAL,
        AUTO_DEACTIVATE_HOURS,
    )
    while True:
        try:
            send_notifications()
        except Exception as exc:
            logger.error("Expiry notification error: %s", exc)
        try:
            run_auto_deactivations()
        except Exception as exc:
            logger.error("Auto-deactivation error: %s", exc)
        time.sleep(NOTIFICATION_INTERVAL)
