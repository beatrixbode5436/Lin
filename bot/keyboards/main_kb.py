from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS


def main_menu_keyboard(telegram_id: int, has_licenses: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 خرید اشتراک",        callback_data="main_buy"),
        InlineKeyboardButton("📢 کانال اطلاع رسانی",  callback_data="main_channel"),
    )
    if has_licenses:
        kb.add(InlineKeyboardButton("📋 لایسنس های من", callback_data="main_licenses"))
    if telegram_id in ADMIN_IDS:
        kb.add(InlineKeyboardButton("⚙️ پنل مدیریت", callback_data="main_admin"))
    return kb
