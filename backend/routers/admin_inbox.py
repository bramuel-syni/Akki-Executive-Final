"""Phase P5.8.2 (2026-02) — Admin "Akki Inbox" surface.

A read-side view onto every inbound email the application receives,
written from `_dispatch_inbound_payload` BEFORE provider-specific
routing happens. The Akki Inbox shows every inbound regardless of
how the dispatch handled it (queued for review, attached to a task,
quarantined, dropped) so the admin always has visibility.

Endpoints (all super-admin + MFA + CSRF where state-changing):

  GET  /api/admin/inbox/messages?status=&since=&q=&limit=&skip=
       → list with pagination + filter
  GET  /api/admin/inbox/messages/{id}
       → detail view; marks row as `read` on first open
  POST /api/admin/inbox/messages/{id}/status
       → toggle read / replied / dismissed

The capture itself happens in `inbound_email.py`'s
`_dispatch_inbound_payload` (single-line addition that writes a row
to `admin_inbox_messages` at the very start of the function). This
file owns the read-side + state transitions only.

Stored doc shape:
  {
    id:              str (uuid hex),
    received_at:     ISO str,
    provider:        "sendgrid" | "postmark" | "unknown",
    from_email:      str (LC),
    from_name:       str,
    to_addresses:    list[str] (raw, multi-recipient supported),
    subject:         str,
    body_snippet:    str (first 240 chars of text, no HTML),
    text_body:       str (full text, up to 64KB capped)
    html_body:       str (full html, up to 256KB capped; sanitized on render)
    attachments:     list[{name, content_type, size_bytes, sg_attachment_id}],
    message_id:      str (provider message id),
    mailbox_hash:    str (the routing local-part used)
    routing_result:  str ("task_reply" | "context_doc" | "quarantine" |
                          "cycle_reply" | "no_match" | "error")
    routing_target:  str (the entity id the inbound ended up attached to,
                          if any — e.g. task_id, context_id)
    status:          "new" | "read" | "replied" | "dismissed"
    read_at:         Optional[ISO]
    read_by:         Optional[admin_id]
    replied_at:      Optional[ISO]
    dismissed_at:    Optional[ISO]
  }

Audit log writes:
  - `admin.inbox.opened`     — first time an admin opens a row (status: new → read)
  - `admin.inbox.status_set` — explicit status toggle

Body sanitization: the HTML body is stored verbatim but rendered
through DOMPurify on the frontend. This file does NOT sanitize at
write time — that's a render-side concern; sanitizing at write
would lose data that turns out useful in forensics.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, get_current_account, iso as _iso, now as _now, write_audit

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/inbox", tags=["admin-inbox"])


async def _require_super_admin_with_mfa(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Local copy of the same gate used by admin_cohort_applications —
    keeps the dependency surface narrow without cross-router imports."""
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    import os as _os
    grace = {
        e.strip().lower() for e in
        (_os.environ.get("MFA_ADMIN_GRACE_EMAILS", "admin@akki.ai")).split(",")
        if e.strip()
    }
    if (current.get("email") or "").lower() not in grace and not current.get("mfa_enabled"):
        raise HTTPException(status_code=428, detail={
            "code": "mfa_enrolment_required",
            "message": "Enrol MFA before viewing the admin inbox.",
            "enrol_url": "/app/security",
        })
    return current

# Body size caps (defensive — a truly huge email gets truncated; the
# original lives in inbound_queue_raw or task_inbound_emails for
# forensic recovery).
_TEXT_CAP_BYTES = 64 * 1024
_HTML_CAP_BYTES = 256 * 1024


