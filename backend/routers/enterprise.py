"""Enterprise interest — light-touch lead-gen funnel from Personal contexts.

Captures expressions of interest from users on Personal-tier contexts who want
to evaluate Enterprise (multi-seat, sponsored data ownership, audit-grade
provenance, SSO). One row per (account_id, context_id) keyed by latest expression.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now, write_audit

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


class EnterpriseInterestIn(BaseModel):
    use_case: Optional[str] = Field(None, max_length=600)
    company_size: Optional[str] = Field(None, max_length=40)
    timing: Optional[str] = Field(None, max_length=40)


@router.post("/interest")
async def record_interest(payload: EnterpriseInterestIn,
                          account: Dict[str, Any] = Depends(get_current_account)):
    rec = {
        "id": str(uuid.uuid4()),
        "account_id": account["id"],
        "account_email": account.get("email"),
        "account_name": account.get("name"),
        "use_case": (payload.use_case or "").strip()[:600],
        "company_size": (payload.company_size or "").strip()[:40] or None,
        "timing": (payload.timing or "").strip()[:40] or None,
        "created_at": iso(now()),
    }
    await db.enterprise_interest.insert_one(rec)
    rec.pop("_id", None)

    # Best-effort audit on the user's first context (so it appears in their log).
    try:
        m = await db.memberships.find_one(
            {"account_id": account["id"], "status": "active"},
            {"_id": 0, "context_id": 1},
            sort=[("created_at", 1)],
        )
        if m:
            await write_audit(
                m["context_id"], account["id"],
                "enterprise.interest_recorded", "account", account["id"],
                {"timing": rec["timing"], "company_size": rec["company_size"]},
            )
    except Exception:  # noqa: BLE001
        pass

    return {"ok": True, "id": rec["id"]}


@router.get("/interest/me")
async def my_latest_interest(account: Dict[str, Any] = Depends(get_current_account)):
    rec = await db.enterprise_interest.find_one(
        {"account_id": account["id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not rec:
        return {"submitted": False}
    return {"submitted": True, "interest": rec}
