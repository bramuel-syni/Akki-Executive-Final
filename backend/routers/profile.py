"""Profile endpoints (Patch 25C, 2026-05-12).

Exposes `/api/me/profile` GET + PATCH for fields that don't belong on
the auth bootstrap payload (`/api/auth/me` is already big enough).
Currently only carries `country` (ISO-3166-1 alpha-2) used by the
news-feed region resolver. UI not yet wired — the API is in place so
the same endpoint can power a future "Locale & language" settings
panel without an extra patch.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileOut(BaseModel):
    country: Optional[str] = None  # ISO-3166-1 alpha-2 or "GLOBAL"


class ProfilePatchIn(BaseModel):
    # 2-letter ISO code (`UK`, `US`, …) or `GLOBAL`. We do a light check
    # — anything 2-7 uppercase letters — instead of a giant validation
    # table. The news feed treats unknown codes as GLOBAL.
    country: Optional[str] = Field(
        None, min_length=2, max_length=7,
        pattern=r"^[A-Za-z]{2,7}$",
    )


@router.get("/me/profile", response_model=ProfileOut)
async def get_my_profile(
    account: Dict[str, Any] = Depends(get_current_account),
) -> ProfileOut:
    profile = (account.get("profile") or {})
    return ProfileOut(country=profile.get("country"))


@router.patch("/me/profile", response_model=ProfileOut)
async def patch_my_profile(
    body: ProfilePatchIn,
    account: Dict[str, Any] = Depends(get_current_account),
) -> ProfileOut:
    if body.country is None:
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    new_country = body.country.upper()
    update: Dict[str, Any] = {"profile.country": new_country}

    await db.accounts.update_one({"id": account["id"]}, {"$set": update})
    return ProfileOut(country=new_country)
