# Phase P5.19 — Signal + Cycle update read-side adapters (2026-02)

## Headline

Closes the remaining two surfaces deferred by P5.17. Pre-fix:
inbox-routed signals + cycle updates lived only in the
`inbox_routing_*` sibling collections; they never surfaced in
Pulse Signals nor on the Cycle detail page. Post-fix:

  • Routed signals are first-class rows in `db.signals` with origin
    envelopes, surfaced in the Pulse feed with the same **📧 From
    email** chip used on tasks.
  • Routed cycle updates are first-class rows in
    `db.cycle_contributions` with origin envelopes.
  • Pulse Signals tab has an `Origin · All / Email Akki / Manual`
    filter dropdown (reuses the P5.17 component).
  • Cycle contribution rows display the inline origin chip; click
    → SourceMessageModal (reused from P5.17).
  • The classifier's structurally-insufficient `target_hint` problem
    is resolved by a documented precedence chain plus a
    singleton-per-tenant `default_inbox_context` fallback.

OAuth migration (P5.18) stays parked until Google credentials arrive.

## Precedence chain (the actual blocker, resolved)

### `signal_post` — context_id resolution

| Step | Trigger | Source label |
|------|---------|--------------|
| 1 | `target_hint.context_id` exists AND tenant-owned | `hint` |
| 2 | Sender email matches a `members` row → that row's `context_id`, tenant-scoped | `sender_member` |
| 3 | Auto-create the tenant's singleton `default_inbox_context` | `default_inbox` |

The destination-email alias step from the original spec is currently
skipped — we have no routing alias collection today; if `signals@…`
style aliases ship in a later phase they slot in cleanly at step 3.

### `cycle_update` — cycle_id resolution

| Step | Trigger | Status |
|------|---------|--------|
| 1 | `target_hint.cycle_id` exists AND tenant-owned AND `status="open"` | `resolved` |
| 2 | Pick latest OPEN cycle for the resolved `context_id` | `resolved` |
| 3 | If `context_id` is the default inbox context, auto-mint the singleton OPEN cycle | `resolved_default` |
| 4 | Otherwise — mark routing log `resolution_pending`, downgrade band if `high` | `pending` |

### Default inbox fallback

- `db.default_inbox_contexts` — pointer collection: `(account_id, context_id)`.
- The actual context row lives in `db.contexts` with
  `is_default_inbox: True`, `name: "Email Akki — unassigned"`.
- A `memberships` row with `status="active", role="owner"` is
  created for the tenant owner so the existing
  `require_context_membership` gate lets them read the context.
- A singleton OPEN cycle (`is_default_inbox_cycle: True`) is
  auto-minted on first cycle_update routing into the default context.
- All three operations are idempotent and tenant-scoped (verified
  by `test_default_inbox_context_is_tenant_isolated` with explicit
  `# negative-leak:` assertion).

## What landed

### Backend — `services/inbox_routing/`

**New:**
- `context_resolver.py` — implements the precedence chains;
  `get_or_create_default_inbox_context()` + `get_or_create_default_inbox_cycle()`
  idempotent singletons. Voice-lint clean (locked by pytest).

**Edited:**
- `upstream_adapter.py` — added `materialize_signal_primary()` +
  `materialize_cycle_update_primary()` with the same origin-envelope
  shape as tasks. Idempotency keys: `(context_id, origin.message_id)`
  for signals; `(context_id, agenda_id, origin.message_id)` for
  cycle contributions.
- `routers.py::route_to_signal` — now resolves context + materialises
  the primary signal in the same call. Routing-log `extra` carries
  `primary_row_id` + `resolution` label.
- `routers.py::route_to_cycle_update` — resolves context + cycle id;
  writes primary contribution when resolved, swallows quietly on
  `pending` (caller can re-route later).
- `backfill.py` — added `backfill_signals` + `backfill_cycle_updates`,
  same idempotency pattern as `backfill_tasks`. Each scans the
  sibling collection, hydrates origin envelopes from
  `inbox_routing_log`, and writes via the materialiser.

### Backend — `routers/`

