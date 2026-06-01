# P5.14 — Work Studio: Analyze tab (Monte Carlo + cited PPTX)

**Date:** 2026-02-23 · fork-resume on the live preview cluster
**Status:** SHIPPED to disk in preview · full E2E green at 4 viewports · 31/31 lockdowns green in isolation
**ANTIFORGET PROTOCOL:** acknowledged. No subagent testing. Raw Playwright + source-strict pytest. Solva v1/v2 engine untouched.

---

## 1. Step-by-step checkpoint table

| Step | Surface | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Workbook upload (xlsx/csv, 25 MB cap) | ✅ | `POST /api/workbook/upload` → 200 in trace; `test_upload_and_full_pipeline` green |
| 2 | Sheet parsing (openpyxl + csv stdlib; type inference; per-column stats) | ✅ | 2 sheet cards rendered live; `test_parser_xlsx_two_sheets_correct_metadata` + `test_parser_csv_single_sheet` green |
| 3 | Pull signals (deterministic, cited) | ✅ | 10 cited signals on the sample workbook live; `test_signal_extraction_produces_cited_signals` green |
| 4 | Monte Carlo simulations (numpy, deterministic seed) | ✅ | Live: P10=89.4 ≤ P50=155.5 ≤ P90=218.6 (bands monotonic); `test_monte_carlo_normal_deterministic`, `test_monte_carlo_four_distributions`, `test_monte_carlo_linear_formula_shifts_bands` all green |
| 5 | Forecast outcomes (linear regression + 80% CI) | ✅ | Live: status 200; `test_forecaster_matches_known_linear_series` green (R² > 0.99 on a perfect linear sample) |
| 6 | Anomaly detection (z-score + IQR) | ✅ | Live: 1 anomaly row (the planted q4 spike); `test_anomaly_detector_finds_planted_outlier` green |
| 7 | Generate cited PPTX report | ✅ | Live: 49,096 bytes, **8 slides, 8 speaker-notes XMLs**; `test_pptx_report_is_valid_zip_and_has_notes` + `test_pptx_report_speaker_notes_pass_refuse_to_decide` green |

## 2. Live Playwright trace evidence

Script: `/tmp/p5_14_analyze_e2e.py` (one file, 4-viewport probe + full 1280 pipeline).
Artefacts directory: `/tmp/p5_14_analyze/`.
Sample workbook used: `/tmp/p5_14_analyze/sample.xlsx` (12-month revenue + cost workbook with a planted q4 cloud-cost outlier).

### Full 1280 pipeline JSON summary

```json
{
  "sheet_cards": 2,
  "signals_status": 200,
  "signal_count": 10,
  "simulate_status": 200,
  "simulate_bands": {
    "p10": 89.39, "p25": 120.79, "p50": 155.46, "p75": 187.48, "p90": 218.60,
    "mean": 154.66, "stddev": 50.36
  },
  "forecast_status": 200,
  "anomalies_status": 200,
  "anomaly_count": 1,
  "report_status": 200,
  "report_bytes": 49096,
  "report_slide_count": 8,
  "report_notes_count": 8
}
```

Screenshots: `01_upload_zone.png` → `06_anomalies.png` plus `<viewport>_generate_top.png` and `<viewport>_analyze_top.png` per viewport.

### Multi-viewport (1280/1024/820/414) — master tab strip

| viewport | `work-studio-master-tabs` | generate pill | analyze pill | analyze H1 | upload zone | analyze pill active after nav |
| --- | --- | --- | --- | --- | --- | --- |
| 1280 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 1024 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 820  | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 414  | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

At 820/414 the initial probe found the master tabs **missing** on `/app/work-studio` — admin lands there without an active context and WorkStudio.jsx returned its pre-P5.14 "No company selected." stub. Surgical fix: added the master tabs to the no-context stub so the Analyze tab (which is account-scoped, not context-scoped) remains reachable at every viewport. Confirmed green on the re-run.

