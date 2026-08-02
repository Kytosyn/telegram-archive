"""Configuration for telegram-archive."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Telegram API credentials
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")
TELEGRAM_SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "telegram_archive")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "telegram.db"))

# Media
MEDIA_DIR = os.getenv("MEDIA_DIR", str(BASE_DIR / "media"))

# Whoosh search index
INDEX_DIR = os.getenv("INDEX_DIR", str(BASE_DIR / "index"))

# Server
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))

# Rate limiting
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "0.05"))
MAX_MESSAGES_PER_SECOND = float(os.getenv("MAX_MESSAGES_PER_SECOND", "3"))

# Media download settings
# MEDIA_MODE: "all" | "none" | "selective"
# - "all": download all media (default, original behavior)
# - "none": text-only, skip all media downloads
# - "selective": only download media from chats listed in MEDIA_ALLOW_LIST
MEDIA_MODE = os.getenv("MEDIA_MODE", "all")

# MEDIA_ALLOW_LIST: comma-separated list of chat IDs or usernames
# Only used when MEDIA_MODE=selective
# Examples: "123456789,johndoe,-1001234567890" or "@johndoe,channelusername"
MEDIA_ALLOW_LIST = os.getenv("MEDIA_ALLOW_LIST", "")

# MAX_MEDIA_SIZE_MB: skip media larger than this (0 = unlimited)
MAX_MEDIA_SIZE_MB = int(os.getenv("MAX_MEDIA_SIZE_MB", "0"))