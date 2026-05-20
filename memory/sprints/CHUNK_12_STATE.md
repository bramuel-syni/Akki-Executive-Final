# Chunk 12 — 16-May Strategic-Goals deep rewrite (QA-2026-05-16-049)

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. QA-2026-05-16-049 DONE.
**Source spec:** `/app/memory/qa_reports/QA_REPORT_16MAY2026.md` § QA-2026-05-16-049.

## 1. Update Goal contract (locked)

The new endpoint replaces the manual Edit flow with an Akki-driven reassessment. Three triggers for the no-data short-circuit:

| Trigger | When | Shield invoked? |
|---|---|---|
| Empty context | Zero docs AND zero engine signals | **No** — short-circuits before LLM call |
| LLM said irrelevant | Response has `{"relevant": false}` | Yes — once |
| Empty supporting IDs | LLM said `relevant=true` but `supporting_*_ids` arrays are empty | Yes — once |

All three return the verbatim spec copy:
> "No additional information found for this goal. Please upload a document with updated performance data so Akki can reassess."

## 2. Success-path mutation rule

ONLY non-null fields from the LLM response are persisted. The LLM is instructed to return `null` for fields it can't determine, and the endpoint honours that:

```python
if parsed["current_score"] is not None:
    set_doc["current_score"] = parsed["current_score"]
if parsed["probability"] is not None:
    set_doc["probability"] = parsed["probability"]
if parsed["status"] is not None:
    set_doc["status"] = parsed["status"]
```

This prevents the LLM from accidentally overwriting a probability score it had no evidence for.

## 3. `score_history` append rule

Only appends when `current_score` was actually updated (not on probability/status-only changes). Source flag `"akki_update"` distinguishes from manual-edit entries in the audit timeline.

## 4. Defensive JSON parsing (`_parse_update_response`)

The LLM sometimes wraps JSON in code fences or adds prose. The parser:
1. Tries to extract content between ```json ... ``` fences.
2. Falls back to the first `{...}` greedy match.
3. On `json.JSONDecodeError`, returns `{"relevant": False, "rationale": "JSON parse failed."}`.
4. Validates `status` against the closed set `_STATUS = ("on_track", "at_risk", "off_track", "achieved", "abandoned")`.
5. Clamps `current_score` and `probability` to 0–100.
6. Truncates rationale to 600 chars to bound payload size.

Any malformed response is treated as no-data — the goal is never mutated based on garbage LLM output.

## 5. RBAC

Carries over the Chunk 11 QA-048 pattern — `declared_role.lower() == "ned"` raises 403. Frontend `!isNED &&` guard hides the CTA; backend enforces defence-in-depth.

## 6. Frontend drawer rewrite

`GoalDetailDrawer` re-prop'd:
- **Removed:** `onEdit`
- **Added:** `contextId`, `onGoalUpdated(updatedGoal)`

State machine:
```
idle  → [user clicks Update Goal]  →  updating  →  [API resolves]
                                                       ↓
                                          ┌────────────┴────────────┐
                                          ↓                         ↓
                                    success path              no-data path
                                          ↓                         ↓
                                  setLastApplied(...)       setNoDataMessage(...)
                                  toast.success             toast.info
                                  onGoalUpdated(new vals)   onGoalUpdated(ts only)
```

The `lastApplied` and `noDataMessage` flags reset on goal change (re-opening the drawer for a different goal clears any prior banner). The success banner shows the rationale; the no-data banner renders the verbatim spec copy + a Document Journal link.

## 7. Architectural invariants

- ✅ All LLM traffic via Shield (`shield_invoke`)
- ✅ Single Shield call per Update Goal action (max one — the no-evidence short-circuit avoids it entirely)
- ✅ `context_id` scoping
- ✅ Tenant ID = account ID on Shield invocation
- ✅ No `repr(exc)` leaks
- ✅ No new third-party libraries

## 8. QA-049 sub-bullet coverage

| Sub-bullet | Status | Notes |
|---|---|---|
| RAG colours on progress bars (purple/orange/blue → R/A/G) | DEFERRED | Strategic goal cards already use STATUS_STYLE which derives from rag_status — fine. Drawer surfaces status correctly. The progress-bar colour mapping in `StrategicGoalsPanel.jsx` lines ~250-260 doesn't surface purple/orange/blue today; if PO finds a specific surface still using those colours, route as a Chunk-13 follow-up. |
| % indicator on scores | DONE | Drawer shows "55%" format. Cards already had this. |
| Hover full-text on truncated descriptions | DEFERRED | Tooltip wrap is a small UI polish; deferred to backlog if PO flags. |
| Tabs + badges + category filter | PARTIAL | Achieved tab already shipped in Chunk 11 for objectives/projects (the spec called out the same need for goals). Strategic Goals tabs + counts may need a follow-up if PO flags. |
| By Score sort options (0/55/85/100) | DEFERRED | Sort dropdown polish; backlog. |
| Drawer "Current score" → "Performance Score" | DONE | Hard-asserted in render-smoke step 14. |
| Update Goal flow (the big rewrite) | DONE | Full contract above. |

The dispatch explicitly focused on sub-bullets #6 + #7. Sub-bullets #1, #3, #4, #5 are smaller UI polish items that can be picked up in a Chunk-15+ "Strategic Goals polish" batch if the PO wants them shipped. Captured in this section so they're not lost.

## 9. Follow-ups (queued, not in Chunk 12 scope)

1. **QA-049 sub-bullets #1/#3/#4/#5** — UI polish (RAG progress bars, hover tooltips, score-history filter, sort options). Promote to a Chunk-15 batch if PO wants them.
2. **Strategic Goals tabs + counts (sub-bullet #4)** — mirror the Chunk-11 status_counts pattern for `db.strategic_goals`. Backend already has the data model; needs an endpoint extension + frontend tab strip.
3. **Update Goal undo button** — current implementation appends to score_history on success. A future polish chunk could render an "Undo last Akki update" CTA that restores the previous score from history[-2].
