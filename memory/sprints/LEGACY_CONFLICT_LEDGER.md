# Legacy Conflict Ledger — Read-Only Audit

**Audit dispatched:** 2026-05-25 (post-hardening sprint, post-static-analyzer triage).
**Scope:** Find places where there is BOTH an old implementation AND a newer spec-grounded one of the same thing. Catalog them. Do not fix.
**Hard rules honoured:** READ ONLY. No code changes. No spec edits. No interpretation. Ambiguous rows are tagged `escalate` with the ambiguity noted.
**Canonical authority for "newer / spec-grounded":**
- `/app/memory/AKKI_PRODUCT_SPEC.md` v1.1 (24 May 2026, PO-ratified G1–G12).
- `/app/memory/AKKI_ONBOARDING_SPEC.md` v1.1 (J-series).
- The four QA reports under `/app/memory/sprints/qa_24may2026/` — canonical product journeys per spec §1.
- Closeout logs: `T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md`, `BACKLOG_B_LOG.md`, `HARDENING_LOG.md`.

**Row counts (totals):**

| Category | Rows |
| --- | --- |
| 1. Duplicate feature implementations (live coexistence) | 13 |
| 2. Dead code (defined but never rendered / imported) | 11 |
| 3. Documentation contradicting canonical specs | 10 |
| 4. Tests contradicting current behaviour | 4 |
| **Total** | **38** |

---

## Category 1 — Duplicate feature implementations (live coexistence)

Both an old implementation and a newer (spec-grounded or supersession-named) implementation are present on disk and either both wired or one obviously a remnant from the other.

