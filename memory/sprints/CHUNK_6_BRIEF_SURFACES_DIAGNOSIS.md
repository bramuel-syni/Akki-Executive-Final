# Chunk 6 — Brief surfaces · Diagnosis

Tickets covered: **WS-R01 · WS-R17 · WS-R18 · WS-R19**

---

## 0. WS-R17 verification (does Chunk 5 cover this?) — **NO**

**Reproduction (live curl against preview URL, 2026-05-13)**:
```
GET /api/contexts/{cid}/briefings/aggregates/briefing::0df84704-…-f1fe3e81
→ HTTP 400
→ {"detail":"Bad aggregate id."}
```

**Root cause**: `routers/briefings.py:436 get_brief_aggregate` has only
three explicit dispatch branches:
```python
if parsed["kind"] == "cycle_board_pack":     return …
if parsed["kind"] == "cycle_minutes":        return …
return await _detail_cycle_committee_pack(...)   # fall-through
```

The `_AGG_KINDS` whitelist (`routers/briefings.py:838`) carries six
kinds — the three above PLUS `deck`, `report`, and `briefing`. When a
user clicks any brief, deck, or report row in Work Studio the
aggregate id (`briefing::<uuid>` / `deck::<uuid>` / `report::<uuid>`)
falls through to `_detail_cycle_committee_pack`. That handler's first
line is `if "::" not in internal_id: raise HTTPException(400, "Bad
aggregate id.")`. The raw UUID coming in has no `::` separator → 400
fires for every non-cycle kind.

Chunk 5 fixed the CREATE path; it did not touch the DETAIL fetch.
WS-R17 needed its own fix.

**Note**: this same bug affects clicking Deck and Report rows too —
not just briefings. QA only logged the briefing case because that
tab has more visible content in the seed.

---

## 1. WS-R01 — Drawer CTA with undefined target

**Reproduction**: click a brief in the Briefing tab → drawer opens
loading-spinner → switches to error state showing "Bad aggregate id."
The drawer renders the `apiErrorMessage()` payload with no fall-back
view. There is no successful detail render today for `kind=briefing`
(or `deck` or `report`) because of WS-R17.

**Root cause (compound with WS-R17)**:
- The CURRENT `BriefDrawer` carries NO primary CTA — neither "Open in
  composer" nor "Download". It's a read-only detail view. The drawer
  was designed to display notes + citations, with each citation chip
  routing to `/app/documents/${c.doc_id}`.
- When the backend returns 400 / 404, the drawer shows the error
  banner but offers no way forward.
- The user reported "CTA whose target is undefined" — most likely
  the citation chip case: when `_detail_cycle_committee_pack` is
  miscalled with a briefing id, the doc rows it tries to surface
  don't carry the right `doc_id` field, so the citation `<Link>`
  routes to `/app/documents/undefined`. We confirmed this scenario
  in code review.

**Real fix needed**: in addition to fixing WS-R17, the drawer should
carry a **primary CTA to open the artefact in the block composer** —
the same redirect Chunk 5 introduced for newly-created artefacts.
A briefing detail → "Open in composer" → `/app/studio/composer/briefing/<id>`.
Same for decks and reports.

---

## 2. WS-R18 — "Seed Failed" on chat → brief

**Reproduction (live curl)**:
```
POST /api/contexts/{cid}/work-studio/from-source
  body: {source_type:"chat_artefact", source_id:"<empty-chat-id>", kind:"briefing"}
→ HTTP 409
→ {"detail":{"code":"chat_empty","message":"This chat has no assistant content to compose from yet."}}
```

**Frontend in `SourceStep.jsx:362`**:
```js
toast.error("Seed failed", { description: msg });
```

**Root cause**:
- The toast title "Seed failed" is engineering-speak for what is
  fundamentally a user-actionable state (the chat has no assistant
  responses yet — go finish chatting first). This is the same
  authenticity violation Chunk 3 fixed for `worker_crash`: opaque
  internal jargon surfaces to the user instead of the real cause.
