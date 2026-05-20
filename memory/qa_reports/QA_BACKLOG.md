---
built: 2026-05-18
last_updated: 2026-05-20 (Chunk 9.5 — Solva SV-01/02/03 + Phase C audit regression closed)
source: /app/memory/qa_reports/QA_REPORT_16MAY2026.md (16-May rows)
              + /app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md (Solva rows)
total_findings: 51 (16-May) + 8 (Solva 20-May) = 59
total_clarifications: 2
priority_histogram: "P0: 6 (DONE) · P1: 10 + 18 (DONE Chunk-8 8 + Chunk-9 5 + Chunk-10 1 + Chunk-11 3 + Chunk-12 1) · P2: 7 (DONE Chunk-10 6 + Chunk-11 2) · P3: 2 · SV-Crit: 3 (DONE Chunk-9.5) · SV-High/Med: 5 (BACKLOG)"
maintainer: e1_main (Chunk 12 close, autonomous overnight)
---

# QA Backlog — 16 May 2026 (Master Tracker)

This is the canonical QA backlog. Every dispatch must quote verbatim from the
spec anchor of the row being worked. See `/app/memory/FORGETTING_MITIGATION.md`
for the anti-pattern protocol that produced this file.

Source-of-truth document: [`QA_REPORT_16MAY2026.md`](QA_REPORT_16MAY2026.md).
If this table and the source ever disagree, the source wins; rebuild this table.

## Backlog table

