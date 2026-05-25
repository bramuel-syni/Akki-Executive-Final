# Skip Ledger — Full repo pytest skipped-test classification

**Status:** READ-ONLY audit. No test file modified during this pass.
**Source:** `/app/memory/sprints/skip_audit_run.log` (`pytest -rs --tb=no -q`) + `/app/memory/sprints/skip_audit_collection.log`.
**Run date:** 2026-05-25.
**Total skipped tests:** **500** (across 76 distinct `SKIPPED [N]` rows in the short summary).
**Total passed tests:** 1100. **Failed:** 1 (`test_requirements_guard.py` — pre-existing, see closeout §6).

---

## 1. Counts per classification

| Class | Test count | What it means | Recommendation |
| --- | --- | --- | --- |
| `broken-masked-prequel` | **255** | Pre-autonomous-sprint failures `@skip`'d so the suite went green. **Worst class** — features that may still exist but coverage is silently dark. | **fix-and-enable** (per file, prioritised) |
| `broken-masked-rewrite-needed` | **144** | `requests.Session()` against live BASE_URL → 429-rate-limited under full suite. Test infra needs in-process httpx+ASGI rewrite. Feature may still work; the *test* is broken. | **fix-and-enable** via the `test_phase_b_chat_retention.py` pattern |
| `coverage-loss` | **73** | Feature ships but its test broke when an API contract / Solva guardrail tuning / seed-data drifted. Regressions invisible. | **fix-and-enable** (highest priority within skips) |
| `broken-masked-isolation` | **18** | Passes in isolation but fails in full-suite due to fixture pollution. The test is correct; the harness needs a scoped fixture. | **fix-and-enable** via per-test fixture |
| `broken-masked` | **5** | Test-harness pattern broken (cross-test cookie persistence) — feature covered by other tests but THIS test is wrong. | **delete** or `convert-to-xfail` |
| `env-gated` | **5** | Legitimately requires an external service (tesseract binary, LLM key + sandbox endpoint) that is intentionally absent in this env. | **leave** |
| **TOTAL** | **500** | | |

**Top-line read:** 422 of 500 skips (84%) are some flavour of `broken-masked`. The 5 `env-gated` skips are the only ones with a defensible rationale.

---

## 2. Per-class detail

### coverage-loss  (73 tests · 17 skip rows)

**Recommendation:** fix-and-enable (HIGHEST PRIORITY)

| # | File | Line | Test count | Skip reason (truncated) |
| --- | --- | --- | --- | --- |
| 1 | `tests/test_iter62_solve_wave2_wave3.py` | — | 10 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 2 | `tests/test_iter40_goals_kpi.py` | — | 9 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 3 | `tests/test_iter41_signal_actions.py` | — | 9 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 4 | `tests/test_iter19_polish_committee_medium.py` | — | 8 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 5 | `tests/test_iter38_sandbox_tier1.py` | — | 8 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 6 | `tests/test_iter42_signal_kpi.py` | — | 8 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 7 | `tests/test_phase_b_solva_no_opinion.py` | 228 | 5 | Patch 19 attempt — adversarial parametrize set fails on all 5 prompts; Solva no-opinion guardrail tuning has drifted. Reclassified to Phase 4 (REWRITE). |
| 8 | `tests/test_phase_b_chat_stream.py` | — | 4 | Patch 19 attempt — chat-stream contract diverged from this test. All 4 tests fail. Reclassified to Phase 4 (REWRITE). |
| 9 | `tests/test_phase_b_solva_no_opinion.py` | — | 4 | Patch 19 attempt — adversarial parametrize set fails on all 5 prompts; Solva no-opinion guardrail tuning has drifted. Reclassified to Phase 4 (REWRITE). |
| 10 | `tests/test_iter62_solve_wave2_wave3.py` | 284 | 1 | Patch 19 — E2E test using requests.Session() against live BASE_URL. Reclassified to Phase 4-large; needs in-process httpx+ASGI rewrite. Re-quarantined after ... |
| 11 | `tests/test_phase_b_chat_retention.py` | 90 | 1 | Patch 19 — chat-create endpoint now requires X-Active-Context header (post-Phase 15 contract change). Needs test rewrite to seed an active context for the te... |
| 12 | `tests/test_phase_i_solva_export.py` | 238 | 1 | Patch 19 — explicit cluster_id contract changed; needs rewrite. The other 12 export tests in this file remain green. |
| 13 | `tests/test_solva_v2_session_limits.py` | 71 | 1 | Patch 19 — concurrent-session limit changed across Solva v2 versions. Needs rewrite. |
| 14 | `tests/test_solva_v2_session_limits.py` | 117 | 1 | Patch 19 — max-turns-per-session limit changed; needs rewrite. |
| 15 | `tests/test_solva_v2_session_limits.py` | 179 | 1 | Patch 19 — stale-session cron path moved; needs rewrite to hit the new admin route. |
| 16 | `tests/test_solva_v2_shield_invariant.py` | 131 | 1 | Patch 19 — full-session invariant currently fails on one assertion; needs Solva v2 shield contract review. |
| 17 | `tests/test_work_studio_briefings_visible.py` | 105 | 1 | Patch 19 — freshly-created briefing visibility depends on briefings list filter contract that diverged from this test. Other test in this file remains green. |

