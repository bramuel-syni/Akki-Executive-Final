# Phase F.1 — Three production gaps closed (CLOSEOUT)

**Date:** 2026-05-18
**Status:** ✅ COMPLETE. Phase F.1 is a follow-up to Phase F closing three production gaps surfaced by the post-rewrite capability check.

## Scope dispatched

> P0 — Phase F Sub-task A seed-payload anchoring broken in production.
> P1 — Mid-Solva-session document upload missing (workflow wall when FAR asks for evidence mid-session).
> P2 — OCR + spreadsheet text extraction (images and tabular data invisible to the LLM).

All three landed. **660 pytest passing** (was 648, +12 net new). Render-smoke GREEN across 11 routes. CI guard `test_no_direct_llm_calls_outside_shield` green.

---

## P0 — Phase F seed-payload anchoring

### What was broken
The Phase F-shipped `_resolve_seed_references` in `routers/solva_phase_d.py` had three real production bugs:
1. Query filter `account_id` — the `documents` collection has NO `account_id` field. Production queries matched nothing. The Phase F test fixture seeded an `account_id` synthetically and so passed in CI but failed in real life.
2. Projection asked for `title` + `summary` — the schema stores `name` + `preview` + `extracted_text`. The `label` fallback always returned a bare doc ID.
3. Even when resolution would have worked, the anchor only carried `{ref_type, ref_id, label}`. The document body was NEVER pulled into the session row. FAR ran blind on Layer 0.

### What changed (`routers/solva_phase_d.py`)
- **Dropped `account_id` from the documents query.** `context_id` already scopes correctly via the membership chain in `require_context_membership()`.
- **Projection switched to real schema fields**: `name`, `original_filename`, `extracted_text`, `preview`, `status`.
- **Each anchor now carries an `excerpt`** of `extracted_text[:8000]`, with `preview` as the fallback. FAR / Layer 0 reasoning now sees real document body.
- `account_id` is still accepted by the helper (back-compat) but unused for documents/cycles. Work-studio artefacts also dropped the `account_id` query filter for symmetry.

### Live evidence

```bash
$ curl -F file=@q4-audit.docx -F display_name="P0 curl test" .../api/contexts/{cid}/documents
{"id":"5f861cbf-…","status":"extracted","extracted_chars":80, …}

$ curl -X POST .../api/contexts/{cid}/solva/v2/sessions \
    -d '{"sub_module":"seek_clarity",
         "seed_payload":{"source":"document_journal",
                         "source_id":"5f861cbf-…",
                         "attached_references":["5f861cbf-…"]}}'
ref_type:  document
ref_id:    5f861cbf-ed17-4760-9662-3147e7d6909e
label:     P0 curl test                              ← real `name`, not bare id
excerpt:   'Q4 audit committee briefing — bank reported 12% lift in tier-1 capital ratios.'
status:    extracted                                  ← real `status`
```

The anchor excerpt contains real text from the DOCX. FAR can now read it.

### Test coverage
- `test_p0_seed_resolves_documents_without_account_id_field` — uploads a real DOCX through the actual upload endpoint, references it in a seed payload, asserts the anchor label = `display_name` and the excerpt contains a distinctive substring from the file.
- `test_p0_cycle_anchor_resolves_without_account_id` — cycles also context-scoped, no `account_id` needed.

---

## P1 — Mid-Solva-session document attach

### What was missing
When FAR asks "what document supports that?" mid-session, the user had no way to attach. Phase D had zero attach UI and zero attach backend. Legacy v2 had a link-only backend (no real upload) and only on the framing screen. Workflow: abandon session → upload via Doc Journal → return → no way to bind to active session.

### What changed

**Backend** — `routers/solva_phase_d.py`:
- New `POST /api/contexts/{cid}/solva/v2/sessions/{sid}/attach-document`. Dispatched by `Content-Type`:
  - `multipart/form-data` with `file=…` → ClamAV scan → `extract_text` → storage save → insert into `documents` (with `doc_type=solva_attachment`, `source_channel=solva_attach`) → anchor on the session.
  - `application/json` with `{"document_id":"…"}` → context-scoped lookup → 404 if not found → anchor on the session.