| # | file_path | what_it_is | what_supersedes_it | recommended_action |
| --- | --- | --- | --- | --- |
| 1.1 | `frontend/src/components/layout/AppShell.jsx` lines 102–115 (`const NAV`) + lines 121–126 (`const DEPTH_NAV`) + lines 130–133 (`const MANAGE_NAV`) | Three left-rail nav arrays. The comment at lines 84–87 states: *"Legacy left-rail surfaces. The arrays are retained because some existing code paths (depth gating, lookup helpers) still reference them; the rendering of the left aside has been removed in Phase 13.3."* | The TOP_NAV array at lines 69–82 is the rendered nav today. | **escalate** — arrays are claimed to be referenced by depth-gating + lookup helpers; need to confirm those references are actually live before deletion. |
| 1.2 | `frontend/src/pages/SolvaSession.jsx` (page) — talks to `/api/solva/v2/*` (per-user, not context-bound) | Pre-Phase-D Solva session UI. App.js comment at lines 84–86: *"Phase D session page wired at a distinct route so the legacy SolvaSession.jsx stays available for pre-Phase-D sessions until the migration in Phase E Sub-task F."* | `frontend/src/pages/SolvaPhaseDSession.jsx` — Phase E Sub-task A (2026-05-16). | **escalate** — Phase E Sub-task F (`/api/admin/solva/legacy/soft-archive`, `backend/routers/solva_phase_e_polish.py` line 60) was implemented and PHASE_E_CLOSEOUT.md line 181 confirms preview pod found 0 orphans. Whether legacy `SolvaSession.jsx` + `/app/solva/session/:sessionId` route should now be retired requires PO call. |
| 1.3 | `backend/routers/solva_v2.py` — legacy `/api/solva/v2/*` (per-user) | Pre-Phase-D Solva orchestrator. solva_phase_d.py line 3 comment: *"distinct from the legacy `/api/solva/v2/...` paths in `routers/solva_v2.py`"* | `backend/routers/solva_phase_d.py` — context-scoped `/api/contexts/{cid}/solva/v2/*`. Phase D synthesis renderer + refusal voice layer. | **escalate** — same gate as row 1.2. Two routers are live today; legacy router is referenced by the still-routed `SolvaSession.jsx`. Retire together. |
| 1.4 | `frontend/src/pages/SandboxV2.jsx` + App.js routes `/legacy-sandbox` + `/legacy-sandbox/resume` | Phase J 4-step pre-auth sandbox (Welcome → Solva → Studio → Cycle). Page docstring (line 3–6): *"The legacy 60-second narrative remains accessible at /sandbox/legacy for 30 days as a forensic fallback."* | `/sandbox` route now serves `SandboxApp` (`frontend/src/sandbox/SandboxApp.jsx`). | **escalate** — 30-day forensic-fallback window may have elapsed. Need PO call on whether to delete legacy. |
| 1.5 | `frontend/src/pages/Cycle.jsx` (Phase D rewire — MEMO Item 3, D-001) | Six-step cycle DETAIL page (Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation). Internal comments at lines 561 + 590 reference *"legacy default-to-…"* + *"Fall back to ALL members if no v2 cycle (legacy path) — keeps the legacy path"* meaning the page handles both v1 single-cycle and v2 multi-cycle data shapes. | T5 `frontend/src/components/cycle/CycleSetupWizard.jsx` + `frontend/src/pages/cycle/CycleList.jsx` are the new SETUP entry; Cycle.jsx is the per-cycle DETAIL page they navigate INTO. | **leave** — these are sequential pages, not parallel implementations. The internal v1/v2-branching legacy fallbacks within Cycle.jsx itself are a separate cleanup question; flag if PO wants v1-cycle support fully retired. |
| 1.6 | `backend/routers/cycle.py` (§12 iter18 redesign — Questions / Reportees / Checklists / Reports / Schedule, all under `/api/contexts/{cid}/...`) | Pre-Cycle-v2 §12 single-cycle data model. Owns `/cycle/committees`, `/cycle/schedule`, `/cycle/actions`, `/reports/*`, `/checklists/*`, `/respond/{token}`, etc. | `backend/routers/cycles.py` (Cycle Manager v2 — multi-cycle master, status 201 create / list / get / activate / close / apply-template under `/contexts/{cid}/cycles`) + `backend/routers/cycle_manager.py` (Phase D Executive flow — agenda / team / contributions / readiness / follow-ups / draft-compilation under `/cycle/...`). | **escalate** — partial overlap. cycle.py routes are still wired and tests reference them. cycle.py owns Reports + Checklists + Questions + Reportees data domains that cycle_manager.py / cycles.py do not. Cannot delete cycle.py without porting those domains. |
| 1.7 | `backend/routers/monitor.py` (`/api/contexts/{cid}/monitor?function=...` — v1, role-adaptive) | §4 Monitor v1 — role-adaptive view of signals / cycle / reports / engagement. `backend/tests/test_monitor_v1_compat.py` lines 10–17 state: *"the v1 endpoint is still wired in `routers/monitor.py` and the schema is still served … but the v2 surface … is the modern path."* | `backend/routers/monitor_v2.py` (Patch 5 — Objectives & Projects CRUD + drawer) + `backend/routers/monitor_status_assessment.py` (Phase F — Update goal). | **escalate** — `test_monitor_v1_compat.py` was added specifically to keep v1 alive for back-compat. PO call: full retirement vs continued back-compat. |
| 1.8 | `backend/routers/work_studio_phase_c.py` (Phase C.1 export router under `/api/work_studio/picker` + `/exports/...`) + `backend/routers/work_studio_phase_c2.py` (Phase C.2 brief enhance under `/api/work_studio/briefs/{brief_id}/...`) | Pre-Phase-C.3 Work Studio export + enhance routers, mounted with NO `/contexts/{cid}` scoping. | `backend/routers/work_studio_export.py` (Phase C.2 — context-scoped `/api/contexts/{cid}/work-studio/export/{kind}` + enhance), `backend/routers/work_studio_from_source.py` (Phase C.3 — `/api/contexts/{cid}/work-studio/from-source`), `backend/routers/work_studio_render.py` (T4.1 G6 — DOCX/PDF/PPTX), `backend/routers/work_studio_overlay.py` (Chunk 8 — drawer endpoints). | **escalate** — phase_c.py + phase_c2.py routes (no context scoping) overlap conceptually with the context-scoped surfaces. Need PO confirmation that no live frontend code path still calls the un-scoped variants. |
| 1.9 | `backend/routers/cycle_config.py` (Phase 2 / Advisory 6 — phase id → collection mapping for delete-phase guard) | Single endpoint family for cycle phase config. | Unclear — `cycles.py` (v2 cycles master) + `cycle_manager.py` (Phase D executive flow) own cycle phase state. | **escalate** — confirm if cycle_config.py is still imported by an active frontend surface or only by deprecated paths. |
| 1.10 | `frontend/src/pages/AppHome.jsx` (Patch 3 dispatcher) | Dispatcher: routes `/app` to `HomeUndeclared` / `Home1` / `Home2` based on `account.declared_role` + `activeContext`. Docstring (lines 12–15): *"Legacy role-specific homes (HomeNed / HomeExecutive / HomeDual) were deleted in Patch 17."* | `frontend/src/pages/home/Home1.jsx` + `Home2.jsx` + `HomeUndeclared.jsx` are the canonical post-Patch-3 home surfaces. AppHome is a thin router. | **leave** — AppHome IS the dispatcher; the legacy role homes it dispatched between were already deleted. Not a duplicate. |
| 1.11 | `backend/routers/help.py` — `/api/help/features` reads `/app/memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` | Phase E endpoint that serves the legacy "AKKI Features and Functionality" document as JSON+markdown for the React `/help` page (`frontend/src/pages/HelpFeatures.jsx`) to render inline. | `AKKI_PRODUCT_SPEC.md` v1.1 §1.4 states verbatim: *"The legacy `AKKI_FEATURES_AND_FUNCTIONALITY.md` has no authority."* The new spec is the canonical product description. | **escalate** — the spec says the doc has no authority but the endpoint + page are still wired and the page is linked from the sidebar (AppShell.jsx). Retiring the page needs PO call on whether `/help` should redirect to the new spec or be re-authored. |
| 1.12 | `frontend/src/pages/PlaysLibrary.jsx` + `PlayView.jsx` + `frontend/src/components/plays/*` + `backend/routers/plays.py` + `backend/routers/agenda.py` | "Plays" / "Workflows" — §13 choreography layer (Board Pack Play, Pre-Board Play, etc.). Live routes `/app/plays`, `/app/plays/:playId`. CHANGELOG.md describes the rename "Play → Workflow" in iter26. | NEITHER canonical spec (`AKKI_PRODUCT_SPEC.md` v1.1, `AKKI_ONBOARDING_SPEC.md` v1.1) references Plays or Workflows. The spec scopes journeys to Document Journal, Cycle Manager, Work Studio, Aggregated (Monitor). Plays sit outside that surface set. | **escalate** — pre-spec layer. Decide: (a) retire the whole Plays surface because the spec doesn't include it, (b) keep as ancillary chrome, (c) propose adding Plays to spec v1.2. |
| 1.13 | `backend/routers/documents.py` (sync) + `backend/routers/documents_async_mirror.py` (async-mirror — `/generate-meta`, `/summary`, `/journal-commentary`, `/evolution-diff`) | Phase C async-mirror endpoints. Companion to the 4 sync Document Reader endpoints. Both `documents.py` and `documents_async_mirror.py` are live and the sync endpoints remain. | Async-mirror is an additive enhancement, not a supersession. | **leave** — additive coexistence by design. Sync endpoints are the 524-prone-on-slow-LLM path; async-mirror returns immediately. |

