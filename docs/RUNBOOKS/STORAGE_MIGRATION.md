# Runbook — Local-disk → S3/MinIO migration

_Phase 10 / Item B. Only needed when a deploy crosses Phase 10 with a populated `/app/backend/uploads/` directory._

## Preconditions

- `STORAGE_BACKEND=s3` is set in the backend env.
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` are set and the bucket exists. `storage_service` auto-creates the bucket on first `put`.
- Mongo is reachable from the host running the script.

## Dry run (always run this first)

```bash
cd /app
python3 scripts/migrate_local_to_s3.py --report /tmp/migration.dryrun.csv
less /tmp/migration.dryrun.csv
```

The report rows carry one of the following statuses:

| status                   | meaning                                                                 |
|--------------------------|-------------------------------------------------------------------------|
| `would_migrate_dryrun`   | Source found on disk, target absent from S3; migration would run.       |
| `skipped_already_in_s3`  | Target already present. Idempotent no-op.                               |
| `missing_on_disk`        | DB row points at a legacy key, but the file is gone. Operator decides.  |
| `failed:...`             | Read or upload raised. Investigate before re-running.                   |

## Execute

```bash
python3 scripts/migrate_local_to_s3.py --execute --report /tmp/migration.live.csv
```

This rewrites `db.documents.storage_key` to the canonical S3 key. The script is idempotent — a second run finishes with every row `skipped_already_in_s3`.

## Post-migration verification

1. `grep -c ',migrated,' /tmp/migration.live.csv` should match the expected count.
2. Spot-check: open `/app/workspace`, pick a migrated document, hit Download. Expected: a 302 to a presigned URL.
3. Backend log line `akki.storage  storage backend initialised: s3`.

## Cleaning up local disk

Leave `/app/backend/uploads/` in place for **at least 14 days** after the migration. The script does not delete source files. Once you're satisfied, `rm -rf /app/backend/uploads/` or leave it; the code no longer writes there.

## Rollback

Set `STORAGE_BACKEND=local` and restart the backend. Legacy rows continue to resolve from disk via the `services.storage_service.read()` fallback. Migrated rows will 410 because the storage_key is the S3 canonical — run `scripts/migrate_local_to_s3.py` in reverse (trivial extension: swap source/target). We recommend not rolling back after 24 h of normal traffic.