- Conflict gate: returns `409 ConflictError` if the session is already in a terminal layer state.
- New `GET /api/contexts/{cid}/solva/v2/sessions/{sid}/attachments` — listing view that omits the full `excerpt` body (only `excerpt_chars` is exposed) so the UI list stays light.
- Anchor shape includes `attached_mid_session: True` + `attached_at` ISO timestamp + an `orchestration_audit_log` event.

**Frontend** — `pages/SolvaPhaseDSession.jsx` + new `components/solva/AttachDocumentModal.jsx`:
- Paperclip button visible on EVERY answer surface (framing + layer 1 + layer 2). `data-testid`s: `solva-phase-d-attach-btn-framing`, `solva-phase-d-attach-btn-layer_1`, `solva-phase-d-attach-btn-layer_2`.
- Modal has two tabs: **Upload new** (drop-zone + file picker, multipart POST) + **From Document Journal** (searchable list of context docs, JSON POST).
- After attach succeeds, an inline emerald confirmation strip surfaces: `"Attached: {doc_name}. Akki now has the document in context."` Dismissible.
- Persistent "Akki is reading N documents:" strip with anchor chips above the body whenever any anchor exists.

### Live evidence

```bash
$ SID=$(curl -X POST .../sessions -d '{"sub_module":"seek_clarity"}' | jq -r .session_id)
$ curl -X POST .../sessions/$SID/attach-document -F file=@midsession.docx
{
  "ok": true,
  "mode": "upload",
  "anchor": {
    "ref_type": "document",
    "ref_id": "…",
    "label": "p1-midsession",
    "excerpt": "Mid-session evidence — the CFO approved the proposed haircut.",
    "attached_mid_session": true,
    …
  },
  "session": {...}
}
```

Screenshot at `/tmp/p1-paperclip-modal.png` (attached to closeout dispatch) shows the paperclip Attach button + the modal with both tabs visible on the framing screen.

### Test coverage
- `test_p1_attach_via_multipart_upload` — multipart upload anchors with real DOCX text in the excerpt, list endpoint reflects it, list view doesn't leak the excerpt body.
- `test_p1_attach_via_existing_document_id_json` — JSON `{document_id}` links an existing context doc.
- `test_p1_attach_rejects_cross_context_document` — doc from another context returns 404 (tenant/context isolation).
- `test_p1_attach_rejects_when_no_payload` — neither file nor document_id → 400 ValidationError.
- `test_p1_attach_rejects_unsupported_mime` — `.exe` → 415 UnsupportedMediaType.

---

## P2 — OCR + spreadsheet extraction

### What was missing
`.png/.jpg/.jpeg/.webp/.heic/.heif/.csv/.xlsx` were in `ACCEPT_EXT` but the `extract_text` switch returned `"Unsupported file type: .ext"` for all of them. Bank QA visual evidence (scanned letters, regulator screenshots) and tabular financial data were invisible to every downstream Shield consumer.

### What changed (`documents_service.py`)

| Branch | Library | Bounds |
|---|---|---|
| `.png/.jpg/.jpeg/.webp` | `PIL.Image` + `pytesseract` | downscaled to ≤ 2400px max dimension before OCR |
| `.heic/.heif` | `pillow_heif.register_heif_opener` + Pillow + Tesseract | same downscale bound |
| `.xlsx` | `openpyxl.load_workbook(read_only=True, data_only=True)` | early-exit on 200k char cap; `[Sheet: {name}]` headers between sheets |
| `.csv` | `csv.reader` + UTF-8 → Latin-1 fallback for legacy bank exports | early-exit on 200k char cap |

- Per-image cap: **`OCR_MAX_BYTES = 5 MB`**, **`OCR_MAX_DIMENSION = 2400px`** (downscale before OCR to bound Tesseract runtime).
- Graceful failure: Tesseract / Pillow exceptions wrapped uniformly as `("", f"{ExcName}: {msg}")`. Empty OCR result returns `("", "Image had no extractable text. Try a higher-resolution scan.")`. No crashes.

### Deps added (`requirements.txt`)
```
openpyxl==3.1.5
pillow_heif==1.3.0
pytesseract==0.3.13
```
`pillow==12.2.0` was already present. System `tesseract-ocr` (5.3.0) installed via `apt-get install -y tesseract-ocr`. This dep will need to land in the production Dockerfile too — surfaced in the carry-over list below.

### Live evidence

