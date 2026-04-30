"""Inbound queue · iter70 — trust-tiered triage review surface.

When Postmark delivers an email from an UNKNOWN sender (not the account
owner, not a registered reportee for the target context), the inbound
webhook quarantines the payload into `db.inbound_queue` instead of
writing straight to `db.documents`. The owner reviews queued items on
`/app/inbound-queue` and either promotes them (→ documents) or rejects
(→ archived).

Endpoints:
  GET    /api/contexts/{cid}/inbound-queue            list pending/accepted/rejected
  GET    /api/me/inbound-queue/counts                 aggregate counts for Home card
  GET    /api/contexts/{cid}/inbound-queue/{qid}      detail + body preview
  POST   /api/contexts/{cid}/inbound-queue/{qid}/accept   promote → db.documents
  POST   /api/contexts/{cid}/inbound-queue/{qid}/reject   archive with reason

Accept flow runs the same extraction + storage pipeline the live ingest
uses so a promoted document is identical in shape to a Tier-A/B ingest,
except it carries `inbound_trust_tier='unknown_promoted'` and a pointer
back to the queue row so the provenance chain is intact.
"""
from __future__ import annotations

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership, get_current_account, write_audit
from documents_service import (
    extract_text,
    make_preview,
    save_to_storage,
    virus_scan_stub,
)

logger = logging.getLogger("akki.inbound_queue")

router = APIRouter(tags=["inbound_queue"])


# ---------------------------------------------------------------------------
# GET /api/contexts/{cid}/inbound-queue
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/inbound-queue")
async def list_inbound_queue(
    context_id: str,
    status: str = "pending_review",
    limit: int = 50,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    q = {"context_id": context_id}
    if status != "all":
        q["status"] = status
    cursor = db.inbound_queue.find(q, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 200)))
    items = await cursor.to_list(length=limit)
    return {"items": items, "count": len(items)}