### broken-masked-isolation  (18 tests · 7 skip rows)

**Recommendation:** fix-and-enable (per-test fixture)

| # | File | Line | Test count | Skip reason (truncated) |
| --- | --- | --- | --- | --- |
| 1 | `tests/test_phase_i_solva_export.py` | — | 12 | Patch 19 — passes in isolation but fails 7/13 tests under full-suite due to session_id collisions in shared `solva_sessions` test fixtures. Needs per-test se... |
| 2 | `tests/test_phase_a_chat_streaming_audit.py` | 134 | 1 | Patch 19 — cross-test chat_audit_log chain pollution; passes in isolation. Needs per-test reset fixture. |
| 3 | `tests/test_phase_a_chat_streaming_audit.py` | 194 | 1 | Patch 19 — cross-test chat_audit_log chain pollution; passes in isolation. Needs per-test reset fixture. |
| 4 | `tests/test_phase_b_chat_retention.py` | 195 | 1 | Patch 19 — superadmin retention sweep test fails under full-suite (chats from earlier tests get hard-deleted unexpectedly). Needs scoped test fixture. |
| 5 | `tests/test_phase_b_chat_retention.py` | 210 | 1 | Patch 19 — superadmin retention sweep test fails under full-suite (chats from earlier tests get hard-deleted unexpectedly). Needs scoped test fixture. |
| 6 | `tests/test_render_determinism.py` | 99 | 1 | Patch 19 — fixture pollution under full-suite. Passes in isolation. Companion to test_report_docx_deterministic above. |
| 7 | `tests/test_render_determinism.py` | 118 | 1 | Patch 19 — passes in isolation but fails under full-suite due to fixture/render order pollution. Needs per-test fixture isolation. |

### broken-masked-prequel  (255 tests · 30 skip rows)

**Recommendation:** fix-and-enable

| # | File | Line | Test count | Skip reason (truncated) |
| --- | --- | --- | --- | --- |
| 1 | `tests/test_sprint2.py` | — | 19 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 2 | `tests/test_iter51_inbound_enterprise.py` | — | 16 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 3 | `tests/test_iter34_share_evolution.py` | — | 13 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 4 | `tests/test_iter71_studio_blocks.py` | — | 13 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 5 | `tests/test_iter31_lens_coach_email.py` | — | 12 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 6 | `tests/test_iter36.py` | — | 12 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 7 | `tests/test_iter44_prepare.py` | — | 12 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 8 | `tests/test_iter58_walkin_solve.py` | — | 12 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 9 | `tests/test_iter32_report_deck_coach.py` | — | 11 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 10 | `tests/test_sprint5.py` | — | 11 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 11 | `tests/test_daily_review_solva_cycle.py` | — | 10 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 12 | `tests/test_sprint3.py` | — | 10 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 13 | `tests/test_iter53_deep_tier_minutes.py` | — | 9 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 14 | `tests/test_iter70_inbound_edge.py` | — | 9 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 15 | `tests/test_iter33_summary_compose.py` | — | 7 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 16 | `tests/test_iter37_38.py` | — | 7 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 17 | `tests/test_iter39_briefings_objective_check.py` | — | 7 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 18 | `tests/test_iter56_regen_learning.py` | — | 7 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 19 | `tests/test_solva_v2_submodules.py` | — | 7 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 20 | `tests/test_iter48.py` | — | 6 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 21 | `tests/test_iter49.py` | — | 6 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 22 | `tests/test_iter54_llm_spend_quota_inbound.py` | — | 6 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 23 | `tests/test_iter70_inbound_triage.py` | — | 6 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 24 | `tests/test_phase12_2_closeout.py` | — | 5 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 25 | `tests/test_phase12_2_e2e.py` | — | 5 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 26 | `tests/test_iter54_llm_spend_quota_inbound.py` | 67 | 4 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 27 | `tests/test_solva_v2_adversarial_guardrails.py` | — | 4 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 28 | `tests/test_solva_v2_submodules.py` | 92 | 4 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 29 | `tests/test_sprint6.py` | — | 4 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |
| 30 | `tests/test_solva_v2_integration.py` | — | 1 | Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7. |

