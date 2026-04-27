"""Signal actions — track Act-on / Share with per-signal indicators.

The user feedback was explicit: "'Act on this' and 'Share' functionality
feel similar — the difference isn't clear. Have AKKI suggest concrete next
steps under 'Act on this'. Track which recommendation was acted on, not
just whether something happened. Also: 'Shared with N people'."

This module provides:
  GET  /api/contexts/{cid}/signals/{sid}/recommendations
       Three concrete next-step suggestions, derived from signal type/tone.
       No LLM call — deterministic templates so the user can act in one tap.
  POST /api/contexts/{cid}/signals/{sid}/actions
       Log an act/share action. Body: {action_type, recommendation_idx?,
       recommendation_label?, recipients?, note?}.
  GET  /api/contexts/{cid}/signals/{sid}/actions
       List actions taken on this signal (used to render indicators).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership, write_audit

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Recommendation templates, indexed by signal type/tone. Each item is a
# concrete one-tap action a NED/exec can take. The `label` is what appears
# in the dropdown; `note` is the default body if the user opts to share.
# ---------------------------------------------------------------------------
_RECS_BY_TYPE: Dict[str, List[Dict[str, str]]] = {
    "risk": [
        {"label": "Forward to risk-committee chair · 48h response window",
         "note":  "I want this on the risk committee's agenda this week with a response from the named owner within 48 hours."},
        {"label": "Add to my next briefing under Risk · ask the question on the floor",
         "note":  "Bring this risk into the next pre-read; I want to put the sharpest version of the question to management directly."},
        {"label": "Request a one-page mitigation memo from the responsible exec",
         "note":  "Could the named owner draft a one-pager on what would change if this risk crystallised? No more than one page."},
    ],
    "opportunity": [
        {"label": "Forward to commercial lead · ask for a sizing memo",
         "note":  "Worth a sizing memo before next month's strategy session. What's the 1-year + 3-year revenue if we move?"},
        {"label": "Add as a strategy item for the next board briefing",
         "note":  "Put this in front of the board with the resource ask and the decision criteria."},
        {"label": "Pose to management as: 'What's stopping us from acting on this?'",
         "note":  "I want a candid management response on what's stopping us — capital, talent, conviction, or something else."},
    ],
    "gap": [
        {"label": "Request the missing data from the named owner · 5-day SLA",
         "note":  "We can't act on this without the data. Asking the named owner to surface it within 5 working days."},
        {"label": "Add to my next briefing under Open questions",
         "note":  "Bring this into the briefing as an explicit open question for management to close."},
        {"label": "Share with the audit/finance chair to challenge management",
         "note":  "This is a gap the audit/finance chair should put on management's plate at the next session."},
    ],
    "neutral": [
        {"label": "Add to my next briefing as context for the chair",
         "note":  "Surface this as colour for the chair's opening — no immediate action required."},
        {"label": "Forward to the relevant committee chair for awareness",
         "note":  "Sharing for awareness — no decision needed but relevant to your committee."},
        {"label": "Save as a watch-item in my pipeline",
         "note":  "Putting this on my watch list — circle back if things shift."},
    ],
}


def _classify_signal(sig: Dict[str, Any]) -> str:
    """Pick the best recommendation bucket for a signal. We accept a few
    fields the producers have used historically — `tone`, `kind`, `signal_type`
    — and fall back to a keyword sniff on the headline."""
    for k in ("kind", "tone", "signal_type", "category"):
        v = (sig.get(k) or "").lower()
        if v in _RECS_BY_TYPE:
            return v
    head = (sig.get("headline") or "").lower()
    if any(w in head for w in ("risk", "exposure", "breach", "loss", "default", "fraud")):
        return "risk"
    if any(w in head for w in ("opportunity", "growth", "win", "expand", "upside", "tail-wind")):
        return "opportunity"
    if any(w in head for w in ("gap", "missing", "unclear", "no data", "undisclosed")):
        return "gap"
    return "neutral"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/contexts/{context_id}/signals/{signal_id}/recommendations")
async def get_signal_recommendations(
    signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    sig = await db.signals.find_one(
        {"id": signal_id, "context_id": ctx["context"]["id"]},
        {"_id": 0, "headline": 1, "tone": 1, "kind": 1, "signal_type": 1, "category": 1},
    )
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    bucket = _classify_signal(sig)
    return {
        "bucket": bucket,
        "recommendations": _RECS_BY_TYPE[bucket],
    }


class SignalActionIn(BaseModel):
    action_type: str = Field(pattern=r"^(acted|shared)$")
    recommendation_idx: Optional[int] = Field(default=None, ge=0, le=10)
    recommendation_label: Optional[str] = Field(default=None, max_length=200)
    recipients: Optional[List[str]] = None
    note: Optional[str] = Field(default=None, max_length=600)


@router.post("/contexts/{context_id}/signals/{signal_id}/actions")
async def create_signal_action(
    signal_id: str,
    body: SignalActionIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Log an action taken on a signal. Idempotent only at the audit-trail
    level — a user can act twice and we record both, so the indicator shows
    the latest attribution while the audit shows the full history.
    """
    sig = await db.signals.find_one(
        {"id": signal_id, "context_id": ctx["context"]["id"]},
        {"_id": 0, "id": 1, "headline": 1},
    )
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")

    rec_idx = body.recommendation_idx
    rec_label = (body.recommendation_label or "").strip() or None
    if rec_label is None and rec_idx is not None:
        # Resolve label from the templates so the indicator can display it
        # even if the client didn't echo it back.
        bucket = _classify_signal({"headline": sig.get("headline")})
        recs = _RECS_BY_TYPE[bucket]
        if 0 <= rec_idx < len(recs):
            rec_label = recs[rec_idx]["label"]

    doc = {
        "id": str(uuid.uuid4()),
        "signal_id": signal_id,
        "context_id": ctx["context"]["id"],
        "account_id": ctx["account"]["id"],
        "actor_email": (ctx["account"].get("email") or "").lower() or None,
        "action_type": body.action_type,
        "recommendation_idx": rec_idx,
        "recommendation_label": rec_label,
        "recipients": [r.strip() for r in (body.recipients or []) if r.strip()],
        "note": (body.note or "").strip() or None,
        "created_at": iso(now()),
    }
    await db.signal_actions.insert_one(doc)
    doc.pop("_id", None)

    await write_audit(
        ctx["context"]["id"], ctx["account"]["id"],
        f"signal.{body.action_type}", "signal", signal_id,
        {"recommendation_idx": rec_idx, "recommendation_label": rec_label,
         "recipients": doc["recipients"]},
    )
    return doc


@router.get("/contexts/{context_id}/signals/{signal_id}/actions")
async def list_signal_actions(
    signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return the action log for a signal so the card can render indicators
    ('Acted on: <label>' / 'Shared with N people'). Most-recent first."""
    cursor = db.signal_actions.find(
        {"signal_id": signal_id, "context_id": ctx["context"]["id"]},
        {"_id": 0},
    ).sort("created_at", -1)
    actions = [a async for a in cursor]

    last_acted = next((a for a in actions if a["action_type"] == "acted"), None)
    shared = [a for a in actions if a["action_type"] == "shared"]
    share_recipients: set = set()
    for s in shared:
        share_recipients.update(s.get("recipients") or [])

    return {
        "actions": actions,
        "summary": {
            "acted": last_acted is not None,
            "last_acted_label": (last_acted or {}).get("recommendation_label"),
            "last_acted_at": (last_acted or {}).get("created_at"),
            "shared_count": len(share_recipients),
            "shared_with": sorted(share_recipients),
        },
    }
