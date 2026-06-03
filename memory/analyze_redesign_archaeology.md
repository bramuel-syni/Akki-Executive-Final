# Analyze Redesign — Archaeology Pass (read-only)

**Date:** 2026-02 (fork-resume)
**Mode:** READ-ONLY. Zero product code touched, zero tests touched, zero env vars added.
**Operator instruction:** find any on-disk spec for the previously-mentioned "Analyze redesign" (drawer journey, executive-action density, journalistic copy, xlsx export, P5.14.1 stream rename → drawer chrome).

---

## 1. Verbatim grep results

### 1.1 `/app/memory/` — redesign-specific terms

| Query | Hits |
|-------|------|
| `grep -rIn -i "analyze redesign\|analyze.*redesign\|redesign.*analyze" /app/memory/` | **0 lines** (exit 0, empty stdout) |
| `grep -rIn "AR1\|AR2\|AR3" /app/memory/` | **0 lines** |
| `grep -rIn -i "what is running" /app/memory/` | **0 lines** |
| `grep -rIn -i "drawer chrome\|drawer journey" /app/memory/` | **0 lines** |
| `grep -rIn -i "headline-first\|journalistic" /app/memory/` | **0 lines** |
| `grep -rIn -i "site[-_ ]review[-_ ]43\|site-review-43" /app/memory/` | **0 lines** |
| `grep -rIn -i "reflecting back" /app/memory/` | **0 lines** |

### 1.2 `/app/memory/` — adjacent (non-zero) terms (for context, NOT spec matches)

`grep -rIn -i "xlsx" /app/memory/` — 19 lines. **None reference an Analyze-tab xlsx export.** Every hit is one of:
- `documents_service.py` extraction pipeline (PHASE_F1_CLOSEOUT: `.xlsx` → `openpyxl.load_workbook(read_only=True, data_only=True)`).
- Cycle / Studio / Compile wizard input acceptance (T3_LOG, HOME_CLEANUP_LOG, qa_24may2026 — uploads, not exports).
- P5.14 work_studio_analyze memo describing the existing `.xlsx`/`.csv` upload acceptance + sample fixtures.
- Bank-QA evidence pack screenshots README + SOLVA brief listing supported upload formats.

`grep -rIn -i "pre[-_ ]read" /app/memory/` — many lines. All references are to Cycle Manager / NED pre-read packs (CYCLE_MANAGER_BRIEF, PHASE_LEDGER I.4.b, phase_e_addendum_artefacts). **Zero references to Analyze pre-read or to a "pre-read" surface on Work Studio Analyze.**

`grep -rIn "P5\.14\.1\|P5\.14\.2\|P5\.14\.3" /app/memory/` — 14 lines. **P5.14.3 has zero hits.** P5.14.1 and P5.14.2 are the two existing shipped close-outs (real-wire AnalyzeStageStrip + compact-landings hotfix respectively). Memos:
- `/app/memory/sprints/P5_14_work_studio_analyze.md`
- `/app/memory/sprints/P5_14_2_compact_landings.md`

### 1.3 Source-code grep

`grep -rIn "AR1\|AR2\|AR3" /app/backend/ /app/frontend/src/` — **0 lines** (excluding `node_modules`).

### 1.4 qa_24may2026 QA aggregate

`grep -li "analyze" /app/memory/sprints/qa_24may2026/*.md` — **0 files match.** Confirmed: the 24-May QA aggregate (the canonical pre-fork QA bundle) does NOT mention Analyze at all.

### 1.5 `/app/memory/briefs/`

Files: `CHAT.md`, `INTEGRATION.md`, `SOLVA.md`, `SYNISENSE.md`. `grep -li "analyze" /app/memory/briefs/*` — **0 matches.** No brief exists for Analyze.

---

## 2. Current implementation citations (so the redesign has a known baseline to mirror or replace)

### 2.1 The Analyze surface today

- Route: `/app/work-studio/analyze` — declared in `/app/frontend/src/App.js:489`.
- Page component: `/app/frontend/src/pages/WorkStudioAnalyze.jsx` (438 lines, single file).
- Real-wire stage strip hook: `/app/frontend/src/components/work_studio/useAnalyzeStages.js` (87 lines, exports `STAGE_DEFS` for `parse · signals · simulate · forecast · anomalies · report`).
- Stage-strip presentational component: `/app/frontend/src/components/work_studio/AnalyzeStageStrip.jsx` (82 lines).
- Top-of-page master tabs (Generate ↔ Analyze switcher): `/app/frontend/src/components/work_studio/WorkStudioMasterTabs.jsx:22` — `{ id: "analyze", label: "ANALYZE", to: "/app/work-studio/analyze" }`.

