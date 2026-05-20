# Chunk 13 — Solva SV-04 (Sessions list view with 4-bucket status badges)

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. SV-04 DONE. 55-vs-84 anomaly investigated → confirmed as correct context-scoping (per WS-R16).
**Source spec:** `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md` § SV-04.

## 1. Classifier contract (locked decision)

Computed-only — no session-document migration. Reads existing fields,
returns one of `("active", "paused", "complete", "refused")`. Pure
Python, no DB calls, no I/O.

| Bucket    | Rule                                                                   |
|-----------|------------------------------------------------------------------------|
| REFUSED   | `raw_status in {"refused", "abandoned"}` OR `layer_state == "refused"` |
| COMPLETE  | `raw_status == "completed"` OR `layer_state == "done"`                 |
| PAUSED    | `raw_status == "active"` AND `(now - updated_at) >= 24h`               |
| ACTIVE    | `raw_status == "active"` AND `(now - updated_at) < 24h`                |

**Pause threshold:** `PAUSE_THRESHOLD_HOURS = 24`. Constant exported
so tests can drive boundary cases deterministically.

**`abandoned → REFUSED` rationale:** The operator-driven session
closure endpoint (`routers/solva_phase_d.py:1334`) sets
`status="refused"` AND `layer_state="refused"`; the legacy `abandoned`
raw value carries the same UX semantics ("session closed without
synthesis acceptance"). Spec lists only 4 buckets; merging avoids
adding a fifth.

## 2. Timestamp coercion

`_last_activity(session)` checks in order: `updated_at` → `started_at`
→ `created_at`. Each timestamp goes through `_coerce_dt` which
tolerates:
- aware datetime (passes through)
- naive datetime (assumes UTC)
- ISO 8601 string (with or without `Z` suffix)
- missing / None / non-coerceable → returns None

Schema-drift defensive: a row with no timestamp defaults to ACTIVE
(not PAUSED) — claiming "≥24h since last interaction" without a
timestamp is a lie.

## 3. List endpoint shape

`GET /api/solva/v2/sessions?context_id=…[&q=…][&status=…]`

```python
{
  "items": [
    {
      "id": "...",                      # session_id (Phase D) or id (v2)
      "status": "active",               # raw stored status (legacy compat)
      "display_status": "active",       # NEW — 4-bucket per classifier
      "engine": "phase_d" | undefined,  # routing marker
      # ... other existing fields ...
    }
  ],
  "count": N,
  "status_counts": {                    # NEW — for tab badges
    "all": N, "active": Na, "paused": Np, "complete": Nc, "refused": Nr,
  }
}
```

**Filter rules (Chunk 11 status_counts pattern):**
- `q` filter applies at the Mongo find() level (against `intent` for
  v2 + `initial_framing`/`title` for Phase D). Counts AND items both
  drop when `q` doesn't match.
- `status` filter applies AFTER counts are computed. Tabs show stable
  counts as the user clicks between them — only the items list
  shrinks. Accepts the four display buckets verbatim; falls back to
  raw-status matching for legacy callers.

## 4. Read-only enforcement (defence-in-depth)

**Backend** — already enforced pre-Chunk-13 by
`routers/solva_phase_d.py::submit_answer:1013-1014`:
```python
if state in TERMINAL_STATES:
    raise HTTPException(status_code=409, detail=f"Session is {state}; no further answers.")
```
`TERMINAL_STATES = ("done", "refused", "abandoned")`. Chunk 13 didn't
need to add a new backend gate — verified the existing path via
`test_chunk13_read_only_enforced_on_complete_session` +
`_on_refused_session`.

**Frontend** — Chunk 13 added a dedicated read-only banner
(`solva-phase-d-read-only-banner`) above the `<Body>` block in
`pages/SolvaPhaseDSession.jsx`. The existing `<Body>` already routes
`status === "completed"`/`layer_state === "done"` to a synthesis-only
view (no input), and `status === "refused"`/`layer_state === "refused"`
to a refusal-only view (no input). The banner makes the read-only
state visually explicit AND deterministic for the smoke step.

## 5. 55-vs-84 anomaly — investigation result

Per dispatch instructions, ran the per-context count breakdown for
bramuel as of 2026-05-21:

| Collection                  | bramuel sessions | Per-context (5 contexts)        |
|-----------------------------|------------------|---------------------------------|
| `solva_phase_d_sessions`    | 124              | 75 · 30 · 11 · 6 · 2            |
| `solva_v2_sessions`         | 6                | 3 · 3 (one with NULL context)   |
| **Combined**                | **130**          | top context = 78 (75+3)         |

The original "55 vs 84" tester claim was an earlier snapshot; the
counts have grown since. **No bug.** Sessions are strictly
context-scoped per WS-R16 (privacy hardening dispatched in Chunk
9.5), which means the SV-04 list view correctly shows only the
sessions for the currently-active context. The largest single
context bramuel owns now contains 75 Phase D + 3 v2 = 78 sessions,
which is what would surface on the SV-04 tabs.

**Decision:** No fix required. If PO wants a cross-context aggregate
("My Solva sessions across all my workspaces"), that's a new feature
queued as `C17-003` in `CHUNK_17_CLEANUP_QUEUE.md`. Out of scope for
SV-04.

## 6. Sub-bullet coverage table (SV-04 spec → impl)

| Spec sub-bullet                                | Impl                                                                 | Test coverage                                                       |
|------------------------------------------------|----------------------------------------------------------------------|---------------------------------------------------------------------|
| Cards ordered most-recent-first               | Sort by `updated_at` desc (existing behavior)                       | n/a (pre-existing)                                                  |
| Title (auto-gen + inline-editable)             | Already shipped in Chunk 9.5 (SV-03)                                 | n/a (pre-existing)                                                  |
| Status badge (4 colours)                       | `StatusPill` palette → green/amber/blue/grey                         | render-smoke step 15 pill text check                                |
| 5 tabs (All + 4 buckets)                       | `STATUS_CHIPS` array; selects via `status` query param               | render-smoke step 15 filter presence                                |
| Count badges on each tab                       | `status_counts` from server → `solva-sessions-filter-count-{key}`    | render-smoke step 15 count consistency invariant                    |
| Counts strict to status filter (NOT included)  | Counts computed BEFORE applying status filter                        | `test_chunk13_counts_honour_q_filter_but_not_status_filter`         |
| q filter reduces counts                        | Counts computed AFTER q-filtered find()                              | same test above                                                     |
| Card click opens session                       | Existing `navigate(...)` based on `engine === "phase_d"`             | n/a (pre-existing)                                                  |
| Paused continuable                             | `layer_state !== "done"/"refused"` keeps the answer form rendered    | covered by `Body` component logic                                   |
| Complete/Refused read-only                     | Backend 409 + new read-only banner on Phase D session page           | `test_chunk13_read_only_enforced_on_complete_session` + smoke 15    |
| Status derivation is server-computed           | `services/solva_session_status.py` — pure compute                    | `test_chunk13_classify_*` (11 unit tests)                           |
| No session document migration                  | No `$set` of any new field on the session collections                | static check + diff review                                          |

## 7. Architectural invariants checkpoint

- ✅ All LLM traffic via `services.synisense.shield.client.invoke()` —
  Chunk 13 adds **zero** new LLM call sites. Status classifier is
  pure compute. CI guard PASS + `test_chunk13_no_new_direct_llm_calls`
  per-module sanity PASS.
- ✅ `context_id` scoping on the list endpoint — required query param
  + membership check + Mongo filter (`account_id AND context_id`).
- ✅ `tenant_id`/`account_id` boundary — no cross-tenant data leak.
- ✅ No `repr(exc)` leaks — submit_answer already uses
  `HTTPException(detail=…)` with locked copy.
- ✅ No blocking I/O in async routes.
- ✅ No new third-party libraries.
- ✅ Schema-drift defensiveness — classifier tolerates missing /
  mixed-type timestamps without raising.
- ✅ Chunks 7-12 unaffected — pytest count moved up by +18 across
  the touched files (50 passed across chunks 9.5/10/11/12/13 + CI
  guard).

## 8. Carry-forward notes

- The new `services/solva_session_status.py` module is a candidate
  for promotion to a shared `services/solva/__init__.py` re-export
  if a third consumer (e.g. a planned Solva admin dashboard) needs
  the same classifier. Single-source so far; revisit when a second
  use site lands.
- The frontend `StatusPill` palette was tightened to map both raw
  and computed values to the same chip. If the design system gets a
  formal `accent-warning` token, the amber PAUSED chip should swap to
  it (CSS-only change).

## 9. Out-of-scope (deferred)

- SV-05 search bar polish — Chunk 14.
- SV-06 rich text formatting — Chunk 14.
- SV-07 output window sizing — Chunk 14.
- SV-08 422 fix — Chunk 14 (needs the missing screenshot).
- Cross-context "My All Solva Sessions" aggregate view — queued as
  `C17-003` in `CHUNK_17_CLEANUP_QUEUE.md`.
