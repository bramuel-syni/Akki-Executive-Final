"""Document Engagement — read receipts, share counter, linked-docs map.

The user asked for: "being able to know how many users have read your
document, if the document has been shared, and how many other documents
are linked to the document."

Three primitives:
  • document_views collection — one row per (doc_id, account_id, day).
    A re-view by the same account on the same UTC day is deduped (we
    update the timestamp instead of inserting). This keeps the count
    sensible without persisting every page-refresh.
  • document_shares collection — one row per recorded share intent.
    Used for in-context "shared with X by email" tracking. Distinct from
    the /shares router which only handles signal+briefing externalisation.
  • Linked documents — composed from the existing related_doc_id graph
    (ancestors via parent pointer, descendants via inverse lookup).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit, require_context_membership,
)

logger = logging.getLogger("akki.documents.engagement")
router = APIRouter(prefix="/api")


# -----------------------------------------------------------------------------
# Read receipts
# -----------------------------------------------------------------------------
@router.post("/contexts/{context_id}/documents/{doc_id}/view")
async def record_view(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Record (or refresh) a read-receipt for the current account on this
    document. Idempotent across a single UTC day."""
    doc = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "uploaded_by": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    account = ctx["account"]
    # Don't count self-views from the uploader as "readers" — they wrote it.
    is_owner = doc.get("uploaded_by") == account["id"]

    today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    res = await db.document_views.update_one(
        {
            "doc_id": doc_id, "context_id": context_id,
            "account_id": account["id"], "day": today_key,
        },
        {
            "$set": {
                "account_name": account.get("name") or account["email"].split("@")[0],
                "account_email": account["email"],
                "viewed_at": _iso(_now()),
                "is_owner_view": is_owner,
            },
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "context_id": context_id,
                "account_id": account["id"],
                "day": today_key,
                "first_viewed_at": _iso(_now()),
            },
            "$inc": {"view_count": 1},
        },
        upsert=True,
    )
    return {"ok": True, "deduped": res.matched_count > 0}


# -----------------------------------------------------------------------------
# Share recording (internal + external)
# -----------------------------------------------------------------------------
class DocumentShareIn(BaseModel):
    # Track B Phase B5 G7 (2026-06-04) — schema swap from singular
    # `to_email: EmailStr` to multi-recipient `recipient_emails:
    # List[EmailStr]`. The FE has always sent a list (`recipients:`
    # → now `recipient_emails:`); the BE was authored singular so
    # every submit returned 422 "Field required". Mirrors the
    # canonical Q4Y share contract at `questions.py:351-356` and
    # the engagement read panel which already renders
    # `s.recipient_emails || []` as an array. `email_service.
    # send_email(to=List[str], …)` already accepts a list.
    recipient_emails: List[EmailStr] = Field(..., min_length=1, max_length=10)
    message: Optional[str] = Field(default=None, max_length=2000)


