"""Whoosh full-text search engine for telegram-archive."""
import logging
from datetime import datetime
from pathlib import Path

from whoosh import index
from whoosh.fields import DATETIME, ID, KEYWORD, TEXT, Schema
from whoosh.qparser import MultifieldParser, QueryParser
from whoosh.query import And, DateRange, Term

from .config import INDEX_DIR
from .database import Database

logger = logging.getLogger(__name__)

schema = Schema(
    message_id=ID(stored=True, unique=True),
    chat_id=ID(stored=True),
    chat_name=TEXT(stored=True),
    sender_name=TEXT(stored=True),
    sender_username=ID(stored=True),
    content=TEXT(stored=True),
    timestamp=DATETIME(stored=True),
    chat_type=KEYWORD(stored=True),
)


class SearchEngine:
    """Whoosh-based full-text search for Telegram messages."""

    def __init__(self, index_dir: str = None, db: Database = None):
        self.index_dir = index_dir or INDEX_DIR
        self.db = db or Database()
        self._ix = None

    def get_index(self):
        """Get or create the Whoosh index."""
        if self._ix:
            return self._ix

        Path(self.index_dir).mkdir(parents=True, exist_ok=True)

        if index.exists_in(self.index_dir):
            self._ix = index.open_dir(self.index_dir)
        else:
            self._ix = index.create_in(self.index_dir, schema=schema)

        return self._ix

    def rebuild_index(self):
        """Rebuild the entire search index from the database."""
        logger.info("Rebuilding search index...")

        # Remove existing index
        import shutil
        p = Path(self.index_dir)
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)

        self._ix = index.create_in(self.index_dir, schema=schema)
        writer = self._ix.writer()

        messages = self.db.get_all_messages_for_indexing()
        count = 0

        for msg in messages:
            try:
                ts = datetime.fromisoformat(msg["timestamp"])
            except (ValueError, TypeError):
                ts = datetime.min

            writer.add_document(
                message_id=str(msg["id"]),
                chat_id=str(msg["chat_id"]),
                chat_name=msg.get("chat_name", ""),
                sender_name=msg.get("sender_name", ""),
                sender_username=msg.get("sender_username", ""),
                content=msg.get("text", ""),
                timestamp=ts,
                chat_type=msg.get("chat_type", ""),
            )
            count += 1

            if count % 5000 == 0:
                writer.commit()
                writer = self._ix.writer()
                logger.info(f"Indexed {count} messages...")

        writer.commit()
        logger.info(f"Search index rebuilt with {count} messages.")
        return count

    def search(
        self,
        query_string: str,
        chat_id: str = None,
        chat_name: str = None,
        sender_name: str = None,
        date_from: str = None,
        date_to: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Search messages with filters."""
        ix = self.get_index()

        # Build query
        parser = MultifieldParser(["content", "sender_name", "chat_name"], schema=schema)

        queries = []
        if query_string:
            queries.append(parser.parse(query_string))

        if chat_id:
            queries.append(Term("chat_id", str(chat_id)))

        if chat_name:
            queries.append(Term("chat_name", chat_name))

        if sender_name:
            queries.append(Term("sender_name", sender_name))

        if date_from or date_to:
            try:
                dt_from = datetime.fromisoformat(date_from) if date_from else datetime.min
                dt_to = datetime.fromisoformat(date_to) if date_to else datetime.max
                queries.append(DateRange("timestamp", dt_from, dt_to))
            except (ValueError, TypeError):
                pass

        final_query = And(queries) if queries else None

        # Search
        with ix.searcher() as searcher:
            if final_query:
                results = searcher.search_page(final_query, page, pagelen=page_size)
            else:
                results = searcher.search_page(None, page, pagelen=page_size)

            hits = []
            for hit in results:
                hit_dict = dict(hit)
                # Add highlighting
                if query_string:
                    highlighted = hit.highlights("content")
                    if highlighted:
                        hit_dict["highlight"] = highlighted
                hits.append(hit_dict)

            return {
                "total": len(results),
                "page": page,
                "page_size": page_size,
                "results": hits,
            }


def get_search_engine() -> SearchEngine:
    """Get search engine instance."""
    return SearchEngine()