| ID | Surface | One-line summary | Suggested priority | Status | Sprint chunk | Spec anchor |
|----|---------|------------------|--------------------|--------|--------------|-------------|
| QA-2026-05-16-001 | Portfolio | Portfolio page should sit below landing page in post-login flow | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-001 |
| QA-2026-05-16-002 | Document Journal | "All documents" button surfaces need correcting (PO clarification needed) | P3 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-002 |
| QA-2026-05-16-003 | Document Journal | Add All / Uploaded / Akki-Generated tabs with badges below search | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-003 |
| QA-2026-05-16-004 | Document Journal | Rename "Add to Work Studio" → "Work with Document" + Compose modal | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-004 |
| QA-2026-05-16-005 | Document Journal | Add to Cycle CTA backend schema accepted document-attach payload | P0 | DONE | Chunk-7 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-005 |
| QA-2026-05-16-006 | Document Reader | "Take into Solva" payload aligned to backend StartV2In | P0 | DONE | Chunk-7 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-006 |
| QA-2026-05-16-007 | Document Reader | "Generate signals" parser hardened + loading state + long-running status copy + non-silent-reset (Path A info / Path B defensive fallback) | P0 | DONE | Chunk-7 (Fix-pass-2 2026-05-18) | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-007 |
| QA-2026-05-16-008 | Document Reader | Ask/Solva/Studio/Cycle buttons must match Document Journal drawer parity | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-008 |
| QA-2026-05-16-009 | Top bar | Remove the notification-bell sub-page entirely | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-009 |
| QA-2026-05-16-010 | Document upload | Add auto-focused search bar to "link to earlier document" panel | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-010 |
| QA-2026-05-16-011 | Akki Chat | Chat layout overflows right — not responsive at small viewports | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-011 |
| QA-2026-05-16-012 | Akki Chat | Archive button now navigates to dedicated /app/chats/archived page | P0 | DONE | Chunk-7 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-012 |
| QA-2026-05-16-013 | Akki Chat | Delete chat must notify "archived, recoverable" not "deleted" | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-013 |
| QA-2026-05-16-014 | Cycle Manager | Add spacing between top menu and Agent Cycle quick-actions card | P3 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-014 |
| QA-2026-05-16-015 | Cycle Manager | "Activate Cycle" CTA missing on tabs other than Agenda | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-015 |
| QA-2026-05-16-016 | Cycle Manager | Two identical Back/Next bars — bottom one needs "Back to Cycle Manager" label | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-016 |
| QA-2026-05-16-017 | Add a Contribution | Attach icon + From-Journal / Upload-External picker on contribution form | P1 | DONE | Chunk-9 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-017 |
| QA-2026-05-16-018 | Add a Contribution | Attached-document chip with remove icon below attach picker | P1 | DONE | Chunk-9 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-018 |
| QA-2026-05-16-019 | Add a Contribution | Paste-text box stays alongside attachment (do not remove) | P1 | DONE | Chunk-9 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-019 |
| QA-2026-05-16-020 | Add a Contribution | Record Contribution scores attached + pasted content together | P1 | DONE | Chunk-9 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-020 |
| QA-2026-05-16-021 | Add a Contribution | Record Contribution disabled until at least one input is supplied | P2 | DONE | Chunk-9 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-021 |
| QA-2026-05-16-022 | Pulse | Saved comments on signal cards do not display when re-opened | P1 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-022 |
| QA-2026-05-16-023 | Pulse | Save-signal icon must change state + bookmarked-tab notification | P2 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-023 |
| QA-2026-05-16-024 | Pulse | Saved-signal marker must appear wherever the signal surfaces | P2 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-024 |
| QA-2026-05-16-025 | Pulse | Remove duplicate "Resolved" filter under Freshness (keep tab one) | P2 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-025 |
| QA-2026-05-16-026 | Pulse | Remove document citations from signal content + bullet the context | P2 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-026 |
| QA-2026-05-16-027 | Pulse | Signal drawer missing New / High / Recommendation badges | P2 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-027 |
| QA-2026-05-16-028 | Pulse | Drawer needs resolved/bookmarked icon-state + drop "Bookmark" label | P2 | DONE | Chunk-10 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-028 |
| QA-2026-05-16-029 | Work Studio — Document Overlay | Overlay shell + dimmed page + close returns to list — overlay component + new GET endpoint | P1 | DONE | Chunk-8 | Live verification ready 2026-05-18 fix-pass · `qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-029` |
| QA-2026-05-16-030 | Work Studio — Document Overlay | Toolbar with Draft/InReview/Committed variants + Move-to-review (owner only) + lifecycle endpoints | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-030 |
| QA-2026-05-16-031 | Work Studio — Document Overlay | Intelligence card collapsed with RAG accent (≥80 green / 50-79 amber / <50 red) | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-031 |
| QA-2026-05-16-032 | Work Studio — Document Overlay | Intelligence modal — source map, per-section confidence, framing, gaps, recs, audit trail | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-032 |
| QA-2026-05-16-033 | Work Studio — Document Overlay | Document Surface inline editing (tiptap) + 30s autosave; read-mode default per Divergence #1 | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-033 |
| QA-2026-05-16-034 | Work Studio — Document Overlay | AI Revision side panel + Shield-routed `/revise` + server-enforced source-doc allowlist | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-034 |
| QA-2026-05-16-035 | Work Studio — Document Overlay | Version History modal + `work_studio_artefact_versions` collection + Pre-commit snapshot + restore (Draft/InReview only) | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-035 |
| QA-2026-05-16-036 | Work Studio — Document Overlay | Commit Confirmation modal + pre-commit snapshot + lifecycle commit + lock | P1 | DONE | Chunk-8 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-036 |
| QA-2026-05-16-037 | Work Studio — Document Cards | Status badge per card (Draft / In Review / Committed) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-037 |
| QA-2026-05-16-038 | Work Studio — Document Cards | Lock icon overlay on Committed-state document cards | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-038 |
| QA-2026-05-16-039 | Work Studio — Document Cards | Confidence score with RAG colouring on every card | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-039 |
| QA-2026-05-16-040 | Work Studio — Document Cards | Persistent download icon on every card (source format) | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-040 |
| QA-2026-05-16-041 | Work Studio — Right Panel | Replace Ready-to-Compile → Recents and At-Risk → Needs Attention | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-041 |
| QA-2026-05-16-042 | Compile Modal | Step 2 Sources inline-upload prompt (nested-modal state preserved) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-042 |
| QA-2026-05-16-043 | Enhance flow | committee_pack accepted as first-class enhance kind (alongside deck/report/minutes) | P0 | DONE | Chunk-7 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-043 |
| QA-2026-05-16-044 | Enhance flow | Enhanced document mirrors Compile-Report journey (Recent + Akki Generated) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-044 |
| QA-2026-05-16-045 | Monitor | All / At Risk / On Track / Off Track / Achieved tabs + badges (obj+proj only) | P1 | DONE | Chunk-11 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-045 |
| QA-2026-05-16-046 | Monitor | Suggested objective/project removed from Suggested card after add | P1 | DONE | Chunk-11 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-046 |
| QA-2026-05-16-047 | Monitor | Manual obj/proj default = not_started (was off_track); not_started/achieved added to status vocab; no-data path | P0 | DONE | Chunk-7 (Fix-pass 2026-05-18) | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-047 |
| QA-2026-05-16-048 | Monitor | NED user cannot generate strategic goals (CTAs are Exec-only) | P1 | DONE | Chunk-11 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-048 |
| QA-2026-05-16-049 | Monitor — Strategic Goals | Strategic cards: RAG + % + hover-full-text + filter + sort + drawer-rewrite | P1 | DONE (Test 5 fixture verification deferred to Chunk 17) | Chunk-12 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-049 |
| QA-2026-05-16-050 | Context Bar | Exec-only account must show "Executive" only (hide NED chip) | P2 | DONE | Chunk-11 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-050 |
| QA-2026-05-16-051 | Context switcher | Loading state when user clicks Continue switching context | P2 | DONE | Chunk-11 | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-051 |