---

## Category 2 — Dead code (defined but never rendered / imported)

Files/components present on disk where no live code path imports or renders them.

| # | file_path | what_it_is | what_supersedes_it | recommended_action |
| --- | --- | --- | --- | --- |
| 2.1 | `frontend/src/components/cycle/ReportsTab.jsx` (744 lines, exports default `ReportsTab` wrapper around `ReportsTabInner`) | §12 Reports tab component originally rendered on the old multi-tab Cycle page. | Cycle.jsx Phase D rewire (6-step single-column flow) does not import it. 0 importers across the entire codebase. | **escalate** — superseded by the Phase D rewire; component code is still functional and could be useful for a future Cycle-page reports tab. PO call: delete or shelve. |
| 2.2 | `frontend/src/components/cycle/CycleTracker.jsx` | Operational table component the user requested in iter27 (reportee × latest cycle × status × intervention button). | Replaced by §4.B → C7 Draft Journal + C8 Ready Journal flow (T5). 0 importers. | **escalate** — same shape as 2.1. |
| 2.3 | `frontend/src/components/cycle/ReviewInboxCard.jsx` | Review-inbox card component (iter20 §12 Phase 3 multi-tier review chain). | 0 importers. | **escalate** — likely retired with the new T5 cycle UI. |
| 2.4 | `frontend/src/components/cycle/NedInboxTile.jsx` | NED Inbox tile component for Cycle UI. | 0 importers. Phase E NED Cycle Manager mounted `/app/ned/inbox` route uses `pages/ned/NedInbox.jsx` directly. | **escalate** — superseded by ned/NedInbox page; component file appears orphan. |
| 2.5 | `frontend/src/components/cycle/CycleStrip.jsx` | Cycle strip component (legacy multi-tab cycle layout). 0 importers; imports `CyclePhaseSheet` (which IS live, used by 1 other importer). | Phase D Cycle.jsx 6-step single-column layout. | **escalate** — likely retired with Phase D rewire. |
| 2.6 | `frontend/src/components/cycle/tabs/ActionsTab.jsx` | Legacy multi-tab Cycle "Actions" tab. 0 importers. | Phase D Cycle.jsx 6-step single-column layout. | **escalate**. |
| 2.7 | `frontend/src/components/cycle/tabs/BoardpackTab.jsx` | Legacy multi-tab Cycle "Boardpack" tab. 0 importers. | Phase D Cycle.jsx 6-step single-column layout. | **escalate**. |
| 2.8 | `frontend/src/components/cycle/tabs/MinutesTab.jsx` | Legacy multi-tab Cycle "Minutes" tab. 0 importers (but imports `pages/Prepare.jsx`, which itself has the same orphan profile). | Phase D Cycle.jsx 6-step single-column layout. | **escalate**. |
| 2.9 | `frontend/src/components/cycle/tabs/SignalsTab.jsx` | Legacy multi-tab Cycle "Signals" tab. 0 importers (also imports `pages/Prepare.jsx`). | Phase D Cycle.jsx 6-step single-column layout. | **escalate**. |
| 2.10 | `frontend/src/pages/SolvaLanding.jsx` (page file) | Page-level SolvaLanding wrapper. App.js line 20 imports it via `lazy(() => import("@/pages/SolvaLanding"))` but no `<SolvaLanding ... />` JSX exists in any route. The only `<SolvaLanding variant="auth">` JSX lives at `pages/SolvaApp.jsx:77` which imports the COMPONENT (`@/components/solva/SolvaLanding`), not this page. | The component `frontend/src/components/solva/SolvaLanding.jsx` (different file) is the actually-rendered surface. | **escalate** — App.js line 20 lazy import is unreachable. Likely deletable but unreachable lazy imports are cheap; PO call. |
| 2.11 | `frontend/src/components/streaming/StreamingShell.jsx` + `frontend/src/components/lens/AllLensesModal.jsx` + `frontend/src/components/depth/DepthOfferCard.jsx` | Three component files. 0 importers each. `StreamingShell` is referenced in `memory/ROADMAP.md` P1: *"Motion architecture is already shipped; only the wiring remains."* | None — these were built ahead of the wiring sprint. | **escalate** — speculative components; either wire them or retire. ROADMAP.md P1 still references StreamingShell as ready-to-wire. |

