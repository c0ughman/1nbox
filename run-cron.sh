#!/bin/bash
set -e

echo "================================"
echo "STARTING CRON JOB"
echo "================================"

# Run environment check FIRST before anything loads Django
echo "Running environment check..."
python test_env.py || {
    echo "FATAL: Environment check failed!"
    echo "Fix the environment variables in Railway and redeploy."
    exit 1
}

# Run migrations (in case they're needed)
echo "Running database migrations..."
python manage.py migrate --noinput || {
    echo "WARNING: Migrations failed, continuing..."
}

echo "================================"
echo "EXECUTING MANAGEMENT COMMAND"
echo "================================"

# Execute the management command passed as argument
# Usage: bash run-cron.sh runnews
# Or: bash run-cron.sh runmessage
# Or: bash run-cron.sh runbites

COMMAND="${1:-runnews}"
echo "Running: python manage.py $COMMAND"
python manage.py $COMMAND

echo "================================"
echo "CRON JOB COMPLETED"
echo "================================"

