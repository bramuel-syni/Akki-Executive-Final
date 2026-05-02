#!/bin/bash
# Phase 10 / Item D — Mongo backup.
#
# Produces a gzipped mongodump archive. Writes to BACKUP_DIR by
# default; if BACKUP_S3_PATH is set, pushes the archive through the
# same object storage backend the app uses (S3/MinIO).
#
# Usage:
#   scripts/backup_mongo.sh
#   BACKUP_DIR=/var/backups/akki scripts/backup_mongo.sh
#   BACKUP_S3_PATH=akki-uploads/backups/ scripts/backup_mongo.sh

set -euo pipefail

: "${MONGO_URL:=$(grep '^MONGO_URL=' /app/backend/.env | cut -d= -f2-)}"
: "${DB_NAME:=$(grep '^DB_NAME=' /app/backend/.env | cut -d= -f2-)}"
: "${BACKUP_DIR:=/tmp/akki-backups}"

TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${BACKUP_DIR}/${DB_NAME}-${TS}"
mkdir -p "${OUT_DIR}"

echo "[$(date -u -Iseconds)] mongodump → ${OUT_DIR}"
mongodump --uri="${MONGO_URL}" --db="${DB_NAME}" --gzip --archive="${OUT_DIR}/${DB_NAME}-${TS}.archive.gz"

# Manifest — lightweight audit trail alongside the archive.
cat > "${OUT_DIR}/manifest.txt" <<EOF
akki-mongo-backup
database: ${DB_NAME}
taken_at: ${TS}
host:     $(hostname)
script:   $(basename "$0")
EOF

if [ -n "${BACKUP_S3_PATH:-}" ]; then
  echo "[$(date -u -Iseconds)] uploading to s3:${BACKUP_S3_PATH}"
  python3 - <<PY
import sys
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
import os
from pathlib import Path
from services import storage_service
storage = storage_service.get_storage()
src_dir = Path('${OUT_DIR}')
prefix = '${BACKUP_S3_PATH}'.strip('/')
for p in src_dir.iterdir():
    key = f"{prefix}/${DB_NAME}-${TS}/{p.name}"
    storage.put(key, p.read_bytes(), content_type='application/octet-stream')
    print(f'  uploaded {key}  size={p.stat().st_size}')
PY
fi

echo "[$(date -u -Iseconds)] done."
