from datetime import datetime

try:
    import jdatetime as _jdatetime
    _HAS_JDATETIME = True
except ImportError:
    _HAS_JDATETIME = False


def _gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Minimal Gregorian → Jalali conversion (fallback if jdatetime not installed)."""
    g_d_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm - 1):
        g_d_no += [31,28 + (1 if gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0) else 0),31,30,31,30,31,31,30,31,30,31][i]
    g_d_no += gd - 1
    j_d_no = g_d_no - 79
    j_np = j_d_no // 12053
    j_d_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_d_no // 1461)
    j_d_no %= 1461
    if j_d_no >= 366:
        jy += (j_d_no - 1) // 365
        j_d_no = (j_d_no - 1) % 365
    for i, v in enumerate([31,31,31,31,31,31,30,30,30,30,30,29]):
        if j_d_no >= v:
            j_d_no -= v
        else:
            jm = i + 1
            jd = j_d_no + 1
            break
    else:
        jm, jd = 12, j_d_no + 1
    return jy, jm, jd


def shamsi_day_of_month(dt: datetime) -> int:
    """Return the day of month in Jalali (Shamsi) calendar."""
    if _HAS_JDATETIME:
        return _jdatetime.datetime.fromgregorian(datetime=dt).day
    _, _, jd = _gregorian_to_jalali(dt.year, dt.month, dt.day)
    return jd


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
