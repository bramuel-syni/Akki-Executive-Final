# Phase P5.16 — Email Akki auto-routing (2026-02)

## Headline

Closes the **P8 "Email Akki" promise gap** surfaced by the P5.13
journey audit. Pre-P5.16, an inbound email landed in the admin
inbox as a static row; the only affordance was "Mark replied" or
"Dismiss". Post-P5.16, every inbox row carries a deterministic
classification (route_kind + confidence + cited rationale), the
high-confidence subset auto-routes into a tenant-scoped target
(task / cycle update / signal), and the admin can manually route,
re-classify, dismiss, or audit the routing log through the inbox
detail panel.

**v1 posture:** `INBOX_ROUTING_LLM_ENABLED=false`. The classifier
ships **deterministic-v1** — keyword + subject-prefix + sender-tier
heuristics — calibrated conservatively (high band requires multiple
converging signals). The shielded-LLM round-trip stays scaffolded
behind the env flag for a later validation cycle, exactly mirroring
the P5.15 pattern.

## What landed

### Backend — sibling package `services/inbox_routing/`

8 files, ~1 000 LOC total. **NOT** an extension of Solva v1/v2,
Ideas, or workbook_analyzer; sibling-clean.

- `__init__.py` — flat re-export surface.
- `schema.py` — Pydantic models: `ClassificationEnvelope`,
  `ClassificationCitation`, `TargetHint`, `InboxRoutingLogEntry`.
  Frozen vocabularies: `ROUTE_KINDS` (5 entries),
  `CONFIDENCE_BANDS` (3 entries).
- `refuse_to_decide.py` — pure re-export of the workbook_analyzer
  sibling. **Single source of truth** for narration safety
  semantics across Ideas + workbook + inbox-routing.
- `confidence.py` — `calibrate_band(score)` mapping
  `[0.0, 1.0] → {low, medium, high}` with locked thresholds
  (0.35 / 0.70). Calibration is NOT LLM-self-reported.
- `citation_resolver.py` — `InboxRoutingCitationResolver`,
  per-instance message_id cache, batch-aggregate failures into
  one `CitationUnverifiable`, same `citation_unverifiable:`
  prefix as Ideas + workbook_analyzer.
- `classifier.py` — `classify_message(message) → ClassificationEnvelope`.
  Deterministic-v1 path:
    1. Dispatcher-routing-result mirror table.
    2. Subject-prefix verb regex (`Task:`, `Cycle:`, `Signal:`,
       `Action required:`, …).
    3. Body-keyword density score per route-kind (winner-take-all).
    4. Sender-tier bump / penalty (known sender +0.15 / unknown −0.10).
    5. Length floor — bodies < 80 chars cap at 0.20.
    6. Tenant-absence demotion — `cycle_update` / `task_create`
       require `target_hint.account_id`; missing → demote to
       `discussion_only`.
  Every envelope carries ≥ 1 citation pointing back to the source
  message_id; the resolver re-verifies before return (defence-in-depth).
  Rationale validated by `validate_no_imperatives`; fallback to
  `safe_neutral_fallback()` if the template ever trips the validator.
- `routers.py` — per-route-kind dispatch functions, each idempotent
  on `(message_id, route_kind, account_id)` via Mongo `inbox_routing_log`
  precheck. Writes to lightweight collections:
    - `inbox_routing_tasks`         (route_to_task)
    - `inbox_routing_cycle_updates` (route_to_cycle_update)
    - `inbox_routing_signals`       (route_to_signal)
  `route_to_discussion` writes only the audit-log row (no target).
  Top-level `dispatch_route(envelope)` picks the right function.
- `audit_log.py` — `write_routing_log()` + `read_routing_log()` with
  tenant-scope arguments; endpoint enforces the cross-tenant guard.

### Backend — router extensions

- `routers/admin_inbox.py` — **4 new endpoints**, all superadmin +
  MFA + CSRF (state-changing) gated:
    - `POST /api/admin/inbox/messages/{id}/classify`
    - `POST /api/admin/inbox/messages/{id}/route`
    - `POST /api/admin/inbox/messages/{id}/dismiss`
    - `GET  /api/admin/inbox/messages/{id}/routing-log`
