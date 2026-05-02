# AKKI on Azure — production deployment guide

This runbook describes the recommended production topology for AKKI on
Azure, the `az` CLI commands needed to provision it, and the operational
posture (CI/CD, secrets, observability, backup, compliance) that makes
the deployment survivable. Pair with `PRODUCTION_ENV.md` for the env-var
inventory.

The voice is FT, not marketing. Skip what doesn't apply to your scale;
nothing here is required by the application — it is a recommended
shape that the application happens to fit cleanly.

---

## Recommended topology

```
                    ┌─────────────────────────────┐
                    │       Azure Front Door      │
                    │   (WAF, TLS, edge routing)  │
                    └────┬───────────────────┬────┘
        app.akki.ai      │                   │   akki.ai (marketing)
                         ▼                   ▼
       ┌──────────────────────┐   ┌────────────────────────┐
       │ Container Apps env   │   │ Azure Static Web Apps  │
       │ ┌──────────────────┐ │   │ (CRA build of /frontend)│
       │ │ akki-backend     │ │   └────────────────────────┘
       │ │ FastAPI :8001 +  │ │     ┌──────────────────────┐
       │ │ clamd sidecar    │◀┼────▶│ Azure Blob (akkiblobsa)│
       │ └──────────────────┘ │     │ via MinIO gateway     │
       │ ┌──────────────────┐ │     │ (akki-blob-gw)        │
       │ │ akki-blob-gw     │◀┼────▶│ uploads + backups     │
       │ └──────────────────┘ │     └──────────────────────┘
       └────┬─────────────────┘
            │ VNet peering
            ▼
       ┌────────────────────────────┐
       │ MongoDB Atlas (West Europe)│
       │ M10/M30 cluster · VNet peer│
       └────────────────────────────┘

Cross-cutting: Azure Key Vault · Azure Monitor · Sentry EU · ACR · GitHub Actions
```

Region: **West Europe** (`westeurope`) for EU-data-residency posture.

---

## Step 1 — Foundation

Provisions the resource group, Key Vault and the VNet that backend
containers and the Atlas peering will both attach to.

```bash
LOCATION=westeurope
RG=akki-prod-rg
KV=akki-prod-kv
VNET=akki-prod-vnet

# Resource group
az group create --name $RG --location $LOCATION

# Key Vault — soft-delete + purge protection are mandatory for prod.
az keyvault create \
  --resource-group $RG \
  --name $KV \
  --location $LOCATION \
  --enable-rbac-authorization true \
  --enable-purge-protection true \
  --retention-days 90

# VNet — /20 is overkill for one stack but gives headroom for dev pods,
# Atlas peering, and a private MinIO subnet.
az network vnet create \
  --resource-group $RG \
  --name $VNET \
  --address-prefixes 10.30.0.0/20 \
  --subnet-name compute --subnet-prefixes 10.30.0.0/22

az network vnet subnet create \
  --resource-group $RG --vnet-name $VNET \
  --name atlas-peering --address-prefixes 10.30.4.0/24
```

Tag the resource group at creation; tag inheritance keeps cost reports
sane: `--tags app=akki env=prod owner=<team>`.

---

## Step 2 — Data layer

### 2a. MongoDB Atlas (West Europe, VNet-peered)

Create the cluster from the Atlas console, in **AWS / GCP / Azure ›
Azure / westeurope**, M10 or M30 depending on traffic. Then peer it
back to your `$VNET`:

1. Atlas → Network Access → Peering → "Add Peering Connection" → Azure → enter your **subscription ID, tenant ID, RG, VNet name, subnet `atlas-peering`**.
2. Atlas hands you a service principal payload; in Azure Cloud Shell run the script Atlas displays (it grants the SP `Network Contributor` on the VNet, scoped).
3. Wait for "AVAILABLE". Atlas will then accept connections from `10.30.0.0/20`.
4. Atlas → Database Access → create user `akki` with `readWrite@akki` only. Save the connection string into Key Vault as `MONGO-URL` — never `atlasAdmin`.

