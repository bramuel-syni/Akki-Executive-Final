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
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
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
    state: Optional[str] = "active",    # Phase G.1 — lifecycle tab
    show_low: bool = False,             # Phase G.2 — confidence floor toggle
    confidence: Optional[str] = None,   # Phase G.2 — explicit confidence filter
    limit: Optional[int] = None,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Same-context Twitter-style signal feed.

    Phase G additions:
      • `state` query (default 'active') filters by db.signals.state ∈
        {active, bookmarked, resolved, archived}. Falls back to legacy
        `status` field for un-migrated rows.
      • `show_low=true` opts in to low-confidence signals on the
        Active tab. Other tabs always include all confidence levels.
      • `confidence=high|medium|low` is an explicit filter.
      • Default landing limit is 7 for Active (spec §6 volume restraint).
        Other states default to 50.
      • Cards carry `comments[]` inline (G.5 closes PL-01) and
        `reasoning` so the drawer can render the spec's Reasoning
        section without a second roundtrip.
    """
    type_arg = _parse_type(type)
    freshness_arg = _parse_freshness(freshness)
    state_arg = (state or "active").lower()
    if state_arg not in ("active", "bookmarked", "resolved", "archived"):
        state_arg = "active"

    # Volume restraint per spec §6 — Active tab caps to 7 by default;
    # other tabs to 50. Caller can override with limit param (max 200).
    if limit is None:
        limit = 7 if state_arg == "active" else 50
    limit = max(1, min(int(limit), 200))

    # Query layer: prefer the new `state` field, fall back to `status`.
    # Old rows (pre-G.1 migration) may have only `status='active'` —
    # the $or below matches both cleanly.
    if state_arg == "active":
        state_filter = {"$or": [
            {"state": "active"},
            {"state": {"$exists": False}, "status": {"$in": ["active", None]}},
        ]}
    elif state_arg == "resolved":
        state_filter = {"$or": [
            {"state": "resolved"},
            {"state": {"$exists": False}, "status": "resolved"},
        ]}
    else:
        state_filter = {"state": state_arg}

    base_query = {"context_id": context_id, **state_filter}

    sigs = await db.signals.find(base_query, {"_id": 0})\
        .sort("created_at", -1).to_list(500)

    # Phase G.3 — priority sort on Active landing: confidence × recency.
    # high=3, medium=2, low=1. Within the same confidence bucket the newer
    # signal wins. Other tabs keep recency-only ordering.
    if state_arg == "active":
        _CONF_RANK = {"high": 3, "medium": 2, "low": 1}
        sigs.sort(
            key=lambda s: (
                _CONF_RANK.get((s.get("confidence") or "medium").lower(), 2),
                s.get("created_at") or "",
            ),
            reverse=True,
        )

    me_acct = ctx["account"]["id"]
    cards: List[Dict[str, Any]] = []
    for s in sigs:
        topic = _derive_topic_class(f"{s.get('headline') or ''} {s.get('summary') or ''}")
        fresh = _derive_freshness(s)
        kind = _signal_kind(s)
        surface_type = _surface_type(s.get("type"))
        sig_confidence = (s.get("confidence") or "medium").lower()

        # Phase G.2 — refusal floor. The Active tab hides low-confidence
        # signals unless the user explicitly opts in via show_low=true.
        if state_arg == "active" and sig_confidence == "low" and not show_low:
            continue
        # Explicit confidence filter override.
        if confidence in ("high", "medium", "low") and sig_confidence != confidence:
            continue

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
        action_comments = [a for a in actions if a.get("action_type") == "commented"]
        shares = [a for a in actions if a.get("action_type") == "shared"]
        resolved_action = next(
            (a for a in actions if a.get("action_type") == "resolved"), None,
        )

        # Phase G.5 — comments are now stored on the signal itself.
        # Legacy comments from signal_actions are surfaced too so
        # nothing is lost on the QA-brief PL-01 cleanup pass.
        own_comments = [c for c in (s.get("comments") or [])
                        if c.get("account_id") == me_acct]

        cards.append({
            "id": s["id"],
            "headline": s.get("headline") or "(untitled)",
            "summary": s.get("summary") or "",
            "body": s.get("body") or "",
            "reasoning": s.get("reasoning") or "",  # G.4 drawer reads this
            "type": s.get("type"),
            "surface_type": surface_type,
            "signal_kind": kind,
            "topic_class": topic,
            "freshness": fresh,
            "confidence": sig_confidence,
            "data_trust": s.get("data_trust"),
            "merge_count": s.get("merge_count", 1),
            "created_at": s.get("created_at"),
            "state": s.get("state") or s.get("status") or "active",
            "status": s.get("status"),
            "bookmarked_at": s.get("bookmarked_at"),
            "resolved_at": s.get("resolved_at"),
            "resolution_note": s.get("resolution_note"),
            "comments": own_comments,
            "references": s.get("references", []) or s.get("sources", []),
            "actions_summary": {
                "my_saved": my_saved,
                "comments_count": len(action_comments) + len(own_comments),
                "shares_count": len(shares),
                "resolved": resolved_action is not None or (s.get("state") == "resolved"),
                "resolved_at": s.get("resolved_at") or (resolved_action or {}).get("created_at"),
            },
        })
        if len(cards) >= limit:
            break

    # Phase G1 (2026-05-11) — defensive Synisense shield pass on
    # rendered text. Same-context pulse_feed is NOT a wall boundary
    # crossing (the caller is a member of `context_id`), so this is
    # opt-in via env `PULSE_SHIELD_TEXT=true`. When enabled, every
    # headline+summary+body+reasoning goes through `surface="pulse"`
    # before reaching the client. Off by default in dev to avoid
    # 50-100ms per-call Synisense latency. Production toggle when
    # ops is comfortable.
    if os.environ.get("PULSE_SHIELD_TEXT", "false").lower() in ("true", "1", "yes"):
        from services.privacy_wall import redact_for_pulse_text_async
        for c in cards:
            for f in ("headline", "summary", "body", "reasoning"):
                if c.get(f):
                    c[f] = await redact_for_pulse_text_async(c[f]) or c[f]

    return {
        "filters": {
            "type": type_arg,
            "freshness": freshness_arg,
            "state": state_arg,
            "show_low": show_low,
            "confidence": confidence,
        },
        "limit": limit,
        "total": len(cards),
        "cards": cards,
    }


# ──────────────────────────────────────────────────────────────────────
# GET /api/contexts/{cid}/pulse/across-boards — Phase E.0.3
# ──────────────────────────────────────────────────────────────────────
# Cross-board metadata aggregator. Reads ONLY db.context_metadata_signatures.
# NEVER touches db.signals, db.documents, db.chat_messages, or any payload
# collection from a non-active context. NEVER returns source_artefact_id,
# source-board name, or any other field that would identify the source
# tenant.
#
# Response shape — metadata only:
#   {
#     "patterns": [
#       {
#         "signature_kind": "regulatory_ref",
#         "signature_value": "GDPR Art.17",
#         "other_boards_count": 3,           # distinct OTHER context_ids
#         "active_board_count": 2,            # active board's own count
#         "last_seen_other": "ISO-8601",      # most recent across other boards
#         "first_seen_other": "ISO-8601",
#       },
#       ...
#     ],
#     "window_days": 30,
#     "active_board_signature_count": int,
#     "leakage_check": "metadata_only"
#   }
#
# The active_board_count surfaces ONLY the user's own context's matches
# so they can see "this matches what your board already flagged" — a
# useful framing without identifying who else flagged it.
from datetime import datetime as _dt, timedelta as _td

_AGGREGATOR_WINDOW_DAYS = 30


@router.get("/contexts/{context_id}/pulse/across-boards")
async def pulse_across_boards(
    context_id: str,
    window_days: int = _AGGREGATOR_WINDOW_DAYS,
    min_other_boards: int = 1,
    limit: int = 50,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return cross-board metadata patterns visible from the active
    context's perspective. Privacy Wall:
      • Reads ONLY db.context_metadata_signatures.
      • Filters out the active context's own rows from the OTHER-BOARDS
        count.
      • NEVER returns source_artefact_id, context_id-of-source, or any
        identifier of the originating tenant.
      • Active-board's OWN signatures are surfaced as `active_board_count`
        so the user sees their board's match alongside the others'.
    """
    win = max(1, min(int(window_days or _AGGREGATOR_WINDOW_DAYS), 365))
    cutoff = (_dt.now(timezone.utc) - _td(days=win)).isoformat().replace("+00:00", "Z")

    # 1. Pull the active board's own signatures within window.
    own = await db.context_metadata_signatures.find(
        {"context_id": context_id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "signature_kind": 1, "signature_value": 1, "created_at": 1},
    ).to_list(5000)

    own_pairs: set = set()
    own_count_by_value: Dict[tuple, int] = {}
    for r in own:
        key = (r["signature_kind"], r["signature_value"])
        own_pairs.add(key)
        own_count_by_value[key] = own_count_by_value.get(key, 0) + 1

    # 2. For each unique (kind, value) the active board has, look up
    #    OTHER boards' rows in window. Aggregator never touches any
    #    payload collection.
    patterns: List[Dict[str, Any]] = []
    for (kind, value) in sorted(own_pairs):
        # Cross-board lookup — explicitly EXCLUDE the active context_id.
        # No content fields shipped; we project only what the response
        # needs and run distinct() over context_id to count boards
        # without listing them.
        other_rows = await db.context_metadata_signatures.find(
            {
                "signature_kind": kind,
                "signature_value": value,
                "created_at": {"$gte": cutoff},
                "context_id": {"$ne": context_id},
            },
            {"_id": 0, "context_id": 1, "created_at": 1},
        ).to_list(5000)
        if not other_rows:
            continue
        # Distinct OTHER boards.
        other_ctx_ids = {r["context_id"] for r in other_rows if r.get("context_id")}
        if len(other_ctx_ids) < max(1, int(min_other_boards or 1)):
            continue
        timestamps = sorted(r["created_at"] for r in other_rows if r.get("created_at"))
        patterns.append({
            "signature_kind": kind,
            "signature_value": value,
            "other_boards_count": len(other_ctx_ids),
            "active_board_count": own_count_by_value.get((kind, value), 0),
            "first_seen_other": timestamps[0] if timestamps else None,
            "last_seen_other": timestamps[-1] if timestamps else None,
        })

    # 3. Also surface signatures present on OTHER boards but NOT yet
    #    on the active board — useful "you might want to look at" tile.
    #    Same metadata-only contract.
    if len(patterns) < int(limit or 50):
        cursor = db.context_metadata_signatures.aggregate([
            {"$match": {
                "created_at": {"$gte": cutoff},
                "context_id": {"$ne": context_id},
            }},
            {"$group": {
                "_id": {"k": "$signature_kind", "v": "$signature_value"},
                "boards": {"$addToSet": "$context_id"},
                "first_seen": {"$min": "$created_at"},
                "last_seen": {"$max": "$created_at"},
            }},
            {"$match": {"boards.1": {"$exists": True}}},  # ≥ 2 boards
            {"$limit": 200},
        ])
        async for g in cursor:
            kind  = g["_id"]["k"]
            value = g["_id"]["v"]
            if (kind, value) in own_pairs:
                continue  # already covered
            patterns.append({
                "signature_kind": kind,
                "signature_value": value,
                "other_boards_count": len(g["boards"]),
                "active_board_count": 0,
                "first_seen_other": g.get("first_seen"),
                "last_seen_other": g.get("last_seen"),
            })
            if len(patterns) - 0 >= int(limit or 50):
                break

    # 4. Sort by signal strength (other_boards_count desc, then recency).
    patterns.sort(key=lambda p: (-p["other_boards_count"], p["last_seen_other"] or ""), reverse=False)
    patterns.sort(key=lambda p: (-p["other_boards_count"], -(int(_dt.fromisoformat(
        (p["last_seen_other"] or "1970-01-01T00:00:00Z").replace("Z", "+00:00")
    ).timestamp()) if p["last_seen_other"] else 0)))

    # Phase G1 (2026-05-11) — defensive Synisense shield seam.
    # The across-boards aggregator is metadata-only today (no text
    # field), so the shield is a no-op on the current response shape.
    # Wiring it here means any future addition of a text field
    # (e.g. a redacted theme paragraph) is shielded by default — we
    # never have to remember to add the call.
    from services.privacy_wall import redact_for_pulse_text_async
    for p in patterns:
        # Iterate keys defensively in case a future contributor adds a
        # text-valued field. Any non-string is left alone.
        for k, v in list(p.items()):
            if isinstance(v, str) and k in ("snippet", "theme_text", "summary"):
                p[k] = await redact_for_pulse_text_async(v) or v

    return {
        "patterns": patterns[:int(limit or 50)],
        "window_days": win,
        "active_board_signature_count": len(own),
        "leakage_check": "metadata_only",
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
    """Phase G.5 — comments are now first-class on the signal row.

    Persists to BOTH `db.signal_actions` (audit trail, preserves the
    QA-brief PL-01 historical record) AND `db.signals.comments[]`
    (the surface the drawer reads from on every revisit). Comments
    are private per-account: the feed/drawer only surfaces comments
    where `account_id` matches the caller.
    """
    await _load_signal_or_404(signal_id, context_id)
    aid = ctx["account"]["id"]
    note = body.note.strip()
    if not note:
        raise HTTPException(status_code=400, detail="comment text is required")
    comment_doc = {
        "id": str(uuid.uuid4()),
        "account_id": aid,
        "note": note,
        "created_at": iso(now()),
    }
    # Append to signals.comments[]
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id},
        {"$push": {"comments": comment_doc}},
    )
    # Mirror to signal_actions for the audit trail.
    await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=aid, action_type="commented",
        payload={"note": note, "comment_id": comment_doc["id"]},
    )
    return {"ok": True, "comment": comment_doc}


