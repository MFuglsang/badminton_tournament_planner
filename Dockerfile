FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files – does not touch the database and is safe to run during build
RUN SECRET_KEY=build-dummy python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "tournament_planner.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120"]
