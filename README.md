# License Center Bot

ربات تلگرام مستقل برای مدیریت، صدور و بررسی لایسنس — با API داخلی برای اتصال ربات‌های دیگر.

---

## ساختار پروژه

```
license_center/
├── main.py                    # Entry point
├── config.py                  # تنظیمات از .env
├── requirements.txt
├── env.example
├── install.sh
│
├── database/
│   └── db.py                  # راه‌اندازی SQLite + init_db
│
├── bot/
│   ├── states.py              # State machine
│   ├── handlers/
│   │   ├── start.py           # /start, /cancel, منوی اصلی
│   │   ├── admin.py           # پنل مدیریت و Callback های ادمین
│   │   ├── user.py            # لایسنس‌های من
│   │   └── state_handler.py   # پردازش مرحله‌ای فرم‌ها
│   └── keyboards/
│       ├── main_kb.py
│       ├── admin_kb.py
│       └── license_kb.py
│
├── api/
│   └── routes.py              # Flask endpoints
│
├── services/
│   ├── license_service.py     # منطق لایسنس
│   ├── settings_service.py    # خواندن/نوشتن تنظیمات
│   └── notification_service.py# ارسال هشدار ساعتی
│
└── utils/
    └── helpers.py
```

---

## نصب سریع (لینوکس / سرور)

```bash
# ۱. کلون یا آپلود فایل‌ها روی سرور
cd /opt/license-center

# ۲. نصب کامل (venv + deps + systemd)
sudo bash install.sh install

# ۳. ویرایش تنظیمات
sudo bash install.sh edit-config
#   مقادیر مهم:
#     BOT_TOKEN   = توکن ربات از @BotFather
#     ADMIN_IDS   = آیدی عددی تلگرام ادمین‌ها (کاما جدا)
#     API_BASE_URL = http://آی‌پی-سرور:5000

# ۴. اجرا
sudo bash install.sh restart

# مشاهده لاگ
sudo bash install.sh logs
```

---

## دستورات install.sh

| دستور | توضیح |
|---|---|
| `install` | نصب کامل اولیه |
| `update` | بروزرسانی dependencies + ری‌استارت |
| `restart` | ری‌استارت سرویس |
| `stop` | توقف سرویس |
| `status` | وضعیت سرویس |
| `logs` | مشاهده لاگ زنده |
| `remove` | حذف سرویس systemd (داده‌ها حذف نمی‌شوند) |
| `edit-config` | ویرایش فایل .env |

---

## API Endpoints

### `POST /api/license/activate`

اولین فعال‌سازی لایسنس و Bind شدن `machine_id`.

**Request body (JSON):**
```json
{
  "api_key":           "LK-xxxxxxxxxxxxxxxxxxxx",
  "bot_username":      "mybot",
  "owner_telegram_id": 123456789,
  "owner_username":    "john",
  "machine_id":        "unique-server-identifier",
  "server_ip":         "1.2.3.4"
}
```

**Response (active):**
```json
{
  "ok": true,
  "is_licensed": true,
  "status": "active",
  "expires_at": "2026-05-01T12:00:00",
  "remaining_hours": 312,
  "message": "License is valid and active"
}
```

---

### `POST /api/license/check`

بررسی وضعیت لایسنس در هر بار اجرای ربات اصلی.

**Request body:** همان فیلدهای `activate` (بدون `server_ip`).

**Response:**
```json
{
  "ok": true,
  "is_licensed": true,
  "status": "active",
  "expires_at": "2026-05-01T12:00:00",
  "remaining_hours": 312,
  "message": "License is valid",
  "public_disabled_text": "",
  "notify_text": "",
  "subscription_text": "برای خرید اشتراک ..."
}
```

**مقادیر `status`:**  
`active` | `expired` | `disabled` | `not_found` | `mismatch` | `machine_mismatch`

---

## منطق machine_id

- در اولین فراخوانی `activate`، اگر `machine_id` در دیتابیس خالی باشد، مقدار ارسال‌شده **bind** می‌شود.
- در فراخوانی‌های بعدی، `machine_id` باید **دقیقاً** با مقدار ذخیره‌شده مطابقت داشته باشد.
- با **تولید API Key جدید** (از پنل ادمین)، `machine_id` پاک می‌شود و می‌توان دوباره bind کرد.

---

## متغیرهای .env

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `BOT_TOKEN` | — | توکن ربات |
| `ADMIN_IDS` | — | آیدی ادمین‌ها، کاما جدا |
| `API_HOST` | `0.0.0.0` | آدرس bind برای Flask |
| `API_PORT` | `5000` | پورت API |
| `API_BASE_URL` | `http://localhost:5000` | URL عمومی برای نمایش به مشتری |
| `DB_PATH` | `data/license_bot.db` | مسیر فایل SQLite |
| `CHANNEL_URL` | — | لینک کانال |
| `SUPPORT_USERNAME` | `@Emad_Habibnia` | نام کاربری پشتیبانی |
| `NOTIFICATION_INTERVAL` | `3600` | فاصله ارسال هشدار (ثانیه) |

---

## امنیت

- دسترسی پنل مدیریت فقط برای `ADMIN_IDS`
- API Key هر لایسنس ۴۰ کاراکتر رندوم (`secrets.choice`)
- ورودی‌های API تمام‌ها validate می‌شوند
- `machine_id` binding جلوی انتقال لایسنس را می‌گیرد
- امکان rotate کردن API Key از پنل ادمین