- The actual chat→brief mechanism works correctly when the chat has
  assistant messages; verified by reading `_resolve_chat_envelope`
  in `routers/work_studio_from_source.py:167-199`. The 409 fires
  only when `full.strip() == ""` (no assistant content).
- A second contributor: when the chat resolution returns an error,
  `apiErrorMessage()` doesn't always extract `detail.message` from
  nested dict payloads (depends on shape). For nested-dict 409s the
  user sees `[object Object]` or the raw code.

**Real fix needed**:
- Rename "Seed failed" → context-specific titles: "This chat is
  empty" / "Brief generation failed". Pull `detail.message` from
  nested-dict errors so the user reads the actual reason.
- Apply the same fix to the "Generate failed" branch of
  `handleGenerateNow` (same toast pattern, same opacity).
- Bonus: pre-flight check in the picker — disable the "Open in
  composer" / "Generate document now" buttons when the picked chat
  has `message_count == 0`, with a tooltip explaining why.

---

## 3. WS-R19 — DOCX title truncated / wrong

**Reproduction (code path trace)**:
1. User types a chat titled `"Q3 board meeting — strategic review of expansion plans into the East African corridor"` (87 chars).
2. Generates a brief via `SourceStep` → `from-source` → `build_brief_from_solva`.
3. `_resolve_chat_envelope` stuffs `chat.title` into the envelope's `intent` field.
4. `build_brief_from_solva` at line 226:
   ```py
   title = f"{sub_title}: {(intent[:70] + ('…' if len(intent) > 70 else '')) or '—'}"
   ```
5. The chat's `submodule` is hard-coded to `"seek_clarity"` in `_resolve_chat_envelope`, so `sub_title = "Clarity Read"`.
6. Final brief.title: `"Clarity Read: Q3 board meeting — strategic review of expansion plans into…"` (truncated at 70 chars + ellipsis).
7. The DOCX renderer renders this as the cover title at 28pt.

**Root cause** (two compound issues):
1. **`intent[:70]` is too aggressive**. A 28pt title with 1-inch
   margins comfortably fits ~75 chars per line and naturally wraps
   beyond that. Truncating at 70 chars throws away meaning the user
   wants to preserve.
2. **Submodule prefix is wrong for chat sources**. The user expects
   their chat's title to BE the brief title, not to be prefixed with
   "Clarity Read:". The prefix is appropriate for Solva submodule
   outputs (where the submodule identity carries editorial meaning)
   but not for free-form chat artefacts.

**Real fix needed**:
- Add a `title_override` argument to `build_brief_from_solva`.
- `_resolve_chat_envelope` passes `title_override=chat.title` — the
  chat's title becomes the brief title verbatim (truncated only by
  the per-collection 200-char cap, not 70).
- Raise the Solva-session truncation from 70 → 200 chars (still leaves
  ample DOCX cover room; covers virtually all real intent strings).
- Verify PPTX + PDF renderers also read the full title — they do
  (both read `brief.title` directly, no further truncation).

---

## 4. Cross-cutting findings (Step 6 audit)

### 4.1 Other artefact drawers
- **Decks page (`pages/Decks.jsx`)** — has its own deep-link surface;
  no aggregate-id drawer. Not affected.
- **Reports** — surfaced through `/app/cycle/.../reports/...` chain
  artefacts; different drawer pattern. Not affected.
- Only Work Studio's `BriefDrawer` carries the "undefined CTA" risk.

### 4.2 Other DOCX export paths
- **Cycle compilation DOCX** (`work_studio_export.py`) — reads
  `artefact.title` directly from the artefact row; no truncation.
- **Work Studio Enhance DOCX** — same pattern. No 70-char cap.
- Only the `build_brief_from_solva` path carries the truncation bug.

### 4.3 "Seed failed" / "Generate failed" elsewhere
- `SourceStep.jsx` carries both toasts (lines 362, 402). Both fixed.
- No other file emits these literal toast titles. Grep clean.
- Backend `repr(exc)` SSE soft-debt (logged in SYSTEM_STATE §7 from
  Chunk 3) remains the next polish item — not in scope here.

