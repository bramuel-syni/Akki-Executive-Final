# Production environment template

> ⚠️ **DO NOT COMMIT THIS FILE WITH REAL VALUES.** This document is the
> *template*. Every value below is an example. Real values live in
> **Azure Key Vault** and are mounted into Azure Container Apps via
> `secretRef`. Anything you check into git that is not literally one of
> the example placeholders below is a leak — rotate it on detection.

This runbook lists every environment variable the application actually
reads (cross-checked by grepping `backend/` for `os.environ.get(`,
`os.environ[`, `os.getenv(`). Each variable is marked **REQUIRED** or
**OPTIONAL** and includes a one-line note on how to source it.

A blank `.env` template is at the bottom of this file (§ "Copy-paste
template") so an operator can populate it locally and never check it
in.

---

## Table of contents

1. Identity & secrets
2. App
3. LLM
4. Storage (Phase 10)
5. Virus scan (Phase 10)
6. Email out
7. Email in
8. Billing
9. Observability (Phase 13)
10. Backup
11. How to use in Azure Container Apps
12. Copy-paste template

---

## 1. Identity & secrets

| Var | Required | Example | How to source |
|---|---|---|---|
| `MONGO_URL` | **REQUIRED** | `mongodb+srv://akki:<pass>@cluster0.xxx.mongodb.net/akki?retryWrites=true&w=majority` | MongoDB Atlas → Cluster → "Connect" → "Drivers" → copy SRV string. Use a dedicated `akki` user with `readWrite` on `akki` only (never atlasAdmin). |
| `DB_NAME` | **REQUIRED** | `akki` | Logical Mongo database name. Pin per environment (`akki`, `akki_staging`). |
| `JWT_SECRET` | **REQUIRED** | `<64-byte hex>` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. Rotate quarterly; rotation invalidates all sessions. |
| `ADMIN_EMAIL` | **REQUIRED** | `admin@akki.ai` | Boot-seed admin account email. Lower-cased on read. |
| `ADMIN_PASSWORD` | **REQUIRED** | `<32+ char passphrase>` | Boot-seed password. Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. The startup hook **rotates the hash** on every boot to match this value, so changing it here is the rotation mechanism. |

---

## 2. App

| Var | Required | Example | How to source |
|---|---|---|---|
| `APP_NAME` | OPTIONAL | `AKKI` | Surfaced in `FastAPI(title=...)`. Default `AKKI`. |
| `CORS_ORIGINS` | **REQUIRED** in prod | `https://app.akki.ai,https://akki.ai` | Comma-separated list. `*` is allowed for dev only and triggers a credentialed-CORS regex fallback (`server.py:164-210`). In prod, list exactly the origins you serve. |
| `FRONTEND_URL` | **REQUIRED** in prod | `https://app.akki.ai` | Used to construct tracked share links (`/share/:token`) and review URLs in transactional emails. Must match the public origin. |
| `FRONTEND_ORIGIN` | OPTIONAL | `https://app.akki.ai` | Legacy alias used by `cycle.py` `_frontend_origin()` for review-request email links. Set to the same value as `FRONTEND_URL`. |
| `AKKI_CRON_SECRET` | **REQUIRED** in prod | `<32-byte hex>` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. Required header `X-Cron-Secret` on internal cron endpoints. When unset, APScheduler is **disarmed** at boot — set it in prod or you lose the Tue/Mon/Daily schedulers. |
| `AKKI_AUTH_OBSERVE_RATE` | OPTIONAL | `0.1` | Float 0..1. Sample rate for `db.auth_events` writes (default `0.1` → 10 % of auth events are logged). Lower in high-traffic, raise during incident response. |
| `UPLOADS_DIR` | OPTIONAL | `/data/uploads` | Override for the local upload cache. Defaults to `backend/uploads/`. Always points to a persistent volume in container deploys. |
| `INBOUND_DOMAIN` | OPTIONAL | `inbound.akki.ai` | Default mailbox host shown to users in the inbox-address surface. |
| `HOSTNAME` | OPTIONAL | `<auto>` | Read for diagnostic logging only. Set automatically by the container runtime; do not override. |

---

## 3. LLM

| Var | Required | Example | How to source |
|---|---|---|---|
| `EMERGENT_LLM_KEY` | **REQUIRED** | `sk-emergent-...` | Emergent profile → "Universal Key" → copy. One key fronts Anthropic, OpenAI and Google through `emergentintegrations`. When unset, the LLM proxy returns deterministic `"no-key-fallback"` responses (dev only — never run prod unkeyed). |
| `LLM_MODEL_DEEP` | OPTIONAL | `claude-opus-4-6` | Override the deep tier. Per-account-per-day quota lives in `db.llm_deep_usage`. |
| `LLM_MODEL_STANDARD` | OPTIONAL | `claude-sonnet-4-5-20250929` | Override the standard tier. Used by Decks generate, Briefings, Solve synthesis (free). |
| `LLM_MODEL_FAST` | OPTIONAL | `gemini-2.5-flash` | Override the fast tier. Validator runs against this provider/family by design (cross-check). |
| `VALIDATOR_DAILY_SOFT_CAP` | OPTIONAL | `200` | Phase 11 ITEM B — daily soft cap on independent-validator calls per surface. When tripped, `validate_independent` returns the `qualified` fallback and the parent endpoint continues. Default 200/day/surface. |
| `AKKI_DEEP_UNIT_COST_USD` | OPTIONAL | `0.075` | Used by `/admin/spend` to dollarise the deep-tier counter. Update when the deep model price changes. |

---

## 4. Storage (Phase 10)

The storage abstraction in `backend/services/storage_service.py` switches
on `STORAGE_BACKEND`:

- `local` (default for dev) — writes under `UPLOADS_DIR`.
- `s3` — uses the S3 SDK against AWS or any S3-compatible endpoint.
- `minio` — alias of `s3` with `S3_FORCE_PATH_STYLE=true` defaulted.

For Azure prod, see `AZURE_DEPLOY.md` § Step 2 for the **MinIO gateway
on Azure Blob** (Option A) — env vars below are the same as for `s3`.

| Var | Required | Example | How to source |
|---|---|---|---|
| `STORAGE_BACKEND` | **REQUIRED** in prod | `s3` | One of `local` / `s3` / `minio`. Prod must be `s3` or `minio`. |
| `S3_ENDPOINT` | **REQUIRED** for `s3`/`minio` | `https://akki-blob-gw.westeurope.azurecontainer.io` | The MinIO-gateway container's public URL (Option A) or AWS S3 (`https://s3.eu-west-1.amazonaws.com`). |
| `S3_REGION` | **REQUIRED** for `s3`/`minio` | `eu-west-1` | Region tag. MinIO accepts any string; AWS expects a real region. |
| `S3_BUCKET` | **REQUIRED** for `s3`/`minio` | `akki-prod-uploads` | Bucket / container name. Create with versioning + lifecycle (90-day delete on `archived/` prefix). |
| `S3_ACCESS_KEY` | **REQUIRED** for `s3`/`minio` | `<access key>` | MinIO root user (Option A) or AWS IAM access key. Rotate quarterly. |
| `S3_SECRET_KEY` | **REQUIRED** for `s3`/`minio` | `<secret>` | MinIO root password (Option A) or AWS IAM secret. Pair with above. |
| `S3_FORCE_PATH_STYLE` | OPTIONAL | `true` | Required for MinIO and most non-AWS S3 endpoints. Default `false`. |

---

## 5. Virus scan (Phase 10)

ClamAV runs as a sidecar container next to the backend. The backend
opens a TCP `INSTREAM` socket per upload (see `backend/services/clamav_service.py`).

| Var | Required | Example | How to source |
|---|---|---|---|
| `CLAMAV_HOST` | **REQUIRED** in prod | `localhost` | Hostname of the clamd daemon. In Azure Container Apps with sidecar, this is `localhost`. |
| `CLAMAV_PORT` | OPTIONAL | `3310` | Default `3310`. Match the sidecar's listen port. |
| `CLAMAV_TIMEOUT_SECONDS` | OPTIONAL | `30` | Default `30`. Increase if you regularly scan files >50 MB. |
| `ALLOW_UNSAFE_UPLOADS` | OPTIONAL | `0` | Set to `1` only in dev to bypass the scan. **Must be `0` (or unset) in prod.** A boot guard does not enforce this — operators do. |

---

## 6. Email out (Resend)

Outbound transactional email goes through Resend
(`backend/email_service.py`). When `RESEND_API_KEY` is unset, the
sender returns `{"mode": "noop"}` and never raises — useful for staging
without burning sender reputation.

| Var | Required | Example | How to source |
|---|---|---|---|
| `RESEND_API_KEY` | **REQUIRED** in prod | `re_...` | resend.com → API Keys → "Create API key" with the `Sending access` scope. Restrict to the prod sending domain. |
| `RESEND_FROM_EMAIL` | **REQUIRED** in prod | `akki@akki.ai` | Verified sender address on the resend domain. The product writes outbound mail "from AKKI on behalf of <user>" — this is AKKI's own address, not the user's. |
| `RESEND_FROM_NAME` | OPTIONAL | `AKKI` | Friendly name in the From header. Default `AKKI`. |
| `RESEND_FROM` | OPTIONAL | `AKKI <akki@akki.ai>` | Legacy single-string variant some callers consult. Set if you've migrated from an older release that read this. |

---

## 7. Email in (Postmark)

Inbound email goes through Postmark's mailbox-hash routing into
`POST /api/inbound/postmark` (`backend/routers/inbound_email.py`).

| Var | Required | Example | How to source |
|---|---|---|---|
| `POSTMARK_WEBHOOK_SECRET` | **REQUIRED** in prod | `<32-byte hex>` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. Postmark passes it back as `?secret=` on every inbound POST; we 403 if it doesn't match. |
| `POSTMARK_INBOUND_DOMAIN` | **REQUIRED** in prod | `inbound.akki.ai` | The inbound DNS-routed domain configured in Postmark. Surfaced to users in their inbox-address tile. |
| `POSTMARK_SERVER_TOKEN` | OPTIONAL | `<server token>` | Only set if you also send via Postmark (we send via Resend). Safe to leave unset. |

---

## 8. Billing (Stripe)

Billing is **disabled by default**. A boot guard in `server.py:219-227`
refuses to start the app if `BILLING_ENABLED=true` and no Stripe key
is present — a half-configured billing surface is worse than a
disabled one.

| Var | Required | Example | How to source |
|---|---|---|---|
| `BILLING_ENABLED` | OPTIONAL | `false` | One of `1` / `true` / `yes` to enable. Default `false`. |
| `STRIPE_SECRET_KEY` | Required iff `BILLING_ENABLED=true` | `sk_live_...` | Stripe Dashboard → Developers → API keys → "Reveal live key". Use a **restricted key** with only the resources `checkout_sessions`, `customers`, `subscriptions`, `prices`, `webhook_endpoints` (write where required). |
| `STRIPE_API_KEY` | OPTIONAL | (legacy alias of `STRIPE_SECRET_KEY`) | Older releases consult this name. Set to the same value if migrating. |
| `STRIPE_WEBHOOK_SECRET` | Required iff `BILLING_ENABLED=true` | `whsec_...` | Stripe Dashboard → Developers → Webhooks → endpoint → "Signing secret". Per-environment endpoint, per-environment secret. |
| `STRIPE_PUBLISHABLE_KEY` | OPTIONAL | `pk_live_...` | Publishable key for client-side Checkout/Elements if surfaced in the frontend. Safe to expose. |

---

## 9. Observability (Phase 13)

Sentry is **off** by default. When `SENTRY_DSN_BACKEND` is set, the
backend initialises sentry-sdk; same shape for the frontend.

| Var | Required | Example | How to source |
|---|---|---|---|
| `SENTRY_DSN_BACKEND` | OPTIONAL | `https://<key>@<org>.ingest.de.sentry.io/<project>` | Sentry → Project (Python) → Settings → Client Keys (DSN). Use the **EU region** ingest (`*.ingest.de.sentry.io`) for EU compliance posture. |
| `SENTRY_DSN_FRONTEND` | OPTIONAL | `https://<key>@<org>.ingest.de.sentry.io/<project>` | Sentry → Project (React) → DSN. Different DSN from backend. |
| `SENTRY_ENVIRONMENT` | OPTIONAL | `production` | Environment tag. `production` / `staging` / `dev`. |
| `SENTRY_TRACES_SAMPLE_RATE` | OPTIONAL | `0.1` | Float 0..1 trace sampling. Start at `0.1` in prod, `1.0` in staging. |

---

## 10. Backup

Mongo dumps are scripted in `scripts/backup_mongo.sh` and
`scripts/restore_mongo.sh`. Migration script for local→S3 lives at
`scripts/migrate_local_to_s3.py`.

| Var | Required | Example | How to source |
|---|---|---|---|
| `BACKUP_DIR` | OPTIONAL | `/var/backups/akki` | Local path the dump script writes to before pushing to remote. Must be on a persistent volume. |
| `BACKUP_S3_PATH` | OPTIONAL | `s3://akki-prod-backups/mongo/` | Optional remote target; the dump script ships the tarball here on success. AWS CLI (or `s5cmd`) must be installed in the runner. |

---

## 11. How to use in Azure Container Apps

Every secret above is stored as an Azure Key Vault secret and mounted
into the Container App as a **secret reference**. Plain env vars (the
LLM model overrides, sample rates, the `BILLING_ENABLED` flag, etc.)
go in directly as `env` values.

```bash
# 1. Push the secret value to Key Vault.
az keyvault secret set \
  --vault-name akki-prod-kv \
  --name MONGO-URL \
  --value 'mongodb+srv://...'

# 2. Reference it from the Container App (creating the secret entry
#    on the app first, then exposing it as an env var that uses it).
az containerapp secret set \
  --resource-group akki-prod-rg \
  --name akki-backend \
  --secrets mongo-url=keyvaultref:https://akki-prod-kv.vault.azure.net/secrets/MONGO-URL,identityref:/subscriptions/.../akki-backend-mi

az containerapp update \
  --resource-group akki-prod-rg \
  --name akki-backend \
  --set-env-vars MONGO_URL=secretref:mongo-url
```

For the full container-app definition (with sidecar, ingress, scale
rules and managed identity binding to Key Vault), see
`AZURE_DEPLOY.md` § Step 3 and § Step 6.

---

## 12. Copy-paste template

Copy the block below to a local `.env` file. **Never commit.**

```dotenv
# ── 1. Identity & secrets
MONGO_URL=
DB_NAME=akki
JWT_SECRET=
ADMIN_EMAIL=admin@akki.ai
ADMIN_PASSWORD=

# ── 2. App
APP_NAME=AKKI
CORS_ORIGINS=https://app.akki.ai
FRONTEND_URL=https://app.akki.ai
FRONTEND_ORIGIN=https://app.akki.ai
AKKI_CRON_SECRET=
AKKI_AUTH_OBSERVE_RATE=0.1
UPLOADS_DIR=/data/uploads
INBOUND_DOMAIN=inbound.akki.ai

# ── 3. LLM
EMERGENT_LLM_KEY=
LLM_MODEL_DEEP=claude-opus-4-6
LLM_MODEL_STANDARD=claude-sonnet-4-5-20250929
LLM_MODEL_FAST=gemini-2.5-flash
VALIDATOR_DAILY_SOFT_CAP=200
AKKI_DEEP_UNIT_COST_USD=0.075

# ── 4. Storage
STORAGE_BACKEND=s3
S3_ENDPOINT=https://akki-blob-gw.westeurope.azurecontainer.io
S3_REGION=eu-west-1
S3_BUCKET=akki-prod-uploads
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_FORCE_PATH_STYLE=true

# ── 5. Virus scan
CLAMAV_HOST=localhost
CLAMAV_PORT=3310
CLAMAV_TIMEOUT_SECONDS=30
ALLOW_UNSAFE_UPLOADS=0

# ── 6. Email out
RESEND_API_KEY=
RESEND_FROM_EMAIL=akki@akki.ai
RESEND_FROM_NAME=AKKI

# ── 7. Email in
POSTMARK_WEBHOOK_SECRET=
POSTMARK_INBOUND_DOMAIN=inbound.akki.ai

# ── 8. Billing (disabled by default — flip to true once Stripe is wired)
BILLING_ENABLED=false
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PUBLISHABLE_KEY=

# ── 9. Observability
SENTRY_DSN_BACKEND=
SENTRY_DSN_FRONTEND=
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# ── 10. Backup
BACKUP_DIR=/var/backups/akki
BACKUP_S3_PATH=s3://akki-prod-backups/mongo/
```

_End of production environment template. Pair with `AZURE_DEPLOY.md` for the deployment topology._
