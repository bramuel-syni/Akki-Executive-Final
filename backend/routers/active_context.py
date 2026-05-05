"""Phase A — active-context endpoints (Memo Item 5).

Two endpoints + the verbatim memo switch-modal copy.

  - `GET  /api/me/contexts`                lists ONLY the contexts the
                                           caller has an active
                                           membership at, with role
                                           per row (the company
                                           switcher reads this).

  - `POST /api/me/active-context`          validates membership; logs
                                           a `context.switched` audit
                                           row; returns the verbatim
                                           memo switch-notification
                                           body.

Both endpoints are membership-aware but NOT membership-gated — the
caller is the user themselves; nothing cross-context leaks (each row
is for a context the caller has a membership at).

This router does NOT use `services.rbac.require_role` because the
switcher endpoint is the place the user GOES TO when they don't yet
have an active context picked — so requiring `X-Active-Context` here
would be circular. Both endpoints take only the JWT identity; per-row
role comes from the membership lookup.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.rbac import write_context_switched_audit


router = APIRouter(prefix="/api/me", tags=["active-context"])


# ─────────────────────────────────────────────────────────────────────
# Verbatim memo copy — used by both the switch-modal frontend and the
# server response of POST /api/me/active-context. Templated with the
# four placeholders the memo specifies. DO NOT adjust wording.
# ─────────────────────────────────────────────────────────────────────
SWITCH_MODAL_TITLE = "You are now in {to_company}"
SWITCH_MODAL_BODY = (
    "You're now in {to_company} as {to_role}. Your access here is "
    "limited to what {to_role} is permitted to do at {to_company}. "
    "To return to {from_company} as {from_role}, use the company "
    "switcher."
)


def _format_role(role: Optional[str]) -> str:
    """Render the role string for display. Memo uses Title-case in
    the example ("[Role at Company B]"); we render lower-case roles
    as Title-case ("Executive", "NED")."""
    if not role:
        return "—"
    if role.lower() == "ned":
        return "NED"
    return role[:1].upper() + role[1:]


# ─────────────────────────────────────────────────────────────────────
# GET /api/me/contexts
# ─────────────────────────────────────────────────────────────────────
@router.get("/contexts")
async def list_my_contexts(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Return ONLY contexts where the caller has an active membership.

    Each row carries the per-(user, context) role so the company
    switcher can render the role badge ("Ubora · Executive",
    "Mara · NED"). Contexts the user is NOT a member of are not
    listed — there is no leakage of context identity.
    """
    memberships: List[Dict[str, Any]] = await db.memberships.find(
        {"account_id": current["id"], "status": "active"},
        {"_id": 0, "context_id": 1, "role": 1, "sub_role": 1, "joined_at": 1},
    ).to_list(500)
    if not memberships:
        return {"items": [], "count": 0}

    ctx_ids = [m["context_id"] for m in memberships]
    contexts = await db.contexts.find(
        {"id": {"$in": ctx_ids}},
        {"_id": 0, "id": 1, "name": 1, "type": 1, "status": 1,
         "industry": 1, "jurisdiction": 1, "owner_account_id": 1},
    ).to_list(500)
    ctx_by_id = {c["id"]: c for c in contexts}

    items: List[Dict[str, Any]] = []
    for m in memberships:
        c = ctx_by_id.get(m["context_id"])
        if not c:
            # Membership exists but the context row has been hard-deleted
            # — defensive skip; the user can't switch to a missing context.
            continue
        items.append({
            "context_id": m["context_id"],
            "context_name": c.get("name"),
            "context_type": c.get("type"),
            "context_status": c.get("status"),
            "industry": c.get("industry"),
            "jurisdiction": c.get("jurisdiction"),
            "is_owner": c.get("owner_account_id") == current["id"],
            "role": m.get("role"),
            "role_display": _format_role(m.get("role")),
            "sub_role": m.get("sub_role"),
            "joined_at": m.get("joined_at"),
        })

    # Most-recently-joined first; deterministic when timestamps tie.
    items.sort(key=lambda r: (r.get("joined_at") or "", r["context_id"]), reverse=True)

    return {"items": items, "count": len(items)}


# ─────────────────────────────────────────────────────────────────────
# POST /api/me/active-context
# ─────────────────────────────────────────────────────────────────────
class ActiveContextIn(BaseModel):
    context_id: str = Field(..., min_length=1, max_length=128)
    # Optional — when present, used to format the "back to ..." line
    # in the switch-modal body. The server has no concept of a "prior"
    # context so the frontend tells us what was previously active.
    from_context_id: Optional[str] = Field(default=None, max_length=128)


