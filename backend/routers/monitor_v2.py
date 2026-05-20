"""
routers/monitor_v2.py — Patch 5 Monitor v2 (Objectives & Projects).

CRUD endpoints under `/api/contexts/{cid}/monitor/...` for the new
`objectives` and `projects` collections, plus auto-suggest endpoints
that surface candidates from existing cycles + Solva sessions.

All RAG fields are deterministic. No LLM.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso as _iso, now as _now, require_context_membership


router = APIRouter(prefix="/api")


_RAG = ("red", "amber", "green", "not_started", "achieved")
_TREND = ("up", "flat", "down")
_SOURCE = ("auto", "manual", "hybrid")
_KIND = ("objective", "project")


# Chunk 6.5-REVISED Task F (2026-05-13) — canonical owner-role list.
# These are the labels surfaced as tabs in the Monitor Owner filter.
# Matching against `accounts.declared_role` is **case-insensitive**;
# anything not in this list (and any null) collapses into "Other" on
# the frontend. Order is the locked product order — do not re-sort.
#
# PO-18 (open clarification): `declared_role` on accounts uses values
# like `executive`/`ned`/`reportee`/`dual`. None of those literally
# equal "CEO"/"CFO"/... so in practice today most items fall under
# "Other". The owner-roles endpoint will return what's actually in
# the data so the frontend renders the right tabs once the field
# semantics are resolved.
CANONICAL_OWNER_ROLES: tuple[str, ...] = (
    "CEO", "CFO", "COO", "CCO", "CTO", "CRO", "CIO",
    "Audit Committee", "Risk Committee",
)
_CANONICAL_LOWERS: dict[str, str] = {r.lower(): r for r in CANONICAL_OWNER_ROLES}


def _canonical_owner_role(raw: Optional[str]) -> Optional[str]:
    """Map a raw `accounts.declared_role` value to a canonical role
    label. Returns the canonical TitleCase form when matched,
    otherwise None (the frontend buckets it under 'Other')."""
    if not raw:
        return None
    return _CANONICAL_LOWERS.get(str(raw).strip().lower())


def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    rec = dict(rec)
    rec.pop("_id", None)
    return rec


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class ObjectiveIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    owner_account_id: Optional[str] = None
    shared_with: List[str] = Field(default_factory=list)
    # QA-2026-05-16-047 (2026-05-18) — manual creation defaults to
    # `not_started` (was `green`). Manual override is gone from the
    # UI; Akki assigns red/amber/green/achieved on Update-status.
    rag_status: Literal["red", "amber", "green", "not_started", "achieved"] = "not_started"
    score: int = Field(default=0, ge=0, le=100)
    trend: Literal["up", "flat", "down"] = "flat"
    source: Literal["auto", "manual", "hybrid"] = "manual"
    source_refs: List[Dict[str, Any]] = Field(default_factory=list)


class ProjectIn(ObjectiveIn):
    objective_id: Optional[str] = None
    timeline_events: List[Dict[str, Any]] = Field(default_factory=list)


def _coll(kind: str):
    return db.objectives if kind == "objective" else db.projects


def _model(kind: str):
    return ObjectiveIn if kind == "objective" else ProjectIn


# -----------------------------------------------------------------------------
# Auto-suggest — surface candidate objectives/projects from existing data.
# (Declared BEFORE the generic /{kind} routes so FastAPI matches the
# specific paths first.)
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/monitor/auto-suggest-objectives")
async def auto_suggest_objectives(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Suggest objectives derived from active cycles and Solva sessions.

    QA-2026-05-16-046 — filter out candidates whose source cycle/session
    is already represented in the existing objectives collection (i.e.
    a previous accept-suggestion already minted an objective from that
    source). Pre-fix, refetching after accept always returned the same
    suggestion because the seeding loop didn't know what had been
    materialised.
    """
    # Pull source-ref keys for already-accepted objectives so we can
    # filter the candidate list.
    accepted_keys = set()
    async for row in _coll("objective").find(
        {"context_id": context_id, "deleted_at": {"$exists": False}},
        {"_id": 0, "source_refs": 1},
    ):
        for ref in (row.get("source_refs") or []):
            kind = ref.get("kind")
            rid = ref.get("id")
            if kind and rid:
                accepted_keys.add(f"{kind}:{rid}")

    candidates: List[Dict[str, Any]] = []
    async for c in db.cycles.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "readiness_pct": 1},
    ).limit(20):
        if f"cycle:{c['id']}" in accepted_keys:
            continue
        readiness = c.get("readiness_pct") or 0
        rag = "green" if readiness >= 80 else "amber" if readiness >= 40 else "red"
        candidates.append({
            "kind": "objective",
            "source": "auto",
            "title": c.get("title") or "Untitled agenda",
            "source_refs": [{"kind": "cycle", "id": c["id"]}],
            "rag_status": rag,
            "score": readiness,
        })
    async for s in db.solva_sessions.find(
        {"context_id": context_id, "status": {"$in": ["complete", "draft"]}},
        {"_id": 0, "id": 1, "topic": 1, "status": 1},
    ).limit(10):
        if not s.get("topic"):
            continue
        if f"solva_session:{s['id']}" in accepted_keys:
            continue
        candidates.append({
            "kind": "objective",
            "source": "auto",
            "title": f"Investigate: {s.get('topic')}",
            "source_refs": [{"kind": "solva_session", "id": s["id"]}],
            "rag_status": "amber",
            "score": 50,
        })
    return {"items": candidates}