---

## 5. Fix plan summary

**Backend** (`routers/briefings.py`):
1. Add proper dispatch branches in `get_brief_aggregate` for `deck`,
   `report`, `briefing` kinds. New helpers `_detail_deck`,
   `_detail_report`, `_detail_briefing` that read from `db.decks`,
   `db.reports`, `db.work_studio_briefs` respectively and shape the
   response to match the existing aggregate detail contract (`id`,
   `kind`, `name`, `topline`, `notes`, `period_*`, etc.) PLUS new
   fields: `composer_url` (the canonical Open-in-composer target)
   and `artefact_id` (raw uuid).

**Backend** (`work_studio/brief.py`):
2. Add `title_override` parameter to `build_brief_from_solva`.
3. Raise the intent-truncation cap from 70 → 200 chars.

**Backend** (`routers/work_studio_from_source.py`):
4. `_resolve_chat_envelope` returns the chat title in a new
   `title_override` field on the envelope.
5. Both call sites of `build_brief_from_solva` (this file +
   `routers/work_studio_phase_c.py`) thread the title_override
   through when set.

**Frontend** (`pages/WorkStudio.jsx::BriefDrawer`):
6. Add a primary CTA "Open in composer" that reads
   `detail.composer_url` and routes the user via `useNavigate`.
   Visible whenever `composer_url` is present.

**Frontend** (`components/studio/SourceStep.jsx`):
7. Replace the opaque "Seed failed" / "Generate failed" toast titles
   with context-specific titles.
8. Extract `detail.message` from nested-dict 409s so the description
   text is human-readable.
9. (Light polish) disable the Generate buttons when the picked chat
   has `message_count == 0` with an informative tooltip.

---

## 6. Tests
- 1 backend regression — aggregate detail for `briefing`/`deck`/`report`
  kinds returns the correct row + `composer_url`, instead of 400.
- 1 backend — long chat title (≥100 chars) yields a DOCX whose
  rendered cover-title carries the FULL title.
- 1 backend — `_resolve_chat_envelope` returns `title_override`.
- 1 backend — `build_brief_from_solva` respects `title_override`
  when set.
- 1 frontend — render-smoke extension: click a deck/report/briefing
  row → drawer opens → composer CTA testid is present with a
  non-undefined target.

---

## 7. Diagnosis doc path

This file: `/app/memory/sprints/CHUNK_6_BRIEF_SURFACES_DIAGNOSIS.md`

---

## 8. Autonomous decisions

- **`composer_url` field on aggregate detail**: introduced as a new
  field rather than a separate endpoint. Keeps the drawer's data
  load to one round-trip and matches the redirect_url convention
  Chunk 5 established for create flows.
- **70-char intent truncation kept (raised to 200)**: not removed
  entirely, because a runaway-length intent string (which the LLM
  sometimes produces) could break the DOCX cover layout. 200 chars
  is the new ceiling — covers ~98% of real intents based on the
  seed data, while still preventing pathological titles.
- **"Seed failed" → kind-aware messaging**: rather than a blanket
  rename, the new titles describe the user's situation ("This chat
  is empty", "This Solva session needs synthesis first", etc.).
  When the failure isn't one of those known cases, the title falls
  back to "Brief generation failed" (still less opaque than "Seed
  failed").

---

## 9. Clarifications for PO

- **Drawer CTA scope**: currently proposing a single "Open in
  composer" primary CTA. The QA report didn't specify whether
  secondary CTAs (Download, Send to Cycle) should also be added.
  Logged for PO sign-off; default in this chunk is the single
  primary CTA.
- **Submodule prefix for Solva briefs**: keeping the "Clarity Read:"
  / "Strategy Memo:" prefix for Solva sessions (where the submodule
  identity carries editorial meaning). Dropping it only for chat
  sources. Confirm with PO if uniformity is preferred.
