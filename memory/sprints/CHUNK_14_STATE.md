# Chunk 14 — Solva SV-05 / SV-06 / SV-07 / SV-08 (final Solva chunk)

**Date:** 2026-05-21 (autonomous overnight)
**Status:** Closed. SV-05/06/07/08 all DONE — full Solva QA Brief now closed.
**Source spec:** `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md` § SV-05 through SV-08.

---

## 1. SV-05 — Sessions list real-time search bar

### Verbatim spec compliance

> *"A search bar sits at the top of the sessions list page, above the status tabs and session cards. As the user types (debounced ~150ms, no submit button), the list filters by case-insensitive substring match against session title AND session content."*

### Impl

- **Frontend** (`pages/SolvaSessions.jsx`): existing search input from Chunk 9.5 retained; debounce shortened to **150ms** (was 280ms) to match the spec. Placeholder updated to *"Search by title, framing, or synthesis content…"*.
- **Backend** (`routers/solva_v2.py::list_sessions`): the existing `$or` regex on `initial_framing` + `title` now also includes `layer_3.rendered_synthesis` so the synthesis output is searchable. v2 sessions still match on `intent` only — v2 doesn't carry synthesis content.
- **Empty state copy** (`SolvaSessions.jsx`): when `debouncedQ.trim()` is non-empty AND zero items match, render the verbatim spec copy `"No sessions found for "{q}". Try a different word or phrase."` (preserves the original "no sessions saved yet" copy when both q and status are empty).

### Tests

- `test_chunk14_sv05_search_matches_title` — title-only term surfaces the row.
- `test_chunk14_sv05_search_matches_framing` — framing-only term surfaces the row.
- `test_chunk14_sv05_search_matches_synthesis_content` — **NEW regression**: synthesis-only term must surface the row.
- `test_chunk14_sv05_search_case_insensitive` — lowercase form of an uppercase-only seed term still matches.
- `test_chunk14_sv05_zero_match_returns_empty_with_counts` — empty items + all-zero counts (counts honour q-filter per Chunk 11 status_counts pattern).

---

## 2. SV-06 — Rich text formatting in Solva responses

### Verbatim spec compliance

> *"Solva responses should be formatted using structured paragraphs — one idea or argument per paragraph — rather than a single block of unbroken text. Bullet lists and numbered lists should render as visual lists. Bold key terms should display as bold."*

### Impl

- **NEW** `/app/frontend/src/lib/proseBlocks.js` — pure-function `parseProseBlocks(text)` that returns `{type: "paragraph"|"bullets"|"numbered", inlines/items}[]` and `parseInlines(line)` that returns `[{kind: "text"|"bold", text}]`. Handles:
  - `\n\n`-separated paragraphs
  - `- `/`* `-prefixed bullet lines (require ALL lines in the paragraph to be bullet-style — avoids false positives)
  - `\d+\. `-prefixed numbered lines
  - `**bold**` inline markers
- **MODIFIED** `pages/SolvaPhaseDSession.jsx::ProseBlock` — replaced the legacy `<pre whitespace-pre-wrap>` block with two new components:
  - `ProseRenderer({text})` — maps the parsed blocks to JSX (`<p>`, `<ul><li>`, `<ol><li>`).
  - `Inlines({tokens})` — maps inline tokens to JSX (`<strong>` for bold, plain text otherwise).
- Out-of-scope (documented per dispatch): tables, code fences, headings, inline italic/links/images.

### Tests

- ESLint clean on `proseBlocks.js` (pure-function helpers, no React dependencies).
- Render-smoke step 16 verifies `solva-prose-block-*` testid is queryable after entering a Solva session (proves the renderer is wired).
- Manual: tested `parseProseBlocks("foo\n\nbar\n\n- one\n- two\n\n**bold**.")` returns `[paragraph, paragraph, bullets[2], paragraph(with bold inline)]` — confirmed correct.

---

## 3. SV-07 — Output window size + scroll

### Verbatim spec compliance

> *"The output window should occupy the majority of the available vertical space on the Solva page — a minimum of 60% of the viewport height is recommended."*

