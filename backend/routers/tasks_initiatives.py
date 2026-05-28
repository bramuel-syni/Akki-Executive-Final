"""
Phase AA-slice-1 (2026-05-27) — `tasks_initiatives` data model + CRUD.

A new Mongo collection that backs Phase AA (Monitor v2). Holds the
"tasks / initiatives" that ladder up under strategic goals — separate
from the legacy `strategic_goals.initiatives_count` integer field
(which stays as-is for now; reconciliation filed as Z.followup.6).

Schema
------
Every row carries:

  id                   uuid hex (unique)
  context_id           FK → contexts.id (required, indexed)
  title                string 2-180 chars (required)
  body                 string ≤ 4000 chars (optional markdown / plaintext)
  category             enum reused from goals
                       (revenue|customer|product|people|operations|compliance)
  owner_role           enum  (CEO|CFO|COO|CRO|CTO|CHRO|CMO|CIO|OTHER) | null
  parent_objective_id  FK → strategic_goals.id (nullable; tasks can be
                       standalone — e.g. a director's individual
                       initiative outside a board goal)
  status               on_track | at_risk | off_track | achieved
                       | not_started
  performance_score    int 0-100
  probability_score    int 0-100
  last_reassessed_at   ISO datetime (auto-set on create + on PATCH)
  source_document_id   FK → documents.id (set when LLM-extracted)
  extracted_by         "llm" | "manual"
  status_active        bool — soft-delete tombstone flag (DELETE flips
                       it to False; reads filter `status_active != False`)
  created_at           ISO datetime
  updated_at           ISO datetime

Indexes (built at startup via `ensure_indexes()`):
  (id) unique
  (context_id, parent_objective_id)
  (context_id, owner_role)
  (context_id, status)
  (context_id, source_document_id)

CRUD surface
------------
  GET    /api/contexts/{cid}/tasks-initiatives
         ?owner=X&status=Y&parent_objective_id=Z&search=Q
         &page=N&page_size=M
  GET    /api/contexts/{cid}/tasks-initiatives/{id}
  POST   /api/contexts/{cid}/tasks-initiatives
  PATCH  /api/contexts/{cid}/tasks-initiatives/{id}
  DELETE /api/contexts/{cid}/tasks-initiatives/{id}  (soft-delete)

All endpoints require context membership + return JSON-safe dicts
(`_id` stripped, ObjectId never leaves the data layer).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, conint

from core import db, iso as _iso, now as _now, require_context_membership, write_audit


logger = logging.getLogger("akki.tasks_initiatives")
router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────
# Enums — locked
# ─────────────────────────────────────────────────────────────────

# Reuse the `goals` Category enum verbatim per the AA-slice-1 spec.
TICategory = Literal[
    "revenue", "customer", "product", "people", "operations", "compliance",
]

# Phase AA spec — canonical owner role tokens. NULLable column (a task
# may belong to a function that hasn't been declared, or be cross-
# functional). The monitor_v2 router still references an older 7-token
# tuple — reconciliation filed as `AA.followup.1` (do not change here).
TIOwnerRole = Literal[
    "CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER",
]

TIStatus = Literal[
    "on_track", "at_risk", "off_track", "achieved", "not_started",
]

TIExtractedBy = Literal["llm", "manual"]


# ─────────────────────────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────────────────────────


class TaskInitiativeIn(BaseModel):
    """Manual-create payload (POST). LLM extraction (AA-slice-2) writes
    rows directly without going through this schema."""

    title: str = Field(..., min_length=2, max_length=180)
    body: Optional[str] = Field(default=None, max_length=4000)
    category: TICategory = "operations"
    owner_role: Optional[TIOwnerRole] = None
    parent_objective_id: Optional[str] = Field(default=None, max_length=64)
    status: TIStatus = "not_started"
    performance_score: conint(ge=0, le=100) = 0
    probability_score: conint(ge=0, le=100) = 0
    source_document_id: Optional[str] = Field(default=None, max_length=64)


class TaskInitiativePatch(BaseModel):
    """Partial-update payload (PATCH). Every field is optional; only
    keys present in the body get applied. `updated_at` +
    `last_reassessed_at` are always refreshed server-side."""

    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    body: Optional[str] = Field(default=None, max_length=4000)
    category: Optional[TICategory] = None
    owner_role: Optional[TIOwnerRole] = None
    parent_objective_id: Optional[str] = Field(default=None, max_length=64)
    status: Optional[TIStatus] = None
    performance_score: Optional[conint(ge=0, le=100)] = None
    probability_score: Optional[conint(ge=0, le=100)] = None
    # NB: `source_document_id` + `extracted_by` are immutable post-
    # create. Trying to mutate them via PATCH is a silent no-op
    # (caller must DELETE + re-create).


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────


def _strip(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Drop Mongo internals before the row leaves the data layer."""
    if d is None:
        return None
    out = dict(d)
    out.pop("_id", None)
    return out


