# Autonomous-mode Trip Report — UI-cleanup batch (Phases A → F.6)

**Period:** ~2026-05-26 across the rolling forked-context session.
**Mode:** Orchestrator delegated autonomous execution with the standing rule
*"Ensure scope compliance now, unless it compromises system or journey."*
**Final state:** Batch closed. Awaiting user deploy signal on return.

This report consolidates every phase, every test increment, every
autonomous decision, every scope cut, and the open backlog into a
single auditable artefact. Read top-to-bottom for a full trip
record; jump to **Before deploy** for the operator checklist.

---

## Phases closed

Each phase shipped a focused slice of the UI-cleanup batch. None
of the phases touched the AKKI product specs (`memory/AKKI_PRODUCT_SPEC.md`,
`memory/AKKI_ONBOARDING_SPEC.md`) — `git diff` against those returns empty.

| Phase | Theme | One-line summary |
| --- | --- | --- |
| **A** | Home 2 text-size harmonization | Right-rail cards re-typed to the canonical 12/10.5 px scale; overlines unified to `akki-overline` class. |
| **B** | Home 2 layout chrome | Section/header/footer pattern locked in on rail cards; "View more →" footer button standardized. |
| **C** | Solva briefing dismissal state | `solva_briefing_state` per `(user_id, area)` shipped; "Show me again" reset path live. |
| **D** | Chat surface chrome + audit pass | Chat header/composer chrome restyled; 54 wire+live tests; audit correction pass added 10 follow-up assertions. |
| **E** | Work Studio cleanup | Document-listing rationalization; ReadingView quarantined; routes consolidated. |
| **E.3** | Universal Document Drawer + scope compliance | Drawer pattern introduced; URL contract `?doc_id=<uuid>`; prompt-based edits + DRAFT watermark + Related-docs typing landed in the scope-compliance follow-up. |
| **E.4** | Legacy route enumeration & autonomous archive | All doc routes mapped; `ReadingView` archived; `App.js` rewired; 8 borderline routes preserved for user review. |
| **F.1** + **F.2** | Rename Cycle Manager → Task Manager; 3-tab listing + 4-step setup wizard | 20 wire+live tests; cycle-coexistence accepted (no rename of the underlying collection). |
| **F.3** | Universal Task Drawer (5 tabs) | Plan / Contributions / Drafts / Intelligence / Compile shipped; LLM blockers + gaps generation; `?task_id=` linked context. |
| **F.4** | 5-stage Compile flow | Drafting / Review / Circulation / Final Production / Commit orchestrator (`compile_service.py`) + 3-second LLM timeout in `intelligence_service.py` + compile services. |
| **F.5** | Contributor notification modes | 3 modes — akki_account · magic_link · email_reply. `contributor_invitation_service.py`, public `ContributorPortal` page, Postmark inbound webhook in `routers/inbound_email.py`. |
| **F.6** | Side-panel polish + batch close | FollowUpDraftsCard restyled to canonical chrome; new `RecentTaskActivityCard` + `TaskManagerActivity` page; account-scoped task-activity endpoint; DEPLOY_READINESS.md + this trip report. |

---

## Test count progression

Cumulative wire + live tests across the batch — every increment
verified GREEN before moving to the next phase. Pre-batch baseline
referenced for context; the batch additions are the right-hand
column.

| Phase | Phase tests | Cumulative batch tests | Delta |
| --- | ---: | ---: | ---: |
| Phase A | 12 | 12 | +12 |
| Phase B | 14 | 26 | +14 |
| Phase C | 12 | 38 | +12 |
| Phase D (core) | 54 | 92 | +54 |
| Phase D (audit correction) | 10 | 102 | +10 |
| Phase E | 18 | 120 | +18 |
| Phase E.3 | 23 | 143 | +23 |
| Phase E.3 (scope compliance) | 15 | 158 | +15 |
| Phase E.4 | 10 | 168 | +10 |
| Phase F.1 + F.2 | 20 | 188 | +20 |
| Phase F.3 | 24 | 212 | +24 |
| Phase F.4 | 24 | 236 | +24 |
| Phase F.5 | 20 | 256 | +20 |
| **Phase F.6** | **16** | **272** | **+16** |

**Final batch suite:** 272 wire + live tests, all GREEN.
**Pre-existing failure:** `test_real_requirements_file_is_clean`
remains parked per user direction (spaCy direct-URL refs + Stripe
SDK import). No new regressions introduced.

---

## Major features shipped (by surface)

### Task Manager (NEW surface — F.1 → F.6)

- 3-tab listing (Active / Awaiting input / Closed) with status pills,
  compile-session pill, "Needs your input" pill.
