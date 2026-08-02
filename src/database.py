"""SQLite database layer for telegram-archive."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DATABASE_PATH


class Database:
    """SQLite database for storing Telegram chat archive."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self):
        """Create database tables if they don't exist."""
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    username TEXT,
                    participants_count INTEGER,
                    date_created TEXT,
                    last_message_date TEXT,
                    message_count INTEGER DEFAULT 0,
                    scraped_at TEXT,
                    UNIQUE(id, name)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    sender_id INTEGER,
                    sender_name TEXT,
                    sender_username TEXT,
                    text TEXT,
                    timestamp TEXT NOT NULL,
                    reply_to_id INTEGER,
                    forward_from_id INTEGER,
                    forward_from_name TEXT,
                    media_type TEXT,
                    media_path TEXT,
                    media_size INTEGER,
                    is_edited INTEGER DEFAULT 0,
                    is_pinned INTEGER DEFAULT 0,
                    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id, chat_id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
                CREATE INDEX IF NOT EXISTS idx_messages_text ON messages(text);

                CREATE TABLE IF NOT EXISTS scrape_progress (
                    chat_id INTEGER PRIMARY KEY,
                    last_message_id INTEGER,
                    total_messages INTEGER DEFAULT 0,
                    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def upsert_chat(self, chat_data: dict):
        """Insert or update a chat record."""
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO chats (id, name, type, username, participants_count, date_created, scraped_at)
                VALUES (:id, :name, :type, :username, :participants_count, :date_created, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    username = excluded.username,
                    participants_count = excluded.participants_count,
                    date_created = excluded.date_created,
                    scraped_at = CURRENT_TIMESTAMP
                """,
                chat_data,
            )

    def upsert_messages_batch(self, messages: list):
        """Batch insert/update messages."""
        if not messages:
            return
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO messages
                    (id, chat_id, sender_id, sender_name, sender_username,
                     text, timestamp, reply_to_id, forward_from_id,
                     forward_from_name, media_type, media_path, media_size,
                     is_edited, is_pinned, scraped_at)
                VALUES
                    (:id, :chat_id, :sender_id, :sender_name, :sender_username,
                     :text, :timestamp, :reply_to_id, :forward_from_id,
                     :forward_from_name, :media_type, :media_path, :media_size,
                     :is_edited, :is_pinned, CURRENT_TIMESTAMP)
                """,
                messages,
            )

    def update_chat_message_count(self, chat_id: int):
        """Update message count for a chat."""
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE chats SET
                    message_count = (SELECT COUNT(*) FROM messages WHERE chat_id = ?),
                    last_message_date = (SELECT MAX(timestamp) FROM messages WHERE chat_id = ?)
                WHERE id = ?
                """,
                (chat_id, chat_id, chat_id),
            )

    def save_scrape_progress(self, chat_id: int, last_message_id: int, total_messages: int):
        """Save scraping progress for resuming."""
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO scrape_progress (chat_id, last_message_id, total_messages, scraped_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    last_message_id = excluded.last_message_id,
                    total_messages = excluded.total_messages,
                    scraped_at = CURRENT_TIMESTAMP
                """,
                (chat_id, last_message_id, total_messages),
            )

    def get_scrape_progress(self, chat_id: int) -> dict:
        """Get scraping progress for a chat."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM scrape_progress WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_all_chats(self) -> list:
        """Get all chats with message counts."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chats ORDER BY last_message_date DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_chat(self, chat_id: int) -> dict:
        """Get a specific chat."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM chats WHERE id = ?", (chat_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_messages_by_chat(self, chat_id: int, offset: int = 0, limit: int = 50) -> list:
        """Get messages for a chat with pagination."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
                """,
                (chat_id, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_message(self, message_id: int, chat_id: int = None) -> dict:
        """Get a specific message."""
        with self.connection() as conn:
            if chat_id:
                row = conn.execute(
                    "SELECT * FROM messages WHERE id = ? AND chat_id = ?",
                    (message_id, chat_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM messages WHERE id = ?", (message_id,)
                ).fetchone()
            return dict(row) if row else None

    def get_stats(self) -> dict:
        """Get archive statistics."""
        with self.connection() as conn:
            total_chats = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
            total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            total_media = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE media_type IS NOT NULL"
            ).fetchone()[0]
            return {
                "total_chats": total_chats,
                "total_messages": total_messages,
                "total_media": total_media,
            }

    def get_recent_messages(self, limit: int = 20) -> list:
        """Get recent messages across all chats."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_messages_for_indexing(self) -> list:
        """Get all messages for search indexing."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT m.*, c.name as chat_name, c.type as chat_type
                FROM messages m
                JOIN chats c ON m.chat_id = c.id
                ORDER BY m.timestamp ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]


def get_db() -> Database:
    """Get database instance."""
    return Database()