### broken-masked-rewrite-needed  (144 tests · 15 skip rows)

**Recommendation:** fix-and-enable (in-process httpx rewrite)

| # | File | Line | Test count | Skip reason (truncated) |
| --- | --- | --- | --- | --- |
| 1 | `tests/test_iter22_billing_schedule.py` | — | 18 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 2 | `tests/test_iter12_shares_home.py` | — | 14 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 3 | `tests/test_iter24_plays.py` | — | 14 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 4 | `tests/test_iter25_plays_slice2.py` | — | 13 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 5 | `tests/test_iter28_strategic_goals.py` | — | 13 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 6 | `tests/test_iter29_score_history.py` | — | 11 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 7 | `tests/test_iter30_blog_lens.py` | — | 11 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 8 | `tests/test_iter26_engagement.py` | — | 9 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 9 | `tests/test_iter45_shares_brief.py` | — | 9 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 10 | `tests/test_iter11_speaking_notes.py` | — | 8 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 11 | `tests/test_iter50.py` | — | 6 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 12 | `tests/test_iter10_board_deck.py` | — | 5 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 13 | `tests/test_iter16_learn_personalisation.py` | — | 5 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 14 | `tests/test_iter43_quick_results.py` | — | 5 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |
| 15 | `tests/test_sprint1.py` | — | 3 | Patch 19 attempt — E2E test using requests.Session() against live BASE_URL. Auth login gets rate-limited (HTTP 429) under full pytest suite. Architectural re... |

### broken-masked  (5 tests · 5 skip rows)

**Recommendation:** delete or convert-to-xfail

| # | File | Line | Test count | Skip reason (truncated) |
| --- | --- | --- | --- | --- |
| 1 | `tests/test_patch_21_news.py` | 150 | 1 | Cross-test cookie persistence — auth gate covered by FastAPI Depends |
| 2 | `tests/test_patch_23_upload_p0.py` | 76 | 1 | Cross-test cookie persistence — see docstring |
| 3 | `tests/test_patch_25_news_geo.py` | 217 | 1 | Cross-test request-scope account caching — see docstring |
| 4 | `tests/test_solva_v2_post_redirect_recovery.py` | 200 | 1 | Patch 19 — Solva v2 redirect-pivot path returns 500 in current build (downstream change). Needs investigation in a dedicated Solva-v2 sprint. |
| 5 | `tests/test_solva_v2_post_redirect_recovery.py` | 295 | 1 | Patch 19 — recovery-flag persistence path needs Solva v2 schema update. Skipped to keep the other 3 tests in this file green. |

### env-gated  (5 tests · 2 skip rows)

**Recommendation:** leave

| # | File | Line | Test count | Skip reason (truncated) |
| --- | --- | --- | --- | --- |
| 1 | `tests/test_iter15_board_pack.py` | — | 4 | Patch 13 Phase 2 attempt — depends on live sandbox endpoint + LLM key; reclassified to Phase 4 (REWRITE). |
| 2 | `tests/test_phase_f1_capability_gaps.py` | 391 | 1 | tesseract binary not on PATH; install tesseract-ocr to run. |

---

## 3. Top-priority items — explicit enumeration

### 3.1 `coverage-loss` rows (73 tests) — feature ships, regression detection DARK

These are the highest-priority items in the entire ledger. The feature is in production but the test that would catch a regression is disabled.

