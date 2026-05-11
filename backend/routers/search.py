"""Phase F0 — Universal Search router.

Endpoints
---------
- GET  /api/search                — federated search across the caller's memberships
- POST /api/search/cross-context-open — write the audit row when the user
                                       confirms a switch-and-open from a
                                       foreign-context search result. The
                                       SPA still calls the existing
                                       /api/me/active-context endpoint to
                                       perform the switch itself.

Privacy & audit
---------------
- We hash the query (`q_hash = SHA-256(q.strip().lower())`) and store
  ONLY the hash on the audit row. Raw `q` is never persisted.
- `db.audit_log.action` is reused (the canonical audit field is `action`,
  not `event_type`). Values used:
    "search.federated"
    "search.cross_context_open"
  The caller-facing spec names ("event_type") map to this `action` field.
- Every per-context query is scoped via the caller's active-status
  memberships fetched once at the top of the handler. Foreign tenants
  are never iterated.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from core import db, get_current_account, write_audit
from services.universal_search import SURFACE_HANDLERS, run_federated_search

router = APIRouter(prefix="/api", tags=["search"])

# Hard caps — keep the dispatcher latency bounded.
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 25
_PER_CONTEXT_LIMIT = 25


def _q_hash(q: str) -> str:
    """SHA-256 of the normalised query. Stored in audit; raw q is not."""
    return hashlib.sha256((q or "").strip().lower().encode("utf-8")).hexdigest()


async def _resolve_memberships(account_id: str) -> List[Dict[str, Any]]:
    """Return the caller's active memberships, joined with the context
    name. Output rows are `{context_id, context_name, role}`."""
    mships = await db.memberships.find(
        {"account_id": account_id, "status": "active"},
        {"_id": 0, "context_id": 1, "role": 1, "sub_role": 1},
    ).to_list(500)
    if not mships:
        return []
    ids = [m["context_id"] for m in mships]
    contexts = await db.contexts.find(
        {"id": {"$in": ids}},
        {"_id": 0, "id": 1, "name": 1},
    ).to_list(500)
    cmap = {c["id"]: c.get("name") or "(unnamed)" for c in contexts}
    return [
        {
            "context_id": m["context_id"],
            "context_name": cmap.get(m["context_id"], "(unnamed)"),
            "role": m.get("role"),
            "sub_role": m.get("sub_role"),
        }
        for m in mships
        if m["context_id"] in cmap  # drop dangling memberships
    ]


# ---------------------------------------------------------------------------
# GET /api/search
# ---------------------------------------------------------------------------
@router.get("/search")
async def federated_search(
    q: str = Query(..., min_length=2, max_length=200,
                   description="Search query. Min 2 chars, max 200."),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT,
                       description="Max results returned (after federation)."),
    context_id: Optional[str] = Query(
        None,
        description="Optional — restrict search to a single context. "
                    "If omitted, federates across all the caller's "
                    "active memberships.",
    ),
    surface: Optional[str] = Query(
        None,
        description="Optional — restrict to a single surface "
                    "(documents|chats|pulse|monitor|cycle|work_studio|briefs).",
    ),
    offset: int = Query(0, ge=0, le=10_000,
                        description="Pagination offset for the full results page."),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    needle = q.strip()
    if len(needle) < 2:
        raise HTTPException(
            status_code=400,
            detail={"code": "Q_TOO_SHORT", "message": "Query must be at least 2 characters."},
        )

    memberships = await _resolve_memberships(current["id"])
    # Optional scoping — single-context. We refuse silently for any
    # context the caller is NOT a member of (no enumeration leak).
    if context_id:
        memberships = [m for m in memberships if m["context_id"] == context_id]

    surfaces: Optional[List[str]] = None
    if surface:
        if surface not in SURFACE_HANDLERS:
            raise HTTPException(
                status_code=400,
                detail={"code": "BAD_SURFACE", "message": f"Unknown surface '{surface}'."},
            )
        surfaces = [surface]

    t0 = time.monotonic()
    fed = await run_federated_search(
        db,
        account_id=current["id"],
        q=needle,
        memberships=memberships,
        surfaces=surfaces,
        per_context_limit=_PER_CONTEXT_LIMIT,
    )
    total = len(fed["results"])
    sliced = fed["results"][offset: offset + limit]
    # Strip internal `_score` before sending.
    public_results = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in sliced
    ]
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    # Audit — ONE row per call. Raw q never stored.
    await write_audit(
        context_id=None,         # federated — no single context
        account_id=current["id"],
        action="search.federated",
        resource_type="search",
        resource_id=None,
        metadata={
            "q_hash": _q_hash(needle),
            "q_len": len(needle),
            "contexts_searched": [m["context_id"] for m in memberships],
            "scope_context_id": context_id,
            "surface_filter": surface,
            "result_counts": {
                "total": total,
                "per_context": fed["per_context"],
                "per_surface": fed["per_surface"],
            },
            "latency_ms": elapsed_ms,
            "limit": limit,
            "offset": offset,
        },
    )

    return {
        "query": needle,
        "total": total,
        "results": public_results,
        "per_context": fed["per_context"],
        "per_surface": fed["per_surface"],
        "latency_ms": elapsed_ms,
    }


# ---------------------------------------------------------------------------
# POST /api/search/cross-context-open
# ---------------------------------------------------------------------------
@router.post("/search/cross-context-open")
async def cross_context_open(
    body: Dict[str, Any] = Body(...),
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Write an audit row immediately BEFORE the SPA performs a
    cross-context switch-and-open from a search result.

    The actual context switch is still performed by the existing
    POST /api/me/active-context endpoint; this endpoint exists only to
    record the cross-context-open event with both context_ids and the
    surface/result_id pair.
    """
    from_cid = (body or {}).get("from_context_id")
    to_cid = (body or {}).get("to_context_id")
    surface = (body or {}).get("surface")
    result_id = (body or {}).get("result_id")
    if not (to_cid and surface and result_id):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MISSING_FIELDS",
                "message": "to_context_id, surface, and result_id are required.",
            },
        )

    # Verify the caller is actually a member of the destination context.
    # Refuse otherwise so the audit row can't be forged for foreign
    # tenants.
    is_member = await db.memberships.find_one(
        {"account_id": current["id"], "context_id": to_cid, "status": "active"},
        {"_id": 0, "context_id": 1},
    )
    if not is_member:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_A_MEMBER", "message": "Not a member of the destination context."},
        )

    result_id_hash = hashlib.sha256(str(result_id).encode("utf-8")).hexdigest()
    await write_audit(
        context_id=to_cid,           # the destination — auditor view of the new tenant
        account_id=current["id"],
        action="search.cross_context_open",
        resource_type="search",
        resource_id=None,
        metadata={
            "from_context_id": from_cid,
            "to_context_id": to_cid,
            "surface": surface,
            "result_id_hash": result_id_hash,
        },
    )
    return {"ok": True, "from_context_id": from_cid, "to_context_id": to_cid}
