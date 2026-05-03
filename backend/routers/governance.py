"""Governance panel endpoint — Phase 7 / Advisory 7.

Aggregates existing data for the Trust panel: audit log tail + filter +
export, de-identification status, inbound email address, connected
models (imported from chat.py registry), and a sensitivity breakdown of
the user's artefacts.

No new schema. No new collections. All reads against existing data.
"""
from __future__ import annotations

import csv
import io
import os
import zipfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from core import db, get_current_account, iso as _iso, now as _now
from routers.chat import SUPPORTED_MODELS

router = APIRouter(prefix="/api/me/governance", tags=["governance"])


# Which surfaces each model is used in. Used to decorate `connected_models`.
# Kept static here because it's taxonomy, not user data.
_MODEL_USAGE: Dict[str, List[str]] = {
    "claude-sonnet-4-5":  ["Chat", "Briefings", "Catch-up", "Solve (deep)"],
    "claude-haiku-4-5":   ["Chat (fast)", "Ingestion", "Signal extraction"],
    "gpt-5-2":            ["Chat", "Report drafts"],
    "gemini-2-5-pro":     ["Research", "Influence Map"],
    "gemini-2-5-flash":   ["Chat (fastest)", "Catch-up digests"],
}


async def _user_context_ids(account_id: str) -> List[str]:
    return [
        m["context_id"] async for m in db.memberships.find(
            {"account_id": account_id, "status": "active"},
            {"_id": 0, "context_id": 1},
        )
    ]


async def _context_name_map(ctx_ids: List[str]) -> Dict[str, str]:
    if not ctx_ids:
        return {}
    rows = await db.contexts.find(
        {"id": {"$in": ctx_ids}}, {"_id": 0, "id": 1, "name": 1},
    ).to_list(500)
    return {r["id"]: r.get("name") for r in rows}


def _decorate_audit_row(row: Dict[str, Any], ctx_names: Dict[str, str], actor_email: str) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "timestamp": row.get("created_at"),
        "action": row.get("action"),
        "context_id": row.get("context_id"),
        "context_name": ctx_names.get(row.get("context_id")),
        "actor_email": actor_email,
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "metadata": row.get("metadata") or {},
    }