# ---------------------------------------------------------------------------
# GET /api/me/inbound-queue/counts — aggregated counts across every context
# the caller is a member of. Used by the Home card so we don't N+1 the list
# endpoint per context on every Home render.
# ---------------------------------------------------------------------------
@router.get("/api/me/inbound-queue/counts")
async def my_inbound_queue_counts(
    account: Dict[str, Any] = Depends(get_current_account),
):
    # Find every context the caller has membership on.
    memberships = await db.memberships.find(
        {"account_id": account["id"], "status": {"$ne": "removed"}},
        {"_id": 0, "context_id": 1},
    ).to_list(length=500)
    ctx_ids = [m["context_id"] for m in memberships]
    if not ctx_ids:
        return {"total_pending": 0, "by_context": []}

    pipeline = [
        {"$match": {"context_id": {"$in": ctx_ids}, "status": "pending_review"}},
        {"$group": {"_id": "$context_id", "pending": {"$sum": 1},
                     "latest_at": {"$max": "$created_at"}}},
        {"$sort": {"latest_at": -1}},
    ]
    rows: List[Dict[str, Any]] = []
    async for row in db.inbound_queue.aggregate(pipeline):
        rows.append({
            "context_id": row["_id"],
            "pending": row["pending"],
            "latest_at": row.get("latest_at"),
        })
    total = sum(r["pending"] for r in rows)

    # Enrich with context names (one cheap round-trip).
    if rows:
        ctx_names = await db.contexts.find(
            {"id": {"$in": [r["context_id"] for r in rows]}},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(length=200)
        name_map = {c["id"]: c.get("name") for c in ctx_names}
        for r in rows:
            r["context_name"] = name_map.get(r["context_id"])

    return {"total_pending": total, "by_context": rows}


# ---------------------------------------------------------------------------
# GET /api/contexts/{cid}/inbound-queue/{qid}
# Returns the queue row + decoded text body + attachment names. Attachment
# bytes are NOT returned — only the extracted text preview after a virus scan
# passes. Keeps the review surface safe from sending raw bytes over the wire.
# ---------------------------------------------------------------------------
@router.get("/api/contexts/{context_id}/inbound-queue/{queue_id}")
async def get_inbound_queue_item(
    context_id: str,
    queue_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.inbound_queue.find_one(
        {"id": queue_id, "context_id": context_id}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    raw = await db.inbound_queue_raw.find_one(
        {"queue_id": queue_id, "context_id": context_id}, {"_id": 0}
    )
    preview = None
    extracted_preview = None
    if raw:
        preview = raw.get("text_body") or raw.get("html_body") or ""
        primary = raw.get("primary_attachment")
        if primary:
            try:
                data = base64.b64decode(primary.get("Content") or "")
                filename = primary.get("Name") or "attachment"
                clean, reason = virus_scan_stub(data, filename)
                if clean:
                    text, _err = extract_text(data, filename, primary.get("ContentType") or "")
                    if text:
                        extracted_preview = make_preview(text, max_chars=800)
            except Exception as e:  # noqa: BLE001
                logger.warning("inbound_queue preview extract failed: %s", e)
    return {
        **row,
        "body_preview": (preview or "")[:2000],
        "attachment_extracted_preview": extracted_preview,
    }


# ---------------------------------------------------------------------------
# POST /api/contexts/{cid}/inbound-queue/{qid}/accept
# Promotes a quarantined row to db.documents. Mirrors the live inbound
# ingest flow (virus scan → extract → storage) so the promoted doc carries
# the same shape as Tier-A/B ingests, plus `inbound_trust_tier='unknown_promoted'`
# for provenance.
# ---------------------------------------------------------------------------
class AcceptIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=400)


@router.post("/api/contexts/{context_id}/inbound-queue/{queue_id}/accept")
async def accept_inbound_queue_item(
    context_id: str,
    queue_id: str,
    body: AcceptIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.inbound_queue.find_one(
        {"id": queue_id, "context_id": context_id}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if row["status"] != "pending_review":
        raise HTTPException(status_code=409, detail=f"Item already {row['status']}.")

    raw = await db.inbound_queue_raw.find_one(
        {"queue_id": queue_id, "context_id": context_id}, {"_id": 0}
    )
    if not raw:
        raise HTTPException(status_code=410, detail="Queue payload is no longer available.")

    primary = raw.get("primary_attachment")
    text_body = raw.get("text_body") or ""
    html_body = raw.get("html_body") or ""
    doc_id = str(uuid.uuid4())
    created_at = iso(now())

    if primary:
        try:
            data = base64.b64decode(primary.get("Content") or "")
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Attachment payload corrupt.") from None
        filename = primary.get("Name") or "attachment"
        clean, reason = virus_scan_stub(data, filename)
        if not clean:
            await db.inbound_queue.update_one(
                {"id": queue_id},
                {"$set": {"status": "rejected", "rejected_by": ctx["account"]["id"],
                          "rejected_at": iso(now()), "reject_reason": f"virus_scan · {reason}"}},
            )
            raise HTTPException(status_code=400, detail=f"Virus scan rejected: {reason}")
        storage_key = save_to_storage(context_id, doc_id, filename, data)
        text, err = extract_text(data, filename, primary.get("ContentType") or "")
        size = len(data)
        mime = primary.get("ContentType") or "application/octet-stream"
        original_filename = filename
        display_name = row.get("inbound_subject") or filename
    else:
        body_txt = text_body or html_body or "(empty email)"
        data = body_txt.encode("utf-8", errors="replace")
        filename = f"email-{(row.get('inbound_message_id') or doc_id)[:24]}.txt"
        storage_key = save_to_storage(context_id, doc_id, filename, data)
        text, err = extract_text(data, filename, "text/plain")
        size = len(data)
        mime = "text/plain"
        original_filename = filename
        display_name = row.get("inbound_subject") or "Forwarded email"

    subject = row.get("inbound_subject") or ""
    from_email = row.get("inbound_from_email") or ""
    from_name = row.get("inbound_from_name") or ""
    attachment_count = row.get("inbound_attachment_count") or 0

    from routers.inbound_email import _detect_minutes  # noqa: PLC0415 — local reuse
    att_names = [a.get("name") or a.get("Name") or "" for a in (row.get("inbound_attachment_summary") or [])]
    is_minutes = _detect_minutes(subject, att_names)

    doc = {
        "id": doc_id,
        "context_id": context_id,
        "name": (display_name or "Forwarded email")[:200],
        "description": (text_body or "")[:280],
        "original_filename": original_filename,
        "mime_type": mime,
        "size_bytes": size,
        "storage_key": storage_key,
        "status": "extracted" if (text and not err) else ("failed" if err else "empty"),
        "extracted_text": text,
        "extracted_chars": len(text or ""),
        "preview": make_preview(text or text_body or ""),
        "data_trust": "mixed",
        "uploaded_by": ctx["account"]["id"],
        "uploaded_by_email": ctx["account"].get("email"),
        "mentioned_account_ids": [],
        "related_doc_id": None,
        "relation_type": None,
        "error": err,
        "created_at": created_at,
        "updated_at": created_at,
        # Inbound provenance
        "source": "inbound_email",
        "inbound_message_id": row.get("inbound_message_id"),
        "inbound_from_email": from_email or None,
        "inbound_from_name": from_name or None,
        "inbound_subject": subject,
        "inbound_attachment_count": attachment_count,
        "doc_type": "minutes" if is_minutes else None,
        # iter70 trust provenance — promoted after manual review
        "inbound_trust_tier": "unknown_promoted",
        "inbound_trust_reason": row.get("review_reason"),
        "inbound_queue_id": queue_id,
        "inbound_promoted_by": ctx["account"]["id"],
        "inbound_promoted_at": iso(now()),
        "inbound_promoted_note": body.note,
    }
    await db.documents.insert_one(doc)

    await db.inbound_queue.update_one(
        {"id": queue_id},
        {"$set": {
            "status": "accepted",
            "accepted_by": ctx["account"]["id"],
            "accepted_at": iso(now()),
            "promoted_doc_id": doc_id,
            "accept_note": body.note,
        }},
    )

    await write_audit(
        context_id, ctx["account"]["id"],
        "inbound_queue.accept", "inbound_queue", queue_id,
        {"from": from_email, "subject": subject,
         "promoted_doc_id": doc_id, "note": body.note},
    )
    logger.info(
        "Inbound queue: ACCEPTED queue=%s → doc=%s (ctx=%s, from=%s)",
        queue_id, doc_id, context_id, from_email,
    )
    return {"ok": True, "doc_id": doc_id, "queue_id": queue_id, "status": "accepted"}


# ---------------------------------------------------------------------------
# POST /api/contexts/{cid}/inbound-queue/{qid}/reject
# Archives the queue row. Per product direction (3c): log for ops, no reply.
# ---------------------------------------------------------------------------
class RejectIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=200)


@router.post("/api/contexts/{context_id}/inbound-queue/{queue_id}/reject")
async def reject_inbound_queue_item(
    context_id: str,
    queue_id: str,
    body: RejectIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    row = await db.inbound_queue.find_one(
        {"id": queue_id, "context_id": context_id}, {"_id": 0}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if row["status"] != "pending_review":
        raise HTTPException(status_code=409, detail=f"Item already {row['status']}.")

    reason = (body.reason or "not_relevant").strip()[:200]
    await db.inbound_queue.update_one(
        {"id": queue_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": ctx["account"]["id"],
            "rejected_at": iso(now()),
            "reject_reason": reason,
        }},
    )
    # Per product direction (3c) — no reply sent to the sender.
    await write_audit(
        context_id, ctx["account"]["id"],
        "inbound_queue.reject", "inbound_queue", queue_id,
        {"from": row.get("inbound_from_email"), "subject": row.get("inbound_subject"),
         "reason": reason},
    )
    logger.info(
        "Inbound queue: REJECTED queue=%s (ctx=%s, from=%s, reason=%s)",
        queue_id, context_id, row.get("inbound_from_email"), reason,
    )
    return {"ok": True, "queue_id": queue_id, "status": "rejected"}
