# Runbook 02 — Mongo connection saturation

**Sprint:** P1 κ (2026-02)
**Owner:** on-call backend
**Severity:** SEV-1 (all backend write endpoints fail)

## Detection signals

| Signal | Where |
|---|---|
| `pymongo.errors.ConnectionFailure` in backend logs | Supervisor backend logs |
| `5xx` rate on `/api/*` spikes | Sentry / status endpoint |
| `motor` connection pool exhausted warnings | Backend logs |
| Mongo Atlas / self-host: "connection limit reached" alert | Atlas dashboard |
| Frontend toast "Could not load..." surfacing across surfaces | User reports |

## First 3 mitigation steps

1. **Confirm the issue.** Run:
   ```bash
   python3 -c "
   import os, pymongo
   from dotenv import load_dotenv
   load_dotenv('/app/backend/.env')
   c = pymongo.MongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=3000)
   c.admin.command('ping')
   print('Mongo OK')
   "
   ```
   If this fails with `ServerSelectionTimeoutError` → confirmed saturation
   or network partition.

2. **Restart backend to reclaim connections.**
   ```bash
   sudo supervisorctl restart backend
   ```
   This drops the existing motor connection pool and rebuilds it.
   Healthy in-flight sessions are dropped but their data is committed
   (Mongo writes are atomic per document).

3. **Identify long-running queries hogging connections.**
   ```python
   db.command("currentOp", {"active": True, "secs_running": {"$gt": 30}})
   ```
   Kill ids that exceed the cutoff:
   ```python
   db.command("killOp", {"op": <opid>})
   ```

## Escalation path

- **First 5 min:** on-call engineer attempts mitigation steps 1-3
- **5-15 min:** if not resolved, escalate to product owner + scale
  cluster (Atlas: bump M-tier; self-host: add a replica)
- **15+ min:** open incident on status page

## Post-incident checklist

- [ ] Connection pool sized appropriately for peak load (default
      `maxPoolSize=100`; review if regularly hit)
- [ ] Slow queries identified + indexed
- [ ] Audit log shows no data loss for in-flight sessions
- [ ] Capacity plan revised if this is a load-growth trigger
- [ ] Atlas alert thresholds tuned
