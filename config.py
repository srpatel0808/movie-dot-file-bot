"""
Configuration settings for MOVIE DOT Telegram Bot.
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

# Mandatory Subscription & Announcement Channel (e.g. @MyChannel or -100xxxxxxxxxx)
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()

# Bot username without @ (optional override, otherwise fetched dynamically via Bot API)
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

# Directories & Storage
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "bot_database.db"
