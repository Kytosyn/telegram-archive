FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for SQLite and media processing
RUN apt-get update && apt-get install -y \
    libsqlite3-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/

# Create directories
RUN mkdir -p data media index

# Expose port
EXPOSE 8080

# Default command: start the web server
CMD ["python", "-m", "src.main", "serve"]