# Chunk 2 — Backend timeout/gateway failures (DJ-R03, DJ-R05, CM-R04)

> 2026-05-13 — three P0 timeouts converted to async + polling.

---

## 0. Targets

| Code | Endpoint | QA-reported error |
|---|---|---|
| **DJ-R03** | `POST /api/contexts/{cid}/briefings` (Generate Brief) | HTTP 524 — Cloudflare-class upstream timeout |
| **DJ-R05** | `POST /api/contexts/{cid}/signals/generate` (Generate Signals) | HTTP 524 |
| **CM-R04** | `POST /api/contexts/{cid}/cycle/draft-compilation` (Produce Draft Compilation) | HTTP 502 |

All three were inline-LLM-on-the-request-thread synchronous endpoints. The gateway has a ~100 s timeout; LLM calls + persistence + render routinely take 30–120 s.

---

## 1. Per-endpoint diagnosis

### 1.1 DJ-R05 — `POST /contexts/{cid}/signals/generate`

* **Router**: `/app/backend/routers/signals_ask.py` line 92 (`generate_signals`)
* **Heavy path**: gathers Context Object + grounding docs → builds prompt → `await llm_call_llm(...)` (single Sonnet/Gemini call) → parses → per-signal deduplication + persistence
* **Curl reproduction (pre-fix)**:
  ```
  $ time curl -s -X POST "…/contexts/<cid>/signals/generate" -d '{}' …
  HTTP 200
  real  1m17s    # already at threshold for the local pod; production gateway 524s
  ```
* **77 s on local + small fixture**. Production with full grounding and slower LLM provider response = certain to exceed 100 s gateway ceiling.

### 1.2 DJ-R03 — `POST /contexts/{cid}/briefings`

* **Router**: `/app/backend/routers/briefings.py` line 51 (`create_briefing`)
* **Heavy path**: gathers grounding signals + docs → constructs briefing prompt → `await llm_call_llm(...)` (large prompt, big completion) → assembles boardpack object → audit write
* **Curl reproduction (pre-fix)**: indeterminate — gateway returns 524 before the worker finishes. Pod-side logs confirm the LLM call regularly runs 45–90 s.

### 1.3 CM-R04 — `POST /contexts/{cid}/cycle/draft-compilation`

* **Router**: `/app/backend/routers/cycle_manager.py` line 842 (`draft_compilation`)
* **Heavy path**: gathers cycle agenda + contributions + readiness + prior cycles → **two-pass LLM**: drafter (Sonnet 4.5) emits envelope, validator (Gemini 2.5 Flash) scores drift → persists Work Studio Brief → renders DOCX → writes audit row
* **Why 502 not 524**: two sequential LLM calls + the DOCX render put this endpoint at the heavy end. The pod-side worker frequently exceeded the gateway timeout AND the gateway also short-circuited the chain (502 instead of letting it run to 524).

---

## 2. Fix pattern

**Reused existing infrastructure**: the codebase already had the BG-task + status-row pattern in `routers/work_studio_export.py` (its `db.work_studio_exports` collection follows `running → completed | failed`). We mirrored that shape into a small shared helper rather than reinventing it.

**Built one new shared helper** (~150 LoC):
* `/app/backend/services/job_queue.py` — `db.async_jobs` collection with `create_job`, `mark_running`, `mark_completed`, `mark_failed`, `get_job`, `is_terminal`. Idempotent at the row level.
* Also exposes `spawn(coro)` — a thin wrapper around `asyncio.create_task` that holds a strong reference to the task in a module-level set so it isn't GC'd before completion.
* `/app/backend/routers/async_jobs.py` — single polling endpoint `GET /api/jobs/{job_id}`. Scoped per-`account_id`; 404 (not 403) for foreign jobs so existence is not leaked.

**Why `asyncio.create_task` rather than FastAPI `BackgroundTasks`**:
* `BackgroundTasks` is awaited inside Starlette's `TestClient` / `ASGITransport` — the 202 dispatch finishes only after the worker finishes, defeating the test pattern.
* In production with uvicorn, `BackgroundTasks` waits for the response cycle to finish before running, so the gateway connection is held open marginally longer than it needs to be.
* `asyncio.create_task` returns immediately at the event-loop level. The 202 leaves the worker in the kernel before the gateway sees the response. Identical behaviour in prod and tests.