async def _validate_parent_objective(context_id: str, oid: Optional[str]) -> None:
    """Reject `parent_objective_id` pointing at a goal that doesn't
    live in this context (or doesn't exist). Null is allowed —
    standalone tasks have no parent.
    """
    if oid is None:
        return
    g = await db.strategic_goals.find_one(
        {"id": oid, "context_id": context_id},
        {"_id": 0, "id": 1},
    )
    if g is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"parent_objective_id={oid!r} does not reference a "
                f"strategic goal in this context."
            ),
        )


async def _validate_source_document(context_id: str, did: Optional[str]) -> None:
    """Reject `source_document_id` pointing at a doc that doesn't
    live in this context (or doesn't exist). Null is allowed — manual-
    create tasks have no source.
    """
    if did is None:
        return
    d = await db.documents.find_one(
        {"id": did, "context_id": context_id},
        {"_id": 0, "id": 1},
    )
    if d is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"source_document_id={did!r} does not reference a "
                f"document in this context."
            ),
        )


# ─────────────────────────────────────────────────────────────────
# Startup index setup
# ─────────────────────────────────────────────────────────────────


async def ensure_indexes() -> None:
    """Idempotent — call from `server.py` startup. Same pattern as the
    other routers' index helpers."""
    coll = db.tasks_initiatives
    await coll.create_index("id", unique=True)
    await coll.create_index([("context_id", 1), ("parent_objective_id", 1)])
    await coll.create_index([("context_id", 1), ("owner_role", 1)])
    await coll.create_index([("context_id", 1), ("status", 1)])
    await coll.create_index([("context_id", 1), ("source_document_id", 1)])
    # Soft-delete filter — every read filters `status_active != False`,
    # so a compound index across that and context_id keeps the hot path
    # O(log N).
    await coll.create_index([("context_id", 1), ("status_active", 1), ("updated_at", -1)])


# ─────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────


