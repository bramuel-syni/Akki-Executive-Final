"""Phase P5.17 (2026-02) — Non-admin source-message preview.

Tenant-scoped read-only view onto an `admin_inbox_messages` row
that was the source of a routed item (task / cycle update / signal
/ discussion artifact). Non-admins click an origin chip on a
routed row and land here; admins use the admin-inbox surface from
P5.16 instead.

The tenant guard:
  • The admin_inbox_messages row is global (no `account_id` on the
    document itself), so we resolve "this caller's tenant matches
    this message's tenant" by checking `classification.target_hint.account_id`
    against the caller's own `account_id`.
  • If the message has no `classification` yet (never auto-classified
    AND never manually classified), we treat it as not-routed-to-anyone
    → 404 for non-admin callers.
  • Cross-tenant lookups → 404 (existence-leak guard; never 403).

Every preview access writes a row to `source_view_log` for the
tenant audit trail.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core import db, get_current_account, iso as _iso, now as _now

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox", tags=["inbox-message-preview"])


def _strip_html_to_text(html: str) -> str:
    """Crude HTML strip for the preview. We never render HTML for
    non-admin previews — only sanitised text. Heavy sanitisation
    lives on the admin surface (DOMPurify-side)."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_preview(row: Dict[str, Any]) -> Dict[str, Any]:
    """Strip ObjectId, drop the html_body to text, cap text length."""
    body_text = (row.get("text_body") or "")[:8000]
    if not body_text and row.get("html_body"):
        body_text = _strip_html_to_text(row.get("html_body") or "")[:8000]
    cls = row.get("classification") or {}
    return {
        "id":              row.get("id"),
        "received_at":     row.get("received_at"),
        "from_email":      row.get("from_email"),
        "from_name":       row.get("from_name"),
        "subject":         row.get("subject"),
        "body_text":       body_text,
        "attachment_count": len(row.get("attachments") or []),
        "classification": {
            "route_kind":      cls.get("route_kind"),
            "confidence":      cls.get("confidence"),
            "rationale":       cls.get("rationale"),
            "classified_at":   cls.get("classified_at"),
        } if cls else None,
    }


async def _write_source_view_log(*, account_id: str, message_id: str,
                                  user_id: str) -> None:
    """Append-only tenant audit trail for preview accesses."""
    try:
        await db.source_view_log.insert_one({
            "id":          uuid.uuid4().hex,
            "account_id":  account_id,
            "user_id":     user_id,
            "message_id":  message_id,
            "viewed_at":   _iso(_now()),
            "surface":     "inbox.message_preview",
        })
    except Exception as e:  # noqa: BLE001 — audit must never block
        log.warning("[P5.17] source_view_log write failed: %s", e)


@router.get("/messages/{message_id}/preview")
async def preview_source_message(
    message_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Tenant-scoped read-only preview of the inbox message that
    seeded a routed item visible to this caller.

    Tenant resolution: a message is visible to the caller iff
      • the caller is a superadmin, OR
      • the message's `classification.target_hint.account_id`
        matches the caller's `account_id`.

    Any other state → 404. We DO NOT 403 on cross-tenant access —
    that would leak existence; 404 is the only correct response.
    """
    if not message_id or not isinstance(message_id, str):
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "Message not found.",
        })
    row = await db.admin_inbox_messages.find_one(
        {"id": message_id}, {"_id": 0},
    )
    # Same 404 for missing-row AND cross-tenant — caller can't tell
    # which case fired.
    is_super = bool(current.get("is_superadmin"))
    caller_account_id = current.get("id")
    if not row:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "Message not found.",
        })
    if not is_super:
        cls = row.get("classification") or {}
        owner_id = (cls.get("target_hint") or {}).get("account_id")
        if owner_id != caller_account_id:
            raise HTTPException(status_code=404, detail={
                "code": "not_found", "message": "Message not found.",
            })
    payload = _sanitize_preview(row)
    # Audit — only when the caller is the tenant owner. Superadmin
    # views are already audited via `admin.inbox.opened`.
    if not is_super and caller_account_id:
        await _write_source_view_log(
            account_id=caller_account_id,
            message_id=message_id,
            user_id=caller_account_id,
        )
    return {"item": payload}


__all__ = ["router"]
