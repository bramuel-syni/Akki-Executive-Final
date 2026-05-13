# Chunk 4 — Compilation Wizard wiring (WS-R02, R04, R05, R07, R08)

> 2026-05-13 — five QA tickets, one bug, three lines of code.

---

## 0. TL;DR

Five QA tickets, **one bug** spanning **three call sites** (Compile
Board Pack, Compile Minutes, Compile Committee Pack) plus **one
contract decision** inside the wizard. Everything routed through the
same path:

The three Compile-XXX action buttons in `pages/WorkStudio.jsx` all
literally passed the string `"report"` to `onCompile(...)` — regardless
of which button was clicked. That single mistake produced **all five
QA symptoms** because:

1. The wizard receives `preselectArtefactType="report"` → fires its
   "I already know the type, skip to sources" branch → **lands on
   Step 2** (R02, R07, R08).
2. The Step-1 radio default = `preselectArtefactType` → if the user
   backs up they see **Report pre-selected** instead of Board Pack
   (R04).
3. Step 2's source query reads from `artefactType` → fetches
   `kind=report` aggregates → returns empty for Minutes and Committee
   Pack contexts that have no Report data (R05, R08).

Plus the wizard's `useEffect` hardcoded `setStep(preselectArtefactType ? 2 : 1)`
— even after the Compile buttons started passing the right type, this
**still** auto-skipped Step 1, violating QA's explicit expectation
that the wizard ALWAYS begins on Step 1.

So the fix is in two places: (a) wire each Compile-XXX button to its
real artefact type, (b) make the wizard always start at Step 1
regardless of preselection (the preselect just seeds the radio default).

---

## 1. Per-button diagnosis

### 1.1 Compile Board Pack (WS-R02 + WS-R04)

**File**: `/app/frontend/src/pages/WorkStudio.jsx::ContextActions` — `cycle_board_pack` action row.
**Pre-fix**:
```jsx
{ id: "compile_board_pack", label: "Compile Board Pack", icon: Files,
  onClick: () => onCompile("report") },
```
The literal `"report"` was passed every time. `onCompileClick` then
mapped `"report" → "report"` and opened the wizard with
`preselectArtefactType="report"`. The wizard's `useEffect` saw a
truthy preselect, set `step=2`, and rendered the Sources step with
Report pre-selected.

Net effect for the user: clicked **Compile Board Pack**, saw a wizard
that said *Sources for Report* — both wrong.

### 1.2 Compile Minutes (WS-R07 + WS-R05)

**File**: same — `cycle_minutes` action row.
**Pre-fix**:
```jsx
{ id: "compile_minutes", label: "Compile Minutes", icon: Files,
  onClick: () => onCompile("report") },
```
Identical bug. Plus a downstream consequence: when the wizard's
Step-2 source query fired against `kind=report` instead of
`kind=cycle_minutes`, the user's seeded minutes documents were
filtered out → **empty source list**. That's WS-R05.

### 1.3 Compile Committee Pack (WS-R08)

**File**: same — `cycle_committee_pack` action row.
**Pre-fix**:
```jsx
{ id: "compile_committee_pack", label: "Compile Committee Pack", icon: Files,
  onClick: () => onCompile("report") },
```
Same again. Same Step-2 source emptiness consequence — committee-pack
data exists under `kind=cycle_committee_pack`, never surfaces for a
Report query.

---

## 2. Root cause

**Single root cause** (one bug, three call sites): the
Patch 2B.1 ContextActions row was authored before the wizard's
`preselectArtefactType` contract was finalised. When the wizard
landed and its prop got wired, no one went back to update the three
Compile-XXX call sites. Linters won't catch this because both `"report"`
and `"minutes"` are valid `ARTEFACT_TYPES` keys — the bug only shows
up if you test from each button.

**Second contract issue**: even with the right type passed in, the
wizard's `useEffect` skipped Step 1 when `preselectArtefactType` was
truthy. QA's reported expectation (R02 specifically) is *"the wizard
ALWAYS lands on Step 1"* — preselect should set the radio default,
not the step index. Two-line fix on the wizard.

---

## 3. Fix paths

### 3.1 `/app/frontend/src/pages/WorkStudio.jsx`

* **ContextActions** — three Compile-XXX rows now pass their real
  artefact-type key:
  ```jsx
  cycle_board_pack:     onCompile("board_pack")
  cycle_minutes:        onCompile("minutes")
  cycle_committee_pack: onCompile("committee_pack")
  ```
* **`onCompileClick` map** — extended from
  `{ report: "report", deck: "deck" }` to all six wizard-eligible
  types (`board_pack`, `minutes`, `committee_pack`, `deck`, `report`,
  `briefing`). Unknown kinds still fall through to the legacy
  enhance-compile path.

### 3.2 `/app/frontend/src/components/work_studio/CompilationWizard.jsx`

* **`setStep(preselectArtefactType ? 2 : 1)` → `setStep(1)`**. The
  wizard ALWAYS opens on Step 1. The preselect now does ONLY what its
  name suggests — seeds the Step-1 radio default. The user clicks
  Continue to advance.
