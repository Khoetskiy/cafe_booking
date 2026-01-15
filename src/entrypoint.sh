#!/bin/sh

set -e

echo "Waiting for database..."
while ! nc -z db 5432; do
    sleep 1
done

echo "Applying migrations..."
alembic upgrade head

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
