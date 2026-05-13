# Chunk 5 — Create Summary Deck + Create Report flows · Diagnosis

Tickets covered: **WS-R09 · WS-R10 · WS-R11 · WS-R13 · WS-R14**

QA verdict from the 13 May report (paraphrased): the Decks tab's
"Create Summary Deck" action and the Reports tab's "Create Report"
action are non-functional across **all three creation paths** —
*From Existing Brief*, *Blank*, *From External Document*. Two of the
three paths fail silently (toast nothing); the third (brief picker)
renders an empty dropdown even when briefs exist in the workspace.

This is `Patch 2B.1` infrastructure (the `CreateArtefactModal`
component + the per-tab "Create Summary Deck" / "Create Report" action
chips) that was speculatively wired but never finished — the modal
points at backend routes that don't exist, and the brief dropdown
sends a compound aggregate id the backend never reads.

Same class of defect as Chunk 4 (frontend → backend contract drift)
but at a different layer. Chunk 4 was the wizard's `initialType` and
step dispatch; this chunk is the entire create-flow surface.

---

## 1. Per-path diagnosis (6 sections)

### Deck × From Existing Brief — WS-R09 surface, kind=deck
**Symptom**: The brief dropdown lists nothing even when the workspace
clearly has briefs.

**Reproduction**:
1. Sign in as `bramuel@syni.ai` with at least one Solva session
   composed to a brief.
2. Open Work Studio → Decks tab → "Create Summary Deck" →
   pick *An existing brief in this context*.
3. Observe an empty `<select>` (only the "— None selected —" entry).

**Root cause(s)**:
- **The dropdown call is correct in shape but its result is unusable.**
  `CreateArtefactModal.jsx:50-54` queries
  `GET /contexts/{cid}/briefings/aggregates?kind=briefing&page_size=50`,
  which returns rows from `db.work_studio_briefs` (correct collection).
  But each item carries a **compound aggregate id**
  (`briefing::<uuid>`, see `routers/briefings.py:1163` →
  `_agg_id("briefing", r["id"])`). The frontend stores that compound
  id in `selectedBriefId` and posts it to the backend as
  `source_brief_id` — when the backend tries to look it up by UUID it
  fails. Net effect: even if a brief is selected, the downstream
  POST 404s. No code on the dropdown render side actually surfaces
  this (the dropdown renders fine; the failure is on submit).
- **The visible "no briefs" symptom QA reported is a SECOND bug** — on
  freshly-onboarded accounts there are no `work_studio_briefs` rows
  yet (these are written only by the Solva → C.1 export path or the
  C.2 enhance loop). The dropdown is technically empty for the right
  reason on those accounts. We surface a clear empty-state in the fix.

**Severity**: critical (entire path non-functional regardless of brief
availability).

---

### Deck × Blank — WS-R10 surface, kind=deck
**Symptom**: Submitting the modal shows a generic "Could not create
deck" toast; no row appears in the Decks tab.

**Reproduction**: same modal, pick *Blank — I'll write it from scratch*,
type a title, submit.

**Root cause**: `CreateArtefactModal.jsx:81-84` posts to
`POST /api/contexts/{cid}/decks`. **That endpoint does not exist.**
The decks router (`routers/decks.py`) only exposes
`/decks/outline`, `/decks/{outline_id}/generate`,
`/decks/{deck_id}/quality_check`, `/decks/{deck_id}/feedback`,
and `GET /decks` (list). There is no `POST /decks` for a blank draft
creation. FastAPI 405s the request; axios surfaces the generic error
message.

**Severity**: critical.

---

### Deck × From External Document — WS-R10 surface, kind=deck
**Symptom**: Submitting the modal does the same generic failure as
Blank. The user is also never asked to actually attach a document — the
radio option exists but no picker appears.

**Reproduction**: same modal, pick *An external document I'll attach
later*, submit.

**Root cause(s)**:
- Same 404 as Blank: `POST /contexts/{cid}/decks` doesn't exist.
- The frontend never collects a document. The current modal says "I'll
  attach later" — meaning even if the backend route existed, no
  `source_document_id` would be bound to the new artefact. The user
  has no obvious surface to attach the document afterwards either.