## Open clarifications (PO must answer before any dispatch picks these up)

| ID | Surface | One-line summary | Status | Spec anchor |
|----|---------|------------------|--------|-------------|
| QA-2026-05-16-CLR-A | Monitor — manual create | Pre-set status allowed on create? Pairs with -047 | NEEDS_PO_ANSWER | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-clr-a |
| QA-2026-05-16-CLR-B | Around the Goals | Sub-module behaviour spec is missing | NEEDS_PO_ANSWER | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-clr-b |

## Compound finding notes

- **QA-2026-05-16-029 … -036** form the new Document Overlay design. They are 8 distinct components but ship together as one surface; a dispatch picking any one should pull the entire 8-row block or explicitly justify the slice.
- **QA-2026-05-16-049** bundles 7 sub-bullets on the Strategic Goals UI (RAG colouring, percentage, hover-full-text, filter, sort, drawer rename, Update-goal mechanic). Sub-tickets to be split here when a sprint chunk pulls it in.
- **QA-2026-05-16-017 … -021** are the Add-a-Contribution attach-document feature; they ship as one set.
- **QA-2026-05-16-012 + -013** are paired (archive flow + delete notification).
- **QA-2026-05-16-047 + CLR-A** are paired (manual obj/project create status logic).

## Recommended next-dispatch shape (advisory only — PO assigns)

Bundle the 6 P0s into the next chunk; they are the only items that currently throw user-visible errors or block a core workflow:

1. **QA-2026-05-16-005** — Add to Cycle in Document Journal errors out.
2. **QA-2026-05-16-006** — Take into Solva in Document Reader errors out.
3. **QA-2026-05-16-007** — Generate signals in Akki Commentary errors out.
4. **QA-2026-05-16-012** — Archive button → blank page.
5. **QA-2026-05-16-043** — Enhancing minutes/Deck/Report/Committee Pack errors.
6. **QA-2026-05-16-047** — Manual obj/project default status misrepresentation.

P1 items are large UI rewrites (Document Overlay, Strategic Goals rewrite, Add-a-Contribution attach feature). Split into themed chunks rather than 28-in-one.


---

## Solva QA Brief (20 May 2026)

Source: `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md`. Native ID scheme `SV-NN` (kept separate from 16-May `QA-2026-05-16-NNN` rows so the two reports don't bleed).

| ID | Surface | Title | Priority | Status | Sprint chunk | Spec anchor |
|---|---|---|---|---|---|---|
| SV-01 | Solva landing | "How Solva Reasons" redirect goes to wrong URL | Critical | DONE | Chunk-9.5 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-01 |
| SV-02 | Solva sessions list | "View All Sessions" returns Field Required error | Critical | DONE | Chunk-9.5 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-02 |
| SV-03 | Solva sessions | Sessions saving + auto-title + toast + inline edit | Critical | DONE | Chunk-9.5 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-03 |
| SV-04 | Solva sessions list | Cards + ACTIVE/PAUSED/COMPLETE/REFUSED status badges + tabs | High | DONE | Chunk-13 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-04 |
| SV-05 | Solva sessions list | Real-time search bar (title + content) | High | DONE | Chunk-14 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-05 |
| SV-06 | Solva responses | Rich text formatting (paragraphs, lists, bold) | Medium | DONE | Chunk-14 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-06 |
| SV-07 | Solva session UX | Output window ≥60% viewport + scroll | Medium | DONE | Chunk-14 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-07 |
| SV-08 | Solva query | HTTP 422 reproduction + fix (screenshot referenced but not yet attached) | Critical | DONE | Chunk-14 | qa_reports/SOLVA_QA_BRIEF_20MAY2026.md#sv-08 |

## Phase C Audit-Panel Regression (20 May 2026)

Tracked separately from the 16-May / 20-May Solva findings because the audit panel is a Phase C deliverable, not a new spec. Detailed root-cause + fix narrative in `/app/memory/qa_reports/PHASE_C_REGRESSIONS.md`.

| Symptom | Surface | Title | Priority | Status | Sprint chunk |
|---|---|---|---|---|---|
| Sx1 | Inline audit panel | AxiosError 404 leaks verbatim into UI when audit row not ready | P0 | DONE | Chunk-9.5 |
| Sx2 | Trust Panel topline | "On standby" + 0/0/0 counters despite chat containing PII (ts type mismatch) | P0 | DONE | Chunk-9.5 |
| Sx3 | Audit-trail JSON payload rendering | Reported as "missing `at` field / truncated at `char_len: 100`" — verified NOT a bug (the `at` is rendered as a top-level row field, not inside the payload JSON) | N/A | RESOLVED-NO-BUG | Chunk-9.5 (diagnostic) |
