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
# Phase 12.2 ITEM F — Synisense roll-up for the TrustPanel.
# ---------------------------------------------------------------------------
async def _build_synisense_block(
    current: Dict[str, Any], ctx_ids: List[str],
) -> Dict[str, Any]:
    """Aggregate from `db.synisense_runs` over the user's contexts AND
    their account-scoped runs (chat hooks on UNGROUNDED chats persist
    with `context_id=""` so they would be invisible to a pure
    context-id filter — the brief explicitly calls out that those
    runs must still be counted under the user). Counts only — span
    detail and text never come back here. Falls back to honest-empty
    when no runs exist yet so the TrustPanel can render an empty
    state without a special branch.

    Filter shape (locked in Phase 12.2 closeout BUG 1 fix):
        $or:
          - context_id ∈ ctx_ids       (grounded runs in user's contexts)
          - account_id == current.id   (ungrounded runs the user owns)
    """
    from datetime import datetime, timedelta, timezone
    from services.synisense import get_status_snapshot

    status = get_status_snapshot()
    account_id = current.get("id")

    # Filter shared by every aggregation. Built once here so the four
    # pipelines below stay in lock-step.
    user_filter: Dict[str, Any] = {
        "$or": [
            {"context_id": {"$in": ctx_ids}} if ctx_ids else {"_never": True},
            {"account_id": account_id} if account_id else {"_never": True},
        ]
    }

    # Empty state: no contexts AND no account_id (rare). Honest empty.
    if not ctx_ids and not account_id:
        return {
            "status": "live",
            "active": False,
            "last_run_at": None,
            "spans_redacted_7d": 0,
            "spans_redacted_30d": 0,
            "entity_histogram_7d": {},
            "llm_fallback_calls_7d": 0,
            "llm_fallback_cap": status.get("llm_fallback", {}).get("cap_per_doc", 20),
            "key_version": status.get("key_version"),
            "model": status.get("model"),
            "insecure_fallback": bool(status.get("insecure_fallback")),
            "version": status.get("version"),
        }

    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    # 7-day window: spans + entity histogram + llm fallback calls.
    pipeline_7d = [
        {"$match": {**user_filter, "ts": {"$gte": cutoff_7d}}},
        {"$group": {
            "_id": None,
            "runs": {"$sum": 1},
            "spans_total": {"$sum": {"$size": {"$ifNull": ["$spans", []]}}},
            "llm_calls": {"$sum": {"$ifNull": ["$stats.llm_calls", 0]}},
        }},
    ]
    rows_7d = await db.synisense_runs.aggregate(pipeline_7d).to_list(1)
    agg_7d = rows_7d[0] if rows_7d else {"runs": 0, "spans_total": 0, "llm_calls": 0}

    pipeline_hist = [
        {"$match": {**user_filter, "ts": {"$gte": cutoff_7d}}},
        {"$unwind": "$spans"},
        {"$group": {"_id": "$spans.entity_type", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 30},
    ]
    hist_rows = await db.synisense_runs.aggregate(pipeline_hist).to_list(30)
    histogram = {r["_id"]: int(r["n"]) for r in hist_rows if r.get("_id")}

    spans_30d_doc = await db.synisense_runs.aggregate([
        {"$match": {**user_filter, "ts": {"$gte": cutoff_30d}}},
        {"$group": {"_id": None, "n": {"$sum": {"$size": {"$ifNull": ["$spans", []]}}}}},
    ]).to_list(1)
    spans_30d = int(spans_30d_doc[0]["n"]) if spans_30d_doc else 0

    last_doc = await db.synisense_runs.find_one(
        user_filter,
        sort=[("ts", -1)],
        projection={"_id": 0, "ts": 1},
    )
    last_run_at = last_doc.get("ts") if last_doc else None
    if isinstance(last_run_at, datetime):
        last_run_at = last_run_at.isoformat()

    return {
        "status": "live",
        # `active` reflects "any run in the last 7 days for this user"
        # — this is what the TrustPanel renders the badge from.
        "active": agg_7d.get("runs", 0) > 0,
        "last_run_at": last_run_at,
        "spans_redacted_7d": int(agg_7d.get("spans_total", 0)),
        "spans_redacted_30d": spans_30d,
        "entity_histogram_7d": histogram,
        "llm_fallback_calls_7d": int(agg_7d.get("llm_calls", 0)),
        "llm_fallback_cap": status.get("llm_fallback", {}).get("cap_per_doc", 20),
        "key_version": status.get("key_version"),
        "model": status.get("model"),
        "insecure_fallback": bool(status.get("insecure_fallback")),
        "version": status.get("version"),
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

    # ── Phase 12.2 ITEM F — Synisense roll-up. Aggregates from
    # `db.synisense_runs` over the user's currently-active context (or
    # all of their contexts if no active one). Counts only — never
    # individual span detail, never any text. The TrustPanel reads from
    # this block to render real status and retire the
    # `mock_scaffolding_note` from the shielding block.
    syn_block = await _build_synisense_block(current, ctx_ids)

    return {
        "audit_log": {
            "total_entries": total_entries,
            "recent": recent,
            "available_actions": distinct_actions,
        },
        "shielding": {
            "mode": "synisense",
            "masker_status": "live",
            # `mock_scaffolding_note` retired in Phase 12.2 — the
            # in-house Synisense pipeline ships and is consumed by all
            # six surfaces. The trust panel renders the new
            # `synisense` block below for live status.
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
        "synisense": syn_block,
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

    # Phase 15.3 — Solva v2 reasoning logs (decision #12). Pull every
    # solva_v2 session for accessible contexts OR owned by this account,
    # plus their full reasoning_audit_log. Same date filter when present.
    solva_q: Dict[str, Any] = {
        "$or": [
            {"context_id": {"$in": ctx_ids}},
            {"account_id": current["id"]},
        ]
    } if ctx_ids else {"account_id": current["id"]}
    if created_filter:
        solva_q["started_at"] = created_filter
    solva_sessions = await db.solva_v2_sessions.find(
        solva_q,
        {"_id": 0, "id": 1, "account_id": 1, "context_id": 1, "submodule": 1,
         "persona": 1, "cluster_id": 1, "cluster_label": 1, "intent": 1,
         "layer": 1, "status": 1, "version": 1, "schema_version": 1,
         "started_at": 1, "updated_at": 1, "completed_at": 1,
         "abandoned_reason": 1, "jailbreak_soft_count": 1,
         "synthesis": 1, "reflection": 1, "parent_session_id": 1},
    ).sort("started_at", -1).to_list(2000)
    # Reasoning log rows are extracted as a separate flat list so the export
    # consumer (auditor) can ingest them without nesting.
    reasoning_rows: List[Dict[str, Any]] = []
    full_logs = await db.solva_v2_sessions.find(
        solva_q,
        {"_id": 0, "id": 1, "account_id": 1, "context_id": 1,
         "reasoning_audit_log": 1},
    ).to_list(2000)
    for s in full_logs:
        for entry in s.get("reasoning_audit_log") or []:
            row = {
                "session_id": s["id"],
                "account_id": s.get("account_id"),
                "context_id": s.get("context_id"),
            }
            row.update(entry)
            reasoning_rows.append(row)

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
        # Phase 15.3 — Solva v2 sessions + reasoning logs (decision #12).
        import json as _json
        zf.writestr(
            "solva_v2_sessions.json",
            _json.dumps(solva_sessions, ensure_ascii=False, indent=2, default=str),
        )
        zf.writestr(
            "solva_v2_reasoning_log.json",
            _json.dumps(reasoning_rows, ensure_ascii=False, indent=2, default=str),
        )
        manifest = (
            "# AKKI governance audit export\n"
            f"# generated_at: {_iso(_now())}\n"
            f"# actor_email: {actor_email}\n"
            f"# filter.action: {body.action or '(all)'}\n"
            f"# filter.since:  {body.since or '(beginning)'}\n"
            f"# filter.until:  {body.until or '(now)'}\n"
            f"# row_count: {len(decorated)}\n"
            f"# solva_v2_sessions: {len(solva_sessions)}\n"
            f"# solva_v2_reasoning_log: {len(reasoning_rows)}\n"
            "#\n"
            "# Files:\n"
            "#   audit_log.csv               Server-side action log (existing).\n"
            "#   solva_v2_sessions.json      Phase 15.3 — Solva v2 session\n"
            "#                               metadata + synthesis + reflection.\n"
            "#   solva_v2_reasoning_log.json Phase 15.3 — every engine audit\n"
            "#                               entry from every Solva v2 turn,\n"
            "#                               flattened with session+context FK.\n"
            "#\n"
            "# Every row is an immutable record of a server-side action.\n"
            "# audit_log.csv fields: timestamp, action, context_id, context_name,\n"
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