- 4-step Task Setup Wizard (objective → success criteria → output
  spec → team).
- Universal Task Drawer with 5 tabs (Plan / Contributions / Drafts /
  Intelligence / Compile), `?task_id=<uuid>` URL contract, drawer-
  stack pattern (`?task_id=X&doc_id=Y` mounts both).
- 5-stage Compile flow (Drafting → Review → Circulation → Final
  Production → Commit) with deterministic 3-second LLM fallback.
- 3 contributor notification modes (akki_account, magic_link,
  email_reply) with Postmark fan-out + inbound webhook.
- Right-rail polish (F.6) — CompilationReadinessSection +
  FollowUpDraftsCard + RecentTaskActivityCard all on canonical
  Home 2 chrome.
- Full-page activity view at `/app/task-manager/activity`.

### Work Studio + Universal Document Drawer (E + E.3 + E.4)

- Drawer pattern with `?doc_id=<uuid>` URL contract on every
  doc-listing surface (Work Studio, Workspace, Pulse, Cycle).
- Prompt-based edit-apply pipeline (`document.prompted_edit.proposed`
  audit event) + DRAFT watermark on exports + Related-docs typing.
- Legacy `ReadingView` archived; route enumeration documented in
  `PHASE_E4_*` artefacts.

### Solva (C + D)

- Per-account briefing dismissal state with "Show me again" path.
- 60-key question-bank routing + variant emission telemetry
  (`solva_variant_seen`, `solva_key_emissions`).

### Chat (D)

- Header/composer chrome restyled; PII shield contracts preserved.

### Postmark integration (F.4 + F.5)

- Transactional sends (circulation reviewer invites, contributor
  invites in all 3 modes).
- Inbound webhook with `task-<token>` MailboxHash routing for
  email-reply mode.

---

## Autonomous decisions

This section reproduces every autonomous-mode decision verbatim
from `/app/memory/sprints/AUTONOMOUS_DECISIONS_LOG.md` so the
trip report stands alone.

### 2026-05-26 — E.3 scope compliance authorized under autonomous mode

- **Trigger:** User delegated autonomous control with the standing rule
  *"Ensure scope compliance now, unless it compromises system or journey."*
- **Decision:** ship prompt-based edit-apply pipeline, DRAFT watermark
  on exports, and Related-docs typing in a single scope-compliance
  pass.
- **Rationale:** these were the 3 deferred E.3 scope items; closing
  them required no spec change, only implementation.
- **Reversal:** none needed — code-only delta with audit row coverage.

### 2026-05-26 — E.4 legacy route archive

- **Trigger:** dispatch listed 8 borderline routes (G8 Board Pack,
  legacy Cycle pages, deprecated reading views).
- **Decision:** ARCHIVE `ReadingView` (no live callers); RETAIN G8
  Board Pack as full-page surface; map all routes to drawer pattern
  where applicable.
- **Rationale:** G8 has a specific full-page need (board-pack
  rendering is page-level, not drawer-level).
- **Reversal:** `git revert` on the `App.js` edit + restore
  `ReadingView.jsx` from `_archived_coverage_loss/`.

### 2026-05-26 — F.1 cycles ↔ tasks coexistence

- **Trigger:** F.1 brief was "rename Cycle Manager to Task Manager".
- **Decision:** rename the FRONTEND surface + add a new `tasks`
  collection. The legacy `cycles` collection coexists; no data
  migration.
- **Rationale:** tasks are semantically distinct (success criteria,
  output spec, multi-stage compile, contributor modes). A rename
  would have buried the semantic shift.
- **Reversal:** the legacy `cycles` surface is no longer mounted in
  `App.js` but the collection + routes remain intact for any
  future review.

### 2026-05-26 — F.4 in-flight decisions

- **Sequential commit + best-effort rollback** (vs. multi-doc
  transactions): Motor/Mongo config doesn't expose ACID. Stage 5
  commits sequentially; failure audit row
  `task.compile.commit.failed` with `metadata.failed_doc` +
  `metadata.rolled_back`.
- **Send-fail keeps the magic link valid:** Postmark `send_email`
  errors persist the token + record `send_failed` on the per-
  reviewer status.
- **Public-endpoint auth model:** circulation reviewer endpoints
  take NO auth header — the URL-safe 32-byte token IS the credential.
- **3-second LLM timeout default** in intelligence + compile services
  with deterministic fallbacks; timeout audits via
  `task.compile.llm.timeout`.

### 2026-05-26 — F.5 in-flight decisions

- **Signature stripping heuristic vs. parser library:** no
  mailparser-style package added (no-new-packages envelope).
- **MailboxHash routing piggybacks** on existing
  `routers/inbound_email.py` webhook rather than a new file.