# ---------------------------------------------------------------------------
# GET /api/me/governance  (the main panel)
# ---------------------------------------------------------------------------
@router.get("")
async def governance_panel(current: Dict[str, Any] = Depends(get_current_account)):
    ctx_ids = await _user_context_ids(current["id"])
    ctx_names = await _context_name_map(ctx_ids)
    actor_email = current.get("email") or ""

    # Audit — total + most recent 10 + distinct actions.
    audit_q = {
        "$or": [
            {"context_id": {"$in": ctx_ids}},
            {"account_id": current["id"]},
        ]
    } if ctx_ids else {"account_id": current["id"]}
    total_entries = await db.audit_log.count_documents(audit_q)
    recent_raw = await db.audit_log.find(audit_q, {"_id": 0}) \
        .sort("created_at", -1).limit(10).to_list(10)
    recent = [_decorate_audit_row(r, ctx_names, actor_email) for r in recent_raw]
    distinct_actions = sorted(set(r["action"] for r in recent if r.get("action")))

    # Inbound address — mirror the mint-on-first-read pattern used in
    # inbound_email.py so the panel surfaces a ready-to-use address even
    # if the account has never hit /api/inbound/address before.
    inbound_token = (current.get("inbound_token") or "").strip()
    if not inbound_token:
        import secrets
        inbound_token = secrets.token_urlsafe(10).replace("_", "").replace("-", "")[:12].lower()
        await db.accounts.update_one(
            {"id": current["id"]}, {"$set": {"inbound_token": inbound_token}}
        )
    inbound_domain = os.environ.get("INBOUND_DOMAIN", "in.akki.ai")
    inbound_address = f"inbound+{inbound_token}@{inbound_domain}"

    # Connected models — pulled straight from chat.py's registry.
    connected_models = [
        {
            "id": m["id"],
            "label": m["label"],
            "provider": m["provider"],
            "used_in": _MODEL_USAGE.get(m["id"], []),
        }
        for m in SUPPORTED_MODELS
    ]

    # Sensitivity at a glance — across the user's artefact-ish collections.
    # `classification` may be EITHER a string tier ("internal", "confidential"...)
    # — written by `studio_sensitivity.score_sensitivity()` and the daily-review
    # path — OR a full verdict dict `{score, classification, label, reasons}` —
    # written by `studio_blocks.py:569` on the Phase 8 composer rescore path.
    # The dict case went undetected for several sessions because the governance
    # endpoint wasn't exercised against composer-rescored artefacts; it trips
    # `AttributeError: 'dict' object has no attribute 'lower'` the moment it is.
    # We handle both shapes honestly via isinstance dispatch rather than a
    # defensive `.get()` chain that would hide the underlying shape drift.
    buckets = ["public", "internal", "confidential", "restricted"]
    classification_breakdown = {b: 0 for b in buckets}
    last_classified_at: Optional[str] = None
    if ctx_ids:
        for coll in ("studio_artefacts", "decks", "reports", "briefings"):
            cur = db[coll].find(
                {"context_id": {"$in": ctx_ids}, "classification": {"$exists": True}},
                {"_id": 0, "classification": 1, "updated_at": 1, "created_at": 1},
            )
            async for row in cur:
                raw = row.get("classification")
                if isinstance(raw, dict):
                    # Composer rescore verdict; the string tier lives nested
                    # under the same key name.
                    tier = str(raw.get("classification") or "").lower()
                elif isinstance(raw, str):
                    tier = raw.lower()
                else:
                    # Anything else (None, list, int) is honestly unknown —
                    # drop rather than invent a bucket.
                    continue
                if tier in classification_breakdown:
                    classification_breakdown[tier] += 1
                ts = row.get("updated_at") or row.get("created_at")
                if ts and (last_classified_at is None or ts > last_classified_at):
                    last_classified_at = ts
    auto_classify = bool((current.get("preferences") or {}).get("auto_classify", True))

    return {
        "audit_log": {
            "total_entries": total_entries,
            "recent": recent,
            "available_actions": distinct_actions,
        },
        "shielding": {
            "mode": "regex",
            "masker_status": "live",
            "mock_scaffolding_note": (
                "Live Synisense de-identification service replaces the local "
                "masker in a future release."
            ),
        },
        "inbound": {
            "address": inbound_address,
            "domain": inbound_domain,
        },
        "connected_models": connected_models,
        "sensitivity": {
            "auto_classify": auto_classify,
            "last_classified_at": last_classified_at,
            "classification_breakdown": classification_breakdown,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/me/governance/audit — paginated, filterable
# ---------------------------------------------------------------------------
@router.get("/audit")
async def governance_audit(
    current: Dict[str, Any] = Depends(get_current_account),
    action: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO datetime inclusive."),
    until: Optional[str] = Query(None, description="ISO datetime exclusive."),
    limit: int = Query(100, ge=1, le=500),
    cursor: Optional[str] = Query(
        None,
        description=(
            "ISO datetime — returns rows with created_at < cursor "
            "(descending pagination). Omit for the most-recent page."
        ),
    ),
):
    ctx_ids = await _user_context_ids(current["id"])
    ctx_names = await _context_name_map(ctx_ids)
    actor_email = current.get("email") or ""

    q: Dict[str, Any] = {
        "$or": [
            {"context_id": {"$in": ctx_ids}},
            {"account_id": current["id"]},
        ]
    } if ctx_ids else {"account_id": current["id"]}
    if action:
        q["action"] = action

    created_filter: Dict[str, Any] = {}
    if since:
        created_filter["$gte"] = since
    if until:
        created_filter["$lt"] = until
    if cursor:
        created_filter["$lt"] = cursor  # cursor wins over `until` for paging
    if created_filter:
        q["created_at"] = created_filter

    rows = await db.audit_log.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    decorated = [_decorate_audit_row(r, ctx_names, actor_email) for r in rows]
    next_cursor = decorated[-1]["timestamp"] if (decorated and len(decorated) >= limit) else None
    return {"items": decorated, "next_cursor": next_cursor, "limit": limit}


# ---------------------------------------------------------------------------
# POST /api/me/governance/audit/export — one-shot ZIP of CSV audit entries
# ---------------------------------------------------------------------------
class ExportIn(BaseModel):
    action: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


@router.post("/audit/export")
async def governance_audit_export(
    body: ExportIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Zip-streamed CSV of audit entries for the requested filter window.

    Mirrors the pattern from `routers/chat.py#/chats/{id}/audit/export.zip`
    — one-shot, no persistent download URL, auditor ingests the raw bytes.
    """
    ctx_ids = await _user_context_ids(current["id"])
    ctx_names = await _context_name_map(ctx_ids)
    actor_email = current.get("email") or ""

    q: Dict[str, Any] = {
        "$or": [
            {"context_id": {"$in": ctx_ids}},
            {"account_id": current["id"]},
        ]
    } if ctx_ids else {"account_id": current["id"]}
    if body.action:
        q["action"] = body.action
    created_filter: Dict[str, Any] = {}
    if body.since:
        created_filter["$gte"] = body.since
    if body.until:
        created_filter["$lt"] = body.until
    if created_filter:
        q["created_at"] = created_filter

    rows = await db.audit_log.find(q, {"_id": 0}) \
        .sort("created_at", -1).to_list(10000)
    decorated = [_decorate_audit_row(r, ctx_names, actor_email) for r in rows]

    # Build CSV in-memory, wrap in a zip.
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow([
        "timestamp", "action", "context_id", "context_name", "actor_email",
        "resource_type", "resource_id", "metadata_json",
    ])
    for r in decorated:
        import json as _json
        writer.writerow([
            r.get("timestamp") or "",
            r.get("action") or "",
            r.get("context_id") or "",
            r.get("context_name") or "",
            r.get("actor_email") or "",
            r.get("resource_type") or "",
            r.get("resource_id") or "",
            _json.dumps(r.get("metadata") or {}, ensure_ascii=False),
        ])

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("audit_log.csv", csv_buf.getvalue())
        manifest = (
            "# AKKI governance audit export\n"
            f"# generated_at: {_iso(_now())}\n"
            f"# actor_email: {actor_email}\n"
            f"# filter.action: {body.action or '(all)'}\n"
            f"# filter.since:  {body.since or '(beginning)'}\n"
            f"# filter.until:  {body.until or '(now)'}\n"
            f"# row_count: {len(decorated)}\n"
            "#\n"
            "# Every row is an immutable record of a server-side action.\n"
            "# Fields: timestamp, action, context_id, context_name,\n"
            "# actor_email, resource_type, resource_id, metadata_json.\n"
        )
        zf.writestr("manifest.txt", manifest)
    zip_buf.seek(0)
    fname = f'audit-{_iso(_now()).replace(":", "").replace("-", "")[:15]}.zip'
    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
