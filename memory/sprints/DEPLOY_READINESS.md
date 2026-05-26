# Deploy-readiness — UI-cleanup batch (Phases A → F.6)

**Last updated:** 2026-05-26 · **Batch close commit:** F.6 polish + trip report

This document is the operator checklist for promoting the
UI-cleanup batch (Phases A → F.6) to production. The user will
issue an explicit deploy signal on return — DO NOT deploy without it.

---

## Pre-deploy verification

- [ ] **All pytest GREEN.** Target: **276/276** across Phases A–F.6
      (160 pre-batch + 116 added in this batch). Run:
  ```
  cd /app/backend && python -m pytest tests/test_home_cleanup_phase_*.py tests/test_phase_d_audit_correction.py -q
  ```
- [ ] **No frontend console errors** on primary routes:
      `/app/work-studio`, `/app/task-manager`, `/app/solva`,
      `/app/chat`, `/app/task-manager/activity`, `/contribute/<test-token>`.
- [ ] **Universal Document Drawer** mounts on every doc-listing
      surface: Work Studio · Workspace · Pulse · Cycle. URL contract
      `?doc_id=<uuid>` opens it everywhere.
- [ ] **Universal Task Drawer** mounts on Task Manager; URL
      contract `?task_id=<uuid>` opens it.
- [ ] **Drawer stack pattern** verified: `?task_id=X&doc_id=Y`
      mounts both; closing inner returns to outer.
- [ ] **All audit events** firing:
      `task.created`, `task.contributor.invited`,
      `task.contribution.{not_started,in_progress,submitted,approved,needs_revision}`,
      `task.contribution.submitted_via_email`,
      `task.compile.{drafting,review,circulation,final_production,commit}.{started,completed,failed}`,
      `task.compile.llm.timeout`,
      `task.state.auto_closed`,
      `document.prompted_edit.proposed`,
      `solva.briefing.shown`, `solva_variant_seen`, `solva_key_emissions`.
- [ ] **Shield invariants preserved** —
      no `emergentintegrations` direct imports
      (`grep -rn 'from emergentintegrations' /app/backend/ | grep -v __pycache__`
       returns empty), all LLM calls route through
      `services.synisense.shield.client.invoke`.
- [ ] **3-second LLM timeout** wired in intelligence + compile
      services. Fallback paths are deterministic.
- [ ] **Phase A–E.4 surfaces** untouched / verified non-regressed.

---

## Environment requirements

### Backend env vars

| Var | Purpose | Example | Required |
| --- | --- | --- | --- |
| `MONGO_URL`                | Mongo connection URI            | `mongodb://localhost:27017`  | YES — protected |
| `DB_NAME`                  | Mongo database name             | `akki_production`            | YES — protected |
| `JWT_SECRET`               | JWT signing secret              | `<random 32+ bytes>`         | YES |
| `EMERGENT_LLM_KEY`         | Shield-routed LLM credential    | provisioned by Emergent     | YES |
| `SENDGRID_API_KEY`         | SendGrid transactional + Inbound Parse credential | `SG.xxx-xxx-xxx` | YES (Debt W1 — replaces Postmark) |
| `SENDGRID_FROM_EMAIL`      | Verified sender address (SPF + DKIM authenticated) | `noreply@akki.example.com` | YES |
| `SENDGRID_INBOUND_DOMAIN`  | SendGrid Inbound Parse parse hostname (MX records on this domain point at SendGrid) | `inbound.akki.example.com` | YES (Debt W1) |
| `SENDGRID_INBOUND_AUTH_USERNAME` | Optional HTTP Basic Auth user on the Inbound Parse webhook | `sg-inbound` | optional |
| `SENDGRID_INBOUND_AUTH_PASSWORD` | Optional HTTP Basic Auth password on the Inbound Parse webhook | `<random 32+ bytes>` | optional |
| `EMAIL_PROVIDER`           | Force-pick provider (`sendgrid` \| `resend`). When unset, SendGrid is preferred if `SENDGRID_API_KEY` is set, else Resend. | `sendgrid` | optional |
| `RESEND_API_KEY`           | LEGACY fallback transactional provider | `re_xxx` | optional (back-compat) |
| `CYCLE_REPLY_DOMAIN`       | LEGACY reply-to domain (used when `SENDGRID_INBOUND_DOMAIN` unset) | `parse.akki.example.com` | optional |
| `PUBLIC_BASE_URL`          | Canonical app origin used in magic-link URLs | `https://app.akki.example.com` | recommended |
| `RESEND_FROM_EMAIL`        | LEGACY transactional sender address | `onboarding@akki.example.com` | optional (back-compat) |

