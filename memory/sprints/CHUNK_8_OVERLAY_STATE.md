# Chunk 8 — Document Overlay state machine, schema migration, and library exception

**Date:** 2026-05-18
**Status:** Foundation for QA-2026-05-16-029 → -036 (8 IDs).

This document is the single reference for the Document Overlay
state machine and its backing schema. Future agents touching any
lifecycle / version / revision logic on Work Studio artefacts
MUST start here.

## 1. Lifecycle state machine

Every Work Studio artefact (row in `work_studio_exports`) carries
a `lifecycle_state` field with one of three values:

```
   ┌─────────┐  Move to review (owner-only)   ┌─────────────┐
   │  draft  │ ──────────────────────────────►│ in_review   │
   └────┬────┘                                 └──────┬──────┘
        │ Commit                                       │ Commit
        │                                              │
        ▼                                              ▼
   ┌──────────────────────────────────────────────────────┐
   │                     committed                          │
   │                  (immutable record)                    │
   └──────────────────────────────────────────────────────┘
                              │
                              │ Create New Version
                              ▼
                     ┌─────────────────┐
                     │  new draft row  │
                     │  (clone, no     │
                     │  links to       │
                     │  committed)     │
                     └─────────────────┘
```

### Transitions

| From | To | Trigger | Owner-only? |
|------|----|----|-------------|
| `draft` | `in_review` | "Move to review" button in toolbar (per Q1 decision 2026-05-18) | **Yes** |
| `draft` | `committed` | Commit button in toolbar + Commit Confirmation modal accepted | No (any editor) |
| `in_review` | `committed` | Commit button in toolbar + Commit Confirmation modal accepted | No (any reviewer) |
| `committed` | n/a | Read-only. To edit, "Create New Version" spawns a NEW row with `lifecycle_state=draft`. | n/a |

### Read-only enforcement
- When `lifecycle_state == "committed"`:
  - All edit endpoints (`PATCH /…/documents/{aid}`, `POST /…/save`, `POST /…/revise`) reject with HTTP 409 `Conflict`.
  - Frontend toolbar shows the Committed variant (Version History · Download · Create New Version).
  - The Document Surface (`-033`) renders read-only with a lock message.
  - The Intelligence Card (`-031`) remains visible and clickable but the underlying intelligence report is also frozen.

## 2. Schema migration (work_studio_exports)

Backward-compatible additive migration. No data loss. Idempotent.

Fields added to existing rows:

| Field | Type | Default for legacy rows | New rows |
|-------|------|--------------------------|----------|
| `lifecycle_state` | `Literal["draft","in_review","committed"]` | `"committed"` | `"draft"` |
| `legacy` | `bool` | `True` | `False` |
| `document_title` | `Optional[str]` | derived from `file_name` (strip `.docx`/`.pdf`/`.pptx`) or `name` | set at compile-time |
| `structured_content` | `Optional[Dict]` | `None` (read-only render of binary) | `{sections:[{heading,paragraphs:[]}]}` populated at compile-time |
| `source_document_ids` | `List[str]` | `[]` (revision blocked for legacy) | populated at compile-time |
| `intelligence_report` | `Optional[Dict]` | `None` (card shows "—") | populated at compile-time |

Migration script: `/app/backend/migrations/2026_05_18_chunk8_overlay.py` (idempotent).

### `intelligence_report` shape

```json
{
  "confidence_pct": 0..100,
  "period": "Q3 2025-26",
  "framing": "executive",
  "sources_count": 4,
  "pending_recommendations": 3,
  "sections": [
    {
      "heading": "Capital position",
      "confidence_pct": 0..100,
      "source_doc_ids": ["doc-..."],
      "attribution": "Synthesised from <doc names>"
    }
  ],
  "framing_analysis": "<paragraph>",
  "gaps": ["<bullet>", ...],
  "recommendations": [
    {"rank": 1, "text": "<bullet>", "addressed": false}
  ],
  "audit": {
    "generated_at": "<iso>",
    "generated_by": "<account_id>",
    "model_version": "<shield label>",
    "source_document_ids": ["doc-..."]
  }
}
```

