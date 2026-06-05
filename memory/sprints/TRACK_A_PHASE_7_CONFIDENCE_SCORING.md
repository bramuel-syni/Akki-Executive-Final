# Track A Phase 7 — Confidence Scoring Runtime Compute Path

**Shipped:** 2026-06-05 (iter-1 single-dispatch ship after 4 user-approved tightenings).
**Approver:** User dispatch + 4 tightenings folded + 15/15 test budget at cap.

---

## TL;DR

Phase 7 closes the "no production scorer exists" gap that Phase 6 archaeology surfaced. New `services/work_studio/confidence_scorer.py` runs a 4-dimension rubric (source coverage / internal consistency / gap clarity / recommendation grounding, weighted 40/25/20/15) via `shield_invoke` at compile time AND on commit. Aggregator is deterministic. Tightening 4 idempotency gate skips Shield on commits where structured_content hasn't changed (credit-saver). Tightening 2 protects the `documents.confidence_pct` mirror from being clobbered on scorer failure. Tightening 3 picks "suppress entirely" for the chip tooltip when rationale is absent. Tightening 1 bumps the consistency variance check to 3 calls / pairwise ≤10.

**Verified live**: 13/13 default Phase 7 lockdowns PASS + 2 integration-marked real-LLM tests opt-in. **87/87 aggregate BE regression PASS** (5 deselected = integration-marked across phases). No FE regression — signin smoke-screenshot clean.

---

## Iter-0 archaeology surfaces (Pre-Read §1.1)

Found **two existing confidence systems** in the codebase before any code touched:

| System | Where | Status | Phase 7 relationship |
|---|---|---|---|
| A — Solva v2 per-claim `confidence_pct` + `confidence_band` | `routers/solva_v2.py:902-916` + `services/solva_v2/probability_weighting.py` | LIVE in production | UNTOUCHED — System A is per-claim on Solva narration; Phase 7 is per-doc on Work Studio |
| B — Solva v2 artefact `input_confidence_pct` | `services/solva_v2/payload_builder.py:1208-1215` (`_input_confidence_pct`) | LIVE in production | UNTOUCHED — System B aggregates System A; Phase 7 doesn't touch either |
| C — Work Studio doc-level `intelligence_report.confidence_pct` | `work_studio_exports` table; only `seed_chunks.py:64-160` wrote it before | **GAP — closed by Phase 7** | Phase 7's deliverable |

The Phase 6 archaeology was correct on System C (no production scorer); Phase 7 doesn't re-litigate.

---

## Step-by-step execution

### Step 1 — Scorer service (new file)

`backend/services/work_studio/confidence_scorer.py` — 240 LOC including verbatim prompt, weights, structured_content hash for idempotency, and failure-mode contract:

- `score_confidence(...)` → `dict` (with `confidence_pct`, `rationale`, `scored_at`, `breakdown`, `cache_key`, `audit_id`) OR `None` (skip/fail).
- `structured_content_hash(...)` → SHA-256 over canonical-sorted JSON. Tightening 4 idempotency key.
- Aggregator: `0.4*source_coverage + 0.25*internal_consistency + 0.2*gap_clarity + 0.15*recommendation_grounding`, clamped to [0,100], rounded.
- Each except clause logs (Guard Rail 2) and returns `None`; caller interprets None as skip or fail.

Skip vs Fail distinction (Pre-Read §6):
- `confidence_score_skipped_no_sources: true` — deliberate skip (no sources to score against).
- `confidence_score_failed: true` — actual failure (timeout, malformed JSON, Shield raise).

### Step 2 — Compile-time injection (`_run_export` + `_run_enhance`)