### Frontend env vars

| Var | Purpose | Example | Required |
| --- | --- | --- | --- |
| `REACT_APP_BACKEND_URL`    | Backend base URL                | `https://app.akki.example.com` | YES — protected |

---

## SendGrid setup (Debt W1 — 2026-05-26 — replaces Postmark)

### Transactional stream

Required for: F.5 contributor invites (Mode 1 deep-link, Mode 2
magic-link, Mode 3 reply-tagged), F.4 circulation reviewer invites,
post-commit confirmations.

1. Create a **SendGrid account** (or use existing).
2. Settings → Sender Authentication → authenticate your sending domain
   (publish SPF + DKIM records). This is required to clear spam
   filters at scale.
3. Settings → API Keys → create a Full Access key. Save as
   `SENDGRID_API_KEY`.
4. Set `SENDGRID_FROM_EMAIL` to a verified sender on the authenticated
   domain (e.g., `noreply@akki.example.com`).
5. Outbound smoke test (works against in-process app):
   ```bash
   cd /app/backend
   python -c "
   import asyncio
   from email_service import send_email
   r = asyncio.run(send_email(
       to=['you@example.com'],
       subject='SendGrid smoke',
       html='<p>hello from SendGrid</p>',
       text='hello from SendGrid'))
   print(r)"
   # Expected: {'ok': True, 'mode': 'sent', 'provider': 'sendgrid', ...}
   ```

### Inbound Parse (required for F.5 Mode 3 — email reply contributors)

Required for: contributors who choose `email_reply` mode. They reply
to `task-<token>@<SENDGRID_INBOUND_DOMAIN>` and SendGrid POSTs the
parsed message to our webhook as multipart/form-data.

1. **Pick an inbound parse hostname** you own (e.g.,
   `inbound.akki.example.com`). Set `SENDGRID_INBOUND_DOMAIN` to it.
2. **DNS MX record** on that hostname: priority `10`, value
   `mx.sendgrid.net.`. Verify with `dig MX inbound.akki.example.com`.
3. **SendGrid dashboard → Settings → Inbound Parse → Add Host & URL**:
   - Receiving Domain: `inbound.akki.example.com`
   - Destination URL: `https://<prod-host>/api/inbound/sendgrid`
   - **Check** "POST the raw, full MIME message" if you want
     `email` field populated. Optional — the parsed fields are
     sufficient for our adapter.
   - Spam Check: enable (sets `SPF` / `dkim` form fields).
4. **HTTP Basic Auth (optional)**: if you set
   `SENDGRID_INBOUND_AUTH_USERNAME` + `SENDGRID_INBOUND_AUTH_PASSWORD`
   on the backend, configure the SendGrid Inbound Parse URL as
   `https://user:pass@<prod-host>/api/inbound/sendgrid` so SendGrid
   sends matching Basic auth on each POST.
5. **Local verification curl** (against the live deploy):
   ```bash
   curl -X POST "${REACT_APP_BACKEND_URL}/api/inbound/sendgrid" \
     -F "from=contributor@example.com" \
     -F "to=task-<TOKEN>@${SENDGRID_INBOUND_DOMAIN}" \
     -F "subject=Re: contribution" \
     -F "text=Here is my answer." \
     -F "attachments=1" \
     -F 'attachment-info={"attachment1": {"filename": "answer.txt", "type": "text/plain"}}' \
     -F "attachment1=@/tmp/answer.txt;type=text/plain"
   # Expected: 200 {"ok": true, "task_id": "...", "doc_ids": ["..."]}
   # OR        200 {"ok": false, "error": "token_unknown_or_expired"}
   #   if the token doesn't exist (forensic row still written).
   ```

### Postmark — retired (returns 410 Gone)

`POST /api/inbound/postmark` and `POST /api/webhooks/postmark/inbound`
now return **410 Gone** with a JSON migration note. Re-point any
external webhooks to `/api/inbound/sendgrid`. The Postmark code path
is removed from production behaviour; the legacy Phase B tests are
skipped (kept on disk for git-history continuity).

### User-facing setup runbook (operator quick-start)

Three options for setting the SendGrid env vars on an Emergent pod
— pick whichever fits your workflow.

