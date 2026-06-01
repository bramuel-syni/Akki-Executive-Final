# Phase P5.20 — Default-inbox cycle UX wizard scaffolding (2026-02)

## Headline

Closes the UX gap surfaced honestly in P5.19/P5.19.1: the
auto-scaffolded default-inbox cycle existed in Mongo but couldn't
render in the Cycle wizard ContributionsStep because it lacked the
seed agenda + team member rows that the wizard expects. Post-fix:

  • `get_or_create_default_inbox_cycle` seeds one agenda item
    ("Inbound from Email Akki") + one team member (the tenant's
    primary admin) atomically in the same call. Idempotent.
  • An idempotent backward-compat migration `backfill_default_inbox_cycles`
    seeds the same scaffolding onto any pre-P5.20 default-inbox
    cycle.
  • The `/cycle/agenda` endpoint surfaces `is_default_inbox_cycle: true`
    so the FE wizard auto-jumps to the Contributions step.
  • A small `📧 default inbox` badge renders next to the cycle title.
  • Every seeding action lands a `route_kind=default_cycle_seed`
    row in `inbox_routing_log` with `extra.seed_action` distinguishing
    `default_cycle_agenda` from `default_cycle_member`.

OAuth migration (P5.18) stays parked.

## Pre-step (also shipped) — DOM-selector trace pattern fix

Recurring over-match: `[data-testid^="pulse-card-"]` matched both
card root testids AND nested chip/sub-element testids. Logged
three times across P5.17 / P5.19 / P5.19.1 traces — closed now.

**Fix:** added `data-card-root="true"` to the SignalCard
`<article>` in `pages/Pulse.jsx` and to the TaskListing `<li>` in
`components/tasks/TaskListing.jsx`. Trace selectors switched to
`document.querySelectorAll('[data-card-root="true"]')` which is
exact-match. ≤ 30 LOC across the two component files + the trace.

**Proof (BEFORE vs AFTER on `/tmp/p5_19_1_pulse_trace.py`):**

| Step | Filter | BEFORE chips/cards | AFTER chips/cards |
|------|--------|--------------------|--------------------|
| (a) baseline | all | 7 / 28 | **7 / 7** ✓ |
| (c) filter narrow | email_akki | 7 / 28 | **7 / 7** ✓ |
| (d) filter exclude | manual | 0 / 0 | **0 / 0** ✓ |
| (e) filter restore | all | 7 / 28 | **7 / 7** ✓ |

No more 28-vs-7 ratio. Future traces use the same precise selector.

## What landed

### Backend

- `services/inbox_routing/context_resolver.py`:
  - **NEW** `_seed_default_cycle_agenda_and_member()` — pure
    helper, idempotent on `(cycle_id, is_default_inbox_item)` and
    `(cycle_id, account_id)`. Returns
    `{agenda_created: 0|1, member_created: 0|1}`.
  - `get_or_create_default_inbox_cycle()` — calls the seed helper
    on both create and existing-cycle paths. Backward-compat: an
    older default cycle missing the agenda/team gets seeded the
    first time the function is called against it.
  - **NEW** `_log_seed_audit()` — writes `default_cycle_seed`
    rows to `inbox_routing_log` with `extra.seed_action` =
    `"default_cycle_agenda"` or `"default_cycle_member"`. Only fires
    when the corresponding counter is non-zero (no audit noise
    on no-op re-runs).

- `services/inbox_routing/backfill.py`:
  - **NEW** `backfill_default_inbox_cycles(db)` — scans every
    `cycles` row with `is_default_inbox_cycle: true` and runs the
    seed helper; idempotent on both seeded and unseeded cycles.

- `services/inbox_routing/__init__.py`: exports
  `backfill_default_inbox_cycles`.

- `services/inbox_routing/backfill.py::run`: orchestrator
  includes the new backfill alongside tasks / signals /
  cycle_updates.

- `routers/cycle_manager.py::get_agenda`: response now carries
  `is_default_inbox_cycle: bool`. Backward-compat default `false`
  on any failure or missing cycle row.

### Frontend

- `pages/Cycle.jsx`:
  - Imports unchanged (chip + modal reused from P5.17/P5.19).
  - `agenda?.is_default_inbox_cycle` drives a small inline badge
    next to the h1 (`cycle-default-inbox-badge` testid).
  - One-shot auto-jump effect: when the loaded agenda's
    `is_default_inbox_cycle` is true AND no `?tab=` URL override
    is present AND we haven't auto-jumped this cycle yet, switch
    the step to `contributions`. Existing user cycles untouched.

### Tests — `tests/test_phase_p5_20_default_inbox_cycle.py` (8 tests)

  - New default-inbox cycle carries agenda + team seeds.
  - `get_or_create_default_inbox_cycle` idempotent on seeds (exactly
    one agenda item, exactly one team row).
  - Seed audit rows: 2 on first call, 0 on second (`# negative-leak:`).
  - `backfill_default_inbox_cycles` seeds pre-P5.20 cycles, idempotent
    on second run (`# negative-leak:` assertion on counters).
  - `/cycle/agenda` endpoint surfaces `is_default_inbox_cycle: true`
    for default cycles and `false` for user cycles.
  - Voice-lint clean on the seed copy + the strings locked
    (`"Inbound from Email Akki"`, `"Routed contributions from
    email arrive here for triage."`).
  - Source-strict P5.20 markers in `context_resolver.py`.