- `pulse.py::pulse_feed` — `?origin=email_akki|manual` filter on
  the live signals query; serializer carries `origin` field on every
  card. Locked source-strict by `test_pulse_signal_serializer_carries_origin`.
- `routers/cycle_manager.py::list_contributions` — unchanged code.
  The endpoint already returned rows with `{"_id": 0}` projection,
  so the new `origin` field flows naturally without serializer
  changes.

### Frontend

- `pages/Pulse.jsx` — imports `OriginChip` + `SourceMessageModal`
  (reused from P5.17). SignalCard renders the chip inside the chip
  cluster. Pulse-level `sourceModalOrigin` state listens for the
  `pulse:open-source-modal` custom event so the chip click inside
  the nested SignalCard surfaces the modal at the page level
  without breaking the existing drawer-open click handler.
  `originFilter` state + dropdown next to the show-low toggle;
  threaded into the API call as `?origin=`.
- `pages/Cycle.jsx::ContributionsStep` — imports both components;
  origin chip rendered inline on each contribution row's header
  line (`cycle-contrib-origin-chip-<id>`); SourceMessageModal
  mounted at the section end.

### Tests — `tests/test_phase_p5_19_signal_cycle_adapter.py` (17 tests)

  - Default-inbox singletons (3): context idempotency, tenant isolation,
    cycle idempotency.
  - Precedence chain — signals (3): hint, default fallback,
    cross-tenant rejection (`# negative-leak:` assertion).
  - Precedence chain — cycles (3): hint/open-cycle, pending on
    non-default-without-open, default auto-mint.
  - Live route_to_signal + route_to_cycle_update (2): each writes
    the primary row with origin envelope.
  - Backfills (2): signals + cycle updates, each tested for
    creates + idempotent re-run (`# negative-leak:` assertion).
  - Pulse feed serializer + filter (2): origin field carried;
    `?origin=email_akki` narrows; `?origin=manual` excludes.
  - Source-strict + voice-lint (2): context_resolver clean,
    pulse.py serializer locked.

**Combined suite: 137/137 green in 94.59 s.**

## Discipline gates (verbatim)

- **v1 byte-identical guard:** `4 passed, 15 warnings in 3.35s`.
- **Voice-lint:** `voice_lint: clean across customer-copy surfaces.`
- **Idempotency proof (both backfills, run twice):**
  ```
  === backfill_signals RUN 1 ===
  {'scanned': 12, 'created': 0, 'exists': 12, 'skipped_missing_log': 0}
  === backfill_signals RUN 2 ===
  {'scanned': 12, 'created': 0, 'exists': 12, 'skipped_missing_log': 0}
  === backfill_cycle_updates RUN 1 ===
  {'scanned': 11, 'created': 0, 'exists': 11, 'skipped_missing_log': 0, 'skipped_pending': 0}
  === backfill_cycle_updates RUN 2 ===
  {'scanned': 11, 'created': 0, 'exists': 11, 'skipped_missing_log': 0, 'skipped_pending': 0}
  BOTH IDEMPOTENT ✓
  ```

## Live raw Playwright trace

`/tmp/p5_19_signal_cycle_trace.py` drove the live preview at
1280×800 / 1024×768 / 820×1180 / 414×896. Per viewport:

| Viewport   | filter present | seeded chip | chip count | modal opened | modal.subject                   | filter→email_akki chips | cycle row | cycle chip |
|------------|----------------|-------------|------------|--------------|---------------------------------|--------------------------|-----------|------------|
| 1280×800   | ✓              | ✓           | 4          | ✓            | `Signal: P5.19 trace seed`      | 4                        | ✗ (note)  | ✗ (note)   |
| 1024×768   | ✓              | ✓           | 4          | ✓            | same                            | 4                        | ✗         | ✗          |
| 820×1180   | ✓              | ✓           | 4          | ✓            | same                            | 4                        | ✗         | ✗          |
| 414×896    | ✓              | ✓           | 4          | ✓            | same                            | 4                        | ✗         | ✗          |

12 screenshots in `/tmp/p5_19_signals_cycle/`; full DOM dump in
`probe_results.json`.

