---
built: 2026-05-18
source: /app/memory/qa_reports/QA_REPORT_16MAY2026.md
total_findings: 51
total_clarifications: 2
priority_histogram: "P0: 6 · P1: 28 · P2: 15 · P3: 2"
maintainer: e1_main (forgetting-mitigation patch)
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
| QA-2026-05-16-005 | Document Journal | "Add to Cycle" CTA errors out — replace with 3-step Cycle Manager modal | P0 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-005 |
| QA-2026-05-16-006 | Document Reader | "Take into Solva" errors out on every option | P0 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-006 |
| QA-2026-05-16-007 | Document Reader | "Generate signals" in Akki Commentary errors + needs loading/status copy | P0 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-007 |
| QA-2026-05-16-008 | Document Reader | Ask/Solva/Studio/Cycle buttons must match Document Journal drawer parity | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-008 |
| QA-2026-05-16-009 | Top bar | Remove the notification-bell sub-page entirely | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-009 |
| QA-2026-05-16-010 | Document upload | Add auto-focused search bar to "link to earlier document" panel | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-010 |
| QA-2026-05-16-011 | Akki Chat | Chat layout overflows right — not responsive at small viewports | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-011 |
| QA-2026-05-16-012 | Akki Chat | Archive button leads to blank page — must open Archived Chats list | P0 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-012 |
| QA-2026-05-16-013 | Akki Chat | Delete chat must notify "archived, recoverable" not "deleted" | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-013 |
| QA-2026-05-16-014 | Cycle Manager | Add spacing between top menu and Agent Cycle quick-actions card | P3 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-014 |
| QA-2026-05-16-015 | Cycle Manager | "Activate Cycle" CTA missing on tabs other than Agenda | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-015 |
| QA-2026-05-16-016 | Cycle Manager | Two identical Back/Next bars — bottom one needs "Back to Cycle Manager" label | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-016 |
| QA-2026-05-16-017 | Add a Contribution | Attach icon + From-Journal / Upload-External picker on contribution form | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-017 |
| QA-2026-05-16-018 | Add a Contribution | Attached-document chip with remove icon below attach picker | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-018 |
| QA-2026-05-16-019 | Add a Contribution | Paste-text box stays alongside attachment (do not remove) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-019 |
| QA-2026-05-16-020 | Add a Contribution | Record Contribution scores attached + pasted content together | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-020 |
| QA-2026-05-16-021 | Add a Contribution | Record Contribution disabled until at least one input is supplied | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-021 |
| QA-2026-05-16-022 | Pulse | Saved comments on signal cards do not display when re-opened | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-022 |
| QA-2026-05-16-023 | Pulse | Save-signal icon must change state + bookmarked-tab notification | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-023 |
| QA-2026-05-16-024 | Pulse | Saved-signal marker must appear wherever the signal surfaces | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-024 |
| QA-2026-05-16-025 | Pulse | Remove duplicate "Resolved" filter under Freshness (keep tab one) | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-025 |
| QA-2026-05-16-026 | Pulse | Remove document citations from signal content + bullet the context | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-026 |
| QA-2026-05-16-027 | Pulse | Signal drawer missing New / High / Recommendation badges | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-027 |
| QA-2026-05-16-028 | Pulse | Drawer needs resolved/bookmarked icon-state + drop "Bookmark" label | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-028 |
| QA-2026-05-16-029 | Work Studio — Document Overlay | Overlay shell (3 vertical layers, dim + return to list on close) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-029 |
| QA-2026-05-16-030 | Work Studio — Document Overlay | Layer 1 Toolbar (left/right groups, Commit prominent, state-aware) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-030 |
| QA-2026-05-16-031 | Work Studio — Document Overlay | Layer 2 Document Intelligence card (collapsed + RAG accent) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-031 |
| QA-2026-05-16-032 | Work Studio — Document Overlay | Intelligence modal (source map, per-section, audit trail) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-032 |
| QA-2026-05-16-033 | Work Studio — Document Overlay | Layer 3 Document Surface inline editing + 30s autosave | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-033 |
| QA-2026-05-16-034 | Work Studio — Document Overlay | "Revise with AI" side panel — scope/tone, diff, accept/reject | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-034 |
| QA-2026-05-16-035 | Work Studio — Document Overlay | Version History modal (chronological, Preview / Restore, Pre-commit) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-035 |
| QA-2026-05-16-036 | Work Studio — Document Overlay | Commit Confirmation modal — summary, warnings, lock state | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-036 |
| QA-2026-05-16-037 | Work Studio — Document Cards | Status badge per card (Draft / In Review / Committed) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-037 |
| QA-2026-05-16-038 | Work Studio — Document Cards | Lock icon overlay on Committed-state document cards | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-038 |
| QA-2026-05-16-039 | Work Studio — Document Cards | Confidence score with RAG colouring on every card | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-039 |
| QA-2026-05-16-040 | Work Studio — Document Cards | Persistent download icon on every card (source format) | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-040 |
| QA-2026-05-16-041 | Work Studio — Right Panel | Replace Ready-to-Compile → Recents and At-Risk → Needs Attention | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-041 |
| QA-2026-05-16-042 | Compile Modal | Step 2 Sources inline-upload prompt (nested-modal state preserved) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-042 |
| QA-2026-05-16-043 | Enhance flow | Enhancing minutes/Deck/Report/Committee Pack errors out | P0 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-043 |
| QA-2026-05-16-044 | Enhance flow | Enhanced document mirrors Compile-Report journey (Recent + Akki Generated) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-044 |
| QA-2026-05-16-045 | Monitor | All / At Risk / On Track / Off Track / Achieved tabs + badges (obj+proj only) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-045 |
| QA-2026-05-16-046 | Monitor | Suggested objective/project removed from Suggested card after add | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-046 |
| QA-2026-05-16-047 | Monitor | Manual obj/project default status: Off-Track → Not-Started + Update CTA | P0 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-047 |
| QA-2026-05-16-048 | Monitor | NED user cannot generate strategic goals (CTAs are Exec-only) | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-048 |
| QA-2026-05-16-049 | Monitor — Strategic Goals | Strategic cards: RAG + % + hover-full-text + filter + sort + drawer-rewrite | P1 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-049 |
| QA-2026-05-16-050 | Context Bar | Exec-only account must show "Executive" only (hide NED chip) | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-050 |
| QA-2026-05-16-051 | Context switcher | Loading state when user clicks Continue switching context | P2 | BACKLOG |  | qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-051 |

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