- **Sender authority via `From:` header:** `From` must match
  `token.contributor_email`; mismatches → `parse_status:
  sender_mismatch`.
- **Send-fail keeps the link** (F.4 continuation pattern).
- **`_notify_contributors` legacy stub** kept as no-op for any
  external callers.
- **ContributorPortal as a PUBLIC route** — no `<Gated>` wrapper;
  token is the credential.

### 2026-05-26 — F.6 completion authorized after context drift

- **Trigger:** new context window found partial F.6 work on disk
  (14/16 tests passing).
- **Decision:** complete F.6 rather than roll back.
- **Rationale:** work matches dispatched F.6 brief scope.
- **Reversal:** user can audit DEPLOY_READINESS.md + this report;
  either doc can be rewritten if direction is off.

---

## Spec/code deltas

| Layer | What changed | What didn't |
| --- | --- | --- |
| **Frontend pages** | NEW: `TaskManager.jsx`, `TaskManagerActivity.jsx`, `ContributorPortal.jsx`. EDITED: `App.js` route wiring, drawer-mount pages. | `Solva`, `Chat`, `WorkStudio` chrome adjusted but no shape changes. |
| **Frontend components** | NEW: `tasks/TaskDrawer.jsx`, `tasks/TaskListing.jsx`, `tasks/TaskSetupWizard.jsx`, `tasks/FollowUpDraftsCard.jsx`, `tasks/RecentTaskActivityCard.jsx`. | All Home 2 / Solva / Chat components retained their existing public API. |
| **Backend routers** | NEW: extensions in `routers/tasks.py` (~30 endpoints). EDITED: `routers/inbound_email.py` adds `task-<token>` branch. | All pre-existing routers untouched. |
| **Backend services** | NEW: `services/tasks/compile_service.py`, `services/tasks/intelligence_service.py`, `services/tasks/contributor_invitation_service.py`. | Shield client, `email_service`, audit log helpers untouched. |
| **Mongo collections** | NEW: `tasks`, `task_intelligence`, `task_circulation_tokens`, `task_contributor_tokens`, `task_inbound_emails`. | `cycles` collection untouched. |
| **Mongo schema additions** | `documents` gained `task_id`, `contributor_email`, `contributor_id`, `contributor_token`, `contributor_note`, `source`, `compile_session`. | All existing fields preserved; existing docs remain valid. |
| **Audit events** | NEW event prefixes: `task.*` (created, contributor.invited, contribution.*, compile.*.{started,completed,failed}, state.auto_closed, compile.llm.timeout, contribution.submitted_via_email). | All pre-existing `cycle.*` and `document.*` events untouched. |
| **Spec files** | `git diff memory/AKKI_PRODUCT_SPEC.md memory/AKKI_ONBOARDING_SPEC.md` → **empty**. | None. |
| **Dependencies** | `package.json` unchanged. `requirements.txt` unchanged. | (Parked: `spaCy` + Stripe SDK direct-URL refs flagged P3.) |

---

## Scope cuts (surfaced honestly)

Every cut was flagged at the time of the dispatch and is reproduced
here in one place so the operator can plan a follow-up batch.

| Cut | Where it lives | Notes |
| --- | --- | --- |
| Embedding-based content similarity (Related-docs tab) | E.3 scope-compliance section | Would require new pip package + infra. |
| Canonical lineage / explicit attachment relationship types | E.3 scope-compliance section | Data-model change with backfill. |
| Multi-doc ACID commit transactions (F.4 Stage 5) | F.4 autonomous decisions | Motor client config doesn't expose them; sequential commit + rollback ships instead. |
| Inline-comment span resolution (reviewer + contributor) | F.4 + F.5 scope cuts | General comments only ship today. |
| Email signature stripping accuracy | F.5 autonomous decisions | Heuristic regex; no parser library added. |
| Live Postmark inbound delivery verification | F.5 scope cuts | Requires production DNS + Postmark inbound stream config. |
| LLM-voiced Recommendations fallback to rule-based on Shield outage/timeout | F.3 + F.4 autonomous decisions | Visible via `task.compile.llm.timeout` audit. |
| Solva Question Bank lacks variants for 38/60 FAR-routable keys | Pre-batch backlog | Copywriter task in `question_bank.py`. |
| `spaCy` + Stripe SDK direct-URL refs in `requirements.txt` | Pre-batch backlog | `test_real_requirements_file_is_clean` failure parked P3. |

---

## Open backlog

Ordered by priority. The orchestrator should re-prioritize on
return.

### P0 (blocks deploy if not handled)

- **Postmark inbound stream configuration** at deploy-time
  (DNS + MX + webhook URL + `CYCLE_REPLY_DOMAIN` env var). Without
  this, F.5 Mode 3 (email-reply contributors) won't fire. Mode 1
  and Mode 2 work without it.

