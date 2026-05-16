# Post-Rewrite Ramp — Resumption Plan

**Date written:** 2026-05-16
**Status:** Ready to dispatch. Synisense rewrite A → F closed at 648 pytest passing, CI guard green, render-smoke green.

The 12-chunk QA sprint was PAUSED at Chunk 6 to make space for the rewrite. This document is the queue for what comes next.

---

## Priority order

### Track 1 (P0) — Resume the 12-chunk QA sprint

Chunks 1-6 shipped before the rewrite. Resume at **Chunk 7**.

| Chunk | Surface | Scope | Estimated effort | Status |
|------:|---------|-------|------------------|--------|
| 7  | Home + Document Journal fixes | Hero card refresh, document upload polish (4-5 findings) | Medium | NEXT |
| 8  | Pulse renovation | Signal commentary, leading-indicator strip, "Take into Solva" | Medium | queued |
| 9  | Cycle Manager polish | Cycle preview drawer, audit-grade signage, briefing-aggregate fix | Medium | queued |
| 10 | Monitor refresh part 1 | "Update goal" UX iteration (Phase F shipped the mechanic; this iterates the UX) + Strategic-Goals panel | Medium | queued |
| 11 | Monitor refresh part 2 | Owner-role tabs, sparkline KPIs, drawer timeline polish | Small | queued |
| 12 | Work Studio renovation | Brief drawer CTA cleanup, artefact-from-source polish, board-pack compile UX | Medium | queued |

Original sprint document with detailed checklists is under `/app/memory/sprints/QA_SPRINT_CHUNK_*.md`.

### Track 2 (P1) — Reactivate the 14 deferred 15-May QA findings

These were paused at the start of the rewrite ("strict scope discipline: do NOT touch during rewrite"). Each carries a reproduction step and the surface it lives on. Process them in the order below (most-blocking first):

| # | Surface | Finding | Severity |
|--:|---------|---------|----------|
| 1 | Cycle Manager | Briefing aggregator double-includes archived items | High |
| 2 | Document Journal | "Take to Solva" CTA pulls stale evolution diff | High |
| 3 | Monitor | RAG badge in list still shows ghost amber on red items briefly | Medium |
| 4 | Pulse | Signal commentary blank for ANOMALY signals with empty payload trigger | Medium |
| 5 | Pulse | Toolbar tab order non-deterministic on first render | Medium |
| 6 | Work Studio | Brief-from-source modal forgets the last picked source on remount | Medium |
| 7 | Work Studio | Artefact list pagination skips a row at the 5/6 boundary | Medium |
| 8 | Cycle Manager | Status filter resets when navigating between cycles | Medium |
| 9 | Pulse | "Update" hover tooltip lingers after click | Low |
| 10 | Document Journal | Doc upload progress bar never reaches 100% (cosmetic) | Low |
| 11 | Misc UX | App-shell breadcrumb doesn't truncate long titles on mobile | Low |
| 12 | Misc UX | Sidebar collapsed-tooltip text overflows on Cyrillic | Low |
| 13 | Misc UX | Toast stacking pushes errors off-screen on tall sequences | Low |
| 14 | Monitor | Empty-state copy reads "no objectives" even when one is filtered out | Low |

Detailed reproduction steps + screenshots are stored in `/app/memory/sprints/QA_FINDINGS_15MAY.md`.

### Track 3 (P2) — Post-rewrite infra carryover

| # | Item | Source phase | Why | Effort |
|--:|------|--------------|-----|--------|
| 1 | 30s cold-start latency on `evolution-diff` + `generate-meta` | Phase E backlog | Deferred per user instruction "until after rewrite" | Investigation first |
| 2 | Token-accurate Shield metering (audit_log gains `input_tokens` + `output_tokens` + actual_cost_usd) | Phase F Sub-task D | Billing surface is illustrative today; bank QA will eventually want exact pricing | Medium |
| 3 | APScheduler hourly cron for `derivation_scheduler.run_hourly_pass()` | Phase F Sub-task B | Today derivation only runs on startup + on-demand; hourly cron is the locked steady-state cadence | Small |
| 4 | Full migration of 524 orphan legacy `solva_sessions` rows | Phase E Sub-task F | Phase E shipped soft-archive; full shape migration to `solva_phase_d_sessions` is post-rewrite | Large |
| 5 | Around-the-Goals sub_module clarification + ship | Solva backlog | Still `coming_soon: true` — needs PO clarification | Blocked on PO |

### Track 4 (P2) — Bank-QA evidence pack assembly

Bundle every closeout doc + sample artefacts (PDF, screenshots, audit-log samples, trust-receipt verification script) into a single zip suitable for the bank reviewer. This is a "package the work we already did" exercise — no new code.

| Item | Source | Status |
|------|--------|--------|
| PHASE_A → PHASE_F closeouts (6 docs) | `/app/memory/sprints/` | ✅ already written |
| REWRITE_FINAL_CLOSEOUT.md | this rewrite | ✅ written |
| Sample privacy-report PDF + text dump | `/app/memory/sprints/phase_e_addendum_artefacts/` | ✅ already saved |
| Sample HMAC verification script (Python, 30 lines) | needs writing | queued |
| Architecture diagram (mermaid → PNG) | needs drawing | queued |
| Screenshot pack (Observability / Billing / Monitor Update goal / Privacy PDF) | partially in `/tmp/` | needs collation |

---

## What to do FIRST

**Chunk 7 (Home + Document Journal fixes)** is the highest-priority unblocked item. It's medium-sized, exercises real user paths the bank QA reviewer will visit, and finishing it gets us to two-thirds of the original 12-chunk plan complete.

Dispatch shape:

```
CHUNK 7 — Home + Document Journal fixes
- Hero card refresh per the 30-finding QA report items 14-18.
- Document upload polish per items 22-25.
- Render-smoke must pass.
- Target: ≥660 pytest passing (648 + ~12 net new).
- Update SYSTEM_STATE.md § 4 + CHANGELOG.md when done.
```

## Open questions for the user when they wake

1. **Bank-QA pack timing** — is there a hard date for delivering the evidence pack? If yes, that flips Track 4 to P0.
2. **Around-the-Goals sub_module** — still blocked on your clarification. Should we hold for it OR start with a placeholder UX that's hidden behind a feature flag?
3. **Token-accurate metering** — Phase G+ when? It's the foundation for invoiced (not illustrative) billing.

## Status

📋 **Plan ready.** No code changes pending. Awaiting user's choice between (a) start Chunk 7, (b) skip to the 14 deferred findings, (c) work on the evidence pack instead, (d) take a beat.