| File | Line | Tests | What it tests | Cross-tier risk |
| --- | --- | --- | --- | --- |
| `test_iter62_solve_wave2_wave3.py` | — | 10 | Solva Wave 2/3 prompts + responses | Solva contract — adjacent to G2 |
| `test_iter40_goals_kpi.py` | — | 9 | Strategic Goals KPI surface | **T2.4 adjacent (G11/G12)** |
| `test_iter41_signal_actions.py` | — | 9 | Pulse signal actions | T2.2 adjacent |
| `test_iter19_polish_committee_medium.py` | — | 8 | Committee Pack polish flow | **T3.3 / T4 adjacent (G6/G8)** |
| `test_iter38_sandbox_tier1.py` | — | 8 | Sandbox Tier-1 surface | Adjacent to Trust Center / Shield |
| `test_iter42_signal_kpi.py` | — | 8 | Signal-KPI joining | T2.2 adjacent |
| `test_phase_b_solva_no_opinion.py` | — | 4 | Solva no-opinion guardrail | **GUARDRAIL ADJACENT — high risk** |
| `test_phase_b_solva_no_opinion.py` | 228 | 5 | Adversarial parametrize set | **GUARDRAIL ADJACENT — high risk** |
| `test_phase_b_chat_stream.py` | — | 4 | Chat-stream contract | Adjacent to D-chunk wire layer |
| `test_iter62_solve_wave2_wave3.py` | 284 | 1 | Wave 2/3 cluster_id | Solva contract |
| `test_phase_b_chat_retention.py` | 90 | 1 | Chat-create requires X-Active-Context | Phase 15 contract change |
| `test_phase_i_solva_export.py` | 238 | 1 | Explicit cluster_id contract | Solva export contract |
| `test_solva_v2_session_limits.py` | 71 | 1 | Concurrent-session limit | Solva v2 contract |
| `test_solva_v2_session_limits.py` | 117 | 1 | Max-turns-per-session limit | Solva v2 contract |
| `test_solva_v2_session_limits.py` | 179 | 1 | Stale-session cron path | Solva v2 ops contract |
| `test_solva_v2_shield_invariant.py` | 131 | 1 | Full-session invariant | **GUARDRAIL ADJACENT — high risk** |
| `test_work_studio_briefings_visible.py` | 105 | 1 | Briefing-list filter contract | T1 / T3 Work Studio adjacent |

### 3.2 `broken-masked-isolation` rows (18 tests) — fix-and-enable via per-test fixtures

These tests pass in isolation; the bug is in the test harness, not the feature. Should be the easiest to re-enable.

| File | Line | Tests | Reason |
| --- | --- | --- | --- |
| `test_phase_i_solva_export.py` | — | 12 | `session_id` collisions in shared `solva_sessions` fixtures |
| `test_phase_a_chat_streaming_audit.py` | 134 | 1 | `chat_audit_log` chain pollution |
| `test_phase_a_chat_streaming_audit.py` | 194 | 1 | Same |
| `test_phase_b_chat_retention.py` | 195 | 1 | Cross-test chat hard-deletes |
| `test_phase_b_chat_retention.py` | 210 | 1 | Same |
| `test_render_determinism.py` | 99 | 1 | Fixture/render order pollution |
| `test_render_determinism.py` | 118 | 1 | Same |

### 3.3 `unknown` rows — there are none after refined classification

All previously-`unknown` rows are now classified:

| Was | Now | File | Reason |
| --- | --- | --- | --- |
| unknown | `env-gated` | `test_iter15_board_pack.py` | Needs live sandbox endpoint + LLM key |
| unknown | `env-gated` | `test_phase_f1_capability_gaps.py:391` | Needs `tesseract` binary on PATH |
| unknown | `broken-masked` | `test_patch_21_news.py:150` | Cross-test cookie persistence (test-harness bug) |
| unknown | `broken-masked` | `test_patch_23_upload_p0.py:76` | Same harness pattern |
| unknown | `broken-masked` | `test_patch_25_news_geo.py:217` | Same |

### 3.4 `broken-masked` rows (5 tests) — delete or convert-to-xfail

The feature these tests covered is already covered by other passing tests (the docstrings explicitly say "auth gate covered by FastAPI Depends"). These tests should be deleted, not fixed.

| File | Line | Tests |
| --- | --- | --- |
| `test_patch_21_news.py` | 150 | 1 |
| `test_patch_23_upload_p0.py` | 76 | 1 |
| `test_patch_25_news_geo.py` | 217 | 1 |
| `test_patch_21_news.py` (et al.) | — | 2 (sweep) |

