# AKKI — Production Deployment Runbook

> **Audience:** the engineer running the prod cutover and Day-2 ops.
> **Status:** first-issue runbook for the Azure VM + Cosmos DB vCore + MinIO + ClamAV stack on `akki.syni.ai`.
> **Owner:** platform.
> **Last updated:** generated alongside the deployment scaffolding (Phase 2).

---

## 1. Architecture

```
  Browser (TLS 1.3 to Cloudflare edge)
         │
         ▼
  Cloudflare proxy (akki.syni.ai)               — Full (strict) TLS
         │  origin TLS via Cloudflare Origin Certificate
         ▼
  Azure VM  Ubuntu 22.04 LTS  Standard_B2ms (8 GB / 2 vCPU min.)
  ┌─ systemd: akki.service
  │   ◼ akki-load-secrets.sh → fetches all secrets from Key Vault
  │                            via VM managed identity
  │   ◼ docker compose -f /opt/akki/docker-compose.prod.yml up -d
  │
  │  docker network: akki_internal (bridge)
  │  ┌────────────────────────────────────┐
  │  │ frontend  nginx 1.27   :80, :443 (host)  │  ◀ only ports exposed off-host
  │  │   /etc/akki/origin.{crt,key} → :ro mount │
  │  │        │                                  │
  │  │        ▼ /api/* → proxy_pass            │
  │  │ backend   uvicorn      :8001            │
  │  │   FastAPI + APScheduler (SINGLE replica)│
  │  │        │                │                 │
  │  │        ▼                ▼                 │
  │  │ clamav  :3310    minio  :9000  :9001    │
  │  │  /var/lib/akki/   /var/lib/akki/         │
  │  │  clamav/          minio/                 │
  │  └────────────────────────────────────┘
  │
  ▼ (mongodb+srv over TLS)
  Azure Cosmos DB for MongoDB (vCore)
  cluster:  <prefix>.mongocluster.cosmos.azure.com
  database: akki_prod
```

**Secret flow:** Azure Key Vault → (managed identity) → `akki-load-secrets.sh` → `/etc/akki/akki.env` (mode 0600) → docker compose `--env-file`.

**Image flow:** GitHub Actions (push to `main`) → build backend + frontend → push to Azure Container Registry tagged `<git_sha7>` → SSH → `akki-deploy.sh <tag>` → pull-and-up → healthcheck → record `last-good-tag` or auto-rollback.

**Storage paths on the VM:**

| Path | Purpose | Mode | Owner |
|---|---|---|---|
| `/etc/akki/akki.env` | runtime env file (secrets) | 0600 | root:root |
| `/etc/akki/origin.crt` | Cloudflare Origin Certificate | 0644 | root:root |
| `/etc/akki/origin.key` | Cloudflare Origin private key | 0600 | root:root |
| `/etc/akki/image_tag.env` | current `IMAGE_TAG=` line | 0644 | root:root |
| `/etc/akki/bootstrap.env` | KV/ACR pointers for helpers | 0600 | root:root |
| `/var/lib/akki/minio/` | MinIO data | 0755 | root:root |
| `/var/lib/akki/clamav/` | ClamAV signature DB cache | 0755 | root:root |
| `/var/lib/akki/last-good-tag` | most-recent healthy tag | 0644 | root:root |
| `/var/lib/akki/last-good-history` | append-only tag history | 0644 | root:root |
| `/var/log/akki/deploy.log` | deploy script timeline | 0644 | root:root |
| `/opt/akki/docker-compose.prod.yml` | compose file | 0644 | root:root |

---

## 2. Prerequisites

Have these ready before starting §4:

- [ ] **Azure subscription** with Contributor on a fresh resource group (e.g. `akki-prod-rg`, region `westeurope` or `uksouth`).
- [ ] **VM SKU ≥ 8 GB RAM**. Recommended: `Standard_B2ms` (entry, 8 GB / 2 vCPU) or `Standard_D2as_v5` (8 GB / 2 vCPU, more consistent CPU). spaCy `en_core_web_lg` baked into the backend image needs ~700 MB RAM resident; ClamAV daemon needs ~1.5 GB; MinIO ~150 MB; nginx ~30 MB; uvicorn ~500 MB — leaves comfortable headroom on 8 GB.
- [ ] **Cosmos DB for MongoDB (vCore)** cluster, smallest tier (M30-equivalent). Database name `akki_prod`. One DB user (e.g. `akki_app`).
- [ ] **Azure Container Registry** (Basic SKU is fine), e.g. `akkiprod.azurecr.io`.
- [ ] **Azure Key Vault** (Standard SKU), e.g. `akki-prod-kv`. RBAC mode (recommended over access policies).
- [ ] **GitHub repo admin** to add Action secrets and configure deploy workflows.
- [ ] **Cloudflare zone admin** for `syni.ai` (to add the `akki` A record and issue the Origin Certificate).
- [ ] **DNS pointer** — `akki.syni.ai` will be a Cloudflare-proxied A record to the VM's public IP.
- [ ] **Inbound email DNS** — only if you intend to use the inbound feature on launch. MX record to Postmark inbound, plus `INBOUND_DOMAIN` env var. Otherwise leave the feature dormant; the scaffolding ships with it accepted but inert.

---

## 3. Deploy blockers (must be done BEFORE the first deploy)

1. **Rotate every secret** listed in `.env.example` § "Group A — Secrets to rotate". The dev pod's `backend/.env` contained real-looking values; assume any reused are compromised. New `JWT_SECRET`, new `EMERGENT_LLM_KEY`, new `RESEND_API_KEY`, new `POSTMARK_SERVER_TOKEN`, new `SYNISENSE_MASTER_KEY` (one-time issuance — never to be rotated again unless we ship a re-encryption migration, see §11).
2. **Implement Postmark webhook signature verification.** `POSTMARK_WEBHOOK_SECRET` is **already referenced in code**; the verification step itself is incomplete. Do NOT enable inbound routing until that one-line check is wired and tested.
3. **`ALLOW_UNSAFE_UPLOADS=false`** — MUST be set explicitly. Default in code is empty, which evaluates to false, but explicit beats implicit. ClamAV container must be **healthy** before backend accepts traffic; the compose `depends_on: clamav: condition: service_healthy` enforces this.
4. **`SYNISENSE_ALLOW_INSECURE=false`** — if `true` and `AKKI_ENV=production`, boot will refuse with `MasterKeyMissing`. We want the strict path.
5. **`AKKI_ENV=production`** — arms the strict guards in `backend/server.py` and `services/synisense/encryption.py`.
6. **`BILLING_ENABLED=false`** — Stripe is out of scope for first deploy. Do not flip until the dead-letter handling and reconciliation are signed off.
7. **Cosmos `db.health_check` TTL index** — the `/api/health` handler writes a row per call. Without TTL the collection bloats. Run **once** against the prod cluster after `akki_prod` exists:
   ```bash
   mongosh "$MONGO_URL" --eval '
     db.health_check.createIndex(
       { ts: 1 },
       { expireAfterSeconds: 86400, name: "ttl_24h" }
     )
   '
   ```
   (Backend writes a `ts: ISODate()` field on every healthcheck; the TTL trims rows older than 24 h.)
8. **`CORS_ORIGINS`** must be set explicitly to `https://akki.syni.ai`. Empty / `*` falls back to a permissive regex (credentials-safe but undesirable for prod).

---

## 4. One-time Azure setup

Replace placeholders. Run from a workstation with `az` logged in.