@router.get("/contexts/{context_id}/tasks-initiatives")
async def list_tasks_initiatives(
    context_id: str,
    owner: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    parent_objective_id: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: conint(ge=1) = Query(default=1),
    page_size: conint(ge=1, le=200) = Query(default=50),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Paginated list of tasks/initiatives for this context.

    Filters:
      - `owner`               → owner_role exact match (or `"null"` for
                                unassigned rows).
      - `status`              → status enum exact match.
      - `parent_objective_id` → returns ONLY rows under this goal
                                (or `"null"` for standalone rows).
      - `search`              → case-insensitive substring on `title`.

    Pagination:
      - Default page_size 50; capped at 200.

    Response:
      `{rows: [...], page, page_size, total}`
    """
    q: Dict[str, Any] = {
        "context_id": context_id,
        # Soft-deleted rows hidden by default; status_active==False or
        # status_active==null both qualify as deleted.
        "$or": [{"status_active": {"$ne": False}}],
    }

    if owner is not None:
        q["owner_role"] = None if owner.lower() == "null" else owner
    if status is not None:
        # 422 cleanly on bogus values — we'd rather refuse the query
        # than silently return everything.
        if status not in (
            "on_track", "at_risk", "off_track", "achieved", "not_started",
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Unknown status={status!r}. Expected one of "
                f"on_track|at_risk|off_track|achieved|not_started.",
            )
        q["status"] = status
    if parent_objective_id is not None:
        q["parent_objective_id"] = (
            None if parent_objective_id.lower() == "null"
            else parent_objective_id
        )
    if search:
        # $regex with case-insensitive flag. The `(?i)` inline form is
        # honoured by Mongo; keeps the query simple.
        q["title"] = {"$regex": search, "$options": "i"}

    total = await db.tasks_initiatives.count_documents(q)
    skip = (page - 1) * page_size
    cursor = (
        db.tasks_initiatives.find(q, {"_id": 0})
        .sort("updated_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    rows = [_strip(r) async for r in cursor]
    return {
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/contexts/{context_id}/tasks-initiatives/{ti_id}")
async def get_task_initiative(
    context_id: str,
    ti_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.tasks_initiatives.find_one(
        {
            "id": ti_id,
            "context_id": context_id,
            "status_active": {"$ne": False},
        },
        {"_id": 0},
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Task / initiative not found.")
    return _strip(row)


@router.post("/contexts/{context_id}/tasks-initiatives")
async def create_task_initiative(
    context_id: str,
    body: TaskInitiativeIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Manual create. LLM-extracted rows are written directly by
    AA-slice-2 (the extraction service) so they can carry
    `extracted_by="llm"` + the source_document_id. Manual creates
    always carry `extracted_by="manual"`.
    """
    await _validate_parent_objective(context_id, body.parent_objective_id)
    await _validate_source_document(context_id, body.source_document_id)

    now_iso = _iso(_now())
    row = {
        "id":                  uuid.uuid4().hex,
        "context_id":          context_id,
        "title":               body.title.strip(),
        "body":                (body.body or "").strip() or None,
        "category":            body.category,
        "owner_role":          body.owner_role,
        "parent_objective_id": body.parent_objective_id,
        "status":              body.status,
        "performance_score":   int(body.performance_score),
        "probability_score":   int(body.probability_score),
        "last_reassessed_at":  now_iso,
        "source_document_id":  body.source_document_id,
        "extracted_by":        "manual",
        "status_active":       True,
        "created_at":          now_iso,
        "updated_at":          now_iso,
    }
    # `insert_one` mutates the doc to add `_id`; strip it before we
    # echo back to the caller (MongoDB rule).
    await db.tasks_initiatives.insert_one(row)
    row.pop("_id", None)

    await write_audit(
        context_id, ctx["account"]["id"],
        "tasks_initiative.create",
        "tasks_initiative", row["id"],
        {"title": row["title"], "owner_role": row["owner_role"],
         "category": row["category"]},
    )
    return row


@router.patch("/contexts/{context_id}/tasks-initiatives/{ti_id}")
async def patch_task_initiative(
    context_id: str,
    ti_id: str,
    body: TaskInitiativePatch,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Partial update. `updated_at` + `last_reassessed_at` always
    refreshed server-side. Immutable fields (`extracted_by`,
    `source_document_id`) are silently ignored even if the caller
    smuggles them in — those fields belong to the create path only.
    """
    existing = await db.tasks_initiatives.find_one(
        {
            "id": ti_id,
            "context_id": context_id,
            "status_active": {"$ne": False},
        },
        {"_id": 0},
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Task / initiative not found.")

    payload = body.model_dump(exclude_unset=True)
    if "parent_objective_id" in payload:
        await _validate_parent_objective(context_id, payload["parent_objective_id"])

    if "title" in payload and isinstance(payload["title"], str):
        payload["title"] = payload["title"].strip()
    if "body" in payload:
        raw = (payload["body"] or "").strip()
        payload["body"] = raw or None

    now_iso = _iso(_now())
    payload["updated_at"] = now_iso
    payload["last_reassessed_at"] = now_iso

    await db.tasks_initiatives.update_one(
        {"id": ti_id, "context_id": context_id},
        {"$set": payload},
    )

    await write_audit(
        context_id, ctx["account"]["id"],
        "tasks_initiative.patch",
        "tasks_initiative", ti_id,
        {"fields": sorted(k for k in payload.keys() if k not in ("updated_at", "last_reassessed_at"))},
    )

    row = await db.tasks_initiatives.find_one(
        {"id": ti_id, "context_id": context_id},
        {"_id": 0},
    )
    return _strip(row)


@router.delete("/contexts/{context_id}/tasks-initiatives/{ti_id}")
async def delete_task_initiative(
    context_id: str,
    ti_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Soft-delete — flips `status_active` to False + writes an audit
    row. The collection is never physically purged (cohort retention
    + legal hold).
    """
    existing = await db.tasks_initiatives.find_one(
        {
            "id": ti_id,
            "context_id": context_id,
            "status_active": {"$ne": False},
        },
        {"_id": 0, "id": 1, "title": 1},
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Task / initiative not found.")

    now_iso = _iso(_now())
    await db.tasks_initiatives.update_one(
        {"id": ti_id, "context_id": context_id},
        {"$set": {"status_active": False, "updated_at": now_iso}},
    )

    await write_audit(
        context_id, ctx["account"]["id"],
        "tasks_initiative.delete",
        "tasks_initiative", ti_id,
        {"title": existing.get("title")},
    )
    return {"ok": True, "id": ti_id, "deleted_at": now_iso}


# ─────────────────────────────────────────────────────────────────
# AA-slice-3 (2026-05-27) — Trigger endpoint
# Spawns the AA-slice-2 extraction service in a BackgroundTask so
# the upload modal can return 202 instantly while Sonnet 4.5 chews
# on the document body in the background.
# ─────────────────────────────────────────────────────────────────


class ExtractTriggerIn(BaseModel):
    extract_goals: bool = False
    extract_tasks: bool = True
    force: bool = False


async def _bg_extract(
    document_id: str, context_id: str, account_id: str,
    extract_goals: bool, extract_tasks: bool, force: bool,
) -> None:
    """Background driver — silently swallows exceptions (they're
    auditable via `extraction_failures`) so a fault inside the LLM
    pipe never crashes the worker process."""
    try:
        from services.tasks_initiatives.extraction import extract_from_document
        await extract_from_document(
            document_id, context_id, account_id,
            extract_goals=extract_goals,
            extract_tasks=extract_tasks,
            force=force,
        )
    except Exception as e:
        logger.warning(
            "[aa3.trigger] extract_from_document doc=%s ctx=%s failed: %s",
            document_id, context_id, e,
        )


@router.post("/contexts/{context_id}/documents/{doc_id}/extract", status_code=202)
async def trigger_extraction(
    context_id: str,
    doc_id: str,
    body: ExtractTriggerIn,
    bg: BackgroundTasks,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Spawn LLM extraction for this document. Returns 202 Accepted
    immediately; the actual extraction happens in the background.
    Caller can verify completion later via the `extractions_log`
    collection or by polling the target collections.
    """
    if not body.extract_goals and not body.extract_tasks:
        # No-op trigger; surface a 400 so the caller knows the call
        # was meaningless rather than silently 202-ing.
        raise HTTPException(
            status_code=400,
            detail="At least one of extract_goals / extract_tasks must be True.",
        )

    doc = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id},
        {"_id": 0, "id": 1, "extracted_text": 1},
    )
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found in this context.",
        )
    has_text = bool((doc.get("extracted_text") or "").strip())

    # Best-effort audit row — the actual extraction outcome is logged
    # by the service into `extractions_log`.
    await write_audit(
        context_id, ctx["account"]["id"],
        "tasks_initiative.extract_triggered",
        "document", doc_id,
        {"extract_goals": body.extract_goals, "extract_tasks": body.extract_tasks,
         "force": body.force, "has_text": has_text},
    )

    bg.add_task(
        _bg_extract, doc_id, context_id, ctx["account"]["id"],
        body.extract_goals, body.extract_tasks, body.force,
    )
    return {
        "extraction_queued": True,
        "document_id":       doc_id,
        "extract_goals":     body.extract_goals,
        "extract_tasks":     body.extract_tasks,
        "has_extracted_text": has_text,
    }
