from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import calculate_remaining


def user_licenses_keyboard(
    licenses: list[dict],
    page: int = 1,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)

    for lic in licenses:
        total_hours, time_str = calculate_remaining(lic["expires_at"])
        status = "✅" if lic["is_active"] and total_hours > 0 else "❌"
        label = f"{status} @{lic['bot_username']} | ⏳ {time_str}"
        kb.add(InlineKeyboardButton(label, callback_data=f"user_lic_{lic['id']}"))

    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"user_lic_page_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"user_lic_page_{page + 1}"))
    if nav:
        kb.row(*nav)

    return kb