```bash
# Variables
RG=akki-prod-rg
LOC=westeurope
VM_NAME=akki-prod-vm
KV_NAME=akki-prod-kv
ACR_NAME=akkiprod
COSMOS_NAME=akki-prod-cosmos
ADMIN_USER=azureuser

# Resource group
az group create -n $RG -l $LOC

# VM with system-assigned managed identity
az vm create \
  --resource-group $RG \
  --name $VM_NAME \
  --image Ubuntu2204 \
  --size Standard_B2ms \
  --admin-username $ADMIN_USER \
  --generate-ssh-keys \
  --assign-identity \
  --public-ip-sku Standard

# Open 80, 443 ONLY (no MinIO, no ClamAV, no SSH-from-the-internet for prod;
# bind SSH to a jumpbox or use Bastion in real prod — keeping :22 here
# only for the bootstrap day).
az vm open-port -g $RG -n $VM_NAME --port 80   --priority 1010
az vm open-port -g $RG -n $VM_NAME --port 443  --priority 1020

# Cosmos DB for MongoDB (vCore) — portal-driven; CLI command varies by
# region/preview state. The connection string we want looks like:
#   mongodb+srv://akki_app:<PASSWORD>@<prefix>.mongocluster.cosmos.azure.com/
#       ?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&appName=akki-prod
# IMPORTANT: retrywrites=false is mandatory — Cosmos vCore does not
# support retryable writes; pymongo defaults to true.

# Azure Container Registry
az acr create --resource-group $RG --name $ACR_NAME --sku Basic

# Key Vault (RBAC)
az keyvault create --resource-group $RG --name $KV_NAME --enable-rbac-authorization true

# Role assignments
VM_PRINCIPAL=$(az vm show -g $RG -n $VM_NAME --query identity.principalId -o tsv)
KV_ID=$(az keyvault show -g $RG -n $KV_NAME --query id -o tsv)
ACR_ID=$(az acr show -g $RG -n $ACR_NAME --query id -o tsv)

# VM identity → Key Vault Secrets User (read-only)
az role assignment create \
  --assignee $VM_PRINCIPAL \
  --role "Key Vault Secrets User" \
  --scope $KV_ID

# VM identity → ACR Pull
az role assignment create \
  --assignee $VM_PRINCIPAL \
  --role "AcrPull" \
  --scope $ACR_ID

# Generate ACR push token for GitHub Actions (stored as ACR_USERNAME/ACR_PASSWORD)
az acr token create \
  --name akki-ci \
  --registry $ACR_NAME \
  --scope-map _repositories_push \
  --query 'credentials.passwords[0].value' -o tsv
# Capture the value once — it isn't retrievable again.
```

---

## 5. One-time Cloudflare setup

1. **DNS A record:** `akki.syni.ai` → VM public IP, **Proxy status = Proxied** (orange cloud). TTL Auto.
2. **SSL/TLS → Overview:** mode **Full (strict)**.
3. **SSL/TLS → Origin Server → Create Certificate:**
   - Hostnames: `akki.syni.ai`
   - Validity: 15 years
   - Key type: ECC (P-256)
4. Copy the **Origin Certificate** PEM to `/etc/akki/origin.crt` on the VM (mode 0644 root:root).
5. Copy the **Private Key** PEM to `/etc/akki/origin.key` (mode 0600 root:root).
6. **Edge TLS minimum:** TLS 1.2.
7. **Always Use HTTPS:** ON.
8. **Automatic HTTPS Rewrites:** ON.
9. (Optional) **WAF → Managed Rulesets:** enable the OWASP Core Ruleset; the AKKI app does not require relaxed rules.

---

## 6. One-time VM bootstrap

From the VM (SSH in as `azureuser`):

```bash
# Clone the repo (read-only deploy key recommended in real prod)
sudo mkdir -p /opt/akki
sudo chown $USER /opt/akki
git clone <github-url> /opt/akki
cd /opt/akki

# One-shot bootstrap. Installs Docker + compose, az CLI, secrets loader,
# systemd unit. Idempotent — rerunnable.
sudo KEY_VAULT_NAME=akki-prod-kv \
     ACR_LOGIN_SERVER=akkiprod.azurecr.io \
     REPO_DIR=/opt/akki \
     ./scripts/deploy/bootstrap-vm.sh

# Place the Cloudflare origin cert + key:
sudo install -m 0644 /tmp/origin.crt /etc/akki/origin.crt
sudo install -m 0600 /tmp/origin.key /etc/akki/origin.key
```

---

## 7. Secrets in Key Vault

