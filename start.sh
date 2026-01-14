#!/bin/bash
# Don't use set -e - we want to see where failures occur
set +e

# Force output to be unbuffered
export PYTHONUNBUFFERED=1

# Log everything to stderr so Railway captures it
exec 2>&1

echo "================================" >&2
echo "STARTING DEPLOYMENT" >&2
echo "================================" >&2
echo "Current directory: $(pwd)" >&2
echo "Python path: $(which python)" >&2
echo "Python version: $(python --version)" >&2

# Run environment check FIRST before anything loads Django
echo "Running environment check..." >&2
python test_env.py
ENV_CHECK_EXIT=$?
if [ $ENV_CHECK_EXIT -ne 0 ]; then
    echo "FATAL: Environment check failed with exit code $ENV_CHECK_EXIT!" >&2
    echo "Fix the environment variables in Railway and redeploy." >&2
    exit 1
fi
echo "Environment check passed!" >&2

# Collect static files
echo "Collecting static files..." >&2
python manage.py collectstatic --noinput 2>&1
STATIC_EXIT=$?
if [ $STATIC_EXIT -ne 0 ]; then
    echo "WARNING: Static files collection failed (exit $STATIC_EXIT), continuing..." >&2
fi

# Run migrations
echo "Running database migrations..." >&2
python manage.py migrate --noinput 2>&1
MIGRATE_EXIT=$?
if [ $MIGRATE_EXIT -ne 0 ]; then
    echo "WARNING: Migrations failed (exit $MIGRATE_EXIT), continuing..." >&2
fi

# Check if this is a cron job (Railway sets CRON_COMMAND env var for cron jobs)
if [ -n "$CRON_COMMAND" ]; then
    echo "================================"
    echo "EXECUTING CRON COMMAND"
    echo "================================"
    echo "Running: python manage.py $CRON_COMMAND"
    exec python manage.py $CRON_COMMAND
fi

# Start gunicorn with verbose logging (web service)
echo "================================" >&2
echo "STARTING WEB SERVICE" >&2
echo "================================" >&2
echo "Starting Gunicorn on port ${PORT:-8000}..." >&2
echo "Environment variables available:" >&2
echo "  - DATABASE_URL: ${DATABASE_URL:+SET}" >&2
echo "  - DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:+SET}" >&2
echo "  - GEMINI_KEY: ${GEMINI_KEY:+SET}" >&2
echo "  - PORT: ${PORT:-8000}" >&2

# Test Django import before starting Gunicorn
echo "Testing Django import..." >&2
python -c "
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '_1nbox_ai.settings')
try:
    import django
    django.setup()
    from django.conf import settings
    print('✓ Django loaded successfully', file=sys.stderr)
except Exception as e:
    print(f'❌ ERROR: Django failed to load: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
" 2>&1
DJANGO_TEST_EXIT=$?
if [ $DJANGO_TEST_EXIT -ne 0 ]; then
    echo "❌ ERROR: Django import test failed with exit code $DJANGO_TEST_EXIT!" >&2
    echo "This usually means there's an error in settings.py or a missing dependency." >&2
    exit 1
fi

# Start Gunicorn with error handling
# Note: --preload removed as it can cause issues with Django apps
echo "Starting Gunicorn server..." >&2
echo "Gunicorn command: gunicorn _1nbox_ai.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120" >&2

# Use exec to replace shell process, but ensure stderr goes to stdout for Railway
exec gunicorn _1nbox_ai.wsgi \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug \
    --capture-output \
    --enable-stdio-inheritance \
    2>&1

