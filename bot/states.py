import json
import logging
from datetime import datetime
from database.db import get_connection

logger = logging.getLogger(__name__)


class States:
    # ── Admin Wizard: Add License ─────────────────────────────────────────────
    ADMIN_WAITING_BOT_USERNAME   = "admin_waiting_bot_username"
    ADMIN_WAITING_OWNER_USERNAME = "admin_waiting_owner_username"
    ADMIN_WAITING_OWNER_ID       = "admin_waiting_owner_id"
    ADMIN_WAITING_DURATION       = "admin_waiting_duration"

    # ── Admin Wizard: Extend License ──────────────────────────────────────────
    ADMIN_WAITING_EXTEND_HOURS   = "admin_waiting_extend_hours"

    # ── Admin: Edit Settings ──────────────────────────────────────────────────
    ADMIN_WAITING_SUBSCRIPTION_TEXT = "admin_waiting_subscription_text"
    ADMIN_WAITING_START_TEXT        = "admin_waiting_start_text"


def get_state(telegram_id: int) -> tuple[str | None, dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT state, data FROM states WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if row:
            return row["state"], json.loads(row["data"]) if row["data"] else {}
        return None, {}
    finally:
        conn.close()


def set_state(telegram_id: int, state: str, data: dict | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO states (telegram_id, state, data, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                state      = excluded.state,
                data       = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                telegram_id,
                state,
                json.dumps(data or {}),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def clear_state(telegram_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM states WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
    finally:
        conn.close()
