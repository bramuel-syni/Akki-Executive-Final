# T2 Implementation Log

Spec contract: `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (Ratified 24 May 2026).
Scope: T2 = "Surface UX upgrades" — 4 items:
1. Document Journal filter tabs (D3, D4)
2. Pulse Resolved tab (X3)
3. Monitor drawer redesign (X5)
4. Strategic Goals filters with G11 + G12 ratified
Scope-out → `/app/memory/sprints/POST_T5_BACKLOG.md`.

---

## Pre-tier hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-T2` → commit `a0f2f54457928239a718a72a74ec9fa3c929f46a` | 2026-05-25T05:38:00Z |
| Mongo dump | `/app/backup/pre_T2_20260525T053810Z/akki_dev/` (237 bson + metadata files, 63 MB) | 2026-05-25T05:38:10Z |

Note: tag local-only. `git push origin v-pre-T2` requires the user's "Save to Github" feature.

---

## T2.3 RE-OPEN — Tester 1/4 FAIL on 2026-05-25

**False-green diagnosis (do NOT repeat this pattern):**

The first T2.3 implementation shipped the new layout in source, but **three of the five sections were behind conditional render gates**:

1. **Description card** — wrapped in `{row?.description && (...)}`. Test rows without a `description` field never rendered it. Source position was correct (between Status Card and Update CTA), but DOM emission depended on data.
2. **Citations card** — wrapped in `{assessment && !noData && (assessment.supporting_docs || []).length > 0 && (...)}`. The user has to (a) click Update, (b) receive an assessment with non-empty supporting_docs. First-time-open drawers therefore never showed the card.
3. **"Upload Document" empty-state button** — nested inside `{noData && (...)}`, which only sets when the backend explicitly returns `{no_data: true}`. On a happy-path Update or a fresh drawer, the button was unreachable.

The tester (correctly) observed the rendered DOM had only Status-grid + Update CTA + Timeline, with Description / Citations / Upload all missing. My prior diff narrative was technically correct ("sections added in spec order") but practically empty because the gates dropped them at render time. **Lesson: spec-required sections MUST emit DOM unconditionally; only their internal content is data-conditional. Empty states are part of the contract, not a fallback.**

**Component identity check:** `ObjectivesProjectsPanel.jsx` IS the live drawer for both objective and project rows. There is exactly one drawer file in `frontend/src/components/monitor/` — confirmed by `grep "Trend"`, `grep "Score" label`, and `find -iname "*drawer*"`. No sibling/legacy drawer routed to.

**Status Card scope clarification from PO:** the prior 3-column grid (Status / Score / Trend cells) is being collapsed to a single Status pill per the fix-scope directive. The score + trend info is no longer rendered in dedicated drawer cells; the Status badge alone carries the lifecycle state.

---

## T2.3 fix — 2026-05-25

**Files changed:**
- `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` — drawer body:
  - **Status Card** flattened: 3-column grid (Status / Score / Trend) replaced by a single labelled status pill. Score and Trend cells removed. The pill uses the existing `RAG_LABEL` mapping.
  - **Description card** now renders unconditionally with placeholder copy when the row has no description.
  - **Citations Card** now renders unconditionally beneath the Update CTA. Two modes:
    - When `supporting_docs.length > 0`: renders each as `<a href="/app/documents/{id}">{name}</a>` per the fix-scope directive.
    - When empty (no assessment yet OR assessment returned zero docs): renders an explanatory line + `Upload Document` button that triggers a real hidden `<input type="file">` picker. Wired through to the existing `onUploadAndReassess` flow (POST `/contexts/{cid}/documents` → re-run assessment).
  - The old `{noData && ...}` block (Document-Journal-empty branch) collapses into the new always-on Citations Card empty state — single source of truth for "upload more grounding material".
- `backend/tests/test_t2_frontend_wire.py` — added new regression tests asserting Description / Citations / Upload-button are emitted unconditionally (no data gate) so a future false-green diff fails the test, not the tester.



### T2.1 — Document Journal filter tabs (D3 + D4)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L127–L159 (§4.A → D3 + D4).

