# Chunk 3 — Enhance worker_crash diagnosis (WS-R06, WS-R12, WS-R15)

> 2026-05-13 — three "worker_crash" reports turned out to be one
> structural reporting bug + one real schema gap. Both fixed.

---

## 0. The headline you'll want first

"worker_crash" was never a real exception class. It was a **literal
string** that the export-runner's catch-all wrote into the row's
`error` field, eating whatever actually went wrong. Three QA reports
called it three different bugs (Enhance Minutes / Deck / Report all
crashed with "worker_crash"). They were the same symptom on top of
**different** root causes, ALL invisible to the user.

After improving the error reporting first (one-line catch-all rewrite),
the real failures became readable:

* **Enhance Minutes** — `KeyError: 'minutes'` at
  `routers/work_studio_export.py::_two_pass_schema_doc`. `minutes` was
  not registered as a valid enhance kind, neither in the entry-point
  allow-list NOR in the two-pass schema dispatch.
* **Enhance Report / Deck** — `TypeError: sequence item N: expected str
  instance, dict found` inside `services/work_studio_export.py::scrape_content_text`.
  The LLM occasionally returns the `recommendations` field as a list
  of dicts (e.g. `{"owner": "Alice", "action": "Draft Q3"}`) but the
  scraper assumed strings. The crash hit Minutes and Report (the
  shared renderer); Deck was less common but the same code path.

Once both root causes are fixed, all three Enhance variants reach
terminal `complete` status with no errors. Verified via live curl
against `bramuel@syni.ai` / `dcc263b1-…`.

---

## 1. Per-variant diagnosis

### 1.1 WS-R06 — Enhance Minutes

**Reproduction** (pre-fix):
```
POST /api/contexts/{cid}/work-studio/enhance/minutes
  -F instructions=…  -F output_format=docx  -F file=@probe.pdf
→ HTTP 400  {"detail": "Unknown enhance kind. Allowed: deck, report."}
```
The endpoint rejected `minutes` outright. The frontend's error path
then surfaced it generically as "worker_crash" because the toast
plumbing didn't distinguish a 400 from a worker failure (Adjust-and-Retry
button appeared all the same).

But that's only HALF of WS-R06. The QA report also flagged: *"clicking
Adjust and Retry loses the previously attached document."* Looking at
`/app/frontend/src/components/studio/EnhanceModal.jsx` the `file` is
held in React state (preserved across phase transitions) — but the
`<input type="file" required>` HTML element has two browser-level
quirks:

1. It can't be programmatically re-populated (security).
2. The `required` attribute blocks form submission if the input
   element is empty — even though `file` (React state) holds the File
   object.

So the user clicked "Adjust and retry" → re-rendered "compose" → the
input visually said "No file chosen" → submit was blocked by browser
"please choose a file" → user concluded "the document was lost".

**Fix applied (backend)** — `_ENHANCE_KINDS` extended to include
`minutes`. Accepted-extensions added (`.docx`, `.pdf`, `.txt`).
Two-pass schema-dispatch keyword `"minutes"` added (same shape as
Report — narrative artefact, identical key set). Renderer dispatch
extended to route `kind="minutes" + format="docx"` and `+format="pdf"`
through the existing Report renderers.

**Fix applied (frontend)** — `EnhanceModal.jsx`:
* Drop the HTML `required` attribute (the JS `if (!file)` check at
  submit time is the real source of truth and was always there).
* Add a clear "Using: <filename> · <size> KB · clear" affordance that
  shows when `file` is in state regardless of what the `<input>` reads,
  so the user can see "the document IS still attached" at a glance.
* Map the user-visible label "Enhance Minutes" to `kind="minutes"`
  (was `kind="report"` — silently misfiled the artefact).

### 1.2 WS-R12 — Enhance Deck

**Pre-fix traceback** (captured by the improved error reporting, would
have been invisible before Chunk 3):
```
TypeError: sequence item 9: expected str instance, dict found
File "/app/backend/services/work_studio_export.py", line 848,
  in scrape_content_text
    return "\n".join(p for p in parts if p)
```
Same root cause as 1.3 — the `scrape_content_text` helper assumes
`recommendations` is `List[str]` but the LLM returned a list with a
dict at position 9 (e.g. `{"owner": "...", "action": "..."}`).
Crashes the join.