def make_admin_inbox_doc(payload: Dict[str, Any], *, routing_result: str,
                         routing_target: Optional[str] = None) -> Dict[str, Any]:
    """Convert a normalized inbound payload (the Postmark-shape dict
    produced by `_dispatch_inbound_payload`) into the admin-inbox
    row shape. Pure — no side effects."""
    text_body = (payload.get("TextBody") or "")[:_TEXT_CAP_BYTES]
    html_body = (payload.get("HtmlBody") or "")[:_HTML_CAP_BYTES]

    # Snippet: collapse whitespace, take 240 chars, prefer text body.
    raw_snippet = text_body
    if not raw_snippet and html_body:
        # Crude HTML strip for the snippet only.
        raw_snippet = re.sub(r"<[^>]+>", " ", html_body)
    snippet = re.sub(r"\s+", " ", raw_snippet).strip()[:240]

    attachments_in = payload.get("Attachments") or []
    attachments_out = []
    for a in attachments_in[:30]:  # cap to 30 attachments for sanity
        if not isinstance(a, dict):
            continue
        attachments_out.append({
            "name":         (a.get("Name") or "")[:240],
            "content_type": (a.get("ContentType") or "")[:120],
            "size_bytes":   int(a.get("ContentLength") or 0),
        })

    from_full = payload.get("FromFull") or {}
    to_full = payload.get("ToFull") or []
    to_addresses = [
        (entry.get("Email") or "")[:200]
        for entry in to_full if isinstance(entry, dict)
    ] or [(payload.get("To") or "")[:200]]
    to_addresses = [a for a in to_addresses if a]

    return {
        "id":             uuid.uuid4().hex,
        "received_at":    _iso(_now()),
        "provider":       payload.get("_provider") or "unknown",
        "from_email":     (payload.get("From") or "").lower()[:200],
        "from_name":      (from_full.get("Name") or payload.get("FromName") or "")[:200],
        "to_addresses":   to_addresses[:10],
        "subject":        (payload.get("Subject") or "")[:240],
        "body_snippet":   snippet,
        "text_body":      text_body,
        "html_body":      html_body,
        "attachments":    attachments_out,
        "message_id":     (payload.get("MessageID") or "")[:160],
        "mailbox_hash":   (payload.get("MailboxHash") or "")[:160],
        "routing_result": routing_result,
        "routing_target": routing_target,
        "status":         "new",
        "read_at":        None,
        "read_by":        None,
        "replied_at":     None,
        "dismissed_at":   None,
    }


async def capture_for_admin_inbox(payload: Dict[str, Any], *, routing_result: str,
                                  routing_target: Optional[str] = None) -> str:
    """Hook called from `_dispatch_inbound_payload` — writes the row,
    returns the id. Errors are swallowed (capture must never block
    dispatch)."""
    try:
        doc = make_admin_inbox_doc(
            payload, routing_result=routing_result, routing_target=routing_target,
        )
        await db.admin_inbox_messages.insert_one(dict(doc))
        # Phase P5.9.2 — bust the unread-count cache so the badge
        # reflects the new arrival on the next poll (without waiting
        # the full 30s TTL).
        _unread_count_cache["expires_at"] = 0
        return doc["id"]
    except Exception as e:  # noqa: BLE001
        log.warning("admin_inbox capture failed: %s", str(e)[:160])
        return ""


# ─── Phase P5.9.2 (2026-02) — unread-count cache ──────────────────────
# Cheap in-process cache so the polling badge doesn't hammer the
# collection. The cache is per-process; multi-replica deploys each
# carry their own copy, which is fine for a courtesy indicator
# (stale by up to 30s is acceptable). Status transitions in
# `set_inbox_message_status` and new captures also bust the cache
# explicitly so the badge stays close to real time.
import time as _time

_unread_count_cache: Dict[str, Any] = {"value": 0, "expires_at": 0}
_UNREAD_CACHE_TTL_SECONDS = 30


@router.get("/unread-count")
async def get_unread_count(
    admin: Dict[str, Any] = Depends(_require_super_admin_with_mfa),
) -> Dict[str, Any]:
    """Returns the count of admin_inbox_messages with status='new'.

    Cached for 30s in-process. Status writes (set_inbox_message_status,
    capture_for_admin_inbox) bust the cache so the next poll is fresh.
    Hidden from non-super-admin sessions via the dependency."""
    now = _time.monotonic()
    if now < _unread_count_cache["expires_at"]:
        return {"count": _unread_count_cache["value"], "cached": True}
    count = await db.admin_inbox_messages.count_documents({"status": "new"})
    _unread_count_cache["value"] = int(count)
    _unread_count_cache["expires_at"] = now + _UNREAD_CACHE_TTL_SECONDS
    return {"count": int(count), "cached": False}