**Other potentially-dead files surfaced during the audit but NOT confirmed dead** (would need deeper trace to be sure):
- `frontend/src/pages/Prepare.jsx` — App.js comment (line 109) says it's *"not in routes today but imported elsewhere"*. Its only importers (`SignalsTab.jsx`, `MinutesTab.jsx`) are themselves orphans per rows 2.8 / 2.9. Effectively transitively dead, but technically still referenced. **escalate**.

---

## Category 3 — Documentation contradicting canonical specs

Markdown / docs in `/app/memory/` that describe AKKI differently from `AKKI_PRODUCT_SPEC.md` v1.1 or `AKKI_ONBOARDING_SPEC.md` v1.1 — or claim authority that the canonical specs explicitly deny.

| # | file_path | what_it_is | what_supersedes_it | recommended_action |
| --- | --- | --- | --- | --- |
| 3.1 | `memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` (378 lines, last modified 2026-05-21) | Holistic product reference document. Self-describes (line 4) as *"Status: Live (2026-05-21) — reflects rewrite Phases A through F.1 + the QA-2026-05-16 sprint (Chunks 7 through 19)"*. Has §3 Architectural foundation, §4 Feature catalogue by surface, §4.1–§4.9 — all overlapping the canonical journeys in `AKKI_PRODUCT_SPEC.md` v1.1 §4. Still served live at `/api/help/features`. | `AKKI_PRODUCT_SPEC.md` v1.1 §1.4 (verbatim): *"The legacy `AKKI_FEATURES_AND_FUNCTIONALITY.md` has no authority."* | **escalate** — spec strips its authority but it is still served live (see row 1.11). PO call: archive, rewrite, or redirect `/api/help/features` to a new doc. |
| 3.2 | `memory/PRODUCT_FEATURES.md` | Separate "source-of-truth inventory" doc generated from a read-only repo review. Begins: *"AKKI is 'an intelligence layer built for non-executive directors and operating executives…'"* Asserts itself as source-of-truth. | `AKKI_PRODUCT_SPEC.md` v1.1 §1 is the actual source-of-truth hierarchy. | **escalate** — PRODUCT_FEATURES.md was generated before spec v1.1 existed. Demote / archive. |
| 3.3 | `memory/SYSTEM_STATE.md` | Durable ledger of closed sprints (Patch 1 → Patch 9, Phase A → F.1). Treats Patch-numbered sprints (e.g. *"Patch 5 — Monitor v2"*, *"Patch 3 — Home v2"*) as canonical surfaces. Predates spec v1.1. | `AKKI_PRODUCT_SPEC.md` v1.1 §4 product journeys (D1–D9, C1–C8, W1–W12, X1–X8) replaces the patch-history view as the canonical product description. | **escalate** — useful as a sprint-log artefact but should not be confused with current spec. Suggest renaming to `LEGACY_SPRINT_HISTORY.md` or moving under `memory/sprints/`. |
| 3.4 | `memory/ROADMAP.md` | "Prioritised backlog of remaining product work." P1 items reference Plays (row 1.12), Monitor v2 ExCo chips, Lens — surfaces that are not part of the canonical spec. P0 lists *"Deployment blockers (5) — original audit items, not yet triaged"* with no further detail. | `POST_T5_BACKLOG.md` + `HARDENING_LOG.md` + spec §6 GAPs are the live backlog ledger today. | **escalate** — ROADMAP.md was the pre-spec backlog. Either delete or reconcile against spec + POST_T5_BACKLOG.md. |
| 3.5 | `memory/CHANGELOG.md` | Append-only history. Latest header reads *"## 2026-02 — Autonomous polish sprint, Phases A → F (post-Chunk-19)"*. Does not include T1-T5, Backlog-b, J1-J4, or Hardening sprints (all closed between 2026-05-24 and 2026-05-25). | The closeout markdowns under `memory/sprints/` (T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md, BACKLOG_B_LOG.md, HARDENING_LOG.md, J1-J4 logs) are the actual change log for the post-spec period. | **escalate** — CHANGELOG.md is stale; either retire or append the post-spec sprint closures. |
| 3.6 | `memory/READ_FIRST.md` (2026-05-21) AND `memory/sprints/READ_FIRST.md` (2026-05-24, evening) | Two separate READ_FIRST documents, each claiming to be the entry-point read. `memory/READ_FIRST.md` line 5 says *"Maintainer: whichever agent last patched the system"*; `memory/sprints/READ_FIRST.md` line 1 says *"# READ FIRST — Project status (2026-05-24, evening)"*. | Neither describes T1-T5 or Hardening; both predate the canonical spec. | **escalate** — pick one as canonical entry-point, retire or merge the other. |
| 3.7 | `memory/REWRITE_SPRINT_STATE.md` + `memory/REWRITE_DEPLOY_READY.md` | Describe the "rewrite" sprint closing state — *"Phases A → F shipped, verified, and documented. 662 pytest passing"* (current count is 1248). Generated 2026-05-18. | Subsequent sprints (T1-T5, Hardening) closed 2026-05-25 with vastly different test counts. | **escalate** — pre-T1 snapshot. Move to sprints/ archive or annotate as "snapshot frozen 2026-05-18". |
| 3.8 | `memory/AUTONOMOUS_SPRINT_LOG.md` | Append-only log of overnight autonomous-run chunk closures (Chunks 9.5 → 17, 2026-05-20 onwards). | Superseded by the T-series + Hardening sprint logs. | **escalate** — historical record; archive under sprints/ rather than at top-level memory/. |
| 3.9 | `memory/PHASE_15_3_5_QUEUE.md` | *"Captured with locked answers from human. DO NOT touch any of this"* — a queue from a Phase 15.3.5 dispatch. | The work it queued has either shipped (subsequent phases) or been superseded. | **escalate** — confirm queue items are closed before retiring. |
| 3.10 | `memory/sprints/ONBOARDING_INVENTORY.md` + `memory/sprints/J1_PRESERVED_STATE.md` | ONBOARDING_INVENTORY (2026-05-24) audited pre-J1 onboarding. J1_PRESERVED_STATE (2026-05-24) preserved the J1 work that was reverted before T1-T5 began. | J1-J4 was subsequently re-implemented and closed in the J-series sprint (see closeout in T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md or J-suite logs). | **escalate** — both docs are historical records of the J1 revert/restore cycle. Useful as forensic context; not authoritative for current behaviour. |

