from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from config import ADMIN_IDS


def main_menu_keyboard(telegram_id: int, has_licenses: bool = False) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("🛒 خرید اشتراک"), KeyboardButton("📢 کانال اطلاع رسانی"))
    if has_licenses:
        kb.add(KeyboardButton("📋 لایسنس های من"))
    if telegram_id in ADMIN_IDS:
        kb.add(KeyboardButton("⚙️ پنل مدیریت"))
    return kb
