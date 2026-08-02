"""FastAPI web server for telegram-archive."""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import MEDIA_DIR
from .database import Database
from .search import SearchEngine

app = FastAPI(title="Telegram Archive", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

db = Database()
search_engine = SearchEngine()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Dashboard page."""
    stats = db.get_stats()
    recent = db.get_recent_messages(20)
    chats = db.get_all_chats()[:50]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "recent": recent,
        "chats": chats,
    })


@app.get("/chats", response_class=HTMLResponse)
async def list_chats(request: Request):
    """List all chats."""
    chats = db.get_all_chats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "chats": chats,
        "view": "chats",
    })


@app.get("/chats/{chat_id}", response_class=HTMLResponse)
async def view_chat(request: Request, chat_id: int, page: int = 1):
    """View messages in a chat."""
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    page_size = 50
    offset = (page - 1) * page_size
    messages = db.get_messages_by_chat(chat_id, offset=offset, limit=page_size)

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "chat": chat,
        "messages": messages,
        "page": page,
        "page_size": page_size,
        "has_more": len(messages) == page_size,
    })


@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = "",
    chat_id: str = None,
    sender_name: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
):
    """Search messages."""
    results = []
    total = 0
    if q or chat_id or sender_name or date_from or date_to:
        result = search_engine.search(
            query_string=q,
            chat_id=chat_id,
            sender_name=sender_name,
            date_from=date_from,
            date_to=date_to,
            page=page,
        )
        results = result["results"]
        total = result["total"]

    chats = db.get_all_chats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "query": q,
        "results": results,
        "total": total,
        "chats": chats,
        "view": "search",
        "page": page,
    })


@app.get("/stats", response_class=HTMLResponse)
async def stats(request: Request):
    """Statistics page."""
    stats_data = db.get_stats()
    chats = db.get_all_chats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats_data,
        "chats": chats,
        "view": "stats",
    })


@app.get("/message/{message_id}")
async def get_message(message_id: int, request: Request):
    """Single message detail."""
    message = db.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "message": message,
        "view": "message",
    })


@app.get("/media/{path:path}")
async def serve_media(path: str):
    """Serve media files."""
    media_path = Path(MEDIA_DIR) / path
    if not media_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(media_path)


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    return app


if __name__ == "__main__":
    import uvicorn
    from .config import SERVER_HOST, SERVER_PORT

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)