Atlas continuous backup: enable "Continuous Cloud Backup" on the
cluster (not snapshot-only) — that's our 24-hour RPO floor.

### 2b. Object storage — Option A (this phase): MinIO gateway on Azure Blob

The application speaks the S3 protocol via boto3
(`backend/services/storage_service.py`). Rather than rewrite that
adapter for native Azure Blob, we run **MinIO in `gateway azure` mode**
as a small container. Zero application code change, full S3 wire
compatibility, ten minutes to provision.

```bash
SA=akkiblobsa
BLOB_CONTAINER=uploads
GATEWAY_APP=akki-blob-gw

# Storage account — GRS for cross-region durability.
az storage account create \
  --resource-group $RG --name $SA \
  --location $LOCATION --sku Standard_GRS --kind StorageV2 \
  --min-tls-version TLS1_2 --allow-blob-public-access false

az storage container create \
  --account-name $SA --name $BLOB_CONTAINER --auth-mode login

# Capture the storage key into Key Vault.
SAKEY=$(az storage account keys list -g $RG -n $SA --query "[0].value" -o tsv)
az keyvault secret set --vault-name $KV --name AZURE-STORAGE-KEY --value "$SAKEY"
```

The gateway container itself is provisioned in Step 3 alongside the
backend; it only needs `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`,
`MINIO_AZURE_*` to fly. Application sees `S3_ENDPOINT=https://akki-blob-gw...`
and the MinIO root user/secret as `S3_ACCESS_KEY/S3_SECRET_KEY`.

### 2c. Object storage — Option B (deferred, see "Future work")

A native `AzureBlobStorage` adapter in `services/storage_service.py`
that uses `azure-identity` + managed identity. ~1 day of focused work.
Trades the MinIO sidecar for ~50 lines of native code. Documented in
"Future work" at the bottom of this file; not in scope this phase.

---

## Step 3 — Compute

### 3a. Azure Container Registry

```bash
ACR=akkiprodacr
az acr create --resource-group $RG --name $ACR --sku Basic --admin-enabled false

# Build + push the backend image.
az acr build \
  --registry $ACR --image akki-backend:$(git rev-parse --short HEAD) \
  --file backend/Dockerfile backend/

# Build + push the MinIO gateway image. Base image is upstream; we
# wrap it for tag pinning.
az acr build \
  --registry $ACR --image akki-blob-gw:1.0.0 \
  --file deploy/blob-gw.Dockerfile deploy/
```

(The two Dockerfiles are not in this guide — see `DEPLOY.md` for the
backend Dockerfile and `deploy/blob-gw.Dockerfile` for the MinIO
wrapper. Frontend SPA assets are baked into the backend image and
served from `/`. The marketing site goes to Static Web Apps, § Step 4.)

### 3b. Container Apps environment

```bash
CAE=akki-prod-cae

az containerapp env create \
  --resource-group $RG --name $CAE --location $LOCATION \
  --infrastructure-subnet-resource-id $(az network vnet subnet show \
    -g $RG --vnet-name $VNET --name compute --query id -o tsv) \
  --internal-only false
```

### 3c. Backend container app — with ClamAV sidecar

ClamAV is part of the same container app as a **sidecar container**;
the backend talks to it on `localhost:3310`.

```bash
# Managed identity for Key Vault binding (see Step 6).
az identity create -g $RG -n akki-backend-mi
MI_ID=$(az identity show -g $RG -n akki-backend-mi --query id -o tsv)
MI_CID=$(az identity show -g $RG -n akki-backend-mi --query clientId -o tsv)

# Container app — single revision mode for now (HA caveat in 3d below).
az containerapp create \
  --resource-group $RG --name akki-backend --environment $CAE \
  --user-assigned $MI_ID \
  --image $ACR.azurecr.io/akki-backend:$(git rev-parse --short HEAD) \
  --registry-server $ACR.azurecr.io \
  --target-port 8001 --ingress external \
  --transport auto --min-replicas 1 --max-replicas 1 \
  --cpu 1.0 --memory 2.0Gi
```

