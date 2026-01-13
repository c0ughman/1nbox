#!/bin/bash
set -e

echo "================================"
echo "STARTING DEPLOYMENT"
echo "================================"

# Print environment variables (sanitized)
echo "PORT: $PORT"
echo "DATABASE_URL: ${DATABASE_URL:0:20}..."
echo "DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:0:10}..."
echo "FIREBASE_PROJECT_ID: $FIREBASE_PROJECT_ID"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Start gunicorn with verbose logging
echo "Starting Gunicorn..."
exec gunicorn _1nbox_ai.wsgi \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --capture-output \
    --enable-stdio-inheritance