## 3. PPTX export — file integrity + chair-readable speaker notes

| Property | Value | How verified |
| --- | --- | --- |
| File size | 49,096 bytes | `ctx.request.get(...).body()` length |
| Valid zip | ✅ | `zipfile.ZipFile(...).testzip()` on the integration test path; live trace opens the archive and counts `ppt/slides/slide*.xml` |
| Slide count | 8 | cover + sheet-overview (2) + signals + simulation + forecast + anomalies + methodology |
| Speaker-notes XML count | 8 | `ppt/notesSlides/*.xml` — every slide has notes |
| Speaker notes pass refuse-to-decide | ✅ | `validate_no_imperatives()` runs against every notes string BEFORE `_set_notes` attaches it; bad narration trips `RefuseToDecideViolation` at build time (negative test `test_pptx_report_speaker_notes_pass_refuse_to_decide` injects an imperative and asserts the build raises) |

---

## 4. File-touch diff summary

### Backend (new sibling package + router)

| Path | Lines | Purpose |
| --- | --- | --- |
| `services/workbook_analyzer/__init__.py` | 67 | Public surface re-exports |
| `services/workbook_analyzer/schema.py` | 220 | Pydantic models — `WorkbookCitation`, `WorkbookAnalysis`, `WorkbookSheet`, `MonteCarloRun`, `ForecastRun`, `AnomalyRow`, `NarrationBlock` |
| `services/workbook_analyzer/parser.py` | 180 | xlsx (openpyxl) + csv (stdlib) parsing; type inference + per-column stats |
| `services/workbook_analyzer/citation_resolver.py` | 140 | A1 cell-range resolver — rejects unknown sheets, out-of-bounds rows/cols, inverted ranges; sibling to Solva v2's resolver |
| `services/workbook_analyzer/monte_carlo.py` | 160 | Pure-numpy MC; deterministic seed; 4 distributions; `=a*x+b` linear formula support; reproducer-hash for byte-identical re-runs |
| `services/workbook_analyzer/forecaster.py` | 130 | Linear regression baseline; residual-stddev 80% CI; cell-range citations on every projection |
| `services/workbook_analyzer/anomaly_detector.py` | 95 | z-score AND IQR thresholds; observational rationale per row; cell-range citation |
| `services/workbook_analyzer/refuse_to_decide.py` | 90 | Sibling refuse-to-decide validator — 10 imperative-pattern regexes; trips `RefuseToDecideViolation` on any narration containing imperative-to-user phrasing |
| `services/workbook_analyzer/signal_extractor.py` | 130 | Deterministic top-metric / outlier / missing-data signals; every signal carries ≥1 cell-range citation |
| `services/workbook_analyzer/report_builder.py` | 200 | python-pptx deck builder; 8 slides with speaker notes; every notes string passes refuse-to-decide before attach |
| `routers/workbook_analysis.py` | 380 | 7 endpoints, all CSRF-protected by namespace (not in allowlist); tenant scoping on every read/write |
| `server.py` | +9 | Wire-in router |

### Frontend (master tabs + Analyze page)

| Path | Lines | Purpose |
| --- | --- | --- |
| `components/work_studio/WorkStudioMasterTabs.jsx` | 45 | Two-pill switcher; mirrors Monitor pill-tab pattern; auto-detects active tab from `useLocation()` |
| `pages/WorkStudioAnalyze.jsx` | 290 | Full Analyze surface — upload zone, sheet preview, signals list, simulation panel, forecast panel, anomalies panel, PPTX download |
| `pages/WorkStudio.jsx` | +18 | Master tabs injected at top of both the `!cid` stub AND the main render; existing Generate surface otherwise untouched |
| `App.js` | +3 | Lazy-load `WorkStudioAnalyze` + add `/app/work-studio/analyze` route |

### Tests + fixtures

