"""AKKI Solve · interest registration (pre-launch).

Captures early-access expressions from inside the app and via the public
landing page. Uses an append-only audit pattern (every submission is a new
row) — same as the Enterprise lead-gen surface — so we keep the full
intent timeline. /me returns the latest record.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now

router = APIRouter(prefix="/api/solve", tags=["solve"])


class SolveInterestIn(BaseModel):
    use_case: Optional[str] = Field(None, max_length=600)
    role: Optional[str] = Field(None, max_length=80)


@router.post("/interest")
async def register_interest(
    payload: SolveInterestIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    rec = {
        "id": str(uuid.uuid4()),
        "account_id": account["id"],
        "account_email": account.get("email"),
        "account_name": account.get("name"),
        "use_case": (payload.use_case or "").strip()[:600] or None,
        "role": (payload.role or "").strip()[:80] or None,
        "created_at": iso(now()),
    }
    await db.solve_interest.insert_one(rec)
    rec.pop("_id", None)
    return {"ok": True, "id": rec["id"]}


@router.get("/interest/me")
async def my_interest(account: Dict[str, Any] = Depends(get_current_account)):
    rec = await db.solve_interest.find_one(
        {"account_id": account["id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not rec:
        return {"submitted": False}
    return {"submitted": True, "interest": rec}
