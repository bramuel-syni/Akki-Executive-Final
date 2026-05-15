"""Document Journal commentary service — single shared generator.

Phase 1 (2026-05-05). Both the live lazy-on-click path
(`POST /api/contexts/{cid}/documents/{did}/journal-commentary`) and the
backfill script (`backend/scripts/backfill_journal_commentary.py`) call
the same `generate_journal_commentary(...)` function so there is exactly
one code path that:

  1. Decides whether a doc is eligible (extracted text, not RESTRICTED,
     not `status=failed`).
  2. Calls the LLM through `llm_service.call_llm` with the
     "document_journal_commentary" module tag.
  3. Routes the LLM output through `services.synisense.pipeline.run`
     with `surface="journal_commentary"` (NOT `"briefing"` — the
     pre-Phase-1 live path was mis-labelling its Synisense runs and
     that is now fixed here, central to one place).
  4. Persists `journal_commentary`, `journal_commentary_redacted`,
     `journal_commentary_synisense_version`,
     `journal_commentary_generated_at` on the document row.
  5. Writes an audit log entry.

The function is a pure async coroutine. It returns one of three result
shapes — `{"status": "generated", ...}`, `{"status": "skipped",
"reason": ...}`, or raises `CommentaryGenerationError` — so the caller
can handle each case explicitly.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core import db, iso, now, write_audit


# Words to keep the prompt within. Mirrors the brief.
_PROMPT_WORDS = "350-450"

# Sensitivity bands that must NOT be sent to an LLM. Today only
# `restricted` is hard-blocked; `confidential` is allowed because the
# Work Studio review path treats those as "approved for AKKI summary,
# not for external share". This matches the policy implicit in
# `studio_sensitivity.py`.
_RESTRICTED_BANDS = {"restricted"}

# Doc statuses we refuse to summarise — extraction failed or the doc
# is empty. Keeps the LLM bill honest and prevents AKKI from inventing
# context where there is none.
_SKIPPABLE_STATUSES = {"failed", "empty"}

_MAX_BODY_CHARS = 6000


class CommentaryGenerationError(Exception):
    """Raised for non-skip failures: empty LLM response, LLM exception,
    Synisense pipeline error. Skips (band-restricted, no body, already
    cached) come back as a `{"status": "skipped", ...}` dict instead so
    the caller can keep walking the corpus."""


async def generate_journal_commentary(
    *,
    doc: Dict[str, Any],
    account_id: str,
    refresh: bool = False,
    record_audit: bool = True,
) -> Dict[str, Any]:
    """Generate (or return cached) Akki commentary on a single document.

    Parameters
    ----------
    doc
        The full document row (must include `id`, `context_id`,
        `extracted_text` or empty, `name`/`title`, `status`,
        `sensitivity_band`).
    account_id
        Account id attributed in the audit log + Synisense run row.
    refresh
        When True, re-runs generation even if `journal_commentary`
        already exists. The lazy-on-click endpoint exposes this via
        `?refresh=true`.
    record_audit
        Defaults True. Backfill caller can set False for high-volume
        idempotent runs to keep the audit log lean — but the live path
        always records.

    Returns
    -------
    {"status": "generated", "commentary": str, "synisense_version": int,
     "generated_at": str, "redacted": str}
    {"status": "cached", "commentary": str, "synisense_version": int,
     "generated_at": str, "redacted": str}
    {"status": "skipped", "reason": str}
    """
    doc_id = doc["id"]
    context_id = doc["context_id"]

    # ─── Eligibility guards ────────────────────────────────────────
    if doc.get("journal_commentary") and not refresh:
        return {
            "status": "cached",
            "commentary": doc["journal_commentary"],
            "redacted": doc.get("journal_commentary_redacted")
                        or doc["journal_commentary"],
            "synisense_version": doc.get("journal_commentary_synisense_version", 0),
            "generated_at": doc.get("journal_commentary_generated_at"),
        }

    body = (doc.get("extracted_text") or "")[:_MAX_BODY_CHARS]
    if not body.strip():
        return {"status": "skipped", "reason": "no_extracted_text"}

    if (doc.get("status") or "").lower() in _SKIPPABLE_STATUSES:
        return {"status": "skipped", "reason": f"doc_status={doc.get('status')}"}

    band = (doc.get("sensitivity_band") or "").lower()
    if band in _RESTRICTED_BANDS:
        return {"status": "skipped", "reason": f"sensitivity_band={band}"}

    # ─── Generate ──────────────────────────────────────────────────
    title = doc.get("name") or doc.get("title") or "Untitled"
    system = (
        "You are Akki, an analytical co-pilot for board directors. Your "
        "voice is Financial Times: dry, specific, plain. Never editorial. "
        "Always grounded in the document. When evidence is thin, say so."
    )
    user = (
        f"Document: {title}\n"
        f"Type: {doc.get('doc_kind') or doc.get('doc_type') or 'general'}\n\n"
        f"Write a {_PROMPT_WORDS} word commentary on this document for the "
        "board. Cover: what it claims, what is conspicuously absent, the "
        "two or three points that warrant follow-up, and how it sits "
        "against the strategic context. No headlines. Reference passages "
        "inline where you cite them.\n\n"
        f"=== DOCUMENT ===\n\n{body}\n"
    )

    # Imported lazily to avoid pulling the whole LLM stack at module
    # import time (the backfill script may be invoked from a
    # bare-bones Python entry point).
    from llm_service import call_llm

    try:
        llm_resp = await call_llm(
            module="document_journal_commentary",
            user_query=user,
            system_override=system,
            session_context={
                "context_id": context_id,
                "account_id": account_id,
            },
            tier="standard",
            # Phase C (2026-05-13) — explicit Shield purpose so the
            # audit row carries per-call-site provenance.
            purpose="document_journal.commentary.generate",
        )
    except Exception as exc:  # noqa: BLE001
        raise CommentaryGenerationError(f"LLM commentary failed: {exc}") from exc

    commentary = (llm_resp.get("response") if isinstance(llm_resp, dict) else "") or ""
    commentary = commentary.strip()
    if not commentary:
        raise CommentaryGenerationError("LLM returned empty commentary")

    # ─── Synisense Shield — surface=journal_commentary ─────────────
    # The pre-Phase-1 live path used `surface="briefing"` which logged
    # the run against the wrong audit bucket. Phase 1 fixes that. All
    # journal-commentary Synisense runs (live + backfill) now land in
    # `synisense_runs` with surface="journal_commentary".
    from services.synisense import pipeline as synisense_pipeline

    try:
        syn_out = await synisense_pipeline.run(
            commentary,
            context_id=context_id,
            surface="journal_commentary",
            mode="redact",
            account_id=account_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise CommentaryGenerationError(
            f"Synisense pipeline failed: {exc}"
        ) from exc

    new_version = (doc.get("journal_commentary_synisense_version") or 0) + 1
    generated_at = iso(now())
    update = {
        "journal_commentary": commentary,
        "journal_commentary_redacted": syn_out.get("redacted_text") or commentary,
        "journal_commentary_synisense_version": new_version,
        "journal_commentary_generated_at": generated_at,
        "updated_at": generated_at,
    }
    await db.documents.update_one({"id": doc_id}, {"$set": update})

    if record_audit:
        await write_audit(
            context_id, account_id, "document.journal_commentary_generated",
            "document", doc_id, {"synisense_version": new_version},
        )

    return {
        "status": "generated",
        "commentary": commentary,
        "redacted": update["journal_commentary_redacted"],
        "synisense_version": new_version,
        "generated_at": generated_at,
    }


async def is_eligible(doc: Dict[str, Any]) -> Optional[str]:
    """Pre-flight eligibility check used by the backfill summary.

    Returns None if the doc is eligible, or a string reason ("no_extracted_text",
    "doc_status=failed", "sensitivity_band=restricted", "already_cached") if not.
    """
    if doc.get("journal_commentary"):
        return "already_cached"
    if not (doc.get("extracted_text") or "").strip():
        return "no_extracted_text"
    if (doc.get("status") or "").lower() in _SKIPPABLE_STATUSES:
        return f"doc_status={doc.get('status')}"
    band = (doc.get("sensitivity_band") or "").lower()
    if band in _RESTRICTED_BANDS:
        return f"sensitivity_band={band}"
    return None
