# Work Studio Export — Template Schemas (Phase C.2)

The Work Studio export pipeline (`backend/services/work_studio_export.py`) is
**deterministic-template-first** per D-002. Templates are constructed
programmatically using `python-docx` (Brief / Report → DOCX) and
`python-pptx` (Summary Deck → PPTX). PDF output is produced from a
parallel Jinja HTML template rendered with WeasyPrint. All four kinds
of output share the same `content_dict` schema per artefact kind.

The same input always produces the same output bytes (deterministic).

## Common envelope (every kind)

```jsonc
{
  // Header / cover page
  "title":           "string, max 140 chars",
  "subtitle":        "string, max 200 chars (optional)",
  "classification":  "Public|Internal|Confidential|Restricted",
  "period":          "string — e.g. 'Q1 2026' or 'Apr–Jun 2026'",
  "generated_for":   "string — context name",

  // Required first-page content
  "executive_summary": "string — 80-180 words, single paragraph",

  // Body sections — kind-specific (see below)
  "sections": [ … ],

  // Citation manifest — every footnote/cite reference must point at
  // an entry in this list. The renderer fails the export if a citation
  // references a doc_id absent from this manifest (no fabrication).
  "citations": [
    {
      "doc_id":           "uuid",
      "doc_name":         "string",
      "paragraph_anchor": "string|null"
    }
  ]
}
```

## Brief (`brief`)

Document layout (DOCX):
- Cover page — title, subtitle, classification chip, period, generated_for.
- Executive summary — first body page; one tight paragraph.
- Body sections — heading + 1-3 prose paragraphs + optional pull-quote +
  in-line cite footnotes.
- Appendix — citation manifest enumerated in `[1]…[n]` order.

`sections[i]` shape (Brief):
```jsonc
{
  "heading":     "string — one short clause",
  "paragraphs":  ["string", "string"],     // 1-3 paragraphs
  "pullquote":   "string|null",            // optional 1-line emphasis
  "cites":       [int]                     // 1-based indices into citations[]
}
```

## Summary Deck (`deck`)

Slide layout (PPTX):
- Slide 1 — Title (title, classification, period, generated_for).
- Slide 2 — One-line executive summary.
- Slides 3..N — Body slides (one per `sections[]` entry).
- Slide N+1 — Conclusion (single paragraph).
- Slide N+2 — Sources (citation manifest enumerated `[1]…[n]`).

`sections[i]` shape (Deck):
```jsonc
{
  "heading":  "string — slide title",
  "bullets":  ["string", "string", "string"],   // 3-5 prose bullets
  "callout":  "string|null",                    // optional emphasised one-liner
  "cites":    [int]                             // indices into citations[]
}
```

The `executive_summary` envelope key serves Slide 2.
The `conclusion` top-level key (string) serves Slide N+1; if absent the
renderer derives a single sentence from the executive summary.

## Report (`report`)

Heavier than Brief. Document layout (DOCX):
- Cover page — same envelope.
- Executive summary.
- Index — auto-generated bullet list of `sections[].heading` values
  (in document order; renderer-built, not LLM-supplied).
- Body sections — multi-paragraph prose with sub-headings.
- Evidence — citation manifest with one-line per-source rationale lifted
  from `sections[].cites`.
- Recommendations — block of `recommendations[]` (1-5 items).

`sections[i]` shape (Report — extended):
```jsonc
{
  "heading":      "string",
  "subheading":   "string|null",
  "paragraphs":   ["string", "string", …],     // 2-5 paragraphs
  "pullquote":    "string|null",
  "cites":        [int]
}
```

Top-level extras (Report only):
```jsonc
{
  "recommendations": ["string", "string", …]   // 1-5 items
}
```

## Constants

- `BANNED_WORDS` — sourced from `backend/services/two_pass.py` (memo Item 8
  OPERATING PREFERENCES + WEBSITE_BRIEF_V3 §1.3, deduped). Hits in the
  rendered file write a `work_studio.export.voice_violation` audit row.
- Typography — Calibri (sans, headings & chrome), Georgia (serif, body).
- Colour — Cream `#F7F3EA` page chrome; Ink `#0A1F44` headings; Oxblood
  `#8B2E2B` for the classification chip.
