"""Phase W (2026-02 fork-resume) — Multi-tenant org list view for superadmin.

Read-only listing of all `contexts` (tenants) across every account
with member-count + doc-count + last-activity enrichments. Superadmin-
gated; bypasses the per-account membership filter at this layer ONLY.

The Synisense compartmentalization contract remains intact: this
router NEVER returns LLM responses, chat content, doc bodies, or
extracted text. Counts + last-activity timestamps only.

Endpoints:

    GET /api/admin/tenants?limit=50&q=...&type=...   — paginated list
    GET /api/admin/tenants/{cid}                      — drill-down detail
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account, sanitize_context


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/tenants", tags=["admin-tenants"])


async def _require_superadmin(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required.")
    return account


async def _member_counts_for(ctx_ids: List[str]) -> Dict[str, int]:
    if not ctx_ids:
        return {}
    out: Dict[str, int] = {}
    pipeline = [
        {"$match": {"context_id": {"$in": ctx_ids}}},
        {"$group": {"_id": "$context_id", "n": {"$sum": 1}}},
    ]
    async for r in db.memberships.aggregate(pipeline):
        out[r["_id"]] = int(r.get("n", 0))
    return out


async def _doc_counts_for(ctx_ids: List[str]) -> Dict[str, int]:
    if not ctx_ids:
        return {}
    out: Dict[str, int] = {}
    pipeline = [
        {"$match": {
            "context_id": {"$in": ctx_ids},
            "deleted_at": {"$exists": False},
        }},
        {"$group": {"_id": "$context_id", "n": {"$sum": 1}}},
    ]
    async for r in db.documents.aggregate(pipeline):
        out[r["_id"]] = int(r.get("n", 0))
    return out


async def _last_activity_for(ctx_ids: List[str]) -> Dict[str, Optional[str]]:
    """Return the most-recent `updated_at` across documents for each
    context. Cheap heuristic; cohort console handles richer signal."""
    if not ctx_ids:
        return {}
    out: Dict[str, Optional[str]] = {cid: None for cid in ctx_ids}
    pipeline = [
        {"$match": {"context_id": {"$in": ctx_ids}}},
        {"$group": {
            "_id": "$context_id",
            "last": {"$max": "$updated_at"},
        }},
    ]
    async for r in db.documents.aggregate(pipeline):
        out[r["_id"]] = r.get("last")
    return out


@router.get("")
async def list_tenants(
    limit: int = Query(default=50, ge=1, le=200),
    q: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """List every context in the system with summary enrichments.

    Filters:
      - `q`     case-insensitive substring match on context name
      - `type`  exact match on context.type
    """
    match: Dict[str, Any] = {}
    if q:
        match["name"] = {"$regex": q, "$options": "i"}
    if type:
        match["type"] = type

    total = await db.contexts.count_documents(match)
    cursor = (
        db.contexts.find(match, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)
    if not rows:
        return {"total": total, "items": []}

    ctx_ids = [r["id"] for r in rows if r.get("id")]
    members = await _member_counts_for(ctx_ids)
    docs = await _doc_counts_for(ctx_ids)
    last_act = await _last_activity_for(ctx_ids)

    items: List[Dict[str, Any]] = []
    for r in rows:
        cid = r["id"]
        s = sanitize_context(r)
        items.append({
            **s,
            "member_count":   members.get(cid, 0),
            "doc_count":      docs.get(cid, 0),
            "last_activity":  last_act.get(cid),
        })
    return {"total": total, "items": items}


@router.get("/{context_id}/extractions")
async def get_tenant_extractions(
    context_id: str,
    limit: int = Query(default=5, ge=1, le=50),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Phase W.followup.1 — Per-tenant extraction-activity panel feed.

    Returns the most-recent extraction runs for one tenant, shape-
    compatible with the global /api/admin/extractions endpoint so the
    frontend can reuse the OutcomeBadge component verbatim.
    """
    # Defer to the existing list endpoint by importing its helper —
    # simplest path with no duplication. We hand-roll the join here
    # to keep the dependency boundary clean.
    from routers.admin_extractions import _outcome  # local import avoids cycle

    rows_cursor = (
        db.extractions_log.find({"context_id": context_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    rows = await rows_cursor.to_list(length=limit)
    total = await db.extractions_log.count_documents({"context_id": context_id})

    if not rows:
        return {"total": total, "items": []}

    doc_ids = list({r.get("document_id") for r in rows if r.get("document_id")})
    docs_by_id: Dict[str, Dict[str, Any]] = {}
    if doc_ids:
        async for d in db.documents.find(
            {"id": {"$in": doc_ids}},
            {"_id": 0, "id": 1, "title": 1, "category": 1},
        ):
            docs_by_id[d["id"]] = d

    task_counts: Dict[str, int] = {}
    if doc_ids:
        pipeline = [
            {"$match": {
                "source_document_id": {"$in": doc_ids},
                "deleted_at": {"$exists": False},
            }},
            {"$group": {"_id": "$source_document_id", "n": {"$sum": 1}}},
        ]
        async for r in db.tasks_initiatives.aggregate(pipeline):
            task_counts[r["_id"]] = int(r.get("n", 0))

    items: List[Dict[str, Any]] = []
    for r in rows:
        doc_id = r.get("document_id")
        doc = docs_by_id.get(doc_id or "", {})
        items.append({
            "id":                 r.get("id"),
            "document_id":        doc_id,
            "document_title":     doc.get("title"),
            "document_category":  doc.get("category"),
            "context_id":         context_id,
            "kind":               r.get("kind"),
            "model":              r.get("model"),
            "count":              int(r.get("count", 0)),
            "failures":           int(r.get("failures", 0)),
            "tasks_persisted":    task_counts.get(doc_id or "", 0),
            "validation_outcome": _outcome(int(r.get("count", 0)), int(r.get("failures", 0))),
            "created_at":         r.get("created_at"),
        })
    return {"total": total, "items": items}


@router.get("/{context_id}")
async def get_tenant(
    context_id: str,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Read-only drill-down for a single tenant. Returns the
    sanitized context + enrichments + the list of memberships
    (account-id + role only — no payload content)."""
    ctx = await db.contexts.find_one({"id": context_id}, {"_id": 0})
    if not ctx:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    members_q = db.memberships.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "account_id": 1, "role": 1, "created_at": 1},
    )
    memberships = await members_q.to_list(length=500)
    doc_total = await db.documents.count_documents({
        "context_id": context_id,
        "deleted_at": {"$exists": False},
    })
    last_doc = await db.documents.find_one(
        {"context_id": context_id},
        {"_id": 0, "updated_at": 1},
        sort=[("updated_at", -1)],
    )
    return {
        **sanitize_context(ctx),
        "member_count":  len(memberships),
        "doc_count":     doc_total,
        "last_activity": (last_doc or {}).get("updated_at"),
        "memberships":   memberships,
    }
