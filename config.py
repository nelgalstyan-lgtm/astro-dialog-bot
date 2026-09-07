"""
Конфигурация Astro Dialog Bot.
Все секретные значения берутся из переменных окружения (.env локально,
Environment Variables в панели хостинга — в проде).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# --- Telegram ----------------------------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@astrologicheskiy_dialog")
CHANNEL_URL = os.getenv("CHANNEL_URL", f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")

BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# --- Режим запуска: polling (локально) или webhook (на бесплатном хостинге) --
RUN_MODE = os.getenv("RUN_MODE", "polling").lower()

PORT = int(os.getenv("PORT", "10000"))

WEBHOOK_URL = os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL", "")

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", BOT_TOKEN)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# --- Пути к статике (шрифты, референсы, готовые карточки) --------------------

ASSETS_DIR = BASE_DIR / "assets"
REFERENCES_DIR = ASSETS_DIR / "references"
CARDS_DIR = ASSETS_DIR / "cards"
MISC_DIR = ASSETS_DIR / "misc"
FONTS_DIR = ASSETS_DIR / "fonts"