**Option A — Emergent secrets panel (recommended for prod)**
1. Open the Emergent app dashboard → your project → Settings →
   Secrets.
2. Add each key from the SendGrid block in `/app/backend/.env.example`:
   - `SENDGRID_API_KEY`
   - `SENDGRID_FROM_EMAIL`
   - `SENDGRID_INBOUND_DOMAIN`
   - `SENDGRID_INBOUND_AUTH_USERNAME` *(optional)*
   - `SENDGRID_INBOUND_AUTH_PASSWORD` *(optional)*
3. Click "Save" — the panel injects them into the pod env on next
   boot. No file edit required. Restart the backend supervisor
   (`sudo supervisorctl restart backend`) to pick them up.

**Option B — VS Code (when iterating locally on the pod)**
1. Open `/app/backend/.env` in the editor.
2. Fill the empty SendGrid slots that the debt-closure pass added.
3. Save → supervisor hot-reloads .env-dependent paths on next
   backend restart. Run `sudo supervisorctl restart backend`.

**Option C — Terminal (one-liner, for ad-hoc testing)**
```bash
# Edit in place
sed -i 's|^SENDGRID_API_KEY=$|SENDGRID_API_KEY=SG.your-real-key-here|' /app/backend/.env
sed -i 's|^SENDGRID_FROM_EMAIL=$|SENDGRID_FROM_EMAIL=noreply@akki.example.com|' /app/backend/.env
sed -i 's|^SENDGRID_INBOUND_DOMAIN=$|SENDGRID_INBOUND_DOMAIN=inbound.akki.example.com|' /app/backend/.env
# Restart
sudo supervisorctl restart backend
```

**Basic Auth (recommended for production Inbound Parse)**

SendGrid lets you secure the inbound parse webhook with HTTP Basic
Auth. Steps:

1. Generate a strong username + password (≥ 32 bytes each):
   ```bash
   python -c "import secrets; print('user:', secrets.token_urlsafe(16)); print('pass:', secrets.token_urlsafe(32))"
   ```
2. Set them in your env (via Option A/B/C above):
   ```
   SENDGRID_INBOUND_AUTH_USERNAME=<the-username>
   SENDGRID_INBOUND_AUTH_PASSWORD=<the-password>
   ```
3. In the SendGrid dashboard → Inbound Parse → edit your hostname,
   update the **Destination URL** to:
   ```
   https://<the-username>:<the-password>@<prod-host>/api/inbound/sendgrid
   ```
4. SendGrid will send a `Authorization: Basic <base64>` header on
   each POST. The backend verifies it via
   `secrets.compare_digest` (constant-time).

**Verify wiring — health-ping endpoint**

After env vars are set + backend restarted, hit the admin
health-ping (superadmin only — never logs secrets):

```bash
TOKEN=$(curl -s -X POST "${REACT_APP_BACKEND_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"<admin-email>","password":"<admin-pw>"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s "${REACT_APP_BACKEND_URL}/api/admin/email-provider/health" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
```

Expected (when all 5 vars set + DNS + Inbound Parse configured):
```json
{
  "active_provider": "sendgrid",
  "from_email_configured": true,
  "inbound_domain_configured": true,
  "basic_auth_configured": true,
  "outbound_smoke": {
    "ok": true,
    "provider_response_ms": 234,
    "sandbox_mode": true
  },
  "inbound_parse": {
    "domain": "inbound.akki.example.com",
    "webhook_path": "/api/inbound/sendgrid",
    "ready": true,
    "route_mounted": true
  },
  "warnings": []
}
```

The health-ping uses SendGrid's `mail_settings.sandbox_mode` flag —
the API call **validates** the envelope (credentials, sender, domain
auth) without delivering a real email. Safe to run as often as you
like. The endpoint NEVER 500s — any error surfaces in `warnings[]`.

---

## MongoDB collections — new in this batch

