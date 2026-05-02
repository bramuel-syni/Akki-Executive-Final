#!/usr/bin/env python3
"""Phase 10 — migrate local-disk uploads to S3/MinIO.

Walks /app/backend/uploads/ (or UPLOADS_DIR), uploads every file via
services.storage_service.get_storage(), rewrites db.documents.storage_key
from the relative disk path to the canonical S3 key, and writes a CSV
report at the path passed as --report (default stdout).

Idempotent — files whose storage_key already exists in S3 (head
returns exists=true) are skipped. Dry-run by default; pass --execute
to actually do it.

Usage:
    STORAGE_BACKEND=s3 \
    S3_ENDPOINT=http://127.0.0.1:9000 S3_ACCESS_KEY=... S3_SECRET_KEY=... \
    python3 scripts/migrate_local_to_s3.py --execute --report /tmp/migration.csv

The script does NOT delete the source files on disk. Keep them until
an operator verifies the migration report.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

import asyncio  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from services import storage_service  # noqa: E402


async def main(execute: bool, report_path: str):
    uploads_root = Path(os.environ.get("UPLOADS_DIR", "/app/backend/uploads"))
    if not uploads_root.exists():
        print(f"uploads dir {uploads_root} does not exist — nothing to migrate")
        return

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[db_name]

    storage = storage_service.get_storage()
    report_rows = []
    migrated = skipped = missing = failed = 0

    async for doc in db.documents.find({}, {"_id": 0, "id": 1, "context_id": 1, "storage_key": 1, "original_filename": 1, "mime_type": 1}):
        key = doc.get("storage_key") or ""
        if not key:
            continue
        # Legacy keys are relative paths like "ctx-id/doc-id.pdf".
        legacy_path = uploads_root / key
        # Canonical key under Phase 10 is context_id/doc_id/filename.
        filename = doc.get("original_filename") or Path(key).name
        canonical = storage_service.make_key(doc["context_id"], doc["id"], filename)
        existing = storage.head(canonical)
        if existing.get("exists"):
            report_rows.append([doc["id"], key, canonical, "skipped_already_in_s3", existing.get("size")])
            skipped += 1
            continue
        if not legacy_path.exists():
            report_rows.append([doc["id"], key, canonical, "missing_on_disk", 0])
            missing += 1
            continue
        try:
            data = legacy_path.read_bytes()
            if execute:
                result = storage.put(canonical, data, content_type=doc.get("mime_type"))
                await db.documents.update_one(
                    {"id": doc["id"]},
                    {"$set": {"storage_key": canonical, "migrated_from_local_at": storage_service.get_storage().backend}},
                )
                report_rows.append([doc["id"], key, canonical, "migrated", result["size"]])
            else:
                report_rows.append([doc["id"], key, canonical, "would_migrate_dryrun", len(data)])
            migrated += 1
        except Exception as e:
            report_rows.append([doc["id"], key, canonical, f"failed:{e}", 0])
            failed += 1

    if report_path and report_path != "-":
        with open(report_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["doc_id", "legacy_key", "new_key", "status", "size_bytes"])
            w.writerows(report_rows)
    else:
        w = csv.writer(sys.stdout)
        w.writerow(["doc_id", "legacy_key", "new_key", "status", "size_bytes"])
        w.writerows(report_rows)
    print(f"\nMIGRATED={migrated}  SKIPPED={skipped}  MISSING={missing}  FAILED={failed}  EXECUTE={execute}", file=sys.stderr)
    mongo.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true", help="Actually perform the migration. Default is dry-run.")
    p.add_argument("--report", default="-", help="CSV report path, or - for stdout.")
    args = p.parse_args()
    asyncio.run(main(args.execute, args.report))
