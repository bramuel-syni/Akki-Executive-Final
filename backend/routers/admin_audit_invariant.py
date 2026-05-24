"""Admin · Audit invariant violations panel.

H2.5 follow-up (2026-05-24). The chat router's streaming path writes a
row to ``db.audit_invariant_violations`` whenever Shield's contract is
violated at runtime:

  * ``shield_failure_at_entry`` — Shield's de-identifier failed before
    the LLM call (translates to HTTP 503). The collection traps every
    such event so ops can spot a real outage vs a transient blip.
  * ``luhn_pan_in_shielded_prompt`` — Fix #6 defense-in-depth canary.
    AFTER Shield runs and BEFORE the LLM call, the route scans the
    redacted prompt for residual Luhn-valid 13-19 digit runs. A match
    is impossible-by-design (Shield's regex pass should have caught
    every PAN); finding one means a regression slipped past the test
    suite. The route refuses to forward to the LLM, returns an
    in-stream error, and logs this row so ops know to investigate.

This module exposes a read-only superadmin endpoint so the operator can
view recent violations without going into Mongo directly. Same pattern
as ``/api/admin/auth/events`` and ``/api/admin/llm/spend``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from core import db, get_current_account

router = APIRouter(prefix="/api/admin", tags=["admin", "audit"])


async def _require_superadmin(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return account


def _coerce_ts(value: Any) -> str:
    """Return an ISO 8601 string regardless of whether the row's ``ts``
    landed as a datetime (BSON Date) or a string (legacy)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value or "")


@router.get("/audit-invariant-violations")
async def list_audit_invariant_violations(
    hours: int = Query(24, ge=1, le=720),
    kind: str = Query(
        "",
        pattern=r"^$|^[a-z_]+$",
        description=(
            "Optional kind filter — e.g. ``shield_failure_at_entry`` or "
            "``luhn_pan_in_shielded_prompt``. Empty string returns all kinds."
        ),
    ),
    limit: int = Query(500, ge=1, le=5000),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """List recent audit-invariant violations. Read-only.

    Response shape::

        {
            "since": "<iso 8601 cutoff>",
            "total": <int>,
            "by_kind": {"<kind>": <count>, ...},
            "rows": [
                {"id", "kind", "surface", "channel", "account_id",
                 "chat_id", "ts", ...},
                ...
            ]
        }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    # The collection's ``ts`` column has historically been written as an
    # ISO string by the chat router (see chat.py shield_failure_at_entry
    # writes). Filter by string compare which is safe for ISO 8601.
    match: Dict[str, Any] = {"ts": {"$gte": cutoff_iso}}
    if kind:
        match["kind"] = kind

    rows: List[Dict[str, Any]] = await db.audit_invariant_violations.find(
        match, {"_id": 0},
    ).sort("ts", -1).to_list(length=limit)

    by_kind: Dict[str, int] = {}
    for r in rows:
        k = r.get("kind") or "unknown"
        by_kind[k] = by_kind.get(k, 0) + 1
        # Normalise ts for the response (some legacy writes used
        # `datetime`; we coerce to ISO 8601 for UI consumers).
        r["ts"] = _coerce_ts(r.get("ts"))

    return {
        "since": cutoff_iso,
        "total": len(rows),
        "by_kind": by_kind,
        "rows": rows,
    }


@router.get("/audit-invariant-violations/summary")
async def audit_invariant_violations_summary(
    hours: int = Query(24, ge=1, le=720),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Lightweight rollup — no row payloads, just per-kind counts.
    Suitable for the Admin Health dashboard tile."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff_iso}}},
        {"$group": {"_id": "$kind", "count": {"$sum": 1}}},
    ]
    rows = await db.audit_invariant_violations.aggregate(pipeline).to_list(length=100)
    by_kind = {r["_id"] or "unknown": int(r["count"]) for r in rows}
    return {
        "since": cutoff_iso,
        "total": sum(by_kind.values()),
        "by_kind": by_kind,
    }
