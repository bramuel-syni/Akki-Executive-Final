# ClamAV Setup Guideline — AKKI Malware Scanning

> Drafted 2026-05-12 by Patch 15-19 sprint. AKKI lets users upload PDFs, DOCX, images, and other files into a workspace. In production we MUST scan every upload before persisting it, or one infected pack ruins multiple boards.

> Current state in code (see SYSTEM_STATE §7): **dev bypass** — uploads land directly in the storage layer without virus scanning. ClamAV wiring is pending this guideline being actioned.

---

## 1. Deployment options

### Option A — Sidecar container in AKS (recommended for self-hosted production)

ClamAV is FOSS, well-understood, and the daemon `clamd` runs comfortably as a Kubernetes Deployment. The pattern:
- One Deployment running `clamav/clamav:1.3` (official upstream image), 1 replica, ~512Mi memory request, 1Gi limit.
- Daily `freshclam` signature pull as a Kubernetes CronJob OR as the same Deployment's startup command (freshclam runs every 6h in the official image by default).
- A Kubernetes Service `clamav.default.svc.cluster.local:3310` so the AKKI backend pod can `socket.connect(...)`.
- The AKKI backend uses `pyclamd` (or the simpler `clamd` Python library) to stream each upload's bytes to the daemon and receive `OK` / `FOUND <virus name>`.

**Pros**: Free, fast (loopback inside cluster), zero external dependency, full control over signature freshness.
**Cons**: Requires the cluster to have egress to `database.clamav.net` for signature pulls (or a mirror). Adds ~500-700MB resident memory per pod replica. Initial signature download is ~250MB.

**Helm chart** (use `bitnami/clamav` or roll your own — both work):
```
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install clamav bitnami/clamav --namespace virus-scan --create-namespace \
  --set persistence.enabled=true \
  --set persistence.size=1Gi \
  --set resources.requests.memory=512Mi \
  --set resources.limits.memory=1Gi
```

### Option B — Hosted ClamAV-as-a-Service (good for getting unstuck fast)

Several providers offer a ClamAV REST API behind an HTTPS endpoint:
- **CloudMersive** (`api.cloudmersive.com`) — free tier 800 calls/month, paid £8/mo for 50k.
- **VirusTotal** (Google) — premium tier required for commercial use; covers ClamAV + 70 other engines.
- **Self-hosted "ClamAV-REST" image** on a separate Azure Container App (cheaper than full AKS sidecar if your volume is low).

**Pros**: No cluster maintenance, no signature management, instant deploy.
**Cons**: Outbound HTTPS per upload (latency 100-400ms), per-call cost at scale, you're sending file bytes to a 3rd party (privacy review needed for governance customers).

**Recommendation**: **Option A (sidecar in AKS)** for the production cluster. Keep Option B (CloudMersive) as a fallback for staging environments where you don't want to run the daemon.

## 2. Signature DB strategy

ClamAV signatures need refresh every few hours or the engine misses recent malware.

**With Option A (sidecar)**:
- The official `clamav/clamav` image runs `freshclam` automatically every 6 hours.
- Set the env var `CLAMAV_FRESHCLAM_HOURLY=true` to refresh hourly for higher-risk workloads (cost: a few MB of egress per pull).
- **Network egress required**: outbound HTTPS to `*.clamav.net` (port 443). If your cluster is locked down, allow-list:
  - `database.clamav.net`
  - `current.cvd.clamav.net`
  - `db.local.clamav.net` (mirror if you configure one)

**With Option B (hosted)**: provider handles refresh.

## 3. Integration point in AKKI

The AKKI upload pipeline today (search `upload_document`, `documents.py`, `briefings.py`):

```
client -> POST /api/contexts/{cid}/documents/upload  (multipart)
       -> documents_router.upload_document()
       -> [DEV BYPASS] write bytes to disk / blob
       -> insert metadata into Mongo `documents` collection
```

After wiring ClamAV:
```
client -> POST .../documents/upload
       -> documents_router.upload_document()
       -> ClamAVClient.scan_stream(bytes)
            -> if OK:     write to blob, insert metadata
            -> if FOUND:  return 422 with body { detail: "infected: <virus name>", virus: <name> }
                          DO NOT persist; DO log to audit_trail collection with kind='upload_rejected_infected'
            -> if ERROR:  fail closed (return 503) — never persist an unscanned file in production
```

Add `CLAMAV_HOST` and `CLAMAV_PORT` to backend/.env (or Key Vault in production).

Test routers that exercise the upload path:
- `backend/tests/test_iter44_uploads.py` (existing)
- `backend/tests/test_briefings_upload.py` (existing)
Add a new test once the wiring lands: `test_clamav_blocks_eicar.py` posting the EICAR test string and asserting 422.

## 4. Failure modes

| Failure | What ClamAV does | What AKKI must do |
|---|---|---|
| Daemon unreachable (network blip) | `pyclamd` raises ConnectionError | Return 503 to client with "Antivirus temporarily unavailable" — DO NOT silently accept the upload |
| Scan times out (>30s, e.g. huge PDF) | Daemon logs `TIMEOUT` | Same as above: 503. Tune the timeout for your largest expected pack. |
| File scans as `OK` | Daemon returns `stream: OK` | Proceed with persistence |
| File scans as `FOUND` | Daemon returns `stream: Eicar-Test-Signature FOUND` | Reject (422). Write audit trail. Notify the uploader. |
| File scans as `ERROR` (corrupt archive etc.) | Daemon returns `ERROR` | Reject (422). Treat as untrustworthy. |
| Signatures stale (>24h since freshclam) | Daemon scans normally but with outdated DB | Add a Prometheus alert: `clamav_freshclam_seconds_ago > 86400`. Page on-call. |

**Critical rule**: in production, fail closed. Never write an unscanned file to blob storage. The dev bypass currently in `documents_router.upload_document()` MUST be replaced with a hard fail on missing CLAMAV_HOST in production.

## 5. What to give me back

Send these values back so I can wire AKKI:

```
CLAMAV_DEPLOYMENT_MODE:      sidecar | hosted
CLAMAV_HOST:                 clamav.virus-scan.svc.cluster.local         (sidecar)
                          or api.cloudmersive.com                          (hosted)
CLAMAV_PORT:                 3310                                          (sidecar default)
                          or 443                                            (hosted)
CLAMAV_TIMEOUT_SECONDS:      30                                            (default)
CLAMAV_API_KEY:              <only required for hosted option>
CLAMAV_REJECT_ON_ERROR:      true                                          (always true in production)
```

Plus paste:
- Output of `kubectl get pods -n virus-scan` confirming the daemon is Running.
- Output of `kubectl logs -n virus-scan deploy/clamav | grep "Database correctly reloaded"` confirming signatures loaded.
- Or the hosted provider's account dashboard screenshot showing API key + quota.

— end of ClamAV setup guideline —
