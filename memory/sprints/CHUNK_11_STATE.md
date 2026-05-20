# Chunk 11 — 16-May Monitor-surface P1+P2 batch (-045/-046/-048/-050/-051)

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. All 5 IDs DONE.
**Source spec:** `/app/memory/qa_reports/QA_REPORT_16MAY2026.md` §§ -045 / -046 / -048 / -050 / -051.

## 1. `status_counts` pattern (QA-045)

The Monitor list endpoint now returns a `status_counts` dict alongside `items` + `total`:

```json
{
  "kind": "objective",
  "items": [...],
  "total": 6,
  "status_counts": {
    "all": 23, "green": 8, "amber": 5, "red": 3,
    "achieved": 2, "not_started": 5
  }
}
```

**Key contract:** `status_counts` is computed off the SAME pipeline (lookup + owner_role filter applied) but WITHOUT the `rag_status` match. This means:

- If you filter `status=amber`, the items list shows only amber rows but `status_counts.green` still reflects the total green rows in scope.
- If you filter `owner_role=cfo`, both `items` and `status_counts` honour that filter — counts won't include rows owned by other roles.

This is the correct semantics for tab badges: clicking "On Track" tab shouldn't make the "At Risk" badge change.

**Implementation strategy:** the helper rebuilds the pipeline with the `rag_status` $match stripped, appends a `$group` on `rag_status`, and counts. The frontend tab strip reads `data.status_counts.{key}` directly with `count: sc[key]`.

## 2. Auto-suggest dedup (QA-046)

Pre-fix, `auto_suggest_objectives` iterated every active cycle in the context and returned them all as candidates. After a user accepted a suggestion, the next fetch returned the SAME suggestion because the seeding loop didn't know what had been materialised.

Fix shape: build an `accepted_keys` set from existing items' `source_refs[]` BEFORE building the candidate list. Any candidate whose `source_refs[0]` matches an entry in the set is skipped.

The keys are formatted `"<kind>:<id>"` (e.g. `"cycle:abc-123"`, `"solva_session:def-456"`). Same logic mirrored across both `_objectives` and `_projects` endpoints.

## 3. NED RBAC defence-in-depth (QA-048)

Frontend already hid the strategic-goal generation CTAs from NED accounts (`!isNED &&` guards). Chunk 11 adds server-side enforcement at TWO endpoints:

- `POST /contexts/{cid}/strategic-goals` (manual create)
- `POST /contexts/{cid}/strategic-goals/extract` (AI extract from doc)

Both raise `HTTPException(403)` when `declared_role.lower() == "ned"` with message:
> "Strategic goal generation is an Executive-only action. NED users have read-only access to strategic goals."

**Pattern:** defence-in-depth at the route handler level (not via a separate Depends, which would require the body parser to run first — Pydantic validation errors would surface as 422 before the 403). For tests that need to confirm the 403 path, supply a syntactically valid body so the guard fires.

## 4. Context-bar dual-role probe (QA-050)

`deriveRoleKicker` now requires THREE conditions to compose "Executive · NED":
1. `accountDeclaredRole === "dual"`
2. `activeContext.my_role === "executive"`
3. `contexts.some(c => c?.my_role === "ned")` — actual NED membership

Pre-fix only conditions 1+2 were checked. A stale `declared_role` left over from a role change could make condition 1 true even though the user had no NED contexts → label was wrong on every Exec context.

## 5. Context-switcher loading state (QA-051)

`ContextSwitchModal` adds a `continuing` state flag set on Continue click. The dismiss is deferred 50ms via `setTimeout` so the spinner paints first. Button is disabled + `aria-busy` while continuing.

**Lesson:** any handler that triggers a `window.location.reload()` (or any synchronous navigation) should show a transient loading state BEFORE the navigation begins. Users perceive instant-state buttons as "did nothing" on slow networks.

## 6. Latent Pulse `saved: bool` fix (carried from Chunk 10 follow-up)

`pulse_bookmark` and `pulse_unbookmark` now return `{ok, state, id, saved: bool}` explicitly. The Chunk 10 toast direction fix depended on this; the contract is now also tested in Chunk 10's `test_qa023_save_endpoint_returns_saved_flag`.

## 7. Test fixtures (seed Pass F)

`backend/scripts/seed_chunks.py::_seed_chunk11_monitor_fixture` writes one `achieved`-state objective per bramuel context. `score=100`, `trend="flat"`, `rag_status="achieved"`. Title includes "Chunk 11 seed" suffix for tester observability. Idempotent via `chunk11_monitor_marker="v1"`.

## 8. Architectural invariants reconfirmation

- ✅ No new LLM call sites
- ✅ `context_id` scoping on every touched endpoint
- ✅ Schema-drift defensiveness — NED detection uses `(... or "").lower()` to handle None/empty
- ✅ No `repr(exc)` leaks
- ✅ No new third-party libraries
- ✅ CI guard PASS

## 9. Follow-ups (queued, not in Chunk 11 scope)

1. **QA-049 (Strategic Goals deep work)** — Chunk 12 will handle the full rewrite (Current → Performance Score rename + Update Goal AI flow replacing manual editing). DON'T touch the Update flow here.
2. **Monitor status_counts in summary cards** — the summary cards at the top of `/app/monitor` could also surface the per-status counts. Currently only objective/project list panels do. Minor polish; queued for backlog.
3. **deriveRoleKicker — exec-only fallback** — for an Exec-only account in a NED context (boundary case), the kicker today shows "Non-Executive Director" because `role === "ned"`. The dispatch doesn't ask for this to change but PO might want the chip to show "Executive · NED" only when account is dual-declared. Captured here for future PO clarification.
