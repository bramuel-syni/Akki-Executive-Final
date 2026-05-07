"""Pulse — Phase F.1 (MEMO Item 4) — same-context only.

A Twitter-style signal feed for the *active* context. Cross-context
aggregation requires Privacy Wall completion; that is a separate big
lift and is deliberately deferred per the F.1 brief.

Endpoints
---------
GET  /api/contexts/{cid}/pulse/feed?type=&freshness=&limit=
     Ranked, annotated signal feed scoped to the active context.
     Default filter: type=any, freshness=new+critical.

POST /api/contexts/{cid}/pulse/signals/{sid}/comment
     Body: {note}.  Records a private comment on the signal.

POST /api/contexts/{cid}/pulse/signals/{sid}/share
     Body: {recipients[], note?}.  Records a share intent.

POST /api/contexts/{cid}/pulse/signals/{sid}/save
     Toggle save/unsave for the current user.

POST /api/contexts/{cid}/pulse/signals/{sid}/resolve
     Mark the signal resolved (status → resolved on db.signals).

POST /api/contexts/{cid}/pulse/signals/{sid}/take-to-solva
     Record the action AND mint a Solva v2 session whose intent is
     derived from the signal headline + summary. Returns the new
     session_id so the frontend can navigate to /app/solva/session/<id>.

All endpoints require X-Active-Context (via require_context_membership).
Same-context boundary is the Privacy Wall floor for F.1.

Hash chain — Pulse actions write to `db.signal_actions` and `db.audit_log`
(via write_audit). They do NOT touch the chat hash chain.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership, write_audit

router = APIRouter(prefix="/api")


# ──────────────────────────────────────────────────────────────────────
# Taxonomy & freshness derivation (server-side, deterministic)
# ──────────────────────────────────────────────────────────────────────
# D-002 — 4-class topic taxonomy. Existing db.signals docs predate the
# field, so we derive at read time from headline + summary keywords.
_TOPIC_PATTERNS: List[tuple] = [
    ("capital",     re.compile(r"\b(covenant|capital|headroom|cash|liquidity|"
                               r"funding|concentration|exposure|debt|gearing)\b", re.I)),
    ("succession",  re.compile(r"\b(succession|leadership|departure|ceo|cfo|coo|"
                               r"chair|board\-?level|talent|key person)\b", re.I)),
    ("regulatory",  re.compile(r"\b(regulator|regulation|compliance|disclosure|audit|"
                               r"breach.*regulation|sanction|sox|pcaob|ifrs|gaap)\b", re.I)),
    ("cyber",       re.compile(r"\b(cyber|ransomware|breach|incident|data leak|"
                               r"phishing|attack|exploit|vulnerab)\w*", re.I)),
]


def _derive_topic_class(text: str) -> str:
    t = text or ""
    for label, pat in _TOPIC_PATTERNS:
        if pat.search(t):
            return label
    return "other"


# Memo Item 4 freshness dimension — five values plus the implicit
# "Resolved" for status==resolved. We compute on-the-fly from
# created_at + signal.type + confidence.
_NEW_DAYS = 7        # any signal newer than 7 days is "new"
_OLD_DAYS = 30       # ≥ 30 days = "old-but-unresolved"
_CRIT_HEADLINE_RE = re.compile(
    r"\b(critical|urgent|breach|loss|default|fraud|material)\b", re.I,
)


def _derive_freshness(signal: Dict[str, Any]) -> str:
    """Return one of:
        new | critical | old-but-unresolved | nice-to-look-into |
        for-tracking-purposes | resolved
    """
    if signal.get("status") in ("resolved",):
        return "resolved"
    headline = signal.get("headline") or ""
    summary = signal.get("summary") or ""
    text = f"{headline} {summary}"
    sig_type = (signal.get("type") or "").lower()
    confidence = signal.get("confidence")
    confidence = float(confidence) if isinstance(confidence, (int, float)) else 0.0

    is_critical = (
        sig_type == "risk" and (confidence >= 0.8 or _CRIT_HEADLINE_RE.search(text))
    )
    if is_critical:
        return "critical"

    # Age in days.
    created_at = signal.get("created_at") or ""
    try:
        # Mongo stores ISO strings; tolerate both Z and +00:00 suffixes.
        ts = datetime.fromisoformat((created_at or "").replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        ts = None
    age_days: Optional[float] = None
    if ts is not None:
        age_days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0

    if age_days is not None and age_days < _NEW_DAYS:
        return "new"
    if age_days is not None and age_days >= _OLD_DAYS:
        return "old-but-unresolved"

    if sig_type == "opportunity" and confidence < 0.7:
        return "nice-to-look-into"
    return "for-tracking-purposes"


# Map db.signals.type → MEMO Item 4 surface tag
_TYPE_TO_TAG = {
    "risk":        "risk",
    "opportunity": "opportunity",
    "gap":         "recommendation",
    "neutral":     "recommendation",
}


def _surface_type(signal_type: Optional[str]) -> str:
    return _TYPE_TO_TAG.get((signal_type or "").lower(), "recommendation")


def _signal_kind(signal: Dict[str, Any]) -> str:
    """Pulse card chip — kind == surface_type for now (Phase F.1)."""
    return _surface_type(signal.get("type"))


# ──────────────────────────────────────────────────────────────────────
# GET /api/contexts/{cid}/pulse/feed
# ──────────────────────────────────────────────────────────────────────
_VALID_TYPE_FILTERS = {"risk", "opportunity", "recommendation", "any"}
# Default freshness per brief: New + Critical.
_DEFAULT_FRESHNESS = ("new", "critical")
_VALID_FRESHNESS = (
    "new", "critical", "old-but-unresolved", "nice-to-look-into",
    "for-tracking-purposes", "resolved", "any",
)


def _parse_freshness(arg: Optional[str]) -> List[str]:
    if not arg:
        return list(_DEFAULT_FRESHNESS)
    parts = [p.strip().lower() for p in arg.split(",") if p.strip()]
    parts = [p for p in parts if p in _VALID_FRESHNESS]
    if not parts:
        return list(_DEFAULT_FRESHNESS)
    if "any" in parts:
        return list(_VALID_FRESHNESS)
    return parts


def _parse_type(arg: Optional[str]) -> str:
    if not arg:
        return "any"
    arg = arg.strip().lower()
    return arg if arg in _VALID_TYPE_FILTERS else "any"


@router.get("/contexts/{context_id}/pulse/feed")
async def pulse_feed(
    context_id: str,
    type: Optional[str] = None,         # noqa: A002 — public query name
    freshness: Optional[str] = None,
    limit: int = 100,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Same-context Twitter-style signal feed."""
    type_arg = _parse_type(type)
    freshness_arg = _parse_freshness(freshness)

    # Pull all signals (default and resolved both — we then filter via
    # freshness server-side based on derived classifiers).
    sigs = await db.signals.find(
        {"context_id": context_id, "status": {"$in": ["active", "resolved"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(min(max(limit, 1), 500))

    me_acct = ctx["account"]["id"]
    cards: List[Dict[str, Any]] = []
    for s in sigs:
        topic = _derive_topic_class(f"{s.get('headline') or ''} {s.get('summary') or ''}")
        fresh = _derive_freshness(s)
        kind = _signal_kind(s)
        surface_type = _surface_type(s.get("type"))

        # Filter by query params.
        if type_arg != "any" and surface_type != type_arg:
            continue
        if fresh not in freshness_arg:
            continue

        # Annotate with current-user signal_actions counters.
        actions = await db.signal_actions.find(
            {"signal_id": s["id"], "context_id": context_id}, {"_id": 0},
        ).to_list(500)
        my_saved = any(
            a.get("action_type") == "saved" and a.get("account_id") == me_acct
            for a in actions
        )
        comments = [a for a in actions if a.get("action_type") == "commented"]
        shares = [a for a in actions if a.get("action_type") == "shared"]
        resolved_action = next(
            (a for a in actions if a.get("action_type") == "resolved"), None,
        )
        cards.append({
            "id": s["id"],
            "headline": s.get("headline") or "(untitled)",
            "summary": s.get("summary") or "",
            "type": s.get("type"),
            "surface_type": surface_type,
            "signal_kind": kind,
            "topic_class": topic,
            "freshness": fresh,
            "confidence": s.get("confidence"),
            "data_trust": s.get("data_trust"),
            "created_at": s.get("created_at"),
            "status": s.get("status"),
            "references": s.get("references", []) or s.get("sources", []),
            "actions_summary": {
                "my_saved": my_saved,
                "comments_count": len(comments),
                "shares_count": len(shares),
                "resolved": resolved_action is not None,
                "resolved_at": (resolved_action or {}).get("created_at"),
            },
        })

    return {
        "filters": {
            "type": type_arg,
            "freshness": freshness_arg,
        },
        "total": len(cards),
        "cards": cards,
    }


# ──────────────────────────────────────────────────────────────────────
# POST endpoints — engagement actions
# ──────────────────────────────────────────────────────────────────────
class CommentIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class ShareIn(BaseModel):
    recipients: List[str] = Field(default_factory=list)
    note: Optional[str] = Field(default=None, max_length=600)


async def _load_signal_or_404(signal_id: str, context_id: str) -> Dict[str, Any]:
    sig = await db.signals.find_one(
        {"id": signal_id, "context_id": context_id}, {"_id": 0},
    )
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    return sig


async def _record_action(
    *, signal_id: str, context_id: str, account_id: str,
    action_type: str, payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = payload or {}
    doc = {
        "id": str(uuid.uuid4()),
        "signal_id": signal_id,
        "context_id": context_id,
        "account_id": account_id,
        "action_type": action_type,
        "channel": "pulse",
        "created_at": iso(now()),
        **payload,
    }
    await db.signal_actions.insert_one(doc)
    doc.pop("_id", None)
    try:
        await write_audit(
            context_id, account_id,
            f"pulse.signal.{action_type}", "signal", signal_id,
            {k: v for k, v in payload.items() if k != "note"},
        )
    except Exception:  # noqa: BLE001
        pass
    return doc


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/comment")
async def pulse_comment(
    context_id: str, signal_id: str, body: CommentIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    await _load_signal_or_404(signal_id, context_id)
    return await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="commented",
        payload={"note": body.note.strip()},
    )


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/share")
async def pulse_share(
    context_id: str, signal_id: str, body: ShareIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    await _load_signal_or_404(signal_id, context_id)
    recipients = [r.strip() for r in (body.recipients or []) if r.strip()]
    return await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="shared",
        payload={"recipients": recipients,
                 "note": (body.note or "").strip() or None},
    )


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/save")
async def pulse_save(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Toggle save: if a `saved` row exists for this user+signal, delete
    it (unsave); otherwise create one (save)."""
    await _load_signal_or_404(signal_id, context_id)
    existing = await db.signal_actions.find_one(
        {
            "signal_id": signal_id, "context_id": context_id,
            "account_id": ctx["account"]["id"], "action_type": "saved",
        }, {"_id": 0},
    )
    if existing:
        await db.signal_actions.delete_many(
            {
                "signal_id": signal_id, "context_id": context_id,
                "account_id": ctx["account"]["id"], "action_type": "saved",
            },
        )
        try:
            await write_audit(
                context_id, ctx["account"]["id"],
                "pulse.signal.unsaved", "signal", signal_id, {},
            )
        except Exception:
            pass
        return {"saved": False, "signal_id": signal_id}
    doc = await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="saved", payload={},
    )
    return {"saved": True, "signal_id": signal_id, "action": doc}


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/resolve")
async def pulse_resolve(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Mark signal resolved — flips db.signals.status and logs the action."""
    await _load_signal_or_404(signal_id, context_id)
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id},
        {"$set": {"status": "resolved",
                  "resolved_at": iso(now()),
                  "resolved_by": ctx["account"]["id"]}},
    )
    return await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="resolved", payload={},
    )


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/take-to-solva")
async def pulse_take_to_solva(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Record the action AND mint a Solva v2 session whose intent is
    derived from the signal headline+summary. Returns the new
    session_id; the frontend then navigates to
    /app/solva/session/<session_id>.

    We re-use the canonical solva_v2 entrypoint via a programmatic
    construct on db.solva_v2_sessions so we don't run an HTTP roundtrip
    against ourselves. The session is tagged `from_signal=<sid>` so the
    Solva surface can render the framing chip."""
    sig = await _load_signal_or_404(signal_id, context_id)

    headline = sig.get("headline") or ""
    summary = sig.get("summary") or ""
    intent = (
        f"Signal from Pulse — {headline}".strip() +
        (f"\n\n{summary}" if summary else "")
    )

    # Programmatic session insertion. Mirrors the minimal shape the
    # Solva v2 router writes; full priming (cluster resolve, prime
    # turn, guardrail) runs lazily on the first /turn call. Until
    # then, the session is "active" and visible in /me/review-queue.
    session_id = str(uuid.uuid4())
    rec = {
        "id": session_id,
        "account_id": ctx["account"]["id"],
        "context_id": context_id,
        "version": 2,
        "schema_version": 5,
        "submodule": "develop_strategy",
        "persona": None,
        "parent_session_id": None,
        "cluster_id": None,            # auto-resolved on first turn
        "cluster_label": None,
        "cluster_resolution": "deferred",
        "intent": intent[:2000],
        "layer": "framing",
        "layer_index": 0,
        "status": "active",
        "pro_tier": False,
        "pro_account": False,
        "sandbox": False,
        "turns": [],
        "reasoning_audit_log": [],
        "synthesis": None,
        "reflection": None,
        "lockin": None,
        "jailbreak_soft_count": 0,
        "started_at": iso(now()),
        "updated_at": iso(now()),
        "completed_at": None,
        # Pulse-take-to-solva markers
        "from_signal": signal_id,
        "from_pulse": True,
    }
    await db.solva_v2_sessions.insert_one(rec)

    action = await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="take_to_solva",
        payload={"solva_session_id": session_id},
    )
    return {
        "ok": True,
        "signal_id": signal_id,
        "solva_session_id": session_id,
        "action": action,
    }
