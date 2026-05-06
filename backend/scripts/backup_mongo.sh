#!/usr/bin/env bash
# Daily MongoDB backup script for WatchNexus Licensing Server.
# Usage:  ./backup_mongo.sh [retention_days]
# Cron:   0 3 * * *  /app/backend/scripts/backup_mongo.sh 14 >> /var/log/watchnexus_backup.log 2>&1
set -euo pipefail

MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
DB_NAME="${DB_NAME:-test_database}"
BACKUP_DIR="${BACKUP_DIR:-/app/backend/backups}"
RETENTION="${1:-14}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUT="$BACKUP_DIR/watchnexus_${DB_NAME}_${STAMP}"

echo "[$(date -u +%FT%TZ)] Starting backup -> $OUT"
if command -v mongodump >/dev/null 2>&1; then
  mongodump --uri="$MONGO_URL" --db="$DB_NAME" --out="$OUT"
  tar -czf "${OUT}.tar.gz" -C "$BACKUP_DIR" "$(basename "$OUT")"
  rm -rf "$OUT"
  echo "Backup complete: ${OUT}.tar.gz"
else
  echo "mongodump not found - falling back to JSON export via Python."
  python3 - <<PY
import json, os, datetime, pathlib
from pymongo import MongoClient
cli = MongoClient(os.environ.get("MONGO_URL", "$MONGO_URL"))
dbn = os.environ.get("DB_NAME", "$DB_NAME")
db = cli[dbn]
out = pathlib.Path("$OUT")
out.mkdir(parents=True, exist_ok=True)
for coll in db.list_collection_names():
    docs = list(db[coll].find({}, {"_id": 0}))
    (out / f"{coll}.json").write_text(json.dumps(docs, default=str, indent=2))
print("JSON export complete")
PY
  tar -czf "${OUT}.tar.gz" -C "$BACKUP_DIR" "$(basename "$OUT")"
  rm -rf "$OUT"
fi

# Retention
find "$BACKUP_DIR" -name "watchnexus_*.tar.gz" -type f -mtime +$RETENTION -delete
echo "[$(date -u +%FT%TZ)] Retention applied (>$RETENTION days deleted)"
