# Chunk 1 — P0 Solva cross-account leakage (WS-R16)

> 2026-05-13 — **CRITICAL SECURITY** fix shipped + verified green.

---

## 0. Severity

QA tester report:

> *"Solva Contexts from other accounts and companies are available for selection in the Generate Brief from Solva flow. The user was on an account they had not previously used with Solva, yet Solva contexts from other accounts were visible."*

Data-segregation failure. Non-negotiable fix.

---

## 1. Reproduction (BEFORE the fix)

### 1.1 Surface area
* **Frontend entry point**: Generate-Brief-from-Solva picker —
  `/app/frontend/src/components/studio/SourceStep.jsx` `InlinePicker`
  component (rendered inside `ExportModal` when the user picks
  *"From a Solva session"*).
* **API call**: `GET /api/solva/v2/sessions?status=completed`
* **Auth model**: JWT Bearer (axios `api` client). The frontend did
  NOT pass any workspace identifier — neither query param nor
  `X-Active-Context` header.

### 1.2 Probe script

A test user (`bramuel@syni.ai`) was authenticated. The user has
**9 active memberships** across 9 distinct contexts (per
`GET /api/me/contexts`).

Two fresh Solva sessions were seeded directly into Mongo, one in
each of two different contexts owned by the same user:

| ID prefix | `context_id` (truncated) | Intent |
|---|---|---|
| `leakprobe-A-…` | `cef8714a` | "PROBE-A: leak detection (context A only)" |
| `leakprobe-B-…` | `5afb0f40` | "PROBE-B: leak detection (context B only)" |

### 1.3 Observed response (BEFORE fix)

```
$ curl -H "Authorization: Bearer <token>" \
       "$API/solva/v2/sessions?status=completed"

{
  "count": 2,
  "items": [
    {"id": "leakprobe-A-...", "intent": "PROBE-A: leak detection (context A only)", ...},
    {"id": "leakprobe-B-...", "intent": "PROBE-B: leak detection (context B only)", ...}
  ]
}
```

**Both probe sessions returned regardless of which context the user
is currently "in".** This is the leak.

The picker's UX intent is *"sessions from this workspace"* but the
backend was returning *"sessions from any workspace this user belongs
to"*. A user wearing multiple board hats (advisor on Company A and
NED on Company B) sees both workspaces' sessions mixed together.

---

## 2. Root cause (1 line)

`GET /api/solva/v2/sessions` (`/app/backend/routers/solva_v2.py`
line 1383) built its Mongo find filter as `{"account_id": ..., "version": 2}`
**with no `context_id` clause** — every session the user had ever
created in any workspace was returned.

---

## 3. Fix

### 3.1 Backend — `/app/backend/routers/solva_v2.py`

The `list_sessions` handler now requires a `context_id` query
parameter and applies four defense-in-depth checks:

1. `context_id: str` is **required** — FastAPI raises 422 if absent.
2. Caller must hold an **active membership** in that context — 403
   if not.
3. The Mongo filter combines `account_id` + `context_id` — belt-and-braces
   if membership lookup is ever bypassed.
4. Sessions with null/missing `context_id` (orphans — see §6) cannot
   surface under any context filter because Mongo strict-equality
   excludes them.

```python
@router.get("/sessions")
async def list_sessions(
    context_id: str,
    status: Optional[str] = None,
    q: Optional[str] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    membership = await db.memberships.find_one(
        {"context_id": context_id, "account_id": account["id"], "status": "active"},
        {"_id": 0},
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this context")
    qfilter = {"account_id": account["id"], "context_id": context_id, "version": 2}
    ...
```

### 3.2 Frontend — `/app/frontend/src/components/studio/SourceStep.jsx`

`InlinePicker` now accepts `contextId` as a prop and forwards it to
the API call. `SourceStep` already received `contextId` from
`ExportModal` so the thread was a single new prop.

```jsx
const path = sourceType === "solva_session"
  ? { url: "/solva/v2/sessions", params: { status: "completed", context_id: contextId } }
  : { url: "/chats", params: { limit: 25 } };
```

---

## 4. Verification (AFTER the fix)

### 4.1 Curl

```
$ curl -o /dev/null -w "HTTP %{http_code}\n" \
       -H "Authorization: Bearer <token>" \
       "$API/solva/v2/sessions?status=completed"
HTTP 422       # missing context_id → required field error

$ curl -H "Authorization: Bearer <token>" \
       "$API/solva/v2/sessions?status=completed&context_id=cef8714a..."
{"count": 1, "items": [{"id": "leakprobe-A-...", "intent": "PROBE-A: ..."}]}

$ curl -H "Authorization: Bearer <token>" \
       "$API/solva/v2/sessions?status=completed&context_id=5afb0f40..."
{"count": 1, "items": [{"id": "leakprobe-B-...", "intent": "PROBE-B: ..."}]}

$ curl -o /dev/null -w "HTTP %{http_code}\n" \
       -H "Authorization: Bearer <token>" \
       "$API/solva/v2/sessions?status=completed&context_id=00000000-0000-0000-0000-000000000000"
HTTP 403       # caller not a member of that context
```

Each context now returns **exactly one** session — its own. Crossing
the wall is impossible without either an unauthorized membership
(which the 403 blocks) or the param itself (which the 422 blocks).

### 4.2 Backend tests

Added `/app/backend/tests/test_chunk1_solva_leak.py` — 4 tests:

* `test_list_sessions_requires_context_id` — 422 when omitted.
* `test_list_sessions_rejects_non_member_context` — 403 when caller is not a member.
* `test_list_sessions_strictly_scopes_to_context` — **canonical isolation test**. Two contexts, one session each, must surface only the requested context's session.
* `test_list_sessions_excludes_orphan_context_id_rows` — sessions with null `context_id` cannot leak under any filter.

All 4 green.

Updated existing `tests/test_solva_v2_smoke.py`:
* The two tests that previously called `GET /sessions` with no params now seed a fresh context for the test account and pass `context_id` explicitly. Both green.

### 4.3 Full pytest sweep
**406 passed**, 565 skipped (pre-existing quarantines), 0 failed.
(Was 393 going into this chunk — net +13 from chunk-1 tests +
the Patch-30B requirements-guard tests already counted.)

### 4.4 render-smoke
```
PASS — 8 routes clean · 2 upload paths green · Patch 28 interactions green.
```

---

## 5. Step-5 audit — sibling vulnerabilities

Audited adjacent listing endpoints for the same flaw pattern.

| Endpoint | Verdict | Evidence |
|---|---|---|
| `GET /api/chats` | ✅ **SAFE** | Requires `X-Active-Context` header (400 if missing); filters by `account_id` + `context_id`. Hardened in Workstream A.2. |
| `GET /api/contexts/{cid}/cycles` | ✅ **SAFE** | `context_id` is part of the URL → cannot be omitted; `require_context_membership` dependency on the router. |
| `GET /api/contexts/{cid}/briefings/aggregates` | ✅ **SAFE** | Same URL-scoped + membership-checked pattern. |
| `GET /api/contexts/{cid}/monitor` | ✅ **SAFE** | Same pattern. |
| `GET /api/contexts/{cid}/pulse/feed` | ✅ **SAFE** | Same pattern. |
| `GET /api/contexts/{cid}/pulse/across-boards` | ✅ **SAFE** | URL-scoped; the cross-boards pivot is intentional and explicit per item 11 of the Clarifications doc. |
| `GET /api/contexts/{cid}/work-studio/compilations` | ✅ **SAFE** | URL-scoped. |
| `GET /api/contexts/{cid}/work-studio/exports/{eid}` | ✅ **SAFE** | URL-scoped + per-export check. |

### ⚠️ ONE adjacent risk found (defense-in-depth gap, not an active leak)

`GET /api/solva/v2/sessions/{sid}` and several sibling endpoints
(`POST /sessions/{sid}/fork`, `/take-to-cycle`, `/abandon`, `/turn`,
`/attach-document`, `/handoff/cycle`, `/synisense-breakdown`,
`/reasoning-log`, `/artefact-reasoning`, `/export.pdf`, `/export.docx`)
filter only by `id` + `account_id` — **no `context_id` check**.

This is **not the live leak** the QA tester reported (the picker can
no longer surface a foreign-context session id), but it remains a
defense-in-depth gap: if a session UUID is leaked through any channel
(logs, screenshot, share link), a user could fetch a session from a
context they're not currently "in" but happen to belong to.

Per the brief: not fixed in this chunk. Documented as new debt in
SYSTEM_STATE §7 with **Chunk 7 earmarked** for the lockdown sweep
(the lockdown is mechanical — apply the same context-membership
check the list endpoint now does, across ~10 single-session routes).

---

## 6. Data debt — orphan sessions

Local seed database state:

```
solva_v2_sessions total = 541
solva_v2_sessions with null/missing context_id (orphans) = 524
```

**97% of seeded sessions have no `context_id`**. After the fix these
are completely invisible to the picker, which is correct from a
privacy standpoint but means a non-trivial volume of legacy session
data is now dark.

Action: **DO NOT** retroactively assign `context_id` to orphans via
inference — there's no safe way to determine which workspace each
session originally belonged to without the user's input. Three
options for the cleanup chunk:

* **(a)** Surface orphans in an admin tool that lets the original
  account-holder claim each session into a workspace of their choice.
* **(b)** Archive all orphans into a `solva_v2_sessions_archive`
  collection and surface a "lost sessions" link on the user's profile
  page that lets them export the data.
* **(c)** Treat orphans as test-only / pre-Patch-N rows and delete
  them outright on PO sign-off.

Recommend **(b)** as the safest default — no data loss, but they're
out of the live UI until claimed. Will be scoped as a follow-up
chunk after PO weighs in.

---

## 7. Close-out checklist

- ✅ Reproduction transcript captured (§1)
- ✅ Root cause identified (§2)
- ✅ Fix applied — backend (§3.1) + frontend (§3.2)
- ✅ Defense-in-depth tests added — 4 new tests in `test_chunk1_solva_leak.py`
- ✅ Two existing smoke tests updated for the new contract
- ✅ Step-5 sibling audit complete — 1 adjacent gap documented (Chunk 7 earmark)
- ✅ Orphan data debt logged (§6)
- ✅ Full pytest green — 406 passed
- ✅ render-smoke green — 8 routes + 2 uploads + Patch 28 interactions
- ✅ SYSTEM_STATE.md §4 + §7 updated (next file)

---

## 8. Files touched

| File | Change |
|---|---|
| `/app/backend/routers/solva_v2.py` | `list_sessions` now requires & enforces `context_id` + membership |
| `/app/frontend/src/components/studio/SourceStep.jsx` | `InlinePicker` accepts `contextId` prop; threads to `/solva/v2/sessions` query |
| `/app/backend/tests/test_chunk1_solva_leak.py` | new — 4 regression tests |
| `/app/backend/tests/test_solva_v2_smoke.py` | updated — seeds context + passes `context_id`; +1 helper |

— end of Chunk 1 close-out —