| Collection | Purpose | Created by |
| --- | --- | --- |
| `tasks`                       | F.1+ — Task Manager primary record (objective, success_criteria, output_spec, team, state, readiness_score, compile_session, status_history). | F.1 |
| `task_intelligence`           | F.3 — cache of intelligence payloads keyed by `(task_id, task_hash)`. | F.3 |
| `task_circulation_tokens`     | F.4 — magic-link tokens for compile-stage reviewers. | F.4 |
| `task_contributor_tokens`     | F.5 — magic-link tokens for contributors. | F.5 |
| `task_inbound_emails`         | F.5 — forensic log of inbound emails (ingested / sender_mismatch / token_unknown_or_expired). | F.5 |
| `document_intelligence`       | E.3 — cache of document-level intelligence payloads. | E.3 |
| `solva_briefing_state`        | C — per-account briefing dismissal state. | C |
| `solva_variant_seen`          | D.2 — telemetry for question-variant emissions. | D.2 |
| `solva_key_emissions`         | D.2 — telemetry for question-key emissions. | D.2 |

**Schema additions to existing collections:**

| Collection | New fields | Purpose |
| --- | --- | --- |
| `documents` | `task_id`, `contributor_email`, `contributor_id`, `contributor_token`, `contributor_note`, `source`, `compile_session` | F.3 + F.5 — link docs to tasks + contributor provenance. |
| `documents.origin` | accepts `"magic_link"`, `"email_receipt"` | F.5 — contributor channels. |

---

## Indexes

Hot-path queries observed during the batch — apply these before
deploy to avoid full-collection scans. These are
**recommendations** for the deploy operator to apply post-deploy;
the code does NOT auto-create them. Apply during a low-traffic
window — most are `{ background: true }` safe but unique indexes
may need a pre-flight dedupe step if duplicate documents exist.

### `tasks`

```javascript
// Task Listing — filter by state + sort by created_at desc.
// Powers GET /api/tasks?state=<…>.
db.tasks.createIndex({ "account_id": 1, "state": 1, "created_at": -1 });

// Owner-scoped tasks ordered by last update (used by drawer & rail).
db.tasks.createIndex({ "account_id": 1, "owner_id": 1, "updated_at": -1 });

// Single-task lookup by ID. NOTE: the live schema stores the task
// identifier in field `id` (not `task_id`); the unique index is on
// `id`. If you migrate to a `task_id` field name later, repoint this.
db.tasks.createIndex({ "id": 1 }, { unique: true });
```

**Reasoning:** the Task Listing surface (Task Manager 3-tab view)
filters on `(account_id, state)` and sorts on `created_at`; the
right-rail FollowUpDraftsCard + Task Drawer load by owner +
updated_at. The unique index on the canonical task id prevents
duplicate inserts under retry storms.

### `task_contributor_tokens` (F.5 magic links)

```javascript
db.task_contributor_tokens.createIndex({ "token": 1 }, { unique: true });
db.task_contributor_tokens.createIndex({ "contributor_email": 1 });
db.task_contributor_tokens.createIndex({ "task_id": 1 });

// TTL — Mongo auto-evicts expired tokens 30 days after expires_at.
// expires_at is stored as ISO string in the live schema; convert to
// `Date` BSON type before applying this TTL OR apply on the Date
// field if you add a parallel `expires_at_dt` column.
db.task_contributor_tokens.createIndex(
  { "expires_at": 1 },
  { expireAfterSeconds: 0 }
);
```

**Reasoning:** every contributor portal hit (`GET /api/tasks/
contribute/<token>`) does a `findOne({ token })`; that path needs
to be O(log n). The `contributor_email` index supports re-invite
rotation (revoke prior tokens for this email). TTL is operational
hygiene — tokens are credentials, expired credentials should be
expunged.

### `task_circulation_tokens` (F.4 reviewer links)

```javascript
db.task_circulation_tokens.createIndex({ "token": 1 }, { unique: true });
db.task_circulation_tokens.createIndex({ "task_id": 1 });

// TTL on 14-day expiry (same caveat re: ISO string vs Date).
db.task_circulation_tokens.createIndex(
  { "expires_at": 1 },
  { expireAfterSeconds: 0 }
);
```

**Reasoning:** identical lookup pattern as contributor tokens; 14-day
window per F.4 trust model.

### `task_inbound_emails` (F.5 forensics)

```javascript
db.task_inbound_emails.createIndex({ "token": 1 });
db.task_inbound_emails.createIndex({ "parse_status": 1, "received_at": -1 });
db.task_inbound_emails.createIndex({ "task_id": 1, "received_at": -1 });
db.task_inbound_emails.createIndex({ "message_id": 1 });
```

**Reasoning:** forensic queries land here when an inbound email
fails to route (`parse_status: token_unknown_or_expired |
sender_mismatch`); operator dashboards filter by `parse_status`
and slice by `received_at`. The token index supports cross-
referencing a contributor's submission attempts.

