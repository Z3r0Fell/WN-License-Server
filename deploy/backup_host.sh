#!/usr/bin/env bash
# WatchNexus host-side MongoDB backup.
# Invoked by systemd timer (watchnexus-backup.service).
# Uses `mongodump` from inside the running `mongo` container (which always
# has it) and writes the resulting archive to the shared ./backups volume.
#
# Usage: backup_host.sh [retention_days]
set -Eeuo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/watchnexus/deploy}"
RETENTION="${1:-14}"
DB_NAME="$(grep -E '^DB_NAME=' "$DEPLOY_DIR/.env" 2>/dev/null | cut -d= -f2-)"
DB_NAME="${DB_NAME:-watchnexus}"

cd "$DEPLOY_DIR"

STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
ARCHIVE="/backups/watchnexus_${DB_NAME}_${STAMP}.archive.gz"

echo "[$(date -u +%FT%TZ)] Starting backup -> $ARCHIVE"
docker compose exec -T mongo mongodump \
    --db="$DB_NAME" \
    --archive="$ARCHIVE" \
    --gzip
echo "Backup complete."

# Retention (delete files older than $RETENTION days). The ./backups dir is
# bind-mounted from the host at $DEPLOY_DIR/backups.
find "$DEPLOY_DIR/backups" -name "watchnexus_*.archive.gz" -type f -mtime "+$RETENTION" -delete || true
echo "[$(date -u +%FT%TZ)] Retention applied (>$RETENTION days deleted)"