| Path | Lines | Purpose |
| --- | --- | --- |
| `tests/fixtures/__init__.py` | 1 | Package marker |
| `tests/fixtures/workbook_sample.py` | 70 | `build_sample_xlsx()` / `build_sample_csv()` builders — used by pytest AND by the Playwright trace |
| `tests/test_phase_p5_14_workbook_analyze.py` | 380 | 31 tests across parser, MC, forecaster, anomaly, citation-resolver, refuse-to-decide, PPTX, endpoint pipeline, tenant isolation |

---

## 5. Pytest output + new test count

```
pytest tests/test_phase_p5_14_workbook_analyze.py -q
31 passed in 4.65s
```

### Tests added (by promise area)

| Promise / area | Tests | Negative-sample test included? |
| --- | --- | --- |
| Citation realness (P3) | 6 | ✅ `test_resolver_rejects_unknown_sheet`, `_rejects_out_of_bounds_row`, `_rejects_out_of_bounds_col`, `_rejects_inverted_range`, `_rejects_missing_sheet_separator` |
| Refuse-to-decide (P5) | 6 | ✅ 5 imperative phrasings rejected (`you should…`, `you must…`, `decide now…`, `the right action is…`, `you need to…`) via parametrize |
| MC determinism | 6 | ✅ `_different_seed_different_bands`, `_rejects_unsupported_formula`, `_rejects_bad_iterations` |
| Forecaster | 2 | ✅ `_rejects_too_few_pairs` |
| Anomaly detector | 2 | ✅ `_empty_on_constant_column` |
| Parser | 3 | ✅ `_rejects_unknown_format` |
| PPTX builder | 2 | ✅ `_speaker_notes_pass_refuse_to_decide` injects an imperative narration and asserts the builder raises |
| CSRF invariant | 1 | source-strict — `/api/workbook` NOT in csrf allowlist |
| Tenant isolation (P6) | 1 | ✅ Viewer cannot GET admin's analysis (404), cannot mutate (404), cannot download report (404) |
| Endpoint E2E | 1 | full pipeline upload → signals → simulate → forecast → anomalies → report.pptx |
| Signal extraction | 1 | every signal carries a cell-range citation that resolves |

**Total: 31 new tests + full E2E live trace.**

### Cross-test state leak — flagged, NOT fixed in this phase

When run in a broader suite (P5.10 + P5.11 + P5.12 + P5.14 together), `test_upload_and_full_pipeline` and `test_tenant_isolation_cross_account_returns_404` fail due to **the same shared-fixture state leak previously flagged in P5.11 + P5.13** (`test_cycle_assignment_handoff.py` showed the same pattern). When the two tests are run in isolation OR within just the P5.14 file, all 31 tests pass green.

Per discipline rule #9 (no piggybacked fixes), the cross-test fixture isolation is left for a future P5.x test-infrastructure cleanup phase. P5.14's contract is met because the tests themselves are correct + the live E2E proves the path works against the running server.

---

## 6. Architecture notes (for the next maintainer)

### Why a sibling package, not an extension of Solva v2

The user instruction stated `DO NOT touch Solva v1 or Solva v2 engine`. Extending `services/solva_v2/artefact_schema.py::SourceCitation.source_kind` with `"workbook_cell"` would have been the minimum-code path but would have:
- Modified the v2 engine schema → potentially regressed the byte-identical guard.
- Coupled future workbook changes to the v2 release cadence.

Instead `services/workbook_analyzer` is a clean sibling with its own `WorkbookCitation` type, its own resolver, and its own refuse-to-decide validator. The only Solva v2 surface this package depends on is `llm_adapter.shielded_call` — the canonical shielded LLM entry point. Every LLM call (when narration is eventually opted into) routes through it, so the `test_no_direct_llm_calls_outside_shield.py` guard stays green.

### Citation resolver design