@router.delete("/contexts/{context_id}/pulse/signals/{signal_id}/comments/{comment_id}")
async def pulse_comment_delete(
    context_id: str, signal_id: str, comment_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Remove a comment from the signal. Only the comment's author
    can delete their own comment."""
    aid = ctx["account"]["id"]
    res = await db.signals.update_one(
        {"id": signal_id, "context_id": context_id,
         "comments.id": comment_id, "comments.account_id": aid},
        {"$pull": {"comments": {"id": comment_id, "account_id": aid}}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Comment not found or not yours")
    return {"ok": True, "id": comment_id}


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


class ResolveIn(BaseModel):
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/resolve")
async def pulse_resolve(
    context_id: str, signal_id: str,
    body: ResolveIn = Body(default_factory=ResolveIn),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase G.1 — mark signal resolved. Sets `state='resolved'` plus
    legacy `status='resolved'` for back-compat. Optional resolution_note
    on body is shown in the Resolved tab card."""
    await _load_signal_or_404(signal_id, context_id)
    upd = {
        "state": "resolved",
        "status": "resolved",
        "resolved_at": iso(now()),
        "resolved_by": ctx["account"]["id"],
    }
    if body and body.resolution_note:
        upd["resolution_note"] = body.resolution_note.strip()
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id}, {"$set": upd},
    )
    return await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="resolved",
        payload={"resolution_note": upd.get("resolution_note")},
    )


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/unresolve")
async def pulse_unresolve(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase G.1 — recover from accidental resolve. Per QA brief E-02:
    the user resolved in error and wants the signal back on the
    Active tab. Returns state='active'; clears resolved metadata."""
    await _load_signal_or_404(signal_id, context_id)
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id},
        {"$set": {"state": "active", "status": "active"},
         "$unset": {"resolved_at": "", "resolved_by": "", "resolution_note": ""}},
    )
    return await _record_action(
        signal_id=signal_id, context_id=context_id,
        account_id=ctx["account"]["id"], action_type="unresolved", payload={},
    )


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/bookmark")
async def pulse_bookmark(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase G.1 + QA brief E-04 — Bookmarks as first-class state.
    Sets state='bookmarked' on the signal AND records a per-user
    saved row on signal_actions so per-user bookmark history
    (multi-NED context) is preserved."""
    await _load_signal_or_404(signal_id, context_id)
    aid = ctx["account"]["id"]
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id},
        {"$set": {"state": "bookmarked",
                  "bookmarked_at": iso(now()),
                  "bookmarked_by": aid}},
    )
    # mirror to signal_actions for the per-user trail
    existing = await db.signal_actions.find_one(
        {"signal_id": signal_id, "context_id": context_id,
         "account_id": aid, "action_type": "saved"}, {"_id": 0},
    )
    if not existing:
        await _record_action(
            signal_id=signal_id, context_id=context_id,
            account_id=aid, action_type="saved", payload={},
        )
    return {"ok": True, "state": "bookmarked", "id": signal_id}