- `routers/inbound_email.py::_dispatch_inbound_payload` — added
  auto-classify hook AFTER `capture_for_admin_inbox`. Classifier
  runs synchronously within the request (deterministic-v1 latency
  < 50 ms). High-confidence non-unclassified envelopes auto-route
  in the same call; medium / low / unclassified land in the queue
  as suggestions only. Errors are swallowed (must not block
  dispatch — same contract as `capture_for_admin_inbox`).

### Frontend — `pages/admin/AdminInbox.jsx`

- Per-row route-kind chip (Task / Cycle / Signal / Discussion /
  Unclassified / Pending) tinted by confidence (high → emerald,
  medium → amber, low → slate).
- Detail panel `rationale` line above the body when the message
  has been classified.
- 6 routing affordances on the detail panel (P5.16 actions row):
    - **Classify** / **Re-classify**
    - **Route → Task** / **Route → Cycle** / **Route → Signal**
      (each disabled until the classifier resolves a tenant)
    - **Mark discussion only** (calls the dismiss endpoint)
    - **Routing log** (opens the modal)
- Routing-log modal showing every audit-log row with
  `route_kind · confidence · decision_source · rationale · target`.
- Every interactive element carries a `data-testid`.

### Tests — `tests/test_phase_p5_16_inbox_routing.py` (31 tests)

Confidence + vocabulary boundary tests (4); LLM env-flag tests (2);
classifier-direct tests across 6 fixtures (task / cycle / signal
prefixes; unknown sender; short body cap; no-signal); citation
resolver positive + 3 negatives + batch aggregate; per-route-kind
idempotency (4 — task / cycle / signal / unclassified dispatch);
`route_to_task` requires `account_id`; endpoint surface (5 —
classify happy path, classify 404, route happy path, dismiss
status flip, routing-log persisted rows, routing-log 404
existence-leak guard); non-admin 403 on classify + route;
tenant-scope on routing-log read helper (positive isolation +
negative-leak comment per P5.15.1 honesty protocol);
inbound-hook integration (real `_dispatch_inbound_payload` call →
admin_inbox row + classification persisted); voice-lint clean on
classifier source; CSRF allowlist invariant (`/api/admin/inbox`
NOT in the allowlist); source-strict P5.16 markers in router.

**Combined suite: 104/104 green in 88.54 s** (16 P5.15 ideas + 12
P5.15 scheduler + 4 v1 byte-identical + 41 P5.14 workbook analyze +
31 P5.16). Suite-size delta vs prior 73-pass baseline: **+31**.

## Discipline gates

- **v1 byte-identical guard:** 4/4 green (verbatim).
- **Voice-lint:** clean across customer-copy surfaces (verbatim).
- **CSRF:** `/api/admin/inbox` namespace NOT in the allowlist;
  every state-changing endpoint requires `X-CSRF-Token`. Locked
  by source-strict test.
