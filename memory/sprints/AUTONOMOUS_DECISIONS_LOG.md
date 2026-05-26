# Autonomous-mode Decisions Log

This log records orchestrator-delegated autonomous decisions made by the
agent without per-task user approval. Each entry includes the trigger,
the decision, the rationale, and the reversal path so the orchestrator
can re-direct on return.

---

## 2026-05-26 — E.3 scope compliance authorized under autonomous mode

- **Trigger:** User delegated autonomous control with the standing rule
  *"Ensure scope compliance now, unless it compromises system or
  journey."* Original dispatch surfaced as the orchestrator scope-
  compliance brief returned right after Phase E.3 initial report.
- **Decision:** Authorize all 3 scope cuts to close in the same pass:
  1. Prompt-based edit apply pipeline (Shield-bounded LLM rewrite + diff
     preview).
  2. DRAFT watermark embed for PDF / DOCX / PPTX exports (ratify the
     dormant `watermark_service.py`; flip the export-guard from
     unconditional block to conditional pass-with-watermark + block-on-
     failure fallback).
  3. Related-docs typing (4 buckets — metadata_match, content_similarity,
     explicit_attachment gap, canonical_lineage gap — surface gaps
     honestly).
- **Rationale:** Each of the 3 cuts is spec-explicit in the original
  E.3 brief. None compromise system invariants:
  - All LLM calls still route through Shield (`shield_invoke`); no
    `emergentintegrations` direct import added.
  - Watermark libs (`reportlab`, `pypdf`, `python-docx`, `python-pptx`)
    are already in `requirements.txt` — no new packages.
  - Blocking remains the spec-compliant fallback path when watermarking
    fails (HTTP 503 with `code=DRAFT_WATERMARK_FAILED`).
- **Reversal:** User can override any of the 3 on return; each cut is
  independent. To revert any item, see the surgical-diff anchors in the
  HOME_CLEANUP_LOG.md "E.3 — scope compliance" subsection.
- **Surface:** orchestrator message dispatching scope-compliance closure.

---

## 2026-05-26 — E.4 legacy-doc-route archive authorized; G8 page flagged borderline

- **Trigger:** Orchestrator dispatched E.4 enumeration + autonomous
  archive under the standing rule *"Clean up any other route that does
  not align with this. All documents are found in Document Journal.
  The drawer is the primary journey to interacting with documents."*
- **Decision:** Archived the legacy `ReadingView` surface, all 7
  reading subcomponents, and the 2 reading hooks. Replaced
  `/app/documents/:id` with a `<Navigate>` redirect to the Universal
  Document Drawer surface (`/app/work-studio?doc_id=:id`). Rewired 3
  explicit doc-click handlers (MentionInbox, AppShell upload,
  CompilationRail Document Journal).
- **Rationale:**
  - Universal Drawer's 5-tab Reference mode (E.3) fully covers the
    ReadingView surface's content contract.
  - Redirect preserves all bookmarks + 13+ in-code `<Link>` /
    `href="/app/documents/…"` references without urgent rewiring.
  - No active code imports any of the archived files (grep-verified
    before move).
- **BORDERLINE (kept):** `/app/work-studio/document/:artefactId` +
  `pages/WorkStudioDocumentPage.jsx`. This route binds the
  G8-ratified full-page surface for Board Packs + Committee Packs
  (T3.3 / 2026-05-25). The directive *"drawer is the primary
  journey"* would archive it, but G8 was a deliberate prior
  ratification choosing full-page over overlay. Archiving would erase
  a previously-approved user decision. **Kept as-is**; user input
  would resolve whether to fold Board/Committee Packs into the drawer
  as well or maintain the G8 full-page exception.
- **Reversal:** to restore the archived surface, `git mv
  frontend/src/_archived/e4_doc_routes/pages/ReadingView.jsx
  frontend/src/pages/`, restore the reading subcomponents and hooks
  the same way, and re-point `DocumentRouteSwitch` in `App.js` back
  to `<ReadingView />`. The 3 click-handler rewires are isolated
  one-line changes and easy to revert independently.
- **Surface:** orchestrator E.4 dispatch + Phase F kickoff message.

---

## 2026-05-26 — F.1+F.2 dispatched under autonomous mode; collection rename deferred

