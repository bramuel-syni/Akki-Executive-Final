# Track B Phase B4 — G11 — Doc-extracted question → Q4Y promotion

**Dispatch:** 2026-06-04T06:25:00Z
**Scope:** persistence + provenance gap closure for G11. Doc-extracted `open_questions[]` now mirror into `cycle_questions` with stable-id upsert + orphan close-out + eager/lazy promotion sites.

**Hard nos honoured:** no Track A touch, no Phase 4 prep, no Operation-ID cleanup, no `shield_invoke` / LLM-prompt touch, no new env vars, no copy changes, no FE changes, no schema additions (`source_doc_id` already addressable per G13).

---

## Problem (per the approved Pre-Read)

Two compounding bugs:

- **Persistence gap.** Doc-extracted `open_questions` were cached only on `db.document_intelligence`. They never reached `db.cycle_questions`. CompanyHome's "Open questions" attention card reads from `cycle_questions` and showed **0** even when docs contained extracted questions. Clicking the card landed on an empty Q4Y list.
- **Provenance gap.** Even with persistence, the G13 drawer's "related document as attachment" surface needs `cycle_questions.source_doc_id`, which the only writer (`raise_question`) does not set. Doc-extracted questions must carry it.

---

## Fix

### 1. New promoter (`services/documents/intelligence_service.py`)

`promote_intelligence_questions_to_q4y(db, doc, context_id, account_id, open_questions)` — mirror of the signals promoter at line 63 of the same file. Stable id `q4y:from_intel:{doc_id}:{idx}`. Writes `cycle_questions` rows with:

- `context_id`
- `cycle_id=""` (sentinel — matches `admin_qa_hooks` for cycle-less doc-extracted questions)
- `text` (verbatim, capped 2000 chars)
- `asked_by_account_id` + `assignee_account_id = doc.account_id` (so the count reaches the executive who owns the doc)
- `asker_role` derived via `derive_asker_role(account_id, context_id)` (single membership lookup per promotion run)
- `source_doc_id = doc.id` (provenance for G13 drawer)
- `status="open"` (only on insert — never blindly reset by re-runs so user mark-answered isn't regressed)
- `history[]` initial `{kind: "raised_from_doc", actor_id, note: "Surfaced from document {name}"}`
- `promoted_from="document_intelligence"`

Idempotency contract — `$set` rewrites refined text + provenance every run; `$setOnInsert` pins `asked_at`, `status`, initial history so re-runs don't reset original surface timestamp.

Cap defensively at 8 (mirrors signals cap; intel envelope's own `[:4]` truncation can change).

### 2. Tightening 1 — orphan close-out (orchestrator-requested)

When the doc is re-extracted and the new question list shrinks (M→N, N<M), the leftover `q4y:from_intel:{doc_id}:{N..M-1}` rows are flipped to:

```python
{
  "status": "closed",
  "history": [..., {
    "ts": now_iso, "kind": "closed",
    "actor_id": account_id,
    "note": "superseded_by_reextraction",
  }],
}
```

**Rows are NOT deleted** — audit trail preserved. Idempotent — a row already `status="closed"` is skipped (no duplicate history entries on subsequent re-runs).

Implementation walks `db.cycle_questions.find({"id": {"$regex": f"^{re.escape(prefix)}"}})` with prefix `q4y:from_intel:{doc_id}:` and filters by `idx >= len(items)`.

### 3. Eager call site (`routers/documents.py`)

Inside the existing `extract_intelligence` background task, right after the signals promoter:

```python
try:
    from services.documents.intelligence_service import (
        promote_intelligence_questions_to_q4y,
    )
    await promote_intelligence_questions_to_q4y(
        db, doc=doc, context_id=context_id,
        account_id=account_id,
        open_questions=envelope.get("open_questions") or [],
    )
except Exception as e:  # noqa: BLE001
    _log.getLogger("documents.intelligence").warning(
        "promote_intelligence_questions_to_q4y failed for doc=%s: %s",
        doc_id, e,
    )
```

Failure is logged + swallowed (matches the signals promoter pattern — the drawer still works even if promotion fails).

### 4. Lazy call site — Brief-gate back-fill (`routers/documents.py`)

Inside the Brief-gate's signals-back-fill block (when no `db.signals` row exists yet but `document_intelligence` has cached signals), piggyback the same back-fill for questions:

```python
intel_questions = await db.document_intelligence.find_one(
    {"doc_id": doc_id, "context_id": context_id},
    {"_id": 0, "open_questions": 1},
)
iqs = (intel_questions or {}).get("open_questions") or []
if iqs:
    await promote_intelligence_questions_to_q4y(
        db, doc=doc, context_id=context_id,
        account_id=ctx["account"]["id"],
        open_questions=iqs,
    )
```

This back-fills Q4Y for any pre-G11 intel rows whose extraction predates the eager hook. Stable-id upsert means it's a no-op on docs already promoted eagerly.

---

## Tightening 2 — no-double-fire (orchestrator-requested)

Test 4 pins the contract end-to-end. Promoting `["Q1?", "Q2?", "Q3?"]` twice in succession (simulating eager + lazy paths both firing) keeps `cycle_questions.count_documents(...) == 3`. Stable-id upsert is what guarantees it.

---

## Lockdown tests (4 — well under R4 ≤10 cap)

**File:** `backend/tests/test_track_b_phase_b4_g11_q4y_promotion.py`

| # | Test | Asserts |
|---|---|---|
| 1 | `test_promote_questions_writes_to_cycle_questions_with_provenance` | Stable id, `source_doc_id`, `assignee_account_id`, `cycle_id=""`, `asker_role` derived, history `raised_from_doc`, `promoted_from="document_intelligence"`. |
| 2 | `test_promote_questions_is_idempotent_and_closes_orphans` | Three sub-paths: (a) same input twice → no dupes; (b) shrink from 2→1 → idx=1 flips to `closed` with `superseded_by_reextraction` history, NOT deleted; (c) re-run with shrunk input → NO duplicate `closed` history entry (close-out is idempotent). |
| 3 | `test_promote_questions_no_op_on_empty_list_when_no_prior_rows` | Empty input + no prior rows → returns `[]`, writes nothing. |
| 4 | `test_companyhome_attention_card_count_reflects_doc_extracted_questions` | Promote 3 questions → call `/api/contexts/{cid}/home/insights` → `body.insights.open_questions.count == 3`. Also: promote same 3 again (simulates eager+lazy double-fire) → count stays at 3. |

**Pytest verbatim:** 4/4 PASS in 3.61s.

**Combined regression sweep — 91/91 PASS in 20.90s:**
- `test_track_b_phase_b4_g11_q4y_promotion.py` — 4
- `test_track_b_phase3_questions_completion.py` — B3 Q4Y feature (last week's ship) → no regression
- `test_solva_v1_unchanged.py` — v1 byte-identical guard → intact
- `test_track_a_phase3_prompt_fix.py` + `test_track_a_phase3_narration.py` — Track A Phase 3 → no regression
- `test_phase_p5_14_workbook_analyze.py` — workbook engine → no regression
- `test_q4y_p0_c3_mark_answered.py` — mark-answered round-trip → no regression
- `test_phase_i5_open_questions.py` — asker_role pipeline → no regression

**Voice-lint:** clean across customer-copy surfaces.
**Ruff:** zero new errors introduced. Pre-existing rot in `documents.py` (E402/F401/F811 from unrelated earlier work) parked per "No Side Quests".

---

## Files touched (verbatim diff stat)

```
M backend/services/documents/intelligence_service.py     # +154 LOC: promoter + orphan close-out
M backend/routers/documents.py                           # +58  LOC: eager + lazy call sites
?? backend/tests/test_track_b_phase_b4_g11_q4y_promotion.py  # 4 lockdown tests
M memory/MASTER_STATE.md                                 # G11 row, Section 4 B4, Sections 6+7
?? memory/sprints/TRACK_B_PHASE_B4_G11_DOC_QUESTION_SURFACING.md
```

**No frontend changes.** Existing `CompanyHome` attention card route + existing `Questions.jsx` Q4Y page render the rows correctly — the gap was zero-write to `cycle_questions`.

---

## Risks honoured (per Pre-Read)

| # | Risk | Outcome |
|---|---|---|
| R1 | Re-extraction churns Q4Y | Mitigated by stable-id upsert + orphan close-out (T1). Test 2 lockdown. |
| R2 | Ripples into B3 Q4Y feature | None — B3 regression suite green (test 2 in combined sweep). |
| R3 | Ripples into B1 Onboarding | None — no route, page, or auth touched. |
| R4 | Ripples into Track A | None — Phase 3 regression suite green. |
| R5 | Auto-promotion changes UX expectations | Eager promotion matches the signals UX users already have. Open Questions card moving from 0 → N is the intended fix. |
| R6 | `derive_asker_role` cost | Single lookup per promotion run. Negligible. |

---

## Hard nos honoured

- ✓ No Track A touch.
- ✓ No Track A Phase 4 prep.
- ✓ No Operation-ID warning cleanup.
- ✓ No `shield_invoke` or LLM-prompt touch.
- ✓ No new env vars.
- ✓ No customer-facing copy changes (question text passes through verbatim).
- ✓ No DB schema additions.
- ✓ No frontend changes.

---

## Resume contract

Pause for tester journey-completion run. Track B Phase B4 G11 stays **🟡 SHIPPED tester-pending** in MASTER_STATE.md Section 3 + Section 4 until the live browser journey confirms:
1. Upload a reference-mode doc with content rich enough to yield ≥2 open_questions
2. Wait for intel extraction (Intelligence tab populates)
3. Navigate to `/app/home` — "Open questions" attention card count ≥ 2
4. Click the card → land on `/app/questions?status=open&context_id=...`
5. See the doc-extracted question rows in the Q4Y list
6. Click one card → drawer opens → "related document as attachment" surfaces the originating doc