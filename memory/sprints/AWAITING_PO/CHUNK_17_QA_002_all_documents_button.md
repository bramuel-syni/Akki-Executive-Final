# AWAITING_PO — QA-2026-05-16-002 · Document Journal "All documents" button

**Routed:** 2026-05-21 (Chunk 17)
**Status:** AWAITING_PO clarification
**Backlog row:** `QA_BACKLOG.md` line ~26, priority P3
**Source:** `qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-002`

## Why this was routed instead of implemented

The QA row description reads verbatim:
> `Document Journal | "All documents" button surfaces need correcting (PO clarification needed)`

The row itself explicitly flags `(PO clarification needed)`. The QA author left the expected behaviour ambiguous — "surfaces need correcting" could mean any of:

1. The "All documents" button currently lands on the wrong route — fix the navigation target.
2. The button renders too many surfaces (cross-context leakage) — tighten the scoping.
3. The button label / placement is off — copy/UX fix.
4. The button works correctly but the SECTIONS the button reveals need different content rules.

Without the QA author's clarification (and without the screenshot referenced in the original sheet), shipping any one interpretation risks introducing the wrong fix. Per autonomy rules (route ambiguities, don't pause the chunk), this stays parked.

## Questions for PO

1. What is the current behaviour of the "All documents" button when clicked, and what should it be?
2. Which surface does "documents" refer to — `/app/workspace`? `/app/documents`? Both?
3. Is this a routing fix, a scope fix, or a copy fix?
4. Screenshot of the broken surface (referenced in the original report but not attached) — please link.

## Suggested resolution path once PO clarifies

- If routing: 1-line `navigate(...)` target change.
- If scope: backend filter tweak on the document listing endpoint.
- If copy/UX: text + Tailwind class change.

All three options are < 30 minutes of work. Defer until clarified.

## Owning chunk

Chunk 18 or later — re-pull from backlog once PO replies.
