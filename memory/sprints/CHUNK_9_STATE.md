# Chunk 9 — Add-a-Contribution attach feature

**Date:** 2026-05-18
**Status:** Closed. QA-2026-05-16-017 → -021 all DONE.
**Source spec:** `/app/memory/qa_reports/QA_REPORT_16MAY2026.md` §§ -017…-021.

This document records the locked decisions and contracts for the
Add-a-Contribution attach surface so a future agent touching this
flow doesn't relitigate the trade-offs.

## 1. Picker placement decision

**Decision:** Inline a new `ContributionAttachPicker.jsx` local to the
Cycle Manager surface; do NOT share with the Solva attach modal.

**Rationale (YAGNI vs shared `DocumentAttachPicker`):**
- The Solva flow has its own `AttachDocumentModal.jsx` with
  session-attach semantics (the attached doc is treated as
  ephemeral framing, not a stored journal artefact).
- Contribution attach binds the doc to a server-stored
  `cycle_contributions.source_doc_id` field — different lifecycle.
- Two consumers ≠ shared abstraction. Per the strict-scope rule,
  defer dedup to Chunk 12+ when a third consumer is stable.

**File:** `frontend/src/components/cycle/ContributionAttachPicker.jsx`
(262 lines, named export, two-tab dialog: "From Document Journal" +
"Upload External"). All interactive elements carry data-testids.

## 2. Combined-scoring contract (QA-020)

**Decision (a) from dispatch:** Concatenate body_text + attachment's
extracted_text into a single string, run the existing
`_heuristic_score` heuristic once. Single rubric pass.

**Implementation:**
```python
async def _build_combined_contribution_text(
    *, context_id, body_text, source_doc_id,
) -> str:
    parts = []
    body = (body_text or "").strip()
    if body:
        parts.append(body)
    if source_doc_id:
        doc = await db.documents.find_one(
            {"id": source_doc_id, "context_id": context_id}, ...)
        if doc:
            title = doc.get("name") or doc.get("original_filename") or "attached document"
            extracted = (doc.get("extracted_text") or "").strip()
            if extracted:
                parts.append(f"[Attached: {title}]\n{extracted}")
            else:
                parts.append(f"[Attached: {title}]")
    return "\n\n".join(parts)
```

**Robustness guarantees:**
- Missing attachment id (doc deleted between create + score) →
  silent fallback to body_text alone. Never 500s.
- Attached doc with no extracted_text (OCR pending) → marker
  string carries the doc's title so the heuristic can still pick
  up name-token overlap with the contribution_description.
- Body-only / attachment-only / both — all three call-shapes
  flow through the same single-pass scorer.

**Audit surface:** the score endpoint update payload includes:
```python
"scoring_input": {
    "has_body_text": bool((rec.get("body_text") or "").strip()),
    "has_attachment": bool(rec.get("source_doc_id")),
    "combined_char_count": len(combined_text),
},
```
so any future audit/UI can render "Scored: attached doc + pasted
text" if both contributed.

## 3. CTA-gating contract (QA-021)

**Frontend:** `disabled={busy || (!draft.body_text.trim() && !draft.attached_doc)}`.

**Backend:** Pydantic `model_validator(mode="after")` on
`ContributionIn` rejects when neither `body_text` nor
`source_doc_id` is present:
```python
@model_validator(mode="after")
def _qa_021_at_least_one_input(self):
    has_body = bool((self.body_text or "").strip())
    has_doc = bool(self.source_doc_id)
    if not (has_body or has_doc):
        raise ValueError(
            "Contribution must include at least one of `body_text` or "
            "`source_doc_id` (QA-2026-05-16-021)."
        )
    return self
```

This produces HTTP 422 (Pydantic) on the bad-shape request. Frontend
disables the CTA AND backend rejects empty payloads — defence in
depth, neither side is single point of failure.

## 4. Auto-Title behaviour (QA-018)

**`titleEditedByUser` state flag** tracks whether the user has typed
in the Title field since the form opened. Three resulting branches:

| Event | titleEditedByUser | Action |
|---|---|---|
| Attach doc | `false` AND title is empty | Auto-populate title with `doc.name` |
| Attach doc | `true` OR title already has text | LEAVE title untouched |
| User types in Title | n/a | Flip flag to `true` |
| Remove chip | `false` | Clear the auto-populated title |
| Remove chip | `true` | LEAVE user-typed title untouched |
| Submit | n/a | Reset flag + clear title on success |

This is the spec's "doesn't destroy user work" guarantee, surfaced
on both add and remove paths.

## 5. Seed data model alignment

The seed script (`backend/scripts/seed_chunks.py` Pass C) writes
THREE collections in lockstep so the live UX runs end-to-end:

```
db.cycles                              ← MASTER (status="active")
  id: cyc-c9-xxxxxxxx
  context_id, account_id, title, status, created_at, activated_at,
  closed_at: None
  chunk9_seed_marker: "v1"

db.cycle_agendas
  id: cyc-c9-xxxxxxxx                  ← MUST equal cycles.id
  cycle_id: cyc-c9-xxxxxxxx            ← alias for new code paths
  context_id, account_id, title, status: "active",
  items: [{id: agi-c9-xxxxxxxx, label: "Risk register update", ...}],
  chunk9_seed_marker: "v1"

db.cycle_team
  id: tm-c9-xxxxxxxx
  agenda_id: cyc-c9-xxxxxxxx           ← MUST equal cycles.id (filter)
  cycle_id: cyc-c9-xxxxxxxx
  context_id, name, email, role, contribution_description,
  owns_item_ids: [agi-c9-xxxxxxxx],
  status: "active",                    ← required by GET /cycle/team
  chunk9_seed_marker: "v1"
```

Three foot-guns to remember if you ever rewrite this:
1. `cycle_agendas.id` MUST equal `cycles.id` — the legacy resolver
   in `routers/cycle_manager._get_or_init_agenda` looks up
   `cycle_agendas` by the cycle_id parameter.
2. `cycle_team.agenda_id` MUST equal `cycles.id` AND `status` MUST
   be `"active"` — the GET /cycle/team list query filters on both.
3. `cycle_team.owns_item_ids` MUST reference at least one item id
   from the same agenda — otherwise PO-decision-#2's filtered
   eligible-contributors dropdown returns 0 rows and the
   contribution form silently can't pick a contributor.

## 6. Test coverage

`/app/backend/tests/test_qa_chunk_9.py` — 11 tests covering all 5
IDs + 3 cross-cutting guards:
- `test_qa_017_contribution_with_source_doc_accepted`
- `test_qa_018_attached_doc_remains_in_journal_after_chip_removed`
- `test_qa_019_paste_text_alongside_attachment_both_persisted`
- `test_qa_020_combined_scoring_uses_both_attachment_and_pasted_text`
- `test_qa_020_combined_scoring_works_with_attachment_only`
- `test_qa_020_combined_scoring_works_with_paste_only`
- `test_qa_020_combined_scoring_silent_fallback_when_source_doc_missing`
- `test_qa_021_contribution_rejected_when_no_input_provided`
- `test_chunk9_combined_scoring_single_pass_with_both_inputs`
- `test_chunk9_cta_gating_both_inputs_clear_means_reject`
- `test_chunk9_title_round_trip_preserves_user_intent`

`/app/frontend/scripts/render-smoke.js` step 10
(`smokeChunk9ContributionAttach`) — 11 hard-asserts on the live
preview. **Cannot soft-skip** when seed is present (per Chunk-9
close instruction); soft-skips ONLY when no bramuel context has an
active cycle + ≥1 team member + ≥1 doc (i.e. genuine fixture
absence, not code-correctness).

## 7. Follow-ups (queued, NOT in Chunk 9 scope)

1. **Chunk-8 smoke probe defensive fix** — its `/api/me/contexts`
   walk uses `c.id` instead of `c.context_id || c.id`. Dormant
   bug today (the active-context branch covers it), but if a
   future tester runs against an account where the active ctx
   has no overlay artefacts the probe will silently soft-skip
   instead of finding one via memberships. Fix when touching
   Chunk-8 surface next.
2. **Shared `DocumentAttachPicker`** — when a third consumer
   lands (post-Chunk 12), dedup `AttachDocumentModal.jsx` (Solva)
   + `ContributionAttachPicker.jsx` (Cycle) into one component
   with a `mode` prop (session-attach vs persisted-attach).
3. **render-smoke soft-skip audit** — Chunks 4/5/6/7 still
   soft-skip when bramuel ctx lacks the right seed. Pull each
   into `seed_chunks.py` as additional passes, or hard-flag the
   verification gap in `READ_FIRST.md`. Queued for a dedicated
   10-minute pass after Chunk 12.

## 8. Architectural invariants checkpoint

- ✅ **No direct LLM calls outside Shield** — `test_no_direct_llm_calls_outside_shield.py` PASS. Chunk 9 added zero LLM calls; combined-scoring uses the existing deterministic `_heuristic_score`.
- ✅ **Strict tenant_id == account_id scoping** — all 3 touched endpoints (`POST /contributions`, `POST /contributions/{cid}/score`, `GET /documents`) gate via `require_context_membership()`.
- ✅ **`{type(exc).__name__}: {str(exc)[:300]}` error format** — no `repr(exc)` introduced; all error paths route through `apiErrorMessage` (frontend) / `HTTPException` (backend) with the locked format.
- ✅ **Phase D unchanged** — Solva orchestration untouched in Chunk 9.
- ✅ **Pricing/governance unchanged** — `ALLOWED_PURPOSES` and pricing tables not touched.
- ✅ **Trust receipts HMAC** — Bank-QA surface unchanged.
