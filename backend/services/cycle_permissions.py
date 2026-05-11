"""Cycle Manager — submit/assign authorisation helper.

Single chokepoint for the question "can this account submit a Brief for
board reporting in this context, and therefore also assign it to NEDs?"

Decision matrix (locked in CYCLE_MANAGER_BRIEF.md §3.3):

  Workspace type (context.type)   |  Permitted callers
  --------------------------------|---------------------------------------
  executive_personal              |  owner only
  executive_enterprise            |  owner + sub_role="admin" + sub_role="chief_of_staff" + ExCo team member
  ned_personal / ned_sponsored    |  not permitted (NED-side never submits)

ExCo team membership is derived from `db.exco_teams.member_account_ids`
for any active team in this context (see HOME sprint — routers/exco_teams.py).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core import db

logger = logging.getLogger("akki.cycle_permissions")


_INDIVIDUAL_TYPES = {"executive_personal"}
_TEAM_TYPES = {"executive_enterprise"}
_TEAM_PERMITTED_SUB_ROLES = {"admin", "chief_of_staff"}


async def can_submit_for_board(
    *,
    account: Dict[str, Any],
    context: Dict[str, Any],
    membership: Dict[str, Any],
) -> bool:
    """Return True iff the caller is permitted to submit a Brief for
    board reporting in this context. See module docstring for the
    decision matrix.

    The three input dicts are exactly the shape produced by
    `core.require_context_membership()(...)`'s `{"account", "context",
    "membership"}` triple — callers should pass them straight through.
    """
    if not account or not context or not membership:
        return False
    ctype = context.get("type") or ""
    aid = account.get("id")
    if not aid:
        return False
    # NED contexts: never permitted to submit (NED side is consumer only).
    if ctype.startswith("ned_"):
        return False
    # Owner always permitted.
    if context.get("owner_account_id") == aid:
        return True
    # Individual workspace: owner-only. Already returned True above
    # if the caller is the owner; everything else is refused here.
    if ctype in _INDIVIDUAL_TYPES:
        return False
    # Team workspace: admin or chief_of_staff sub_role permitted.
    if ctype in _TEAM_TYPES:
        if (membership.get("sub_role") or "") in _TEAM_PERMITTED_SUB_ROLES:
            return True
        # ExCo team member is permitted too. We treat membership in ANY
        # active ExCo team in this context as the permission grant.
        team = await db.exco_teams.find_one(
            {
                "context_id": context["id"],
                "member_account_ids": aid,
                "status": "active",
            },
            {"_id": 0, "id": 1},
        )
        if team:
            return True
    return False


def workspace_kind(context: Dict[str, Any]) -> str:
    """Return 'individual' | 'team' | 'ned' | 'unknown' for logging /
    audit metadata."""
    ctype = (context or {}).get("type") or ""
    if ctype in _INDIVIDUAL_TYPES:
        return "individual"
    if ctype in _TEAM_TYPES:
        return "team"
    if ctype.startswith("ned_"):
        return "ned"
    return "unknown"


async def permission_reason(
    *,
    account: Dict[str, Any],
    context: Dict[str, Any],
    membership: Dict[str, Any],
) -> str:
    """Return a short human-readable reason describing the grant.

    Used in audit_log.metadata so a future auditor can see WHY a
    submit/assign was allowed (or refused). Cheap to compute; never
    surfaces content fields."""
    if not account or not context or not membership:
        return "missing_input"
    ctype = context.get("type") or ""
    aid = account.get("id")
    if ctype.startswith("ned_"):
        return "ned_context_not_permitted"
    if context.get("owner_account_id") == aid:
        return "owner"
    if ctype in _INDIVIDUAL_TYPES:
        return "individual_non_owner_refused"
    if ctype in _TEAM_TYPES:
        sub_role = membership.get("sub_role") or ""
        if sub_role == "admin":
            return "team_admin"
        if sub_role == "chief_of_staff":
            return "team_chief_of_staff"
        team = await db.exco_teams.find_one(
            {
                "context_id": context["id"],
                "member_account_ids": aid,
                "status": "active",
            },
            {"_id": 0, "id": 1},
        )
        if team:
            return "team_exco_member"
        return "team_non_privileged_refused"
    return "unknown_context_type"