**Files changed:**
- `backend/routers/documents.py` — `sanitize_doc` (L32–L82) now surfaces `source_channel` + `doc_kind` so the listing payload carries enough signal to derive origin client-side. No new endpoint.
- `frontend/src/pages/Workspace.jsx`:
  - Added a parallel `GET /contexts/{cid}/briefings` to the existing docs fetch (Promise.all). Briefings live in `db.boardpacks` so they need to be merged client-side.
  - Added `deriveOrigin(d)`: `source_channel ∈ {cycle_compilation, work_studio_export} → "akki_generated"`, everything else → `"uploaded"`. Briefings are tagged `"briefing"` at the merge step.
  - `listingRows` now merges docs + briefings, sorted newest-first, each row carrying `origin`. Briefing IDs are prefixed `briefing-<id>` to avoid collisions.
  - Added `tabCounts` (live) + `filteredRows` (filter applied) + `filterTab` state defaulting to `"all"` per D3 step 4.
  - Rendered the 4-tab strip below the search box — All / Uploaded / Akki Generated / Briefings — with live counts. Tabs are suppressed while a search query is active (search is the global filter).
  - Added an "empty after filter" state distinct from the "no documents at all" state.
  - Added origin badge to the listing row meta line (D4 step) and to the drawer's meta line (D4 drawer rule).

### T2.2 — Pulse Resolved tab (X3)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L674–L685 (§4.D → X3).

**Files changed:**
- `frontend/src/pages/Pulse.jsx` — `SignalCard`'s headline+body block (the line just below the headline) now routes through the existing `splitToBullets(card.summary)` helper (which calls `stripCitations` internally). Single-point bodies render as a paragraph, two-or-more points render as a `<ul>` of bullets. The card-level `pulse-card-summary-${id}` testid is preserved; each bullet adds `pulse-card-summary-bullet-${id}-${i}`.

**Note:** The Resolved tab (X3 step 1) was already present on `Pulse.jsx` (L38–L43) — confirmed shipped. The Resolved tab + the bulleted card body + the citation strip together satisfy X3 in full.

### T2.3 — Monitor drawer redesign (X5)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L697–L719 (§4.D → X5).

**Files changed:**
- `backend/routers/monitor_status_assessment.py` — between L340 and L380, the `update-status` endpoint now resolves `supporting_doc_ids` → `supporting_docs: [{id, name}]` via a single `db.documents.find` lookup and includes it on `last_akki_assessment`. Order preserved, missing IDs dropped. Citations Card needs names, not IDs.
- `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` — `ItemDrawer` fully reordered to match X5:
  - **Status Card** unchanged at top.
  - **Description** moved directly below the Status Card (was previously beneath the Akki Status subcard).
  - **Akki Status subcard wrapper deleted.** The Update CTA now sits as a single full-width button below the description.
  - Update CTA label is kind-aware: "Update Project" if `row.kind === "project"`, "Update Objective" otherwise.
  - **No-data branch rebuilt**: the previous "Open Document Journal →" link is replaced by an `Upload Document` button that opens a hidden `<input type="file">`. On a successful upload (POST `/contexts/{cid}/documents`), the assessment is re-run automatically so the agent uses the new doc.
  - **Citations Card** (new) sits between the assessment block and the Timeline. Renders only when the latest assessment carries at least one supporting doc. Each row shows the resolved doc `name` as a hyperlink to `/app/documents/{id}`.
  - **Timeline** unchanged at bottom.

### T2.4 — Strategic Goals filters (X6 G11 + X8 G12)
Spec ref: `AKKI_PRODUCT_SPEC.md` v1.1 L722–L766 (§4.D → X6, X7, X8 + §6 G11 + G12).

