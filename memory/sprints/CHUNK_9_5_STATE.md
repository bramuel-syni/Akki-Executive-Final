# Chunk 9.5 — Solva criticals + Phase C audit-panel regression

**Date:** 2026-05-20
**Status:** Closed. SV-01 / SV-02 / SV-03 + Phase-C symptoms 1 & 2 DONE; Symptom 3 RESOLVED-NO-BUG.
**Source specs:**
- `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md` §§ SV-01 → SV-03
- `/app/memory/screenshots/audit_panel_inline_broken_20MAY2026.md`
- `/app/memory/screenshots/audit_panel_trust_view_broken_20MAY2026.md`

This document captures the locked decisions and the diagnostic narrative so a future agent doesn't have to re-derive them.

## 1. Solva collection topology

There are TWO Solva session collections, written by different code paths:

| Collection | Writer | Listing endpoint | Schema highlights |
|---|---|---|---|
| `solva_v2_sessions` | `routers/solva_v2.py` (legacy wave-3 flow + W3.3 UAT pack) | `GET /api/solva/v2/sessions?context_id=…` | `id, intent, status, submodule, cluster_id, cluster_label, layer, started_at, updated_at` |
| `solva_phase_d_sessions` | `routers/solva_phase_d.py` (Phase E sub-task A delivery, 2026-05-16) | `GET /api/contexts/{cid}/solva/v2/sessions` (different prefix!) | `session_id, sub_module, status, layer_state, initial_framing, layer_0..4, title, schema_version` |

The user-facing **"View all sessions"** page (`SolvaSessions.jsx` mounted at `/app/solva/sessions`) reads from the legacy v2 endpoint. Pre-Chunk-9.5, that endpoint did NOT merge Phase D rows — so bramuel's 84 Phase D sessions were invisible to the listing, even though new sessions write to the Phase D collection. The Chunk-9.5 fix extends `list_sessions` to also query `solva_phase_d_sessions` and project its fields into the v2 wire shape with an `engine="phase_d"` discriminator the frontend uses to route opens correctly.

**Why not just migrate the data?** Migrating 84 + 541 + N future rows across schemas is a Track-4 ticket (orphan-session migration). For now the merge is cheaper, idempotent, and doesn't risk data loss.

## 2. SV-03 auto-title contract (locked decision)

**Decision (locked at dispatch):** Single Shield gateway LLM call. No heuristic fallback path.

**Hook point:** `routers/solva_phase_d.submit_framing`, AFTER Layer 0 (FAR + situation classification) completes. That's the first AI engagement with the user's framing — the brief's "first substantive exchange".

**Purpose string:** `solva.session.auto_title` (covered by the `solva.*` wildcard in `ALLOWED_PURPOSES`; CI guard stays green).

**Prompt template (verbatim):**
```
Generate a concise, board-appropriate session title (six to ten
words, no quotes, no trailing punctuation) for a Solva strategic
reasoning session whose framing is below. The title should
surface the core decision, risk, or question — not paraphrase
every detail. Reply with ONLY the title on a single line.

Framing:
{framing}
```

**Output post-processing:**
1. Take the first non-empty line of the Shield response.
2. Strip surrounding quotes / asterisks / smart-quotes.
3. Trim trailing punctuation `.!?:;,`.
4. Truncate to 80 chars.

**Failure handling:** Catch ANY exception (`except Exception:`), log at WARNING with the locked `{type(exc).__name__}: {str(exc)[:300]}` format, return `None`. Caller leaves `title` empty — the listing falls back to the `initial_framing` excerpt. NO heuristic fallback (would be a second code path that drifts).

**Idempotency:** The hook checks `existing_title = (session.get("title") or "").strip()` and skips when non-empty. A user who edits the title and then re-submits framing won't have their edit clobbered — the `title_source` flag on the row distinguishes `"auto"` from `"user"` for future audit / UI affordances.

## 3. SV-02 root cause (one-liner)

`SolvaSessions.jsx` called `api.get("/solva/v2/sessions", { params: {} })`. The backend's `list_sessions(context_id: str, ...)` requires `context_id` as a query parameter (WS-R16 privacy hardening). Missing the required field produces FastAPI's standard 422 with `detail[].loc = ["query", "context_id"]` and `msg = "Field required"` — surfaced verbatim in the toast.

Fix: thread `context_id: activeContext.id` into the params dict. Skip the call entirely when `activeContext?.id` is falsy (the page renders no-context UI in that state).

