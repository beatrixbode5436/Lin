import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import Any

from database.db import get_connection

logger = logging.getLogger(__name__)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _generate_api_key() -> str:
    alphabet = string.ascii_letters + string.digits
    return "LK-" + "".join(secrets.choice(alphabet) for _ in range(40))


def _unique_api_key(conn) -> str:
    while True:
        key = _generate_api_key()
        if not conn.execute(
            "SELECT 1 FROM licenses WHERE api_key = ?", (key,)
        ).fetchone():
            return key


# ─── CRUD ────────────────────────────────────────────────────────────────────

def create_license(
    bot_username: str,
    owner_username: str,
    owner_telegram_id: int,
    duration_hours: int,
) -> dict:
    conn = get_connection()
    try:
        api_key = _unique_api_key(conn)
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=duration_hours)

        conn.execute(
            """
            INSERT INTO licenses
                (bot_username, owner_username, owner_telegram_id,
                 api_key, created_at, expires_at, status, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 1)
            """,
            (
                bot_username.lower().lstrip("@"),
                owner_username.lower().lstrip("@"),
                owner_telegram_id,
                api_key,
                now.isoformat(),
                expires_at.isoformat(),
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM licenses WHERE api_key = ?", (api_key,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_license_by_id(license_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE id = ?", (license_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_license_by_api_key(api_key: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE api_key = ?", (api_key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_licenses_by_owner(owner_telegram_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM licenses WHERE owner_telegram_id = ? ORDER BY created_at DESC",
            (owner_telegram_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_licenses(page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
    conn = get_connection()
    try:
        offset = (page - 1) * per_page
        rows = conn.execute(
            "SELECT * FROM licenses ORDER BY expires_at ASC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
        return [dict(r) for r in rows], total
    finally:
        conn.close()


def get_inactive_licenses(page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
    conn = get_connection()
    try:
        offset = (page - 1) * per_page
        rows = conn.execute(
            "SELECT * FROM licenses WHERE is_active = 0 ORDER BY expires_at ASC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM licenses WHERE is_active = 0"
        ).fetchone()[0]
        return [dict(r) for r in rows], total
    finally:
        conn.close()


def update_license_field(license_id: int, field: str, value: str) -> dict | None:
    allowed = {"bot_username", "owner_username", "owner_telegram_id"}
    if field not in allowed:
        raise ValueError(f"Field '{field}' is not editable")
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE licenses SET {field} = ?, updated_at = ? WHERE id = ?",
            (value, datetime.utcnow().isoformat(), license_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def adjust_license_hours(license_id: int, hours: int) -> dict | None:
    """Add (hours > 0) or subtract (hours < 0) from license expiry."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE id = ?", (license_id,)
        ).fetchone()
        if not row:
            return None
        now = datetime.utcnow()
        current_expiry = datetime.fromisoformat(row["expires_at"])
        new_expiry = current_expiry + timedelta(hours=hours)
        conn.execute(
            "UPDATE licenses SET expires_at = ?, updated_at = ? WHERE id = ?",
            (new_expiry.isoformat(), now.isoformat(), license_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_license_status(license_id: int, is_active: bool, status: str | None = None) -> None:
    if status is None:
        status = "active" if is_active else "disabled"
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE licenses SET is_active = ?, status = ?, updated_at = ? WHERE id = ?",
            (1 if is_active else 0, status, datetime.utcnow().isoformat(), license_id),
        )
        conn.commit()
    finally:
        conn.close()


def extend_license(license_id: int, hours: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE id = ?", (license_id,)
        ).fetchone()
        if not row:
            return None

        now = datetime.utcnow()
        current_expiry = datetime.fromisoformat(row["expires_at"])
        base = max(now, current_expiry)
        new_expiry = base + timedelta(hours=hours)

        conn.execute(
            """
            UPDATE licenses
            SET expires_at = ?, status = 'active', is_active = 1, updated_at = ?
            WHERE id = ?
            """,
            (new_expiry.isoformat(), now.isoformat(), license_id),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM licenses WHERE id = ?", (license_id,)
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_license(license_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
        conn.commit()
    finally:
        conn.close()


def rotate_api_key(license_id: int) -> str:
    conn = get_connection()
    try:
        new_key = _unique_api_key(conn)
        conn.execute(
            "UPDATE licenses SET api_key = ?, machine_id = NULL, updated_at = ? WHERE id = ?",
            (new_key, datetime.utcnow().isoformat(), license_id),
        )
        conn.commit()
        return new_key
    finally:
        conn.close()


# ─── API Operations ───────────────────────────────────────────────────────────

def activate_license(
    api_key: str,
    bot_username: str,
    owner_telegram_id: Any,
    owner_username: str,
    machine_id: str,
    server_ip: str | None = None,
) -> dict:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE api_key = ?", (api_key,)
        ).fetchone()

        if not row:
            return {
                "ok": False, "is_licensed": False, "status": "not_found",
                "message": "License not found",
                "expires_at": None, "remaining_hours": 0,
            }

        lic = dict(row)

        if lic["bot_username"] != bot_username.lower().lstrip("@"):
            return _mismatch_response("Bot username mismatch")

        if lic["owner_username"] != owner_username.lower().lstrip("@"):
            return _mismatch_response("Owner username mismatch")

        if not lic["is_active"]:
            return {
                "ok": True, "is_licensed": False, "status": "disabled",
                "message": "License is disabled",
                "expires_at": lic["expires_at"], "remaining_hours": 0,
            }

        now = datetime.utcnow()
        expires_at = datetime.fromisoformat(lic["expires_at"])
        if now > expires_at:
            conn.execute(
                "UPDATE licenses SET status = 'expired' WHERE id = ?", (lic["id"],)
            )
            conn.commit()
            return {
                "ok": True, "is_licensed": False, "status": "expired",
                "message": "License has expired",
                "expires_at": lic["expires_at"], "remaining_hours": 0,
            }

        if not lic["machine_id"]:
            conn.execute(
                "UPDATE licenses SET machine_id = ?, server_ip = ?, status = 'active', updated_at = ? WHERE id = ?",
                (machine_id, server_ip, now.isoformat(), lic["id"]),
            )
            conn.commit()
        elif lic["machine_id"] != machine_id:
            return {
                "ok": False, "is_licensed": False, "status": "machine_mismatch",
                "message": "Machine ID mismatch",
                "expires_at": lic["expires_at"], "remaining_hours": 0,
            }

        remaining_hours = int((expires_at - now).total_seconds() / 3600)
        return {
            "ok": True, "is_licensed": True, "status": "active",
            "message": "License is valid and active",
            "expires_at": lic["expires_at"],
            "remaining_hours": remaining_hours,
        }
    finally:
        conn.close()


def check_license(
    api_key: str,
    bot_username: str,
    owner_telegram_id: Any,
    owner_username: str,
    machine_id: str,
) -> dict:
    from services.settings_service import get_setting

    subscription_text = get_setting(
        "subscription_text",
        "برای خرید اشتراک با @Emad_Habibnia در تماس باشید.",
    )

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM licenses WHERE api_key = ?", (api_key,)
        ).fetchone()

        if not row:
            return _check_fail(
                "not_found", "License not found",
                "❌ لایسنس یافت نشد", subscription_text,
            )

        lic = dict(row)

        if lic["bot_username"] != bot_username.lower().lstrip("@"):
            return _check_fail("mismatch", "Bot username mismatch",
                               "❌ خطا در تطبیق اطلاعات ربات", subscription_text)

        if lic["owner_username"] != owner_username.lower().lstrip("@"):
            return _check_fail("mismatch", "Owner username mismatch",
                               "❌ خطا در تطبیق یوزرنیم مالک", subscription_text)

        if not lic["is_active"]:
            return {
                "ok": True, "is_licensed": False, "status": "disabled",
                "expires_at": lic["expires_at"], "remaining_hours": 0,
                "message": "License is disabled",
                "public_disabled_text": "🚫 لایسنس شما غیرفعال است",
                "notify_text": get_expiry_notify_text(),
                "subscription_text": subscription_text,
            }

        now = datetime.utcnow()
        expires_at = datetime.fromisoformat(lic["expires_at"])

        if now > expires_at:
            conn.execute(
                "UPDATE licenses SET status = 'expired' WHERE id = ?", (lic["id"],)
            )
            conn.commit()
            return {
                "ok": True, "is_licensed": False, "status": "expired",
                "expires_at": lic["expires_at"], "remaining_hours": 0,
                "message": "License has expired",
                "public_disabled_text": "🚫 لایسنس شما منقضی شده است",
                "notify_text": get_expiry_notify_text(),
                "subscription_text": subscription_text,
            }

        if lic["machine_id"] and lic["machine_id"] != machine_id:
            return _check_fail(
                "machine_mismatch", "Machine ID mismatch",
                "❌ شناسه دستگاه تطابق ندارد", subscription_text,
                expires_at=lic["expires_at"],
            )

        remaining_hours = int((expires_at - now).total_seconds() / 3600)
        return {
            "ok": True, "is_licensed": True, "status": "active",
            "expires_at": lic["expires_at"],
            "remaining_hours": remaining_hours,
            "message": "License is valid",
            "public_disabled_text": "",
            "notify_text": "",
            "subscription_text": subscription_text,
        }
    finally:
        conn.close()


def get_expiry_notify_text() -> str:
    return (
        "🚫 لایسنس ربات شما به پایان رسیده و ربات در حال حاضر خاموش است.\n\n"
        "برای تمدید، دیگر وقتشه رباتت رو به Seamless Premium ارتقا بدی 🚀\n"
        "ربات با کلی امکانات\n\n"
        "برای اطلاعات بیشتر و خرید اشتراک به @Emad_Habibnia پیام بدهید."
    )


def get_expired_licenses_for_notification() -> list[dict]:
    conn = get_connection()
    try:
        now = datetime.utcnow()
        one_hour_ago = (now - timedelta(hours=1)).isoformat()
        rows = conn.execute(
            """
            SELECT * FROM licenses
            WHERE (status = 'expired' OR is_active = 0 OR expires_at < ?)
              AND (last_notified_at IS NULL OR last_notified_at < ?)
            """,
            (now.isoformat(), one_hour_ago),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_last_notified(license_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE licenses SET last_notified_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), license_id),
        )
        conn.commit()
    finally:
        conn.close()


# ─── Private Helpers ─────────────────────────────────────────────────────────

def _mismatch_response(message: str) -> dict:
    return {
        "ok": False, "is_licensed": False, "status": "mismatch",
        "message": message, "expires_at": None, "remaining_hours": 0,
    }


def _check_fail(
    status: str,
    message: str,
    public_text: str,
    subscription_text: str,
    expires_at: str | None = None,
) -> dict:
    return {
        "ok": False, "is_licensed": False, "status": status,
        "expires_at": expires_at, "remaining_hours": 0,
        "message": message,
        "public_disabled_text": public_text,
        "notify_text": "",
        "subscription_text": subscription_text,
    }