# ─── List ─────────────────────────────────────────────────────────────
@router.get("/messages")
async def list_inbox_messages(
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    admin: Dict[str, Any] = Depends(_require_super_admin_with_mfa),
) -> Dict[str, Any]:
    limit = max(1, min(limit, 200))
    skip = max(0, skip)
    query: Dict[str, Any] = {}
    if status and status in ("new", "read", "replied", "dismissed"):
        query["status"] = status
    if q:
        q_safe = q.strip()[:120]
        if q_safe:
            # Simple text search across subject / from / body snippet.
            rx = {"$regex": re.escape(q_safe), "$options": "i"}
            query["$or"] = [
                {"subject": rx},
                {"from_email": rx},
                {"from_name": rx},
                {"body_snippet": rx},
            ]
    total = await db.admin_inbox_messages.count_documents(query)
    cursor = db.admin_inbox_messages.find(
        query,
        {"_id": 0, "text_body": 0, "html_body": 0},  # bodies excluded from list
    ).sort("received_at", -1).skip(skip).limit(limit)
    rows: List[Dict[str, Any]] = []
    async for r in cursor:
        rows.append(r)
    return {"items": rows, "total": total, "limit": limit, "skip": skip}


# ─── Detail ───────────────────────────────────────────────────────────
@router.get("/messages/{message_id}")
async def get_inbox_message(
    message_id: str,
    admin: Dict[str, Any] = Depends(_require_super_admin_with_mfa),
) -> Dict[str, Any]:
    row = await db.admin_inbox_messages.find_one({"id": message_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "Inbox message not found.",
        })
    # Mark as read on first open.
    if row.get("status") == "new":
        await db.admin_inbox_messages.update_one(
            {"id": message_id},
            {"$set": {
                "status": "read",
                "read_at": _iso(_now()),
                "read_by": admin.get("id"),
            }},
        )
        # P5.9.2 — bust the badge cache.
        _unread_count_cache["expires_at"] = 0
        try:
            await write_audit(
                None, admin.get("id"),
                "admin.inbox.opened", "admin_inbox_messages", message_id,
                {"subject_prefix": (row.get("subject") or "")[:60]},
            )
        except Exception:  # noqa: BLE001
            pass
        row["status"] = "read"
        row["read_at"] = _iso(_now())
        row["read_by"] = admin.get("id")
    return {"item": row}


class _StatusIn(BaseModel):
    status: str = Field(..., pattern="^(new|read|replied|dismissed)$")


@router.post("/messages/{message_id}/status")
async def set_inbox_message_status(
    message_id: str,
    body: _StatusIn,
    admin: Dict[str, Any] = Depends(_require_super_admin_with_mfa),
) -> Dict[str, Any]:
    set_fields: Dict[str, Any] = {"status": body.status}
    now_iso = _iso(_now())
    if body.status == "replied":
        set_fields["replied_at"] = now_iso
    elif body.status == "dismissed":
        set_fields["dismissed_at"] = now_iso
    elif body.status == "read":
        set_fields["read_at"] = now_iso
        set_fields["read_by"] = admin.get("id")
    elif body.status == "new":
        # Re-opening a row — clear the read/replied/dismissed stamps.
        set_fields["read_at"] = None
        set_fields["read_by"] = None
        set_fields["replied_at"] = None
        set_fields["dismissed_at"] = None
    result = await db.admin_inbox_messages.update_one(
        {"id": message_id},
        {"$set": set_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "Inbox message not found.",
        })
    # P5.9.2 — bust the badge cache.
    _unread_count_cache["expires_at"] = 0
    try:
        await write_audit(
            None, admin.get("id"),
            "admin.inbox.status_set", "admin_inbox_messages", message_id,
            {"new_status": body.status},
        )
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "status": body.status}
