#!/bin/bash
#
# Entrypoint for the backup container.
# Sleeps until the configured daily hour, runs backup.sh, repeats.
#
set -euo pipefail

HOUR="${BACKUP_HOUR:-2}"
MINUTE="${BACKUP_MINUTE:-0}"
TZ="${TZ:-UTC}"
export TZ

echo "[entrypoint] Daily backup scheduled for ${HOUR}:$(printf '%02d' "$MINUTE") (${TZ})"

if [ "${BACKUP_ON_START:-0}" = "1" ]; then
    echo "[entrypoint] BACKUP_ON_START=1 - running an initial backup now"
    /usr/local/bin/backup.sh || echo "[entrypoint] initial backup failed (continuing)"
fi

while true; do
    now_epoch=$(date +%s)
    next=$(date -d "today ${HOUR}:$(printf '%02d' "$MINUTE")" +%s)
    if [ "$next" -le "$now_epoch" ]; then
        next=$((next + 86400))
    fi
    sleep_for=$((next - now_epoch))
    echo "[entrypoint] Sleeping ${sleep_for}s until $(date -d "@${next}" '+%Y-%m-%d %H:%M:%S %Z')"
    sleep "$sleep_for"

    echo "[entrypoint] Triggering scheduled backup"
    if /usr/local/bin/backup.sh; then
        echo "[entrypoint] Backup finished OK"
    else
        rc=$?
        echo "[entrypoint] Backup FAILED (exit=$rc) - will retry on next schedule"
    fi
done