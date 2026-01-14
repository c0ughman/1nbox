#!/bin/bash
set -e

echo "================================"
echo "STARTING DEPLOYMENT"
echo "================================"

# Run environment check FIRST before anything loads Django
echo "Running environment check..."
python test_env.py || {
    echo "FATAL: Environment check failed!"
    echo "Fix the environment variables in Railway and redeploy."
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

# Check if this is a cron job (Railway sets CRON_COMMAND env var for cron jobs)
if [ -n "$CRON_COMMAND" ]; then
    echo "================================"
    echo "EXECUTING CRON COMMAND"
    echo "================================"
    echo "Running: python manage.py $CRON_COMMAND"
    exec python manage.py $CRON_COMMAND
fi

# Start gunicorn with verbose logging (web service)
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

