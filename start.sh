#!/bin/bash
set -e

echo "================================"
echo "STARTING DEPLOYMENT"
echo "================================"

# Print ALL environment variables to debug
echo "=== ENVIRONMENT CHECK ==="
echo "PORT: ${PORT:-NOT SET}"
echo "DATABASE_URL exists: $(if [ -n "$DATABASE_URL" ]; then echo YES; else echo NO; fi)"
echo "DATABASE_URL first 30 chars: ${DATABASE_URL:0:30}..."
echo "DJANGO_SECRET_KEY exists: $(if [ -n "$DJANGO_SECRET_KEY" ]; then echo YES; else echo NO; fi)"
echo "FIREBASE_PROJECT_ID: ${FIREBASE_PROJECT_ID:-NOT SET}"
echo "FIREBASE_PRIVATE_KEY exists: $(if [ -n "$FIREBASE_PRIVATE_KEY" ]; then echo YES; else echo NO; fi)"
echo "FIREBASE_PRIVATE_KEY starts with: ${FIREBASE_PRIVATE_KEY:0:25}"
echo "========================="

# Test Python import
echo "Testing Python and Django import..."
python -c "import django; print(f'Django version: {django.get_version()}')"

# Test settings import
echo "Testing settings import..."
python -c "from django.conf import settings; print('Settings loaded successfully')" || {
    echo "FATAL: Settings failed to load!"
    exit 1
}

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || {
    echo "WARNING: Static files collection failed, continuing..."
}

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput || {
    echo "WARNING: Migrations failed, continuing..."
}

# Test that health endpoint is accessible
echo "Testing Django setup..."
python manage.py check || {
    echo "WARNING: Django check failed, continuing..."
}

# Start gunicorn with verbose logging
echo "Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn _1nbox_ai.wsgi \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --capture-output \
    --enable-stdio-inheritance

