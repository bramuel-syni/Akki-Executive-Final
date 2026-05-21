# Phase E.A — ClamAV gap-fill — DONE (2026-05-21)

Anchor for the autonomous-mode hardening sprint. The dispatch framed
ClamAV as "still a mock" — the file-wins audit at the start of this
phase showed otherwise: clamd was already wired through 8 upload
entry points with real `INSTREAM` over TCP. The actual delta was
size pre-reject, audit collection, sidecar-DNS host default, boot
guard hardening (option c), and a unified test file.

## Scope ledger

| Item | Status |
|------|--------|
| `CLAMAV_MAX_FILE_SIZE_MB` env (default 25 MB) + uniform 413 BEFORE clamd | ✅ via `FileTooLarge(HTTPException)` raised in `scan()` itself; every entry point inherits the same 413 body shape |
| `upload_scan_log` Mongo collection (file_id · user_id · filename · size_bytes · scan_result · signature · scanned_at · duration_ms) | ✅ written by `_log_scan()` from `scan()` regardless of outcome |
| `CLAMAV_HOST` default flipped from `127.0.0.1` → `clamd` | ✅ (sidecar-DNS convention; matches `docker-compose.yml` service name) |
| `.env.example` updated | ✅ added `CLAMAV_MAX_FILE_SIZE_MB` row + flipped default-host comment |
| Top-level `docker-compose.yml` for local dev | ✅ created (Mongo + Mongo Express + MinIO + clamd sidecar with 240s start_period healthcheck) |
| Unified `tests/test_clamav_integration.py` (4 acceptance cases + 3 boot-guard cases) | ✅ 7 tests, all passing |
| Legacy `test_patch_22_clamav.py` migrated to async signature | ✅ 5 tests still passing |
| `routers/admin_health.py` `/admin/health/full` surfaces `clamav` check with `scans_24h` breakdown by `scan_result` | ✅ added `_check_clamav()` |
| Option (c) boot guard — refuse `AKKI_ENV=production` + `ALLOW_UNSAFE_UPLOADS=true` | ✅ `assert_safe_boot()` raises at startup; 3 dedicated tests |
| Boot log line declaring active mode | ✅ confirmed in backend logs: `clamav: dev escape hatch ARMED — uploads will bypass scan if clamd unreachable (AKKI_ENV='(unset)')` |

## Files touched

| File | Action |
|------|--------|
| `backend/services/clamav_service.py` | Rewrite (async `scan` + `_scan_blocking` exec; `FileTooLarge`; `assert_safe_boot`; `_log_scan`; `ScanResult.bypassed` explicit flag; default host = `"clamd"`; `CLAMAV_MAX_FILE_SIZE_MB` constants) |
| `backend/server.py` | Added clamav boot-guard call inside `on_startup` with mode-aware log line |
| `backend/routers/admin_health.py` | Added `_check_clamav()` + wired into `admin_health_full` |
| `backend/routers/documents.py` | `await scan(..., file_id=doc_id, user_id=ctx["account"]["id"])`; moved `doc_id = str(uuid.uuid4())` ABOVE scan call so the audit row carries the persisted document's id |
| `backend/routers/chat.py` | `await scan(..., file_id=doc_id, user_id=current["id"])` |
| `backend/routers/daily_review.py` | `await scan(..., file_id=qid, user_id=account["id"])` |
| `backend/routers/inbound_email.py` | `await scan(..., file_id=message_id, user_id=account["id"])` |
| `backend/routers/inbound_queue.py` | `await scan(...)` at two call sites (initial intake + retry) |
| `backend/routers/solva_phase_d.py` | `await scan(..., file_id=session_id, user_id=ctx["account"]["id"])` |
| `backend/routers/studio_blocks.py` | `await scan(..., file_id=artefact_id, user_id=current["id"])` |
| `backend/routers/work_studio_export.py` | `await scan(..., user_id=account_id)` |
| `backend/tests/test_clamav_integration.py` | NEW — 4 scenario tests + 3 boot-guard tests |
| `backend/tests/test_patch_22_clamav.py` | Updated `fake_scan` to `async def`; renamed `unsafe` → `dev-bypass` in healthcheck assertion |
| `.env.example` | Added `CLAMAV_MAX_FILE_SIZE_MB=25`; flipped default-host comment to `clamd` |
| `docker-compose.yml` | NEW — top-level local-dev compose with clamd sidecar |