Add the ClamAV sidecar via YAML (Container Apps multi-container is
YAML-only at the time of writing):

```yaml
# containerapp-akki-backend.yaml — patch with `az containerapp update --yaml`
properties:
  template:
    containers:
      - name: akki-backend
        image: akkiprodacr.azurecr.io/akki-backend:<sha>
        env:
          - name: CLAMAV_HOST
            value: localhost
          - name: CLAMAV_PORT
            value: "3310"
          # ...all other env from PRODUCTION_ENV.md, mounted as secretRef
      - name: clamav
        image: clamav/clamav:1.3
        env:
          - { name: CLAMAV_NO_FRESHCLAMD, value: "false" }
        resources:
          cpu: 0.5
          memory: 1Gi
```

### 3d. APScheduler caveat in multi-replica deployments

`backend/server.py` arms three in-process schedulers (Tue 10:00 Exco360,
Mon 08:00 Influence Digest, Daily 03:00 anchors sweep) using
APScheduler. **In-process schedulers do not coordinate across
replicas** — if you scale `akki-backend` to N>1, the schedulers fire
N times.

Two options:

1. **Pin to one replica.** Set `--min-replicas 1 --max-replicas 1` (as
   above). Simplest. Acceptable if the scheduler workload is small and
   the cron endpoints themselves are idempotent.
2. **Extract to an Azure Container App Job.** Move the three schedules
   to `az containerapp job` invocations on Azure-managed cron triggers,
   each calling the equivalent backend endpoint with `X-Cron-Secret`.
   Removes the single-replica constraint. ~half-day of work; sized in
   "Future work" below.

For Phase 11 we go with option 1 and document the trade-off.

### 3e. MinIO gateway container app

```bash
az containerapp create \
  --resource-group $RG --name akki-blob-gw --environment $CAE \
  --image $ACR.azurecr.io/akki-blob-gw:1.0.0 \
  --target-port 9000 --ingress internal \
  --min-replicas 1 --max-replicas 2 \
  --cpu 0.5 --memory 1Gi \
  --secrets \
      minio-root-user=keyvaultref:https://$KV.vault.azure.net/secrets/MINIO-ROOT-USER,identityref:$MI_ID \
      minio-root-pass=keyvaultref:https://$KV.vault.azure.net/secrets/MINIO-ROOT-PASS,identityref:$MI_ID \
      azure-storage-key=keyvaultref:https://$KV.vault.azure.net/secrets/AZURE-STORAGE-KEY,identityref:$MI_ID \
  --env-vars \
      MINIO_ROOT_USER=secretref:minio-root-user \
      MINIO_ROOT_PASSWORD=secretref:minio-root-pass \
      MINIO_AZURE_ACCOUNT_NAME=$SA \
      MINIO_AZURE_ACCOUNT_KEY=secretref:azure-storage-key
```

Internal ingress (the gateway never faces the public internet);
backend reaches it at `https://akki-blob-gw.internal.<env>.azurecontainerapps.io`.

---

## Step 4 — Frontend

The marketing site (`/`, `/about`, `/features`, `/blog`, etc.) is served
from Azure Static Web Apps; the app surface (`/app/*`) is **already
served from the backend** (the CRA build is baked into the backend
image and mounted as a static directory). This avoids cookie / CORS
complexity for `/api` calls.

```bash
SWA=akki-marketing

az staticwebapp create \
  --resource-group $RG --name $SWA --location $LOCATION \
  --source https://github.com/bramuel-syni/Akki-Executive \
  --branch main --app-location frontend --output-location build \
  --login-with-github
```

The marketing site is the same React build with a runtime flag
(`REACT_APP_BACKEND_URL=https://app.akki.ai`) so deep-links into `/app`
hit the backend origin. The SWA build skips the `/app/*` routes — they
404 to the catch-all and the Front Door rule (Step 5) routes anything
under `/app` and `/api` to the backend instead.