### Impl

- `pages/SolvaPhaseDSession.jsx::ProseBlock` — inner container now uses Tailwind: `min-h-[400px] sm:min-h-[60vh] max-h-[70vh] overflow-y-auto pr-1`.
  - 60vh on viewports ≥ sm breakpoint (640px) per spec.
  - 400px minimum on narrower viewports (responsive floor per dispatch).
  - 70vh cap with `overflow-y-auto` so very long syntheses scroll inside the panel rather than pushing the page chrome out.
  - Right-padding (`pr-1`) leaves space for the scrollbar so content doesn't get visually clipped.

### Tests

- Render-smoke step 16 measures `solva-prose-block-*` clientHeight ≥ 400px (verified after a session is opened).

---

## 4. SV-08 — 422 diagnostic + friendly-message fix

### Diagnostic finding (reproduction matrix, live preview)

| Test | Endpoint | Payload | HTTP | Trigger |
|---|---|---|---|---|
| 1 | `GET /api/solva/v2/sessions` (no `context_id`) | n/a | **422** | Required query param missing — already addressed via frontend `activeContext?.id` guard in Chunk 9.5 (`SolvaSessions.jsx:67-72`). |
| 2 | `POST /sessions/{sid}/framing` | `{"framing_text":""}` | **422** | `Field(min_length=20)` violation. |
| 3 | `POST /sessions/{sid}/framing` | `{"framing_text":"too short!"}` (10 chars) | **422** | Same min_length violation. |
| 4 | `POST /sessions/{sid}/framing` | `{}` | **422** | Required field missing. |

**Conclusion:** 422s only reproduce on truly malformed input. The bug class is friendliness — the raw Pydantic detail (`{type, loc, msg, input, ctx, url}` array shape) leaks a `pydantic.dev` URL to users via the toast. Per dispatch instruction: *"document the test cases in CHUNK_14_STATE.md and add user-facing validation messages."*

### Impl

- **NEW** `friendlySolvaError(err)` helper in `SolvaPhaseDSession.jsx` — smart-cast for Pydantic 422 detail arrays. Identifies the common patterns (`string_too_short` + `missing` on `framing_text`/`answer_text`) and returns user-friendly copy. Falls back to joining the raw `msg` fields with `·` for unknown 422 shapes.
- **Pre-validation** in `submitFramingAction` and `submitAnswerAction` — short-circuits BEFORE the API call when `draft.trim().length < 20` (framing) or `< 2` (answer), with the same friendly copy. Defence-in-depth: even if the disabled-button guard is bypassed, the 422 never round-trips.
- **Inline character-count hint** under the framing textarea (`solva-phase-d-framing-min-hint`) — shows `"X / 20 characters required"` while below threshold, flips to `"X characters — ready to submit"` (green) once threshold passed. Surfaces the rule visually so users never wonder why the button is disabled.

### Tests

- `test_chunk14_sv08_list_endpoint_422_without_context_id` — Pre-Chunk-9.5 SV-02 422 path remains correctly enforced server-side.
- `test_chunk14_sv08_framing_empty_returns_422` — empty framing_text → 422 `string_too_short`.
- `test_chunk14_sv08_framing_too_short_returns_422` — sub-threshold framing → 422.
- `test_chunk14_sv08_framing_missing_returns_422_with_loc` — missing field → 422 with extractable `loc` (proves `friendlySolvaError` smart-cast can identify the field).
- Render-smoke step 16 asserts the inline hint renders verbatim copy and flips on threshold passage.

---

## 5. Architectural checkpoint

- ✅ Zero new LLM call sites — SV-05 is search, SV-06 is render, SV-07 is CSS, SV-08 is validation. CI guard `test_no_direct_llm_calls_outside_shield` remains green.
- ✅ Shield gateway exclusivity preserved.
- ✅ `context_id` scoping intact.
- ✅ `tenant_id == account_id` boundary intact.
- ✅ No `repr(exc)` leaks — `friendlySolvaError` constructs strings via known-safe templates.
- ✅ No new third-party libraries — `proseBlocks.js` is pure JS + JSX, no markdown library.
- ✅ Schema-drift defensiveness — `parseProseBlocks` handles missing / non-string input without raising.
- ✅ Prior chunks (7–13) unaffected — cross-chunk pytest moved up by +10 (50 → 60).

