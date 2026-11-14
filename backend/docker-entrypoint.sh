#!/bin/sh
# Apply database migrations, then start the API.
# Several workers are safe: real-time events go through PostgreSQL LISTEN/NOTIFY,
# so every worker receives them (see app/services/realtime.py).
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting uvicorn with ${WEB_CONCURRENCY:-2} workers"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