### RAG thresholds (Q4 decision)

`confidence_pct ≥ 80` → green; `50 ≤ confidence_pct ≤ 79` → amber;
`confidence_pct < 50` → red. Applied identically to:
- Layer 2 Intelligence Card accent border (-031)
- Per-section confidence in the Intelligence modal (-032)
- Any sibling document-card surface that re-reads this field.

Helper: `backend/services/work_studio_overlay.rag_band(pct: int) -> Literal["green","amber","red"]`.

## 3. Version-snapshot collection

New MongoDB collection: `work_studio_artefact_versions`.

```json
{
  "id": "ver-<uuid>",
  "artefact_id": "<work_studio_exports id>",
  "context_id": "<ctx>",
  "account_id": "<account>",
  "saved_at": "<iso>",
  "saved_by": "<account_id>",
  "label": "Pre-commit" | "Auto-save" | "<user label>" | null,
  "structured_content_snapshot": { ... full doc shape at the moment of save ... },
  "document_title_snapshot": "<title at moment of save>",
  "lifecycle_state_snapshot": "draft" | "in_review",
  "pre_commit": false
}
```

- `Save` (toolbar) creates a snapshot with `label="Auto-save"` if triggered by the 30s autosave timer, otherwise the user-supplied label or `null`.
- Right before a Commit, a `pre_commit=true` snapshot is taken automatically with `label="Pre-commit"`. The Commit itself does NOT snapshot — committed state is the canonical record.
- Restore is allowed only when `lifecycle_state in (draft, in_review)`.

## 4. Library exception (Q5 decision)

`@tiptap/react` + `@tiptap/starter-kit` added to `frontend/package.json`.
These are the ONLY new third-party libraries permitted in Chunk 8.
No other tiptap extensions are added in this chunk. The version
is locked in `package.json` at first install. Future chunks may
add focused tiptap extensions (e.g. `@tiptap/extension-link` for
in-paragraph links) only with an explicit dispatch-level exception.

The "Edit" toggle on the subdued toolbar (per the Q5 mode-activation
divergence — see `qa_reports/QA_REPORT_16MAY2026.md#implementation-divergences-from-verbatim-qa-spec`)
gates tiptap's `editable` prop. The editor is read-only by default.

## 5. AI Revision source-document allowlist (-034)

`POST /api/contexts/{cid}/work-studio/documents/{aid}/revise`

Server-side enforcement:
1. Reject if `lifecycle_state == "committed"` (409).
2. Reject if `source_document_ids` is empty (412 — typically a legacy doc).
3. Validate the user instruction does NOT explicitly name any doc id outside the allowlist (substring scan of the instruction against all doc-ids in the context that are NOT in `source_document_ids`); reject 400 if a foreign id is named.
4. Shield invocation is constructed with `context_documents = source_document_ids` ONLY. No context-wide fallback.
5. Response surfaces a structured diff (`additions[]`, `deletions[]`, `unchanged[]`) at paragraph granularity.

Acceptance is client-driven: the user picks accept/reject per change; only on Apply does the new structured content land via the standard `PATCH /…/documents/{aid}` endpoint with the merged paragraph tree.

## 6. End-of-chunk audit checklist

- [ ] Migration ran cleanly on a fresh dump; existing rows have `lifecycle_state="committed", legacy=True`.
- [ ] No existing API endpoint regressed (export/enhance/download flows still 200).
- [ ] CI guard `test_no_direct_llm_calls_outside_shield` GREEN — the new revise endpoint goes through Shield.
- [ ] render-smoke 11/11 routes + new Chunk 8 step GREEN.
- [ ] Three modals (Intelligence / Version History / Commit Confirmation) close cleanly via X AND click-outside.
- [ ] Committed-state Document Surface is read-only — toolbar shows Create New Version + Version History + Download only; AI Revision endpoint returns 409.