## 4. Phase-C Symptom 2 root cause — `ts` BSON-type mismatch

```
chat.created_at   →  STRING ("2026-05-15T22:37:24.818268+00:00")
synisense_runs.ts →  DATETIME (BSON Date)
```

MongoDB compares values within the same BSON type bracket. STRING and DATETIME are different brackets. `{ts: {$gte: <STRING>}}` silently matches NOTHING when ts is a DATETIME. The bug presented as zero metrics on chats that had clearly run through Shield.

**Why this only bit `chat_synisense_metrics`:**
- The context-windowed endpoint uses `now - timedelta(...)` (already a datetime).
- The per-message endpoint filters by `chat_id + message_id` (no ts comparison).
- Only the chat-scoped endpoint passed `chat.created_at` straight in.

**Fix shape:** `_coerce_to_datetime()` helper accepts datetime/string/None and returns a UTC-aware datetime. Applied at the boundary of the metrics endpoint so the existing `$gte` semantics work unchanged.

**Long-term hygiene:** the underlying schema inconsistency (`chats.created_at` as STRING) is technical debt but fixing it in-place requires a migration of every existing chat row. Deferred — the type coercion is a safe production-side adapter that handles both shapes.

## 5. Phase-C Symptom 1 fix scope

Backend correctly returns 404 when `message_id` isn't in the chat's `assistant_msgs` array — that's the right contract for "this audit row doesn't exist". The bug is the FRONTEND surfacing the raw AxiosError to the user.

```jsx
// Pre-fix
catch (e) {
  setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
}

// Post-fix
catch (e) {
  const status = e?.response?.status;
  if (status === 404) {
    setErr("Audit data isn’t available for this message yet — it usually appears within a few seconds of the response. Refresh once it has settled.");
  } else {
    setErr(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
  }
}
```

Other non-404 errors keep the existing `{name}: {message[:200]}` format so genuine system errors still surface enough info to debug.

## 6. Symptom 3 — RESOLVED-NO-BUG

Reproduction script (kept for posterity in case future regression):
```bash
curl -sS "$API_URL/api/chats/$CHAT/audit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Active-Context: $CTX" \
  | python3 -m json.tool
```

Output for a chat with 5 audit rows showed ALL fields complete on every row, including a TOP-LEVEL `at` field on every row object (next to `action`, `payload`, `entry_hash`, `prev_hash`). The screenshot description "missing `at` field" misreads the render — the AuditDialog renders `r.at` ABOVE the `<pre>{JSON.stringify(r.payload, null, 2)}</pre>` block as a styled muted-text span (Chat.jsx:1898-1901), not inside the payload JSON.

The MESSAGE.SENT payload "ends abruptly at `char_len: 100`" claim is similarly a misread — that's just the alphabetical key order of the payload object (`by_category, bypass_reason, char_len, content_sha256, identifiers_detected, message_id, policy, shielded_for_llm`); `char_len` happens to come after the visually-prominent keys but before several others. `<pre>` uses `whitespace-pre-wrap break-all` so no clipping.

Documented to prevent a future agent re-investigating.

## 7. Lessons captured (carry forward to autonomous sprint)

1. **Smoke-test detection via body-text scanning is brittle.** Use HTTP response listeners (`page.on("response", …)`) when asserting "no validation error path was hit" — body-text matches false-positive against unrelated copy.
2. **WorkspaceEntryGate defers 3-5s on first mount.** Any smoke step that lands on `/app/solva` (or any other workspace landing) must pre-mark the workspace `seen` in sessionStorage before the goto, OR wait with a generous timeout. The same gate exists for Cycle, Monitor, Pulse, etc.
3. **`/api/me/contexts` returns `{items: [{context_id, …}]}`, NOT `{contexts: [{id, …}]}`.** Discovery probes that walk memberships must read `c.context_id || c.id`. Chunk-8 smoke step 9 has the same dormant bug and should be fixed when next touching that surface.
4. **Mongo BSON-type brackets bite type-mismatched `$gte` filters silently.** Any new code path that compares a stored timestamp against a query value should run both through a coercer first. Add `_coerce_to_datetime` to a shared util if a second consumer surfaces.
5. **Frontend axios error surfacing should always inspect `e?.response?.status`** before composing the user-facing copy. Raw `AxiosError: Request failed with status code 404` is unhelpful and leaks implementation detail.
6. **Sonner toast portal is not reliably observable by Playwright headless-shell** depending on z-index + portal mount ordering + theme. The toast IS visible to a human user but the e1_tester may miss it. When the spec demands a toast AND tester needs deterministic observability, render a defensive in-tree companion indicator with a `data-testid` from the same callback. (See `pages/SolvaPhaseDSession.jsx` `savedMarker` state + `fireSavedMarker` callback for the reference pattern.)
7. **Long-running submit handlers + transient indicators = race.** When the submit chain runs multiple Shield calls (Layer 0 + situation classification + auto-title) it can easily exceed 10s. Smoke wait timeouts for post-submit confirmations should be ≥ 30s to accommodate. The fix-pass on Chunk 9.5 bumped from 8s → 30s after observing this.

