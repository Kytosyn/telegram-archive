"""Configuration for telegram-archive."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Telegram API credentials
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
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
SERVER_PORT = int(os.getenv("SERVER_PORT", 8080))

# Rate limiting
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", 0.05))
MAX_MESSAGES_PER_SECOND = float(os.getenv("MAX_MESSAGES_PER_SECOND", 3))