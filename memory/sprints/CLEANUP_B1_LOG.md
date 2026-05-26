# Cleanup — Bucket 1 Log

**Dispatched:** 2026-05-26 (post-LEGACY_CONFLICT_LEDGER audit).
**Snapshot tag:** `v-pre-cleanup-bucket-1` (local-only).
**Mongo dump:** `/app/backup/pre_cleanup_b1_20260526T012123Z/akki_dev/` (84 MB).
**Brief:** Archive items in `LEGACY_CONFLICT_LEDGER.md` where (a) the canonical spec supersedes, (b) grep proves 0 live importers/callers, (c) hard rules met (no refactor, no spec edits, pytest stays green).

---

## Reference-check corrections to the original ledger

Reviewing each Category 1 row against grep evidence BEFORE archiving exposed three misclassifications in `LEGACY_CONFLICT_LEDGER.md`. Per hard rule *"If something does, leave it and escalate that row"* — these rows are NOT archived in this pass.

| Ledger row | Original verdict | Reference-check finding | Updated action |
| --- | --- | --- | --- |
| 1.1 | `escalate` (claimed dependencies) | `NAV`, `DEPTH_NAV`, `MANAGE_NAV` arrays ARE actively rendered at `AppShell.jsx:733` (`{NAV.filter(...).map(...)}`), `:804` (`{DEPTH_NAV.map(...)}`), `:854` (`{MANAGE_NAV.map(...)}`). The comment at lines 84–87 saying *"rendering of the left aside has been removed in Phase 13.3"* is stale — the rendering IS present. | **leave + escalate**. Comment is misleading; arrays are not dead. |
| 1.2 + 1.3 | `escalate` (Solva legacy session UI + router) | Phase E CLOSEOUT.md line 18 explicitly says: *"Seed-bearing flows (cycle / work-studio / document-journal handoffs) continue to use the legacy /app/solva/session/new until Phase E.5 wires seed support into the new framing endpoint."* Phase E.5 has not shipped. Live deps confirmed in: `lib/takeToSolva.js`, `lib/solvaPhaseDClient.js`, `components/sandbox/v2/Step1SolvaWrapper.jsx`, `components/studio/SourceStep.jsx`, `components/documents/DocumentRoutingActions.jsx`, `components/chat/AuditPanel.jsx`, `components/solva/SolvaLanding.jsx:395`. Soft-archive endpoint (`POST /api/admin/solva/legacy/soft-archive`) archives ORPHAN DB ROWS, not the code. | **leave + escalate**. Archive blocked until Phase E.5 ships seed support on the Phase D framing endpoint. |
| 1.8 | `escalate` (work_studio_phase_c/c2 routers) | Live deps confirmed: `components/studio/SourceStep.jsx:346,405` calls `/work_studio/picker` + `/work_studio/exports`; `components/studio/EnhanceModal.jsx:222,223,248,255,283` calls `/work_studio/briefs/{id}/...`. | **leave + escalate**. |

---

## Archive actions executed in this pass

Per the user's "go" directive on Bucket 1 + ledger rows where supersedence is clean AND grep proves 0 live importers/callers.

### Frontend pages — unreachable

| # | source path | archived path | supersedence evidence |
| --- | --- | --- | --- |
| 1 | `frontend/src/pages/SolvaLanding.jsx` | `frontend/src/_archived_legacy/pages/SolvaLanding.jsx.archived` | App.js line 20 `lazy(() => import("@/pages/SolvaLanding"))` but no `<SolvaLanding />` JSX in any `<Route element=…>`. Marketing `/solva` route at line 222 binds to `WebsiteProductSolva`. The COMPONENT (`@/components/solva/SolvaLanding`) is the rendered one — used by `SolvaApp.jsx:77`. The page wrapper is unreachable. App.js lazy import removed in the same step. |

### Frontend pages — legacy sandbox

| # | source path | archived path | supersedence evidence |
| --- | --- | --- | --- |
| 2 | `frontend/src/pages/SandboxV2.jsx` | `frontend/src/_archived_legacy/pages/SandboxV2.jsx.archived` | App.js line 262 comment: *"Phase J (2026-05-12): /sandbox is now the new Generative Sandbox MVP. The legacy guided tour (SandboxV2) moved to /legacy-sandbox for back-link compatibility."* — 30-day forensic-fallback window long elapsed. New `/sandbox` route at App.js:264 binds to `SandboxApp` (`@/sandbox/SandboxApp`). `/legacy-sandbox` + `/legacy-sandbox/resume` routes removed; App.js lazy import removed. |

