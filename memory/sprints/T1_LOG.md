# T1 Implementation Log

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (Ratified 24 May 2026).
Scope: T1.1, T1.2 (closed pre-flight), T1.3, T1.4, T1.5, T1.6 only.
Scope-out lands in `/app/memory/sprints/POST_T5_BACKLOG.md`.

---

## Pre-tier hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-T1` → commit `fbea67fd05125148564d13fd4e314a26c0793837` | 2026-05-25T05:08:40Z |
| Mongo dump | `/app/backup/pre_T1_20260525T050845Z/akki_dev/` (237 bson + metadata files, 62 MB) | 2026-05-25T05:08:46Z |

Note: tag was created locally on the pod. Pushing to `origin` requires the user's "Save to Github" feature; the local tag itself is the rollback point used by `git checkout v-pre-T1` on the pod.

---

## T1.2 — Closed by e1_tester (no code action)

Status: **Resolved — verified by e1_tester on 24 May 2026, evidence in spec §6 audit trail.**
Notes: stripping regex (`/T:[a-zA-Z_0-9]+/` and `/\[T:/`) confirmed 0 matches across Document Journal listing, drawer, reader, and Chat as `bramuel@syni.ai`. Per PO instruction, the regex is not touched.

---

## Disk re-verification (per item)

### T1.1 — Chat responsive width + fixed input bar — **Confirmed on disk (no change)**
- `frontend/src/pages/Chat.jsx`:
  - L878: container `… overflow-x-hidden overflow-hidden …`
  - L1112: message scroll area `flex-1 overflow-y-auto overflow-x-hidden …`
  - L1605: composer `<div className="sticky bottom-0 z-10 border-t … bg-white" data-testid="chat-composer">` (with T1.1 comment block above at L1598–L1604)
- Spec ref: §4.D → X2.
- Action: none (shipped before this sprint).

### T1.3 — Context switch lands on Home — **Confirmed on disk (no change)**
- `frontend/src/contexts/AuthContext.jsx`:
  - L246–L248: `switchContext` non-modal branch hard-navigates to `/app`.
  - L253–L265: `dismissSwitchModal` hard-navigates to `/app` after closing the role-change modal.
- Spec ref: §4.A → D1.
- Action: none (shipped before this sprint).

### T1.4 — Generate Brief button visibility + failure toast — **Implemented**
- **Root cause**: `.akki-overline` in `frontend/src/index.css` L165–L172 sets `color: var(--oxblood)` and is declared AFTER `@tailwind utilities`, so it silently overrode the Tailwind `text-white` on the Generate-Brief button (same specificity, later in the cascade). Button text was rendering dark warm-tone on the accent fill → invisible against the warm accent.
- **Fix (visibility)** — `frontend/src/components/reading/ReadingTopBar.jsx` L96–L111: removed `akki-overline` from the button className; replaced with `uppercase font-semibold` (Tailwind utilities, no color override). `text-white` now wins.
- **Fix (failure toast — G3 ratified verbatim)** — `frontend/src/pages/ReadingView.jsx` L298–L304: catch-block toast now reads exactly *"We couldn't generate a brief from this document. Please try again."* The button is re-enabled via the existing `finally { setGeneratingBrief(false); }` block, satisfying the D8 "re-enable on failure" requirement.
- Spec ref: §4.A → D8 + §6 G3.

### T1.5 — "All documents" routing — **Implemented**
- **Fix** — `frontend/src/components/home/HeroDocActions.jsx` L60–L62: changed `to="/app/work-studio"` → `to="/app/workspace"`. Updated the doc-comment block at L14–L16 to cite spec D2.
- **Route confirmed** — `frontend/src/App.js` L280 already registers `<Route path="/app/workspace" element={<Workspace />}/>`. `Workspace.jsx` is the canonical Document Journal listing surface.
- Spec ref: §4.A → D2.