@router.post("/contexts/{context_id}/documents/{doc_id}/share")
async def share_document(
    context_id: str, doc_id: str,
    body: DocumentShareIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Record a share intent for the document. The actual email send is
    deferred (mirrors the /shares router pattern); for now we persist
    the share record so the engagement panel can report it."""
    doc = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "name": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    account = ctx["account"]
    # G7 (2026-06-04) — multi-recipient storage. Store BOTH:
    #   • `recipient_emails: List[str]` (new canonical shape; engagement
    #     read surfaces this for FE rendering).
    #   • `shared_with_email: str` (= recipient_emails[0]; backwards-
    #     compat with prior singular-shape engagement consumers).
    # Mongo is schemaless so prior rows without `recipient_emails`
    # naturally surface as missing → engagement read falls back to
    # the singular `shared_with_email` field.
    recipient_emails = [str(e) for e in body.recipient_emails]
    primary_email = recipient_emails[0]
    record = {
        "id": str(uuid.uuid4()),
        "doc_id": doc_id,
        "context_id": context_id,
        "shared_by_account_id": account["id"],
        "shared_by_name": account.get("name") or account["email"],
        "shared_by_email": account["email"],
        "recipient_emails": recipient_emails,
        "shared_with_email": primary_email,
        "shared_with_name": primary_email.split("@")[0],
        "message": (body.message or "").strip()[:2000],
        "created_at": _iso(_now()),
    }
    await db.document_shares.insert_one(record)
    record.pop("_id", None)

    # Real send via Resend / SendGrid. `send_email(to=List[str], …)`
    # already accepts a list — fan-out is provider-native. Failures
    # are logged but the share intent record still persists.
    try:
        from email_service import send_email
        view_url = f"{os.environ.get('FRONTEND_ORIGIN', '').rstrip('/')}/app/documents/{doc_id}"
        sender_label = record["shared_by_name"]
        html = (
            f"<div style=\"font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:32px 24px;"
            f"background:#f5efe6;color:#1a1f2e;\">"
            f"<p style=\"font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#7a6a52;"
            f"margin:0 0 16px 0;\">{sender_label} sent you a document via AKKI</p>"
            f"<h1 style=\"font-size:22px;line-height:1.35;margin:0 0 14px 0;font-weight:normal;\">"
            f"{doc.get('name')}</h1>"
            + (f"<p style=\"font-size:14px;line-height:1.7;color:#3a3a3a;margin:0 0 22px 0;font-style:italic;\">{record['message']}</p>" if record["message"] else "")
            + f"<a href=\"{view_url}\" style=\"display:inline-block;background:#722f37;color:#fff;padding:11px 22px;text-decoration:none;font-size:13px;letter-spacing:0.05em;\">Open the document &rarr;</a>"
            + "<p style=\"font-size:11px;color:#7a6a52;margin:32px 0 0 0;\">Your read is recorded so the sender knows you've seen it.</p>"
            + "</div>"
        )
        send_result = await send_email(
            to=recipient_emails, subject=f"{sender_label} shared: {doc.get('name')}",
            html=html,
            text=f"{sender_label} shared a document with you via AKKI: {doc.get('name')}\n\n{record['message'] or ''}\n\nOpen: {view_url}",
        )
        record["email_send_id"] = send_result.get("id")
        record["email_send_mode"] = send_result.get("mode")
        await db.document_shares.update_one(
            {"id": record["id"]},
            {"$set": {"email_send_id": send_result.get("id"), "email_send_mode": send_result.get("mode")}},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Document share email failed: %s", e)

    await write_audit(
        context_id, account["id"], "document.shared", "document", doc_id,
        {"recipient_emails": recipient_emails, "doc_name": doc.get("name")},
    )
    return record


@router.get("/contexts/{context_id}/documents/{doc_id}/engagement")
async def get_engagement(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Returns the engagement summary for one document:

        {
          "view_count": int,                  # total views (all readers, all days)
          "unique_readers": int,              # distinct accounts (excl. owner)
          "readers": [{name, email, last_viewed_at, view_count}],
          "share_count": int,
          "shares": [{shared_with_name, shared_with_email, shared_by_name, created_at}],
          "linked_count": int,
          "linked_documents": [{id, name, relation, created_at}]
        }
    """
    doc = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id},
        {"_id": 0, "id": 1, "uploaded_by": 1, "related_doc_id": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    owner_id = doc.get("uploaded_by")

    # -- Views (deduped by account; owner views excluded from "readers")
    views_cursor = db.document_views.find(
        {"doc_id": doc_id, "context_id": context_id}, {"_id": 0},
    ).sort("viewed_at", -1)
    by_account: Dict[str, Dict[str, Any]] = {}
    total_views = 0
    async for v in views_cursor:
        total_views += int(v.get("view_count") or 1)
        aid = v.get("account_id")
        if not aid or aid == owner_id:
            continue
        agg = by_account.setdefault(aid, {
            "account_id": aid,
            "name": v.get("account_name") or "Reader",
            "email": v.get("account_email") or "",
            "last_viewed_at": v.get("viewed_at"),
            "view_count": 0,
        })
        agg["view_count"] += int(v.get("view_count") or 1)
        # Keep the most recent timestamp (cursor is desc, so first wins)
        if not agg.get("last_viewed_at") or (v.get("viewed_at") and v["viewed_at"] > agg["last_viewed_at"]):
            agg["last_viewed_at"] = v.get("viewed_at")
    readers = sorted(by_account.values(), key=lambda r: r["last_viewed_at"] or "", reverse=True)

    # -- Shares
    shares_cursor = db.document_shares.find(
        {"doc_id": doc_id, "context_id": context_id}, {"_id": 0},
    ).sort("created_at", -1)
    shares: List[Dict[str, Any]] = []
    async for s in shares_cursor:
        # Track B Phase B5 G7 (2026-06-04) — surface `recipient_emails`
        # as the canonical array shape (FE renders `s.recipient_emails
        # || []`). Legacy rows authored under the singular schema lack
        # this field, so fall back to wrapping `shared_with_email` in
        # a one-element list for engagement-read consumers.
        legacy_singular = s.get("shared_with_email")
        recipient_emails = (
            s.get("recipient_emails")
            or ([legacy_singular] if legacy_singular else [])
        )
        shares.append({
            "id": s.get("id"),
            "recipient_emails": recipient_emails,
            "shared_with_name": s.get("shared_with_name"),
            "shared_with_email": legacy_singular,
            "shared_by_name": s.get("shared_by_name"),
            "message": s.get("message", ""),
            "created_at": s.get("created_at"),
        })

    # -- Linked documents (ancestors + descendants, excluding self).
    linked: List[Dict[str, Any]] = []
    seen_ids: set = {doc_id}

    # Ancestors (chain via related_doc_id pointer)
    parent_id = doc.get("related_doc_id")
    while parent_id and parent_id not in seen_ids:
        p = await db.documents.find_one(
            {"id": parent_id, "context_id": context_id, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1, "name": 1, "relation_type": 1, "created_at": 1, "related_doc_id": 1},
        )
        if not p:
            break
        seen_ids.add(p["id"])
        linked.append({
            "id": p["id"],
            "name": p.get("name") or "Untitled",
            "relation": "previous version",
            "created_at": p.get("created_at"),
        })
        parent_id = p.get("related_doc_id")

    # Descendants (anything pointing TO this doc OR any ancestor we collected)
    desc_cursor = db.documents.find(
        {
            "context_id": context_id,
            "related_doc_id": {"$in": list(seen_ids)},
            "id": {"$nin": list(seen_ids)},
            "status": {"$ne": "archived"},
        },
        {"_id": 0, "id": 1, "name": 1, "relation_type": 1, "created_at": 1, "related_doc_id": 1},
    ).sort("created_at", 1)
    async for d in desc_cursor:
        rel = d.get("relation_type") or "follow_up"
        linked.append({
            "id": d["id"],
            "name": d.get("name") or "Untitled",
            "relation": rel.replace("_", " "),
            "created_at": d.get("created_at"),
        })

    return {
        "view_count": total_views,
        "unique_readers": len(readers),
        "readers": readers,
        "share_count": len(shares),
        "shares": shares,
        "linked_count": len(linked),
        "linked_documents": linked,
    }