### Frontend components — confirmed 0 live importers

Grep recipe used: `grep -rln "import.*<Name>\b" frontend/src/ | grep -v "/<Name>.jsx"`.

| # | source path | archived path | importer count |
| --- | --- | --- | --- |
| 3 | `frontend/src/components/cycle/ReportsTab.jsx` | `frontend/src/_archived_legacy/components/cycle/ReportsTab.jsx.archived` | 0 |
| 4 | `frontend/src/components/cycle/CycleTracker.jsx` | `frontend/src/_archived_legacy/components/cycle/CycleTracker.jsx.archived` | 0 |
| 5 | `frontend/src/components/cycle/ReviewInboxCard.jsx` | `frontend/src/_archived_legacy/components/cycle/ReviewInboxCard.jsx.archived` | 0 (only mentioned in `hooks/useDraggableSections.js` JSDoc example — which itself has 0 importers) |
| 6 | `frontend/src/components/cycle/NedInboxTile.jsx` | `frontend/src/_archived_legacy/components/cycle/NedInboxTile.jsx.archived` | 0 |
| 7 | `frontend/src/components/cycle/CycleStrip.jsx` | `frontend/src/_archived_legacy/components/cycle/CycleStrip.jsx.archived` | 0 |
| 8 | `frontend/src/components/cycle/CyclePhaseSheet.jsx` | `frontend/src/_archived_legacy/components/cycle/CyclePhaseSheet.jsx.archived` | Was 1 (CycleStrip — also archived in row 7). Now 0. Transitive orphan, archived in the same step. |
| 9 | `frontend/src/components/cycle/tabs/ActionsTab.jsx` | `frontend/src/_archived_legacy/components/cycle/tabs/ActionsTab.jsx.archived` | 0 |
| 10 | `frontend/src/components/cycle/tabs/BoardpackTab.jsx` | `frontend/src/_archived_legacy/components/cycle/tabs/BoardpackTab.jsx.archived` | 0 |
| 11 | `frontend/src/components/cycle/tabs/MinutesTab.jsx` | `frontend/src/_archived_legacy/components/cycle/tabs/MinutesTab.jsx.archived` | 0 |
| 12 | `frontend/src/components/cycle/tabs/SignalsTab.jsx` | `frontend/src/_archived_legacy/components/cycle/tabs/SignalsTab.jsx.archived` | 0 |
| 13 | `frontend/src/components/lens/AllLensesModal.jsx` | `frontend/src/_archived_legacy/components/lens/AllLensesModal.jsx.archived` | 0 |
| 14 | `frontend/src/components/depth/DepthOfferCard.jsx` | `frontend/src/_archived_legacy/components/depth/DepthOfferCard.jsx.archived` | 0 |
| 15 | `frontend/src/components/streaming/StreamingShell.jsx` | `frontend/src/_archived_legacy/components/streaming/StreamingShell.jsx.archived` | 0 (`lib/clauseStream.js` only referenced from `lib/clauseStream.test.js` — same orphan profile) |

### Tests — contradicting current contract

| # | source path | archived path | supersedence evidence |
| --- | --- | --- | --- |
| 16 | `backend/tests/test_iter22_billing_schedule.py` | `backend/tests/_archived_coverage_loss/test_iter22_billing_schedule.py.archived` | Asserts `body["url"].startswith("https://checkout.stripe.com/")` at line 98. Superseded by `test_chunk_c_billing_coming_soon.py` which asserts the EXACT OPPOSITE: every billing endpoint returns `coming_soon: true`, `/checkout` returns `coming_soon: true` and *"NEVER a Stripe URL"*. Per chunk (c) Stripe Coming Soon. Archive README updated with this rationale. |

### Route source-switch — `/api/help/features`

| # | file | change | supersedence evidence |
| --- | --- | --- | --- |
| 17 | `backend/routers/help.py` | `_FEATURES_DOC` path changed from `/app/memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` → `/app/memory/AKKI_PRODUCT_SPEC.md`. Endpoint kept alive; document body source switched. | `AKKI_PRODUCT_SPEC.md` v1.1 §1.4 (verbatim): *"The legacy AKKI_FEATURES_AND_FUNCTIONALITY.md has no authority."* User preferred option: *"switch it to serve AKKI_PRODUCT_SPEC.md (preferred — keeps the route alive)."* |

### Auxiliary App.js updates

