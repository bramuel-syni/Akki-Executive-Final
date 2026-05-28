"""AA.followup.4 (2026-02 fork-resume) — Extraction Activity superadmin view.

Read-only listing of recent LLM-extraction runs from
`db.extractions_log`. Joins against `db.documents` (title + category)
and against `db.tasks_initiatives` (per-doc task count) to surface a
single rich row per run.

Endpoint (superadmin-gated):

    GET /api/admin/extractions?limit=50&since=...&kind=...

Response shape:

    {
        "total":   int,                  # total matching rows
        "items":   [
            {
                "id":                str,
                "document_id":       str,
                "document_title":    str | null,
                "document_category": str | null,
                "context_id":        str,
                "kind":              "goals" | "tasks",
                "model":             str | null,
                "count":             int,       # validated rows persisted
                "failures":          int,       # validation failures
                "tasks_persisted":   int,       # live tasks from this doc
                "validation_outcome": "all_passed" | "partial" | "all_failed",
                "created_at":        str (iso),
            },
            ...
        ]
    }
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/extractions", tags=["admin-extractions"])


async def _require_superadmin(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required.")
    return account


def _outcome(count: int, failures: int) -> str:
    if count > 0 and failures == 0:
        return "all_passed"
    if count > 0 and failures > 0:
        return "partial"
    if count == 0 and failures > 0:
        return "all_failed"
    return "all_passed"  # nothing extracted, nothing failed — clean run


@router.get("")
async def list_extractions(
    limit: int = Query(default=50, ge=1, le=200),
    kind: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None),
    tenant_id: Optional[str] = Query(default=None),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """List the most-recent extraction runs, newest first.

    Filters:
      - `kind`       ∈ {"goals", "tasks"} → only that kind
      - `since`      ISO datetime         → only created_at >= since
      - `tenant_id`  context_id           → only runs for that tenant
                                            (Phase W.followup.1)
    """
    match: Dict[str, Any] = {}
    if kind:
        if kind not in ("goals", "tasks"):
            raise HTTPException(status_code=400, detail="kind must be goals or tasks")
        match["kind"] = kind
    if since:
        # ISO-string comparison works because we store strict ISO-8601
        # with timezone in `created_at`.
        match["created_at"] = {"$gte": since}
    if tenant_id:
        match["context_id"] = tenant_id

    total = await db.extractions_log.count_documents(match)
    cursor = (
        db.extractions_log.find(match, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )

    rows = await cursor.to_list(length=limit)
    if not rows:
        return {"total": total, "items": []}

    # Batch the document join — pull doc titles + categories in one query.
    doc_ids = list({r.get("document_id") for r in rows if r.get("document_id")})
    docs_by_id: Dict[str, Dict[str, Any]] = {}
    if doc_ids:
        async for d in db.documents.find(
            {"id": {"$in": doc_ids}},
            {"_id": 0, "id": 1, "title": 1, "category": 1},
        ):
            docs_by_id[d["id"]] = d

    # Per-doc task count (only counts active rows — soft-deleted excluded).
    task_counts: Dict[str, int] = {}
    if doc_ids:
        pipeline = [
            {"$match": {
                "source_document_id": {"$in": doc_ids},
                "deleted_at": {"$exists": False},
            }},
            {"$group": {"_id": "$source_document_id", "n": {"$sum": 1}}},
        ]
        async for row in db.tasks_initiatives.aggregate(pipeline):
            task_counts[row["_id"]] = int(row.get("n", 0))

    items: List[Dict[str, Any]] = []
    for r in rows:
        doc_id = r.get("document_id")
        doc = docs_by_id.get(doc_id or "", {})
        items.append({
            "id":                 r.get("id"),
            "document_id":        doc_id,
            "document_title":     doc.get("title"),
            "document_category":  doc.get("category"),
            "context_id":         r.get("context_id"),
            "kind":               r.get("kind"),
            "model":              r.get("model"),
            "count":              int(r.get("count", 0)),
            "failures":           int(r.get("failures", 0)),
            "tasks_persisted":    task_counts.get(doc_id or "", 0),
            "validation_outcome": _outcome(int(r.get("count", 0)), int(r.get("failures", 0))),
            "created_at":         r.get("created_at"),
        })

    return {"total": total, "items": items}
