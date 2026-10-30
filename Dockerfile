FROM python:3.10-slim

# Install system dependencies (ffmpeg is required for audio transcription and live calls)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and data
COPY . .

# Ensure data directory exists
RUN mkdir -p data

# Ensure startup script is executable
RUN chmod +x start.sh

# Expose default port (overridden by cloud providers via $PORT)
EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

CMD ["./start.sh"]