### `task_intelligence` + `document_intelligence` (cache)

```javascript
db.task_intelligence.createIndex(
  { "task_id": 1, "task_hash": 1 }, { unique: true }
);
db.document_intelligence.createIndex(
  { "doc_id": 1, "doc_hash": 1 }, { unique: true }
);
```

**Reasoning:** intelligence cache is keyed by `(entity_id,
content_hash)` — every Intelligence-tab open does an upsert on this
pair. Unique guarantees idempotency and prevents the cache from
fragmenting.

### `documents` (task link + contributor provenance)

```javascript
// Doc → task link (F.3 Drafts tab + F.5 contributor docs).
db.documents.createIndex({ "task_id": 1, "state": 1 });

// Contributor docs lookup (used by F.5 reconciliation queries).
db.documents.createIndex({ "task_id": 1, "contributor_email": 1 });
```

**Reasoning:** the Task Drawer Drafts tab queries by
`(task_id, state="draft")`; contributor reconciliation queries by
`(task_id, contributor_email)`.

### `audit_log` (activity feeds)

```javascript
// Account-scoped task activity (F.6).
db.audit_log.createIndex(
  { "account_id": 1, "action": 1, "created_at": -1 }
);

// Context-scoped activity (pre-existing, used by Recent Activity).
db.audit_log.createIndex({ "context_id": 1, "created_at": -1 });
```

**Reasoning:** the F.6 RecentTaskActivityCard hits the account-
scoped index; the Work Studio Recent Activity panel hits the
context-scoped one. Both queries are bounded by `limit` so the
sort key is critical to keep latency flat as the audit log grows.

### `solva_briefing_state`

```javascript
db.solva_briefing_state.createIndex(
  { "user_id": 1, "area": 1 }, { unique: true }
);
```

**Reasoning:** per-user-per-area briefing dismissal state is read on
every Solva surface load. The unique index prevents drift from
concurrent dismissal POSTs.

### `solva_variant_seen` (D.2 cycle detection)

```javascript
db.solva_variant_seen.createIndex(
  { "user_id": 1, "question_key": 1, "seen_at": -1 }
);

// Plain question_key index supports the cross-user cycle-detection
// pass that audits "is this key cycling repeatedly?".
db.solva_variant_seen.createIndex({ "question_key": 1 });
```

**Reasoning:** the cycle-detection pass at session boundary reads
`(user_id, question_key)` for the current user, and the global key
emission audit reads `(question_key)` across users.

### `solva_key_emissions` (D.2 telemetry)

```javascript
db.solva_key_emissions.createIndex({ "question_key": 1 });
db.solva_key_emissions.createIndex({ "emitted_at": -1 });
```

**Reasoning:** admin time-window dashboards query by
`(emitted_at >= cutoff)` and group by `question_key`. Two
single-field indexes outperform a compound here because the
queries combine them with `$or` style filters.

### Apply procedure (post-deploy operator)

1. Connect to prod Mongo: `mongosh "$MONGO_URL"`.
2. `use <DB_NAME>;` (matches `DB_NAME` env var).
3. Paste each block above. All `createIndex` calls are idempotent —
   re-running is safe.
4. Verify: `db.<col>.getIndexes()` — confirm all listed indexes
   present.
5. For TTL indexes: if `expires_at` is stored as ISO string (current
   live schema), Mongo will NOT honor `expireAfterSeconds`. Convert
   the column to `Date` first OR add a parallel `expires_at_dt`
   field + repoint the index. Logged as a known gap below.

---

## Migration steps

- **Audit log:** legacy `cycle.*` events untouched. New `task.*`
  events flow naturally. **No migration needed.**
- **`cycles` collection** coexists with the new `tasks` collection.
  Per the F.1 borderline decision (logged in
  `AUTONOMOUS_DECISIONS_LOG.md`), the two are semantically distinct.
  **No rename.**
- **`documents.task_id`** is OPTIONAL. Existing docs without it
  remain valid. **No backfill needed.**
- **`documents.origin`** accepts new values but doesn't enforce them.
  Existing docs with `origin="upload"` etc. remain valid.
- **Side panel cards:** F.6 visual harmonization changes presentational
  classes only — no data shape changes.

---

## Known gaps surfaced honestly