@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/unbookmark")
async def pulse_unbookmark(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase G.1 — remove bookmark; returns to Active state."""
    await _load_signal_or_404(signal_id, context_id)
    aid = ctx["account"]["id"]
    await db.signals.update_one(
        {"id": signal_id, "context_id": context_id},
        {"$set": {"state": "active"},
         "$unset": {"bookmarked_at": "", "bookmarked_by": ""}},
    )
    await db.signal_actions.delete_many(
        {"signal_id": signal_id, "context_id": context_id,
         "account_id": aid, "action_type": "saved"},
    )
    return {"ok": True, "state": "active", "id": signal_id}


# Legacy /save toggle — kept for back-compat with the existing UI.
# New UI should call /bookmark + /unbookmark explicitly.
@router.post("/contexts/{context_id}/pulse/signals/{signal_id}/save")
async def pulse_save(
    context_id: str, signal_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """LEGACY toggle — flips between bookmark/unbookmark."""
    await _load_signal_or_404(signal_id, context_id)
    aid = ctx["account"]["id"]
    existing = await db.signal_actions.find_one(
        {"signal_id": signal_id, "context_id": context_id,
         "account_id": aid, "action_type": "saved"}, {"_id": 0},
    )
    if existing:
        return await pulse_unbookmark(context_id, signal_id, ctx)
    return await pulse_bookmark(context_id, signal_id, ctx)


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
