"""
Phase C.2 — Work Studio Brief enhance/revision endpoints.

  POST /api/work_studio/briefs/{brief_id}/enhance
  GET  /api/work_studio/briefs/{brief_id}
  GET  /api/work_studio/briefs/{brief_id}/revisions
  GET  /api/work_studio/briefs/{brief_id}/revisions/{revision_id}/diff
  POST /api/work_studio/briefs/{brief_id}/set_active

Operates on the structured Brief snapshot persisted by C.1's first
export. C.1's renderers stay the source of truth for binary output —
this module never produces a binary; it produces a NEW revision row
in `db.work_studio_brief_revisions` that the user can later export via
the C.1 endpoint passing `revision_id=<this row's id>`.

Refused revisions are persisted (so the user can inspect the diff and
the validator's reason) but `set_active` cannot point at them.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account
from work_studio import (
    enhance_brief_two_pass,
    compute_section_diff,
    get_brief, get_revision, get_active_revision, list_revisions,
    insert_revision, set_active_revision,
)

router = APIRouter(prefix="/api/work_studio/briefs", tags=["work_studio_c2"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class EnhanceRequest(BaseModel):
    instruction: str = Field(..., min_length=4, max_length=2000)
    scope: str = Field(
        "whole_brief",
        description="whole_brief | recommendations | exec_summary | section:<id>",
    )
    base_revision_id: Optional[str] = Field(
        None,
        description="Revision to enhance from. Defaults to active.",
    )


class SetActiveRequest(BaseModel):
    revision_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _load_parent_brief_or_404(brief_id: str, account):
    parent = await get_brief(db, brief_id, account["id"])
    if not parent:
        raise HTTPException(status_code=404, detail="brief_not_found")
    return parent


async def _load_revision_or_404(brief_id: str, revision_id: str, account):
    rev = await get_revision(
        db, brief_id=brief_id, revision_id=revision_id, account_id=account["id"],
    )
    if not rev:
        raise HTTPException(status_code=404, detail="revision_not_found")
    return rev


def _validate_scope(scope: str) -> None:
    if scope in {"whole_brief", "recommendations", "exec_summary"}:
        return
    if scope.startswith("section:") and len(scope) > len("section:"):
        return
    raise HTTPException(status_code=422, detail={
        "code": "invalid_scope",
        "message": "scope must be one of: whole_brief, recommendations, "
                   "exec_summary, or section:<section_id>",
    })


# ---------------------------------------------------------------------------
# GET /api/work_studio/briefs/{brief_id}
# ---------------------------------------------------------------------------
@router.get("/{brief_id}")
async def get_brief_meta(
    brief_id: str,
    account=Depends(get_current_account),
):
    parent = await _load_parent_brief_or_404(brief_id, account)
    active = await get_active_revision(
        db, brief_id=brief_id, account_id=account["id"],
    )
    return {
        "brief": parent,
        "active_revision": active,
    }


# ---------------------------------------------------------------------------
# GET /api/work_studio/briefs/{brief_id}/revisions
# ---------------------------------------------------------------------------
@router.get("/{brief_id}/revisions")
async def list_brief_revisions(
    brief_id: str,
    account=Depends(get_current_account),
):
    await _load_parent_brief_or_404(brief_id, account)
    revs = await list_revisions(
        db, brief_id=brief_id, account_id=account["id"],
    )
    return {
        "brief_id": brief_id,
        "count": len(revs),
        "items": revs,
    }


# ---------------------------------------------------------------------------
# GET /api/work_studio/briefs/{brief_id}/revisions/{revision_id}/diff?against=...
# ---------------------------------------------------------------------------
@router.get("/{brief_id}/revisions/{revision_id}/diff")
async def diff_brief_revision(
    brief_id: str,
    revision_id: str,
    against: Optional[str] = None,
    account=Depends(get_current_account),
):
    """Diff `revision_id` (the right-hand side) against `against`
    (the left-hand side, defaults to revision's parent_revision_id, or
    the original revision_0 if `revision_id` is the original)."""
    rev = await _load_revision_or_404(brief_id, revision_id, account)
    base_id = against or rev.get("parent_revision_id")
    if not base_id:
        # Diffing the original against itself yields an empty diff.
        return {
            "brief_id": brief_id,
            "left": None,
            "right": revision_id,
            "diff": [],
        }
    base = await _load_revision_or_404(brief_id, base_id, account)
    diff = compute_section_diff(
        base.get("snapshot") or {}, rev.get("snapshot") or {},
    )
    return {
        "brief_id": brief_id,
        "left": base_id,
        "right": revision_id,
        "diff": diff,
    }


# ---------------------------------------------------------------------------
# POST /api/work_studio/briefs/{brief_id}/enhance
# ---------------------------------------------------------------------------
@router.post("/{brief_id}/enhance")
async def enhance_brief(
    brief_id: str,
    body: EnhanceRequest,
    account=Depends(get_current_account),
    x_active_context: Optional[str] = Header(None, alias="X-Active-Context"),
):
    parent = await _load_parent_brief_or_404(brief_id, account)
    _validate_scope(body.scope)

    base_revision_id = body.base_revision_id or parent["active_revision_id"]
    base_rev = await _load_revision_or_404(brief_id, base_revision_id, account)
    base_snapshot = base_rev.get("snapshot") or {}
    if not base_snapshot:
        raise HTTPException(
            status_code=409,
            detail={"code": "base_revision_empty",
                    "message": "Base revision has no snapshot to enhance."},
        )

    # Run the two-pass.
    result = await enhance_brief_two_pass(
        parent_snapshot=base_snapshot,
        instruction=body.instruction,
        scope=body.scope,
        account_id=account["id"],
        context_id=x_active_context,
        brief_id=brief_id,
    )
    revised_snapshot = result["revised_snapshot"]
    diff = compute_section_diff(base_snapshot, revised_snapshot)

    new_rev = await insert_revision(
        db,
        brief_id=brief_id,
        account_id=account["id"],
        context_id=x_active_context,
        parent_revision_id=base_revision_id,
        instruction=body.instruction,
        scope=body.scope,
        snapshot=revised_snapshot,
        diff=diff,
        claims_changed=result["claims_changed"],
        claims_added_without_citation=result["claims_added_without_citation"],
        validation=result["validation"],
        llm_audit=result["llm_audit"],
    )

    return {
        "brief_id": brief_id,
        "revision_id": new_rev["id"],
        "parent_revision_id": base_revision_id,
        "instruction": body.instruction,
        "scope": body.scope,
        "diff": diff,
        "claims_changed": result["claims_changed"],
        "claims_added_without_citation": result["claims_added_without_citation"],
        "validation": result["validation"],
        "drafter_refused": result["drafter_refused"],
        "set_active": False,   # never auto-promote — user must opt in
    }


# ---------------------------------------------------------------------------
# POST /api/work_studio/briefs/{brief_id}/set_active
# ---------------------------------------------------------------------------
@router.post("/{brief_id}/set_active")
async def set_active(
    brief_id: str,
    body: SetActiveRequest,
    account=Depends(get_current_account),
):
    await _load_parent_brief_or_404(brief_id, account)
    rev = await _load_revision_or_404(brief_id, body.revision_id, account)
    if (rev.get("validation") or {}).get("verdict") == "refused":
        raise HTTPException(
            status_code=409,
            detail={"code": "revision_refused",
                    "message": "This revision was refused by the validator and "
                               "cannot be set active. Inspect the diff and try a "
                               "different instruction."},
        )
    ok = await set_active_revision(
        db, brief_id=brief_id, revision_id=body.revision_id,
        account_id=account["id"],
    )
    if not ok:
        raise HTTPException(
            status_code=500,
            detail={"code": "set_active_failed",
                    "message": "Could not update active revision."},
        )
    return {
        "brief_id": brief_id,
        "active_revision_id": body.revision_id,
        "status": "ok",
    }