**Density today** (from `WorkStudioAnalyze.jsx:264-315`, locked here for the redesign delta):
- `<section data-testid="analyze-actions">` is a `flex flex-wrap gap-3` row carrying **5 action buttons**:
  1. `data-testid="analyze-run-signals-btn"` — "Extract signals"
  2. `data-testid="analyze-run-simulate-btn"` — "Run Monte Carlo (P10/P50/P90)"
  3. `data-testid="analyze-run-forecast-btn"` — "Forecast forward (8 periods)"
  4. `data-testid="analyze-run-anomalies-btn"` — "Detect anomalies"
  5. `data-testid="analyze-download-pptx-btn"` — "Download PPTX report"

**Surface pattern today**: flat scrolling page. Sheet preview → 5-button action row → AnalyzeStageStrip → signals list → simulations list → forecasts list → anomalies list. No drawer. No journey gating. No journalistic headlines (section headers are tracking-uppercase eyebrows: "Sheet preview", "Signals", "Simulations", "Forecasts", "Anomalies").

### 2.2 Generate's drawer-journey pattern (what the redesign is asked to mirror)

The Generate side of Work Studio is rendered by `/app/frontend/src/pages/WorkStudio.jsx` (1247 lines). Two drawer-pattern primitives:

1. **Detail drawer** — `BriefDrawer` function-component at `WorkStudio.jsx:381` (mounts at line `1162`). Built on shadcn `<Sheet>` + `<SheetContent>` + `<SheetHeader>` + `<SheetTitle>` + `<SheetDescription>` (imports at lines 35-40). Opens on row click. Carries `data-testid="work-studio-brief-drawer"`. Bottom-half hosts the validation badge, provenance citation list, topline notes, and the CTA to open the composer.
2. **Multi-step modal "wizard"** — `CompilationWizard` (`/app/frontend/src/components/work_studio/CompilationWizard.jsx`, 890 lines). 4-step Dialog: `STEPS = ["1 Choose", "2 Sources", "3 Contributors", "4 Cadence"]` (line 46), with the step indicator at line 67. Opens from the right rail (`CompilationRail.jsx` — primary CTA "Compile a Report") OR a "Ready" row in the rail (pre-selects on step 2). Posts to `/api/contexts/{cid}/work-studio/compilations`.

State plumbing in `WorkStudio.jsx`: `const [drawerOpen, setDrawerOpen] = useState(false);` (line 674), `const [wizardOpen, setWizardOpen] = useState(false);` (line 718). Mount sites at 1162 (BriefDrawer) and 1203 (CompilationWizard). The `onOpenWizard` opener prop is at line 1153.

### 2.3 P5.14.1 stage-timing emit / consume paths

- **Emit** (the producer of stage-lifecycle events): `WorkStudioAnalyze.jsx:30` `const stagesApi = useAnalyzeStages();`. Each fetch wraps with `stagesApi.start(<id>)` → `stagesApi.success(<id>)` or `stagesApi.error(<id>, msg)`. Six instrumented stages: `parse` (line 37/47/50), `signals` (65/68/71), `simulate` (79/93/96), `forecast` (104/112/115), `anomalies` (123/128/131), `report` (139/158/160).
- **State** (the reducer): `useAnalyzeStages.js:43-86`. Returns `{ stages, defs, start, success, error, reset }`. Per-stage state shape: `{ status: "idle"|"running"|"success"|"error", startMs, durationMs, error }`. Real `performance.now()` deltas — no synthetic timers.
- **Consume** (the renderer): `<AnalyzeStageStrip stages={stagesApi.stages} defs={stagesApi.defs} />`. Two mount points: line 209 (during upload, inside the dashed upload zone) and line 320 (steady state, between the action row and signals list). Component file: `AnalyzeStageStrip.jsx`. Renders an ordered `<ol data-testid="analyze-stage-strip">` of `<li data-testid="analyze-stage-{id}">` rows; each row carries a `data-status` attribute + a glyph (✓ / spinner / ✗ / ·) + label + duration in ms.

### 2.4 Existing export endpoints + files

Backend router (sole source of truth): `/app/backend/routers/workbook_analysis.py` — header comment at lines 1-13 lists the eight endpoints:

```
POST   /api/workbook/upload                                    → create analysis from xlsx/csv
GET    /api/workbook/analyses                                  → list current-account analyses
GET    /api/workbook/analyses/{aid}                            → fetch (+sheet metadata + accreted artefacts)
POST   /api/workbook/analyses/{aid}/signals/extract            → run deterministic signal extraction
POST   /api/workbook/analyses/{aid}/simulate                   → Monte Carlo run
POST   /api/workbook/analyses/{aid}/forecast                   → linear forecast run
POST   /api/workbook/analyses/{aid}/anomalies                  → detect anomalies on a column
GET    /api/workbook/analyses/{aid}/report.pptx                → download the PPTX
```