| # | change |
| --- | --- |
| 18 | App.js — removed lazy import of `pages/SolvaLanding` (line 20). |
| 19 | App.js — removed lazy import of `pages/SandboxV2` (line 75). |
| 20 | App.js — removed `/legacy-sandbox` and `/legacy-sandbox/resume` route declarations (lines 265–266). |

---

## Anti-false-green test

`backend/tests/test_cleanup_b1_invariants.py` — pins every cleanup. Each anchor fails against `v-pre-cleanup-bucket-1` and passes post-cleanup.

| # | test name | invariant |
| --- | --- | --- |
| B1.1 | `test_b1_solva_landing_page_archived` | `frontend/src/pages/SolvaLanding.jsx` does NOT exist on disk. Archive at `frontend/src/_archived_legacy/pages/SolvaLanding.jsx.archived` DOES exist. |
| B1.2 | `test_b1_sandbox_v2_page_archived` | Same shape — page archived, archive file present. |
| B1.3 | `test_b1_legacy_sandbox_routes_removed` | `frontend/src/App.js` does NOT contain the string `/legacy-sandbox`. |
| B1.4 | `test_b1_cycle_components_archived` | 9 components in `cycle/` (rows 3–11) are gone from live tree, present under `_archived_legacy/`. |
| B1.5 | `test_b1_solo_components_archived` | 3 components (AllLensesModal, DepthOfferCard, StreamingShell) gone from live tree, present in archive. |
| B1.6 | `test_b1_test_iter22_archived` | `backend/tests/test_iter22_billing_schedule.py` not on disk; archive `.archived` present in `_archived_coverage_loss/`. |
| B1.7 | `test_b1_help_route_serves_product_spec` | `GET /api/help/features` returns content starting with the `AKKI_PRODUCT_SPEC.md` H1 (`# AKKI Product Spec`) AND does NOT contain the `AKKI_FEATURES_AND_FUNCTIONALITY.md` H1 (`# AKKI — Features & Functionality`). |

---

## Guardrails not touched

This cleanup did not modify any file under:
- `backend/services/synisense/shield/`
- `backend/services/clamav_service.py`
- `backend/routers/trust_center.py`
- `backend/services/backfill_shield_v1.py`
- `backend/routers/healthz_shield.py`
- `backend/routers/admin_audit_invariant.py`
- `backend/routers/healthz_clamav.py`

Verified by `git diff --name-only v-pre-cleanup-bucket-1 -- backend/services/synisense backend/services/clamav_service.py backend/routers/trust_center.py backend/routers/admin_audit_invariant.py backend/routers/healthz_* backend/services/backfill_shield_v1.py`.

---

## Pytest counts

| Snapshot | Passed | Failed | Skipped |
| --- | --- | --- | --- |
| `v-pre-cleanup-bucket-1` baseline (post-hardening) | 1248 | 1 (pre-existing `test_real_requirements_file_is_clean`) | 453 |
| Post-cleanup B1 (this commit) | **1266** | 1 (same pre-existing) | 435 |
| Δ | **+18** (all from `test_cleanup_b1_invariants.py`) | 0 | −18 (test_iter22's multiple cases retired from collection) |

**Zero regressions.** The single failure is the unchanged spaCy `requirements.txt` direct-URL flag, parked in `POST_T5_BACKLOG.md` for a future housekeeping pass.

## Tag

`git tag v-post-cleanup-bucket-1 -m "after legacy bucket 1 cleanup — 16 archives + help.py source switch"` (local-only).

## Skipped per "leave + escalate" hard rule

Ledger rows where reference-check found live deps and the archive was NOT performed:
- 1.1 — AppShell NAV / DEPTH_NAV / MANAGE_NAV arrays (actively rendered).
- 1.2 — `frontend/src/pages/SolvaSession.jsx` (legacy seed-bearing handoffs depend on it until Phase E.5).
- 1.3 — `backend/routers/solva_v2.py` (same gate as 1.2; live deps in 6 frontend files).
- 1.4 — `/legacy-sandbox` routes ARE archived in this pass; the underlying SandboxV2.jsx is archived.
- 1.7 — `routers/monitor.py` (v1 back-compat test `test_monitor_v1_compat.py` exists for this).
- 1.8 — `routers/work_studio_phase_c.py` + `work_studio_phase_c2.py` (live callers in `SourceStep.jsx` + `EnhanceModal.jsx`).
- 1.9 — `routers/cycle_config.py` → DEFERRED TO TASK B (cycle-adjacent provenance trace).
- 1.12 — Plays surface → DEFERRED TO TASK B (provenance trace).
- 1.6 — three cycle routers → DEFERRED TO TASK B (provenance trace).

