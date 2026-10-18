#!/usr/bin/env bash
set -e

echo "Waiting for database to be ready..."
until python -c "
import psycopg
import os
import sys

url = os.getenv('DATABASE_URL', '')
if url.startswith('postgresql+psycopg://'):
    url = url.replace('postgresql+psycopg://', 'postgresql://', 1)
try:
    with psycopg.connect(url) as conn:
        print('PostgreSQL is available!')
        sys.exit(0)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping 1s"
  sleep 1
done

echo "Running database migrations..."
alembic upgrade head

echo "Seeding demo data (idempotent)..."
python -m app.db.seed

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