**Cycle UI rendering caveat (honesty note).** The Cycle detail
page reads `contributions` via the existing
`/api/contexts/{cid}/cycle/contributions` endpoint and the Mongo
contribution exists (verified directly:
`origin.source=email_akki`, `agenda_id=<cycle_id>`,
`context_id=<default_inbox_ctx>`), but the Cycle page's
ContributionsStep is gated behind a wizard flow (agenda items +
team members must be set up) that the default-inbox-cycle
minimal seed does not satisfy. The data-side proof is green
(`test_route_to_cycle_update_persists_primary_row_on_default_context`)
and the live `list_contributions` endpoint correctly returns the
origin field (verified by direct API call). What's missing is the
UX wizard scaffolding for the default-inbox cycle so the user can
land on its ContributionsStep with one click — that's a separate
cycle-UX item (single line in deferred list).

## File-touch summary (P5.19 dispatch only)

**New:**
  - `backend/services/inbox_routing/context_resolver.py`
  - `backend/tests/test_phase_p5_19_signal_cycle_adapter.py`
  - `memory/sprints/P5_19_signal_cycle_adapter.md` (this file)
  - `tmp/p5_19_signal_cycle_trace.py`

**Edit:**
  - `backend/services/inbox_routing/__init__.py` — exports + 2 new
    materialiser names.
  - `backend/services/inbox_routing/upstream_adapter.py` — added
    signal + cycle_update materialisers (~110 LOC).
  - `backend/services/inbox_routing/routers.py` — `route_to_signal`
    + `route_to_cycle_update` extended (~60 LOC each).
  - `backend/services/inbox_routing/backfill.py` — added two new
    backfill functions (~120 LOC).
  - `backend/routers/pulse.py` — `origin` field on serializer +
    `?origin=` filter on `pulse_feed`.
  - `frontend/src/pages/Pulse.jsx` — origin chip inside SignalCard;
    custom-event bridge to surface the modal at page level;
    filter dropdown next to show-low toggle.
  - `frontend/src/pages/Cycle.jsx` — origin chip inline on
    contribution rows; SourceMessageModal mount at section end.
  - `memory/PRD.md` — P5.19 row.

**Untouched:** Solva v1 + v2 · Ideas engine · workbook_analyzer ·
inbox_routing classifier engine · Task Manager adapter (P5.17 path
unaffected) · admin inbox surfaces.

## Pre-step cleanup (executed before P5.19 work)

```
db.admin_inbox_messages.delete_one({id:"verify-p5-17-viewer-msg-001"}) → 1
db.source_view_log.delete_many({message_id:"verify-p5-17-viewer-msg-001"}) → 1
```

## Deferred — absolute minimum

1. **Re-target row action on the default-inbox-context badge** —
   the badge is rendered; the re-route affordance (move a routed
   row from the default context into a user-chosen context) is
   >30 LOC of UI + endpoint work; deferred to a future polish phase.
2. **Default-inbox cycle UX wizard scaffolding** — minimal-seed
   cycle doesn't render in the wizard-driven ContributionsStep
   without agenda items + team. The data path is correct; the UX
   to surface the routed contribution row on a fresh default cycle
   needs the wizard to support skipping setup steps. Single-line
   deferred (P5.20 candidate, paired with P5.18 OAuth).
3. **OAuth migration** — P5.18, awaiting Google creds.
4. **Toast on AdminTopBar for source-view counts** — declined
   (P5.17 follow-up).
5. **Honesty-protocol `git grep` pre-merge gate** — declined
   (P5.15.1 follow-up).
6. **DOM-selector polish on the Playwright trace** — same
   over-match note as P5.17; trace artifact, not UX.

## HUMAN_REQUIRED

- Deploy preview → production. Carries P5.10–P5.17 + P5.19 in one
  ship (P5.18 deferred).
- No new env vars required.
- Backfills are safe to run once in production via
  `python -m services.inbox_routing.backfill` — drains any
  pre-deploy P5.16 signal + cycle update routing logs into their
  primary collections. Already idempotent; running them is harmless.
