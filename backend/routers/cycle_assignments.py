"""Cycle Manager — Brief assignment handoff to NED(s).

Implements the ASSIGNMENT HANDOFF model locked in
/app/memory/sprints/CYCLE_MANAGER_BRIEF.md §3.3.

Five state transitions:

  1. Submit  → POST /api/contexts/{cid}/cycles/{cycle_id}/briefs/{bid}/submit-for-board
  2. Assign  → POST /api/contexts/{cid}/cycles/{cycle_id}/briefs/{bid}/assignments
  3. NED inbox → GET /api/ned/inbox/assignments
  4. Accept  → POST /api/ned/assignments/{aid}/accept
  5. Decline → POST /api/ned/assignments/{aid}/decline

Permissions for (1) and (2): see services/cycle_permissions.can_submit_for_board.

Privacy Wall enforcement for (3), (4):
  • NED inbox returns ONLY a strict whitelist of fields. No Exec-internal
    metadata is included at any point in the read pipeline.
  • Accept ingests ONLY the approved Brief artefact (via brief_id → render
    on demand). Agenda metadata, contribution metadata, scoring rationale,
    cycle_team rows are NEVER copied into NED collections.

Collections owned here:
  db.cycle_assignments  — one row per (brief, ned).

Auxiliary fields written on db.work_studio_briefs.board_status:
  null | "draft" | "submitted" | "shipped"
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now, require_context_membership, write_audit
from services.cycle_permissions import (
    can_submit_for_board,
    permission_reason,
    workspace_kind,
)

logger = logging.getLogger("akki.cycle_assignments")

router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────
class SubmitForBoardOut(BaseModel):
    brief_id: str
    board_status: str
    submitted_at: str
    submitter_account_id: str


class AssignmentCreateIn(BaseModel):
    ned_ids: Optional[List[str]] = Field(default=None, max_length=64)
    cohort_id: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=600)


class AssignmentOut(BaseModel):
    id: str
    brief_id: str
    cycle_id: str
    context_id: str
    ned_id: str
    submitter_account_id: str
    submitter_display_name: str
    cycle_title: str
    submitted_at: str
    note: Optional[str] = None
    cohort_id: Optional[str] = None
    cohort_label: Optional[str] = None
    status: str  # pending | accepted | declined | cancelled
    created_at: str
    updated_at: str
    accepted_at: Optional[str] = None
    declined_at: Optional[str] = None
    decline_reason: Optional[str] = None


class NedInboxItemOut(BaseModel):
    """STRICT whitelist for the NED inbox surface.

    NO Exec-internal fields. Adding a field here requires updating the
    privacy-wall negative tests in test_cycle_assignment_privacy_wall.py.
    """
    assignment_id: str
    brief_id: str
    submitter_display_name: str
    cycle_title: str
    submitted_at: str
    cohort_label: Optional[str] = None
    note: Optional[str] = None
    status: str  # pending | accepted | declined


class AcceptOut(BaseModel):
    assignment_id: str
    brief_id: str
    status: str
    accepted_at: str


class DeclineIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=600)


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
async def _resolve_cohort_neds(
    *, context_id: str, cohort_id: str,
) -> List[str]:
    """Snapshot NED account ids for a cohort at assignment time.

    A "cohort" today is interpreted as a board's NED membership set —
    i.e., every active membership with role="ned" inside the cohort's
    context. If we later introduce a richer `db.cohorts` collection,
    this resolver swaps in one place.
    """
    cohort = await db.cohorts.find_one(
        {"id": cohort_id, "context_id": context_id, "status": "active"},
        {"_id": 0, "id": 1, "label": 1, "ned_account_ids": 1, "context_id": 1},
    )
    if cohort and isinstance(cohort.get("ned_account_ids"), list):
        return [str(a) for a in cohort["ned_account_ids"] if a]
    # Fallback: every active NED membership in this context.
    memberships = await db.memberships.find(
        {"context_id": context_id, "role": "ned", "status": "active"},
        {"_id": 0, "account_id": 1},
    ).to_list(200)
    return [m["account_id"] for m in memberships if m.get("account_id")]


async def _cohort_label(*, context_id: str, cohort_id: Optional[str]) -> Optional[str]:
    if not cohort_id:
        return None
    cohort = await db.cohorts.find_one(
        {"id": cohort_id, "context_id": context_id},
        {"_id": 0, "label": 1},
    )
    return (cohort or {}).get("label")


async def _cycle_title(*, context_id: str, cycle_id: str) -> str:
    cycle = await db.cycle_agendas.find_one(
        {"id": cycle_id, "context_id": context_id},
        {"_id": 0, "title": 1},
    )
    return (cycle or {}).get("title") or "Reporting cycle"


async def _submitter_display_name(account_id: str) -> str:
    acc = await db.accounts.find_one(
        {"id": account_id},
        {"_id": 0, "display_name": 1, "name": 1},
    )
    return (acc or {}).get("display_name") or (acc or {}).get("name") or "Anonymous"


async def _get_brief_or_404(
    *, brief_id: str, context_id: str,
) -> Dict[str, Any]:
    brief = await db.work_studio_briefs.find_one(
        {"id": brief_id, "context_id": context_id},
        {"_id": 0},
    )
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found.")
    return brief


async def _get_assignment_for_ned_or_404(
    *, assignment_id: str, account_id: str,
) -> Dict[str, Any]:
    row = await db.cycle_assignments.find_one(
        {"id": assignment_id, "ned_id": account_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return row


# ─────────────────────────────────────────────────────────────────────
# 1. Submit a brief for board reporting
# ─────────────────────────────────────────────────────────────────────
@router.post(
    "/contexts/{context_id}/cycles/{cycle_id}/briefs/{brief_id}/submit-for-board",
    response_model=SubmitForBoardOut,
)
async def submit_brief_for_board(
    context_id: str,
    cycle_id: str,
    brief_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Mark a brief as submitted for board reporting.

    State transition: board_status null|draft -> submitted (idempotent
    if already submitted; refuses if already shipped).
    """
    permitted = await can_submit_for_board(
        account=ctx["account"], context=ctx["context"], membership=ctx["membership"],
    )
    if not permitted:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to submit briefs for board reporting in this workspace.",
        )

    brief = await _get_brief_or_404(brief_id=brief_id, context_id=context_id)
    current_status = brief.get("board_status") or "draft"
    if current_status == "shipped":
        raise HTTPException(
            status_code=409,
            detail="Brief has already shipped; cannot be re-submitted.",
        )

    submitted_at = iso(now())
    await db.work_studio_briefs.update_one(
        {"id": brief_id, "context_id": context_id},
        {"$set": {
            "board_status": "submitted",
            "submitted_at": submitted_at,
            "submitter_account_id": ctx["account"]["id"],
            "submitted_cycle_id": cycle_id,
            "updated_at": submitted_at,
        }},
    )
    reason = await permission_reason(
        account=ctx["account"], context=ctx["context"], membership=ctx["membership"],
    )
    await write_audit(
        context_id, ctx["account"]["id"],
        "cycle.brief.submit_for_board", "brief", brief_id,
        {
            "cycle_id": cycle_id,
            "workspace_kind": workspace_kind(ctx["context"]),
            "permission_reason": reason,
        },
    )
    return SubmitForBoardOut(
        brief_id=brief_id,
        board_status="submitted",
        submitted_at=submitted_at,
        submitter_account_id=ctx["account"]["id"],
    )


