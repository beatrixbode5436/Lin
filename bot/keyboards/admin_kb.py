from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.helpers import calculate_remaining


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📝 تنظیم متن خرید اشتراک", callback_data="admin_set_sub_text"),
        InlineKeyboardButton("📋 مدیریت لایسنس‌ها",       callback_data="admin_licenses"),
        InlineKeyboardButton("� مدیریت کاربران",          callback_data="admin_users"),
        InlineKeyboardButton("📢 ارسال پیام (فوروارد)",    callback_data="admin_forward"),
        InlineKeyboardButton("�💾 بکاپ",                    callback_data="admin_backup"),
    )
    return kb


def licenses_panel_keyboard(
    licenses: list[dict],
    page: int = 1,
    total_pages: int = 1,
    inactive_mode: bool = False,
    search_mode: bool = False,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ اضافه کردن لایسنس", callback_data="admin_add_license"),
        InlineKeyboardButton("🔍 جستجو",              callback_data="admin_lic_search"),
    )
    if search_mode:
        kb.add(InlineKeyboardButton("✅ همه لایسنس‌ها", callback_data="admin_licenses"))
    elif not inactive_mode:
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
    if search_mode:
        prefix = "admin_lic_search_page_"
    elif inactive_mode:
        prefix = "admin_inactive_lic_page_"
    else:
        prefix = "admin_lic_page_"

    if page > 1:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"{prefix}{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data=f"admin_lic_goto_page_{prefix}"))
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
    kb.add(
        InlineKeyboardButton("⏱ ست کردن زمان دقیق", callback_data=f"admin_lic_set_hours_{lid}"),
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


def backup_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📦 بکاپ دستی الان",          callback_data="admin_backup_now"),
        InlineKeyboardButton("♻️ بازیابی بکاپ",             callback_data="admin_backup_restore"),
        InlineKeyboardButton("⏰ زمان بکاپ خودکار (ساعت)", callback_data="admin_backup_set_interval"),
        InlineKeyboardButton("📬 مقصد بکاپ خودکار",        callback_data="admin_backup_set_dest"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back"))
    return kb


def users_panel_keyboard(filter_mode: str = "all") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    all_btn    = InlineKeyboardButton("👥 همه" + (" ✓" if filter_mode == "all" else ""),       callback_data="admin_users_filter_all")
    lic_btn    = InlineKeyboardButton("✅ دارندگان لاینسس" + (" ✓" if filter_mode == "licensed" else ""),  callback_data="admin_users_filter_licensed")
    no_lic_btn = InlineKeyboardButton("❌ بدون لاینسس" + (" ✓" if filter_mode == "unlicensed" else ""), callback_data="admin_users_filter_unlicensed")
    kb.row(lic_btn, no_lic_btn)
    kb.add(all_btn)
    kb.add(InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_users_search"))
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back"))
    return kb


def users_list_keyboard(
    users: list[dict],
    page: int,
    total_pages: int,
    filter_mode: str = "all",
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for u in users:
        uname = u.get("owner_username") or ""
        label_name = f"@{uname}" if uname else f"ID:{u['telegram_id']}"
        cnt = u.get("license_count", 0)
        kb.add(InlineKeyboardButton(
            f"👤 {label_name}  |  🔑 {cnt} لاینسس",
            callback_data=f"admin_user_view_{u['telegram_id']}",
        ))

    prefix = f"admin_users_page_{filter_mode}_"
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"{prefix}{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data=f"{prefix}{page + 1}"))
    if nav:
        kb.row(*nav)

    kb.add(InlineKeyboardButton("🔙 بازگشت به فیلترها", callback_data="admin_users"))
    return kb


def forward_panel_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📢 ارسال برای همه",              callback_data="admin_fwd_all"),
        InlineKeyboardButton("✅ ارسال فقط برای دارندگان لاینسس", callback_data="admin_fwd_licensed"),
        InlineKeyboardButton("❌ ارسال برای کاربران بدون لاینسس", callback_data="admin_fwd_unlicensed"),
    )
    kb.add(InlineKeyboardButton("🔙 بازگشت", callback_data="admin_back"))
    return kb
