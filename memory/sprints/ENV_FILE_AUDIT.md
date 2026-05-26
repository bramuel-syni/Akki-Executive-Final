# `.env` File Audit — Keys Only

**Dispatched:** 2026-05-26 (redeploy-cleanup chunk, Task 3).
**Scope:** Read-only audit. Lists only the LEFT-HAND-SIDE (keys) — never the values. Safe to commit.
**Trigger:** User whitelisted `backend/.env` + `frontend/.env` in `.gitignore` so the bundle travels with the deploy. This audit gives the user situational awareness of which keys carry which class of data so they can decide later whether any need rotation/relocation.
**Hard rule honoured:** No `.env` file modifications during this audit.

---

## `backend/.env`

| Metric | Count |
| --- | --- |
| Total lines | 81 |
| Comment lines (`#`-prefixed) | 29 |
| Blank lines | 9 |
| Key lines (KEY=value) | 43 |

### Keys by category

#### URL / host config (5 keys)

| Key | Notes |
| --- | --- |
| `MONGO_URL` | Backend → MongoDB connection string. Production swap point (local → Atlas). Protected variable. |
| `CORS_ORIGINS` | FastAPI CORSMiddleware allowed-origins list. |
| `CLAMAV_HOST` | ClamAV daemon hostname (Synisense Shield upload scanning). |
| `S3_ENDPOINT` | S3-compatible storage endpoint URL (used when `STORAGE_BACKEND=s3`). |
| `CYCLE_REPLY_DOMAIN` | Postmark inbound reply-routing domain. |

#### Service identifier (10 keys)

| Key | Notes |
| --- | --- |
| `DB_NAME` | MongoDB database name. Protected variable. |
| `APP_NAME` | Application display name. |
| `CLAMAV_PORT` | ClamAV daemon port number. |
| `CLAMAV_TIMEOUT_SECONDS` | ClamAV scan timeout. |
| `S3_REGION` | S3 bucket region code. |
| `S3_BUCKET` | S3 bucket name. |
| `BACKUP_DIR` | Local disk path for mongodump output. |
| `RESEND_FROM_EMAIL` | "From" address used by the Resend send-mail integration. |
| `RESEND_FROM_NAME` | "From" display name for Resend sends. |
| `CHAT_STREAMING_MODE` | Mode toggle for chat streaming (e.g. `anthropic` / `gemini` / `off`). |

#### Feature flag / operational dial (14 keys)

| Key | Notes |
| --- | --- |
| `ALLOW_UNSAFE_UPLOADS` | Bypasses ClamAV gate (DEV-ONLY; must be `false` in production). |
| `STORAGE_BACKEND` | Storage backend selector (`local` / `s3`). |
| `S3_FORCE_PATH_STYLE` | S3 path-style addressing toggle. |
| `BILLING_ENABLED` | Master switch for Stripe billing surface (currently `false` per chunk-c). |
| `SYNISENSE_USE_POOL` | Synisense LLM connection-pool toggle. |
| `SYNISENSE_POOL_SIZE` | Synisense LLM connection-pool size. |
| `SYNISENSE_ALLOW_INSECURE` | Dev-only Synisense TLS bypass. |
| `SYNISENSE_LLM_FALLBACK_CAP` | Fallback rate cap (operational dial). |
| `SYNISENSE_LLM_FALLBACK_CONCURRENCY` | Fallback concurrency cap (operational dial). |
| `SYNISENSE_LLM_FALLBACK_TIMEOUT_MS` | Fallback timeout in ms (operational dial). |
| `SYNISENSE_SHIELD_MAP_TTL_HOURS` | Shield-map cache TTL in hours (operational dial). |
| `POSTMARK_USE_HMAC` | Postmark webhook HMAC verification toggle. |
| `ANTHROPIC_STREAM_MODEL` | Anthropic chat-streaming model name override. |
| `GEMINI_STREAM_MODEL` | Gemini chat-streaming model name override. |

#### API key / secret / token (11 keys)

| Key | Notes |
| --- | --- |
| `JWT_SECRET` | HS-family JWT signing secret. **Production-tier.** |
| `EMERGENT_LLM_KEY` | Emergent universal LLM key (OpenAI / Anthropic / Gemini). **Production-tier — runs through emergentintegrations.** |
| `AKKI_CRON_SECRET` | Shared secret for the cron-triggered admin endpoints. |
| `S3_ACCESS_KEY` | S3 access key ID. |
| `SYNISENSE_MASTER_KEY` | Synisense Shield master signing key. |
| `RESEND_API_KEY` | Resend transactional email API key. |
| `POSTMARK_SERVER_TOKEN` | Postmark inbound + outbound server token. |
| `POSTMARK_WEBHOOK_SECRET` | Postmark webhook verification secret. |
| `ANTHROPIC_API_KEY` | Anthropic direct API key (for direct streaming, separate from universal LLM key). |
| `GEMINI_API_KEY` | Google Gemini direct API key. |
| `OPENAI_API_KEY` | OpenAI direct API key. |

#### Password / credential (3 keys)

| Key | Notes |
| --- | --- |
| `S3_SECRET_KEY` | S3 secret access key. **Production-tier.** |
| `SYNISENSE_MASTER_SECRET` | Synisense Shield master signing secret (companion to MASTER_KEY). **Production-tier.** |
| `POSTMARK_BASIC_AUTH_USER` | Postmark webhook basic-auth username. |

### Category summary — `backend/.env`

| Category | Key count |
| --- | --- |
| URL / host config | 5 |
| Service identifier | 10 |
| Feature flag / operational dial | 14 |
| API key / secret / token | 11 |
| Password / credential | 3 |
| **Total** | **43** |

---

## `frontend/.env`

| Metric | Count |
| --- | --- |
| Total lines | 2 |
| Comment lines | 0 |
| Blank lines | 0 |
| Key lines (KEY=value) | 2 |

### Keys by category

#### URL / host config (1 key)

| Key | Notes |
| --- | --- |
| `REACT_APP_BACKEND_URL` | Production-deployed external URL for the FastAPI backend. Protected variable. |

#### Service identifier (1 key)

| Key | Notes |
| --- | --- |
| `WDS_SOCKET_PORT` | Webpack-dev-server hot-reload socket port (dev-only — irrelevant on production builds). |

### Category summary — `frontend/.env`

| Category | Key count |
| --- | --- |
| URL / host config | 1 |
| Service identifier | 1 |
| Feature flag | 0 |
| API key / secret / token | 0 |
| Password / credential | 0 |
| **Total** | **2** |

---

## Production-tier callout (information only)

Items where rotation/relocation may be appropriate depending on how the production environment is provisioned:

| Key | Why flagged |
| --- | --- |
| `JWT_SECRET` | Signs every auth token. If the bundle ever leaks, all tokens forge-able. |
| `EMERGENT_LLM_KEY` | Spend-bearing. |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Direct-vendor spend-bearing keys (in addition to the universal one). |
| `RESEND_API_KEY` | Send-mail spend-bearing. |
| `POSTMARK_SERVER_TOKEN`, `POSTMARK_WEBHOOK_SECRET` | Inbound-mail authentication. |
| `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Object storage credentials. |
| `SYNISENSE_MASTER_KEY`, `SYNISENSE_MASTER_SECRET` | Shield signing keys. |
| `AKKI_CRON_SECRET` | Cron job authentication. |

The user decides whether any of these should rotate before deploying the bundle to a public-internet-facing pod. This audit is informational only — no `.env` files modified.

---

*Audit complete. No `.env` files touched.*