- **Tenant isolation:** routing-log read helper rejects
  cross-tenant reads for non-superadmin callers. Positive-isolation
  assertion (caller's account_id is what the rows carry) AND
  negative-leak assertion (foreign tenant's rows excluded) — both
  with `# negative-leak:` comment per the P5.15.1 honesty addendum.
- **Refuse-to-decide:** validated on every classifier rationale
  before persistence; `safe_neutral_fallback()` covers the
  template-trips-validator edge case.
- **Idempotency:** every route function checks `inbox_routing_log`
  for a pre-existing `(message_id, route_kind, account_id)` row;
  re-run returns `status="exists"` with the existing target_id.
- **No piggybacking:** existing inbox list / detail / status / unread
  count endpoints untouched. Existing inbound dispatch paths
  (task_reply / cycle_reply / quarantine / context_doc) untouched.
- **No fake placeholder targets:** every routing row points at a
  real target row (or `target_kind=None` for unclassified / discussion).

## Live raw Playwright trace

`/tmp/p5_16_inbox_routing_trace.py` drove the live preview at
1280×800 / 1024×768 / 820×1180 / 414×896 with a fresh seeded inbox
row per viewport.

Live results per viewport (from `/tmp/p5_16_inbox/probe_results.json`):

| Viewport   | page_loaded | row in list | chip pre-classify | chip post-classify             | route→Task enabled | log modal opened | log rowCount | dismiss flips status |
|------------|-------------|-------------|-------------------|--------------------------------|--------------------|------------------|--------------|----------------------|
| 1280×800   | ✓           | ✓           | pending           | `inbox-routekind-chip-task_create` | ✓                  | ✓                | 1            | dismissed            |
| 1024×768   | ✓           | ✓           | pending           | `inbox-routekind-chip-task_create` | ✓                  | ✓                | 1            | dismissed            |
| 820×1180   | ✓           | ✓           | pending           | `inbox-routekind-chip-task_create` | ✓                  | ✓                | 1            | dismissed            |
| 414×896    | ✓           | ✓           | pending           | `inbox-routekind-chip-task_create` | ✓                  | ✓                | 1            | dismissed            |

Twelve JPEGs (3 states × 4 viewports + a log-modal capture for each
viewport) under `/tmp/p5_16_inbox/`. Full DOM dump under
`probe_results.json`.

## File-touch summary (P5.16 dispatch only)

New:
  - `backend/services/inbox_routing/__init__.py`
  - `backend/services/inbox_routing/schema.py`
  - `backend/services/inbox_routing/refuse_to_decide.py`
  - `backend/services/inbox_routing/confidence.py`
  - `backend/services/inbox_routing/citation_resolver.py`
  - `backend/services/inbox_routing/classifier.py`
  - `backend/services/inbox_routing/routers.py`
  - `backend/services/inbox_routing/audit_log.py`
  - `backend/tests/test_phase_p5_16_inbox_routing.py`
  - `memory/sprints/P5_16_email_akki_routing.md` (this file)
  - `tmp/p5_16_inbox_routing_trace.py`

Edit:
  - `backend/routers/admin_inbox.py` — 4 new endpoints + `_RouteIn`
    Pydantic model + `_load_message_or_404` helper. ~200 LOC append.
  - `backend/routers/inbound_email.py` — ~30 LOC auto-classify hook
    inside `_dispatch_inbound_payload` after the inbox capture.
  - `frontend/src/pages/admin/AdminInbox.jsx` — route-kind chip,
    detail rationale line, 6 P5.16 action buttons, routing-log modal,
    4 new component-local state hooks.
  - `memory/PRD.md` — P5.16 row.

Untouched (constraint check):
  - `backend/services/solva_v1/` — byte-identical guard 4/4 green.
  - `backend/services/solva_v2/` — unchanged.
  - `backend/services/ideas_engine/` — unchanged.
  - `backend/services/workbook_analyzer/` — unchanged.
  - Pulse / Monitor / Work Studio / Solva surfaces — unchanged.

## Deferred — absolute minimum

1. **LLM-shielded classification path** — scaffolded behind
   `INBOX_ROUTING_LLM_ENABLED=false`; flip in a separate cycle once
   we've audited the deterministic calibration on live admin-inbox
   traffic.
2. **Upstream task / cycle / signal integration** — current routing
   writes to lightweight sibling collections (`inbox_routing_tasks`,
   `inbox_routing_cycle_updates`, `inbox_routing_signals`). The
   Task Manager / Cohort Cycle / Pulse Signals widgets need a
   single read-side adapter to surface these as first-class rows;
   that's a 2-3 page edit deferred to P5.17.
3. **Background queue for classification** — sync within the
   request handler is fine for the deterministic path (< 50 ms).
   LLM mode would push to background.
4. **Multi-message threading / conversation linking** — out of
   scope; classify-per-message only.
5. **Attachment classification** — body + subject only in v1.
6. **Email reply-back from Akki to sender** — one-way ingest in v1.
7. **Honesty-protocol `git grep` pre-merge gate** — declined by
   user (P5.15.1 follow-up); revisit only if the inverted-assertion
   class of bug recurs.

## HUMAN_REQUIRED

- Deploy preview → production. Carries P5.10/P5.11/P5.12/P5.14/
  P5.14.1/P5.14.2/P5.15/P5.15.1/P5.16 in one ship.
- No new env vars required for the v1 posture
  (`INBOX_ROUTING_LLM_ENABLED` defaults to `false`).
- Postmark / SendGrid inbound webhook configuration unchanged —
  the auto-classify hook runs server-side inside the existing
  dispatch function.
