# Autonomous-mode Decisions Log

This log records orchestrator-delegated autonomous decisions made by the
agent without per-task user approval. Each entry includes the trigger,
the decision, the rationale, and the reversal path so the orchestrator
can re-direct on return.

---

## 2026-05-26 — E.3 scope compliance authorized under autonomous mode

- **Trigger:** User delegated autonomous control with the standing rule
  *"Ensure scope compliance now, unless it compromises system or
  journey."* Original dispatch surfaced as the orchestrator scope-
  compliance brief returned right after Phase E.3 initial report.
- **Decision:** Authorize all 3 scope cuts to close in the same pass:
  1. Prompt-based edit apply pipeline (Shield-bounded LLM rewrite + diff
     preview).
  2. DRAFT watermark embed for PDF / DOCX / PPTX exports (ratify the
     dormant `watermark_service.py`; flip the export-guard from
     unconditional block to conditional pass-with-watermark + block-on-
     failure fallback).
  3. Related-docs typing (4 buckets — metadata_match, content_similarity,
     explicit_attachment gap, canonical_lineage gap — surface gaps
     honestly).
- **Rationale:** Each of the 3 cuts is spec-explicit in the original
  E.3 brief. None compromise system invariants:
  - All LLM calls still route through Shield (`shield_invoke`); no
    `emergentintegrations` direct import added.
  - Watermark libs (`reportlab`, `pypdf`, `python-docx`, `python-pptx`)
    are already in `requirements.txt` — no new packages.
  - Blocking remains the spec-compliant fallback path when watermarking
    fails (HTTP 503 with `code=DRAFT_WATERMARK_FAILED`).
- **Reversal:** User can override any of the 3 on return; each cut is
  independent. To revert any item, see the surgical-diff anchors in the
  HOME_CLEANUP_LOG.md "E.3 — scope compliance" subsection.
- **Surface:** orchestrator message dispatching scope-compliance closure.