---

## Step 5 — Edge, DNS, TLS

### 5a. Azure DNS

```bash
ZONE=akki.ai
az network dns zone create -g $RG -n $ZONE
# Update registrar to delegate to the four NS records az returns.

# Records (ALIAS to Front Door once 5b is up):
az network dns record-set a create -g $RG -z $ZONE -n app --ttl 300
az network dns record-set a create -g $RG -z $ZONE -n @ --ttl 300
```

### 5b. Front Door (WAF + TLS + edge routing)

Use Azure Front Door **Standard** (Premium gives Private Link to
backend if you want zero-public-IP later).

```bash
FD=akki-fd
az afd profile create -g $RG --profile-name $FD --sku Standard_AzureFrontDoor

# Endpoint
az afd endpoint create -g $RG --profile-name $FD --endpoint-name akki-edge

# Origins — backend container app + SWA.
az afd origin-group create -g $RG --profile-name $FD \
  --origin-group-name app-origin --probe-protocol Https --probe-path /api/health
az afd origin create -g $RG --profile-name $FD --origin-group-name app-origin \
  --origin-name akki-backend --host-name <backend.fqdn>

az afd origin-group create -g $RG --profile-name $FD --origin-group-name marketing-origin
az afd origin create -g $RG --profile-name $FD --origin-group-name marketing-origin \
  --origin-name akki-swa --host-name <swa.fqdn>

# Routes — /app/* and /api/* → backend; everything else → SWA.
az afd route create -g $RG --profile-name $FD --endpoint-name akki-edge \
  --route-name app-routes --patterns-to-match "/api/*" "/app/*" \
  --origin-group app-origin --supported-protocols Https \
  --forwarding-protocol HttpsOnly --link-to-default-domain Enabled

az afd route create -g $RG --profile-name $FD --endpoint-name akki-edge \
  --route-name marketing-routes --patterns-to-match "/*" \
  --origin-group marketing-origin --supported-protocols Https \
  --forwarding-protocol HttpsOnly
```

