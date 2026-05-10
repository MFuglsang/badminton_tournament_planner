# Docker Production Plan

This file describes all steps required to run the project in Docker
with PostgreSQL, Gunicorn, and Nginx.

---

## Target Architecture

```
Internet → port 80/443
              │
         ┌────▼─────┐
         │  nginx   │  serves /static/ and /media/ directly
         └────┬─────┘  proxy_pass everything else → web:8000
              │ internal Docker network
         ┌────▼─────┐
         │  web     │  Django + Gunicorn (2 workers)
         └────┬─────┘
              │
         ┌────▼─────┐
         │  db      │  PostgreSQL 16
         └────┬─────┘
              │
         [volume: postgres_data]   ← persistent database
         [volume: media_data]      ← uploaded files (logos, etc.)
         [volume: static_data]     ← collectstatic output (shared with nginx)
```

---

## Step 1 – Update `requirements.txt`

Add these two packages:

```
gunicorn
psycopg2-binary
```

Full contents of `requirements.txt` after that change:

```
django
pillow
pytest
pytest-django
coverage
ortools
gunicorn
psycopg2-binary
```

---

## Step 2 – Update `tournament_planner/settings.py`

### 2a. Add `import os` at the top of the file

```python
import os
from pathlib import Path
```

### 2b. Replace `SECRET_KEY`, `DEBUG`, and `ALLOWED_HOSTS`

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')
```

### 2c. Replace the `DATABASES` block

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'badminton'),
        'USER': os.environ.get('POSTGRES_USER', 'badminton'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}
```

### 2d. Add `STATIC_ROOT`

```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

---

## Step 3 – Create `Dockerfile`

Place it in the project root:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files - does not touch the database and is safe to run during build
RUN SECRET_KEY=build-dummy python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "tournament_planner.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120"]
```

---

## Step 4 – Create `docker-compose.yml`

Place it in the project root:

```yaml
services:

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-badminton}
      POSTGRES_USER: ${POSTGRES_USER:-badminton}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-badminton}"]
      interval: 5s
      timeout: 5s
      retries: 10

  web:
    build: .
    restart: unless-stopped
    environment:
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: "False"
      ALLOWED_HOSTS: ${ALLOWED_HOSTS:-localhost}
      POSTGRES_DB: ${POSTGRES_DB:-badminton}
      POSTGRES_USER: ${POSTGRES_USER:-badminton}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_HOST: db
      POSTGRES_PORT: "5432"
    volumes:
      - media_data:/app/media
      - static_data:/app/staticfiles
    depends_on:
      db:
        condition: service_healthy

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - static_data:/static:ro
      - media_data:/media:ro
    depends_on:
      - web

volumes:
  postgres_data:
  media_data:
  static_data:
```

---

## Step 5 – Create `nginx/nginx.conf`

```nginx
server {
    listen 80;
    client_max_body_size 20M;

    location /static/ {
        alias /static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /media/;
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

---

## Step 6 – Create `.env` (NEVER commit this file to git)

Create `.env` in the project root:

```env
SECRET_KEY=change-to-a-long-random-string-at-least-50-characters
POSTGRES_DB=badminton
POSTGRES_USER=badminton
POSTGRES_PASSWORD=change-this-to-something-secure
ALLOWED_HOSTS=localhost,your-domain.example
```

Add this to `.gitignore`:

```
.env
```

Generate a SECRET_KEY with Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## Step 7 – Create `.dockerignore`

Place it in the project root:

```
.venv/
__pycache__/
*.pyc
*.pyo
db.sqlite3
.env
.git/
```

---

## First Startup

```bash
# 1. Build the images
docker compose build

# 2. Start the stack
docker compose up -d

# 3. Run migrations (PostgreSQL is empty on first start)
docker compose exec web python manage.py migrate

# 4. Create a superuser
docker compose exec web python manage.py createsuperuser

# 5. Check the logs
docker compose logs -f web
```

---

## Update / Re-deploy

```bash
# Build a new image and restart only the web container (db and nginx unchanged)
docker compose build web
docker compose up -d --no-deps web

# Run any new migrations
docker compose exec web python manage.py migrate
```

---

## PostgreSQL Backup

```bash
# Dump to a file
docker compose exec db pg_dump -U badminton badminton > backup_$(date +%Y%m%d).sql

# Restore from a file
docker compose exec -T db psql -U badminton badminton < backup_20260101.sql
```

---

## Important Notes

- **The existing Django code does not require changes** — views, models, and templates remain untouched.
- **Tests still run against SQLite** via `pytest-django` — PostgreSQL is only for production.
- **OR-Tools** works unchanged inside the container (installed via `requirements.txt`).
- **`CONN_MAX_AGE`** can be added to the `DATABASES` config if connection reuse is desired under heavy load: `'CONN_MAX_AGE': 60`.
- **HTTPS**: Add a Certbot container or use Caddy instead of nginx once a domain is ready.
