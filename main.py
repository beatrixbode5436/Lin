"""
License Center – Entry Point
Starts three concurrent components:
  1. Flask API server   (background thread)
  2. Notification scheduler (background thread)
  3. Telegram bot polling (main thread)
  4. Auto-backup scheduler (background thread)
"""
import logging
import os
import shutil
import time
import threading

import telebot

# ── Logging setup (must be first) ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Project imports ───────────────────────────────────────────────────────────
from config import BOT_TOKEN, API_HOST, API_PORT, DB_PATH
from database.db import init_db
from bot.handlers import register_handlers
from api.routes import create_app
from services.notification_service import start_notification_scheduler
from services.settings_service import get_setting


def _run_flask() -> None:
    app = create_app()
    logger.info("Flask API starting on %s:%s", API_HOST, API_PORT)
    # Use werkzeug's built-in server; replace with gunicorn in production
    app.run(host=API_HOST, port=API_PORT, debug=False, use_reloader=False)


def _run_notifications() -> None:
    start_notification_scheduler()


def _run_auto_backup(bot: telebot.TeleBot) -> None:
    """Check every minute if it's time to send an auto-backup."""
    while True:
        try:
            interval_str = get_setting("backup_interval_hours", "0")
            interval = int(interval_str) if interval_str and interval_str.isdigit() else 0
            if interval > 0:
                dest = get_setting("backup_dest", "")
                if dest:
                    target = int(dest) if dest.lstrip("-").isdigit() else dest
                    ts = __import__("datetime").datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    backup_copy = f"/tmp/license_autobackup_{ts}.db"
                    shutil.copy2(DB_PATH, backup_copy)
                    with open(backup_copy, "rb") as f:
                        bot.send_document(target, f, caption=f"💾 بکاپ خودکار - {ts}")
                    os.remove(backup_copy)
                    logger.info("Auto-backup sent to %s", dest)
            time.sleep(interval * 3600 if interval > 0 else 3600)
        except Exception as e:
            logger.error("Auto-backup error: %s", e)
            time.sleep(3600)


def main() -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set in .env – aborting.")
        raise SystemExit(1)

    # Init database
    init_db()

    # Flask API thread
    flask_thread = threading.Thread(target=_run_flask, name="flask-api", daemon=True)
    flask_thread.start()

    # Notification scheduler thread
    notif_thread = threading.Thread(
        target=_run_notifications, name="notif-scheduler", daemon=True
    )
    notif_thread.start()

    # Telegram bot (main thread)
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    register_handlers(bot)

    # Auto-backup thread
    backup_thread = threading.Thread(
        target=_run_auto_backup, args=(bot,), name="auto-backup", daemon=True
    )
    backup_thread.start()

    logger.info("Telegram bot starting (polling)…")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)


if __name__ == "__main__":
    main()