WAF: attach the Microsoft default rule set ("Microsoft_DefaultRuleSet
2.1") in **Prevention** mode. Add a rate-limit rule of 600 req/min per
IP on `/api/*` to catch the brute-force surface.

TLS: Front Door auto-provisions managed certs for custom domains.
Bind `app.akki.ai` and `akki.ai` to the endpoint after DNS propagates.

---

## Step 6 — Secrets & rotation

Every runtime secret is in Key Vault, mounted into the container app
via `keyvaultref` + the managed identity. Plain (non-secret) env vars
go directly.

```bash
# Grant the managed identity Key Vault read access (RBAC mode).
az role assignment create \
  --assignee $MI_CID \
  --role "Key Vault Secrets User" \
  --scope $(az keyvault show -g $RG -n $KV --query id -o tsv)

# Push every secret listed in PRODUCTION_ENV.md.
for kv in MONGO-URL JWT-SECRET ADMIN-PASSWORD EMERGENT-LLM-KEY \
           AKKI-CRON-SECRET RESEND-API-KEY POSTMARK-WEBHOOK-SECRET \
           STRIPE-SECRET-KEY STRIPE-WEBHOOK-SECRET \
           MINIO-ROOT-USER MINIO-ROOT-PASS AZURE-STORAGE-KEY \
           SENTRY-DSN-BACKEND ; do
  az keyvault secret set --vault-name $KV --name $kv --value '<paste>'
done
```

**Rotation policy**

| Secret | Cadence | Mechanism |
|---|---|---|
| `JWT_SECRET` | Quarterly | Generate new value → push to Key Vault → bounce backend revision. Active sessions are invalidated. |
| `ADMIN_PASSWORD` | Quarterly | Same pattern; backend startup hook (`server.py:390`) rotates the bcrypt hash on next boot. |
| Stripe keys | On every dashboard rotation | Stripe is the source of truth; mirror to Key Vault same day. |
| MinIO root creds | Quarterly | `mc admin user add ...` on the gateway, then push new creds; restart `akki-backend`. |
| `AZURE_STORAGE_KEY` | Bi-annually | `az storage account keys renew` → push new value → restart `akki-blob-gw`. |
| Atlas connection user | Bi-annually | New user, dual-deploy, retire old. |
| `EMERGENT_LLM_KEY` | On compromise only | Emergent profile → revoke + reissue. |

---

## Step 7 — CI/CD

GitHub Actions, two workflows: PR (tests + lint + build) and main
(build → push to ACR → rolling update of Container App).

```yaml
# .github/workflows/deploy-prod.yml
name: deploy-prod
on:
  push:
    branches: [main]
permissions:
  id-token: write
  contents: read
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Build & push backend image
        run: |
          az acr build --registry akkiprodacr \
            --image akki-backend:${{ github.sha }} \
            --file backend/Dockerfile backend/
      - name: Roll backend Container App
        run: |
          az containerapp update -g akki-prod-rg -n akki-backend \
            --image akkiprodacr.azurecr.io/akki-backend:${{ github.sha }}
      - name: Tag Sentry release
        env:
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
          SENTRY_ORG: akki
          SENTRY_PROJECT: akki-backend
        run: |
          npx @sentry/cli releases new ${{ github.sha }}
          npx @sentry/cli releases set-commits ${{ github.sha }} --auto
          npx @sentry/cli releases finalize ${{ github.sha }}
```

Auth: federated identity (OIDC), not long-lived service principals.
Script `az ad app federated-credential create ...` once per subject
(repo + main + env=production); GitHub Actions then receives a fresh
token per run and never holds an Azure secret.

Container Apps does a rolling update by default — old revision drains
on the same `--target-port` for 30 seconds before the new revision
takes over. Health probes are `/api/health`.

---

## Step 8 — Observability

### 8a. Sentry (errors + traces)

EU ingest, **not** US. DSN goes in `SENTRY_DSN_BACKEND` /
`SENTRY_DSN_FRONTEND` (PRODUCTION_ENV.md § 9). Initialise in
`backend/server.py` boot:

```python
import os, sentry_sdk
if os.environ.get("SENTRY_DSN_BACKEND"):
    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_BACKEND"],
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
    )
```

(Phase 13 wires this — today the env var exists but the SDK is not
initialised. Surface it as a known gap below.)

### 8b. Azure Monitor

Container Apps emits Log Analytics by default — set retention to
30 days minimum.

```bash
az monitor log-analytics workspace create \
  --resource-group $RG --workspace-name akki-prod-logs \
  --retention-time 90

# Alert: backend 5xx rate over 1 % for 5 minutes.
az monitor metrics alert create \
  --resource-group $RG --name "akki-backend 5xx > 1%" \
  --scopes $(az containerapp show -g $RG -n akki-backend --query id -o tsv) \
  --condition "avg Requests where ResultCode startswith '5' > 1" \
  --window-size 5m --evaluation-frequency 1m \
  --action $(az monitor action-group show -g $RG -n akki-pager --query id -o tsv)
```

### 8c. Availability test

Front Door has a managed availability test. Add one synthetic GET to
`https://app.akki.ai/api/health` from three regions, alert at any
two-failure window.

---

## Step 9 — Backup & DR

| Layer | Mechanism | RPO | RTO |
|---|---|---|---|
| Mongo | Atlas Continuous Cloud Backup (oplog) | 1 minute | 1 hour (point-in-time restore from console) |
| Object storage | Azure Blob GRS replication | 15 minutes (RA-GRS read endpoint) | 1 hour (failover the storage account, repoint MinIO gateway) |
| Mongo logical dump | Daily `scripts/backup_mongo.sh` → `BACKUP_S3_PATH` | 24 hours | 2 hours |
| Backend image | Pinned in ACR by SHA | n/a | 5 minutes (`az containerapp update --image`) |

The aggregate target is **RPO 1 hour, RTO 1 hour** for normal incidents
and **RPO 24 hours, RTO 2 hours** for catastrophic loss requiring the
logical dump. Document the recovery drill quarterly.

---

## Step 10 — Compliance posture (EU/UK boards)

- **Data residency.** All persistent stores (Atlas, Blob, Container
  Apps logs, Sentry) anchored in EU regions. No data leaves the
  EU/EEA at rest.
- **Encryption.** TLS 1.2 minimum at edge. Azure Storage encrypts at
  rest with platform-managed keys; rotate to customer-managed keys
  (CMK) via Key Vault when an enterprise contract requires it.
- **Audit ledger.** `db.audit_log` is append-only at the application
  layer; the chat audit pack adds SHA-256 chaining and exports a
  verifiable ZIP. Operators do not have read access without an Atlas
  audit row being written.
- **GDPR right to erasure.** Account deletion path is `DELETE
  /api/contexts/{cid}` for context-owned data and the manual Atlas
  query for cross-context records (documented in `DEPLOY.md`).
- **Subprocessors.** MongoDB, Microsoft Azure, Resend, Postmark,
  Stripe, Sentry, Emergent. Maintain the list in
  `/app/docs/SUBPROCESSORS.md` and update on every signing.

---

## Future work (not this phase)

These are scoped here because the topology is clearer with them
mentioned, but they are explicitly **out of scope** for the Phase 12
Azure cutover.

### F1. Native `AzureBlobStorage` adapter (Option B)

Replace the MinIO gateway with a native adapter in
`backend/services/storage_service.py` using `azure-identity` and
`azure-storage-blob`. ~1 day of focused work.

- New dependency: `azure-storage-blob`, `azure-identity`.
- New env vars: `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_KEY` (or
  managed-identity path with `AZURE_CLIENT_ID`).
- Drop env vars: `S3_ENDPOINT`, `S3_FORCE_PATH_STYLE`, MinIO root creds.
- Trade-offs vs Option A:
  - **+** Removes one container, one secret pair, one network hop.
  - **+** Native managed identity — no symmetric secret to rotate.
  - **−** Application code change; risk of a dual-backend window
       during cutover.
  - **−** Loses the S3-protocol fungibility (cannot swap to AWS S3
       without a second adapter).

This is Phase 13 backlog. Don't ship it the same week as the Azure
cutover.

### F2. APScheduler → Container App Jobs

Extract the three in-process schedules into Container App Jobs with
Azure-managed cron triggers, each calling the existing
`/cron/<name>` endpoint with `X-Cron-Secret`. Removes the
`min-replicas == max-replicas` constraint on `akki-backend`. Half-day
of work. Phase 13 backlog.

### F3. Front Door → Container App Private Link

Move from Front Door Standard with public origin to Front Door Premium
with Private Link. Eliminates the public-internet-facing backend FQDN
entirely; Front Door is the only ingress. Phase 14 once we cross the
traffic threshold that justifies the SKU jump.

---

## Known gaps (max 5)

1. **Sentry SDK is not initialised in `backend/server.py`.** Env vars
   exist (`PRODUCTION_ENV.md` § 9), the init block in § 8a above is the
   recommended snippet — Phase 13 work.
2. **APScheduler runs in-process and assumes a single replica.** See § 3d.
3. **`scripts/backup_mongo.sh` does not auto-push to `BACKUP_S3_PATH`.**
   The variable exists; the wiring does not. ~30-minute fix when we
   confirm the backup target.
4. **No `SUBPROCESSORS.md` yet.** Listed as a compliance dependency
   in § Step 10. Stub it before first enterprise signature.
5. **`backend/Dockerfile` and `deploy/blob-gw.Dockerfile` do not
   exist in the repo today.** They are referenced by Step 3 and need
   to be authored as part of the Phase 12 cutover ticket.

---

_End of guide. Pair with `PRODUCTION_ENV.md` for the env-var inventory
and with `STORAGE_MIGRATION.md` for the local→S3 cutover script._
