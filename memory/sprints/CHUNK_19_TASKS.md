# Chunk 19 — Track 5 final (Bank-QA polish + holistic product features doc)

Anchor: `POST_REWRITE_RAMP.md § Track 5`.

Status: PLANNING (dispatch pending). Items below collect everything the
orchestrator + dev have queued for the Bank-QA evidence pack assembly +
the closing-chunk polish.

## Items

### C19-001: Sample HMAC verification script (Python)
**Source**: `POST_REWRITE_RAMP.md` Track 5 row 4
**Surface**: NEW `/app/memory/sprints/phase_e_addendum_artefacts/verify_trust_receipt.py`
**Why**: Bank reviewers need a 30-line standalone script that takes a
saved trust-receipt JSON + the public key and verifies the HMAC chain.
**Size**: S (~30 LOC + a fixture receipt + a README snippet)

### C19-002: Architecture diagram (mermaid → PNG)
**Source**: `POST_REWRITE_RAMP.md` Track 5 row 5
**Surface**: NEW `/app/memory/sprints/phase_e_addendum_artefacts/architecture_diagram.{md,png}`
**Why**: Bank-QA wants a one-page system overview showing
SPA → API → Shield → LLM router → audit log + trust receipts.
**Size**: S (mermaid source + rendered PNG)

### C19-003: Screenshot pack collation
**Source**: `POST_REWRITE_RAMP.md` Track 5 row 6
**Surface**: collect partials from `/tmp/` into
`/app/memory/sprints/BANK_QA_EVIDENCE_PACK/screenshots/`
**Why**: Reviewers need annotated UI evidence for Observability + Billing
+ Monitor Update Goal + Privacy PDF surfaces.
**Size**: S

### C19-004: Holistic product features + functionality document
**Source**: `POST_REWRITE_RAMP.md` Chunk 19 placeholder
**Surface**: NEW `/app/memory/PRODUCT_FEATURES.md` (or update existing)
**Why**: Single canonical doc enumerating every shipped feature surface
with its anchor file + verbatim copy + governance gate. Pairs with the
phase closeouts as the "what's in the box" reference.
**Size**: M (will cite every shipped chunk + patch from SYSTEM_STATE.md
§ 4)

### C19-005: Admin cron-health endpoint
**Source**: Chunk 18 dev offer 2026-05-21
**Surface**: NEW `GET /api/admin/synisense/cron-health` reading
`scheduler_runs` collection (created in Chunk 18)
**Returns**: `[{job_id, last_run_at, status, duration_ms, summary,
hour_bucket}]` for each registered job. Order: most-recent run per
job_id. Empty list if no runs yet.
**Auth**: superadmin-only (existing `require_superadmin` dependency)
**Why**: Bank-QA reviewers expect evidence that scheduled work
actually runs (matches existing observability + audit pattern). Reuses
the heartbeat foundation laid in Chunk 18 — no new collections, no new
LLM call sites.
**Size**: S (~30 LOC)
**Risk**: LOW — read-only endpoint, existing collection
**Tests**: 1 contract (response shape + ordering) + 1 RBAC (non-admin
gets 403) + 1 empty-state (no runs → `[]`)

## Out of scope for Chunk 19

- Item 5 of Track 4 (Around-the-Goals) — AWAITING_PO; leave on the
  blocked queue.
- HA scheduler upgrade (Mongo-lock leader election for multi-replica)
  — only matters if the deployment topology changes; tracked as Future.
- The Phase 5 Quarantine pass (5 files) — separate sprint per
  `QUARANTINE_TRIAGE_PLAN.md`.

## Ordering preference

C19-005 first (cleanest end-to-end win, single endpoint + 3 tests),
then C19-001/-002/-003 in parallel (docs + diagrams), then C19-004
last (large enumeration doc that benefits from all earlier closeouts
being settled).
