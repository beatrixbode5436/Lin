from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import calculate_remaining


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📝 تنظیم متن خرید اشتراک", callback_data="admin_set_sub_text"),
        InlineKeyboardButton("📋 مدیریت لایسنس‌ها",       callback_data="admin_licenses"),
        InlineKeyboardButton("🤖 مدیریت ربات‌ها",          callback_data="admin_bots"),
    )
    return kb


def licenses_panel_keyboard(
    licenses: list[dict],
    page: int = 1,
    total_pages: int = 1,
    inactive_mode: bool = False,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ اضافه کردن لایسنس", callback_data="admin_add_license")
    )
    if not inactive_mode:
        kb.add(
            InlineKeyboardButton("🔴 لایسنس‌های غیرفعال", callback_data="admin_inactive_licenses_1")
        )
    else:
        kb.add(
            InlineKeyboardButton("✅ همه لایسنس‌ها", callback_data="admin_licenses")
        )

    for lic in licenses:
        total_hours, time_str = calculate_remaining(lic["expires_at"])
        status = "✅" if lic["is_active"] and total_hours > 0 else "❌"
        label = f"{status} @{lic['bot_username']} (@{lic['owner_username']}) | ⏳ {time_str}"
        kb.add(
            InlineKeyboardButton(label, callback_data=f"admin_lic_view_{lic['id']}")
        )

    nav: list[InlineKeyboardButton] = []
    prefix = "admin_inactive_lic_page_" if inactive_mode else "admin_lic_page_"
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"{prefix}{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"{prefix}{page + 1}"))
    if nav:
        kb.row(*nav)

    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back"))
    return kb


def license_detail_keyboard(license_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    lid = license_id
    kb = InlineKeyboardMarkup(row_width=2)

    # Toggle activate/deactivate
    if is_active:
        toggle_label = "🔴 غیرفعال کردن"
    else:
        toggle_label = "🟢 فعال کردن"
    kb.add(
        InlineKeyboardButton(toggle_label,          callback_data=f"admin_lic_toggle_{lid}"),
        InlineKeyboardButton("🗑 حذف",               callback_data=f"admin_lic_del_{lid}"),
    )
    kb.add(
        InlineKeyboardButton("🕐 مدیریت زمان",       callback_data=f"admin_lic_time_{lid}"),
        InlineKeyboardButton("🔑 API Key جدید",      callback_data=f"admin_lic_rot_{lid}"),
    )
    kb.add(
        InlineKeyboardButton("📤 متن فعال‌سازی",    callback_data=f"admin_lic_act_{lid}"),
        InlineKeyboardButton("✏️ ویرایش",            callback_data=f"admin_lic_edit_{lid}"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="admin_licenses"))
    return kb


def license_time_management_keyboard(license_id: int) -> InlineKeyboardMarkup:
    lid = license_id
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ اضافه کردن ساعت", callback_data=f"admin_lic_add_hours_{lid}"),
        InlineKeyboardButton("➖ کم کردن ساعت",    callback_data=f"admin_lic_sub_hours_{lid}"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_lic_view_{lid}"))
    return kb


def license_edit_keyboard(license_id: int) -> InlineKeyboardMarkup:
    lid = license_id
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👤 ویرایش یوزرنیم خریدار",  callback_data=f"admin_lic_edit_oun_{lid}"),
        InlineKeyboardButton("🆔 ویرایش آیدی عددی خریدار", callback_data=f"admin_lic_edit_oid_{lid}"),
        InlineKeyboardButton("🤖 ویرایش یوزرنیم ربات",    callback_data=f"admin_lic_edit_bun_{lid}"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_lic_view_{lid}"))
    return kb


def bots_panel_keyboard(bots: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for bot in bots:
        kb.add(
            InlineKeyboardButton(
                f"🤖 @{bot['bot_username']}  ({bot['total']} لایسنس / {bot['active']} فعال)",
                callback_data=f"admin_bot_view_{bot['bot_username']}",
            )
        )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back"))
    return kb
