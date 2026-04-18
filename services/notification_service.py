import time
import logging
import telebot

from config import BOT_TOKEN, NOTIFICATION_INTERVAL
from services.license_service import (
    get_expired_licenses_for_notification,
    update_last_notified,
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


def start_notification_scheduler() -> None:
    logger.info(
        "Notification scheduler started (interval=%ss)", NOTIFICATION_INTERVAL
    )
    while True:
        try:
            send_notifications()
        except Exception as exc:
            logger.error("Notification scheduler error: %s", exc)
        time.sleep(NOTIFICATION_INTERVAL)
