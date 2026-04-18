import sqlite3
import os
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript("""
        -- ── Settings ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS settings (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Admins ────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS admins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username    TEXT,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Bots ──────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS bots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_username TEXT UNIQUE NOT NULL,
            description  TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Licenses ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS licenses (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_username       TEXT    NOT NULL,
            owner_username     TEXT    NOT NULL,
            owner_telegram_id  INTEGER NOT NULL,
            api_key            TEXT    UNIQUE NOT NULL,
            machine_id         TEXT,
            server_ip          TEXT,
            status             TEXT    DEFAULT 'active',
            is_active          INTEGER DEFAULT 1,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at         TIMESTAMP NOT NULL,
            last_notified_at   TIMESTAMP,
            updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_licenses_api_key
            ON licenses(api_key);

        CREATE INDEX IF NOT EXISTS idx_licenses_owner_id
            ON licenses(owner_telegram_id);

        -- ── Notification Log ──────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS notifications_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id        INTEGER NOT NULL,
            owner_telegram_id INTEGER NOT NULL,
            message           TEXT,
            sent_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_id) REFERENCES licenses(id) ON DELETE CASCADE
        );

        -- ── User States ───────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS states (
            telegram_id INTEGER PRIMARY KEY,
            state       TEXT,
            data        TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- ── Default Settings ──────────────────────────────────────────────
        INSERT OR IGNORE INTO settings (key, value) VALUES
            ('subscription_text',
             '🛒 برای خرید اشتراک و فعال‌سازی ربات خود با @Emad_Habibnia در تماس باشید.'),
            ('start_text',
             '🎯 به مرکز مدیریت لایسنس خوش آمدید!\n\nاز این ربات می‌توانید وضعیت لایسنس ربات‌های خود را مشاهده کنید.'),
            ('channel_url', 'https://t.me/your_channel');
        """)
        conn.commit()
        logger.info("Database initialized successfully at %s", DB_PATH)
    finally:
        conn.close()
