#!/bin/bash
# Phase 10 — Mongo restore.
#
# Usage:
#   scripts/restore_mongo.sh /tmp/akki-backups/akki_dev-20251201T030000Z/akki_dev-20251201T030000Z.archive.gz akki_restored

set -euo pipefail

ARCHIVE="${1:-}"
TARGET_DB="${2:-}"

if [ -z "${ARCHIVE}" ] || [ -z "${TARGET_DB}" ]; then
  echo "usage: $0 <archive.gz> <target-db-name>"
  exit 2
fi
if [ ! -f "${ARCHIVE}" ]; then
  echo "archive not found: ${ARCHIVE}"
  exit 2
fi

: "${MONGO_URL:=$(grep '^MONGO_URL=' /app/backend/.env | cut -d= -f2-)}"

echo "[$(date -u -Iseconds)] mongorestore → ${TARGET_DB}"
mongorestore --uri="${MONGO_URL}" --nsFrom='*.*' --nsTo="${TARGET_DB}.*" --gzip --archive="${ARCHIVE}" --drop
echo "[$(date -u -Iseconds)] done."
