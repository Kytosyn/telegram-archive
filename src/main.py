"""CLI entry point for telegram-archive."""
import asyncio
import logging
import sys

from .config import DATABASE_PATH, INDEX_DIR, MEDIA_DIR, SERVER_HOST, SERVER_PORT
from .database import Database
from .scraper import TelegramScraper
from .search import SearchEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def cmd_init():
    """Initialize database."""
    logger.info(f"Initializing database at {DATABASE_PATH}")
    db = Database()
    db.init_schema()
    logger.info("Database initialized successfully.")
    logger.info(f"Media directory: {MEDIA_DIR}")
    logger.info(f"Index directory: {INDEX_DIR}")
    # Create directories
    import os
    os.makedirs(MEDIA_DIR, exist_ok=True)
    os.makedirs(INDEX_DIR, exist_ok=True)


def cmd_scrape():
    """Start scraping all chats."""
    logger.info("Starting scraper...")
    scraper = TelegramScraper()

    async def run():
        try:
            await scraper.scrape_all()
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user.")
            scraper.stop()
        finally:
            await scraper.disconnect()

    asyncio.run(run())


def cmd_index():
    """Build search index."""
    logger.info("Building search index...")
    engine = SearchEngine()
    count = engine.rebuild_index()
    logger.info(f"Indexed {count} messages.")


def cmd_serve():
    """Start web server."""
    import uvicorn

    logger.info(f"Starting web server on {SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(
        "src.server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
    )


def cmd_status():
    """Show scraping progress."""
    db = Database()

    try:
        db.init_schema()
    except Exception:
        pass

    stats = db.get_stats()
    logger.info("=" * 50)
    logger.info("TELEGRAM ARCHIVE STATUS")
    logger.info("=" * 50)
    logger.info(f"Total chats:     {stats['total_chats']}")
    logger.info(f"Total messages:  {stats['total_messages']}")
    logger.info(f"Total media:     {stats['total_media']}")

    chats = db.get_all_chats()
    if chats:
        logger.info("-" * 50)
        logger.info("Chat breakdown:")
        for chat in chats[:20]:
            logger.info(
                f"  [{chat['type']:10s}] {chat['name'][:40]:40s} — {chat['message_count']} msgs"
            )
        if len(chats) > 20:
            logger.info(f"  ... and {len(chats) - 20} more chats.")


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m src.main <command>")
        print("Commands: init, scrape, index, serve, status")
        sys.exit(1)

    command = sys.argv[1]

    commands = {
        "init": cmd_init,
        "scrape": cmd_scrape,
        "index": cmd_index,
        "serve": cmd_serve,
        "status": cmd_status,
        "list": cmd_list,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[command]()


def cmd_list():
    """List all chats with IDs (for configuring MEDIA_ALLOW_LIST)."""
    scraper = TelegramScraper()

    async def run():
        try:
            await scraper.list_chats()
        finally:
            await scraper.disconnect()

    asyncio.run(run())


if __name__ == "__main__":
    main()