### T1.6 — Add to Cycle (G1 ratified) — **Implemented**
- **Modal rewritten** — `frontend/src/components/documents/DocumentRoutingActions.jsx` (full file rewrite of the cycle path; Solva and Work Studio paths untouched). Replaced the agenda-item picker with a Select-Cycle dropdown:
  - Loads cycles in two parallel `GET /api/contexts/{cid}/cycles?status=active|draft` calls (page_size=60) and merges client-side.
  - Renders a `<select>` with one row per cycle, each labelled `Title (active|draft)`.
  - POSTs G1 verbatim payload `{cycle_id, kind: "document", source_doc_id, title}` to `/api/contexts/{cid}/cycle/contributions?cycle_id=<selected>`. `agenda_item_id` and `team_member_id` are intentionally omitted — document attaches at cycle root.
  - On success: `toast.success(\`Your document has been added to Cycle Manager in ${cycleName}.\`)` (verbatim D6) → navigate to `/app/cycle?attached=<cycleId>`.
  - On failure: status-aware human-readable toasts for 423 (cycle locked), 422 (validation), 400 (generic bad request), with the D6-verbatim generic fallback *"We couldn't add this document to the cycle. Please try again."*
- **Pulse highlight wired** (D6 step 5):
  - `frontend/src/pages/cycle/CycleList.jsx`: reads `?attached=<cycleId>` from URL; passes `highlight={c.id === attachedCycleId}` to each CycleCard; clears the query param 1.7 s after arrival so refresh/back doesn't re-pulse; force-flips to All tab if user was on a different filter.
  - `frontend/src/components/cycle/CycleCard.jsx`: accepts `highlight?: boolean`; applies the `cycle-card-pulse` class + a `data-pulse="true"` attribute when truthy.
  - `frontend/src/index.css`: added `@keyframes cycle-card-pulse-kf` + `.cycle-card-pulse` rule running 0.5 s × 3 iterations (3 gentle pulses then settle, per spec "2–3 gentle pulses").
- Spec ref: §4.A → D6 + §6 G1.

---

## Tests written and run

- `backend/tests/test_t1_add_to_cycle_g1.py` — 4 backend tests asserting the G1 wire format, cycle_id routing, the QA-2026-05-16-021 invariant still rejects empty payloads with 422, and the active+draft listing shape used by the modal.
- `backend/tests/test_t1_frontend_wire.py` — 7 file-source assertions on T1.4 / T1.5 / T1.6 frontend invariants (className value lacks `akki-overline`, G3 verbatim toast present, `/app/workspace` route wired, G1 payload shape literal, status-aware error toasts present).

Run results (24 May 2026):

```
$ pytest backend/tests/test_t1_add_to_cycle_g1.py backend/tests/test_t1_frontend_wire.py -v
======================== 11 passed, 7 warnings in 2.88s ========================

$ pytest backend/tests/test_cycle_feel_pass.py backend/tests/test_cycles_v2.py backend/tests/test_cycle_manager_actions_tab.py -q
24 passed, 7 warnings in 3.70s
```

Existing cycle test suite (24 tests) regression-clean after the change.

---

## Spec invariants check

| Invariant | Status | Where |
| --- | --- | --- |
| G1 wire format used verbatim | ✅ Used literally | `DocumentRoutingActions.jsx` L98–L116; covered by `test_t1_add_to_cycle_g1.py::test_g1_wire_format_accepted_and_persists` |
| G3 toast wording verbatim | ✅ Used literally | `ReadingView.jsx` L302; covered by `test_t1_frontend_wire.py::test_t1_4_generate_brief_failure_toast_is_g3_verbatim` |
| G6 PPTX format NOT touched | ✅ Confirmed not pulled forward | No changes under `Compile` flow; T2/T3 scope. |
| T1.2 regex (`/T:[a-zA-Z_0-9]+/`, `/\[T:/`) | ✅ Untouched | Per PO instruction — e1_tester swept 4/4 PASS on 24 May 2026. |

