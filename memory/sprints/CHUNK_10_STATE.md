# Chunk 10 — 16-May Pulse-surface P1 + P2 batch

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. QA-2026-05-16-022 → -028 all DONE.
**Source spec:** `/app/memory/qa_reports/QA_REPORT_16MAY2026.md` §§ -022 → -028.

This document captures the non-trivial decisions on the Pulse surface so a future agent doesn't have to re-derive them.

## 1. Citation-stripper regex catalogue

`stripCitations()` in `pages/Pulse.jsx` removes the following patterns from any string before render. The list is conservative — only well-formed document-citation-style markers, not regulatory references like "GDPR Article 5" or "FCA SYSC 9.2".

| Pattern | Example | Why we strip |
|---|---|---|
| `\s?\[(?:doc\|source\|src\|file)[^[\]]{0,80}\]` | `[doc:audit_pack.pdf]`, `[source:Q2_capital_pack]` | Inline file-name markers belong in the drawer's Source section, not the prose |
| `\s?\([^()]*\.(?:pdf\|docx\|xlsx\|pptx\|csv)[^()]*\)` | `(Q2_capital_pack.pdf)`, `(source: audit.docx)` | Parenthetical filename mentions interrupt reading flow |
| `\s?\(p\.\s*\d{1,4}(?:[\-,]\s*\d{1,4})?\)` | `(p. 12)`, `(p. 12-14)` | Page-number citations are doc-context, not signal-context |
| `\s?\(source:[^()]*\)` | `(source: anything)` | Catches `(source: …)` patterns the file-extension regex missed |
| `\s?\[\d{1,3}\](?=[\s.,;:!?]\|$)` | `[1]`, `[12]` (only as footnote markers, NOT inline like `range[12]`) | Footnote-style references at sentence boundaries |

**Backend deliberately keeps citations in payloads.** The drawer's Source/References section renders citations from `signal.references[]`; stripping them at the producer would lose the audit trail. The architectural-invariant test `test_chunk10_citation_stripper_is_frontend_only` enforces this — `stripCitations` / `CITATION_PATTERNS` MUST NOT appear in any backend file.

## 2. Bullet-splitter heuristic (`splitToBullets`)

The QA spec says "each unique point as a bullet point". Strategy (lazy fall-through):

```
if text contains "\n\n":      split on paragraph breaks
elif text contains "\n":      split on single newlines
elif >= 3 sentences:          split on sentence boundaries
else:                          render as single paragraph (no benefit to bulleting <3 sentences)
```

Sentence-boundary regex: `/(?<=[.!?])\s+(?=[A-Z(])/` — splits on punctuation followed by whitespace + capital letter / opening paren. Avoids false-positives on common abbreviations (Dr., Mr., e.g., i.e.) because they're typically followed by lowercase.

## 3. Save / Bookmark merge (QA-028)

`save` and `bookmark` are the SAME backend action — both write `state="bookmarked"` on the signal row and an `action_type="saved"` row in `signal_actions`. They were visually rendered as two separate footer buttons in the drawer, which the QA author rightly flagged as redundant.

The Chunk-10 fix removes the Bookmark/Unbookmark buttons from `SignalDrawer` and keeps the single Save button. Card stays unchanged (already had only one bookmark icon).

The `save` endpoint now returns `{ok, state, id, saved: bool}` explicitly so the frontend can render a deterministic icon-state + correctly-directioned toast without interpreting `state` strings.

## 4. Schema-drift defensiveness pattern (lesson captured)

Pulse confidence field has TWO shapes in the wild:
- Canonical: STRING bucket `"high"|"medium"|"low"`
- Legacy/derived: FLOAT `0.0..1.0`

`routers/pulse.py:236` previously crashed with `AttributeError: 'float' object has no attribute 'lower'` when a legacy float row showed up. Fix shape: defensive `_conf_bucket(v)` helper that accepts both forms (≥0.66 → high, 0.33–0.66 → medium, <0.33 → low).

**Lesson:** any backend code path that calls `.lower()` / `.upper()` / `.strip()` on a Mongo-stored field should be wrapped with an `isinstance(v, str)` guard OR a coercion helper. Future chunks should audit Pulse / Solva / Cycle surfaces for similar string-method calls and apply the same defensive pattern.

## 5. Per-account comment privacy (QA-022)

Verified at `routers/pulse.py:289-312` — feed serializer filters `signal.comments[]` by `c["account_id"] == ctx.account.id` before returning. A second account's comments are NEVER surfaced on the caller's feed. The test `test_qa022_pulse_feed_hides_other_users_comments` guards this contract.

## 6. Test fixtures (seed Pass E)

`backend/scripts/seed_chunks.py::_seed_chunk10_pulse_signal_fixture` writes one signal per bramuel context with:
- Pre-populated comment (so QA-022 is renderable without driving the comment UX)
- `[doc:capital_pack.pdf]` + `[doc:audit_report.pdf]` markers in summary/body/reasoning (so QA-026 stripper is visible)
- Three `\n\n`-separated paragraphs in `reasoning` (so QA-026 bullet split fires)
- `type=risk`, `topic_class=capital`, `freshness=new` (so QA-027 chips populate)
- `confidence="high"` STRING (post schema-drift lesson)

Idempotent via `chunk10_pulse_marker="v1"` on the signal row.

## 7. Architectural invariants reconfirmation

- ✅ No new LLM call sites
- ✅ `account_id == tenant_id` privacy boundary intact on save / unsave / comment
- ✅ No `repr(exc)` leaks
- ✅ No new third-party libraries
- ✅ Frontend `stripCitations` does NOT exist in backend (static check)

## 8. Follow-ups (queued, not in Chunk 10 scope)

1. **Schema-drift audit** — Solva / Cycle / Strategic Goals routers should be audited for the same `.lower()`-on-Mongo-value pattern. Track-4 candidate.
2. **High-confidence chip on drawer** — currently the drawer chip cluster shows confidence only when `typeof === "number"`. After the schema-drift fix backend STRINGS are the canonical shape — should also render a chip when `confidence === "high"`. Minor polish; queued for Chunk 11 or 12 if it touches Pulse.
3. **Resolved status tab smoke** — render-smoke step 12 asserts the duplicate Resolved chip is GONE; it doesn't yet assert the canonical Resolved STATUS tab works. Worth adding when a tester finds a regression.