**Severity**: critical.

---

### Report × From Existing Brief — WS-R13 surface, kind=report
**Symptom**: Identical empty dropdown; submit fails.

**Reproduction**: Work Studio → Reports tab → "Create Report" → pick
*An existing brief in this context*.

**Root cause(s)**:
- Same compound-id bug as the Deck variant.
- **Additionally**: the frontend posts to
  `POST /api/contexts/{cid}/cycle/reports/compose`. The actual backend
  route is `POST /api/contexts/{cid}/reports/compose` (no `cycle/`
  prefix). Path mismatch → 404.
- **Even if the path matched**, the backend's `ReportComposeIn`
  Pydantic model (`routers/cycle.py:687`) requires `cycle_name`,
  `title`, and a `chain` array of named reviewers — a strict shape
  for the multi-tier review-chain flow. The CreateArtefactModal sends
  only `{title, source, source_brief_id}` — 422 even if the path were
  right.

**Severity**: critical.

---

### Report × Blank — WS-R14 surface, kind=report
**Symptom**: Generic failure toast; no row.

**Root cause**: Same triple — wrong path (`cycle/reports/compose`),
wrong payload shape, no route accepts `{title, source}` for a draft
report.

**Severity**: critical.

---

### Report × From External Document — WS-R14 surface, kind=report
**Symptom**: Generic failure toast; no row; no document bound.

**Root cause**: Same triple as above + no document picker on the
frontend (radio option only).

**Severity**: critical.

---

## 2. Root cause(s), consolidated

Three orthogonal defects compound:

1. **No backend endpoint exists** for creating a draft Deck or draft
   Report from Work Studio. The CreateArtefactModal was written
   against speculative routes (`POST /decks`, `POST /cycle/reports/compose`)
   that were never implemented.
2. **Compound aggregate id leakage**: the brief dropdown picks an id
   from the aggregates listing (`briefing::<uuid>`) and forwards it
   unchanged. The backend (when one is added) needs the raw uuid.
3. **External document path is half-wired**: the radio option exists
   but no document picker. The user has no way to actually attach a
   document, so even with backend support the artefact would be born
   detached.

A sibling defect: aggregate row listings for Decks/Reports/Briefings
don't surface a `description` field, so the Work Studio listing rows
silently lack the same description chain Patch 28D added to the
Document Journal (`Workspace.jsx`).

---

## 3. Fix paths

### Backend
- **New endpoint**: `POST /api/contexts/{cid}/work-studio/artefacts`
  in `routers/work_studio_from_source.py`. Accepts:
  ```json
  {
    "kind":               "deck" | "report",
    "title":              "<= 200 chars",
    "source":             "blank" | "brief" | "external_document",
    "source_brief_id":    "<raw uuid>" (required when source=brief),
    "source_document_id": "<raw uuid>" (required when source=external_document)
  }
  ```
  Returns:
  ```json
  {
    "kind":         "<kind>",
    "artefact_id":  "<uuid>",
    "brief_id":     "<uuid or null>",
    "document_id":  "<uuid or null>",
    "redirect_url": "/app/studio/composer/<kind>/<artefact_id>"
  }
  ```
- Inserts into `db.decks` / `db.reports`. Row carries `title`,
  `description`, `body`, `status="draft"`, `source`, `brief_id` (when
  applicable), `source_document_id` (when applicable), `account_id`,
  `context_id`, `created_at`, `updated_at`.
- The composer (`routers/studio_blocks.py:_seed_blocks_from_artefact`)
  already supports `body`-driven seeding for both kinds — no change
  needed there.
- `_list_decks` / `_list_reports` extended to surface `description`
  on each row so the Work Studio listing carries the Patch 28D
  description chain (`preview → description → placeholder`).

