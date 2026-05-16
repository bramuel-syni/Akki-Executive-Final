# Phase E — CLOSEOUT ADDENDUM (Fix Bundle 1)

**Date:** 2026-05-16
**Trigger:** `e1_tester` flagged 2 WARNs on Sub-task H (Chat privacy-report PDF) + 1 render-smoke gap on Sub-tasks A + D.
**Scope:** PDF generator + render-smoke only. No other Phase E surface touched.

## Fix 1 — PDF renders the actual Trust Receipt signature (was `—`)

`routers/solva_phase_e_polish.py::chat_privacy_report_pdf` now fetches
the matching `synisense_trust_receipts` row for every audit entry
(WITHOUT the previous `payload_hash` projection exclusion). Each PDF
entry surfaces:

* `audit_id`
* `receipt_id`
* `version` (always `v1`)
* `signature` — the full HMAC-SHA256 hex (no truncation)
* `payload_hash` (first 22 chars of `sha256:...` + ellipsis)
* `timestamp`

Verification footer line, italicised:

> *To verify: compute HMAC-SHA256 of the audit body with the per-tenant
> key (your Synisense admin console) and compare to the signature above.*

When a legacy audit row has NO matching trust receipt, the entry shows
"(no receipt recorded)" instead of silently rendering a dash —
unambiguous to the bank-QA reviewer.

## Fix 2 — PDF reads as natural-language prose, not a form

Per-entry layout switched from a 7-row table to TWO sections:

### Narrative paragraph (Body 10pt, leading 14pt)

Identical sentence the UI audit panel composes. Example output from
the test fixture (extracted with `pypdf`):

> Synisense shielded 3 person names, 2 monetary figures, 1 organisation
> name, and 1 email address before any LLM saw your message. The
> redacted content was read by Anthropic's claude-sonnet-4-5. Exposure
> reduction: 92.5% (almost all sensitive content shielded). Dilution:
> 11.0% (most semantic content preserved). Purpose: Chat reply.

### Audit references block (Courier 8pt, indented, grey)

Five lines of monospaced key/value pairs as above.

### Aggregate footer (Body 9pt)

> Across this conversation, Synisense governed 2 LLM calls across 3
> messages. Average exposure reduction: 90.2%. Average dilution: 12.8%.

### Verification footer (oblique, 8pt, lighter grey)

Verification recipe as above.

## DRY — explainer composer shared between UI panel and PDF

NEW pure helpers in `routers/chat_audit_panel.py`:

| Helper | Used by |
|---|---|
| `compose_audit_entry_prose(audit_row, receipt_row)` | UI `get_audit_panel` endpoint + PDF `_build_pdf_bytes` |
| `compose_aggregate_footer(...)` | PDF aggregate footer (UI `get_audit_panel_aggregate` already has a sibling string; left as-is to avoid scope creep) |

`get_audit_panel` was refactored to call `compose_audit_entry_prose`
and PROJECT only the public subset of the references — `signature`
and `payload_hash` are intentionally NOT surfaced on the UI (security-
by-design). They surface ONLY on the downloadable PDF so the tenant
can self-verify the HMAC chain.

This DRY contract is locked by two new tests:

* `test_pdf_builder_narrative_uses_shared_composer` — asserts the
  PDF text content contains the same sentence the composer produces.
* `test_audit_panel_endpoint_still_hides_signature` — asserts the UI
  panel response carries `trust_receipt_id` + `trust_receipt_version`
  but NOT `signature` / `payload_hash`.

## Fix 3 — Render-smoke covers the new Phase E React surfaces

`/app/frontend/scripts/render-smoke.js` `ROUTES` array extended by
three entries (Phase E Sub-tasks A + D):

| Route | What's exercised |
|---|---|
| `/app/solva` | Solva landing page (now Phase D-routing per Sub-task A) |
| `/app/solva/phase-d/session/new?submodule=seek_clarity` | New `SolvaPhaseDSession.jsx` page boots a fresh Phase D session |
| `/app/admin/synisense-observability` | New `SynisenseObservability.jsx` admin dashboard |

The admin route renders the AppShell + headers cleanly even when the
caller isn't a superadmin (it shows the API 403 inside the error
panel via `data-testid="syn-obs-error"`) — no fatal console errors,
no uncaught page errors.

Final smoke output:

```
[render-smoke] PASS — 11 routes clean · 2 upload paths green · Patch 28
interactions green · Chunk 4 wizard green · Chunk 5 create-artefact
green · Chunk 6 brief-drawer CTA green.
```

Browser install: `yarn playwright install chromium` (one-off in this
pod after a Playwright upgrade).

## Optional — tenant label hygiene

Looked into the `"Duplicate"` tenant label the tester observed. The
PDF reads `account.name OR account.email OR account.id`. In the dev
seed, one historical account record carries `name="Duplicate"` —
that's a real seeded value, not a code defect (kept for that
account's audit continuity). No fix applied; this is harmless dev-
seed data and would not surface for real tenants whose `name` is
populated normally.

## Tests + lint

| Metric | Before | After |
|---|---|---|
| pytest passing | 620 | **629** (+9 net new) |
| pytest skipped | 565 | 565 |
| Regressions | — | **0** |
| CI guard `test_no_direct_llm_calls_outside_shield` | PASS | **PASS** |
| `pyflakes` / `ruff` on touched files | clean | clean |

### New tests in `tests/test_phase_e_polish.py`

1. `test_compose_audit_entry_prose_renders_narrative_and_signature`
2. `test_audit_panel_ui_does_not_leak_signature_or_payload_hash`
3. `test_aggregate_footer_one_call_one_message`
4. `test_aggregate_footer_no_scores_when_no_audits`
5. `test_pdf_builder_renders_signature_when_receipt_present`
6. `test_pdf_builder_renders_placeholder_when_no_receipt`
7. `test_pdf_builder_narrative_uses_shared_composer`
8. `test_chat_privacy_report_pdf_renders_signature_e2e` (E2E)
9. `test_audit_panel_endpoint_still_hides_signature` (E2E)

## File diff summary

```text
MODIFIED backend
  routers/chat_audit_panel.py     +109 lines (composer helpers + refactor)
  routers/solva_phase_e_polish.py rewrite of _build_pdf_bytes (+narrative
                                  prose, +signature rendering, +aggregate
                                  + verification footers, +receipt fetch)
  tests/test_phase_e_polish.py    +9 new tests

MODIFIED frontend
  scripts/render-smoke.js         +3 routes (Solva landing, Solva Phase D
                                  new session, Synisense Observability)
```

## Status

✅ **PHASE E — closed (Fix Bundle 1 landed 2026-05-16)**.
**Next:** Phase F + Phase E.5 bundled (real Engine signal generation
+ seed-payload support on the Phase D framing endpoint).
