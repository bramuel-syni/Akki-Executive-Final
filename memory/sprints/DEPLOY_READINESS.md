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
| `POSTMARK_API_KEY` / `POSTMARK_SERVER_TOKEN` | Postmark transactional stream | `xxx-xxx-xxx`               | YES (F.5 contributor invites + F.4 circulation) |
| `POSTMARK_WEBHOOK_SECRET`  | HMAC verification of inbound webhook payloads | `<random 32+ bytes>` | YES (F.5 Mode 3) |
| `CYCLE_REPLY_DOMAIN`       | Parse domain for `task-<token>@…` reply-to addresses | `parse.akki.example.com` | YES (F.5 Mode 3) |
| `PUBLIC_BASE_URL`          | Canonical app origin used in magic-link URLs | `https://app.akki.example.com` | recommended |
| `RESEND_FROM_EMAIL`        | Transactional sender address (legacy var name) | `onboarding@akki.example.com` | YES |

### Frontend env vars

| Var | Purpose | Example | Required |
| --- | --- | --- | --- |
| `REACT_APP_BACKEND_URL`    | Backend base URL                | `https://app.akki.example.com` | YES — protected |

---

## Postmark setup

### Transactional stream (already required)

Required for: F.5 contributor invites (Mode 1 deep-link emails,
Mode 2 magic-link emails, Mode 3 reply-to-tagged emails), F.4
circulation reviewer invites, post-commit confirmations.

1. Verify the sending domain in Postmark.
2. `POSTMARK_API_KEY` env var set.
3. Test send from the backend:
   ```
   python -c "import asyncio; from email_service import send_email;
   print(asyncio.run(send_email(to='you@example.com', subject='test',
                                text='hello', html='<p>hello</p>')))"
   ```

### Inbound stream (NEW — required for F.5 Mode 3)

Required for: contributors who choose `email_reply` mode. They
reply to `task-<token>@<CYCLE_REPLY_DOMAIN>` and Postmark POSTs the
parsed message to our webhook.

1. **Create an Inbound Server** in the Postmark dashboard.
2. **Domain & MX records:** point a subdomain (e.g.,
   `parse.akki.example.com`) at Postmark's MX hosts.
3. **Webhook URL:**
   `https://<prod-host>/api/inbound/postmark?secret=$POSTMARK_WEBHOOK_SECRET`
4. **MailboxHash routing:** Postmark automatically captures the
   `+<hash>` portion of the recipient as `MailboxHash` in the
   webhook JSON. Our handler recognises the `task-<token>` prefix
   and dispatches to `_handle_task_contributor_reply`. No
   per-recipient config needed.
5. **Local mock test:** see `backend/tests/test_home_cleanup_phase_f5.py::
   test_f5_inbound_webhook_ingests_email_reply` for a curl-friendly
   payload shape.

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

## Recommended Mongo indexes

Hot-path queries observed during the batch — add these before
deploy to avoid full-collection scans:

```javascript
// Task listing (filter by state + sort by created_at desc)
db.tasks.createIndex({ "account_id": 1, "state": 1, "created_at": -1 });

// Task detail
db.tasks.createIndex({ "id": 1 }, { unique: true });

// Doc → task link (F.3 Drafts tab + F.5 contributor docs)
db.documents.createIndex({ "task_id": 1, "state": 1 });

// Account-scoped task activity (F.6)
db.audit_log.createIndex({ "account_id": 1, "action": 1, "created_at": -1 });

// Context-scoped activity (existing, used by Recent Activity)
db.audit_log.createIndex({ "context_id": 1, "created_at": -1 });

// Magic-link token lookups (F.4 + F.5)
db.task_circulation_tokens.createIndex({ "token": 1 }, { unique: true });
db.task_contributor_tokens.createIndex({ "token": 1 }, { unique: true });
db.task_contributor_tokens.createIndex({ "task_id": 1, "contributor_email": 1, "used": 1 });

// Intelligence cache hit
db.task_intelligence.createIndex({ "task_id": 1, "task_hash": 1 }, { unique: true });
db.document_intelligence.createIndex({ "doc_id": 1, "doc_hash": 1 }, { unique: true });

// Inbound email forensics
db.task_inbound_emails.createIndex({ "task_id": 1, "received_at": -1 });
db.task_inbound_emails.createIndex({ "message_id": 1 });

// Solva telemetry
db.solva_variant_seen.createIndex({ "user_id": 1, "question_key": 1, "seen_at": -1 });
```

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
