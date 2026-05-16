#!/bin/bash
#
# Manual restore helper. NEVER runs automatically.
#
# Usage (from host):
#   docker compose run --rm backup /usr/local/bin/restore.sh <db-file.dump.gz> [media-file.tar.gz]
#
# Restores the database into $POSTGRES_DB, dropping existing objects.
# If a media archive is given, EXTRACTS into /media (which is mounted from
# the media_data volume, so files land in the live media volume).
#
set -euo pipefail

DB_ARCHIVE="${1:-}"
MEDIA_ARCHIVE="${2:-}"

if [ -z "$DB_ARCHIVE" ]; then
    echo "Usage: $0 <db-file.dump.gz> [media-file.tar.gz]" >&2
    echo "Files must be inside /backups (the bind-mounted host backup dir)." >&2
    exit 1
fi

[ -f "$DB_ARCHIVE" ] || { echo "Not found: $DB_ARCHIVE" >&2; exit 1; }

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?}"
: "${POSTGRES_PASSWORD:?}"
: "${POSTGRES_DB:?}"

echo
echo "==============================================================="
echo "  About to RESTORE on ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "  This will DROP existing tables in the database."
echo "  DB:    $DB_ARCHIVE"
echo "  Media: ${MEDIA_ARCHIVE:-<none>}"
echo "==============================================================="
read -r -p "Type 'YES' to continue: " CONFIRM
[ "$CONFIRM" = "YES" ] || { echo "Aborted."; exit 1; }

export PGPASSWORD="$POSTGRES_PASSWORD"

echo "[restore] Decompressing and restoring database..."
gunzip -c "$DB_ARCHIVE" \
  | pg_restore \
        --host="$POSTGRES_HOST" \
        --port="$POSTGRES_PORT" \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges

if [ -n "$MEDIA_ARCHIVE" ]; then
    [ -f "$MEDIA_ARCHIVE" ] || { echo "Not found: $MEDIA_ARCHIVE" >&2; exit 1; }
    echo "[restore] Extracting media archive into /media ..."
    # Ensure /media is writable in this run (it's read-only when scheduled,
    # but `docker compose run` lets us override mounts via -v if needed).
    tar xzf "$MEDIA_ARCHIVE" -C /media
fi

unset PGPASSWORD
echo "[restore] Done."
