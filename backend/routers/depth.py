"""Depth-status endpoint — Phase 6 / Advisory 8.

Drives the "depth disclosure" UX: hide Lens / Simulate / Influence Map /
Monitor from the left rail until the user has accumulated enough corpus
to make them useful, then surface ONE sector-mapped offer on Home v2.

Eligibility: ≥3 documents OR ≥1 briefing across any of the user's
active contexts. Once crossed, the flag is sticky (there is nothing
here to un-crossover; future work may re-evaluate dismissals).

Pro-gating (Lens + Simulate) is handled in the frontend — this endpoint
only tells the UI which features the gate applies to (`pro_features`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from core import db, get_current_account, iso as _iso, now as _now, write_audit

router = APIRouter(prefix="/api/me/depth-status", tags=["depth"])

DOCS_REQUIRED = 3
BRIEFINGS_REQUIRED = 1

# Pro-gated depth features. Changing this list is a product decision —
# keep in sync with `ProPill`/`UpgradeModal` usage on the frontend.
PRO_FEATURES: List[str] = ["lens", "simulate"]

# Sector → lens mapping. Defaults to audit_committee for everything the
# mapper doesn't explicitly know about (public sector, industrials, retail
# etc.). Case-insensitive match on whole token and on substring.
# The lens_id here is what LensRoom's auto-select is expected to pick up
# via the `?lens=` query param.
SECTOR_TO_LENS = [
    (("banking", "financial-services", "financial services", "fintech", "finance"),
     {"lens_id": "risk", "lens_label": "Risk Lens"}),
    (("saas", "software", "tech", "technology", "software-as-a-service"),
     {"lens_id": "growth", "lens_label": "Growth Lens"}),
    (("healthcare", "pharma", "biotech", "health", "medtech", "pharmaceutical"),
     {"lens_id": "compliance", "lens_label": "Compliance Lens"}),
]
DEFAULT_LENS = {"lens_id": "audit_committee", "lens_label": "Audit Committee Lens"}


def _lens_for_sector(sector: Optional[str]) -> Dict[str, str]:
    s = (sector or "").strip().lower()
    if not s:
        return {**DEFAULT_LENS, "sector_basis": "other"}
    for keys, lens in SECTOR_TO_LENS:
        for k in keys:
            if k == s or k in s:
                return {**lens, "sector_basis": s}
    return {**DEFAULT_LENS, "sector_basis": s}


async def _primary_sector(account_id: str) -> Optional[str]:
    """The 'primary' context is the oldest active membership — same
    choice `first_session` uses for context provisioning fallback."""
    m = await db.memberships.find_one(
        {"account_id": account_id, "status": "active"},
        {"_id": 0, "context_id": 1},
        sort=[("created_at", 1)],
    )
    if not m:
        return None
    ctx = await db.contexts.find_one(
        {"id": m["context_id"]}, {"_id": 0, "sector": 1}
    )
    return (ctx or {}).get("sector")


async def _build_status(current: Dict[str, Any]) -> Dict[str, Any]:
    # Gather the user's active context ids.
    ctx_ids = [
        m["context_id"] async for m in db.memberships.find(
            {"account_id": current["id"], "status": "active"},
            {"_id": 0, "context_id": 1},
        )
    ]
    if ctx_ids:
        docs_count = await db.documents.count_documents(
            {"context_id": {"$in": ctx_ids}}
        )
        briefings_count = await db.briefings.count_documents(
            {"context_id": {"$in": ctx_ids}, "status": {"$ne": "archived"}}
        )
    else:
        docs_count = 0
        briefings_count = 0

    # threshold_met_via — prefer briefings (higher-signal milestone) when
    # both apply.
    threshold_met_via: Optional[str] = None
    if briefings_count >= BRIEFINGS_REQUIRED:
        threshold_met_via = "briefings"
    elif docs_count >= DOCS_REQUIRED:
        threshold_met_via = "docs"
    eligible = threshold_met_via is not None

    offer_dismissed = bool(current.get("depth_offer_dismissed_at"))

    suggested_offer: Optional[Dict[str, Any]] = None
    if eligible:
        sector = await _primary_sector(current["id"])
        lens = _lens_for_sector(sector)
        suggested_offer = {
            "feature": "lens",
            "lens_id": lens["lens_id"],
            "lens_label": lens["lens_label"],
            "sector_basis": lens["sector_basis"],
        }

    return {
        "eligible": eligible,
        "threshold": {
            "docs_count": docs_count,
            "briefings_count": briefings_count,
            "threshold_met_via": threshold_met_via,
            "docs_required": DOCS_REQUIRED,
            "briefings_required": BRIEFINGS_REQUIRED,
        },
        "suggested_offer": suggested_offer,
        "offer_dismissed": offer_dismissed,
        "pro_features": PRO_FEATURES,
    }


@router.get("")
async def get_depth_status(current: Dict[str, Any] = Depends(get_current_account)):
    return await _build_status(current)


@router.post("/dismiss")
async def dismiss_offer(current: Dict[str, Any] = Depends(get_current_account)):
    """Sticky dismissal — flag persists until manually cleared from
    `db.accounts.{id}.depth_offer_dismissed_at`. For v1 we don't re-offer
    after dismissal; future work can ratchet the offer on a new threshold
    milestone."""
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"depth_offer_dismissed_at": _iso(_now())}},
    )
    await write_audit(
        None, current["id"], "depth_status.offer_dismissed",
        "account", current["id"], {},
    )
    # Re-hydrate the account so the returned status reflects the update.
    refreshed = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return await _build_status(refreshed or current)