- **Trigger:** Orchestrator paired-dispatched E.4 archive + Phase F
  kickoff (F.1 rename + F.2 listing/wizard) under continued autonomous
  authority. F.3–F.6 explicitly queued.
- **Decision (rename scope):** UI-level rename only. Routes, nav
  labels, URL params (with `cycle_id` → `task_id` alias). The MongoDB
  `cycles` collection is NOT renamed.
- **Borderline call — collection rename:** The orchestrator brief said
  *"if there's a `cycles` collection, rename to `tasks` with a Mongo
  `renameCollection` migration."* On inspection: the existing `cycles`
  collection serves the legacy Reporting Cycle surface (close dates,
  checklists, reportee submissions, reports). The new Phase F `tasks`
  collection has a structurally distinct schema (objective,
  success_criteria, output_spec, team[], contribution_mode). They are
  semantically different objects. A `renameCollection` migration
  would couple two unrelated concepts and force a schema rewrite on
  all `cycle*` routers (3,700 lines). **Conservative choice:**
  introduce `tasks` collection FRESH; leave `cycles` untouched. Both
  surfaces coexist (legacy `/app/cycle` continues to render the
  legacy CycleList listing for now). If the orchestrator wants the
  two unified, that's a follow-up data-model phase.
- **Borderline call — `agent-prefill` LLM fallback:** When Shield
  invocation fails, the endpoint returns a generic objective +
  success-criteria pair (`source:"none"`) so the wizard is never
  blocked. The conservative call here is to never let an upstream
  LLM outage gate user workflow. Audit-traceable via the response's
  `source` field.
- **Reversal:** all routes and labels are isolated; revert by:
  1. Restoring the old nav labels in `AppShell.jsx`.
  2. Removing the `/app/task-manager` routes from `App.js`.
  3. (Optional) deleting `pages/TaskManager.jsx`,
     `components/tasks/`, `routers/tasks.py`,
     `tests/test_home_cleanup_phase_f.py`.
  4. The `tasks` collection survives until manually dropped.
- **Surface:** orchestrator E.4 + Phase F kickoff dispatch.

---

## 2026-05-26 — F.3 locked-in autonomous picks (orchestrator-confirmed)

The orchestrator returned and **locked** the borderline calls from
prior entries before dispatching F.3:

1. **G8 Board/Committee Pack (E.4 borderline):** STAYS as full-page
   surface. Do not refactor into the Universal Document Drawer.
   `pages/WorkStudioDocumentPage.jsx` + `/app/work-studio/document/:artefactId`
   route preserved indefinitely.
2. **`cycles` MongoDB collection (F.1 borderline):** STAYS coexisting
   with the new `tasks` collection. No `renameCollection` migration.
   The two surfaces are semantically distinct objects and remain so.
3. **Email send transport (F.5 forward-look):** **Postmark** with the
   user's existing API key. Audit rows continue to be the durable
   record; live send wires when F.5 ships.

These are now locked decisions, not pending borderline calls.

---

## 2026-05-26 — F.3 in-flight decisions

- **`<EntityDrawer>` base extraction:** orchestrator suggested
  extracting genuinely shared chrome from `DocumentDrawer` into a
  shared base if there's clean reuse. On inspection the chrome
  *looks* shareable but the inner state machine (mode selectors,
  tab routers, content sourcing) is bespoke per entity. **Decision:**
  compose, do NOT extract a base class today. Premature abstraction
  risks. `TaskDrawer` and `DocumentDrawer` share the `<Sheet>`
  primitive from `components/ui/sheet.jsx` (already shared) plus a
  small reused helper `_stripWatermarkOnReader` — that's it. The
  two components stay independently editable.
- **Intelligence LLM Recommendations:** per the brief's "scope cut
  allowed" clause, the LLM-voiced Recommendations bullet ships with
  a rule-based fallback. If Shield fails, the section renders rule-
  derived prose ("Sarah's contribution is overdue by 3 days")
  WITHOUT the LLM polish; tab still functional. No silent gaps.
- **Share-task tracking:** ports the DocumentDrawer pattern
  (`ShareDocumentModal` → `engagement` endpoints). Minimal initial
  ship: link-copy + audit row via `task.shared` event. Engagement
  metrics surface from the existing `/engagement` listing if a row
  is present.

