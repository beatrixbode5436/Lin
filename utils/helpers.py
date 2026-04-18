from datetime import datetime


def calculate_remaining(expires_at_str: str) -> tuple[int, str]:
    """Return (total_hours, human_readable_str)."""
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        delta = expires_at - datetime.utcnow()
        if delta.total_seconds() <= 0:
            return 0, "منقضی شده"
        total_hours = int(delta.total_seconds() / 3600)
        days, rem_hours = divmod(total_hours, 24)
        if days > 0:
            return total_hours, f"{days}d {rem_hours}h"
        return total_hours, f"{total_hours}h"
    except Exception:
        return 0, "نامشخص"


def format_datetime(dt_str: str) -> str:
    try:
        return datetime.fromisoformat(dt_str).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str or "نامشخص"


def sanitize_username(username: str) -> str:
    return username.strip().lower().lstrip("@") if username else ""


def is_valid_telegram_id(value: str) -> bool:
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False


def paginate(items: list, page: int, per_page: int = 5) -> tuple[list, int]:
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    start = (page - 1) * per_page
    return items[start : start + per_page], total_pages