| Gap | Status | Surfaced where |
| --- | --- | --- |
| Postmark inbound LIVE delivery | Requires deploy-time DNS + Postmark inbound stream config | This doc, F.5 section in HOME_CLEANUP_LOG |
| Embedding-based content similarity (Related-docs tab) | Out of batch envelope (would require new pip package + infra) | E.3 scope compliance section |
| Canonical lineage / explicit attachment relationship types | Out of batch envelope (data-model change with backfill) | E.3 scope compliance section |
| Multi-doc ACID commit transactions (F.4 Stage 5) | Motor client config doesn't expose them; we ship sequential commit + rollback | F.4 section, autonomous decisions log |
| ClamAV daemon STOPPED in preview pod | Existing constraint, not introduced by this batch | Project Health Check (pre-batch) |
| Stripe library in requirements.txt | Parked P3 | Pre-batch backlog |
| spaCy direct-URL refs in requirements.txt | Parked P3 | Pre-batch backlog |
| `test_real_requirements_file_is_clean` | Failing on the above two — parked P3 | Pre-batch backlog |
| Inline-comment span resolution (F.4 circulation + F.5 contributor) | General comments only ship; inline anchoring queued | F.4 + F.5 scope cuts |
| Email signature stripping is heuristic | No parser library added per "no new packages" envelope | F.5 autonomous decisions |
| LLM-voiced Recommendations may fall back to rule-based on Shield outage / timeout | Audit row `task.compile.llm.timeout` records frequency | F.3 + F.4 autonomous decisions |
| **G8 Board/Committee Pack** retained as full-page surface | Locked decision — drawer is primary, but the G8 full-page surface stays for this specific case | E.4 enumeration table |
| Token TTL indexes need `expires_at` as `Date` BSON type | Currently stored as ISO string; TTL won't fire until converted. Operator should convert at deploy-time OR add parallel `expires_at_dt` column. | Indexes section, apply procedure |

---

## Recommended deploy approach

1. **Tag:** `v-post-task-manager-rollout` (supersedes the deferred
   `v-post-home-cleanup` tag from earlier in this batch).
2. **Backend first:**
   - Roll backend with new env vars set (`POSTMARK_API_KEY`,
     `POSTMARK_WEBHOOK_SECRET`, `CYCLE_REPLY_DOMAIN`).
   - Verify `/api/health` returns 200.
   - Smoke test: `POST /api/tasks` with a draft → confirm row appears
     in the new `tasks` collection.
3. **Add Mongo indexes** (see list above). Run during a low-traffic
   window — most are `{ background: true }` safe but
   `task_*_tokens.token` unique index may need pre-flight dedupe if
   tokens already exist.
4. **Frontend deploy:**
   - Push the new bundle.
   - Verify Universal Document Drawer mounts on Work Studio.
   - Verify Universal Task Drawer mounts on Task Manager.
   - Verify `/contribute/<test-token>` renders as a public page.
5. **Postmark inbound stream:** configure DNS + webhook URL as
   documented above. Test with a real reply email; confirm
   `task.contribution.submitted_via_email` audit fires.
6. **24h watch window:**
   - Error rates < 0.5%.
   - Audit log volume on new event names (`task.compile.*`,
     `task.contributor.invited`) trending normally.
   - `task.compile.llm.timeout` frequency: < 5% of compile runs
     would be healthy; higher indicates Shield latency drift.
7. **Hold deploy of email-reply functionality** until Postmark
   inbound stream is confirmed live. Until then, magic-link
   contributors use the `/contribute/<token>` portal (Mode 2 works
   without Postmark inbound).

---

## Operator quick-reference cards

### "Tests aren't green"
- Check `/var/log/supervisor/backend.err.log` for tracebacks.
- `grep -rn 'from emergentintegrations' /app/backend/` should return empty.
- `python -c "from routers import tasks; print('OK')"` smoke-tests imports.

### "Postmark inbound isn't picking up email"
- Confirm MX records: `dig MX parse.akki.example.com`
- Postmark dashboard → Servers → Inbound → Activity tab shows raw delivery.
- Backend log: `tail -f /var/log/supervisor/backend.out.log | grep inbound`
- Look for `parse_status` in `db.task_inbound_emails` for forensics.

### "Magic link link won't open"
- Confirm `PUBLIC_BASE_URL` env var.
- Token might be expired (30-day window) — Re-invite from the
  Contributions tab to mint fresh.
- Confirm route is mounted BEFORE marketing routes in `App.js`.
