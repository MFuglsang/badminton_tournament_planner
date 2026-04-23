# Docker-produktionsplan

Denne fil beskriver alle trin der skal gennemføres for at køre projektet i Docker
med PostgreSQL, Gunicorn og Nginx.

---

## Målarkitektur

```
Internet → port 80/443
              │
         ┌────▼─────┐
         │  nginx   │  serverer /static/ og /media/ direkte
         └────┬─────┘  proxy_pass alt andet → web:8000
              │ intern Docker-netværk
         ┌────▼─────┐
         │  web     │  Django + Gunicorn (2 workers)
         └────┬─────┘
              │
         ┌────▼─────┐
         │  db      │  PostgreSQL 16
         └────┬─────┘
              │
         [volume: postgres_data]   ← persistent database
         [volume: media_data]      ← uploadede filer (logoer m.m.)
         [volume: static_data]     ← collectstatic output (deles med nginx)
```

---

## Trin 1 – Tilpas `requirements.txt`

Tilføj disse to pakker:

```
gunicorn
psycopg2-binary
```

Fuldt indhold af `requirements.txt` når det er gjort:

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

## Trin 2 – Tilpas `tournament_planner/settings.py`

### 2a. Tilføj `import os` øverst i filen

```python
import os
from pathlib import Path
```

### 2b. Erstat `SECRET_KEY`, `DEBUG` og `ALLOWED_HOSTS`

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-skift-mig-i-produktion')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')
```

### 2c. Erstat `DATABASES`-blokken

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

### 2d. Tilføj `STATIC_ROOT`

```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

---

## Trin 3 – Opret `Dockerfile`

Placer i projektets rod:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Saml statiske filer – rammer ikke databasen, er sikker at køre ved build
RUN SECRET_KEY=build-dummy python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "tournament_planner.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120"]
```

---

## Trin 4 – Opret `docker-compose.yml`

Placer i projektets rod:

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

## Trin 5 – Opret `nginx/nginx.conf`

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

## Trin 6 – Opret `.env` (commit ALDRIG denne til git)

Opret `.env` i projektets rod:

```env
SECRET_KEY=skift-til-en-lang-tilfaeldig-streng-mindst-50-tegn
POSTGRES_DB=badminton
POSTGRES_USER=badminton
POSTGRES_PASSWORD=skift-dette-til-noget-sikkert
ALLOWED_HOSTS=localhost,dit-domæne.dk
```

Tilføj til `.gitignore`:

```
.env
```

Generér en SECRET_KEY med Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## Trin 7 – Opret `.dockerignore`

Placer i projektets rod:

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

## Første opstart

```bash
# 1. Byg images
docker compose build

# 2. Start stakken
docker compose up -d

# 3. Kør migrationer (PostgreSQL er tom ved første start)
docker compose exec web python manage.py migrate

# 4. Opret superbruger
docker compose exec web python manage.py createsuperuser

# 5. Tjek logs
docker compose logs -f web
```

---

## Opdatering / re-deploy

```bash
# Byg nyt image og genstart kun web-containeren (db og nginx uberørt)
docker compose build web
docker compose up -d --no-deps web

# Kør eventuelle nye migrationer
docker compose exec web python manage.py migrate
```

---

## Backup af PostgreSQL

```bash
# Dump til fil
docker compose exec db pg_dump -U badminton badminton > backup_$(date +%Y%m%d).sql

# Gendan fra fil
docker compose exec -T db psql -U badminton badminton < backup_20260101.sql
```

---

## Vigtige noter

- **Eksisterende Django-kode kræver ingen ændringer** — views, models og templates er uberørt.
- **Tests kører stadig mod SQLite** via `pytest-django` — PostgreSQL er kun til produktion.
- **OR-Tools** fungerer uændret inde i containeren (installeres via `requirements.txt`).
- **`CONN_MAX_AGE`** kan tilføjes til `DATABASES`-config hvis forbindelsesgenbrug ønskes ved høj belastning: `'CONN_MAX_AGE': 60`.
- **HTTPS**: Tilføj Certbot-container eller brug Caddy i stedet for nginx når et domæne er klar.
