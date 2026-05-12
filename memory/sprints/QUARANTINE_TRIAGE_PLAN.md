# QUARANTINE TRIAGE PLAN

> Patch 11 deliverable. **READ-ONLY** — no tests modified. The user reviews
> this plan and picks which phases to execute. Generated 2026-05-12.

## Summary stats

- **Total files quarantined**: 70
- **Total tests** (visible def-counts; excludes parametrize fan-out): 187
- **By classification**:
  - OBSOLETE: 11
  - FIXABLE: 11
  - REWRITE: 48
- **By phase**:
  - Phase 1: 11 files
  - Phase 2: 3 files
  - Phase 3: 8 files
  - Phase 4: 43 files
  - Phase 5: 5 files

## Phase ladder

- **Phase 1 — OBSOLETE deletions** (quick wins, no test rewrite needed)
- **Phase 2 — FIXABLE small** (S effort, fixtures/schema patch)
- **Phase 3 — FIXABLE medium** (M effort)
- **Phase 4 — REWRITE small/medium** (new tests against current API)
- **Phase 5 — REWRITE large + UNCLEAR** (largest investment)

## Triage table

| Phase | File | Tests | Feature | Class | Effort |
|---|---|---|---|---|---|
| 1 | `test_akki_g1.py` | 0 | Auth/Account v1 | OBSOLETE | S |
| 1 | `test_akki_v3.py` | 0 | v3 scaffold | OBSOLETE | S |
| 1 | `test_iter6.py` | 7 | Early scaffold | OBSOLETE | M |
| 1 | `test_iter64_studio.py` | 0 | Late-iter scaffold | OBSOLETE | S |
| 1 | `test_iter65_landing.py` | 0 | Late-iter scaffold | OBSOLETE | S |
| 1 | `test_iter66_studio_engagement.py` | 0 | Late-iter scaffold | OBSOLETE | S |
| 1 | `test_iter67_regression.py` | 6 | Late-iter scaffold | OBSOLETE | M |
| 1 | `test_iter68_share_chair.py` | 8 | Late-iter scaffold | OBSOLETE | M |
| 1 | `test_phase10_infra.py` | 0 | Infra phase 10 | OBSOLETE | S |
| 1 | `test_sandbox_phase1.py` | 0 | Sandbox phase | OBSOLETE | S |
| 1 | `test_sandbox_phase2.py` | 0 | Sandbox phase | OBSOLETE | S |
| 2 | `test_iter15_board_pack.py` | 0 | Board pack export | FIXABLE | S |
| 2 | `test_phase_a_chat_streaming_audit.py` | 2 | Chat streaming audit | FIXABLE | S |
| 2 | `test_work_studio_briefings_visible.py` | 2 | Work Studio briefings | FIXABLE | S |
| 3 | `test_phase_b_chat_retention.py` | 5 | Chat retention | FIXABLE | M |
| 3 | `test_phase_b_chat_stream.py` | 4 | Chat SSE stream | FIXABLE | M |
| 3 | `test_phase_b_solva_no_opinion.py` | 5 | Solva guardrails | FIXABLE | M |
| 3 | `test_phase_i_solva_export.py` | 13 | Solva export | FIXABLE | L |
| 3 | `test_render_determinism.py` | 6 | Render determinism | FIXABLE | M |
| 3 | `test_solva_v2_post_redirect_recovery.py` | 5 | Solva v2 redirect | FIXABLE | M |
| 3 | `test_solva_v2_session_limits.py` | 5 | Solva v2 limits | FIXABLE | M |
| 3 | `test_solva_v2_shield_invariant.py` | 6 | Solva shield invariant | FIXABLE | M |
| 4 | `test_daily_review_solva_cycle.py` | 10 | Solva×Cycle daily review | REWRITE | M |
| 4 | `test_iter10_board_deck.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter11_speaking_notes.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter12_shares_home.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter16_learn_personalisation.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter22_billing_schedule.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter24_plays.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter25_plays_slice2.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter26_engagement.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter28_strategic_goals.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter29_score_history.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter30_blog_lens.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter31_lens_coach_email.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter32_report_deck_coach.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter33_summary_compose.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter34_share_evolution.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter36.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter37_38.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter39_briefings_objective_check.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter43_quick_results.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter44_prepare.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter45_shares_brief.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter48.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter49.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter50.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter51_inbound_enterprise.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter53_deep_tier_minutes.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter54_llm_spend_quota_inbound.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter56_regen_learning.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter58_walkin_solve.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_iter70_inbound_edge.py` | 9 | Sprint iter regression | REWRITE | M |
| 4 | `test_iter70_inbound_triage.py` | 6 | Sprint iter regression | REWRITE | M |
| 4 | `test_iter71_studio_blocks.py` | 0 | Sprint iter regression | REWRITE | S |
| 4 | `test_phase12_2_closeout.py` | 5 | Phase 12 closeout/e2e | REWRITE | M |
| 4 | `test_phase12_2_e2e.py` | 5 | Phase 12 closeout/e2e | REWRITE | M |
| 4 | `test_solva_v2_adversarial_guardrails.py` | 4 | Solva v2 adversarial | REWRITE | M |
| 4 | `test_solva_v2_integration.py` | 1 | Solva v2 full flow | REWRITE | S |
| 4 | `test_solva_v2_submodules.py` | 8 | Solva submodules | REWRITE | M |
| 4 | `test_sprint1.py` | 3 | Sprint scaffold | REWRITE | S |
| 4 | `test_sprint2.py` | 0 | Sprint scaffold | REWRITE | S |
| 4 | `test_sprint3.py` | 0 | Sprint scaffold | REWRITE | S |
| 4 | `test_sprint5.py` | 0 | Sprint scaffold | REWRITE | S |
| 4 | `test_sprint6.py` | 0 | Sprint scaffold | REWRITE | S |
| 5 | `test_iter18_cycle_blog.py` | 16 | Sprint iter regression | REWRITE | L |
| 5 | `test_iter27_monitor.py` | 11 | Sprint iter regression | REWRITE | L |
| 5 | `test_iter35_chat.py` | 13 | Sprint iter regression | REWRITE | L |
| 5 | `test_iter55_decks.py` | 11 | Sprint iter regression | REWRITE | L |
| 5 | `test_iter9_refactor_smoke.py` | 11 | Sprint iter regression | REWRITE | L |
