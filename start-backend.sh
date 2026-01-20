#!/bin/bash

# Start Django backend server
cd 1nbox

# Set DEBUG for local development
export DEBUG=true

# Run migrations if needed
echo "Checking database migrations..."
python3 manage.py migrate --noinput 2>&1 | grep -v "No changes detected" || true

# Start the server
echo "Starting Django backend on http://localhost:8000..."
python3 manage.py runserver 8000


