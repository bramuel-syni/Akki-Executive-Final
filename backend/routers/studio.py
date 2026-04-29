"""Studio · cross-artefact endpoints (decks, briefings, reports).

iter64 — the merged Decks + Reports surface needs:
  - Read-receipt tracking on every Studio artefact (deduped per
    account-day, like document_engagement.views).
  - Exposure score derived from reader count + shares + age.
  - A single 'history' endpoint that returns every Studio artefact
    (decks + briefings) for a context with sensitivity + exposure
    surfaced inline so the UI can render the strip.
  - On-demand re-scoring endpoint (sensitivity heuristics may evolve).

Pattern mirrors document_engagement.py so the testing agent + ops can
reason about it the same way. Read-tracking is real for all plans;
"information exposure score" surfaces as a marketing differentiator
but is computed for everyone — the gating happens at UI level if we
need to. (User chose option a — "build it now with a real read-receipt
mechanism + visible exposure score on each generated artifact".)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership

logger = logging.getLogger("akki.studio")

router = APIRouter(tags=["studio"])

ARTEFACT_KINDS = {"deck", "briefing"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _days_between(start_iso: str, end_iso: Optional[str] = None) -> int:
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = (datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
               if end_iso else datetime.now(timezone.utc))
        return max(0, (end - start).days)
    except Exception:  # noqa: BLE001
        return 0


async def _resolve_artefact(context_id: str, kind: str, artefact_id: str) -> Dict[str, Any]:
    if kind not in ARTEFACT_KINDS:
        raise HTTPException(status_code=400, detail=f"Unsupported artefact kind: {kind}")
    coll = db.decks if kind == "deck" else db.briefings
    doc = await coll.find_one({"id": artefact_id, "context_id": context_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{kind.title()} not found.")
    return doc


# ---------------------------------------------------------------------------
# Read receipt — POST /api/contexts/{cid}/studio/{kind}/{aid}/view
# ---------------------------------------------------------------------------
@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/view")
async def record_view(
    context_id: str,
    kind: str,
    artefact_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    artefact = await _resolve_artefact(context_id, kind, artefact_id)
    today = _utc_today()
    account_id = ctx["account"]["id"]
    is_owner = artefact.get("account_id") == account_id or artefact.get("created_by") == account_id

    # Upsert one row per (artefact, account, day). Duplicate insert hits the
    # unique index and the resulting Mongo retry pattern gives us idempotency.
    res = await db.studio_views.find_one_and_update(
        {"artefact_kind": kind, "artefact_id": artefact_id,
         "context_id": context_id, "account_id": account_id, "day_utc": today},
        {"$inc": {"view_count": 1},
         "$setOnInsert": {
             "id": str(uuid.uuid4()),
             "first_viewed_at": iso(now()),
             "is_owner": is_owner,
         },
         "$set": {"last_viewed_at": iso(now())}},
        upsert=True,
        return_document=True,
        projection={"_id": 0},
    )
    return {
        "ok": True,
        "deduped": (res or {}).get("view_count", 1) > 1,
        "is_owner": is_owner,
    }


# ---------------------------------------------------------------------------
# Engagement summary — GET /api/contexts/{cid}/studio/{kind}/{aid}/engagement
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/engagement")
async def get_engagement(
    context_id: str,
    kind: str,
    artefact_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    artefact = await _resolve_artefact(context_id, kind, artefact_id)

    # All views — owner views excluded from unique_readers but included in
    # view_count so the artefact creator can see their own check-ins.
    views = await db.studio_views.find(
        {"artefact_kind": kind, "artefact_id": artefact_id, "context_id": context_id},
        {"_id": 0},
    ).to_list(length=500)

    non_owner_views = [v for v in views if not v.get("is_owner")]
    unique_readers = len({v["account_id"] for v in non_owner_views})
    total_view_count = sum((v.get("view_count") or 1) for v in views)

    # Pull reader display names (best-effort, public-safe fields only).
    reader_account_ids = list({v["account_id"] for v in non_owner_views})
    reader_docs = await db.accounts.find(
        {"id": {"$in": reader_account_ids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1},
    ).to_list(length=200) if reader_account_ids else []
    reader_map = {a["id"]: a for a in reader_docs}
    readers = []
    for v in non_owner_views:
        a = reader_map.get(v["account_id"], {})
        readers.append({
            "account_id": v["account_id"],
            "name": a.get("name") or "—",
            "email": a.get("email") or "—",
            "first_viewed_at": v.get("first_viewed_at"),
            "last_viewed_at": v.get("last_viewed_at"),
            "view_count": v.get("view_count", 1),
        })
    readers.sort(key=lambda r: r.get("last_viewed_at") or "", reverse=True)

    # Shares: reuse existing shares collection for briefings; for decks
    # we look at studio_shares (recorded explicitly when a user shares a
    # deck out via the studio share endpoint, optional — defaults to 0).
    shares = await db.studio_shares.count_documents(
        {"artefact_kind": kind, "artefact_id": artefact_id, "context_id": context_id}
    )
    external_shares = await db.studio_shares.count_documents(
        {"artefact_kind": kind, "artefact_id": artefact_id, "context_id": context_id, "external": True}
    )

    # Compute exposure score
    days = _days_between(artefact.get("created_at") or iso(now()))
    from studio_sensitivity import exposure_score
    expo = exposure_score(
        unique_readers=unique_readers,
        share_count=shares,
        external_share_count=external_shares,
        days_since_creation=days,
    )

    return {
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "view_count": total_view_count,
        "unique_readers": unique_readers,
        "readers": readers,
        "share_count": shares,
        "external_share_count": external_shares,
        "exposure": expo,
        "days_since_creation": days,
        "sensitivity": artefact.get("sensitivity"),
    }


# ---------------------------------------------------------------------------
# Share record — POST /api/contexts/{cid}/studio/{kind}/{aid}/share
# ---------------------------------------------------------------------------
class ShareIn(BaseModel):
    to_email: str = Field(min_length=4, max_length=120)
    to_name: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=600)
    external: bool = Field(default=False, description="True if recipient is outside the org")


@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/share")
async def record_share(
    context_id: str,
    kind: str,
    artefact_id: str,
    body: ShareIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    await _resolve_artefact(context_id, kind, artefact_id)
    rec = {
        "id": str(uuid.uuid4()),
        "artefact_kind": kind,
        "artefact_id": artefact_id,
        "context_id": context_id,
        "shared_by": ctx["account"]["id"],
        "to_email": body.to_email.strip().lower(),
        "to_name": body.to_name,
        "message": body.message,
        "external": bool(body.external),
        "created_at": iso(now()),
    }
    await db.studio_shares.insert_one(rec)
    rec.pop("_id", None)
    return rec


# ---------------------------------------------------------------------------
# Re-score — POST /api/contexts/{cid}/studio/{kind}/{aid}/rescore
# ---------------------------------------------------------------------------
@router.post("/api/contexts/{context_id}/studio/{kind}/{artefact_id}/rescore")
async def rescore_sensitivity(
    context_id: str,
    kind: str,
    artefact_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    artefact = await _resolve_artefact(context_id, kind, artefact_id)
    from studio_sensitivity import score_sensitivity
    sensitivity = score_sensitivity(artefact)
    coll = db.decks if kind == "deck" else db.briefings
    await coll.update_one(
        {"id": artefact_id, "context_id": context_id},
        {"$set": {"sensitivity": sensitivity, "sensitivity_rescored_at": iso(now())}},
    )
    return {"sensitivity": sensitivity, "artefact_kind": kind, "artefact_id": artefact_id}


@router.post("/api/contexts/{context_id}/studio/backfill_sensitivity")
async def backfill_sensitivity(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """One-shot backfill — score every deck + briefing in a context that
    doesn't already carry a sensitivity record. Idempotent: artefacts
    that already have `sensitivity` are skipped. Useful after iter64 ships
    so the UI can render the strip on day-1 without waiting for a regen."""
    from studio_sensitivity import score_sensitivity
    scored = {"decks": 0, "briefings": 0}

    async for d in db.decks.find(
        {"context_id": context_id, "sensitivity": {"$exists": False}},
        {"_id": 0},
    ):
        sens = score_sensitivity(d)
        await db.decks.update_one(
            {"id": d["id"], "context_id": context_id},
            {"$set": {"sensitivity": sens, "sensitivity_rescored_at": iso(now())}},
        )
        scored["decks"] += 1

    async for b in db.briefings.find(
        {"context_id": context_id, "sensitivity": {"$exists": False}, "status": {"$ne": "archived"}},
        {"_id": 0},
    ):
        sens = score_sensitivity(b)
        await db.briefings.update_one(
            {"id": b["id"], "context_id": context_id},
            {"$set": {"sensitivity": sens, "sensitivity_rescored_at": iso(now())}},
        )
        scored["briefings"] += 1

    return {"ok": True, "scored": scored}


# ---------------------------------------------------------------------------
# History — GET /api/contexts/{cid}/studio/history
# Returns every deck + briefing for a context with sensitivity + exposure
# folded in, sorted newest-first. Single endpoint the Studio history strip
# can hit.
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/studio/history")
async def studio_history(
    context_id: str,
    limit: int = 30,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    items: List[Dict[str, Any]] = []

    decks_cursor = db.decks.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "title": 1, "intent": 1, "subtitle": 1,
         "created_at": 1, "tier": 1, "sensitivity": 1, "audience": 1,
         "research_question": 1, "account_id": 1},
    ).sort("created_at", -1).limit(limit)
    async for d in decks_cursor:
        items.append({**d, "kind": "deck"})

    briefings_cursor = db.briefings.find(
        {"context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "title": 1, "version": 1, "opening_paragraph": 1,
         "items": 1, "created_at": 1, "sensitivity": 1, "role": 1,
         "mode": 1, "created_by": 1},
    ).sort("created_at", -1).limit(limit)
    async for b in briefings_cursor:
        items.append({
            "id": b.get("id"),
            "title": b.get("title"),
            "intent": (b.get("opening_paragraph") or "")[:200],
            "subtitle": f"{len(b.get('items') or [])} items · v{b.get('version', 1)}",
            "created_at": b.get("created_at"),
            "tier": "standard",
            "sensitivity": b.get("sensitivity"),
            "audience": b.get("role"),
            "research_question": None,
            "account_id": b.get("created_by"),
            "kind": "briefing",
            "mode": b.get("mode"),
        })

    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    items = items[:limit]

    # Cheap fan-out for engagement: for each item we tally view + share
    # counts in a single aggregate pass (one query per collection).
    artefact_ids = [i["id"] for i in items]
    if artefact_ids:
        # Group views by (kind, id, account_id) → unique_readers per artefact
        view_pipeline = [
            {"$match": {"artefact_id": {"$in": artefact_ids}, "context_id": context_id,
                        "is_owner": {"$ne": True}}},
            {"$group": {"_id": {"kind": "$artefact_kind", "id": "$artefact_id",
                                 "acct": "$account_id"}}},
            {"$group": {"_id": {"kind": "$_id.kind", "id": "$_id.id"},
                         "unique_readers": {"$sum": 1}}},
        ]
        readers_by_id: Dict[str, int] = {}
        async for row in db.studio_views.aggregate(view_pipeline):
            readers_by_id[row["_id"]["id"]] = row["unique_readers"]

        share_pipeline = [
            {"$match": {"artefact_id": {"$in": artefact_ids}, "context_id": context_id}},
            {"$group": {"_id": {"id": "$artefact_id"},
                         "shares": {"$sum": 1},
                         "external_shares": {"$sum": {"$cond": ["$external", 1, 0]}}}},
        ]
        shares_by_id: Dict[str, Dict[str, int]] = {}
        async for row in db.studio_shares.aggregate(share_pipeline):
            shares_by_id[row["_id"]["id"]] = {
                "shares": row.get("shares", 0),
                "external_shares": row.get("external_shares", 0),
            }

        from studio_sensitivity import exposure_score
        for it in items:
            uniq = readers_by_id.get(it["id"], 0)
            sh = shares_by_id.get(it["id"], {}).get("shares", 0)
            ext_sh = shares_by_id.get(it["id"], {}).get("external_shares", 0)
            days = _days_between(it.get("created_at") or iso(now()))
            it["exposure"] = exposure_score(
                unique_readers=uniq, share_count=sh,
                external_share_count=ext_sh, days_since_creation=days,
            )
            it["unique_readers"] = uniq

    return {"items": items, "count": len(items)}