### P1 (post-deploy, soon)

- **Mongo indexes** from `DEPLOY_READINESS.md#indexes` need to be
  applied before traffic scales. None are required for correctness;
  all are required for latency.
- **TTL on token `expires_at`** — currently stored as ISO string;
  convert to `Date` BSON or add parallel `expires_at_dt` column.
  Without this, expired tokens accumulate (correctness intact).
- **24h watch window** — `task.compile.llm.timeout` frequency, error
  rates, audit-log volume sanity check.

### P2 (next batch)

- **Inline-comment span resolution** on circulation review + contributor portal.
- **Solva Question Bank content variants** for the 38/60 missing FAR keys.
- **Cycles collection retirement** — once tasks are confirmed
  exercising all use cases, evaluate retiring the legacy `cycles`
  collection + routes.

### P3 (parked)

- `spaCy` direct-URL refs cleanup in `requirements.txt`.
- Stripe SDK import audit (legacy unused import).
- `test_real_requirements_file_is_clean` will go green once the
  above two land.
- Embedding-based document similarity (requires new infra).

---

## Borderline routes (preserved for user review)

Surfaced during E.4 enumeration; held back from autonomous
archive for explicit user review on return.

| Route | Status | Reason held |
| --- | --- | --- |
| `/app/g8/board-pack` | RETAINED — full-page surface | Board-pack rendering is page-level, not drawer-level. |
| `/app/cycle/manager` (legacy) | Not mounted in `App.js` but code retained | F.1 chose coexistence over rename. |
| `/app/reading/:doc_id` | ARCHIVED — `_archived_coverage_loss/ReadingView.jsx` | No live callers; drawer covers the use case. |
| `/app/exco/teams` | RETAINED — distinct surface | Phase D audit pass confirmed live usage. |
| `/app/blog/admin/v2` | RETAINED — distinct admin surface | Phase D audit pass confirmed live usage. |
| `/app/decks/work-studio` | RETAINED — distinct authoring surface | Phase D audit pass confirmed live usage. |
| `/app/contribute/:token` | NEW (F.5) — public route | Mounted BEFORE marketing routes; no `<Gated>` wrapper. |
| `/app/task-manager/activity` | NEW (F.6) — full-page activity feed | Account-scoped equivalent of context-scoped activity. |

---

## Before deploy

The orchestrator's deploy-time checklist. Cross-reference with
`/app/memory/sprints/DEPLOY_READINESS.md` for the full operator
runbook.

### Confirm before issuing the deploy signal

1. **Pytest GREEN** end-to-end. Target: **272/272** in the
   `tests/test_home_cleanup_phase_*` + `test_phase_d_audit_correction`
   set. The pre-existing parked failure
   (`test_real_requirements_file_is_clean`) is NOT a regression.
2. **Postmark inbound stream** configured (DNS + webhook URL +
   `CYCLE_REPLY_DOMAIN`). If not yet configured, deploy backend
   + frontend but flag email-reply mode as "post-launch".
3. **All env vars set** in production:
   `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `EMERGENT_LLM_KEY`,
   `POSTMARK_API_KEY`, `POSTMARK_WEBHOOK_SECRET`,
   `CYCLE_REPLY_DOMAIN`, `PUBLIC_BASE_URL`, `RESEND_FROM_EMAIL`.
4. **Mongo indexes** applied per `DEPLOY_READINESS.md#indexes`. Not
   a correctness blocker but a latency blocker at scale.
5. **Smoke test plan**:
   - `POST /api/tasks` creates a task, audit row fires.
   - `/app/task-manager` lists the task.
   - `?task_id=<id>` opens the drawer.
   - `/contribute/<token>` renders as a public page (no auth gate).
   - One transactional Postmark send completes end-to-end.

### Items that need user attention BEFORE deploy

- **Verify the partial-F.6-found-on-disk autonomous decision** is
  acceptable in retrospect. Reversal path documented above.
- **Confirm the borderline-routes table** — anything to remount,
  re-archive, or rename?
- **Confirm Postmark inbound rollout sequencing** — deploy code
  now with inbound disabled, or hold for inbound stream config?
- **Tag name** for the batch close: proposal is
  `v-post-task-manager-rollout` (supersedes the earlier deferred
  `v-post-home-cleanup` tag).

### Items that need user attention AFTER deploy

- 24h watch window readings (timeout frequency, audit log volume).
- Decision on P2 backlog priority — particularly inline-comment
  spans + Solva content variants.
- Cycle collection retirement timeline.

---

**Batch status:** CLOSED. Awaiting user deploy signal.