`WorkbookCitation.cell_range` is an Excel-A1 reference: `"<sheet>!<TL>[:<BR>]"`. The resolver (`citation_resolver.py:resolve()`) verifies four invariants:
1. Sheet name matches a parsed sheet.
2. Top-left row/col are within the sheet's bounds.
3. Bottom-right row/col are within the sheet's bounds.
4. Top-left ≤ bottom-right in both axes.

Any failure raises `CitationUnverifiable` — the workbook-analyzer analogue of Solva v2's `citation_unverifiable`. The error message prefix is stable so upstream UI/pytest assertions can rely on it.

The router runs `WorkbookCitationResolver.resolve_many()` over every signal/forecast/anomaly/simulation citation BEFORE persisting to Mongo. **Fabricated cell ranges therefore never reach disk.**

### Monte Carlo determinism

`monte_carlo._sample()` uses `numpy.random.default_rng(seed)` exclusively. Given a `(column, distribution, params, formula, iterations, seed)` tuple, two runs produce byte-identical bands — `test_monte_carlo_normal_deterministic` asserts this exact equality.

The `reproducer_hash` is `sha256(JSON.dumps(tuple, sort_keys=True))`. It's stored on every `MonteCarloRun` row and rendered in the PPTX methodology slide. Re-running the same hash returns the same bands.

Formula support is intentionally restricted to identity `=x` or a linear transform `=a*x+b` (a, b numeric literals). Anything richer raises `ValueError` — see `test_monte_carlo_rejects_unsupported_formula`. Column-reference formulas (`=ColumnA * (1 + ColumnB / 100)`) are explicitly out of scope for v1 and surfaced as future work in the memo (not implemented).

### Narration safety

