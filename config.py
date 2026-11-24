"""
Configuration settings for Telegram Thumbnail Watermark Bot.
Loads environment variables from .env file with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs (comma-separated list of integer IDs)
_admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
ADMIN_IDS = set()
if _admin_ids_raw:
    for aid in _admin_ids_raw.split(","):
        aid = aid.strip()
        if aid.isdigit():
            ADMIN_IDS.add(int(aid))

# Directories
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# File Paths
DB_PATH = DATA_DIR / "bot_database.db"
ACTIVE_WATERMARK_PATH = DATA_DIR / "watermark.png"
SAMPLE_WATERMARK_PATH = ASSETS_DIR / "sample_watermark.png"

# Default Watermark Settings
DEFAULT_SETTINGS = {
    "position": "bottom_right",   # top_left, top_center, top_right, center_left, center, center_right, bottom_left, bottom_center, bottom_right
    "scale": 22,                 # watermark width as % of thumbnail width (5% - 60%)
    "opacity": 85,               # opacity % (10% - 100%)
    "padding": 20,               # padding from edges in pixels
    "output_mode": "both"        # "both" (photo + document), "document" (uncompressed only), "photo" (photo only)
}

# Supported Image Formats
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_FILE_SIZE_MB = 20  # Telegram bot API download limit for standard bot is 20MB
