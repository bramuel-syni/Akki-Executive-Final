# Chunk 17 — 16-May P3 + Cleanup Queue

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. 1 P3 DONE + 1 P3 routed to PO + 3 cleanup-queue items resolved + 2 housekeeping items shipped.
**Source spec:** `/app/memory/qa_reports/QA_BACKLOG.md` P3 rows + `/app/memory/sprints/CHUNK_17_CLEANUP_QUEUE.md`.

This chunk is the "morning report win" the orchestrator predicted: closing C17-002 + C17-004 retroactively flips Chunks 12 and 14 from PARTIAL → DONE.

---

## 1. Items closed

### 16-May P3 (2 IDs)

| ID | Surface | Verdict | Files | Test |
|---|---|---|---|---|
| QA-2026-05-16-002 | Document Journal — "All documents" button | **AWAITING_PO** | n/a (routed) | n/a |
| QA-2026-05-16-014 | Cycle Manager — top-menu spacing | **DONE** | `pages/cycle/CycleList.jsx` — `<div className="pt-6" data-testid="cycle-list-quickactions-spacer" />` | `test_chunk17_qa014_cycle_quickactions_spacer_present` |

QA-002 was flagged in the backlog row itself as `(PO clarification needed)`. Routed to `AWAITING_PO/CHUNK_17_QA_002_all_documents_button.md` with 4 disambiguation questions for the PO. Chunk 18+ re-pulls once PO replies.

### Cleanup queue (3 entries closed)

| Entry | Action | Files | Test |
|---|---|---|---|
| **C17-001** Orphan EditGoalRow | DELETED — ~75 lines of dead code excised: `EditGoalRow` + `NumField` components, `editingId` state, `isEditing` prop threading, `onEdit/onCancel/onSaved` prop chain | `components/monitor/StrategicGoalsPanel.jsx` | `test_chunk17_c17_001_edit_goal_row_removed` |
| **C17-002** Seed Exec for QA-049 | EXTENDED — `seed_chunks.py` now iterates admin@akki.ai contexts + runs Pass H against each (11 fixtures minted) | `backend/scripts/seed_chunks.py:43-52` (`ADMIN_EMAIL` constant) + `:1064-1088` (loop block) | `test_chunk17_c17_002_admin_no_data_fixture_seeded` + `_seed_pass_is_idempotent` |
| **C17-004** SV-07 overflow-y | RESTRUCTURED — `ProseBlock` outer `<article>` AND inner `<div>` both carry `overflow-y-auto` + `max-h-[70vh]` (defence-in-depth) | `pages/SolvaPhaseDSession.jsx::ProseBlock` (lines ~653-680) | `test_chunk17_c17_004_solva_prose_outer_overflow_class` |

### Housekeeping (2 shipped)

| Item | Action | Files | Test |
|---|---|---|---|
| **Item 6** Non-owner seed identity | ADDED — admin@akki.ai inserted as `sub_role="viewer"` member of bramuel's largest context (`fbc54a51-...`, 75 Phase D sessions). Idempotent via marker `chunk17_non_owner_membership_marker="v1"`. Closes the Chunk 8 HUMAN_REQUIRED on Move-to-Review owner-only gating. | `backend/scripts/seed_chunks.py:1090-1120` | `test_chunk17_item6_admin_non_owner_membership` |
| **Item 7** Smoke probe defensive `||` | FIXED — `render-smoke.js:1018` now uses `c.context_id || c.id` (mirroring 3 existing call sites). Handles both legacy and WS-R16 `/me/contexts` shapes. | `frontend/scripts/render-smoke.js:1014-1022` | `test_chunk17_item7_smoke_probe_defensive_fallback` |

### Soft-skip audit (item 5) — decision-only, no code

Per orchestrator pre-lock, chose **option (b)**: annotate, don't seed. Updated `READ_FIRST.md` status snapshot to note that Chunks 4/5/6/7 smoke steps soft-skip on empty fixtures (pytest is authoritative for those surfaces).

---

## 2. Retroactive PARTIAL → DONE flips

C17-002 closing means admin@akki.ai (Exec-aligned via `declared_role="dual"`) can now reach the QA-049 no-data UI path that bramuel (NED) couldn't due to the Chunk-11 RBAC defence-in-depth. This **closes the Chunk-12 PARTIAL on Test 5** (verbatim no-data copy + Document Journal link). Tester pending; barring a regression, Chunk 12 flips to clean DONE.