---

## Category 4 — Tests contradicting current behaviour

Tests on disk that assert opposite-direction invariants or exercise retired surfaces.

| # | file_path | what_it_is | what_supersedes_it | recommended_action |
| --- | --- | --- | --- | --- |
| 4.1 | `backend/tests/test_iter22_billing_schedule.py` (skipped via `pytestmark`) | Asserts the old §M4 Stripe billing contract: `test_checkout_pro_returns_stripe_url` (line 90) → `body["url"].startswith("https://checkout.stripe.com/")` (line 98). Tests `/api/billing/plans`, `/api/billing/me`, `/api/billing/checkout`, `/api/billing/status/{sid}`, `/api/webhook/stripe`. | `backend/tests/test_chunk_c_billing_coming_soon.py` (chunk c, 2026-05-25) asserts the OPPOSITE: every billing endpoint returns `coming_soon: true`, `/checkout` returns `coming_soon: true` and *"NEVER a Stripe URL"*, webhook dead-letters. | **escalate** — `test_iter22` is skip-marked so it doesn't actually fail; but the file on disk contradicts the new contract. Two paths: (a) delete `test_iter22` entirely, (b) keep as historical skip-marker pointing to the contract flip. PO call. |
| 4.2 | `backend/tests/test_iter24_plays.py` + `backend/tests/test_iter25_plays_slice2.py` (both skipped) | Tests for `/api/plays/library`, `/api/contexts/{cid}/plays`, `auto-launch` schedule hook, Pre-Board Play `read` endpoint, PLAY READY trigger card on Home. | Plays is not in canonical spec — see row 1.12. | **escalate** — paired with the Plays-surface retirement decision. |
| 4.3 | `backend/tests/test_iter44_prepare.py` (skipped) | Tests for `/api/contexts/{cid}/prepare/*` endpoints. | App.js line 109 declares Prepare *"not in routes today"* — see Prepare orphan note under row 2.10's note. | **escalate** — coupled to the Prepare orphan-retirement decision. |
| 4.4 | 28 `tests/test_iter*.py` files marked `Patch 8 quarantined` (e.g. `test_iter31_lens_coach_email.py`, `test_iter32_report_deck_coach.py`, `test_iter33_summary_compose.py`, `test_iter34_share_evolution.py`, `test_iter36.py`, `test_iter37_38.py`, `test_iter39_briefings_objective_check.py`, `test_iter44_prepare.py`, etc.) | Pre-existing failing tests `@skip`'d during Patch 8 to keep the suite green. SKIP_LEDGER.md classifies these as `broken-masked-prequel` (255 tests) — *"the worst class — features that may still exist but coverage is silently dark."* | The full ledger and triage recipe live at `/app/memory/sprints/SKIP_LEDGER.md` §2. | **escalate** — out of scope for THIS legacy-conflict audit but flagged for completeness. SKIP_LEDGER.md already catalogues these in detail. |