**Combined suite: 145/145 green in 100.24 s.**

## Discipline gates (verbatim)

- **v1 byte-identical guard:** `4 passed, 15 warnings in 3.41s`.
- **Voice-lint:** `voice_lint: clean across customer-copy surfaces.`
- **Migration idempotency proof (run twice):**
  ```
  === RUN 1 ===
  {'scanned': 41, 'agenda_seeded': 0, 'member_seeded': 0}
  === RUN 2 ===
  {'scanned': 41, 'agenda_seeded': 0, 'member_seeded': 0}
  IDEMPOTENT ✓
  ```
  (Both runs zero because prior P5.20 test runs already seeded
  every default-inbox cycle in the dev DB; the lockdown test
  `test_backfill_default_inbox_cycles_seeds_pre_p520_cycles`
  exercises the `created > 0` path against a fresh sibling-only
  seed and is green.)

## Live raw Playwright trace

`/tmp/p5_20_default_cycle_trace.py` (uses the FIXED selector
pattern from the pre-step) drove the live preview at
1280×800 / 1024×768 / 820×1180 / 414×896:

| Viewport   | URL ends            | badge | contrib row | origin chip | active tab                      | modal opened | modal.subject |
|------------|---------------------|-------|-------------|-------------|----------------------------------|--------------|---------------|
| 1280×800   | `&tab=contributions`| ✓     | ✓           | ✓           | `cycle-step-tab-contributions-active` | ✓        | `Cycle: P5.20 default inbox trace` |
| 1024×768   | `&tab=contributions`| ✓     | ✓           | ✓           | same                              | ✓            | same          |
| 820×1180   | `&tab=contributions`| ✓     | ✓           | ✓           | same                              | ✓            | same          |
| 414×896    | `&tab=contributions`| ✓     | ✓           | ✓           | same                              | ✓            | same          |

The trailing `&tab=contributions` on every URL proves the auto-jump
landed the user on the Contributions step without any user input —
the Agenda + Team wizard steps are correctly skipped. Badge text
verbatim: `✉ DEFAULT INBOX`. 8 JPEGs (cycle + modal × 4 viewports)
in `/tmp/p5_20_default_cycle/`.

## File-touch summary (P5.20 dispatch only)

**New:**
  - `backend/tests/test_phase_p5_20_default_inbox_cycle.py`
  - `memory/sprints/P5_20_default_inbox_cycle.md` (this file)
  - `tmp/p5_20_default_cycle_trace.py`

**Edit:**
  - `backend/services/inbox_routing/context_resolver.py` —
    `_seed_default_cycle_agenda_and_member` helper + `_log_seed_audit`
    + extended `get_or_create_default_inbox_cycle` (~180 LOC).
  - `backend/services/inbox_routing/backfill.py` —
    `backfill_default_inbox_cycles` (~25 LOC) + orchestrator entry.
  - `backend/services/inbox_routing/__init__.py` — exports update.
  - `backend/routers/cycle_manager.py::get_agenda` — surfaces
    `is_default_inbox_cycle` flag (~15 LOC).
  - `frontend/src/pages/Cycle.jsx` — badge + auto-jump effect
    (~25 LOC).
  - `frontend/src/pages/Pulse.jsx` — `data-card-root="true"`
    (pre-step, 1 line).
  - `frontend/src/components/tasks/TaskListing.jsx` —
    `data-card-root="true"` (pre-step, 1 line).
  - `tmp/p5_19_1_pulse_trace.py` — exact-match selector (pre-step).
  - `memory/PRD.md` — P5.20 row.

**Untouched:** Solva v1 + v2 · Ideas engine · workbook_analyzer ·
inbox_routing classifier engine · Task Manager adapter (P5.17) ·
Pulse Signals adapter (P5.19) · admin inbox surfaces.

## Deferred — absolute minimum

1. **Re-target row action on default-inbox-context badge** —
   carried from P5.19; still > 30 LOC of UI + endpoint work.
2. **OAuth migration** — P5.18, awaiting Google creds.
3. **AdminTopBar tile for source-view counts** — declined
   (P5.17 follow-up).
4. **Routing-log distribution chart on admin inbox modal** —
   declined per minimum-backlog (P5.19 follow-up).
5. **Honesty-protocol `git grep` pre-merge gate** — declined
   (P5.15.1 follow-up).
6. **LLM-shielded classifier flag flip** — env-flagged; out of
   v1 scope.

## HUMAN_REQUIRED

- Deploy preview → production. Carries P5.10–P5.17 + P5.19 +
  P5.19.1 + P5.20 in one ship (P5.18 deferred).
- No new env vars required.
- Backfill safe to run once in production via
  `python -m services.inbox_routing.backfill` — drains any
  pre-deploy P5.16 routing log rows AND seeds agenda/team on any
  pre-P5.20 default-inbox cycles. Idempotent.