### 3.5 `env-gated` rows (5 tests) — **the only legitimate skips**

| File | Line | Tests | Env requirement |
| --- | --- | --- | --- |
| `test_iter15_board_pack.py` | — | 4 | Live sandbox endpoint + LLM key |
| `test_phase_f1_capability_gaps.py` | 391 | 1 | `tesseract-ocr` binary |

---

## 4. Coverage cross-check — G1 through G12

For every PO-ratified gap, confirm at least one PASSING (not skipped, not xfail) test exercises the spec.

| Gap | Tier | Anchor probed in targeted suite | Status |
| --- | --- | --- | --- |
| G1 — Add to Cycle wire format | T1.6 | `/cycle/contributions` literal | ✅ `test_t1_add_to_cycle_g1.py` GREEN |
| **G2 — Take into Solva auto-loads grounding** | T1 (D7) | `Take into Solva` testid / handoff | ❌ **Coverage-loss confirmed.** No passing automated test in the targeted suite. Handoff log explicitly marks G2 as "code-verified only". **This is a pre-disclosed gap — not a hidden one.** Recommend adding a backend integration test that hits `/api/solva/v2/sessions` with `seed_kind=document` + `seed_id=<doc_id>` and asserts the grounding manifest carries the doc. |
| G3 — Generate Brief failure toast | T1.4 | `"We couldn't generate a brief from this document. Please try again."` | ✅ `test_t1_frontend_wire.py` GREEN |
| G4 — C2 Setup Wizard validation | T5.2 | `READINESS_OPTIONS` + 4-field validation | ✅ `test_t5_frontend_wire.py` GREEN |
| G5 — C3 email + dupe verbatim | T5.3 | `"This contributor is already on the team."` | ✅ `test_t5_frontend_wire.py` GREEN |
| G6 — DOCX/PDF/PPTX parity | T4.1 + T5.5 | `/work-studio/documents/{aid}/render` | ✅ `test_t4_backend.py` + `test_t5_backend.py` GREEN |
| G7 — W3 Refine failure | T4.2 | `"We couldn't apply that refinement. Please try again."` | ✅ `test_t4_frontend_wire.py` GREEN (code-verified) |
| G8 — Drawer-vs-page disambiguation | T3.3 | `board_pack` kind routing | ✅ `test_t3_frontend_wire.py` GREEN |
| G9 — ClamAV toast verbatim | T3.4 | `"We couldn't upload that file. It was rejected by virus scanning."` | ✅ `test_t3_frontend_wire.py` GREEN (code-verified — clamd sidecar STOPPED in env, live not exercised) |
| G10 — W10 Refine inside drawer | T4.5 | `"We couldn't refine this version. Please try again."` | ✅ `test_t4_frontend_wire.py` GREEN (code-verified) |
| G11 — Strategic Goals dual RAG | T2.4 (X6) | `probability` bar | ✅ `test_t2_frontend_wire.py` GREEN |
| G12 — Strategic Goals filter list | T2.4 (X8) | `G12_FALLBACK_CATEGORIES = ["Operations", "People", "Compliance", "Product", "Commercial"]` | ✅ `test_t2_frontend_wire.py` GREEN |

**Verdict: 11/12 gaps have a passing automated test in the targeted suite. G2 is code-verified-only and was pre-disclosed in the T1 log.**

---

## 5. Tier coverage cross-check (T1 → T5 + backlog-b)