### Frontend
- `CreateArtefactModal.jsx`:
  - Strip the `briefing::` aggregate prefix before sending
    `source_brief_id`.
  - Add a document picker for the `external_document` path
    (fetches `GET /contexts/{cid}/documents`, simple `<select>`).
  - Post to the new endpoint, use the returned `redirect_url`.
  - Defer-route: the `kind="report"` route is now the canonical
    composer surface (`/app/studio/composer/report/{id}`), not the
    legacy `/app/cycle?tab=overview&report={id}` deep-link (which
    expects the multi-tier review-chain flow, not a fresh draft).
- `WorkStudio.jsx::BriefRow`: render a 1-line description under the
  title using the same `preview → description → placeholder` chain
  Patch 28D applied to the Document Journal. (Re-uses
  `data-testid="work-studio-brief-row-description"`.)

---

## 4. Tests

`/app/backend/tests/test_chunk5_create_artefact.py` covers:

1. `test_create_deck_blank_creates_draft_row` — POST blank → 200 +
   `artefact_id`; listing endpoint shows it.
2. `test_create_deck_from_brief_links_source` — seed brief → POST
   source=brief + raw uuid → row carries `brief_id` ref.
3. `test_create_deck_from_external_document_links_doc` — seed doc →
   POST source=external_document → row carries `source_document_id`.
4. `test_create_report_blank_creates_draft_row` — same for reports.
5. `test_create_report_from_brief_links_source` — same.
6. `test_create_report_from_external_document_links_doc` — same.
7. `test_create_artefact_rejects_briefing_kind` — only `deck`/`report`
   accepted; `briefing` (which has its own ExportModal flow) 422s.
8. `test_create_artefact_brief_missing_raises_404` — bogus
   `source_brief_id` returns 404 (vs silent draft).
9. `test_create_artefact_document_missing_raises_404` — bogus
   `source_document_id` returns 404.
10. `test_create_artefact_compound_brief_id_is_accepted` — the
    aggregate-id form (`briefing::<uuid>`) is gracefully unwrapped
    server-side (defence-in-depth in case future UI calls slip).
11. `test_list_decks_surfaces_description` — listing API now emits
    `description` per row (Patch 28D parity).

Render-smoke extended with `smokeChunk5CreateArtefact` step that
clicks "Create Summary Deck" on the Decks tab, fills the Blank path,
asserts the new row appears in the listing.

---

## 5. Step-5 cross-check

- **Briefing tab Create a Brief** (`onExport("brief")`) — uses the
  C.1 ExportModal (legacy), NOT the CreateArtefactModal. Unchanged
  and still functional.
- **`api` client compliance** — CreateArtefactModal uses `api.post`
  (axios with bearer interceptor); ESLint clean per Patch 24.
- **Patch 28D description chain** — listing endpoint now emits
  `description`, BriefRow renders it.
- **Sibling soft-debts found**: none new this chunk.

---

## 6. Diagnosis doc path

This file: `/app/memory/sprints/CHUNK_5_DECK_REPORT_DIAGNOSIS.md`

---

## 7. Clarifications or autonomous decisions

**Autonomous decisions** (logged for PO review):

- **Report draft route**: changed the post-create redirect for new
  Reports from `/app/cycle?tab=overview&report={id}` to
  `/app/studio/composer/report/{id}`. The former expects the
  multi-tier review-chain (`compose_report` in `routers/cycle.py`);
  the latter is the Phase 8 block composer which is the canonical
  artefact editor surface. Reports created via Work Studio are
  block-composer artefacts, not review-chain artefacts; routing them
  through the composer matches Decks and Briefings.
- **Blank path body**: a Blank-source artefact is born with an empty
  body string. The block composer seeds a single heading (the title)
  + a fallback `—` paragraph automatically. The user starts editing
  in the composer immediately.
- **External-document path body**: the artefact's `body` is seeded
  with the document's `preview` (when present) or a short `Composed
  from document: <name>.` placeholder line. The composer's seeder
  picks this up. The user can then continue editing with the document
  attached as a citation source via the existing block composer
  affordances.

**Clarifications for PO** (deferred, not blocking the fix):

- **Source attribution surface**: should the composer header carry a
  visible "Composed from: <brief|document>" chip? Currently the link
  is stored on the row but not shown in the composer UI. Logged for
  product review.