---

## Top 5 highest-risk items

Ranked by likelihood of biting a real user or a new developer.

1. **Row 1.11 — `/api/help/features` serves `AKKI_FEATURES_AND_FUNCTIONALITY.md` despite the canonical spec stripping its authority.** A friendly-tester reading the in-app `/help` page will read a different product description than the one your engineering team is building against. Highest-impact doc/code/spec contradiction.
2. **Row 1.12 — Plays / Workflows surface exists end-to-end (router + 2 pages + components + side-nav not — but routes `/app/plays` + `/app/plays/:playId` are reachable) but is NOT in spec v1.1.** A tester or new developer landing on `/app/plays` will assume it's canonical. The spec does not back any of its behaviours.
3. **Row 1.6 — Three cycle-related backend routers (`cycle.py`, `cycles.py`, `cycle_manager.py`) all live under `/api/contexts/{cid}/cycle*`.** A new developer adding cycle endpoints has no clear file to choose. Endpoint discovery is muddy; future refactor risk is high.
4. **Row 1.2 + 1.3 — Legacy Solva session UI + router are still wired** despite Phase E Sub-task F's archive sweep landing and PHASE_E_CLOSEOUT confirming 0 orphans on preview. The two routes (`/app/solva/session/:sessionId` vs `/app/solva/phase-d/session/:sessionId`) confuse the user about which Solva they're in.
5. **Row 4.1 — `test_iter22_billing_schedule.py` asserts Stripe contracts that no longer hold.** If someone un-skips the test under "let's see what's still in here", it will fail loudly against the live `coming_soon` invariant. Either contract flip or test deletion needed.

---

## Verification recipes (so any reader can re-derive)

For Category 1 imports / route bindings:
```
grep -nE "import.*<Component>\|from.*<Component>" frontend/src --include="*.jsx" --include="*.js"
grep -nE "<Component\>"                            frontend/src --include="*.jsx" --include="*.js"
```

For Category 2 dead-component counts:
```
grep -rln "import.*<Name>\b\|from.*<Name>\"" --include="*.jsx" --include="*.js" frontend/src \
  | grep -v "/<Name>.jsx"
```

For Category 3 spec-vs-doc contradictions:
- Open the named doc + spec side-by-side. Verbatim quotes in this ledger cite line numbers.

For Category 4 test contradictions:
- Inspect `backend/tests/test_iter22_billing_schedule.py` line 98 vs `backend/tests/test_chunk_c_billing_coming_soon.py` line 13 of docstring.

---

*Legacy conflict audit complete. Awaiting user review.*