| Item | Targeted test file(s) | Status | Skip-shadow risk from §3.1 |
| --- | --- | --- | --- |
| T1.1 Chat sticky | `test_t1_frontend_wire.py` | ✅ | None |
| T1.2 Context switch | `test_t1_frontend_wire.py` | ✅ | None |
| T1.3 Generate Brief visibility | `test_t1_frontend_wire.py` | ✅ | None |
| T1.4 Generate Brief failure (G3) | `test_t1_frontend_wire.py` | ✅ | None |
| T1.5 "All documents" routing | `test_t1_frontend_wire.py` | ✅ | None |
| T1.6 Add to Cycle (G1) | `test_t1_add_to_cycle_g1.py` | ✅ | None |
| T1 D7 Take into Solva (G2) | (handoff log) | ⚠️ code-verified only | **`test_iter62_solve_wave2_wave3.py` (10 skipped) covers Solva wave 2/3 — DARK** |
| T2.1 Doc Journal filter tabs | `test_t2_frontend_wire.py` | ✅ | None |
| T2.2 Pulse Resolved tab | `test_t2_frontend_wire.py` | ✅ | `test_iter41_signal_actions.py` (9 skipped) — DARK |
| T2.3 Monitor drawer | `test_t2_frontend_wire.py` + `test_backlog_b_blocker_3_*` | ✅ (with backlog-b import fix) | None directly; iter22 billing schedule (18 skipped) is unrelated |
| T2.4 Strategic Goals (G11/G12) | `test_t2_frontend_wire.py` | ✅ | **`test_iter40_goals_kpi.py` (9 skipped) covers KPI surface — DARK** |
| T3.1 Add to Work Studio modal | `test_t3_frontend_wire.py` | ✅ | None |
| T3.2 Add to Cycle parity | `test_t3_backend.py` + `test_t3_frontend_wire.py` | ✅ | None |
| T3.3 Work Studio kind routing (G8) | `test_t3_frontend_wire.py` | ✅ | **`test_iter19_polish_committee_medium.py` (8 skipped) covers Committee Pack flow — DARK** |
| T3.4 Compile modal nested upload (G9) | `test_t3_frontend_wire.py` | ✅ (code-verified) | None |
| T4.1 W3 toolbar + G6 | `test_t4_backend.py` + `test_t4_frontend_wire.py` | ✅ | **`test_iter15_board_pack.py` (4 env-gated)** — env-gated, defensible |
| T4.2 W3 Refine failure (G7) | `test_t4_frontend_wire.py` | ✅ (code-verified) | None |
| T4.3 W5 Committed | `test_t4_frontend_wire.py` | ✅ | None |
| T4.4 Enhance flow W7/W9 | `test_t4_frontend_wire.py` | ✅ | None |
| T4.5 W10 Refine drawer (G10) | `test_t4_frontend_wire.py` | ✅ (code-verified) | None |
| T5.1 Cycle Manager landing | `test_t5_frontend_wire.py` | ✅ | None |
| T5.2 Wizard step 1 (G4) | `test_t5_frontend_wire.py` | ✅ | None |
| T5.3 Wizard step 2 (G5) | `test_t5_frontend_wire.py` | ✅ | None |
| T5.4 Wizard submit | `test_t5_frontend_wire.py` | ✅ | None |
| T5.5 Cycle Page Compile (G6) | `test_t5_backend.py` + `test_t5_frontend_wire.py` + `test_backlog_b_blocker_2_*` | ✅ | None |
| T5.6/7/8 Draft + Ready journals | `test_t5_frontend_wire.py` | ✅ | None |
| B1 Overlay title fallback | `test_backlog_b_blocker_1_*` | ✅ | None |
| B2 Cycle Page compilation linkage | `test_backlog_b_blocker_2_*` | ✅ | None |
| B3 Monitor drawer FileText import | `test_backlog_b_blocker_3_*` | ✅ | None |

---

## 6. Honest self-grade — how many prior PASS verdicts are weakened?

### 6.1 The good news

**Of the 22 e1_tester PASS verdicts across T1–T5 and backlog-b, ZERO depend on a test that is itself skipped, xfail-masked, or otherwise broken.** The targeted T1–T5 suite (89 tests) + backlog-b suite (28 tests) + chunk-(d) (10 tests) = 127 tests, ALL PASSING, with only 13 skips in the adjacent `iter28_strategic_goals` that were already disclosed. No verdict was rendered using a skipped test as evidence.

### 6.2 The bad news — adjacent-feature regression DARK

While the *spec verbatim* for G1–G12 is covered (11/12 with G2 pre-disclosed), the **underlying business logic those gaps sit on top of is partly invisible**:

| Tier | Adjacent skipped coverage | Risk if a regression lands |
| --- | --- | --- |
| **T1 D7 (Take into Solva, G2)** | `test_iter62_solve_wave2_wave3.py` (10 skipped, coverage-loss) | Grounding manifest could break and tests would not catch it |
| **T2.4 Strategic Goals (G11/G12)** | `test_iter40_goals_kpi.py` (9 skipped, coverage-loss) | KPI-derivation regressions invisible; G11 probability-bar math could go silently wrong |
| **T2.2 Pulse Resolved** | `test_iter41_signal_actions.py` (9 skipped, coverage-loss) | Signal action wire-up regressions invisible |
| **T3.3 Work Studio routing (G8)** | `test_iter19_polish_committee_medium.py` (8 skipped, coverage-loss) | Committee Pack polish flow regressions invisible |
| **Solva guardrails (no opinion + shield invariant)** | `test_phase_b_solva_no_opinion.py` (9 skipped, coverage-loss); `test_solva_v2_shield_invariant.py:131` (1 skipped, coverage-loss) | **HIGH PRIORITY — guardrail drift invisible.** These touch the Shield audit chain. |

### 6.3 Weakening verdict (per the user's framing)

**Strict reading:** 0 of 22 prior PASS verdicts are technically wrong. Every verdict points at a passing test that exercises the verbatim spec.

**Honest reading:** 5 of the 22 verdicts (T1 D7, T2.2, T2.4, T3.3, and the implicit guardrail-coverage commitment) sit on top of business-logic surfaces whose deeper coverage is DARK due to the 73 `coverage-loss` skips. A regression in any of those underlying surfaces would NOT be caught by the targeted suite alone.

**Most acute risk:** the Solva guardrail tuning (`phase_b_solva_no_opinion` + `solva_v2_shield_invariant`) — guardrail drift could escape Shield's audit chain invariants and we would not catch it from a single pytest run. This is the one that earns the user's pushback most directly.

### 6.4 Recommended next moves

| Priority | Action | Effort |
| --- | --- | --- |
| **P0** | Re-enable `test_phase_b_solva_no_opinion.py` + `test_solva_v2_shield_invariant.py:131`. Either rewrite to current guardrail tuning or convert to `xfail` with the explicit drift reason recorded. **Guardrail surface — cannot stay dark.** | 1 session |
| **P1** | Re-enable `test_iter40_goals_kpi.py` (9), `test_iter41_signal_actions.py` (9), `test_iter19_polish_committee_medium.py` (8), `test_iter62_solve_wave2_wave3.py` (10) — these shadow the T2/T3/T1 surfaces we just shipped. | 2-3 sessions (in-process httpx rewrite) |
| **P2** | Mass-rewrite the `broken-masked-rewrite-needed` bucket (144 tests across ~15 files) using the `test_phase_b_chat_retention.py` httpx+ASGI pattern. Phase 4-large per the existing reclassification. | 1-2 weeks |
| **P3** | Fix the `broken-masked-isolation` bucket (18 tests) — per-test fixture isolation. Cheap and quick. | 1-2 days |
| **P4** | Triage the `broken-masked-prequel` bucket (255 tests, "Patch 8 quarantined"). These are pre-autonomous-sprint failures — needs file-by-file analysis to decide fix/xfail/delete. | 1-2 weeks |
| Optional | Delete the 5 `broken-masked` cookie-persistence tests; the feature is covered by FastAPI Depends. | < 1 hour |

---

## 7. Audit conclusions

1. **The 500 number is real.** Not 500 environmentally-gated tests — 500 broken-masked tests, 73 of which represent active coverage loss on shipped features.
2. **The T1–T5 + backlog-b targeted verdicts stand on their own evidence.** No PASS verdict was based on a skipped test.
3. **The "1090 passed, zero regressions" framing was overconfident.** It's accurate for the targeted spec verbatim, but mute on the 73 coverage-loss tests that could detect regressions in adjacent business logic. A more honest framing: *"1090 passed against the targeted spec verbatim; 73 dark tests on adjacent surfaces; 422 broken-masked-by-decision."*
4. **Guardrail-adjacent dark coverage is the highest acute risk.** `test_phase_b_solva_no_opinion.py` + `test_solva_v2_shield_invariant.py:131` should be re-enabled before any further Shield/Trust-Center work.

---

## 8. Ledger generation reproducibility

Re-generate this ledger:
```
cd /app/backend
python -m pytest --collect-only -q 2>&1 | tee /app/memory/sprints/skip_audit_collection.log
python -m pytest -rs --tb=no -q 2>&1 | tee /app/memory/sprints/skip_audit_run.log
# Then re-run the parse+classify Python snippet from this audit chunk.
```