`akki-load-secrets.sh` translates UPPER_SNAKE_CASE env-var names to kebab-case Key Vault secret names automatically (`MONGO_URL` ↔ `mongo-url`).

**Required secrets** (boot refuses if any are missing):

```
# Group A — secrets-to-rotate
mongo-url
jwt-secret
emergent-llm-key
akki-cron-secret
synisense-master-key
resend-api-key
postmark-server-token
postmark-webhook-secret
s3-access-key
s3-secret-key
admin-password

# Group B — service-config
db-name
app-name
cors-origins
frontend-url
public-app-url
admin-email
s3-endpoint
s3-region
s3-bucket
s3-force-path-style
storage-backend
clamav-host
clamav-port
clamav-timeout-seconds
synisense-pool-size
synisense-use-pool
synisense-llm-fallback-cap
synisense-llm-fallback-concurrency
synisense-llm-fallback-timeout-ms
synisense-shield-map-ttl-hours

# Group C — feature-flags
akki-env                           # "production"
billing-enabled                    # "false"
allow-unsafe-uploads               # "false"
synisense-allow-insecure           # "false"

# Compose — used by docker-compose.prod.yml at evaluation time
acr-name                           # e.g. akkiprod.azurecr.io
```

**Optional** (emitted only if present):

```
resend-from-email
resend-from-name
postmark-inbound-domain
inbound-domain
llm-model-fast
llm-model-standard
llm-model-deep
akki-auth-observe-rate
akki-deep-quota-solve
akki-deep-unit-cost-usd
stripe-secret-key
stripe-webhook-secret
backup-dir
backup-s3-path
```

Load them all in one go (CLI helper):

```bash
az keyvault secret set --vault-name akki-prod-kv --name mongo-url            --file - <<<"mongodb+srv://..."
az keyvault secret set --vault-name akki-prod-kv --name jwt-secret           --value "$(openssl rand -hex 64)"
az keyvault secret set --vault-name akki-prod-kv --name akki-env             --value "production"
az keyvault secret set --vault-name akki-prod-kv --name billing-enabled      --value "false"
az keyvault secret set --vault-name akki-prod-kv --name allow-unsafe-uploads --value "false"
az keyvault secret set --vault-name akki-prod-kv --name synisense-allow-insecure --value "false"
# …etc.
```

---

## 8. First production deploy (manual, validates the stack)

From your workstation:

```bash
# (a) Build images locally and push (sanity check the Dockerfiles before
# trusting CI). REACT_APP_BACKEND_URL is baked into the bundle.
az acr login --name akkiprod
IMAGE_TAG=$(git rev-parse --short=7 HEAD)

docker build -f Dockerfile.backend  -t akkiprod.azurecr.io/akki-backend:$IMAGE_TAG  .
docker build -f Dockerfile.frontend -t akkiprod.azurecr.io/akki-frontend:$IMAGE_TAG \
  --build-arg REACT_APP_BACKEND_URL=https://akki.syni.ai .

docker push akkiprod.azurecr.io/akki-backend:$IMAGE_TAG
docker push akkiprod.azurecr.io/akki-frontend:$IMAGE_TAG
```

From the VM:

```bash
# (b) Copy the compose file in place (or git pull it).
sudo cp /opt/akki/docker-compose.prod.yml /opt/akki/docker-compose.prod.yml

# (c) First deploy.
sudo /usr/local/bin/akki-deploy.sh "$IMAGE_TAG"

# (d) Smoke tests.
curl -fsS https://akki.syni.ai/api/health
# {"status":"ok","db":"up"}

# Login (admin@akki.ai / ADMIN_PASSWORD from Key Vault), then:
curl -i -X POST https://akki.syni.ai/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@akki.ai","password":"<ADMIN_PASSWORD>"}'

# Upload smoke test (use a small DOCX)
# Brief generation smoke test (after at least one signal exists)
```

If `/api/health` doesn't return 200 within 60 s, `akki-deploy.sh` rolls back automatically.

---

## 9. CI/CD wiring

**GitHub repo → Settings → Secrets and variables → Actions:**

