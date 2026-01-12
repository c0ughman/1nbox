web: python manage.py collectstatic --noinput; python manage.py migrate --noinput; gunicorn _1nbox_ai.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120
