"""Phase J — Human-readable Synisense audit metrics for the chat UI.

Two endpoints:
  GET /api/chats/{chat_id}/synisense-metrics
      Per-conversation counts. Scoped to the chat's account_id AND the
      chat surfaces (`chat, chat_classifier, chat_four_check,
      chat_evidence_list`) AND ts >= chat.created_at.

  GET /api/contexts/{cid}/synisense-metrics?window=today|7d|30d
      Aggregate counts for an active context, windowed by ts.

Numbers (all integers):
  identifiers_redacted     — total `len(spans)` across matching runs
  model_calls              — count of matching runs (one per LLM hop)
  layer_breakdown          — dict {regex, presidio, llm} of `stats.layer_won`
  storyline                — one editorial sentence synthesising the above

The storyline is shaped on the server so the same line shows everywhere
the metrics surface.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["synisense_metrics"])

_CHAT_SURFACES = ["chat", "chat_classifier", "chat_four_check", "chat_evidence_list"]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _aggregate(query: Dict[str, Any]) -> Dict[str, Any]:
    """Run the standard count + layer-breakdown aggregation."""
    from core import db
    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": None,
                "runs": {"$sum": 1},
                "identifiers": {"$sum": {"$size": {"$ifNull": ["$spans", []]}}},
                "layers": {"$push": "$stats.layer_won"},
            }
        },
    ]
    out = await db.synisense_runs.aggregate(pipeline).to_list(length=1)
    if not out:
        return {"runs": 0, "identifiers": 0, "layer_breakdown": {"regex": 0, "presidio": 0, "llm": 0}}
    row = out[0]
    layers = row.get("layers") or []
    breakdown = {"regex": 0, "presidio": 0, "llm": 0}
    for lw in layers:
        if not lw:
            continue
        if lw == "regex":
            breakdown["regex"] += 1
        elif lw == "presidio":
            breakdown["presidio"] += 1
        elif lw in ("llm", "llm_fallback"):
            breakdown["llm"] += 1
    return {
        "runs": int(row.get("runs") or 0),
        "identifiers": int(row.get("identifiers") or 0),
        "layer_breakdown": breakdown,
    }


def _build_storyline(identifiers: int, runs: int, breakdown: Dict[str, int]) -> str:
    """One editorial sentence synthesising the redaction record. Voice
    is senior peer, no superlatives."""
    if identifiers == 0 and runs == 0:
        return "Nothing has needed redaction in this conversation yet — Synisense Shield is on standby."
    layers_used = [k for k, v in breakdown.items() if v > 0]
    layer_phrase = (
        "three layers" if len(layers_used) >= 3
        else "two layers" if len(layers_used) == 2
        else "one layer"
    )
    return (
        f"This conversation passed through {layer_phrase} of redaction before any AI saw it. "
        f"{identifiers} identifier{'s' if identifiers != 1 else ''} "
        f"— names, emails, account numbers and similar — "
        f"{'were' if identifiers != 1 else 'was'} masked deterministically across {runs} model call{'s' if runs != 1 else ''}. "
        f"Nothing left your tenant."
    )


@router.get("/chats/{chat_id}/synisense-metrics")
async def chat_synisense_metrics(chat_id: str) -> Dict[str, Any]:
    """Per-conversation metrics. Scope: chat_id's account_id +
    chat surfaces + ts >= chat.created_at."""
    from core import db, get_current_account
    chat = await db.chats.find_one({"id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="chat not found")
    account_id = chat.get("account_id")
    created_at = chat.get("created_at") or _now_utc()
    query = {
        "account_id": account_id,
        "surface": {"$in": _CHAT_SURFACES},
        "ts": {"$gte": created_at},
    }
    agg = await _aggregate(query)
    storyline = _build_storyline(agg["identifiers"], agg["runs"], agg["layer_breakdown"])
    return {
        "chat_id": chat_id,
        "identifiers_redacted": agg["identifiers"],
        "model_calls": agg["runs"],
        "layer_breakdown": agg["layer_breakdown"],
        "storyline": storyline,
    }


@router.get("/chats/{chat_id}/messages/{msg_id}/synisense-runs")
async def message_synisense_runs(chat_id: str, msg_id: str) -> Dict[str, Any]:
    """Phase J.2 — per-message Synisense metrics. Returns counts +
    layer breakdown scoped to a SINGLE chat message. Used by the chat
    UI to render an inline redaction badge per assistant message.

    Filter is on (chat_id, message_id) which is reliable once
    `_record_synisense_audit_evidence` and `shield_payload_async`
    started threading these fields (Phase J.2)."""
    query = {"chat_id": chat_id, "message_id": msg_id}
    agg = await _aggregate(query)
    return {
        "chat_id": chat_id,
        "message_id": msg_id,
        "identifiers_redacted": agg["identifiers"],
        "model_calls": agg["runs"],
        "layer_breakdown": agg["layer_breakdown"],
    }


class _BatchMsgIds(BaseModel):
    msg_ids: List[str] = Field(default_factory=list, max_length=200)


@router.post("/chats/{chat_id}/messages/synisense-runs/batch")
async def messages_synisense_runs_batch(chat_id: str, body: _BatchMsgIds) -> Dict[str, Any]:
    """CHAT sprint (2026-05-12) — batched per-message Synisense metrics.

    Replaces the N+1 pattern (one HTTP call per assistant message) with
    a single aggregation pipeline grouped by `message_id`. The UI calls
    this once after the message list paints.

    Response shape:
      {"items": { "<msg_id>": {identifiers_redacted, model_calls,
                               layer_breakdown}, ... }}
    Messages with zero shield activity simply aren't present in the
    map — the UI treats absent as zero."""
    from core import db
    msg_ids = [m for m in (body.msg_ids or []) if isinstance(m, str)]
    if not msg_ids:
        return {"items": {}}
    pipeline = [
        {"$match": {"chat_id": chat_id, "message_id": {"$in": msg_ids}}},
        {
            "$group": {
                "_id": "$message_id",
                "runs": {"$sum": 1},
                "identifiers": {"$sum": {"$size": {"$ifNull": ["$spans", []]}}},
                "layers": {"$push": "$stats.layer_won"},
            }
        },
    ]
    rows = await db.synisense_runs.aggregate(pipeline).to_list(length=len(msg_ids))
    items: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        msg_id = row.get("_id")
        if not msg_id:
            continue
        layers = row.get("layers") or []
        breakdown = {"regex": 0, "presidio": 0, "llm": 0}
        for lw in layers:
            if not lw:
                continue
            if lw == "regex":
                breakdown["regex"] += 1
            elif lw == "presidio":
                breakdown["presidio"] += 1
            elif lw in ("llm", "llm_fallback"):
                breakdown["llm"] += 1
        items[msg_id] = {
            "identifiers_redacted": int(row.get("identifiers") or 0),
            "model_calls": int(row.get("runs") or 0),
            "layer_breakdown": breakdown,
        }
    return {"items": items}


@router.get("/contexts/{cid}/synisense-metrics")
async def context_synisense_metrics(
    cid: str,
    window: str = Query("today", regex="^(today|7d|30d)$"),
) -> Dict[str, Any]:
    """Aggregate metrics for a tenant, windowed by ts. Used in the
    Trust Panel rollup row."""
    now = _now_utc()
    if window == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif window == "7d":
        since = now - timedelta(days=7)
    else:
        since = now - timedelta(days=30)
    query = {"context_id": cid, "ts": {"$gte": since}}
    agg = await _aggregate(query)
    storyline = _build_storyline(agg["identifiers"], agg["runs"], agg["layer_breakdown"])
    return {
        "context_id": cid,
        "window": window,
        "since": since.isoformat(),
        "identifiers_redacted": agg["identifiers"],
        "model_calls": agg["runs"],
        "layer_breakdown": agg["layer_breakdown"],
        "storyline": storyline,
    }
