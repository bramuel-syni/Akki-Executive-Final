# Runbook — Mongo backup & restore

_Phase 10 / Item D. Scripts are present in this environment; a live cron is NOT configured in this container — it is the operator's responsibility on the target host._

## Scripts

| Path                                | Purpose                                    |
|-------------------------------------|--------------------------------------------|
| `scripts/backup_mongo.sh`           | `mongodump --gzip` to `BACKUP_DIR` (or S3) |
| `scripts/restore_mongo.sh <archive> <db>` | `mongorestore` into a target DB      |

## Daily cron example

Run at 03:00 UTC on the primary host. Crontab snippet:

```cron
# akki — daily mongo backup at 03:00 UTC
0 3 * * *  /app/scripts/backup_mongo.sh >> /var/log/akki-backup.log 2>&1
```

If you want the archive shipped to object storage as well, set
`BACKUP_S3_PATH` in the environment of the cron — the script will use
the same `services/storage_service.py` the app uses (so it works
against MinIO in dev and real S3 in prod).

## Retention policy

| Tier     | Kept for | Cadence                          |
|----------|----------|----------------------------------|
| Daily    | 14 days  | Every night (cron above)         |
| Weekly   | 8 weeks  | Snapshot of Sunday's daily       |
| Monthly  | 12 months| Snapshot of the 1st of the month |

Rotation is operator-enforced on the host (a simple `find -mtime +14 -delete` alongside the cron is sufficient for the daily tier). Weekly and monthly snapshots are copies of the daily into `$BACKUP_DIR/weekly/` / `$BACKUP_DIR/monthly/` taken by a separate rule.

## Restore drill (quarterly)

Every quarter, verify the backup by restoring into a staging DB and spot-checking a handful of known rows.

```bash
# On the staging host, clone the latest nightly
LATEST=$(ls -1t /var/backups/akki/ | head -1)
scripts/restore_mongo.sh "/var/backups/akki/${LATEST}/*.archive.gz" akki_restore_drill

mongosh "mongodb://localhost:27017/akki_restore_drill" --eval '
  print("accounts:", db.accounts.countDocuments({}));
  print("documents:", db.documents.countDocuments({}));
  print("briefings:", db.briefings.countDocuments({}));
'
```

A drill is considered passed when the three counts are within 1 % of the primary's counts at the archive's timestamp.

## RPO / RTO

- **RPO (Recovery Point Objective): 24 hours.** Worst-case loss is the day's writes between the nightly dump and the incident.
- **RTO (Recovery Time Objective): 1 hour.** A mongodump archive of AKKI at current scale restores in minutes; the one-hour budget covers DNS cut-over and app restart on the standby.

Shortening RPO to < 1 h is a Phase 12+ decision (either Mongo oplog tailing, Atlas continuous backup, or a replica-set primary in a second AZ).

## Where the script does NOT run in this environment

The repo's sandbox / preview container does NOT wire the cron in, intentionally. This runbook is the contract the operator executes on the target host.
