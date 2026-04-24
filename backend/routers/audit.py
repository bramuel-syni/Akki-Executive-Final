"""Audit log + context export."""
from __future__ import annotations

import io
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core import db, now, iso, write_audit, require_context_membership

router = APIRouter(prefix="/api")


@router.get("/contexts/{context_id}/audit-log")
async def get_audit_log(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 100,
):
    entries = await db.audit_log.find(
        {"context_id": ctx["context"]["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(min(limit, 500))
    account_ids = list({e["account_id"] for e in entries if e.get("account_id")})
    accounts = await db.accounts.find(
        {"id": {"$in": account_ids}}, {"_id": 0}
    ).to_list(500) if account_ids else []
    by_id = {a["id"]: a for a in accounts}
    for e in entries:
        a = by_id.get(e.get("account_id") or "")
        e["actor_email"] = a["email"] if a else None
        e["actor_name"] = a.get("name") if a else None
    return entries


@router.post("/contexts/{context_id}/export")
async def export_context(
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    context_id = ctx["context"]["id"]
    contexts = await db.contexts.find({"id": context_id}, {"_id": 0}).to_list(1)
    memberships = await db.memberships.find({"context_id": context_id}, {"_id": 0}).to_list(1000)
    account_ids = [m["account_id"] for m in memberships]
    accounts = await db.accounts.find(
        {"id": {"$in": account_ids}},
        {"_id": 0, "password_hash": 0, "mfa_secret": 0, "mfa_secret_pending": 0},
    ).to_list(1000)
    invitations = await db.invitations.find({"context_id": context_id}, {"_id": 0}).to_list(1000)
    audit = await db.audit_log.find({"context_id": context_id}, {"_id": 0}).to_list(5000)
    telemetry = await db.telemetry_events.find({"context_id": context_id}, {"_id": 0}).to_list(5000)
    consent = await db.consent_decisions.find({"context_id": context_id}, {"_id": 0}).to_list(1000)

    payload = {
        "export_version": "3.0",
        "exported_at": iso(now()),
        "context": contexts[0] if contexts else None,
        "accounts": accounts,
        "memberships": memberships,
        "invitations": invitations,
        "consent_decisions": consent,
        "audit_log": audit,
        "telemetry_events": telemetry,
    }
    await write_audit(context_id, ctx["account"]["id"], "context.exported", "context", context_id, {})

    buf = io.BytesIO(json.dumps(payload, indent=2, default=str).encode())
    filename = f"akki-export-{context_id[:8]}-{now().strftime('%Y%m%d-%H%M%S')}.json"
    return StreamingResponse(
        buf, media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
