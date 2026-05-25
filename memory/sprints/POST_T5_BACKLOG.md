# POST-T5 Backlog

This file collects out-of-scope observations surfaced during T1–T5 implementation. Nothing here is acted on until after T5 completes. Each entry: discovery date · sprint where it surfaced · brief note · pointer.

---

## T1 (24–25 May 2026) — no items
T1 ran clean against the spec. No off-scope issues surfaced.

## T2 (25 May 2026) — seed-data coverage gap

- **Seed-data gap** — at least one objective + one project should have populated `supporting_docs` for future Citations link rendering tests. (Surfaced during T2.3 re-verification 2/2 PASS + 1 SKIP — the SKIP was because no live row produced supporting docs after an Update assessment.)
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Consolidated under the T5 section below (same fix). See `demo-t5backlog-obj-001` + `demo-t5backlog-prj-001`.

## T2 (25 May 2026) — 1 deferred item

## T3 (25 May 2026) — optional spot-check

- **EICAR spot-check** — Optional human EICAR spot-check on Compile modal nested upload to live-verify G9 ClamAV reject path. Not blocking; e1_tester verified the toast wording in source.
  - **2026-05-25 (backlog-b chunk) — RE-PARKED.** Attempted live spot-check; `supervisorctl status` reports `clamd: STOPPED` in the preview environment (production stance — clamd is a sidecar that's not running here). `clamav_service.scan()` therefore raises `ClamAVUnreachable` → 503 instead of producing the `INFECTED + signature` reply needed to exercise the G9 reject path. Re-parked until a follow-on environment with clamd live.


## T4 (25 May 2026) — seed-data gap

- **Compiled Board Pack / Committee Pack with non-null `structured_content`** missing from seed. Manual compile required to demo G6 downloads end-to-end. Recommend adding 1-2 seeded compiled artefacts (`work_studio_exports` rows with rich `structured_content.sections`) for future tester coverage. Not blocking.
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Seeded by `/app/backend/scripts/seed_backlog_b_demo.py`. One Board Pack (`demo-t5backlog-bp-001`, lifecycle=committed) + one Committee Pack (`demo-t5backlog-cp-001`, lifecycle=draft) in Bramuel's Tuli CFO executive context. Idempotent, marker `seed_marker = "DEMO_T5_BACKLOG"`. 3 sections each. Test: `tests/test_backlog_b_seed.py::test_t4_gap_board_pack_has_non_null_structured_content` + `…_committee_pack…` GREEN.

## T5 (25 May 2026) — seed-data gap + deferred LLM step

- **Seed-data gap — Cycle compilation** — one Cycle Manager cycle should be seeded with a compiled `work_studio_exports.structured_content` (kind=`cycle_board_pack`) so the C5 Cycle Page download click-path is browser-observable end-to-end. Same gap pattern as T4 (Board/Committee Pack seed gap). The render endpoint itself is verified GREEN at the wire layer; only the live click-through demo is gated.
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Seeded by `/app/backend/scripts/seed_backlog_b_demo.py`. One cycle (`demo-t5backlog-cycle-001`, status=active, readiness_pct=95 vs target 85) + one linked compilation (`demo-t5backlog-cycle-compile-001`, kind=cycle_board_pack, 3 sections) in Bramuel's Tuli NED context. Test: `tests/test_backlog_b_seed.py::test_t5_gap_cycle_has_linked_compilation_with_structured_content` GREEN.

- **T2.3 seed-data gap (re-parked here for consolidation)** — at least one objective + one project should have populated `supporting_docs` for future Citations link rendering tests.
  - **2026-05-25 (backlog-b chunk) — CLOSED.** Seeded by `/app/backend/scripts/seed_backlog_b_demo.py`. Objective `demo-t5backlog-obj-001` + Project `demo-t5backlog-prj-001` in Bramuel's Tuli NED context. Each carries `last_akki_assessment.supporting_docs` resolving to 2 real (non-orphan) document references from the existing Tuli strategic-pack mirror. Tests: `tests/test_backlog_b_seed.py::test_t2_3_gap_objective_supporting_docs_resolves_at_least_two` + `…_project…` + `…does_not_create_orphan_doc_references` GREEN.

- **C4 Project Brief LLM step deferred** — the wizard ships with the direct create-and-commission path. The full C4 Review / Save-as-Draft branches (with Shield-routed agent-cycle summary regeneration via `llm_router.invoke()` + `deidentifier.deidentify()`) are not in this tier. Follow-on sprint should add the brief-generation endpoint + the `Review` + `Save as Draft` CTAs alongside `Commission Cycle`.

## Backlog-b deployment-pipeline gap (25 May 2026) — LOW PRIORITY

- **Demo seeds are NOT auto-applied on preview pod boot.** During the backlog-b verification, e1_tester had to manually run `cd /app/backend && python -m scripts.seed_backlog_b_demo` on a fresh preview pod. The seed itself is idempotent and safe; the gap is procedural.
  - **Park decision** (deferred to future sprint): *"Decide whether demo seeds should auto-apply on preview pod boot (e.g. via an idempotent startup hook), or remain manual to keep prod-like environments lean."* Defensible both ways:
    - **Auto-apply** — faster tester ramp-up, predictable demo state.
    - **Manual** — keeps preview pods prod-like, avoids leaking `[DEMO]` rows into any audit chain by accident.
  - Decision intentionally NOT made in backlog-b. Owned by a future sprint that scopes the demo-pipeline question.



- **X4 — Remove Monitor objective/project filter tabs** (`AKKI_PRODUCT_SPEC.md` v1.1 L687–L695). The user's T2 scope named only "Monitor drawer redesign" (X5) and explicitly excluded Strategic Goals (X6–X8 covered separately). X4 removes the RAG filter tabs on the *Objectives & Projects* listing panel itself — not the drawer. Strictly outside T2.3 by the user's own wording, so deferred. Surface to revisit during a follow-on sprint focused on Monitor listing UX. Spec text: *"delete the filter tabs circled in figure 6 and figure 7."*
  - File that would be touched: `frontend/src/components/monitor/ObjectivesProjectsPanel.jsx` (filterTabs L539–L548 + `<ListingShell filterTabs={filterTabs}>` prop at L658).