@router.get("/contexts/{context_id}/monitor/auto-suggest-projects")
async def auto_suggest_projects(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Suggest projects from active cycles.

    QA-2026-05-16-046 — see auto_suggest_objectives for the dedup
    pattern; identical logic against the `project` collection.
    """
    accepted_keys = set()
    async for row in _coll("project").find(
        {"context_id": context_id, "deleted_at": {"$exists": False}},
        {"_id": 0, "source_refs": 1},
    ):
        for ref in (row.get("source_refs") or []):
            kind = ref.get("kind")
            rid = ref.get("id")
            if kind and rid:
                accepted_keys.add(f"{kind}:{rid}")

    candidates: List[Dict[str, Any]] = []
    async for c in db.cycles.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "readiness_pct": 1},
    ).limit(20):
        if f"cycle:{c['id']}" in accepted_keys:
            continue
        readiness = c.get("readiness_pct") or 0
        rag = "green" if readiness >= 80 else "amber" if readiness >= 40 else "red"
        candidates.append({
            "kind": "project",
            "source": "auto",
            "title": c.get("title") or "Untitled agenda",
            "source_refs": [{"kind": "cycle", "id": c["id"]}],
            "rag_status": rag,
            "score": readiness,
        })
    return {"items": candidates}


# -----------------------------------------------------------------------------
# Owner-roles aggregator — Chunk 6.5-REVISED Task F (2026-05-13).
#
# Declared BEFORE the generic /monitor/{kind} route so FastAPI matches
# the specific path first (without this ordering the literal
# `/monitor/owner-roles` would be captured by `kind=owner-roles` and
# 400 from the `_KIND` validation).
#
# Returns the distinct list of `owner_role` values currently present
# in this context's objectives + projects, with counts per role.
# Frontend uses this to populate the tab strip without having to
# fetch the full list of items first.
#
# Response shape:
#   {
#     "total": int,
#     "roles": [
#       {"role": "CEO",   "count": 4},
#       {"role": "Audit Committee", "count": 1},
#       {"role": "Other", "count": 3},   ← anything not in the canonical list
#       ...
#     ]
#   }
#
# Strict context scoping; no cross-context leakage.
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/monitor/owner-roles")
async def list_owner_role_counts(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    counts: Dict[str, int] = {}
    total = 0
    for kind in _KIND:
        pipeline: List[Dict[str, Any]] = [
            {"$match": {"context_id": context_id, "deleted_at": {"$exists": False}}},
            {
                "$lookup": {
                    "from": "accounts",
                    "localField": "owner_account_id",
                    "foreignField": "id",
                    "as": "_owner",
                }
            },
            {
                "$addFields": {
                    "_decl": {
                        "$let": {
                            "vars": {"first": {"$arrayElemAt": ["$_owner", 0]}},
                            "in": {
                                "$cond": [
                                    {"$ifNull": ["$$first.declared_role", False]},
                                    "$$first.declared_role",
                                    None,
                                ]
                            },
                        }
                    }
                }
            },
            {"$group": {"_id": "$_decl", "n": {"$sum": 1}}},
        ]
        async for row in _coll(kind).aggregate(pipeline):
            raw = row.get("_id")
            canonical = _canonical_owner_role(raw)
            bucket = canonical if canonical else "Other"
            counts[bucket] = counts.get(bucket, 0) + int(row.get("n", 0))
            total += int(row.get("n", 0))

    # Always emit canonical roles in their locked order, then Other
    # last. Roles with zero count are omitted (the frontend will not
    # render a tab for them).
    ordered: List[Dict[str, Any]] = []
    for r in CANONICAL_OWNER_ROLES:
        n = counts.get(r, 0)
        if n > 0:
            ordered.append({"role": r, "count": n})
    if counts.get("Other", 0) > 0:
        ordered.append({"role": "Other", "count": counts["Other"]})
    return {"total": total, "roles": ordered}


# -----------------------------------------------------------------------------
# CRUD — shared shape across objectives and projects.
#
# Chunk 6.5-REVISED Task F (2026-05-13): switched from `find()` to an
# aggregation pipeline that `$lookup`s `db.accounts` against
# `owner_account_id` and projects `accounts.declared_role` onto each
# item as `owner_role`. The frontend's owner-tab strip filters on this
# field. When the lookup yields no match (owner_account_id is null or
# the account row is gone), `owner_role` is set to null — the item
# falls under the "Other" tab on the frontend.
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/monitor/{kind}")
async def list_items(
    context_id: str,
    kind: str,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    owner_role: Optional[str] = None,
    page: int = 1,
    page_size: int = 5,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    page = max(1, int(page or 1))
    page_size = max(1, min(50, int(page_size or 5)))
    match: Dict[str, Any] = {"context_id": context_id, "deleted_at": {"$exists": False}}
    if status:
        if status not in _RAG and status != "all":
            raise HTTPException(status_code=400, detail="Unknown status.")
        if status != "all":
            match["rag_status"] = status
    if owner:
        match["owner_account_id"] = owner

    # Aggregation pipeline:
    #   1) $match the base context+kind filters.
    #   2) $lookup the owner account row (to read declared_role).
    #   3) Project owner_role from declared_role; strip _id and the
    #      heavy joined doc array.
    #   4) Apply owner_role filter (if any) AFTER the lookup since the
    #      field doesn't exist on the source documents.
    #   5) Sort, skip, limit.
    pipeline: List[Dict[str, Any]] = [
        {"$match": match},
        {
            "$lookup": {
                "from": "accounts",
                "localField": "owner_account_id",
                "foreignField": "id",
                "as": "_owner",
            }
        },
        {
            "$addFields": {
                "owner_role": {
                    "$let": {
                        "vars": {"first": {"$arrayElemAt": ["$_owner", 0]}},
                        "in": {
                            "$cond": [
                                {"$ifNull": ["$$first.declared_role", False]},
                                "$$first.declared_role",
                                None,
                            ]
                        },
                    }
                }
            }
        },
        {"$project": {"_id": 0, "_owner": 0}},
    ]
    # owner_role filter — accepts canonical TitleCase forms ("CEO",
    # "Audit Committee") plus the special sentinel "__other__" which
    # matches items whose owner_role is null OR not in the canonical
    # list. Case-insensitive on the canonical match.
    if owner_role:
        if owner_role == "__other__":
            canonical_lowers = [r.lower() for r in CANONICAL_OWNER_ROLES]
            pipeline.append({
                "$match": {
                    "$expr": {
                        "$or": [
                            {"$eq": ["$owner_role", None]},
                            {"$not": {"$in": [
                                {"$toLower": {"$ifNull": ["$owner_role", ""]}},
                                canonical_lowers,
                            ]}},
                        ]
                    }
                }
            })
        else:
            # Case-insensitive equality on the raw stored value.
            ci_target = owner_role.strip().lower()
            pipeline.append({
                "$match": {
                    "$expr": {
                        "$eq": [{"$toLower": {"$ifNull": ["$owner_role", ""]}}, ci_target]
                    }
                }
            })

    # Total count for this filter set (re-runs the pipeline with $count).
    total_pipeline = list(pipeline) + [{"$count": "n"}]
    total_cursor = _coll(kind).aggregate(total_pipeline)
    total_doc = await total_cursor.to_list(1)
    total = (total_doc[0]["n"] if total_doc else 0)

    # QA-2026-05-16-045 — status_counts for the tab badges.
    #
    # The Monitor tab strip (All · At Risk · On Track · Off Track ·
    # Achieved · Not Started) needs a count per status. We compute it
    # OFF the lookup+owner_role-filtered pipeline (i.e. status_counts
    # honour every active filter EXCEPT the status filter itself, so
    # switching tabs doesn't re-shuffle counts).
    #
    # Build the counter pipeline by stripping the rag_status match
    # (it's only present when `status` was passed) and aggregating on
    # the resulting rows.
    counter_match = {k: v for k, v in match.items() if k != "rag_status"}
    counter_pipeline: List[Dict[str, Any]] = [{"$match": counter_match}]
    # Carry the same $lookup + $addFields + $project so the owner_role
    # filter applies identically. Skip the trailing $sort/$skip/$limit.
    for stage in pipeline:
        if "$match" in stage and stage["$match"] is match:
            continue   # already handled
        if "$sort" in stage or "$skip" in stage or "$limit" in stage:
            continue
        counter_pipeline.append(stage)
    counter_pipeline.append({"$group": {"_id": "$rag_status", "n": {"$sum": 1}}})
    status_counts: Dict[str, int] = {s: 0 for s in _RAG}
    status_counts["all"] = 0
    async for row in _coll(kind).aggregate(counter_pipeline):
        bucket = row.get("_id")
        n = int(row.get("n", 0))
        status_counts["all"] += n
        if bucket in status_counts:
            status_counts[bucket] = n

    pipeline += [
        {"$sort": {"score": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
    ]
    items = [_sanitize(r) async for r in _coll(kind).aggregate(pipeline)]
    return {
        "kind": kind,
        "items": items,
        "total": total,
        "status_counts": status_counts,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


@router.post("/contexts/{context_id}/monitor/{kind}")
async def create_item(
    context_id: str,
    kind: str,
    body: dict,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    parsed = _model(kind)(**body)
    now = _now()
    rec: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "created_at": _iso(now),
        "updated_at": _iso(now),
        **parsed.model_dump(),
    }
    await _coll(kind).insert_one(rec.copy())
    return _sanitize(rec)


@router.get("/contexts/{context_id}/monitor/{kind}/{rid}")
async def get_item(
    context_id: str,
    kind: str,
    rid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    rec = await _coll(kind).find_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Not found.")
    return _sanitize(rec)


@router.patch("/contexts/{context_id}/monitor/{kind}/{rid}")
async def update_item(
    context_id: str,
    kind: str,
    rid: str,
    body: dict,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    body.pop("id", None); body.pop("context_id", None); body.pop("_id", None)
    body["updated_at"] = _iso(_now())
    res = await _coll(kind).update_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"$set": body},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found.")
    rec = await _coll(kind).find_one({"id": rid, "context_id": context_id}, {"_id": 0})
    return _sanitize(rec)


@router.delete("/contexts/{context_id}/monitor/{kind}/{rid}")
async def delete_item(
    context_id: str,
    kind: str,
    rid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if kind not in _KIND:
        raise HTTPException(status_code=400, detail="Unknown kind.")
    res = await _coll(kind).update_one(
        {"id": rid, "context_id": context_id, "deleted_at": {"$exists": False}},
        {"$set": {"deleted_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found.")
    return {"ok": True}


# -----------------------------------------------------------------------------
# (Auto-suggest endpoints moved above the CRUD block so FastAPI matches
# their specific paths before the generic /{kind} pattern.)
# -----------------------------------------------------------------------------
