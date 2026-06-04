"""Track A Phase 1 (2026-06-03) — Analysis lifecycle service.

Helpers for the new `Analysis` entity (see `models.analysis`).
Phase 1 covers:
  • Create an Analysis row from a multi-file upload payload.
  • Session-close hook: delete blobs in `analysis_blobs`, mark the
    Analysis sources `blob_purged=True`, and append a
    "session-close" entry to `refresh_history`.

Phase 2 will add the read-side adapter for the UI; Phase 3 will
populate `observations[]` via Solva v2 narration; Phase 4 will
add the multi-version semantics. None of those land in Phase 1.
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from models.analysis import (
    Analysis,
    AnalysisRefreshEntry,
    AnalysisSource,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def build_analysis_from_uploads(
    *,
    account_id: str,
    context_id: str,
    title: str,
    files: List[Tuple[str, bytes, str]],
    objective: str = "",
) -> Tuple[Analysis, List[Dict[str, Any]]]:
    """Create a draft Analysis from 1+ uploaded files.

    `files`: list of `(filename, raw_bytes, file_format)` where
    `file_format ∈ {"xlsx", "csv"}`. The blobs are returned as a
    SEPARATE list of dicts ready to insert into `analysis_blobs`;
    the Analysis itself only carries the source refs (no bytes).

    `objective`: optional text the user typed at the top of the
    drawer (Track A Phase 2, 2026-06-04).

    Returns: (Analysis instance, list of analysis_blobs documents).
    """
    if not files:
        raise ValueError("at_least_one_file_required")
    if not context_id:
        raise ValueError("context_id_required")

    analysis_id = _new_id("ana")
    sources: List[AnalysisSource] = []
    blob_docs: List[Dict[str, Any]] = []
    for (fname, raw, fmt) in files:
        source_id = _new_id("src")
        sources.append(AnalysisSource(
            source_id=source_id,
            filename=fname,
            file_format=fmt,  # type: ignore[arg-type]
            file_size_bytes=len(raw),
        ))
        blob_docs.append({
            "analysis_id": analysis_id,
            "source_id": source_id,
            "account_id": account_id,
            "context_id": context_id,
            "filename": fname,
            "file_format": fmt,
            "data_b64": base64.b64encode(raw).decode("ascii"),
            "created_at": _iso_now(),
        })

    analysis = Analysis(
        id=analysis_id,
        account_id=account_id,
        context_id=context_id,
        title=title,
        objective=objective,
        sources=sources,
        refresh_history=[
            AnalysisRefreshEntry(
                refresh_id=_new_id("rf"),
                triggered_by="upload",
                note=f"Initial upload of {len(sources)} file(s)",
            ),
        ],
    )
    return analysis, blob_docs


async def session_close(db, *, analysis_id: str, account_id: str, context_id: str) -> Dict[str, Any]:
    """Delete blobs in `analysis_blobs` scoped to this Analysis,
    mark sources `blob_purged=True`, append a session-close
    refresh-history row. Idempotent on re-run.

    Returns the touched Analysis row (sanitized; no _id).
    Returns None if the analysis doesn't exist or belongs to
    another tenant.
    """
    row = await db.analyses.find_one(
        {"id": analysis_id, "account_id": account_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        return None

    # Delete blobs scoped to this analysis.
    del_result = await db.analysis_blobs.delete_many({
        "analysis_id": analysis_id,
        "account_id": account_id,
    })

    # Mark sources purged + append refresh-history row.
    purged_count = del_result.deleted_count
    refresh_id = _new_id("rf")
    refresh_row = {
        "refresh_id": refresh_id,
        "ran_at": _iso_now(),
        "triggered_by": "session-close",
        "note": f"Purged {purged_count} blob(s)",
    }
    await db.analyses.update_one(
        {"id": analysis_id, "account_id": account_id, "context_id": context_id},
        {
            "$set": {
                "updated_at": _iso_now(),
                "sources.$[].blob_purged": True,
                "status": "purged",
            },
            "$push": {"refresh_history": refresh_row},
        },
    )
    fresh = await db.analyses.find_one(
        {"id": analysis_id, "account_id": account_id, "context_id": context_id},
        {"_id": 0},
    )
    return fresh


__all__ = [
    "build_analysis_from_uploads",
    "session_close",
]