---

## 6. Sub-bullet coverage table (Solva QA Brief → impl)

| SV-ID | Spec sub-bullet                                       | Impl                                                                                                                  | Test                                                                  |
|-------|-------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| SV-05 | Search bar at top of list                             | Existing in `SolvaSessions.jsx`                                                                                       | render-smoke step 16                                                  |
| SV-05 | Debounced ~150ms                                      | `useDebouncedValue(q, 150)` (was 280)                                                                                 | smoke + manual                                                        |
| SV-05 | Filters on title + content                            | Backend `$or` now includes `layer_3.rendered_synthesis`                                                               | `test_chunk14_sv05_search_matches_synthesis_content`                  |
| SV-05 | Case-insensitive substring                            | Mongo `$regex` with `$options: "i"` (pre-existing)                                                                    | `test_chunk14_sv05_search_case_insensitive`                           |
| SV-05 | Zero-match empty state                                | Verbatim spec copy in `SolvaSessions.jsx:208-223`                                                                     | render-smoke step 16 + `test_chunk14_sv05_zero_match_returns_empty_with_counts` |
| SV-05 | Counts honour both q AND status filter                | Counts taken AFTER q-filter, BEFORE status-filter (existing Chunk 13 + Chunk 11 pattern)                              | `test_chunk14_sv05_zero_match_returns_empty_with_counts`              |
| SV-06 | Paragraphs (preserve newlines)                        | `parseProseBlocks` splits on `\n\s*\n`                                                                                | static (block-shape test in jsdoc)                                    |
| SV-06 | Bullet lists (`- `, `* `)                             | `BULLET_LINE` regex; all-or-none promotion                                                                            | manual                                                                |
| SV-06 | Numbered lists (`1. `, `2. `)                         | `NUMBERED_LINE` regex                                                                                                 | manual                                                                |
| SV-06 | Bold (`**`)                                           | `BOLD` regex → `<strong>`                                                                                             | render-smoke step 16 (testid query)                                   |
| SV-06 | Applied to framing/answer/synthesis surfaces          | Single `ProseBlock` component used by all three                                                                       | static                                                                |
| SV-07 | ≥60% viewport height                                  | `sm:min-h-[60vh]`                                                                                                     | render-smoke step 16 clientHeight check                               |
| SV-07 | Overflow-y scroll                                     | `max-h-[70vh] overflow-y-auto pr-1`                                                                                   | manual                                                                |
| SV-07 | 400px responsive floor                                | `min-h-[400px]`                                                                                                       | smoke + manual                                                        |
| SV-08 | 422 diagnostic                                        | Reproduction matrix above                                                                                             | `test_chunk14_sv08_*` (4 cases)                                       |
| SV-08 | Friendly validation messages                          | `friendlySolvaError` smart-cast + pre-validation + inline hint                                                        | render-smoke step 16                                                  |

---

## 7. Out-of-scope / deferred

- Tables / code fences in `ProseBlock` — backend voice files keep responses prose-only; add only if a real session surfaces a complex shape.
- Promotion of `stripCitations` + `splitToBullets` from Pulse into the shared `proseBlocks.js` — left for a future cleanup pass to avoid scope creep.
- Cross-context Solva sessions aggregate — queued in `CHUNK_17_CLEANUP_QUEUE.md` as C17-003.

## 8. Solva QA Brief — fully closed

All 8 SV-IDs from the Solva QA Brief are now DONE:
- SV-01 ✅ Chunk 9.5
- SV-02 ✅ Chunk 9.5
- SV-03 ✅ Chunk 9.5
- SV-04 ✅ Chunk 13
- SV-05 ✅ Chunk 14
- SV-06 ✅ Chunk 14
- SV-07 ✅ Chunk 14
- SV-08 ✅ Chunk 14

Next: 16-May P2 batch 1 (Chunk 15).