| Secret name | Value |
|---|---|
| `AZURE_VM_HOST` | VM public IP or DNS |
| `AZURE_VM_USER` | `azureuser` |
| `AZURE_VM_SSH_KEY` | private key (PEM) |
| `ACR_LOGIN_SERVER` | `akkiprod.azurecr.io` |
| `ACR_USERNAME` | ACR push-token user (e.g. `akki-ci`) |
| `ACR_PASSWORD` | ACR push-token password |
| `REACT_APP_BACKEND_URL` | `https://akki.syni.ai` |

Workflow (`.github/workflows/deploy.yml`):

1. **`build`** job: checkout, login to ACR, `docker buildx build --push` for both images, tag `<git_sha7>` AND `latest-prod`.
2. **`deploy`** job: SSH in, run `sudo akki-deploy.sh <git_sha7>`. The helper:
   - refreshes secrets from Key Vault
   - writes `IMAGE_TAG=<sha>` to `/etc/akki/image_tag.env`
   - `docker compose pull backend frontend`
   - `docker compose up -d --no-deps backend frontend`
   - polls `https://akki.syni.ai/api/health` for 60 s
   - on success: appends to `last-good-history`, writes `last-good-tag`
   - on failure: redeploys the previous `last-good-tag`, exits non-zero
3. **`notify`** job: writes a one-screen Action Summary with the SHA, tag, and per-job result.

**Manual rollback button:** trigger the workflow with `workflow_dispatch` and supply the older SHA in the `ref` input, or SSH and run `sudo /usr/local/bin/akki-rollback.sh` (1-step) / `sudo akki-rollback.sh --steps 3`.

---

## 10. Day-2 operations

```bash
# Tail logs (follow)
sudo docker compose -f /opt/akki/docker-compose.prod.yml logs -f backend
sudo docker compose -f /opt/akki/docker-compose.prod.yml logs -f frontend
sudo docker compose -f /opt/akki/docker-compose.prod.yml logs -f clamav
sudo docker compose -f /opt/akki/docker-compose.prod.yml logs -f minio

# Restart one service (zero downtime for the others)
sudo docker compose -f /opt/akki/docker-compose.prod.yml restart backend

# Check container health
sudo docker compose -f /opt/akki/docker-compose.prod.yml ps

# Check the deploy history
tail /var/log/akki/deploy.log
tail /var/lib/akki/last-good-history
cat  /var/lib/akki/last-good-tag

# Cosmos DB monitoring
#   Azure portal → Cosmos cluster → Metrics: RU usage, query latency,
#   server selection errors. Alert on any sustained server-selection-error.

# MinIO bucket inspection (port-forward; console NOT exposed publicly)
ssh -L 9001:localhost:9001 azureuser@akki.syni.ai
# then open http://localhost:9001 in your browser

# ClamAV signature freshness (auto-updated via freshclam in the official
# image; verify the daemon ran a successful refresh recently):
sudo docker logs akki-clamav 2>&1 | grep -E 'freshclam|reload' | tail -10

# Backup verification (Mongo)
# scripts/backup_mongo.sh dumps to BACKUP_DIR; run weekly via cron and
# restore-test on a throwaway DB monthly. The restore script lives at
# /app/scripts/restore_mongo.sh (already in the repo).
```

**Container memory budget on B2ms (8 GB):** backend ~0.7 GB, clamav ~1.5 GB, minio ~150 MB, frontend ~30 MB. If WeasyPrint PDF jobs spike RAM, watch `docker stats` — sustained pressure means upgrade to D2as_v5 / D4as_v5.

**Daily ops checklist (manual until we wire alerting):**
- `/api/health` 200
- All four containers `Up (healthy)` in `docker compose ps`
- `last-good-tag` matches the most recent successful deploy in GitHub Actions
- Cosmos RU usage < 80 % of cluster ceiling
- `/var/log/akki/deploy.log` last entry shows SUCCESS

---

## 11. The "without breaking it" checklist

Edits that look small but require care.

