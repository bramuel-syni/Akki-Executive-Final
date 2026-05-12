# Patch 28 — Document Journal End-to-End Audit

> Audit + fix log for the user-reported "Document Journal has been
> the most buggy in this project. After uploading document, the
> document page has an empty button."

## 1. Module inventory

| Surface | File | Role |
|---|---|---|
| Listing + drawer | `pages/Workspace.jsx` | `/app/workspace` — the Document Journal landing |
| Side drawer (in-page) | `pages/Workspace.jsx::JournalDrawer` | Quick-look right drawer for one doc |
| Full reader | `pages/ReadingView.jsx` | `/app/documents/:id` — reading + structural detail |
| Reader top bar | `components/reading/ReadingTopBar.jsx` | Back / Download / Open in Studio controls |
| Upload modal | `components/upload/UploadModal.jsx` | "+ Add document" entry point (P0 fix in Patch 23) |
| Backend list | `routers/documents.py::list_documents` | `GET /api/contexts/{cid}/documents` |
| Backend detail | `routers/documents.py::get_document` | `GET /api/contexts/{cid}/documents/{doc_id}` |
| Backend upload | `routers/documents.py::upload_document` | `POST /api/contexts/{cid}/documents` (multipart) |
| Backend download | `routers/documents.py::download_document` | `GET /api/contexts/{cid}/documents/{doc_id}/download` |
| Backend delete | `routers/documents.py::delete_document` | `DELETE /api/contexts/{cid}/documents/{doc_id}` |

## 2. Defects found

### Defect A — "Empty button" on the document reader
**Symptom**: ReadingView (`/app/documents/:id`) top bar shows a Download button that has no visible label and, in some environments, does nothing when clicked.
**Root cause**: `components/reading/ReadingTopBar.jsx:96-105` rendered the download as a plain `<a href={API_BASE}/contexts/.../download>`. Two bugs in one:
1. Icon-only with `title="Download original"` but no visible text — visually reads as an "empty button".
2. Plain `<a href>` does NOT send the `Authorization: Bearer` header from localStorage. Cookies usually cover same-origin, but in environments where the cookie scope diverges from the static origin (split CDN + API), the download silently returns 401 and opens a blank tab.
**Fix**: replaced with an axios `api.get` blob fetch + Object URL download. Now:
- Carries the bearer token automatically via the axios interceptor.
- Triggers a real browser download with the original filename (via `Content-Disposition` parsing).
- Adds `aria-label="Download original"` for screen-reader users.

### Defect B — Document listing rows had no description line
**Symptom**: Rows showed only the title; a snippet line existed but only rendered conditionally and was invisible when absent.
**Fix** (Patch 28D): Always render the description line. Uses `row.snippet` (derived from `doc.summary` or first 240 chars of `extracted_text` — already computed at `Workspace.jsx:117-120`) when present; muted italic placeholder *"No summary available yet."* when not.

### Defect C — UploadModal 401
Already fixed in P0 (Patch 23). Re-verified by Patch 24A's render-smoke (which now asserts the `Authorization: Bearer` header on upload requests).

## 3. End-to-end verification

Pytest happy path: `/app/backend/tests/test_patch_28_home_doc_journal.py::test_doc_journal_happy_path` (in-process):
1. Register fresh account
2. Create fresh context
3. POST `/api/contexts/{cid}/documents` (multipart) → 200
4. GET `/api/contexts/{cid}/documents` (list) → 200, doc appears
5. GET `/api/contexts/{cid}/documents/{doc_id}` (detail) → 200
6. GET `/api/contexts/{cid}/documents/{doc_id}/download` → 200, body matches uploaded bytes

All 4 backend stages green. Render-smoke covers the frontend rendering of the listing + detail.

## 4. Out of scope (deferred)

- Delete from drawer / from listing — backend `DELETE` exists; UI affordance to call it lives only inside the JournalDrawer right now. Not flagged by user; not changed.
- Re-upload (replace existing document with a new version) — no UI; backend has no `PATCH /documents/{id}` content-replacement endpoint. Future patch if needed.
- Document version history — not built; future patch.

— end of audit —