### 1.3 WS-R15 — Enhance Report

Same traceback as 1.2 — same fix.

---

## 2. Shared root cause synthesis

Two distinct bugs were all hiding behind ONE meta-bug:

* **Meta-bug**: the export-runner's catch-all wrote the literal
  string `"worker_crash"` to the row's `error` field. The real
  exception was logged via `logger.exception(...)` but never
  persisted, never sent to the frontend. Two identical-looking
  "worker_crash" rows in QA's report were actually two different
  underlying exceptions.

* **Bug A** (`minutes` not registered) — affected WS-R06 only.

* **Bug B** (`scrape_content_text` crashes on dict recommendations)
  — affected WS-R12, WS-R15, AND WS-R06 (now that `minutes` is
  registered and reaches the renderer).

* **Frontend retry sub-bug** (`required` HTML attribute blocks
  resubmission when input is empty but `file` state isn't) —
  affected WS-R06's QA narrative directly.

---

## 3. Fixes applied

### Backend

| File | Change |
|---|---|
| `routers/work_studio_export.py` line 127 | `_ENHANCE_KINDS = ("deck", "report", "minutes")` (added Minutes) |
| `routers/work_studio_export.py` line 134 | Accepted-extensions table extended for `minutes` |
| `routers/work_studio_export.py` line 138 | `_AUTO_FORMAT` + `_VALID_KINDS` extended for `minutes` |
| `routers/work_studio_export.py` `_two_pass_schema_doc` | Schema entry added for `kind="minutes"` (tighter than Report — minutes have many short sections, recommendations renamed to "actions" semantically while keeping the JSON key as `recommendations` for renderer compatibility) |
| `routers/work_studio_export.py` `_render_kind` dispatch | Routes `(kind="minutes", format="docx")` and `(…"pdf")` to the existing `render_report_docx`/`render_report_pdf` |
| `routers/work_studio_export.py` enhance-runner catch-all (~line 1655) | Replaces literal `"worker_crash"` with `f"{type(exc).__name__}: {str(exc)[:300]}"`. `logger.exception` retained for ops |
| `routers/work_studio_export.py` export-runner catch-all (~line 1335) | Same fix |
| `routers/work_studio_export.py` LLM-stage catch (~line 1091) | `llm_error:KeyError` → `llm_error:KeyError: 'minutes'` (carry message) |
| `routers/work_studio_export.py` LLM-stage catch (~line 617) | Same |
| `services/work_studio_export.py::normalize_content_for_render` | `kind in ("report","minutes")` branch normalises recommendations; coerces dict-shaped LLM outputs (`{owner,action,when}`, `{heading,body}`, etc.) into clean strings instead of dropping them |
| `services/work_studio_export.py::scrape_content_text` | Defensive coercion — dict items in `recommendations` are flattened to readable strings; ints / Nones tolerated |

### Frontend

| File | Change |
|---|---|
| `components/studio/EnhanceModal.jsx` | `ACCEPT_BY_KIND` + `KIND_LABEL` extended for `minutes` |
| `components/studio/EnhanceModal.jsx` | Drop `required` attribute on `<input type="file">`; rely on JS-side `if (!file)` check |
| `components/studio/EnhanceModal.jsx` | New "Using: <filename> · <size> · clear" affordance — visible while `file` is in React state (proves the attached document survives Adjust-and-Retry) |
| `pages/WorkStudio.jsx` | Quick-action "Enhance Minutes" calls `onEnhance("minutes")` (was `onEnhance("report")` — silently misfiled the resulting artefact) |

---

## 4. Tests

`/app/backend/tests/test_chunk3_enhance_worker.py` — **7 new tests**:

1. `test_minutes_is_a_registered_enhance_kind` — locks `minutes` into `_ENHANCE_KINDS` + accepted-extensions map. Any future "let's remove minutes" change fails this.
2. `test_enhance_runner_writes_structured_error_not_worker_crash[minutes-docx]` — parametrised over three (kind, format) variants. Mocks `_run_enhance` to raise `ValueError("Synthetic chunk-3 explosion: …")` and asserts the row's `error` field is `ValueError: Synthetic chunk-3 explosion: …` and **specifically not** the literal `"worker_crash"`. This is the canonical "no more opaque errors" guarantee.
3. `[report-docx]` — same.
4. `[deck-pptx]` — same.
5. `test_scrape_content_text_handles_dict_recommendations` — direct unit test of the scraper. Feeds it a mixed list (`str`, `{owner,action,when}`, `{heading,body}`, `{text}`, `int`, `None`) and asserts no crash + the readable values surface in the output.
6. `test_enhance_can_be_resubmitted_after_a_failed_attempt` — proves the server accepts a second submission of the same file (Adjust-and-Retry happy path).
7. `test_unknown_enhance_kind_returns_400_not_worker_crash` — defence-in-depth.

**Test counts**:
* Was 412 entering chunk.
* **419 passed** after chunk. 0 failed. 565 skipped (unchanged).

---

## 5. Verification

### Curl reproduction (after fixes)

```
POST /api/contexts/<cid>/work-studio/enhance/minutes
  …same shape as before…
→ HTTP 200  {"export_id": "5b9237c1-…", "status": "running"}

(poll the export row)
 1: running
 2: running
 …
12: complete  | error: null  | byte_len: <set>
```

```
POST /api/contexts/<cid>/work-studio/enhance/report
 16 polls → complete, no error
POST /api/contexts/<cid>/work-studio/enhance/deck
 14 polls → complete, no error
```

### render-smoke

```
PASS — 8 routes clean · 2 upload paths green · Patch 28 interactions green.
```

### Pytest

```
419 passed, 565 skipped, 44 warnings — 124 s.
```

---

## 6. Step-5 audit — sibling SSE error pathways

| Endpoint | Verdict | Note |
|---|---|---|
| `streaming_v9.py` work-studio enhance stream (line 108, 155) | ⚠ soft-debt | Wraps unknown exceptions with `repr(exc)`. Not opaque (carries class + args) but raw Python repr leaks to the frontend. Surfaces ARE actionable (the user sees `ValueError('foo')`) so this isn't blocking the QA bar. Earmark for a polish chunk. |
| `solva_v2.py` turn endpoint error handlers (line 1950, 2970, 3004) | ⚠ soft-debt | Same pattern — `repr(exc)` reaches the SSE stream. Has the same "not blocking but worth polishing" verdict. Earmark. |
| `work_studio_export.py` enhance-runner | ✅ FIXED — typed error, no `worker_crash` literal. |
| `work_studio_export.py` export-runner | ✅ FIXED — same. |
| `work_studio_export.py` LLM-stage catch | ✅ FIXED — `llm_error:{Class}: {msg}` carries the actionable info. |
| Cycle Manager streaming (via Chunk 2 `_runner` wrapper) | ✅ FIXED — Chunk 2 made the worker exception flow through `mark_failed` with typed message. |

**No other `worker_crash` literals remain in the codebase**. The two `repr(exc)` soft-debts above don't share the same opaque-token failure mode and don't block production.

---

## 7. Files touched

### Backend
* `/app/backend/routers/work_studio_export.py` — kind allow-list + extensions + two-pass schema + renderer dispatch + two catch-all rewrites + two LLM-stage catch rewrites
* `/app/backend/services/work_studio_export.py` — `normalize_content_for_render` recommendation coercion + `scrape_content_text` recommendation coercion
* `/app/backend/tests/test_chunk3_enhance_worker.py` — **new** — 7 regression tests

### Frontend
* `/app/frontend/src/components/studio/EnhanceModal.jsx` — kind table + file-input `required` removed + "Using: …" affordance
* `/app/frontend/src/pages/WorkStudio.jsx` — Quick-action wiring

---

## 8. PO clarifications surfaced

**None new** — the fixes are all "make the broken thing work" rather than product decisions. One minor naming question implicitly answered by Chunk 3:

* "Enhance Minutes" now writes a `minutes`-kind artefact (was silently `report`). When the QA tester next opens Work Studio they'll see Minutes filed under Minutes, not Reports. If PO wants a different default category (e.g. "always file enhance-of-minutes under Reports for cohesion"), single-line revert: change the WorkStudio.jsx line back to `onEnhance("report")`.

— end of Chunk 3 close-out —