```bash
$ python3 -c "from PIL import Image, ImageDraw, ImageFont
img=Image.new('RGB',(800,200),'white'); d=ImageDraw.Draw(img)
font=ImageFont.truetype('DejaVuSans-Bold.ttf',48)
d.text((30,70),'PHASE F1 OCR LIVE TEST','black',font); img.save('/tmp/ocr.png')"

$ curl -F file=@/tmp/ocr.png -F display_name="P2 OCR live test" .../api/contexts/{cid}/documents
{"id":"a0e80f37-…","status":"extracted","extracted_chars":20}

$ curl .../api/contexts/{cid}/documents/a0e80f37-…
{"status":"extracted",
 "extracted_chars":20,
 "preview":"PHASE 1 OCRLIVE TEST",
 "extracted_text":"PHASE 1 OCRLIVE TEST"}
```

OCR recovers 4 of 5 word tokens (Tesseract dropped the "F" between PHASE/F1 and merged "OCR LIVE" → "OCRLIVE" — typical OCR noise at 48-pt resolution but the content is unambiguously recovered).

### Test coverage
- `test_p2_extract_text_png_ocr` — PNG with rendered text → at least 2 of 3 keywords recovered.
- `test_p2_extract_text_xlsx` — round-trip a 4-row workbook, asserts cell values + `[Sheet: …]` header appear.
- `test_p2_extract_text_csv` — UTF-8 CSV round-trip.
- `test_p2_extract_text_corrupted_image_graceful` — corrupted PNG returns `(text="", err="…")` without crashing.
- `test_p2_image_routing_does_not_crash_on_empty_image` — blank-white PNG → "no extractable text" hint.

---

## Tests + lint

| Metric | Before | After |
|---|---|---|
| pytest passing | 648 | **660** (+12 net new) |
| pytest skipped | 565 | 565 |
| Regressions | — | **0** |
| CI guard `test_no_direct_llm_calls_outside_shield` | PASS | **PASS** |
| ruff / pyflakes on touched files | clean | clean |
| ESLint on touched frontend files | clean | clean |
| `yarn render-smoke` (11 routes) | PASS | **PASS** |

### New tests in `tests/test_phase_f1_capability_gaps.py` (12 total)
P0 (2) + P1 (5) + P2 (5).

## File diff summary

```text
NEW backend
  tests/test_phase_f1_capability_gaps.py        +388 lines

MODIFIED backend
  documents_service.py                          +120 / -8 (OCR + XLSX + CSV extraction)
  routers/solva_phase_d.py                      +220 / -30 (anchor excerpt + attach-document endpoint)
  requirements.txt                              +pytesseract, +pillow_heif, +openpyxl

NEW frontend
  components/solva/AttachDocumentModal.jsx      +204 lines

MODIFIED frontend
  pages/SolvaPhaseDSession.jsx                  +118 / -5 (paperclip + attach modal wiring + anchor strip + confirmation)
```

## Carry-over (NOT IN THIS DISPATCH)

- **Dockerfile / production image** needs `apt-get install -y tesseract-ocr` to make the OCR path available in the deployed pod. Currently the pip-installed `pytesseract` binds to whatever `tesseract` binary is on PATH. Without it, OCR returns the graceful "no extractable text" hint but no text is ever recovered. **Surface to user before next prod deploy.**
- HEIC tests skipped — `pillow_heif` is installed but the test PNG fixture doesn't cover HEIC. Acceptance test should be added with a real HEIC fixture if Bank QA expects mobile-photo evidence.
- 16-May QA expansion product specs (Work Studio Document Overlay, "Work with Document" modal flow, Recents/Needs Attention rename, Add Contribution attachment picker, DOCJ tabs/badges) — **explicitly NOT touched in this dispatch per scope**.
- 14 deferred 15-May QA findings — explicitly NOT touched.
- Chunks 7-12 of the paused QA sprint — explicitly NOT resumed.
- Token-accurate Shield metering (Phase G+) — billing remains illustrative.

## Status

✅ **PHASE F.1 — closed (2026-05-18).** Three production gaps closed. Ready for the post-rewrite expansion sprint OR user-prioritised next-up.

**Next dispatch options** (see `POST_REWRITE_RAMP.md`):
1. **Resume Chunk 7** (Home + Document Journal fixes) — highest-priority unblocked item.
2. **16-May QA new product specs** (Work Studio Document Overlay etc.) — needs user prioritisation pass first.
3. **Bank-QA evidence pack assembly**.