@router.post("/active-context")
async def set_active_context(
    body: ActiveContextIn,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Validate that the caller has an active membership at
    `context_id`. On success: write a `context.switched` audit row
    and return the verbatim memo switch-modal payload. On failure:
    `403 MEMBERSHIP_REVOKED`.

    The server is **stateless** about active context — it does NOT
    persist "the user's current active context" anywhere. The SPA
    holds that state per-tab in `sessionStorage` (D-004). This
    endpoint is purely a validation + audit + UI-payload step.
    """
    # 1. Validate the destination membership.
    to_membership = await db.memberships.find_one(
        {
            "account_id": current["id"],
            "context_id": body.context_id,
            "status": "active",
        },
        {"_id": 0},
    )
    if not to_membership:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "MEMBERSHIP_REVOKED",
                "message": "You do not have membership at that context.",
            },
        )

    to_role = to_membership.get("role") or "—"

    to_ctx = await db.contexts.find_one(
        {"id": body.context_id},
        {"_id": 0, "id": 1, "name": 1, "type": 1},
    )
    if not to_ctx:
        # Edge case — membership exists but context row is gone.
        raise HTTPException(
            status_code=404,
            detail={"code": "CONTEXT_NOT_FOUND", "message": "Context not found."},
        )

    # 2. Resolve the prior context for the modal copy (best-effort —
    #    if the SPA doesn't pass `from_context_id`, we render "your
    #    previous context" rather than a name).
    from_ctx_name: str = "your previous context"
    from_role: Optional[str] = None
    if body.from_context_id:
        fm = await db.memberships.find_one(
            {
                "account_id": current["id"],
                "context_id": body.from_context_id,
                "status": "active",
            },
            {"_id": 0, "role": 1},
        )
        if fm:
            from_role = fm.get("role")
        fc = await db.contexts.find_one(
            {"id": body.from_context_id}, {"_id": 0, "name": 1},
        )
        if fc and fc.get("name"):
            from_ctx_name = fc["name"]

    # 3. Audit the switch.
    await write_context_switched_audit(
        account_id=current["id"],
        from_context_id=body.from_context_id,
        from_role=from_role,
        to_context_id=body.context_id,
        to_role=to_role,
    )

    # 4. Compose the verbatim memo modal payload.
    notification_body = SWITCH_MODAL_BODY.format(
        to_company=to_ctx.get("name") or "this company",
        to_role=_format_role(to_role),
        from_company=from_ctx_name,
        from_role=_format_role(from_role) if from_role else "your previous role",
    )
    notification_title = SWITCH_MODAL_TITLE.format(
        to_company=to_ctx.get("name") or "this company",
    )

    return {
        "active_context_id": body.context_id,
        "context_name": to_ctx.get("name"),
        "context_type": to_ctx.get("type"),
        "role": to_role,
        "role_display": _format_role(to_role),
        "switch_notification": {
            "title": notification_title,
            "body": notification_body,
        },
    }


# ─────────────────────────────────────────────────────────────────────
# Role probes — the demonstrative endpoints used by the SPA boot
# health check + by Phase A acceptance test #5. Importing
# `require_role` lazily so this module's import-time graph stays
# narrow.
# ─────────────────────────────────────────────────────────────────────
from services.rbac import require_role  # noqa: E402  intentional lazy import


@router.get("/role-probe")
async def role_probe(
    ctx: Dict[str, Any] = Depends(require_role()),
) -> Dict[str, Any]:
    """Any-role probe. Returns the active context + role for the
    caller after going through the full RBAC pipeline (header read +
    membership lookup + audit write). The SPA calls this on boot to
    confirm the cached `X-Active-Context` is still valid (membership
    might have been revoked since the last tab session)."""
    return {
        "ok": True,
        "context_id": ctx["context_id"],
        "role": ctx["role"],
        "role_display": _format_role(ctx["role"]),
    }


@router.get("/role-probe/executive")
async def role_probe_executive(
    ctx: Dict[str, Any] = Depends(require_role("executive")),
) -> Dict[str, Any]:
    """Executive-only probe. Used by Phase A acceptance #5. NEDs
    hitting this with their NED-context header in the active slot
    should receive `403 ROLE_FORBIDDEN`."""
    return {
        "ok": True,
        "context_id": ctx["context_id"],
        "role": ctx["role"],
        "exec_only_payload": "you are executive at this context",
    }


@router.get("/role-probe/ned")
async def role_probe_ned(
    ctx: Dict[str, Any] = Depends(require_role("ned")),
) -> Dict[str, Any]:
    """NED-only probe. Mirror of the executive one. Useful for the
    contrapositive test (executive at A, switching to NED at B,
    confirming B's NED role grants this endpoint)."""
    return {
        "ok": True,
        "context_id": ctx["context_id"],
        "role": ctx["role"],
        "ned_only_payload": "you are ned at this context",
    }