13 files. No new libraries (clamd python pkg was already in requirements.txt at v1.0.2).

## `upload_scan_log` schema (final)

```javascript
{
  file_id:    <string>     // canonical document/session/artefact id
  user_id:    <string?>    // account id, null if surface didn't pass one
  filename:   <string?>
  size_bytes: <int>
  scan_result: <enum>      // "clean" | "infected" | "unreachable" | "too_large" | "bypassed"
  signature:  <string?>    // ClamAV signature on "infected"; error message on "unreachable"
  scanned_at: <iso8601-utc string>
  duration_ms: <int>       // 0 for too_large path (no clamd contact)
}
```

## EICAR test — exact command

```bash
cd /app/backend && python -m pytest tests/test_clamav_integration.py -v --no-header
```

Tests use monkeypatched `_scan_blocking` so they pass even when no
clamd sidecar is running in this pod. For an end-to-end test with a
real sidecar:

```bash
docker compose up -d clamd
# wait ~2 minutes for first signature DB pull
docker compose ps clamd  # STATUS must be "healthy"
# then post the EICAR string through any upload endpoint and confirm
# 422 + signature="Eicar-Test-Signature" + a row in upload_scan_log.
```

## docker-compose health gate

`docker compose up` brings up Mongo + Mongo Express + MinIO + clamd
with explicit healthchecks. The clamd healthcheck uses
`clamdcheck.sh` shipped with the official image, runs every 30s
after a 240s `start_period` so freshclam has time to pull the
signature DB on first boot. Backend depends on `clamd healthy` if you
choose to containerise the backend later (current dev runs under
supervisor, so the gate is moot for the local pod).

## Deviations from the brief

- **No new library install needed** — `clamd==1.0.2` was already in
  `requirements.txt`. The brief said "pin to latest stable, add to
  requirements.txt" but the pin already exists. Verified, no change.
- **Removed the brittle "scan_ms < 5 + signature is None" dev-bypass
  heuristic** in favour of an explicit `ScanResult.bypassed: bool`
  flag set by `_scan_blocking` when the dev escape hatch returned a
  synthetic clean. Same observable contract; cleaner internal state.

## Cross-chunk regression

```
tests/test_qa_chunk_9_5.py through tests/test_qa_chunk_19.py
+ tests/test_clamav_integration.py
+ tests/test_patch_22_clamav.py
+ tests/test_no_direct_llm_calls_outside_shield.py
= 114 passed, 33 warnings in 28.17s
```

(+12 from Chunk 19 baseline of 102: 7 new clamav_integration tests +
5 updated patch_22 tests, all green.)

CI guards (both shield-exclusivity guards) PASS. Ruff clean on all
touched files.

## What ships to user

| Surface | Value |
|---------|-------|
| Production stance | `AKKI_ENV=production` + `ALLOW_UNSAFE_UPLOADS` unset/false → enforce. Process refuses boot if both prod AND bypass simultaneously. |
| Dev stance | Bypass honored only when `AKKI_ENV != "production"`. Every 60s a stderr warning fires while the bypass is armed. |
| 25 MB cap | Per `CLAMAV_MAX_FILE_SIZE_MB` env (default 25). 413 fires before any clamd I/O. |
| Forensic surface | `db.upload_scan_log` carries one row per scan attempt. `/api/admin/health/full` surfaces a 24h breakdown by `scan_result`. |
| Sidecar | `clamav/clamav:stable` on TCP 3310, service name `clamd`, signature volume persisted, 240s start_period. |