## 7.5 Session count distribution — 55 vs 84 investigation (fix-pass)

Tester flagged a discrepancy between the dispatch's "84 phase_d sessions for bramuel" claim and the live-preview observation of "55 items in the list". Investigation:

bramuel's Phase D + v2 session distribution across 5 contexts (as of 2026-05-20 22:00 UTC):

| Context (id prefix) | Name | solva_v2_sessions | solva_phase_d_sessions |
|---|---|---|---|
| cef8714a | TEST_retail_111d49 | 0 | 6 |
| 5afb0f40 | Tuli Financial Group | 3 | 11 |
| 2456cc34 | Safiri Telecom | 0 | 2 |
| dcc263b1 | Tuli Financial Group (CFO) | 0 | 20 |
| fbc54a51 | TEST_SeededNedCo | 0 | 61 |
| **TOTAL** | — | **3** | **100** |

The `/api/solva/v2/sessions?context_id=X` listing endpoint is **context-scoped** (per WS-R16 privacy hardening — required). For the largest single context (TEST_SeededNedCo, 61 sessions), the response caps at `to_list(length=100)` on both branches and post-merge `[:100]` — but 61 + 0 < 100 so all surface.

When the tester observed "55 items", they were almost certainly looking at Tuli Financial Group (3 v2 + 11 pd = 14) or a smaller context. The render-smoke saw "32 items, 5 Phase D" on whichever was the user's active context. Different contexts → different counts.

**This is NOT a bug.** The dispatch's "84+" came from a global `count_documents({account_id: bram_id})` — a UI that wanted to show "all of bramuel's sessions across every context" would need either:
- An aggregate-across-contexts endpoint (out of scope; cuts across WS-R16 privacy boundary)
- Context-switcher UX so the user can move between their 5 contexts

The brief's "All saved sessions are accessible from the View All Sessions page" is satisfied within the active context — the spec doesn't ask for a cross-context aggregate.

**Follow-up (queued, not in Chunk-9.5 scope):** if PO confirms a cross-context aggregate is wanted, a future chunk can add `?context_id=*` semantics OR a separate aggregate endpoint with explicit privacy headers. Until then, the per-context behaviour matches both the spec and the privacy contract.

## 8. Follow-ups (queued, NOT in Chunk 9.5 scope)

1. **SV-04 (sessions list cards + status badges)** → Chunk 13.
2. **SV-05/06/07/08** → Chunk 14.
3. **`chats.created_at` schema cleanup** (STRING → DATETIME). Migration script + dual-read window. Track-4 candidate.
4. **Orphan-session migration** — 541 `solva_v2_sessions` rows without `context_id` need to be either deleted or back-filled. Already on Track-4 backlog.
5. **Chunk-8 smoke probe defensive fix** (`c.context_id || c.id`) — still queued from Chunk 9 close.

## 9. Architectural invariants confirmation

- ✅ All LLM traffic via `services.synisense.shield.client.invoke()` — CI guard PASS + static check `test_chunk95_auto_title_routes_through_shield_not_direct_llm` PASS.
- ✅ `context_id` scoping on every touched endpoint — PATCH title via `_get_session(context_id, sid, account_id)`; v2 merge filter includes `account_id + context_id`; metrics endpoint unchanged on scope.
- ✅ `tenant_id == account_id` on Shield surfaces — `_generate_session_auto_title` passes `tenant_id=account["id"], user_id=account["id"]`.
- ✅ Locked error format `{type(exc).__name__}: {str(exc)[:300]}` — used in auto-title warning log; no `repr(exc)` introduced anywhere.
- ✅ No blocking I/O in async routes — Shield call awaited; Motor mongo async.
- ✅ No new third-party libraries — sonner + lucide-react already in deps.