| Change | What it actually requires |
|---|---|
| Add a new env var that the backend reads at boot | Add to Key Vault → add to `REQUIRED_SECRETS` (or `OPTIONAL_SECRETS`) in `akki-load-secrets.sh` → add to `.env.example` → deploy. A missing required secret bricks the boot. |
| Rename an env var | Add the new name to Key Vault first, deploy code that reads BOTH names, switch traffic, remove the old name. Atomic single-step rename guarantees a window of broken boots. |
| Mongo schema change (new collection / new index) | Write a one-shot migration script in `backend/scripts/migrate_*.py`. **Add the index in code at startup** (motor's `create_index`) so new pods self-heal; don't rely on operators to run it. |
| Rename / re-route a backend endpoint | Frontend bundle is baked at build time — you MUST rebuild the frontend image. CI does this on every push automatically; manual deploys must trigger a frontend rebuild too. |
| Change `REACT_APP_BACKEND_URL` | Full frontend image rebuild. `docker compose restart frontend` is NOT enough — the URL is inlined in `main.<hash>.js`. |
| Change `CORS_ORIGINS` | Restart backend (env-var read at module load). Confirm the new origin is exact — trailing slash and protocol matter. |
| Change `AKKI_CRON_SECRET` | Restart backend. Crons re-arm on import; nothing persists between restarts. |
| Scale backend to >1 replica | **DON'T.** APScheduler crons run in-process and have no leader election. Two replicas → every cron fires twice (duplicated audit rows, duplicated digest emails, duplicated retention sweeps). Distributed lock work is a separate piece of engineering. |
| Rotate `JWT_SECRET` | Issue a new one, accept BOTH for one access-token TTL (8 h) by listing them in code as a tuple, then drop the old. Single-step rotation logs everyone out. |
| Rotate `SYNISENSE_MASTER_KEY` | **DO NOT** without the re-encryption migration (which doesn't exist yet). Rotating the master key invalidates every row in `db.synisense_shield_maps`, breaking forensic retrieval of any prior shielded payload. Issue once at first prod boot, then leave alone. |
| Edit `nginx/frontend.conf` | Rebuild and redeploy frontend image. The conf is COPY'd at image-build time. |
| Add an APScheduler cron | Single-replica still applies. Use `AKKI_CRON_SECRET` gating; verify Tue 10:00 UTC / Mon 08:00 UTC / 03:00 / 03:30 / 04:00 are still the only entries. |
| Adjust ClamAV signature update cadence | The official `clamav/clamav:stable` image runs `freshclam` automatically on its own schedule. Don't fork the image just to tweak this. |

---

## 12. Rollback procedures

### (a) Image rollback — < 5 minutes
```bash
sudo /usr/local/bin/akki-rollback.sh                 # one step back
sudo /usr/local/bin/akki-rollback.sh --steps 3       # three steps back
sudo /usr/local/bin/akki-rollback.sh <git_sha7>      # pin specific tag
```
The helper writes the chosen tag into `/etc/akki/image_tag.env`, runs `docker compose pull && up -d --no-deps backend frontend`, and polls `/api/health`. No data loss; just a container swap.

**Auto-rollback in CI** is the same path — `akki-deploy.sh` calls into the rollback helper internally on healthcheck failure.

### (b) Cosmos DB point-in-time restore
Azure portal → Cosmos for MongoDB cluster → **Backups** → **Restore** → pick a timestamp within the retention window (default 7 days for vCore Burstable/General) → restore into a new cluster name (e.g. `akki-prod-cosmos-restore-<date>`). Update `mongo-url` in Key Vault to the new connection string → trigger a new deploy (or just `sudo /usr/local/bin/akki-load-secrets.sh && sudo systemctl restart akki.service`).

### (c) Full DR
1. Provision a fresh VM in a secondary region using the same `bootstrap-vm.sh`.
2. Restore Cosmos from latest backup into the secondary region.
3. Update Cloudflare DNS A record to the new VM IP.
4. Trigger a manual deploy with the last-known-good `git_sha7` via `workflow_dispatch`.
5. Verify `/api/health`, login, upload, brief.

---

## 13. Cutover from Emergent preview to Azure prod

**Pre-cutover (T−2 d):**
- Provision Azure resources (§4).
- Populate Key Vault (§7).
- Bootstrap the VM (§6).
- Configure Cloudflare zone but **do not** flip the A record to the VM yet (leave it pointing at the Emergent preview, or to a holding page).
- Import seed data (admin account) by triggering a manual deploy and letting `server.py:468` create the admin on first boot. Confirm by logging in.

**Data export from Emergent preview** (T−1 d):
```bash
# From the Emergent preview pod, export the dev database.
mongodump --uri "$MONGO_URL" --db akki_dev --out /tmp/akki-export
tar -czf /tmp/akki-export.tar.gz -C /tmp/akki-export .
# Transfer the tarball off the preview pod (e.g. via the same export
# mechanism the team uses for dumps).
```

**Data import into Cosmos** (T−1 d):
```bash
# From the Azure VM (or a workstation with az + mongosh tooling).
tar -xzf akki-export.tar.gz -C /tmp/akki-import
mongorestore \
  --uri "$MONGO_URL_PROD" \
  --nsFrom='akki_dev.*' --nsTo='akki_prod.*' \
  --noIndexRestore \
  /tmp/akki-import
# Note --noIndexRestore: Cosmos vCore enforces its own indexing limits;
# let the app re-create indexes at startup (motor's create_index calls
# in backend/server.py startup).
```

**Smoke-test order (T0):**
1. `curl https://akki.syni.ai/api/health` → 200.
2. Login as `admin@akki.ai` (with rotated `ADMIN_PASSWORD`).
3. List contexts → expect imported data.
4. Open Document Journal → list visible.
5. Upload a small DOCX → expect 200 + doc visible (depends on MinIO + ClamAV being healthy and `STORAGE_BACKEND=s3`).
6. Generate a brief on a context with active signals → expect 200 (or `llm_fallback` flag if Claude proxy 502s; both are healthy outcomes).
7. Visit a Solva session → expect 200.
8. Audit log: `/chats/<chat_id>/audit/export.zip` → expect chain validates.

**Cutover (T0):**
1. Communication window: notify users of a 5-min window.
2. Flip Cloudflare A record → VM IP, **Proxied**.
3. Wait for global DNS propagation (Cloudflare is fast, < 60 s with proxied records).
4. Re-run smoke tests against the public URL.
5. Monitor `/api/admin/health/full` and the Cosmos portal for 30 min.

**Post-cutover (T+1 d):**
- Decommission the Emergent preview pod (or freeze it as a read-only forensic copy for 7 days).
- Confirm cron jobs ran on schedule (Tue blog cron, Mon influence digest, daily 03:00 paragraph anchors).
- Confirm Synisense `db.synisense_runs` is being written.

---

## 14. Appendix — env var reference

| Var | Group | Default if any | Lives in |
|---|---|---|---|
| `MONGO_URL` | A | none (required) | Key Vault |
| `DB_NAME` | B | none (required) | Key Vault |
| `JWT_SECRET` | A | none (required) | Key Vault |
| `APP_NAME` | B | `AKKI Sandbox` | Key Vault |
| `CORS_ORIGINS` | B | `*` (regex fallback) | Key Vault |
| `EMERGENT_LLM_KEY` | A | none | Key Vault |
| `AKKI_CRON_SECRET` | A | unset = crons disarm | Key Vault |
| `CLAMAV_HOST` | B | `127.0.0.1` | Key Vault |
| `CLAMAV_PORT` | B | `3310` | Key Vault |
| `CLAMAV_TIMEOUT_SECONDS` | B | `30` | Key Vault |
| `ALLOW_UNSAFE_UPLOADS` | C | `false` | Key Vault |
| `STORAGE_BACKEND` | B | `s3` | Key Vault |
| `S3_ENDPOINT` | B | `http://127.0.0.1:9000` | Key Vault |
| `S3_REGION` | B | `eu-west-1` | Key Vault |
| `S3_BUCKET` | B | none | Key Vault |
| `S3_ACCESS_KEY` | A | none | Key Vault |
| `S3_SECRET_KEY` | A | none | Key Vault |
| `S3_FORCE_PATH_STYLE` | B | `true` | Key Vault |
| `BILLING_ENABLED` | C | unset = false | Key Vault |
| `STRIPE_SECRET_KEY` | A | none | Key Vault (optional) |
| `STRIPE_WEBHOOK_SECRET` | A | none | Key Vault (optional) |
| `BACKUP_DIR` | B | `/tmp/akki-backups` | Key Vault (optional) |
| `SYNISENSE_MASTER_KEY` | A | none | Key Vault |
| `SYNISENSE_POOL_SIZE` | B | `0` | Key Vault |
| `SYNISENSE_USE_POOL` | B | `false` | Key Vault |
| `SYNISENSE_ALLOW_INSECURE` | C | `false` | Key Vault |
| `SYNISENSE_LLM_FALLBACK_CAP` | B | `20` | Key Vault |
| `SYNISENSE_LLM_FALLBACK_CONCURRENCY` | B | `5` | Key Vault |
| `SYNISENSE_LLM_FALLBACK_TIMEOUT_MS` | B | `2000` | Key Vault |
| `SYNISENSE_SHIELD_MAP_TTL_HOURS` | B | `24` | Key Vault |
| `RESEND_API_KEY` | A | none | Key Vault |
| `RESEND_FROM_EMAIL` | B | code default | Key Vault (optional) |
| `RESEND_FROM_NAME` | B | code default | Key Vault (optional) |
| `POSTMARK_SERVER_TOKEN` | A | none | Key Vault |
| `POSTMARK_WEBHOOK_SECRET` | A | none (BLOCKER) | Key Vault |
| `POSTMARK_INBOUND_DOMAIN` | B | `inbound.akki.ai` | Key Vault (optional) |
| `INBOUND_DOMAIN` | B | none | Key Vault (optional) |
| `ADMIN_EMAIL` | B | `admin@akki.ai` | Key Vault |
| `ADMIN_PASSWORD` | A | (dev default — must override) | Key Vault |
| `LLM_MODEL_FAST` | B | `gemini-2.5-flash` | Key Vault (optional) |
| `LLM_MODEL_STANDARD` | B | `claude-sonnet-4-5-20250929` | Key Vault (optional) |
| `LLM_MODEL_DEEP` | B | `claude-opus-4-6` | Key Vault (optional) |
| `AKKI_ENV` | C | unset (`production` MUST be set) | Key Vault |
| `AKKI_AUTH_OBSERVE_RATE` | B | `0.01` | Key Vault (optional) |
| `AKKI_DEEP_QUOTA_SOLVE` | B | code default | Key Vault (optional) |
| `AKKI_DEEP_UNIT_COST_USD` | B | code default | Key Vault (optional) |
| `FRONTEND_URL` | B | none | Key Vault |
| `PUBLIC_APP_URL` | B | none | Key Vault |
| `REACT_APP_BACKEND_URL` | D | none | **GitHub repo secret** (build-arg only) |
| `IMAGE_TAG` | E | none | `/etc/akki/image_tag.env` (deploy-time) |
| `ACR_NAME` | E | none | `/etc/akki/image_tag.env` (deploy-time) |

---

## Outstanding cross-references

- **Phase B.3 — real token streaming.** When direct Anthropic + Gemini keys land, the `proxy_buffering off` line in `nginx/frontend.conf` and the `proxy_read_timeout 300s` are already configured for SSE; no further nginx changes needed. The backend cutover is the only work.
- **Postmark webhook signature verification.** `POSTMARK_WEBHOOK_SECRET` is referenced in code but the verification step appears incomplete. Wire it before enabling inbound routing in prod (§3 deploy blocker #2).
- **`db.health_check` TTL index.** Created **once** against the prod DB during the cutover (§3 deploy blocker #7).
- **APScheduler distributed lock.** Single-instance constraint (§11). When traffic justifies horizontal scaling, plan the Mongo-based leader-election or external scheduler (Azure Logic App / Container App job) before relaxing the cap.
