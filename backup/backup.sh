#!/bin/bash
#
# Daily backup of the Badminton Tournament Planner.
# Runs inside the `backup` container.
#
# Produces, in /backups:
#   db-YYYYMMDD-HHMMSS.dump.gz      (pg_dump --format=custom, gzipped)
#   media-YYYYMMDD-HHMMSS.tar.gz    (full /media tree)
#   <basename>.sha256               (integrity sidecar)
#
# Then prunes old archives:
#   - keep last $BACKUP_RETENTION_DAILY  daily snapshots
#   - keep first snapshot of each of the last $BACKUP_RETENTION_MONTHLY months
#
# Optional off-site copy: if $S3_BUCKET is non-empty, every produced file is
# uploaded with `aws s3 cp` (uses standard AWS env vars, plus optional
# $S3_ENDPOINT for non-AWS providers like Backblaze B2 / Cloudflare R2 /
# Hetzner). Local prune does NOT touch the remote — set bucket lifecycle
# rules for off-site retention.
#
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR_INTERNAL:-/backups}"
MEDIA_DIR="${MEDIA_DIR_INTERNAL:-/media}"
RETENTION_DAILY="${BACKUP_RETENTION_DAILY:-14}"
RETENTION_MONTHLY="${BACKUP_RETENTION_MONTHLY:-12}"

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"

mkdir -p "$BACKUP_DIR"

TS=$(date -u +%Y%m%d-%H%M%S)
DB_FILE="$BACKUP_DIR/db-${TS}.dump.gz"
MEDIA_FILE="$BACKUP_DIR/media-${TS}.tar.gz"
SHA_FILE="$BACKUP_DIR/${TS}.sha256"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "Starting backup ${TS}"

# ── Database dump ────────────────────────────────────────────────────────────
export PGPASSWORD="$POSTGRES_PASSWORD"
log "Dumping database '${POSTGRES_DB}' from ${POSTGRES_HOST}:${POSTGRES_PORT}"
pg_dump \
    --host="$POSTGRES_HOST" \
    --port="$POSTGRES_PORT" \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --format=custom \
    --no-owner \
    --no-privileges \
    --compress=0 \
  | gzip -9 > "$DB_FILE"
unset PGPASSWORD
log "  -> $(ls -lh "$DB_FILE" | awk '{print $5, $9}')"

# ── Media archive ────────────────────────────────────────────────────────────
if [ -d "$MEDIA_DIR" ] && [ -n "$(ls -A "$MEDIA_DIR" 2>/dev/null || true)" ]; then
    log "Archiving media tree ${MEDIA_DIR}"
    tar czf "$MEDIA_FILE" -C "$MEDIA_DIR" .
    log "  -> $(ls -lh "$MEDIA_FILE" | awk '{print $5, $9}')"
else
    log "Media directory empty or missing — skipping media archive"
    MEDIA_FILE=""
fi

# ── Integrity sidecar ────────────────────────────────────────────────────────
{
    sha256sum "$DB_FILE"
    [ -n "$MEDIA_FILE" ] && sha256sum "$MEDIA_FILE"
} > "$SHA_FILE"
log "Wrote $SHA_FILE"

# ── Optional off-site sync ───────────────────────────────────────────────────
if [ -n "${S3_BUCKET:-}" ]; then
    AWS_ARGS=()
    if [ -n "${S3_ENDPOINT:-}" ]; then
        AWS_ARGS+=("--endpoint-url" "$S3_ENDPOINT")
    fi
    PREFIX="${S3_PREFIX:-btp}"
    log "Uploading to s3://${S3_BUCKET}/${PREFIX}/"
    aws "${AWS_ARGS[@]}" s3 cp "$DB_FILE"  "s3://${S3_BUCKET}/${PREFIX}/$(basename "$DB_FILE")"  --storage-class STANDARD_IA
    [ -n "$MEDIA_FILE" ] && \
        aws "${AWS_ARGS[@]}" s3 cp "$MEDIA_FILE" "s3://${S3_BUCKET}/${PREFIX}/$(basename "$MEDIA_FILE")" --storage-class STANDARD_IA
    aws "${AWS_ARGS[@]}" s3 cp "$SHA_FILE" "s3://${S3_BUCKET}/${PREFIX}/$(basename "$SHA_FILE")"
    log "Off-site upload complete"
else
    log "S3_BUCKET not set — skipping off-site upload"
fi

# ── Retention prune ──────────────────────────────────────────────────────────
# We treat each file independently: keep the newest N daily archives of each
# kind (db, media, sha), AND keep the oldest one of each calendar month for
# the last M months. Anything else is deleted.
prune_pattern() {
    local pattern="$1"
    local files
    # newest first
    mapfile -t files < <(ls -1 "$BACKUP_DIR"/$pattern 2>/dev/null | sort -r)
    [ "${#files[@]}" -eq 0 ] && return 0

    declare -A keep=()
    declare -A month_first=()

    # Mark newest N as "keep daily"
    for ((i=0; i < ${#files[@]} && i < RETENTION_DAILY; i++)); do
        keep["${files[$i]}"]=1
    done

    # Walk oldest -> newest to find first-of-month within retention window
    local cutoff_year_month
    cutoff_year_month=$(date -u -d "${RETENTION_MONTHLY} months ago" +%Y%m 2>/dev/null \
        || date -u -v-"${RETENTION_MONTHLY}"m +%Y%m)

    mapfile -t asc < <(printf '%s\n' "${files[@]}" | sort)
    for f in "${asc[@]}"; do
        local base=$(basename "$f")
        # extract YYYYMMDD from filename (positions vary by prefix length)
        local stamp
        stamp=$(echo "$base" | grep -oE '[0-9]{8}-[0-9]{6}' | head -n1)
        [ -z "$stamp" ] && continue
        local ym="${stamp:0:6}"
        if [ "$ym" -ge "$cutoff_year_month" ] && [ -z "${month_first[$ym]:-}" ]; then
            month_first[$ym]=1
            keep["$f"]=1
        fi
    done

    for f in "${files[@]}"; do
        if [ -z "${keep[$f]:-}" ]; then
            log "  prune $(basename "$f")"
            rm -f "$f"
        fi
    done
}

log "Pruning old archives (daily=${RETENTION_DAILY}, monthly=${RETENTION_MONTHLY})"
prune_pattern "db-*.dump.gz"
prune_pattern "media-*.tar.gz"
prune_pattern "*.sha256"

# ── Mark success ─────────────────────────────────────────────────────────────
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/.last-success"
log "Backup ${TS} completed successfully"
