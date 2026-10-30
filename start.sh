#!/bin/bash
set -e

# Default PORT to 8000 if not provided
PORT="${PORT:-8000}"

# If TELEGRAM_BOT_TOKEN is set, start the Telegram bot in the background
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting ScamShield Telegram Bot in background..."
    python -m app.bot &
fi

echo "Starting ScamShield FastAPI on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