Every narration string in this pipeline — Monte Carlo, forecast, anomaly rationale, PPTX speaker notes — passes through `validate_no_imperatives()` before being persisted or attached to a slide. The validator is a regex screen against 10 imperative-to-user patterns (`you should…`, `you must…`, `the right action is…`, etc.). A directive phrasing raises `RefuseToDecideViolation`, which the router catches and either skips the offending signal (for signal extraction) or returns a 500 with the explicit error code (for the PPTX builder — there's no graceful narration fallback that would silently ship a directive).

For the MVP, narration is **deterministic templates only**, not LLM-generated — this guarantees the validator never fires on the production path and removes any LLM-quota dependency. The scaffolding to upgrade signal narration to `shielded_call` is in place in `signal_extractor.py:extract_signals_for` (the `narrate=True` mode docstring); upgrading it is a future iteration not in this phase.

---

## 7. Promise alignment

| Akki promise | How P5.14 holds it |
| --- | --- |
| **Every claim cited** (P3) | Every signal/forecast/anomaly/simulation has ≥1 `WorkbookCitation` that resolves to a real cell. Fabricated ranges fail `CitationUnverifiable` in the resolver before persistence. |
| **No LLM reads your data** (P2) | Deterministic-only narration in this MVP — zero LLM calls. When narration is eventually opted-in, it routes through `services.solva_v2.llm_adapter.shielded_call`, which applies Synisense redaction. Full dataset never crosses the LLM boundary; the existing P2 lockdown guard (`test_no_direct_llm_calls_outside_shield`) covers the analyzer namespace automatically. |
| **Decisions stay yours** (P5) | `validate_no_imperatives()` runs on every narration string before persistence. PPTX builder raises rather than ships a directive. 5-pattern negative test in the lockdown. |
| **Every bias is named** (P4) | The sibling `RefuseToDecideViolation` covers the prescriptive-language side of bias. Frame-shape biases would surface in narrations from a future LLM-mode and would be caught by the existing Solva v2 bias chip pipeline (the analyzer's narration paths share that pipe via `shielded_call`). |
| **Your data never leaves your account** (P6) | Every router read/write scoped on `account_id`. Cross-tenant attempts return 404 (no existence leak). `test_tenant_isolation_cross_account_returns_404` proves this end-to-end. |
| **Akki for Executives — full Claude under governance** (P7) | LLM narration (when opted-in) routes through the same shielded path Solva v2 uses; bias chips + audit log persistence travel for free. |

---

## 8. v1 byte-identical guard + voice-lint

```
pytest tests/test_solva_v1_unchanged.py -q     →  4 passed
python3 scripts/lint_voice.py                  →  voice_lint: clean across customer-copy surfaces.
```

---

## 9. Out of scope for v1 (intentionally not built)

| Item | Notes |
| --- | --- |
| Column-reference formulas (`=ColumnA * (1 + ColumnB / 100)`) | Linear `=a*x+b` only this phase. Surfaced as future expansion. |
| DOCX export | PPTX only this phase per user instruction. |
| Charting library beyond what python-pptx provides | Histogram + projection lines render as text bullets + counts in speaker notes; future iteration can add real charts via `python-pptx`'s native chart API. |
| Real-time collaborative editing | Analyses are single-user-scoped, read-only after upload. |
| Workbook in-app editing | Read-only analysis. |
| External sharing of the analysis | Inbound only. |
| Scheduled re-runs of simulations | One-shot; the reproducer hash guarantees identical re-run on demand. |
| Cross-workbook joins | Single-workbook only. |
| Pulse Ideas tab | P5.15, separate dispatch. |
| Email Akki routing | P5.16, separate dispatch. |

---

## 10. Adjacent items noticed (NOT silently fixed this phase)

| Item | Binary | Where I'd file it |
| --- | --- | --- |
| Cross-test fixture state leak (the 2 broader-suite failures) | **Adjacent — test infra** | Future P5.x: refactor the `transport` fixture + the AsyncClient session jar so tests don't carry login state across files. Already flagged in P5.11 + P5.13 memos. |
| `WorkStudio.jsx` had a pre-existing `if (!cid)` early-return stub that hides the entire content surface when admin has no active context. Master tabs added there per P5.14 scope. | **Adjacent — pre-existing pattern** | Future polish: replace the stub with a richer "pick a company" surface; outside P5.14 scope. |

Neither item was silently fixed inside P5.14.

---

## 11. Deliverable index

| Artefact | Path |
| --- | --- |
| This memo | `memory/sprints/P5_14_work_studio_analyze.md` |
| Playwright E2E + multi-viewport trace | `/tmp/p5_14_analyze_e2e.py` |
| Trace artefacts (summary.json + 8 screenshots + sample.xlsx + report.pptx) | `/tmp/p5_14_analyze/` |
| Sample workbook builder (pytest + trace) | `backend/tests/fixtures/workbook_sample.py` |
| Backend service package | `backend/services/workbook_analyzer/` |
| Router | `backend/routers/workbook_analysis.py` |
| Pytest lockdown | `backend/tests/test_phase_p5_14_workbook_analyze.py` |
| Frontend Analyze page | `frontend/src/pages/WorkStudioAnalyze.jsx` |
| Master tabs component | `frontend/src/components/work_studio/WorkStudioMasterTabs.jsx` |

**HUMAN_REQUIRED to ship:** deploy preview → production. The full pipeline lives entirely behind the existing auth + CSRF chain; no new env vars; no new Mongo indexes (the `workbook_analyses` + `workbook_blobs` collections are created on first insert).

---

**ANTIFORGET PROTOCOL re-acknowledgement.** No subagent testing. Raw Playwright traces against the live preview. Solva v1/v2 engines byte-identical. Voice-lint clean. Refuse-to-decide validator runs on every narration. Cross-tenant access denied + audited. CSRF enforced on every new state-changing endpoint via namespace exclusion from the allowlist.

---

## P5.14.1 — Close-out patch (stage-driven loader UX)

**Date:** 2026-02-23 same-day follow-up. User picked option (c): defer the SSE endpoint, but make the in-flight loader UX honour the "real backend signals" promise by showing real stage labels driven by the actual sequential API calls already in place.

### What landed

| File | Change |
| --- | --- |
| `frontend/src/components/work_studio/useAnalyzeStages.js` | NEW hook — 6-stage state machine; `start/success/error/reset` methods; per-stage real-wire `performance.now()` durations; zero `setTimeout`. |
| `frontend/src/components/work_studio/AnalyzeStageStrip.jsx` | NEW component — renders the 6 stages with spinner / ✓ / ✗ glyphs, real durations in ms, real backend error string per stage. Hidden until the first stage transitions out of idle. |
| `frontend/src/pages/WorkStudioAnalyze.jsx` | Every API call now wrapped with `stagesApi.start(id)` → `success(id)` / `error(id, msg)`. Strip renders in both the upload-zone (mid-parse) and parsed-view (steady-state) surfaces. Toast preserved as the secondary error surface; the strip carries the canonical wire-level error state. |

### Stage labels (voice-lint clean — observational, no banned terms)

| stage id | running label | done label |
| --- | --- | --- |
| `parse` | Parsing workbook… | Parsed |
| `signals` | Extracting signals… | Signals extracted |
| `simulate` | Running Monte Carlo… | Simulation complete |
| `forecast` | Projecting forecast… | Forecast complete |
| `anomalies` | Detecting anomalies… | Anomalies surfaced |
| `report` | Composing report… | Report ready |

### Stage-label trace evidence

Script `/tmp/p5_14_1_stagestrip_trace.py`; artefacts `/tmp/p5_14_1_stagestrip/`.

The probe uses Playwright's `route` API to artificially delay each `/api/workbook/*` call ~700 ms — letting the running-stage label be captured atomically via a browser-side polling `evaluate()` (the snapshot is taken inside the same tick we observe `data-status="running"`, so the production code's real-wire transitions aren't masked by Python ↔ browser round-trip latency).

**Transition table (proves labels flip in declared order; each in-flight snapshot has exactly ONE `running` stage; subsequent stages stay `idle` until their predecessor reaches `success`):**

```
parse_in_flight                par● sig· sim· for· ano· rep·
parse_success                  par✓ sig· sim· for· ano· rep·
signals_in_flight              par✓ sig● sim· for· ano· rep·
signals_done                   par✓ sig✓ sim· for· ano· rep·
simulate_in_flight             par✓ sig✓ sim● for· ano· rep·
simulate_done                  par✓ sig✓ sim✓ for· ano· rep·
forecast_in_flight             par✓ sig✓ sim✓ for● ano· rep·
forecast_done                  par✓ sig✓ sim✓ for✓ ano· rep·
anomalies_in_flight            par✓ sig✓ sim✓ for✓ ano● rep·
anomalies_done                 par✓ sig✓ sim✓ for✓ ano✓ rep·
report_in_flight               par✓ sig✓ sim✓ for✓ ano✓ rep●
report_done                    par✓ sig✓ sim✓ for✓ ano✓ rep✓
```

**Final-state durations (real wire-level, captured by `performance.now()`):**

```
parse      success  Parsed                 888ms
signals    success  Signals extracted      820ms
simulate   success  Simulation complete    803ms
forecast   success  Forecast complete      803ms
anomalies  success  Anomalies surfaced     804ms
report     success  Report ready           889ms
```

The ~800 ms baseline is the artificial route delay introduced by the test harness. Production code has zero added delay — durations reflect the actual API round-trip and would be 100–400 ms per stage depending on workbook size.

### Multi-viewport probe (stage strip rendered mid-parse)

| Viewport | parse status (mid-flight) | label captured |
| --- | --- | --- |
| 1280 | `running` | `Parsing workbook…` |
| 1024 | `running` | `Parsing workbook…` |
|  820 | `running` | `Parsing workbook…` |
|  414 | `running` | `Parsing workbook…` |

Strip visible at every viewport. Screenshots `vp_1280_strip_inflight.png` … `vp_414_strip_inflight.png` under `/tmp/p5_14_1_stagestrip/`.

### Regression check

| Check | Result |
| --- | --- |
| `tests/test_phase_p5_14_workbook_analyze.py` | 31 passed |
| `tests/test_solva_v1_unchanged.py` | 4 passed |
| Voice-lint | `voice_lint: clean across customer-copy surfaces.` |
| P5.14 full-pipeline E2E (`/tmp/p5_14_analyze_e2e.py`) | PASS — Work Studio Analyze E2E green |
| Frontend compile | `Compiled successfully!` |

### Backlog discipline — adjacents addressed

Per user mandate ("keep backlogs at absolute minimum"), the P5.14 close-out adjacents were re-triaged:

| Item | Verdict this phase | Why |
| --- | --- | --- |
| `WorkStudio.jsx` pre-existing `!cid` "No company selected." stub | **LEFT LOGGED — structural, sitewide pattern** | grep confirmed the identical 3-line stub appears in 5+ sibling pages (`InfluenceMap.jsx`, `Pulse.jsx`, `Monitor.jsx`, `TaskManager.jsx`, etc.). Replacing it in WorkStudio alone would be inconsistent; replacing it sitewide is >30 lines × 5 pages — outside P5.14.1 scope. P5.14 already injected the master tabs into the stub so the Analyze tab remains reachable. |
| Cross-test fixture state leak in P5.14 broad-suite runs | **LEFT LOGGED — structural Motor event-loop binding** | Reproduced and root-caused: `Future ... attached to a different loop`. Motor's module-singleton AsyncIOMotorClient binds to the first event loop that touches it; subsequent tests in a new loop get the cross-loop error. This is the canonical Motor pattern issue; the per-file isolation requires a session-scoped `motor` fixture rebinding via `client.io_loop = current_loop` OR moving to a per-test client factory. ≫30 lines of structural refactor. |
| SSE endpoint for stage events | **DEFERRED (user choice)** | The polling-free stage strip in P5.14.1 honours the "real backend signals" promise without SSE. SSE remains future work if multi-second stage durations ever become common. |

Net deferred list is now three items — each logged exactly once in this memo, none piled into P5.16.

### File-touch diff this phase

```
+ frontend/src/components/work_studio/useAnalyzeStages.js     (NEW, 92 lines)
+ frontend/src/components/work_studio/AnalyzeStageStrip.jsx   (NEW, 81 lines)
~ frontend/src/pages/WorkStudioAnalyze.jsx                    (+44 lines wrapping handlers; +1 strip render in upload zone; +1 strip render in parsed view)
~ memory/sprints/P5_14_work_studio_analyze.md                 (this close-out section + slimmed deferred list)
~ memory/PRD.md                                                (P5.14.1 close-out block prepended)
```

Total new code: 173 lines. Total edits to existing files: ~50 lines. Zero backend changes (real-wire stage strip is pure FE state derived from existing endpoint fetches).

### ANTIFORGET PROTOCOL re-acknowledgement

All discipline items honoured:
1. Raw Playwright traces only — atomic browser-side snapshot capture so the transitions aren't lost to round-trip latency. ✅
2. v1 byte-identical guard 4/4 green. ✅
3. Voice-lint clean across the 12 new stage labels (observational, no banned terms). ✅
4. CSRF preserved — no new endpoints, no new fetch sites. ✅
5. Real numpy MC unchanged — strip is a pure UI state observer, no backend semantics shifted. ✅
6. Citation realness unchanged — strip is below the citation pipeline, not adjacent to it. ✅
7. Refuse-to-decide unchanged. ✅
8. Tenant isolation unchanged. ✅
9. Adjacents stayed logged, not silently fixed. The sitewide `!cid` stub and Motor loop binding are explicitly out of P5.14.1 with single-sentence rationale each. ✅
10. Every checkpoint in this close-out cites its artefact path or test name. ✅

