# Dev Pod Caveats

Operational notes specific to the Emergent dev pod that hosts this app. **None of these apply to production.** Production must satisfy the strict path documented in `docs/PRODUCT_FEATURES.md`.

## Why this file exists

The Emergent dev container ships without `clamd` (ClamAV daemon) and `minio` (S3-compatible object store) binaries. The product code path treats both as **hard preconditions** by default — it 503s rather than write a doc nobody scanned, and it 500s rather than fall over silently when MinIO is unreachable.

To keep the dev journey usable while those binaries are not in the image, two `.env` flags are flipped:

| Flag | Dev value | Prod value | Why |
|---|---|---|---|
| `ALLOW_UNSAFE_UPLOADS` | `true` | `false` | Bypass ClamAV when the binary is absent. The startup logs a 60-second nag so this is impossible to forget. |
| `STORAGE_BACKEND` | `local` | `s3` | Use a local-disk backend (`backend/uploads/`) instead of MinIO/S3. The same boto3 wrapper handles both. |

These switches are documented in `backend/.env` next to the values.

## What "broken sandbox" looked like before this runbook

Symptom: prospect walks the 10-stage sandbox seed, lands on `/app?tutorial=1`, clicks "Drop a real pack", picks a PDF — toast turns red, *"Couldn't read that one. Try another pack."*

Root cause: backend `POST /api/contexts/{cid}/documents` was returning 503 (`scanner_unavailable`) because clamd was unreachable; once clamd was bypassed, the next call returned 500 because `STORAGE_BACKEND=s3` was pointed at MinIO and MinIO wasn't running. The toast's user-facing copy hid both errors and blamed the user's PDF.

Fixed in Phase B (sandbox hotfix bundle):
- `.env` flags flipped as above.
- `routers/documents.py` upload path goes through whichever storage backend `.env` selects.
- `components/sandbox/SandboxPackDrop.jsx` now branches on HTTP status so a 503 / 5xx says what it actually means instead of mis-blaming the prospect.
- `tests/test_phase_b_sandbox_upload.py` is a tripwire: it drives the upload end-to-end and fails loudly if either flag is reverted before the binaries are in place.

## Other deferred dev-pod items (Phase G owns the permanent fix)

| Item | Today's posture | Phase G fix |
|---|---|---|
| **clamd** | binary missing; `clamd.conf` in supervisor flipped to `autostart=false` so supervisord boots; uploads bypass scan via `ALLOW_UNSAFE_UPLOADS=true`. | Install `clamav` + `clamav-daemon` + `clamav-freshclam` in the container image, set `autostart=true`, drop the dev bypass. |
| **minio** | binary missing; `minio.conf` in supervisor flipped to `autostart=false`; uploads write to local disk via `STORAGE_BACKEND=local`. | Install minio in the container image, set `autostart=true`, flip `STORAGE_BACKEND=s3` (already the runtime default for prod). |
| **`user=clamav`** in `clamd.conf` | flipped to `user=root` because the `clamav` system user does not exist in this image and supervisord refuses to start the *whole daemon* if any program config references a missing user. | Install the `clamav` package which creates the user; flip back to `user=clamav`. |
| **Resend test-mode constraint** | `RESEND_API_KEY` is the test-mode key with the test-domain `onboarding@resend.dev`; outbound delivery is restricted to the registered email address that owns the test API key. | Production uses a real verified domain on Resend; flips `RESEND_FROM_EMAIL` to `noreply@akki.ai` (or wherever the verified domain lands). |
| **Postmark inbound** | `POSTMARK_SERVER_TOKEN` is set; webhook receives at `POST /api/inbound/postmark`. Inbound domain is configured per-context. | Production points the Postmark webhook at the real ingress hostname and verifies the `MailboxHash` per env. |

## How to spot dev-pod problems quickly

```bash
# 1) Is the bypass flag actually true?
grep ALLOW_UNSAFE_UPLOADS /app/backend/.env

# 2) Is the storage backend pointed at local disk?
grep STORAGE_BACKEND /app/backend/.env

# 3) Do supervisor's clamd / minio configs autostart?
grep -nE 'autostart' /etc/supervisor/conf.d/clamd.conf /etc/supervisor/conf.d/minio.conf

# 4) Is the upload regression test green?
cd /app/backend && /root/.venv/bin/python -m pytest tests/test_phase_b_sandbox_upload.py -q
```

If any of those four turn red, the sandbox conversion moment is broken and the hotfix needs to be re-applied or escalated to Phase G.
