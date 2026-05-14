#!/bin/sh
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it does not exist..."
python manage.py ensure_superuser

echo "Starting gunicorn..."
exec gunicorn tournament_planner.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120
