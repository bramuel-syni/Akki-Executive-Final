"""Phase P5.15 — Ideas by Akki router.

Endpoints (all CSRF-protected; tenant-scoped on `account_id`):

  GET  /api/ideas/digest/current                 → this week's digest (lazy-generates if missing)
  GET  /api/ideas/digest/{week_iso}              → historical digest
  GET  /api/ideas/digest/history?limit=12        → up to last 12 weeks
  GET  /api/ideas/preferences                    → caller's preferences (defaults if absent)
  PUT  /api/ideas/preferences                    → upsert caller's preferences
  POST /api/ideas/digest/regenerate              → admin-only force-regenerate current week

Tenant isolation: every query is scoped by `account_id`.
Cross-account access returns 404 (no existence leak).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.ideas_engine import (
    IDEA_LENSES,
    IdeasDigest,
    UserIdeasPreferences,
    get_or_default_preferences,
    synthesize_digest,
    upsert_preferences,
    week_iso_for,
)


router = APIRouter(prefix="/api/ideas", tags=["ideas-by-akki"])


# ─────────────────────────────────────────────────────────────────
# Idempotent core — used by both `current` and `regenerate`
# ─────────────────────────────────────────────────────────────────


async def _get_or_create_digest(
    *, account_id: str, user_id: str, week_iso: Optional[str] = None,
    force_regen: bool = False,
) -> IdeasDigest:
    week_iso = week_iso or week_iso_for()
    if not force_regen:
        existing = await db.ideas_digests.find_one(
            {"account_id": account_id, "week_iso": week_iso,
             "digest_version": "p5.15.0"},
            {"_id": 0},
        )
        if existing:
            return IdeasDigest.model_validate(existing)
    # Apply caller's preferences (custom_instructions + enabled lenses).
    prefs = await get_or_default_preferences(
        db, account_id=account_id, user_id=user_id,
    )
    digest = await synthesize_digest(
        db,
        account_id=account_id,
        user_id=user_id,
        week_iso=week_iso,
        lenses_enabled=prefs.lenses_enabled,
        custom_instructions=prefs.custom_instructions,
    )
    if force_regen:
        # Wipe any prior digest for this week then insert.
        await db.ideas_digests.delete_one(
            {"account_id": account_id, "week_iso": week_iso,
             "digest_version": digest.digest_version},
        )
    await db.ideas_digests.insert_one(digest.model_dump())
    # Append the audit row.
    await db.ideas_audit_log.insert_one({
        "digest_id": digest.id,
        "account_id": account_id,
        "user_id": user_id,
        "week_iso": digest.week_iso,
        "model_id": digest.model_id,
        "shield_invoke_id": digest.shield_invoke_id,
        "citation_count": digest.citation_count,
        "refuse_to_decide_pass_count": digest.refuse_to_decide_pass_count,
        "refuse_to_decide_fail_count": digest.refuse_to_decide_fail_count,
        "dropped_lenses": digest.dropped_lenses,
        "force_regen": force_regen,
        "generated_at": digest.generated_at,
    })
    return digest


# ─────────────────────────────────────────────────────────────────
# GET /digest/current
# ─────────────────────────────────────────────────────────────────


@router.get("/digest/current")
async def get_current_digest(current: Dict[str, Any] = Depends(get_current_account)):
    digest = await _get_or_create_digest(
        account_id=current["id"], user_id=current["id"],
    )
    return digest.model_dump()


# ─────────────────────────────────────────────────────────────────
# GET /digest/history
# ─────────────────────────────────────────────────────────────────


@router.get("/digest/history")
async def get_digest_history(
    limit: int = 12,
    current: Dict[str, Any] = Depends(get_current_account),
):
    limit = max(1, min(int(limit), 52))
    cursor = db.ideas_digests.find(
        {"account_id": current["id"]},
        {"_id": 0, "id": 1, "week_iso": 1, "digest_version": 1,
         "generated_at": 1, "citation_count": 1, "dropped_lenses": 1},
    ).sort("week_iso", -1).limit(limit)
    items = []
    async for row in cursor:
        items.append(row)
    return {"items": items}


# ─────────────────────────────────────────────────────────────────
# GET /digest/{week_iso}
# ─────────────────────────────────────────────────────────────────


@router.get("/digest/{week_iso}")
async def get_specific_digest(
    week_iso: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    # Validate the week_iso shape — `<YYYY>-W<NN>`.
    if not (
        len(week_iso) == 8 and week_iso[4:6] == "-W"
        and week_iso[:4].isdigit() and week_iso[6:].isdigit()
    ):
        raise HTTPException(400, "week_iso_invalid")
    row = await db.ideas_digests.find_one(
        {"account_id": current["id"], "week_iso": week_iso,
         "digest_version": "p5.15.0"},
        {"_id": 0},
    )
    if not row:
        # Note: cross-tenant access lands here too — same 404
        # response shape, no existence leak.
        raise HTTPException(404, "digest_not_found")
    return row


# ─────────────────────────────────────────────────────────────────
# Preferences CRUD
# ─────────────────────────────────────────────────────────────────


class PreferencesPutRequest(BaseModel):
    custom_instructions: str = Field(default="", max_length=2000)
    lenses_enabled: List[str] = Field(default_factory=lambda: list(IDEA_LENSES))


@router.get("/preferences")
async def get_preferences_endpoint(current: Dict[str, Any] = Depends(get_current_account)):
    prefs = await get_or_default_preferences(
        db, account_id=current["id"], user_id=current["id"],
    )
    return prefs.model_dump()


@router.put("/preferences")
async def put_preferences_endpoint(
    body: PreferencesPutRequest,
    current: Dict[str, Any] = Depends(get_current_account),
):
    prefs = await upsert_preferences(
        db,
        account_id=current["id"],
        user_id=current["id"],
        custom_instructions=body.custom_instructions,
        lenses_enabled=body.lenses_enabled,
    )
    return prefs.model_dump()


# ─────────────────────────────────────────────────────────────────
# Admin regenerate
# ─────────────────────────────────────────────────────────────────


def _is_admin(account: Dict[str, Any]) -> bool:
    return (
        account.get("declared_role") in ("admin", "superadmin", "dual")
        or bool(account.get("is_superadmin"))
    )


@router.post("/digest/regenerate")
async def regenerate_current_digest(
    current: Dict[str, Any] = Depends(get_current_account),
):
    if not _is_admin(current):
        raise HTTPException(403, "admin_required")
    digest = await _get_or_create_digest(
        account_id=current["id"],
        user_id=current["id"],
        force_regen=True,
    )
    return digest.model_dump()


__all__ = ["router"]
