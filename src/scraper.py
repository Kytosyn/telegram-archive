"""Telethon-based Telegram chat scraper."""
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
    PeerChannel,
    PeerChat,
    PeerUser,
)
from tqdm import tqdm

from .config import (
    MEDIA_DIR,
    RATE_LIMIT_SECONDS,
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_PHONE,
    TELEGRAM_SESSION_NAME,
)
from .database import Database

logger = logging.getLogger(__name__)


class TelegramScraper:
    """Scraper for Telegram chats using Telethon user API."""

    def __init__(self, db: Database = None):
        self.db = db or Database()
        self.client: TelegramClient = None
        self.media_dir = Path(MEDIA_DIR)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._stop = False

    async def connect(self):
        """Connect to Telegram."""
        self.client = TelegramClient(
            TELEGRAM_SESSION_NAME,
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH,
        )
        await self.client.connect()

        if not await self.client.is_user_authorized():
            logger.info("User not authorized. Sending code request...")
            await self.client.send_code_request(TELEGRAM_PHONE)
            code = input("Enter the code you received: ")
            try:
                await self.client.sign_in(TELEGRAM_PHONE, code)
            except SessionPasswordNeededError:
                password = input("Two-factor authentication enabled. Enter password: ")
                await self.client.sign_in(password=password)

        logger.info("Connected to Telegram successfully.")

    async def disconnect(self):
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()

    def get_chat_type(self, entity) -> str:
        """Determine chat type from entity."""
        if isinstance(entity, PeerUser):
            return "private"
        elif isinstance(entity, PeerChat):
            return "group"
        elif isinstance(entity, PeerChannel):
            if getattr(entity, "megagroup", False):
                return "supergroup"
            return "channel"
        return "unknown"

    def get_chat_name(self, entity) -> str:
        """Get display name for a chat/entity."""
        if hasattr(entity, "title"):
            return entity.title or "Unknown"
        if hasattr(entity, "first_name"):
            name = entity.first_name or ""
            if hasattr(entity, "last_name") and entity.last_name:
                name += " " + entity.last_name
            return name.strip() or "Unknown"
        if hasattr(entity, "username") and entity.username:
            return f"@{entity.username}"
        return "Unknown"

    def get_sender_name(self, message) -> tuple:
        """Get sender name and username from message."""
        sender_name = None
        sender_username = None
        sender_id = None

        if message.sender:
            sender_id = message.sender.id
            if hasattr(message.sender, "first_name"):
                sender_name = message.sender.first_name or ""
                if hasattr(message.sender, "last_name") and message.sender.last_name:
                    sender_name += " " + message.sender.last_name
                sender_name = sender_name.strip()
                if hasattr(message.sender, "title") and message.sender.title:
                    sender_name = message.sender.title
            elif hasattr(message.sender, "title"):
                sender_name = message.sender.title
            if hasattr(message.sender, "username"):
                sender_username = message.sender.username

        return sender_id, sender_name, sender_username

    def get_media_info(self, message) -> tuple:
        """Extract media type, path, size from message."""
        if not message.media:
            return None, None, None

        media_type = None
        media_path = None
        media_size = None

        if isinstance(message.media, MessageMediaPhoto):
            media_type = "photo"
        elif isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            if doc:
                media_size = doc.size
                # Check for sticker
                for attr in doc.attributes:
                    if isinstance(attr, DocumentAttributeSticker):
                        media_type = "sticker"
                        break
                    if isinstance(attr, DocumentAttributeVideo):
                        media_type = "video"
                        break
                    if isinstance(attr, DocumentAttributeFilename):
                        filename = attr.file_name
                        ext = os.path.splitext(filename)[1].lower() if filename else ""
                        if ext in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"}:
                            media_type = "document"
                        elif ext in {".mp3", ".wav", ".ogg", ".flac", ".m4a"}:
                            media_type = "audio"
                        elif ext in {".gif"}:
                            media_type = "animation"
                        else:
                            media_type = "document"
                if not media_type:
                    media_type = "document"
        elif isinstance(message.media, MessageMediaWebPage):
            media_type = "webpage"

        return media_type, media_path, media_size

    async def download_media(self, message, chat_id: int, message_id: int, media_type: str) -> str:
        """Download media file and return local path."""
        if not message.media:
            return None

        subdir = self.media_dir / str(chat_id)
        subdir.mkdir(parents=True, exist_ok=True)

        filename = f"{message_id}"
        if media_type == "photo":
            filename += ".jpg"
        elif media_type == "video":
            filename += ".mp4"
        elif media_type == "document":
            # Try to get original filename
            if hasattr(message.media, "document") and message.media.document:
                for attr in message.media.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        filename += "_" + attr.file_name
                        break
                else:
                    filename += ".bin"
        elif media_type == "sticker":
            filename += ".webp"
        elif media_type == "audio":
            filename += ".mp3"
        else:
            filename += ".bin"

        file_path = subdir / filename

        if file_path.exists():
            return str(file_path.relative_to(self.media_dir.parent))

        try:
            downloaded = await self.client.download_media(message, file=str(file_path))
            if downloaded:
                return str(Path(downloaded).relative_to(self.media_dir.parent))
        except Exception as e:
            logger.error(f"Failed to download media {message_id}: {e}")

        return None

    async def scrape_chat(self, entity, chat_name: str, chat_type: str) -> int:
        """Scrape all messages from a single chat. Returns message count."""
        chat_id = entity.id

        # Save chat info
        self.db.upsert_chat({
            "id": chat_id,
            "name": chat_name,
            "type": chat_type,
            "username": getattr(entity, "username", None),
            "participants_count": getattr(entity, "participants_count", None),
            "date_created": None,
        })

        # Check for progress to resume
        progress = self.db.get_scrape_progress(chat_id)
        min_id = 0
        start_message_id = None
        already_scraped = 0

        if progress and progress["last_message_id"]:
            min_id = progress["last_message_id"]
            already_scraped = progress["total_messages"]
            logger.info(
                f"Resuming chat '{chat_name}' from message {min_id}, "
                f"already scraped: {already_scraped}"
            )

        message_count = 0
        batch = []
        pbar = tqdm(desc=f"Scraping '{chat_name}'", unit="msgs", initial=already_scraped)

        try:
            async for message in self.client.iter_messages(
                entity, limit=0, min_id=min_id, reverse=True
            ):
                if self._stop:
                    break

                sender_id, sender_name, sender_username = self.get_sender_name(message)
                media_type, _, media_size = self.get_media_info(message)

                # Download media
                media_path = None
                if media_type and media_type != "webpage":
                    media_path = await self.download_media(
                        message, chat_id, message.id, media_type
                    )

                # Handle forward
                forward_from_id = None
                forward_from_name = None
                if message.forward:
                    if message.forward.sender:
                        forward_from_id = message.forward.sender.id
                        forward_from_name = self.get_chat_name(message.forward.sender)
                    elif message.forward.chat:
                        forward_from_id = message.forward.chat.id
                        forward_from_name = self.get_chat_name(message.forward.chat)

                msg_data = {
                    "id": message.id,
                    "chat_id": chat_id,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "sender_username": sender_username,
                    "text": message.text or message.message or "",
                    "timestamp": message.date.isoformat(),
                    "reply_to_id": message.reply_to.reply_to_msg_id if message.reply_to else None,
                    "forward_from_id": forward_from_id,
                    "forward_from_name": forward_from_name,
                    "media_type": media_type,
                    "media_path": media_path,
                    "media_size": media_size,
                    "is_edited": 1 if message.edit_date else 0,
                    "is_pinned": 1 if message.pinned else 0,
                }

                batch.append(msg_data)

                if len(batch) >= 1000:
                    self.db.upsert_messages_batch(batch)
                    batch = []
                    self.db.save_scrape_progress(chat_id, message.id, message_count + already_scraped)

                # Rate limiting
                await asyncio.sleep(RATE_LIMIT_SECONDS)
                message_count += 1
                pbar.update(1)

            # Save remaining batch
            if batch:
                self.db.upsert_messages_batch(batch)

        except FloodWaitError as e:
            logger.warning(f"FloodWait: sleeping for {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error scraping chat '{chat_name}': {e}")

        pbar.close()

        # Update final progress
        total = message_count + already_scraped
        self.db.save_scrape_progress(chat_id, None, total)
        self.db.update_chat_message_count(chat_id)

        logger.info(f"Scraped {message_count} messages from '{chat_name}' (total: {total})")
        return message_count

    async def scrape_all(self):
        """Scrape all dialogs from the Telegram account."""
        if not self.client:
            await self.connect()

        logger.info("Starting to scrape all dialogs...")
        dialog_count = 0
        total_messages = 0

        async for dialog in self.client.iter_dialogs(limit=None):
            if self._stop:
                break

            chat_name = dialog.name
            chat_type = self.get_chat_type(dialog.entity)
            dialog_count += 1

            logger.info(f"Dialog {dialog_count}: '{chat_name}' (type: {chat_type})")

            try:
                count = await self.scrape_chat(dialog.entity, chat_name, chat_type)
                total_messages += count
            except FloodWaitError as e:
                logger.warning(f"FloodWait: sleeping for {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error with dialog '{chat_name}': {e}")
                continue

            # Rate limiting between dialogs
            await asyncio.sleep(0.5)

        logger.info(
            f"Scraping complete. {dialog_count} chats, {total_messages} total messages."
        )

    def stop(self):
        """Signal the scraper to stop."""
        self._stop = True


async def run_scraper():
    """Entry point for the scraper."""
    scraper = TelegramScraper()
    try:
        await scraper.scrape_all()
    finally:
        await scraper.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scraper())