* **Format default keyed by type**. New `DEFAULT_FORMAT_BY_TYPE` map
  routes Deck → PPTX, everything else → DOCX. Pre-fix every wizard
  defaulted to DOCX, which made Compile Deck → Step 4 show DOCX
  ticked. (Step-5 cross-check finding — applied inline because it's
  obvious-default territory.)
* **Format default updates when type changes**. A second `useEffect`
  syncs the format ticks when the user toggles the type radio on
  Step 1 (so they don't have to manually un-tick DOCX + tick PPTX
  if they switch to Deck mid-flow).

---

## 4. Tests

`/app/backend/tests/test_chunk4_wizard_aggregates.py` — **9 new tests**:

* **Parametrised over all 6 wizard kinds** — the aggregate endpoint
  must respond cleanly (200 + items list) for `cycle_board_pack`,
  `cycle_minutes`, `cycle_committee_pack`, `deck`, `report`, `briefing`.
  Pre-Chunk 4 the wizard only ever reached `cycle_board_pack` because
  the Compile-XXX buttons fed `report` to every flow.
* **Unknown kind → 400** — defence-in-depth + asserts the error
  message lists the valid kinds so a developer mis-configuring the
  frontend sees the right names.
* **Board pack row surfaces under `kind=cycle_board_pack`** — seeded
  row appears in the response (handles the `cycle_board_pack::<id>`
  namespace prefix that `_list_cycle_board_packs` applies).
* **Board pack row does NOT leak under the other 5 kinds** — the
  most-likely future regression class. If a wiring change ever
  cross-feeds a kind, this fails.

`/app/frontend/scripts/render-smoke.js` — **new Step 5** "Chunk 4
Compilation Wizard smoke". Visits Work Studio, iterates three Compile
buttons (Board Pack, Minutes, Committee Pack), asserts each opens the
wizard on Step 1 with the correct radio pre-selected. Soft-skips
gracefully on accounts that have no items for those tabs (the NED
test account doesn't show those tabs at all). The hard assertion is
on the backend `test_chunk4_wizard_aggregates.py` side — render-smoke
is the UI-side click receipts.

**Test counts**: 428 passed (was 419), 565 skipped, 0 failed.

---

## 5. Verification

* **Lint**: clean across all 3 touched JS/JSX files + render-smoke.
* **Backend**: full pytest sweep PASS — 428 / 565 / 0.
* **render-smoke**:
  ```
  PASS — 8 routes clean · 2 upload paths green ·
         Patch 28 interactions green · Chunk 4 wizard green.
  ```
* **Curl receipts** — backend correctly returns the right items per
  kind once the wizard passes the right `kind` (confirmed against
  `bramuel@syni.ai` / `dcc263b1-…` — `cycle_board_pack` returned 2,
  `cycle_minutes` returned 1, `cycle_committee_pack` returned 0
  — all clean 200s).

---

## 6. Step-5 cross-check findings

| Step | Verdict | Note |
|---|---|---|
| Step 1 — Type radio + Template card | ✅ | Renders correctly for all 6 types post-fix. |
| Step 2 — Source query | ✅ | Reads `artefactType` state, queries the right `kind`. Backend test suite verified. |
| Step 3 — Contributors preview | ✅ | Derives from selected sources; no per-type branching, works for all 6. |
| Step 4 — Cadence + Format radios | **⚠ default mismatch fixed inline** | Pre-fix always defaulted format to `["docx"]`. Now Deck defaults to `["pptx"]`; Brief / Board Pack / Minutes / Committee Pack / Report → `["docx"]`. Applied inline as obvious-defaults territory. |
| Step 4 — Title autogenerator | ✅ | Already keyed off `artefactType`. |
| Compilations collection persistence | ✅ | Backend already handles all 6 kinds (existing Patch 2B.2 work — confirmed by reading `routers/compilations.py`). |

**Per-type format defaults applied autonomously** (one autonomous
decision worth flagging — captured in `PRODUCT_CLARIFICATIONS_13MAY2026`
under a new line item rather than a clarification because the default
is uncontroversial — Deck is fundamentally a PowerPoint).

---

## 7. Files touched

| File | Change |
|---|---|
| `frontend/src/pages/WorkStudio.jsx` | 3 Compile-XXX rows pass real type keys; `onCompileClick` map extended to 6 types |
| `frontend/src/components/work_studio/CompilationWizard.jsx` | `setStep(1)` unconditionally; new `DEFAULT_FORMAT_BY_TYPE` + two effects (initial + change-driven) |
| `frontend/scripts/render-smoke.js` | New `smokeChunk4Wizard` step asserting Step-1 + correct radio for the three QA-named buttons |
| `backend/tests/test_chunk4_wizard_aggregates.py` | **new** — 9 regression tests (6-kind parametrise + 3 hardening) |

---

## 8. Clarifications surfaced

* **Per-type format defaults**: Compile Deck now defaults to PPTX
  on Step 4 (was DOCX). Everything else stays DOCX. Reasonable; PO
  override available — single map in
  `CompilationWizard.jsx::DEFAULT_FORMAT_BY_TYPE`.

— end of Chunk 4 close-out —