# ─────────────────────────────────────────────────────────────────────
# 2. Create / list / get / cancel assignments
# ─────────────────────────────────────────────────────────────────────
@router.post(
    "/contexts/{context_id}/cycles/{cycle_id}/briefs/{brief_id}/assignments",
    status_code=201,
)
async def create_assignments(
    context_id: str,
    cycle_id: str,
    brief_id: str,
    body: AssignmentCreateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Fan-out one assignment row per NED.

    Exactly one of `ned_ids` / `cohort_id` MUST be set (mutually exclusive).
    Cohort resolution snapshots ned ids at assignment time and persists
    them on the row so a future cohort membership change doesn't retro-
    actively affect existing assignments.

    Returns: {"assignments": [AssignmentOut], "count": N}.
    """
    permitted = await can_submit_for_board(
        account=ctx["account"], context=ctx["context"], membership=ctx["membership"],
    )
    if not permitted:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to assign briefs in this workspace.",
        )

    if (body.ned_ids and body.cohort_id) or (not body.ned_ids and not body.cohort_id):
        raise HTTPException(
            status_code=400,
            detail="Exactly one of ned_ids or cohort_id must be set.",
        )

    brief = await _get_brief_or_404(brief_id=brief_id, context_id=context_id)
    if (brief.get("board_status") or "draft") not in {"submitted", "shipped"}:
        raise HTTPException(
            status_code=400,
            detail="Brief must be submitted for board reporting before assignment.",
        )

    if body.cohort_id:
        ned_ids = await _resolve_cohort_neds(
            context_id=context_id, cohort_id=body.cohort_id,
        )
        if not ned_ids:
            raise HTTPException(
                status_code=400,
                detail="Cohort resolved to zero NEDs; nothing to assign.",
            )
    else:
        ned_ids = list({a for a in (body.ned_ids or []) if isinstance(a, str) and a})
        if not ned_ids:
            raise HTTPException(
                status_code=400,
                detail="ned_ids must contain at least one id.",
            )

    cohort_label = await _cohort_label(context_id=context_id, cohort_id=body.cohort_id)
    cycle_title = await _cycle_title(context_id=context_id, cycle_id=cycle_id)
    submitter_name = await _submitter_display_name(ctx["account"]["id"])
    submitted_at = brief.get("submitted_at") or iso(now())
    now_iso = iso(now())

    # Skip ned_ids that already have a non-cancelled assignment for this
    # brief — idempotent re-assignment.
    existing = await db.cycle_assignments.find(
        {
            "brief_id": brief_id,
            "ned_id": {"$in": ned_ids},
            "status": {"$ne": "cancelled"},
        },
        {"_id": 0, "ned_id": 1},
    ).to_list(len(ned_ids))
    existing_ids = {r["ned_id"] for r in existing}

    inserted_rows: List[Dict[str, Any]] = []
    for nid in ned_ids:
        if nid in existing_ids:
            continue
        row = {
            "id": str(uuid.uuid4()),
            "brief_id": brief_id,
            "cycle_id": cycle_id,
            "context_id": context_id,
            "ned_id": nid,
            "submitter_account_id": ctx["account"]["id"],
            "submitter_display_name": submitter_name,
            "cycle_title": cycle_title,
            "submitted_at": submitted_at,
            "note": (body.note or None),
            "cohort_id": body.cohort_id,
            "cohort_label": cohort_label,
            "status": "pending",
            "created_at": now_iso,
            "updated_at": now_iso,
            "accepted_at": None,
            "declined_at": None,
            "decline_reason": None,
        }
        inserted_rows.append(row)

    if inserted_rows:
        await db.cycle_assignments.insert_many(inserted_rows)

    for r in inserted_rows:
        await write_audit(
            context_id, ctx["account"]["id"],
            "cycle.brief.assigned", "assignment", r["id"],
            {
                "brief_id": brief_id,
                "cycle_id": cycle_id,
                "ned_id": r["ned_id"],
                "cohort_id": body.cohort_id,
                "via": "cohort" if body.cohort_id else "named",
            },
        )

    # MOCKED IN DEV: Resend notification call site. In production each
    # newly-created assignment notifies the assigned NED.
    for r in inserted_rows:
        try:
            # MOCKED IN DEV — Resend is in test mode in the preview env.
            # No fake confirmation surfaced to the user; the audit row
            # above is the system-of-record. Real send is gated behind
            # `RESEND_TEST_MODE=false` in production.
            from email_service import notify_ned_assignment_stub  # type: ignore
            await notify_ned_assignment_stub(
                assignment_id=r["id"],
                ned_account_id=r["ned_id"],
                submitter_name=submitter_name,
                cycle_title=cycle_title,
            )
        except Exception:  # noqa: BLE001
            # Notification failures must never break the assignment.
            pass

    # Re-read the rows we'd already written so the response carries
    # both new and pre-existing assignments for the requested ned set.
    final = await db.cycle_assignments.find(
        {
            "brief_id": brief_id,
            "ned_id": {"$in": ned_ids},
            "status": {"$ne": "cancelled"},
        },
        {"_id": 0},
    ).to_list(len(ned_ids))
    return {
        "assignments": [AssignmentOut(**r).model_dump() for r in final],
        "count": len(final),
        "newly_created": len(inserted_rows),
    }


@router.get(
    "/contexts/{context_id}/cycles/{cycle_id}/briefs/{brief_id}/assignments",
)
async def list_assignments(
    context_id: str,
    cycle_id: str,
    brief_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rows = await db.cycle_assignments.find(
        {
            "brief_id": brief_id,
            "cycle_id": cycle_id,
            "context_id": context_id,
        },
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    return {
        "assignments": [AssignmentOut(**r).model_dump() for r in rows],
        "count": len(rows),
    }


@router.delete("/contexts/{context_id}/cycle-assignments/{assignment_id}")
async def cancel_assignment(
    context_id: str,
    assignment_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Cancel a still-pending assignment. Creator-only, only before
    the NED has accepted.

    The brief's submitter can cancel any pending assignment on their
    own brief. An admin / chief_of_staff in the same context can cancel
    too. Workspace owner can always cancel.
    """
    row = await db.cycle_assignments.find_one(
        {"id": assignment_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if row.get("status") != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel assignment in status '{row.get('status')}'.",
        )
    aid = ctx["account"]["id"]
    is_creator = row.get("submitter_account_id") == aid
    permitted = is_creator or await can_submit_for_board(
        account=ctx["account"], context=ctx["context"], membership=ctx["membership"],
    )
    if not permitted:
        raise HTTPException(
            status_code=403,
            detail="Only the assignment creator (or a workspace admin/CoS) can cancel.",
        )

    now_iso = iso(now())
    await db.cycle_assignments.update_one(
        {"id": assignment_id},
        {"$set": {"status": "cancelled", "updated_at": now_iso, "cancelled_at": now_iso}},
    )
    await write_audit(
        context_id, aid,
        "cycle.brief.assignment_cancelled", "assignment", assignment_id,
        {"brief_id": row.get("brief_id"), "cycle_id": row.get("cycle_id")},
    )
    return {"assignment_id": assignment_id, "status": "cancelled"}


# ─────────────────────────────────────────────────────────────────────
# 3. NED inbox — STRICT whitelist
# ─────────────────────────────────────────────────────────────────────
@router.get("/ned/inbox/assignments")
async def ned_inbox(
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Pending + accepted + declined assignments for the authenticated
    NED. Strict field whitelist; no Exec-internal payload.
    """
    rows = await db.cycle_assignments.find(
        {"ned_id": current["id"], "status": {"$in": ["pending", "accepted", "declined"]}},
        {"_id": 0},
    ).sort("submitted_at", -1).to_list(200)

    items: List[Dict[str, Any]] = []
    for r in rows:
        # The Pydantic model enforces the whitelist; building via the
        # model ensures no field can sneak in without code change.
        items.append(NedInboxItemOut(
            assignment_id=r["id"],
            brief_id=r["brief_id"],
            submitter_display_name=r.get("submitter_display_name") or "Anonymous",
            cycle_title=r.get("cycle_title") or "Reporting cycle",
            submitted_at=r.get("submitted_at") or r.get("created_at") or "",
            cohort_label=r.get("cohort_label"),
            note=r.get("note"),
            status=r.get("status") or "pending",
        ).model_dump())
    return {"items": items, "count": len(items)}


# ─────────────────────────────────────────────────────────────────────
# 4. Accept
# ─────────────────────────────────────────────────────────────────────
@router.post("/ned/assignments/{assignment_id}/accept", response_model=AcceptOut)
async def accept_assignment(
    assignment_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Idempotent accept. Privacy-Wall-enforced ingest into NED record.

    Concretely: ONLY the Brief artefact (resolved via brief_id) lands
    in the NED's durable record. NO Exec-internal fields cross the wall
    here — we never read from db.cycle_agendas, db.cycle_contributions,
    db.cycle_team, db.cycle_followups.
    """
    row = await _get_assignment_for_ned_or_404(
        assignment_id=assignment_id, account_id=current["id"],
    )
    status_now = row.get("status") or "pending"
    if status_now == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Assignment was cancelled by the submitter.",
        )
    if status_now == "declined":
        raise HTTPException(
            status_code=409,
            detail="You have already declined this assignment.",
        )
    if status_now == "accepted":
        # Idempotent: re-return the previous acceptance.
        return AcceptOut(
            assignment_id=assignment_id,
            brief_id=row["brief_id"],
            status="accepted",
            accepted_at=row.get("accepted_at") or "",
        )

    now_iso = iso(now())
    # ──────────────────────────────────────────────────────────────
    # Privacy-Wall enforced ingest. We write a single ned_pack row
    # that references the Brief by id. We deliberately do NOT copy
    # ANY cycle_* collection into the NED side. The NED reads the
    # Brief artefact from db.work_studio_briefs / brief_revisions on
    # demand through the existing NED render path.
    # ──────────────────────────────────────────────────────────────
    pack_row = {
        "id": str(uuid.uuid4()),
        "ned_id": current["id"],
        "assignment_id": assignment_id,
        "brief_id": row["brief_id"],
        # Audit context only — derived from the NED's own view.
        "submitter_display_name": row.get("submitter_display_name"),
        "cycle_title": row.get("cycle_title"),
        "received_at": now_iso,
    }
    await db.ned_packs.insert_one(pack_row)

    await db.cycle_assignments.update_one(
        {"id": assignment_id, "ned_id": current["id"]},
        {"$set": {
            "status": "accepted",
            "accepted_at": now_iso,
            "updated_at": now_iso,
        }},
    )
    # Bump the parent brief to shipped on first accept; idempotent.
    await db.work_studio_briefs.update_one(
        {"id": row["brief_id"], "board_status": {"$in": ["submitted", "shipped"]}},
        {"$set": {"board_status": "shipped", "updated_at": now_iso}},
    )

    await write_audit(
        row.get("context_id"), current["id"],
        "cycle.brief.assignment_accepted", "assignment", assignment_id,
        {"brief_id": row["brief_id"]},
    )
    return AcceptOut(
        assignment_id=assignment_id,
        brief_id=row["brief_id"],
        status="accepted",
        accepted_at=now_iso,
    )


# ─────────────────────────────────────────────────────────────────────
# 5. Decline
# ─────────────────────────────────────────────────────────────────────
@router.post("/ned/assignments/{assignment_id}/decline")
async def decline_assignment(
    assignment_id: str,
    body: DeclineIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    row = await _get_assignment_for_ned_or_404(
        assignment_id=assignment_id, account_id=current["id"],
    )
    status_now = row.get("status") or "pending"
    if status_now in {"accepted", "cancelled", "declined"}:
        raise HTTPException(
            status_code=409,
            detail=f"Assignment in status '{status_now}' cannot be declined.",
        )

    now_iso = iso(now())
    await db.cycle_assignments.update_one(
        {"id": assignment_id, "ned_id": current["id"]},
        {"$set": {
            "status": "declined",
            "declined_at": now_iso,
            "decline_reason": (body.reason or None),
            "updated_at": now_iso,
        }},
    )
    await write_audit(
        row.get("context_id"), current["id"],
        "cycle.brief.assignment_declined", "assignment", assignment_id,
        {"brief_id": row["brief_id"], "has_reason": bool(body.reason)},
    )
    return {
        "assignment_id": assignment_id,
        "status": "declined",
        "declined_at": now_iso,
    }


# ─────────────────────────────────────────────────────────────────────
# 6. Submitter-side rollup view (Should-have)
# ─────────────────────────────────────────────────────────────────────
@router.get("/me/submitted-briefs")
async def my_submitted_briefs(
    current: Dict[str, Any] = Depends(get_current_account),
):
    """List briefs I have submitted for board reporting, with a rollup
    of assignment statuses for each. Used by the submitter inbox view."""
    briefs = await db.work_studio_briefs.find(
        {
            "submitter_account_id": current["id"],
            "board_status": {"$in": ["submitted", "shipped"]},
        },
        {"_id": 0, "id": 1, "title": 1, "subtitle": 1, "company_label": 1,
         "context_id": 1, "submitted_cycle_id": 1, "submitted_at": 1,
         "board_status": 1, "updated_at": 1},
    ).sort("submitted_at", -1).to_list(200)
    if not briefs:
        return {"briefs": [], "count": 0}

    brief_ids = [b["id"] for b in briefs]
    assignments = await db.cycle_assignments.find(
        {"brief_id": {"$in": brief_ids}},
        {"_id": 0, "brief_id": 1, "status": 1},
    ).to_list(2000)
    rollup: Dict[str, Dict[str, int]] = {}
    for a in assignments:
        b = rollup.setdefault(a["brief_id"], {
            "pending": 0, "accepted": 0, "declined": 0, "cancelled": 0,
        })
        s = a.get("status") or "pending"
        if s in b:
            b[s] += 1

    out = []
    for b in briefs:
        out.append({
            **b,
            "assignment_rollup": rollup.get(b["id"]) or {
                "pending": 0, "accepted": 0, "declined": 0, "cancelled": 0,
            },
        })
    return {"briefs": out, "count": len(out)}
