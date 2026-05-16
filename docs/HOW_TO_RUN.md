# How to Run the Badminton Tournament Planner

## Prerequisites
1. **Python**: Ensure Python 3.13.9 or higher is installed.
2. **Virtual Environment**: Use a virtual environment to manage dependencies.
3. **Django**: The application is built using Django 6.0.4.

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd badminton_tournament_planner
```

### 2. Create and Activate a Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
call .venv\Scripts\activate.bat  # Windows Command Prompt
& .venv\Scripts\Activate.ps1     # Windows PowerShell
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Migrations
```bash
python manage.py migrate
```

### 5. Create a Superuser
```bash
python manage.py createsuperuser
```
Follow the prompts to set up an admin account.

### 6. Start the Development Server
```bash
python manage.py runserver
```

---

## Access the Application
- **Homepage**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Tournaments**: [http://127.0.0.1:8000/tournaments/](http://127.0.0.1:8000/tournaments/)
- **Players**: [http://127.0.0.1:8000/players/](http://127.0.0.1:8000/players/)
- **Admin Panel**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## Workflow: Set Up and Run a Tournament

1. **Create players** via `/admin/players/player/add/` or `/players/add/`.
2. **Create teams** (pairs of players) via `/admin/players/team/add/` or `/players/teams/add/`.
3. **Create a tournament** via `/admin/tournaments/tournament/add/`.
4. **Create divisions** under the tournament via `/admin/tournaments/division/add/`, then add teams to each division.
5. **Generate the match programme** by visiting the tournament page (`/tournaments/<id>/`) and clicking **Generate match programme** for a division.
6. **Record results** by clicking **Record result** for the individual matches.

---

## Docker (production)

See [docs/dockerplan.md](docs/dockerplan.md) for the full architecture overview and operational guide.

### Quick start

```bash
# 1. Copy the example env file and set your secrets
cp .env.example .env
#    Edit .env: fill in SECRET_KEY, POSTGRES_PASSWORD, and ALLOWED_HOSTS

# 2. Build and start all services (Postgres + Django/Gunicorn + Nginx)
docker compose build
docker compose up -d

# 3. Apply database migrations (first run only)
docker compose exec web python manage.py migrate

# 4. Create an admin account
docker compose exec web python manage.py createsuperuser
```

The application is then available at **http://localhost/**.

### Stack

| Service | Image / role |
|---------|-------------|
| `db`    | PostgreSQL 16-alpine — persistent data on a named volume |
| `web`   | Python 3.13-slim — Django served by Gunicorn (2 workers) |
| `nginx` | nginx:alpine — reverse proxy, serves `/static/` and `/media/` directly |

All three services communicate on an isolated Docker network (`internal`).
PostgreSQL data, media uploads, and collected static files are stored on
named Docker volumes so data survives container restarts.

---

## Backups & restore

A dedicated `backup` service runs alongside the application and produces a
full snapshot every night at **02:00** server local time:

- `db-YYYYMMDD-HHMMSS.dump.gz` — `pg_dump --format=custom`, gzipped
- `media-YYYYMMDD-HHMMSS.tar.gz` — uploaded media files
- `YYYYMMDD-HHMMSS.sha256` — integrity sidecar

Archives land in **`./backups/`** on the host (a bind-mount). Retention:
last 14 daily snapshots + first snapshot of each of the last 12 months.

### Configure (in `.env`)

```ini
# Required (already set for the app)
POSTGRES_DB=badminton
POSTGRES_USER=badminton
POSTGRES_PASSWORD=...

# Optional — defaults shown
BACKUP_DIR=./backups          # host directory for archives
BACKUP_HOUR=2                  # 0-23, when to run daily
BACKUP_RETENTION_DAILY=14
BACKUP_RETENTION_MONTHLY=12
BACKUP_ON_START=0              # set 1 to run a backup immediately when container starts
TZ=Europe/Copenhagen

# Optional off-site sync — leave empty to disable
S3_BUCKET=                     # e.g. my-btp-backups
S3_PREFIX=btp                  # path prefix inside the bucket
S3_ENDPOINT=                   # e.g. https://s3.eu-central-003.backblazeb2.com (omit for AWS)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=eu-central-1
```

### Run

```bash
docker compose up -d backup
docker compose logs -f backup           # tail backup output
docker compose exec backup /usr/local/bin/backup.sh   # trigger one immediately
```

### Restore (manual)

```bash
# Restore database only
docker compose run --rm backup \
    /usr/local/bin/restore.sh /backups/db-20260516-020000.dump.gz

# Restore database AND media
docker compose run --rm backup \
    /usr/local/bin/restore.sh \
        /backups/db-20260516-020000.dump.gz \
        /backups/media-20260516-020000.tar.gz
```

The restore script asks for `YES` confirmation before dropping anything.

### Off-site copy

When `S3_BUCKET` is set, every produced archive is also uploaded to the
bucket with `aws s3 cp`. Use bucket lifecycle rules for off-site retention
(local prune does not touch the remote). Works with any S3-compatible
provider — AWS, Backblaze B2, Cloudflare R2, Hetzner Object Storage etc.

### Restore drill (recommended quarterly)

1. Spin up a throwaway Postgres + this backup service pointing at it
2. Run `restore.sh` against the latest dump
3. Run `python manage.py check` and verify tournament/player counts

---

## Notes
- For local development, set `DEBUG=True` in your shell or `.env` before running `runserver`.
- For production, set `SECRET_KEY`, `ALLOWED_HOSTS`, and all `POSTGRES_*` variables via the `.env` file (see Docker section above).
- Templates for the project homepage are in `tournament_planner/templates/`.
- App-specific templates are in `<app>/templates/<app>/`.