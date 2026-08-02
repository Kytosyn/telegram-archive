# Telegram Archive & Search System

A complete solution for archiving and searching Telegram chat history using Telethon (user API), SQLite, Whoosh, and FastAPI.

## Features

- Scrape all chats from your personal Telegram account using Telethon
- Store messages in SQLite with WAL mode for concurrency
- Full-text search with Whoosh (highlighted results)
- FastAPI web interface for browsing and searching
- Media file download and serving
- Resume interrupted scrapes
- Rate limiting to avoid Telegram bans
- Dark-themed responsive UI

## Prerequisites

- Python 3.11+
- A Telegram account
- Telegram API credentials

## Getting Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Save the **api_id** and **api_hash**

## Installation

```bash
cd telegram-archive
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# Edit .env with your API ID, API Hash, and phone number
```

## Usage

### 1. Initialize the database

```bash
python -m src.main init
```

### 2. Scrape all chats

```bash
python -m src.main scrape
```

This will:
- Connect to Telegram using your credentials
- Iterate through all dialogs (private chats, groups, channels)
- Download all message history
- Download media files
- Store everything in SQLite

The first time you run this, you'll need to enter the verification code sent to your Telegram account. If you have 2FA enabled, you'll also need to enter your password.

### 3. Build the search index

```bash
python -m src.main index
```

### 4. Start the web server

```bash
python -m src.main serve
```

Open http://localhost:8080 in your browser.

### 5. Check status

```bash
python -m src.main status
```

## Docker

```bash
docker build -t telegram-archive .
docker run -d \
  --name telegram-archive \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/media:/app/media \
  -v $(pwd)/index:/app/index \
  --env-file .env \
  telegram-archive
```

## Project Structure

```
telegram-archive/
├── src/
│   ├── __init__.py
│   ├── config.py       # Configuration from env vars
│   ├── database.py     # SQLite database layer
│   ├── scraper.py      # Telethon scraper
│   ├── search.py       # Whoosh search engine
│   ├── server.py       # FastAPI web server
│   └── main.py         # CLI entry point
├── templates/
│   ├── index.html      # Dashboard & search interface
│   └── chat.html       # Chat view
├── media/              # Downloaded media files
├── data/               # SQLite database
├── index/              # Whoosh search index
├── .env                # Environment variables
├── .env.example        # Example environment file
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker setup
└── README.md           # This file
```

## Media Download Control

You can control which media files (photos, videos, documents) are downloaded:

### Text-Only Mode (No Media)
```env
MEDIA_MODE=none
```
Downloads only message text — no photos, videos, or documents. Storage usage stays under 500 MB even for millions of messages.

### Selective Mode (Specific Chats Only)
```env
MEDIA_MODE=selective
MEDIA_ALLOW_LIST=123456789,johndoe,-1001234567890
```
Only downloads media from chats whose IDs or usernames are in the allow list. To find chat IDs, run:
```bash
python -m src.main list
```

### Size Limit
```env
MAX_MEDIA_SIZE_MB=10
```
Skip media files larger than 10 MB (0 = unlimited).

### Examples

| Scenario | MEDIA_MODE | Storage |
|----------|-----------|---------|
| Just text, no media | `none` | ~100-500 MB |
| Media from 3 private chats only | `selective` + allow list | ~1-5 GB |
| Everything under 10MB | `all` + size limit | ~10-50 GB |
| All media, no limits | `all` | 100+ GB |

## Rate Limiting

The scraper is configured to send at most 3 messages/second by default. Adjust `RATE_LIMIT_SECONDS` in your `.env` if needed. The scraper handles `FloodWait` errors automatically.

## Resuming

If scraping is interrupted, running `python -m src.main scrape` again will resume from where it left off. Progress is tracked per-chat in the `scrape_progress` table.

## Search Syntax

The search supports:
- Plain text: `hello world`
- Phrase search: `"exact phrase"`
- Field-specific: `chat_name:mygroup sender_name:john`
- Date range: Use the date filters in the UI

## License

MIT