C17-004 closing means the SV-07 overflow-y assertion now resolves to `"auto"` on either the outer or inner ProseBlock wrapper. **This closes the Chunk-14 PARTIAL on SV-07.** Tester pending; barring a regression, Chunk 14 flips to clean DONE.

Both retroactive closures will be reflected in the `AUTONOMOUS_SPRINT_LOG.md` once the orchestrator tester confirms.

---

## 3. AWAITING_PO routings

- **NEW** `AWAITING_PO/CHUNK_17_QA_002_all_documents_button.md` — QA-002 disambiguation: routing vs scope vs copy vs sections.

---

## 4. Architectural checkpoint

- ✅ Shield gateway exclusivity preserved — zero new LLM call sites.
- ✅ `context_id` scoping intact — only existing endpoints consumed.
- ✅ `tenant_id == account_id` boundary intact.
- ✅ No `repr(exc)` leaks.
- ✅ No new third-party libraries.
- ✅ Schema-drift defensive — Item 7 fix IS the defensive guard for the `/me/contexts` shape drift.
- ✅ Chunk-8 lifecycle state machine NOT modified.
- ✅ Pytest cross-chunk +8 (72 → 80).

---

## 5. Tests + smoke

`backend/tests/test_qa_chunk_17.py` — **8 tests:**
- 2 seed integration (C17-002 fixtures · idempotency)
- 1 seed integration (Item 6 non-owner membership)
- 1 static check (C17-001 EditGoalRow removal)
- 1 static check (C17-004 outer `<article>` overflow class)
- 1 static check (QA-014 spacer testid)
- 1 static check (Item 7 defensive `||` count)
- 1 CI sanity (touched files have no LLM imports)

**All 8 pass.** Cross-chunk regression (9.5/10/11/12/13/14/15/16/17 + CI guard) = **80 passed**.

Render-smoke unchanged in this chunk (step 16 already asserts overflow on a populated session via the existing inner-div selector; the outer `<article>` is now ALSO `overflow-y-auto` for defence-in-depth, so the same assertion remains green).

---

## 6. Seed verification (live)

```
[seed-chunks] Sample admin Exec no-data fixtures (Chunk 17 C17-002):
   - ctx=<admin-owned ctx-1>  goal=<gid-1>
   - ctx=<admin-owned ctx-2>  goal=<gid-2>
   - ctx=<admin-owned ctx-3>  goal=<gid-3>
   - ctx=<admin-owned ctx-4>  goal=<gid-4>
   - ctx=<admin-owned ctx-5>  goal=<gid-5>
   (11 total across all admin-owned contexts)

[seed-chunks] Chunk 17 non-owner membership: admin@akki.ai →
   ctx=fbc54a51-5a4f-4f2c-aeeb-661494275f4f (viewer role)
```

Re-run idempotent: 0 fresh mints on the second invocation.

---

## 7. Files touched

- `frontend/src/components/monitor/StrategicGoalsPanel.jsx` — C17-001 dead-code deletion (~75 lines).
- `frontend/src/pages/SolvaPhaseDSession.jsx` — C17-004 ProseBlock restructure.
- `frontend/src/pages/cycle/CycleList.jsx` — QA-014 spacer.
- `frontend/scripts/render-smoke.js` — Item 7 defensive `||`.
- `backend/scripts/seed_chunks.py` — C17-002 admin loop + Item 6 non-owner membership.
- NEW `backend/tests/test_qa_chunk_17.py` — 8 tests.
- NEW `memory/sprints/AWAITING_PO/CHUNK_17_QA_002_all_documents_button.md`.
- `memory/sprints/CHUNK_17_CLEANUP_QUEUE.md` — entries C17-001/-002/-004 marked RESOLVED.

---

## 8. Out-of-scope / deferred

- C17-003 cross-context Solva aggregate — AWAITING_PO (privacy boundary change).
- AWAITING_PO/CHUNK_11_QA_050 dual-role interpretation — unchanged.
- Track 4 infra (Chunk 18).
- Track 5 (Chunk 19).

---

## 9. Elapsed effort

~60 minutes — at the low end of the M (60-75 min) estimate. Single-block delivery (no internal split) worked cleanly because items are mostly independent and short.
