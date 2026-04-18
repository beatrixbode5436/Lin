import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot ─────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# ─── API Server ───────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "5000"))
API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:5000")

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "data/license_bot.db")

# ─── Misc ─────────────────────────────────────────────────────────────────────
CHANNEL_URL: str = os.getenv("CHANNEL_URL", "https://t.me/your_channel")
SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "@Emad_Habibnia")
NOTIFICATION_INTERVAL: int = int(os.getenv("NOTIFICATION_INTERVAL", "3600"))
