# Phase P5.15 — Pulse · Ideas by Akki (2026-02)

## Headline

Second master tab on Pulse. Weekly cited synthesis across 4 lenses
(Strategy / Board navigation / Capital / Governance), per-tenant
personalisation, refuse-to-decide-validated narration, real-corpus
citations only, cron-driven idempotent generation. **`IDEAS_LLM_ENABLED=false`**
ships as the v1 default — deterministic synthesis from the indexed
corpus is the v1 path. The shielded-LLM round-trip stays scaffolded
behind the env flag for a later validation cycle.

## What landed

### Backend

- **`services/ideas_engine/`** (sibling package; **NOT** an extension of Solva v1/v2):
  - `schema.py` — Pydantic models: `IdeaCard`, `IdeaCitation`,
    `IdeasDigest`, `UserIdeasPreferences`; `IDEA_LENSES` literal
    tuple; `ConfidenceBand` low/medium/high.
  - `synthesizer.py` — `synthesize_digest()` async; per-lens
    round-robin chunk selection; coverage-calibrated confidence
    bands (NOT LLM-self-reported); 2-retry-then-drop per lens;
    `week_iso_for()` ISO 8601 year-week formatter.
  - `citation_resolver.py` — `IdeasCitationResolver` async, with
    per-instance `document_id` cache; `verify_many()` aggregates
    failures into one `CitationUnverifiable` for upstream
    diagnostic. Same `citation_unverifiable:` prefix as the
    workbook_analyzer sibling.
  - `refuse_to_decide.py` — pure import-and-re-export of the
    workbook_analyzer sibling's regex set. **Single source of
    truth** for narration safety semantics.
  - `personalizer.py` — `build_personalization_block()`; lens
    list + GUARDRAILS section + user's `custom_instructions`
    (sanitised + 2000-char cap). The block is voice-lint clean
    by construction; the user's verbatim instructions are NOT
    voice-lint-checked (they're user-authored).
  - `preferences.py` — `(account_id, user_id)` keyed CRUD on
    `user_ideas_preferences`. Empty / all-invalid lens write →
    fallback to all-enabled (never silently empty).
  - `scheduler.py` — `sweep_account()` + `run_weekly_ideas_sweep()`;
    `(account_id, week_iso, digest_version)` idempotency check;
    dormant-tenant skip (no recent corpus → `status="skipped_no_corpus"`,
    no Mongo row written); `is_scheduler_disabled()` env override.

- **`routers/ideas.py`** — 6 endpoints, all CSRF-protected,
  tenant-scoped on `account_id`:
  - `GET  /api/ideas/digest/current`            (lazy-generates if absent)
  - `GET  /api/ideas/digest/{week_iso}`         (historical; validates `<YYYY>-W<NN>`)
  - `GET  /api/ideas/digest/history?limit=12`   (most recent N weeks)
  - `GET  /api/ideas/preferences`               (defaults if absent)
  - `PUT  /api/ideas/preferences`               (upsert; lens subset enforced)
  - `POST /api/ideas/digest/regenerate`         (admin-only force-regenerate)
  Cross-tenant access lands on 404 (no existence leak).

- **`server.py` cron wiring** — Monday 07:00 UTC `ideas_weekly_sweep`
  job armed alongside the existing 5 jobs. Env override
  `IDEAS_SCHEDULER_DISABLED=true` keeps the cron from arming at
  startup; the router lazy-path remains active.

### Frontend

- **`/app/frontend/src/components/pulse/PulseMasterTabs.jsx`** —
  two-pill switcher (SIGNALS · IDEAS BY AKKI). Active pill derived
  from `useLocation().pathname`. Rendered at the top of both
  `Pulse.jsx` (Signals) and `PulseIdeas.jsx`.

- **`/app/frontend/src/pages/PulseIdeas.jsx`** —
  - 4-column grid at `lg`, 2×2 at `md`, single column at mobile.
  - Per-card chip cluster: lens glyph + label + confidence band.
  - Citation drawer: list of all `IdeaCitation`s for the clicked card.
  - Preferences drawer: 2000-char textarea + 4 lens checkboxes.
  - Week selector: history dropdown with the last 12 weeks.
  - Empty-state surface (`pulse-ideas-empty`) when the synthesizer
    returns zero cards (`dropped_lenses` carries all 4).
  - Dropped-lens caveat row (`pulse-ideas-caveat`) when 1-3 cards
    return but at least one lens failed.
  - Every interactive element carries a `data-testid`.

- **`/app/frontend/src/App.js`** — `/app/pulse/ideas` route wired
  inside the `<Gated>` boundary.

### Tests (27 new / 0 retired)

`tests/test_phase_p5_15_ideas_by_akki.py` — **16 tests**:
  - `week_iso_for()` canonical format + isoyear boundary.
  - Personalizer: guardrail-when-empty · injection · sanitisation
    of control chars · 2000-char cap · imperative-in-instructions
    cannot bypass the validator.
  - Refuse-to-decide: positive + directive-rejection sanity.
  - Citation resolver: positive · fabricated-chunk · cross-tenant
    document · batch-aggregate failures.
  - Synthesizer: full 4-card on seeded corpus (resolved + voice-lint
    validated) · empty-corpus → all 4 dropped · subset-of-lenses
    honoured.
  - Preferences CRUD: defaults · upsert round-trip · empty-lenses fallback.
  - Endpoint: lazy-generate current digest · GET + PUT preferences
    · tenant-isolation specific-week 404 · non-admin regenerate 403
    · admin regenerate 200.
  - CSRF: `/api/ideas` namespace NOT in allowlist (source-strict).
  - Voice-lint: lens-lead templates + confidence rationale clean.

`tests/test_phase_p5_15_ideas_scheduler.py` — **11 tests**:
  - `sweep_account`: generates on present corpus · idempotent on
    double-run (1 row, `status="exists"` second time) · skips
    dormant tenant · skips stale corpus outside `DEFAULT_ACTIVE_WINDOW_DAYS`
    · honours explicit `week_iso` override.
  - `run_weekly_ideas_sweep`: end-to-end aggregate counters across
    multiple tenants; Mongo ground-truth assertion (sample list is
    capped at 50; dev Mongo has 23 500+ accounts).
  - `is_scheduler_disabled` env override default + true paths.
  - `week_iso_for` round-trip with leading-zero padded week.
  - Source-strict: server.py wires Monday-07:00 UTC `ideas_weekly_sweep`.
  - Voice-lint: scheduler source clean across banned vocabulary.
  - Audit-log marker `"trigger": "scheduler_weekly"` distinguishes
    cron-warmed rows from lazy-on-GET rows.

**Combined sweep: 42/42 green** (16 Ideas + 11 Scheduler + 4 v1
byte-identical + 11 P5.14.2 hotfix in the same run).

## Discipline gates

- **v1 byte-identical guard:** 4/4 green.
- **Voice-lint:** clean across customer-copy surfaces.
- **CSRF:** `/api/ideas` namespace NOT in the allowlist; every
  state-changing endpoint requires `X-CSRF-Token`. Locked by
  source-strict test.
- **Tenant isolation:** explicit cross-account 404 test
  (`test_tenant_isolation_specific_week_returns_404`); resolver
  rejects cross-tenant document references with
  `citation_unverifiable:`.
- **Refuse-to-decide:** every card body + title validated before
  persistence; the only narration that lands on the wire is one
  the regex set accepted.
- **No piggybacking:** Pulse Signals surface (`Pulse.jsx`) only
  gained one import + one element (`<PulseMasterTabs />`); no
  other code drift.
- **No fake placeholder cards:** empty-corpus → polite empty-state
  copy; dropped-lens → caveat row; loading → loading text. No
  ghost card ever rendered.

## Live raw Playwright trace (`/tmp/p5_15_ideas_trace.py`)

Drove the live preview UI at 1280×800 / 1024×768 / 820×1180 /
414×896. Seeded admin's corpus + reset Ideas preferences to all
4 lenses + force-regenerated via the admin-only endpoint. Sample
digest (`/tmp/p5_15_ideas/sample_digest.json`):

```
week_iso:       2026-W23
digest_version: p5.15.0
model_id:       deterministic-v1
citation_count: 8
refuse_to_decide:  pass 4 / fail 0
dropped_lenses: []

[strategy]          band=low  citations=2  title="Strategy — patterns surfacing this week"
[board_navigation]  band=low  citations=2  title="Board navigation — questions to pre-empt"
[capital]           band=low  citations=2  title="Capital — posture observations"
[governance]        band=low  citations=2  title="Governance — items worth a closer look"
```

(Bands read "low" because the round-robin chunk picker uses 1-2
unique documents per lens out of the 5 seeded; the calibration is
deliberately conservative when corpus breadth is thin.)

Live results per viewport (from `/tmp/p5_15_ideas/probe_results.json`):

| Viewport   | SIGNALS active | IDEAS-after-click | cards | citations drawer | prefs save | admin regen |
|------------|----------------|-------------------|-------|------------------|------------|-------------|
| 1280×800   | ✓              | ✓                 | 4     | ✓ (2 items)      | ✓          | 200         |
| 1024×768   | ✓              | ✓                 | 3*    | ✓                | ✓          | 200         |
| 820×1180   | ✓              | ✓                 | 4     | ✓                | ✓          | 200         |
| 414×896    | ✓              | ✓                 | 3*    | ✓                | ✓          | 200         |

\* Card count flips 4 → 3 → 4 → 3 between viewports because each
viewport's preferences toggle (`capital` on/off) ACTUALLY round-trips
through `PUT /api/ideas/preferences` → admin regenerate → digest
re-render. The transition is the live preferences→regeneration
proof, not a flake.

Screenshots: `/tmp/p5_15_ideas/ideas_<vp>_{loaded|citations|post_regen}.jpg`
plus `pulse_signals_<vp>.jpg` for the SIGNALS-active pill state.
17 JPEGs in total.

## Empty-state coverage

Not exercised in the live Playwright trace (admin has corpus); the
empty path is locked by two pytest:
  - `test_synthesizer_returns_empty_digest_when_no_corpus` — engine path.
  - `sweep_account` skips dormant tenants with
    `status="skipped_no_corpus"` and writes ZERO Mongo rows.

The UI `pulse-ideas-empty` testid renders when
`!loading && (!digest || digest.cards.length === 0)`. A future
trace can flip this by deleting admin's documents before the trace
runs.

## Files touched

- New: `backend/services/ideas_engine/{__init__.py,schema.py,synthesizer.py,personalizer.py,citation_resolver.py,refuse_to_decide.py,preferences.py,scheduler.py}` (8 files, ~750 LOC total).
- New: `backend/routers/ideas.py` (~215 LOC).
- New: `frontend/src/components/pulse/PulseMasterTabs.jsx` (~50 LOC).
- New: `frontend/src/pages/PulseIdeas.jsx` (~340 LOC).
- Edit: `backend/server.py` — `+` 3-line import block + ~30-line APScheduler entry.
- Edit: `frontend/src/App.js` — `+` 1 lazy import + 1 route.
- Edit: `frontend/src/pages/Pulse.jsx` — `+` `<PulseMasterTabs />` mount.
- New: `backend/tests/test_phase_p5_15_ideas_by_akki.py` (~500 LOC, 16 tests).
- New: `backend/tests/test_phase_p5_15_ideas_scheduler.py` (~230 LOC, 11 tests).
- New: `tmp/p5_15_ideas_trace.py` (raw Playwright; not committed).
- New: `memory/sprints/P5_15_ideas_by_akki.md` (this file).

Untouched (constraint check):
  - `backend/services/solva_v1/` — byte-identical guard 4/4 green.
  - `backend/services/solva_v2/` — schemas + reasoning unchanged.
  - `backend/services/workbook_analyzer/refuse_to_decide.py` —
    re-exported, not duplicated.
  - Pulse Signals UI logic (filter strip, lifecycle tabs, drawer,
    across-boards panel) — only the master-tab mount added.

## Deferred — absolute minimum

1. **LLM-shielded synthesis live wire** — scaffold present
   (`_llm_mode_enabled()` in `synthesizer.py`); enabling means a
   `services.solva_v2.llm_adapter.shielded_call` round-trip with
   the same refuse-to-decide + citation-verify pipeline applied
   to the LLM output. Out of v1 scope per user lock; flip
   `IDEAS_LLM_ENABLED=true` for the next validation cycle.

2. **HA-safe scheduler** — current cron is in-process APScheduler
   (matches `chat_retention_daily`, `cohort_expiry_reminder_daily`).
   The Mongo-lock pattern from `services.synisense.engine.scheduler_lock`
   is the multi-replica upgrade path when Ideas crosses that
   horizon.

3. **Daily / biweekly cadence** — out of scope; weekly only,
   `cadence` field on `UserIdeasPreferences` reserved as a
   literal `"weekly"` for now.

4. **"Why didn't this idea appear last week?" diff view** — backlog;
   not in v1.

5. **Tiny future polish** — Solva landing inline "Recently used"
   row (the post-compact-landing follow-up; user declined inline).

## HUMAN_REQUIRED

- Deploy preview → production. Carries P5.10/P5.11/P5.12/P5.14/P5.14.1/P5.14.2/P5.15
  in one ship. No new env vars are required for P5.15 (the
  optional `IDEAS_SCHEDULER_DISABLED` and `IDEAS_LLM_ENABLED`
  default-false; both unset is the v1 production posture).
- (Optional, post-deploy) backfill historical weeks by calling
  the admin regenerate endpoint with a `?week_iso=` override if
  the executive cohort wants prior-week snapshots in the history
  dropdown. Lazy-on-GET also fills this in over time.