### Refactored endpoints

For each of the three endpoints:

1. Renamed the legacy heavy function to `_<endpoint>_worker(...)` (private; takes scalar args, no `ctx` / `Depends` injection).
2. The public route handler now:
   * Runs **pre-flight checks synchronously** (cheap count queries — the "no documents" / "no signals" / "no contributions" 400s surface instantly).
   * Calls `_create_job(...)` to insert the `queued` row.
   * `_spawn(_runner())` schedules the worker. The runner marks `running`, awaits the worker, then marks `completed` (with the worker's return value as `result`) or `failed` (with a sanitised error string).
   * Returns `202` + `{"job_id": ..., "status": "queued"}`.
3. The endpoint's status code is now `202` (was `200`). `result` schema preserved — the polling endpoint's `result` field carries the legacy response shape so the frontend's downstream logic (toast, list refresh) keeps working unchanged.

### Frontend

* **New shared helper** `/app/frontend/src/lib/pollJob.js` — `pollJob(jobId, { onProgress, cancelled })`. Polls `/api/jobs/{id}` every 1.5 s for the first 30 s, then exponential backoff up to 5 s, with a 6-minute hard ceiling. Handles transient network errors (3 strikes = caller surface).
* **Three call sites updated**:
  * `pages/ReadingView.jsx` — Generate Brief button + Refresh Signals chip.
  * `pages/Prepare.jsx` — Signals tab inline generate form.
  * `pages/Cycle.jsx` — `CompilationStep`'s "Produce draft compilation" button (also added a live "Compiling… {n}s" progress line per the brief).
* All three surfaces let the user keep working / navigate away while the job runs server-side. On `failed`, the existing toast plumbing surfaces the error string from the job row.

---

## 3. Tests

`/app/backend/tests/test_chunk2_async_jobs.py` — **6 new tests**:

1. `test_signals_generate_returns_202_and_job_id_fast` — mocks `_generate_signals_worker` to `await asyncio.sleep(120)`. Asserts the endpoint still returns in < 5 s. **This is the canonical "no more 524" guarantee** — if anyone re-introduces synchronous-inline LLM work to this endpoint, this test fails.
2. `test_job_polling_happy_path` — POST → poll until terminal → `completed` with `result.mode == "stub"`.
3. `test_job_polling_unknown_job_returns_404` — unknown job_id → 404.
4. `test_job_polling_foreign_job_returns_404` — User B cannot poll User A's job. 404 (not 403) so existence is not leaked.
5. `test_worker_exception_yields_failed_status` — worker raises `RuntimeError("LLM provider returned 503")` → terminal `failed` + the error string captured.
6. `test_cancellation_not_implemented_but_status_polls_safely` — cancellation deferred to a future chunk; this test proves rapid-polling during a long-running job doesn't corrupt the row.

**Test counts**:
* Was 406 entering the chunk.
* **412 passed** after the chunk. 0 failed. 565 skipped (pre-existing quarantines unchanged).

---

## 4. Verification

### Curl after the fix

```
$ time curl -X POST .../signals/generate -d '{}'
HTTP 202   {"job_id": "...", "status": "queued"}
real  0m0.04s     # dispatch is now instant

$ curl .../jobs/<id>   # poll
{"status": "running", ...}
... (waits ~33 s)
{"status": "completed", "result": {"signals": [...], "mode": "live"}, ...}
```

```
$ time curl -X POST .../briefings -d '{"title":"probe"}'
HTTP 202   {"job_id": "...", "status": "queued"}
real  0m0.015s
... poll for ~27 s → status=completed
```

```
$ time curl -X POST .../cycle/draft-compilation -d '{}'
HTTP 400  {"detail": {"code": "no_contributions", ...}}   # pre-flight, instant
real  0m0.05s
```

### Render-smoke

```
PASS — 8 routes clean · 2 upload paths green · Patch 28 interactions green.
```

### Pytest

```
412 passed, 565 skipped, 45 warnings — 102 s.
```

The 524/502 errors are now **structurally impossible** on these three routes — the synchronous code path is gone.

---

## 5. Step-7 audit — other slow synchronous endpoints

| Endpoint | Verdict | Note |
|---|---|---|
| `POST /contexts/{cid}/work-studio/enhance/{kind}/stream` | ✅ **SAFE** | Already SSE-streamed via `streaming_v9.py`. The connection stays warm and the gateway sees a streaming body. No 524 class. |
| `POST /contexts/{cid}/work-studio/exports/{eid}/compile` (Compile Wizard commission) | ✅ **SAFE** | `routers/work_studio_export.py` already uses the BackgroundTasks + `db.work_studio_exports` row pattern. The frontend already polls this surface. |
| Solva session turn | ✅ **SAFE** | Already SSE-streamed via `solva_v2.py`. |
| `POST /contexts/{cid}/documents` (Upload + Processing) | ✅ **SAFE** | The P0 upload fix (Patch 23) moved heavy text extraction to a BG task. Upload returns immediately; extraction status surfaces via the document row. |
| `POST /contexts/{cid}/documents/generate-meta` | ⚠ **P1 RISK** | LLM-backed metadata generation. Synchronous today. Smaller prompt than briefings but still > 10 s on heavy docs. **Earmark Chunk N** (after the 12-chunk QA fix sprint completes — this isn't in the QA report yet). |
| `POST /contexts/{cid}/documents/{doc_id}/summary` | ⚠ **P1 RISK** | LLM-backed full-text summary. Synchronous. Long docs > 30 s. Same earmark. |
| `POST /contexts/{cid}/documents/{doc_id}/journal-commentary` | ⚠ **P1 RISK** | LLM-backed Akki's Commentary for a single document. Synchronous. Same earmark. |
| `POST /contexts/{cid}/documents/{doc_id}/evolution-diff` | ⚠ **P1 RISK** | LLM-backed cross-revision diff. Synchronous. Same earmark. |

**Not fixed in this chunk** — earmarked in SYSTEM_STATE §7 as "Document-detail LLM endpoints — same 524 risk class as Chunk 2". When PO requests the next round of resilience work, a single follow-up chunk converts all 4 to the same async pattern with minimal incremental cost (the helper is already there; refactor is mechanical).

---

## 6. Files touched

### Backend
* `/app/backend/services/job_queue.py` — **new** — shared async-job helper + `spawn` task tracker.
* `/app/backend/routers/async_jobs.py` — **new** — `GET /api/jobs/{job_id}` polling endpoint.
* `/app/backend/server.py` — registered `async_jobs.router`.
* `/app/backend/routers/signals_ask.py` — `generate_signals` rewritten to async pattern; `_generate_signals_worker` extracted.
* `/app/backend/routers/briefings.py` — `create_briefing` rewritten; `_create_briefing_worker` extracted.
* `/app/backend/routers/cycle_manager.py` — `draft_compilation` rewritten; `_draft_compilation_worker` extracted.
* `/app/backend/tests/test_chunk2_async_jobs.py` — **new** — 6 regression tests.

### Frontend
* `/app/frontend/src/lib/pollJob.js` — **new** — shared polling helper.
* `/app/frontend/src/pages/ReadingView.jsx` — Generate Brief + Refresh Signals call sites updated.
* `/app/frontend/src/pages/Prepare.jsx` — signals-tab generate call site updated.
* `/app/frontend/src/pages/Cycle.jsx` — `CompilationStep` updated + live "Compiling… {n}s" progress line.

---

## 7. PO clarifications surfaced

None new. The chunk's defaults all match existing UX (toast + navigate-on-success, retry CTA on failure, navigate-away-safely). Cancellation is deferred — adding it would require Mongo CAS on every LLM-call boundary which is heavier than the QA bar requires. If the PO later wants explicit cancel UI, scope it as its own chunk with a `cancel_requested` row flag and worker check-ins.

— end of Chunk 2 close-out —
