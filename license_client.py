"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ماژول چک لاینسس — برای استفاده در ربات مشتری
  این فایل را در پروژه ربات خود کپی کنید.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

تنظیمات:
  LICENSE_API_URL  → آدرس سرور لاینسس شما
  API_KEY          → کلید لاینسس دریافتی از ادمین
  BOT_USERNAME     → یوزرنیم ربات (بدون @)

نحوه استفاده در ربات:
  from license_client import is_licensed, start_license_checker

  # در ابتدای ربات، چکر رو شروع کن:
  start_license_checker()

  # در هر هندلر ورودی چک کن:
  if not is_licensed():
      return   # بدون هیچ پیامی به کاربر نادیده بگیر
"""

import threading
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ─── تنظیمات — اینجا رو تغییر بده ─────────────────────────────────────────
LICENSE_API_URL: str = "http://YOUR_SERVER_IP:5000"   # آدرس سرور لاینسس
API_KEY: str         = "LK-YOUR_API_KEY_HERE"          # کلید لاینسس
BOT_USERNAME: str    = "your_bot_username"              # یوزرنیم ربات (بدون @)

CHECK_INTERVAL: int  = 15 * 60    # هر ۱۵ دقیقه یک‌بار چک (ثانیه)
REQUEST_TIMEOUT: int = 10          # تایم‌اوت درخواست HTTP (ثانیه)
GRACE_PERIOD: int    = 12 * 60 * 60  # ۱۲ ساعت — تا غیر‌فعال‌شدن ربات (ثانیه)
# ────────────────────────────────────────────────────────────────────────────

_license_active: bool         = True   # پیش‌فرض: فعال تا اولین چک
_inactive_since: Optional[float] = None  # زمان اولین تشخیص غیرفعال/قطعی
_lock = threading.Lock()


def is_licensed() -> bool:
    """وضعیت فعلی لاینسس رو برگردون. در هر هندلر ربات صدا بزن."""
    with _lock:
        return _license_active


def _check_once() -> Optional[bool]:
    """
    یک درخواست به API لاینسس می‌زنه.
    برمی‌گردونه:
      True  → لاینسس فعاله
      False → لاینسس منقضی یا غیرفعاله
      None  → سرور در دسترس نیست (ری‌استارت، قطعی، تایم‌اوت)
    """
    try:
        resp = requests.post(
            f"{LICENSE_API_URL}/api/license/check",
            json={"api_key": API_KEY, "bot_username": BOT_USERNAME},
            timeout=REQUEST_TIMEOUT,
        )
        data = resp.json()
        result = bool(data.get("is_licensed", False))
        logger.info("License check: is_licensed=%s status=%s", result, data.get("status"))
        return result
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logger.warning("License server unreachable — grace period running")
        return None
    except Exception as exc:
        logger.error("License check error: %s — grace period running", exc)
        return None


def _apply_result(result: Optional[bool]) -> None:
    """
    نتیجه چک رو اعمال می‌کنه با قانون ۱۲ ساعت:
    - اگه فعاله → بلافاصله فعال
    - اگه غیرفعاله یا سرور قطعه → تایمر شروع می‌شه؛
      فقط بعد از ۱۲ ساعت متوالی ربات خاموش می‌شه
    """
    global _license_active, _inactive_since
    with _lock:
        if result is True:
            # لاینسس تأیید شد — همه چیز ریست
            if not _license_active:
                logger.info("License is active again — bot reactivated")
            _license_active = True
            _inactive_since = None
        else:
            # غیرفعال یا سرور قطعه
            now = time.time()
            if _inactive_since is None:
                _inactive_since = now
                reason = "expired/inactive" if result is False else "server unreachable"
                logger.warning(
                    "License %s — 12h grace period started. Bot stays active for now.",
                    reason,
                )
            elapsed = now - _inactive_since
            if elapsed >= GRACE_PERIOD:
                if _license_active:
                    logger.error(
                        "License inactive for 12h — bot is now deactivated."
                    )
                _license_active = False
            else:
                remaining_h = (GRACE_PERIOD - elapsed) / 3600
                logger.info(
                    "License inactive %.1fh — bot deactivates in %.1fh if not renewed",
                    elapsed / 3600,
                    remaining_h,
                )


def force_recheck() -> bool:
    """
    یک چک فوری اجرا می‌کنه و وضعیت جدید رو برمی‌گردونه.
    از دکمه «بررسی مجدد» در ربات صدا بزن.
    لاینسس قبلی پاک نمیشه — همون کلید موجود رو دوباره چک می‌کنه.
    """
    result = _check_once()
    _apply_result(result)
    return is_licensed()


def _scheduler_loop() -> None:
    while True:
        time.sleep(CHECK_INTERVAL)
        result = _check_once()
        _apply_result(result)


def start_license_checker() -> None:
    """
    چکر لاینسس رو در یک thread جداگانه شروع می‌کنه.
    یک‌بار در ابتدای ربات صدا بزن.
    """
    # اولین چک همزمان — اگه سرور قطعه grace period شروع می‌شه ولی ربات خاموش نمیشه
    result = _check_once()
    _apply_result(result)

    logger.info(
        "License checker started. active=%s grace_since=%s",
        _license_active,
        _inactive_since,
    )

    # Thread پس‌زمینه برای چک‌های دوره‌ای
    t = threading.Thread(target=_scheduler_loop, name="license-checker", daemon=True)
    t.start()