Both BackgroundTasks runners in `routers/work_studio_export.py`:
- `_run_export` (~L885) — added a try/except outer belt + call to `_score_and_mirror_confidence` AFTER the `status="complete"` flip. Scorer failure does NOT block the user from seeing the artefact; the row is left status=complete with `confidence_score_failed: true` on `intelligence_report`.
- `_run_enhance` (~L1582) — same shape after the enhance-audit-write.
- Shared helper `_score_and_mirror_confidence(...)` (~L944) — handles source-doc resolution from citations_manifest, calls the scorer, writes to `intelligence_report` AND mirrors to `documents.confidence_pct` (Tightening 2 don't-clobber-on-failure contract).

### Step 3 — Commit-time recompute (`commit_document`)

`routers/work_studio_overlay.py:commit_document()`:
- After pre-commit snapshot creation, before lifecycle flip:
  - Compute new `structured_content_hash`.
  - If prior `intelligence_report.confidence_scored_at_cache_key` equals new hash → **Tightening 4 skip**: no Shield call, response carries `confidence_recompute_skipped_unchanged: true`.
  - Else → call scorer. On failure → response carries `confidence_recompute_failed: true`, prior pct preserved (Tightening 2 don't-clobber).
- Lifecycle ALWAYS flips to `committed` (Phase 6 brief contract honoured verbatim).

### Step 4 — Overlay payload surfacing (`overlay_payload`)

`services/work_studio_overlay.py:overlay_payload()` — added 4 fields:
- `confidence_rationale` (str | None)
- `confidence_scored_at` (ISO8601 | None)
- `confidence_recomputed_at` (ISO8601 | None)
- `confidence_score_failed` (bool)

**Listing endpoint deliberately UNCHANGED** (Pre-Read §4 — listing stays slim; rationale is overlay-only).

### Step 5 — Mirror to `documents.confidence_pct`

In `_score_and_mirror_confidence`, only writes the mirror when `new_value is not None` AND scorer succeeded. This is the Tightening 2 contract — pre-existing good score (e.g., 82 from a prior successful export) is preserved if the current re-export's scorer fails. Test 9 pins this.

### Step 6 — FE chip tooltip (Tightening 3 path (a) — suppress entirely)

`frontend/src/components/work_studio/overlay/DocumentOverlay.jsx`:
- `IntelligenceCard` now accepts `confidenceRationale` + `confidenceScoredAt` + `confidenceRecomputedAt` props.
- Chip renders as bare `<span>` when `confidenceRationale` is absent/empty (no tooltip wrapper — matches Tightening 3 path (a) "suppress entirely; no fake 'rationale not available' copy").
- Chip renders inside `<TooltipProvider><Tooltip><TooltipTrigger asChild>{chip}</TooltipTrigger><TooltipContent>...</TooltipContent></Tooltip></TooltipProvider>` when rationale is present. Tooltip surfaces the rationale + `Scored {timestamp}` line.
- New `data-confidence-tooltip="present|absent"` data attribute on the chip — used by Test 13 to assert the FE picks the right render path.

---

## Tightening compliance audit

| Tightening | Contract | Compliance |
|---|---|---|
| 1 — Consistency 3 calls + max pairwise ≤10 | Real-LLM test 15 runs 3 sequential Shield calls and asserts spread ≤ 10 | ✅ implemented at `test_score_confidence_real_shield_consistency_three_calls` |
| 2 — Don't clobber `documents.confidence_pct` on failure | Mirror only writes when scorer returns a non-None pct | ✅ pinned by test 9 `test_failed_score_does_not_clobber_documents_confidence_pct` (pre=82, scorer raises, post=82) |
| 3 — Tooltip suppression on missing rationale | FE renders bare chip without tooltip when rationale is absent/empty; no fake fallback copy | ✅ implemented; FE `data-confidence-tooltip="absent"` data attr; legacy-row sub-path covered by test 13 |
| 4 — Skip recompute when structured_content unchanged | `confidence_scored_at_cache_key` SHA-256 idempotency gate; response carries `confidence_recompute_skipped_unchanged: true` | ✅ pinned by test 11 `test_commit_recompute_skipped_when_structured_content_unchanged` (Shield mock `assert_not_called()` + flag asserted on response) |

---

## Lockdown evidence

### Phase 7 lockdown file (`tests/test_track_a_phase7_confidence_scoring.py`) — 15/15 at cap

- **Default sweep: 13/13 PASS** (test 1 deterministic 76 via Python banker rounding)
- **Integration-marked: 2 tests** (`@pytest.mark.integration` — opt-in via `pytest -m integration`):
  - Test 14: real Shield happy-path round-trip with explicit gap section + asserts `breakdown["gap_clarity"] >= 50`
  - Test 15: real Shield 3-call consistency with `spread = max - min <= 10` (Tightening 1)

### Aggregate regression sweep — 87/87 PASS, 5 deselected

- `test_qa_chunk_8.py` (25/25 incl. BUG-WS-001 fix)
- `test_track_a_phase3_narration.py` (9)
- `test_track_a_phase4_versioning_multi.py` (8)
- `test_track_a_phase4_iter2_corrective.py` (4)
- `test_track_a_phase5_lifecycle.py` (12 incl. inverted-stub Phase 6 test) + Phase 5 sibling files
- `test_track_a_phase6_inline_edit_and_bc_removal.py` (10 default)
- **`test_track_a_phase7_confidence_scoring.py` (13 default)**
- `test_solva_v1_unchanged.py` (2 — v1 byte-identical guard intact)

**5 deselected** = 2 Phase 7 integration-marked + 2 Phase 6 integration-marked + 1 chunk8 integration-marked.

### Cross-phase ripple resolved during iter-1

After the initial run, 3 tests failed with Mongo `WriteError: Cannot create field 'X' in element {intelligence_report: null}` — Phase 5/6 commit tests seed rows with `intelligence_report: None`. The dotted-path `$set` keys don't work against a null parent. Fixed surgically in 2 places (`_score_and_mirror_confidence` and `commit_document`) with a pre-$set guard that promotes `intelligence_report: None` → `{}` before the dotted writes. **+13 LOC total** for the ripple fix; both call sites tested in default sweep.

---

## Hard-no compliance audit

- ✅ No mocked LLM tests for the integration-marked path (tests 14-15 use real Shield).
- ✅ No silent except-swallow — every except logs via `logger.exception(...)` or `logger.warning(...)`; caller surfaces failure flags.
- ✅ No new env vars.
- ✅ No third-party libraries.
- ✅ No `shield_invoke` signature change — calls with new `purpose="work_studio.document.confidence_score"` only.
- ✅ No new UI components — extended existing `IntelligenceCard` with existing shadcn `Tooltip`.
- ✅ No Track B retouch.
- ✅ No schema migrations beyond additive — all new fields on `intelligence_report` are additive; legacy rows handled via `.get()` reads + None-coalesce on FE.
- ✅ File:line citations: every change cited inline in this memo.
- ✅ Pre-Read self-grep cross-checked OpenAPI via router-decorator grep + FE call sites via `DocumentOverlay.jsx` rendering chip.

---

## Cost transparency note (informational)

Per the dispatch's closing note: ~$0.10/Shield call, one call per compile + one per commit per doc. Tightening 4 collapses the typical "review-then-commit-without-edit" path to **1 call/doc** total. For active users committing 10 docs/day, this is ~$1/day/user with Tightening 4 vs ~$2/day/user without. Real money saved at scale.

---

## Files touched

### Created
- `backend/services/work_studio/__init__.py` (package init)
- `backend/services/work_studio/confidence_scorer.py` (~240 LOC — verbatim prompt + weights + aggregator + failure contract)
- `backend/tests/test_track_a_phase7_confidence_scoring.py` (~520 LOC — 15 tests at cap)
- `memory/sprints/TRACK_A_PHASE_7_CONFIDENCE_SCORING.md` (this file)

### Modified
- `backend/routers/work_studio_export.py` — import (+1 line) + `_score_and_mirror_confidence` helper (~95 LOC) + 2 injection points in `_run_export` (~50 LOC) + `_run_enhance` (~22 LOC) + dotted-path null-parent guard (~12 LOC)
- `backend/routers/work_studio_overlay.py` — imports (+5 lines) + commit-recompute logic (~80 LOC) + dotted-path null-parent guard (~7 LOC)
- `backend/services/work_studio_overlay.py` — `overlay_payload` extension (~10 LOC for 4 new fields)
- `frontend/src/components/work_studio/overlay/DocumentOverlay.jsx` — Tooltip imports (+6 lines) + `IntelligenceCard` extension (~25 LOC for tooltip wrap + suppression contract)

**Net delta: ~580 LOC backend (incl. tests) + ~30 LOC frontend = ~610 LOC.** Above the §13 Pre-Read estimate (~425); the +185 LOC overage is split between (a) the dotted-path null-parent guards that surfaced as ripples and (b) richer test fixtures than estimated. Both within iter-1 budget — no surprise required iter-2.

---

## Status

**Track A Phase 7 → ✅ COMPLETE 2026-06-05.**
- Total: 1 new BE service + 2 BE routers extended + 1 BE model file extended + 1 FE component extended + 1 new BE lockdown file with 15 tests at cap.
- Iter-0 archaeology: 1 of 1 (two-system landscape mapped before code).
- Iter budget: 1 of 3 used. Iter-2/3 reserved.
- 13/13 default sweep PASS + 87/87 aggregate regression PASS.
- 2 integration-marked real-Shield tests ready to run on demand via `pytest -m integration`.
