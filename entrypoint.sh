#!/bin/sh
set -e

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Creating superuser if it does not exist..."
python manage.py ensure_superuser

echo "Starting gunicorn..."
exec gunicorn tournament_planner.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --forwarded-allow-ips="*"
