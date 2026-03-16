# ──────────────────────────────────────────────────
# Optimized Python-only Dockerfile
# (Frontend is hosted separately on Vercel)
# ──────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# System deps for Whisper + audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
# We install the CPU version of torch first to prevent large GPU package downloads
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend + scripts
COPY backend/ ./backend/
COPY scripts/ ./scripts/
# Copy secrets only if they exist (ignored by git, but might be provided in custom builds)
COPY secrets* ./secrets/

# Copy model files (if present in build context)
COPY kokoro-v0_19.onnx* ./
COPY voices.bin* ./

# Ensure a dummy frontend folder exists so main.py doesn't error out looking for paths
RUN mkdir -p frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
