# NEXA LMS backend: FastAPI + uvicorn. Migrations run on container start.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Tesseract OCR for scanned book pages (Book-to-Test, services/ocr_tesseract.py):
# English, Russian and Kazakh language data
RUN apt-get update     && apt-get install -y --no-install-recommends         tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus tesseract-ocr-kaz     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Unprivileged user; uploaded files live in a volume mounted at /app/storage
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/storage \
    && chown -R app:app /app/storage \
    && chmod +x /app/docker-entrypoint.sh
USER app

ENV ENVIRONMENT=production \
    DEBUG=false \
    LOCAL_STORAGE_PATH=/app/storage \
    WEB_CONCURRENCY=2

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