**Files changed:**
- `frontend/src/components/monitor/StrategicGoalsPanel.jsx`:
  - **X6 G11 ratified dual RAG bars**: added `statusBarClass(status)` mapping (On Track/Achieved → green, At Risk → amber, Off Track → red) and `probabilityBarClass(value)` mapping (≥70 green, 40–69 amber, <40 red — literal G11 thresholds). The `GoalRow` Performance bar swapped from `cat.bar` (category colour) to `statusBarClass(goal.status)`. The Probability bar swapped from `"bg-[var(--ink)]"` to `probabilityBarClass(prob)`. The two bars now paint independently.
  - **X8 status filter tabs**: added `STATUS_FILTER_TABS` constant (6 entries, verbatim spec order). A horizontal tab strip renders above the goal groupings with live per-status counts derived from the role-filtered + category-filtered set.
  - **X8 category dropdown**: added `deriveCategoryOptions(goals)` — distinct `g.department` for the active context; fallback to G12 verbatim list `["Operations", "People", "Compliance", "Product", "Commercial"]`. Dropdown sits on the right of the filter row.
  - Filters combine: the `filtered` useMemo applies both `statusFilter` and `categoryFilter`.
  - Added a "no goals match this filter" state distinct from the empty-goals state.

---

## Tests written and run

- `backend/tests/test_t2_backend.py` (3 tests) — verifies `sanitize_doc` exposes `source_channel`, the `supporting_docs` resolution block returns id+name and drops missing IDs, and the endpoint emits `supporting_docs` literally.
- `backend/tests/test_t2_frontend_wire.py` (16 tests) — file-source assertions covering D3 tab order, default tab, Akki channel constants, parallel fetch, drawer meta origin badge; Pulse `splitToBullets` wiring; Monitor drawer block order, kind-aware button label, no-data upload affordances, "Akki status" label removed, Citations card uses names; Strategic Goals 6-tab order, G11 thresholds, dual-bar independence, G12 fallback verbatim, combined filter logic.

Run results (24 May 2026):

```
$ pytest backend/tests/test_t2_backend.py backend/tests/test_t2_frontend_wire.py -v
======================== 19 passed, 7 warnings in 2.83s ========================

$ pytest backend/tests/test_t1_add_to_cycle_g1.py backend/tests/test_t1_frontend_wire.py \
         backend/tests/test_t2_backend.py backend/tests/test_t2_frontend_wire.py \
         backend/tests/test_cycle_feel_pass.py backend/tests/test_cycles_v2.py \
         backend/tests/test_iter28_strategic_goals.py \
         backend/tests/test_patch_5_monitor_v2.py \
         backend/tests/test_patch_6_pulse_synisense.py -q
55 passed, 13 skipped, 7 warnings in 4.65s
```

13 skipped are pre-existing skips in `test_iter28_strategic_goals.py` (architectural deferral documented in the file — unrelated to T2).

---

## Spec invariants check

| Invariant | Status | Where |
| --- | --- | --- |
| G11 thresholds verbatim (≥70 / 40–69 / <40) | ✅ Literal | `StrategicGoalsPanel.jsx` `probabilityBarClass` — covered by `test_t2_4_x6_g11_probability_thresholds_are_verbatim` |
| G12 dynamic source + fallback list verbatim (`["Operations","People","Compliance","Product","Commercial"]`) | ✅ Literal | `StrategicGoalsPanel.jsx` `G12_FALLBACK_CATEGORIES` + `deriveCategoryOptions` — covered by `test_t2_4_x8_g12_category_filter_dynamic_with_fallback` |
| Copy verbatim from spec | ✅ | D3 labels (All/Uploaded/Akki Generated/Briefings), D4 origin tags (Uploaded/Akki Generated), X5 button labels (Update Objective/Update Project), X8 status tab labels — all literal |
| No guardrail files modified | ✅ | `git diff --name-only HEAD` excludes `backend/services/synisense/**`, `backend/services/clamav_service.py`, `backend/routers/inbound_email.py`, `backend/routers/trust_center.py`, `backend/routers/admin_audit_invariant.py`. `monitor_status_assessment.py` IS modified but it's not a guardrail file — it's the Monitor assessment endpoint (already Shield-routed; we only added doc-name resolution for the response). |
| No T3/T4/T5 scope pulled forward | ✅ | Compile flow untouched (G6 PPTX deferred). Cycle wizard untouched. Work Studio drawer/page (W3/W4/W5) untouched. |

