# Post-Rewrite Ramp — Resumption Plan

**Date written:** 2026-05-16
**Updated:** 2026-05-18 (post pre-deploy hardening + Bank-QA evidence pack)
**Status:** Rewrite definitively closed. **662 pytest passing**, CI guard green, render-smoke green, deploy verdict 🟢 READY (with two 🟡 platform-side confirmations: tesseract in prod image, Postmark webhook URL). Bank-QA evidence pack assembled at `/app/memory/sprints/BANK_QA_EVIDENCE_PACK/`.

The 12-chunk QA sprint was PAUSED at Chunk 6 to make space for the rewrite. This document is the queue for what comes next.

---

## What's new in this update (2026-05-18)

- **Track 4 has been completed** — the Bank-QA evidence pack (`BANK_QA_EVIDENCE_PACK/`) is assembled, indexed, and printable.
- **A new pre-deploy "before bank QA walkthrough" Track 0 sits at the very top** — two 🟡 platform-side items must be confirmed (or accepted as 🟢) before bank-QA's first end-to-end pass.
- Track 1 (Chunk 7) remains the highest-priority unblocked product work.

---

## Track 0 (NEW) — Pre-bank-QA platform confirmation

These are user-action items that don't require code changes. Confirm before bank-QA's first verification pass.

| # | Item | Risk if skipped | Action |
|--:|------|------------------|--------|
| 1 | ✅ **DONE (2026-05-18)** — `tesseract-ocr` + `tesseract-ocr-eng` baked into `Dockerfile.backend` runtime stage. Effective on next build. | Image uploads return `status=failed` for OCR content. Graceful but bank-QA-visible. | Resolved in repo. Next deploy will carry it. |
| 2 | Confirm Postmark inbound webhook URL points at production | Inbound email silently doesn't work. No crash. | Log into Postmark dashboard → confirm inbound stream's webhook URL is `https://akki.syni.ai/api/inbound/postmark`. |
| 3 | Confirm `SYNISENSE_MASTER_SECRET` is set on prod (NOT the dev fallback) | Trust receipts signed with fallback are NOT verifiable. Bank-QA verification script will FAIL. | Set a high-entropy random value in Emergent Platform secrets. Once set, do NOT rotate. |
| 4 | Confirm `CLAMAV_HOST` / `CLAMAV_PORT` reachable from prod backend | Document upload returns 503 ClamAVUnreachable. Hard fail. | Verify ClamAV daemon is up and reachable. |
| 5 | Run the 15-minute post-deploy smoke-test path from `PROD_DEPLOY_CHECKLIST.md` § 6 | First user reports might catch what you missed. | After deploy, run the 6-curl-probe sequence. |

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

> **⚠ SUPERSEDED 2026-05-18 by `qa_reports/QA_BACKLOG.md`.**
> The authoritative QA tracker is now the 16-May report (51 actionable findings
> + 2 PO clarifications). The 14 rows below are retained as historical record
> only — do NOT dispatch against this table. New work must quote IDs of the
> form `QA-2026-05-16-NNN` from `QA_BACKLOG.md`.

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

### Track 3 (P0–P3) — 16-May QA Report Backlog (NEW canonical tracker)

**Source of truth:** `/app/memory/qa_reports/QA_BACKLOG.md`
**Verbatim spec:** `/app/memory/qa_reports/QA_REPORT_16MAY2026.md`

**Priority histogram:** `P0: 6 (DONE — Chunk 7, 2026-05-18) · P1: 11 + 17 (DONE — Chunk-8 8 + Chunk-9 5 + Chunk-10 1 + Chunk-11 3, 2026-05-21) · P2: 7 + 8 (DONE — Chunk-10 6 + Chunk-11 2, 2026-05-21) · P3: 2 · SV-Crit: 3 (DONE — Chunk-9.5, 2026-05-20) · SV-04..-08: 5 (BACKLOG → Chunks 13-14)`

**Chunk 8 close (2026-05-18):** all 8 Document Overlay IDs landed — see `SYSTEM_STATE.md § 4` Chunk 8 entry. Foundation + 8 visible-UX IDs + 25 new pytest + 1 render-smoke step. State machine doc: `sprints/CHUNK_8_OVERLAY_STATE.md`.

The 6 P0s (current user-visible errors / data-misrepresentation):

1. `QA-2026-05-16-005` — Document Journal "Add to Cycle" errors
2. `QA-2026-05-16-006` — Document Reader "Take into Solva" errors
3. `QA-2026-05-16-007` — Document Reader "Generate signals" errors
4. `QA-2026-05-16-012` — Akki Chat Archive → blank page
5. `QA-2026-05-16-043` — Enhance flow errors (minutes/Deck/Report/Committee Pack)
6. `QA-2026-05-16-047` — Monitor manual obj/project default status misrepresentation

PO to assign sprint chunks against backlog rows. Every dispatch quotes verbatim from the spec anchor. See `FORGETTING_MITIGATION.md` for protocol.

### Track 4 (P2) — Post-rewrite infra carryover

| # | Item | Source phase | Why | Effort |
|--:|------|--------------|-----|--------|
| 1 | 30s cold-start latency on `evolution-diff` + `generate-meta` | Phase E backlog | Deferred per user instruction "until after rewrite" | Investigation first |
| 2 | Token-accurate Shield metering (audit_log gains `input_tokens` + `output_tokens` + actual_cost_usd) | Phase F Sub-task D | Billing surface is illustrative today; bank QA will eventually want exact pricing | Medium |
| 3 | APScheduler hourly cron for `derivation_scheduler.run_hourly_pass()` | Phase F Sub-task B | Today derivation only runs on startup + on-demand; hourly cron is the locked steady-state cadence | Small |
| 4 | Full migration of 524 orphan legacy `solva_sessions` rows | Phase E Sub-task F | Phase E shipped soft-archive; full shape migration to `solva_phase_d_sessions` is post-rewrite | Large |
| 5 | Around-the-Goals sub_module clarification + ship | Solva backlog | Still `coming_soon: true` — needs PO clarification | Blocked on PO |

### Track 5 (P2) — Bank-QA evidence pack assembly

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