Only **one** export endpoint exists: `GET /api/workbook/analyses/{aid}/report.pptx` (`workbook_analysis.py:452`). PPTX bytes are built via `services/workbook_analyzer/build_pptx_report` (imported at `workbook_analysis.py:51`). Filename pattern: `{re.sub(r"[^A-Za-z0-9._-]", "_", analysis.filename)}_analysis.pptx` (line 461).

**No `.docx` Analyze export exists.** Repo-wide search `grep -rn "report\.docx\|report\.xlsx\|analyses.*docx\|analyses.*xlsx" /app/backend` returned a single hit — `tests/test_backlog_b_blocker_1_overlay_title.py:107` — unrelated to Analyze (it's a legacy_report.docx test fixture for the document overlay title backlog item).

**No `.xlsx` Analyze export exists.** Same search confirms.

Frontend consumer of the existing PPTX export: `WorkStudioAnalyze.jsx:137-164` — the `downloadPptx` handler fetches `/workbook/analyses/${analysis.id}/report.pptx` as a Blob via the api wrapper, creates an object URL, and triggers a download. Identified `data-testid="analyze-download-pptx-btn"` on the button at line 313.

---

## 3. What's implemented today vs. what's missing per the user's pointers

| User pointer (verbatim) | On disk today | Missing for the redesign |
|---|---|---|
| "Analyze redesign — two additions locked in" | No spec memo, no AR1/AR2/AR3 token anywhere on disk | The entire spec |
| `"What is running"` stream from P5.14.1 → folds into AR1 (drawer chrome) | `AnalyzeStageStrip.jsx` + `useAnalyzeStages.js` exist and are wired into the flat page at lines 209 + 320 of `WorkStudioAnalyze.jsx`. They render under heading "Composing report…" etc — there is NO "What is running" label string anywhere | The strip needs to be lifted out of the flat page and mounted inside the new drawer chrome (AR1) with the renamed label "What is running". The lift is mechanical; the label rename is a 6-row STAGE_DEFS edit |
| `.xlsx` export added alongside `.pptx` / `.docx` → folds into AR3 | Only `report.pptx` exists (`workbook_analysis.py:452`). Frontend has a single PPTX button at `WorkStudioAnalyze.jsx:313` | Two new backend endpoints (`report.docx`, `report.xlsx`) + two new builders in `services/workbook_analyzer/` + a redesigned export affordance (AR3) |
| Tone shift: stats logs → journalistic headline-first | Current copy is bullet/eyebrow-uppercase ("Sheet preview", "Signals", "Simulations", etc.) — no narrative headlines | All section labels need to be rewritten as headline-first journalistic copy. Voice-lint clean required |
| Density shift: 5 buttons → small number of executive actions | 5 `analyze-run-*-btn` buttons in `analyze-actions` row (`WorkStudioAnalyze.jsx:264-315`) | The redesign collapses the action row. No source on disk specifies the new count or labels |
| Surface pattern: flat page → drawer journey (same as Generate) | Generate's two drawer primitives (`BriefDrawer` in `WorkStudio.jsx:381` + `CompilationWizard.jsx`) are ready to mirror. Analyze today is flat | Need to introduce a row-list → drawer journey on Analyze, mirroring Generate's `<Sheet>`-based pattern + the multi-step wizard for the run flow |

---

## 4. Verdict

**`no spec found on disk — fresh build needed`.**

The user's pointers describe a redesign that is real intent — referenced in earlier screenshots — but **the literal spec memo never landed in `/app/memory/`**. No `analyze redesign` string, no `AR1`/`AR2`/`AR3` token, no `what is running` label, no `drawer chrome` mention, no `headline-first` style note, no `P5.14.3` phase tag, no `site-review-43` doc, no `reflecting back` note. The qa_24may2026 bundle and `/app/memory/briefs/` both have zero Analyze references.

Everything needed to *implement* the redesign is, however, already on disk:
- The current Analyze page is single-file (438 lines) and cleanly instrumented with `data-testid`s.
- The stage-timing emit/consume paths are decoupled and lift cleanly into a drawer.
- Generate's drawer + wizard primitives (`BriefDrawer` + `CompilationWizard`) are ready to mirror.
- The PPTX export pattern (`workbook_analysis.py:452-475` + `services/workbook_analyzer/build_pptx_report`) is a clean template for the `.docx` and `.xlsx` sibling endpoints.

**Next step (NOT taken in this dispatch):** the user owes the redesign spec in writing — either by typing it into a fresh memo (e.g., `/app/memory/sprints/P5_14_3_analyze_redesign.md`) or by re-sharing the screenshots so an agent can transcribe them verbatim. Until the spec lands, no code changes are warranted.

---

## 5. Files-touched-by-this-dispatch report

```
?? memory/analyze_redesign_archaeology.md   # this memo
```

ZERO product code, ZERO tests, ZERO env vars. ZERO sprint memos modified.
