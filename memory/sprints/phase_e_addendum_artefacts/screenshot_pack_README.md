# Bank-QA Evidence Pack — Screenshot Pack README

**Document type**: Bank-QA reviewer companion (C19-003)
**Anchor**: `/app/memory/sprints/phase_e_addendum_artefacts/`

This README enumerates the screenshot evidence a Bank-QA reviewer
needs to walk the AKKI privacy + governance story end-to-end. Each
entry below is a single PNG that lives next to this README at
`/app/memory/sprints/BANK_QA_EVIDENCE_PACK/screenshots/`. The pack is
designed to be readable in **<10 minutes** by a non-engineering
reviewer — every screenshot is captioned so it stands alone without
cross-referencing the broader documentation set.

## How to capture / refresh a screenshot

1. Log into `https://akki-executive.preview.emergentagent.com` as the
   user role indicated below.
2. Navigate to the surface listed in the table.
3. Capture at 1920×1080 (default render-smoke viewport) for
   consistency.
4. Save as PNG in `/app/memory/sprints/BANK_QA_EVIDENCE_PACK/screenshots/`
   using the filename in the "File" column below.
5. If a screenshot becomes stale (UI drift), the responsible chunk in
   the table is the anchor for what changed and why.

## Required screenshots (10)

| # | Surface | File | Role | Caption | Anchor chunk |
|---|---------|------|------|---------|--------------|
| 1 | Portfolio landing page | `01_portfolio_landing.png` | Executive | "Post-login Portfolio — Exec sees own + member contexts. Role per context shown on each card." | Chunk 15 (QA-001 redirect race fix) |
| 2 | Akki Chat with Privacy Audit Panel open | `02_chat_privacy_audit_panel.png` | Executive | "Per-message redaction breakdown — counts by category, never values. Dilution + exposure-reduction scores surfaced inline." | Phase B.2 |
| 3 | Document Journal — signals view | `03_journal_signals.png` | Executive | "Auto-generated signals per document chunk; click to expand commentary; evolution-diff button on hover." | Phase C/D |
| 4 | Cycle Manager briefing aggregate | `04_cycle_briefing_aggregate.png` | NED | "NED pre-read pack. Briefing aggregated from journal artefacts; 'Back to Cycle Manager' link renamed in Chunk 15." | Chunk 15 (QA-016) |
| 5 | Pulse surface | `05_pulse_signals.png` | NED | "Late-breaking signals; capital-adequacy seed visible top card; Bell icon removed (QA-009)." | Chunk 10 / Chunk 15 |
| 6 | Strategic Goals drawer with Update Goal CTA | `06_strategic_goals_drawer.png` | Executive | "Goal drawer shows Performance Score % + Reassessed timestamp; Update Goal CTA visible because role=Exec (RBAC-gated)." | Chunk 11 (QA-048) + Chunk 12 (QA-049) |
| 7 | Solva session — Phase D synthesis layer | `07_solva_phase_d_synthesis.png` | Executive | "Layer 3 synthesis rendered with in-house proseBlocks renderer; 60vh panel sizing." | Chunks 13/14 (SV-04 through SV-08) |
| 8 | Work Studio Document Cards | `08_work_studio_document_cards.png` | Executive | "Cards show status badge + lock overlay + confidence chip + download button (QA-037 through QA-040)." | Chunk 16 |
| 9 | Admin observability dashboard | `09_admin_observability.png` | Superadmin | "Per-consumer Shield invoke rates + dilution scores; refusal rate breakdown; pricing-table signature." | Phase E Sub-task D |
| 10 | Admin cron-health endpoint response | `10_admin_cron_health_curl.png` | Superadmin | "Engine hourly cron heartbeat row; status=ok, duration_ms, summary visible." | Chunk 19 (C19-005) |

## Captions are MANDATORY

Each screenshot must carry the caption text from the table above as a
small annotation on the image (top-left corner, 14pt, white text with
black stroke). Reviewers should never have to cross-reference this
README to understand what they're looking at.

## What the pack proves end-to-end

Reading screenshots 1 → 10 in order tells the privacy-first governance
story:

1. **Login + tenancy** (1) — multi-context, multi-role from day one.
2. **Chat with audit transparency** (2) — privacy is visible to the user, not hidden in policy.
3. **Document-grounded reasoning** (3) — answers cite sources; nothing hallucinated.
4. **Pre-read assembly** (4-5) — automation accelerates governance; signals stay visible.
5. **Decision capture** (6-8) — Solva + Strategic Goals + Work Studio together carry the decision audit trail.
6. **Operator visibility** (9-10) — superadmin can prove the system is healthy without reading consumer content.

## Refresh cadence

Refresh after every major chunk that touches a captured surface. A
chunk's `_STATE.md` close-out note should mention whether the
screenshot pack needs an update. The closing audit (per quarter) does
a top-to-bottom refresh regardless.

---

**Last reviewed**: 2026-05-21 (Chunk 19 close).
**Owning artefact dir**: `/app/memory/sprints/BANK_QA_EVIDENCE_PACK/screenshots/`.
**Companion artefacts in this directory**:
- `verify_trust_receipt.py` (C19-001) — HMAC verifier
- `architecture_diagram.md` (C19-002) — Mermaid system diagram
- `phase_e_sample_privacy_report.pdf` — Privacy report sample
