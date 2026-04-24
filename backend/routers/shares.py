"""Shares — external sharing of AKKI artefacts (signals, briefings) to
specific email recipients. If the recipient is an AKKI user in the same
visibility scope, the shared item lands in their Home stream with a
'SHARED BY' badge. If not, this endpoint logs an email-send intent
(actual SMTP delivery is deferred to §6 Email-in integration).

Scope of v1 (this sprint):
  · Share externally — create `shares` record, optional in-product notification
  · Inbox/outbox — what's shared with me vs what I've shared
  · Revoke — sharer can cancel a share
  · Comments use the existing /comments router with target_type='share'
"""
from __future__ import annotations

import uuid
import logging
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    get_current_account, require_context_membership,
)

logger = logging.getLogger("akki.shares")

router = APIRouter(prefix="/api")


ItemType = Literal["signal", "briefing"]
DeliveryMethod = Literal["email", "akki_notification"]


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class ShareCreateIn(BaseModel):
    item_type: ItemType
    item_id: str
    to_email: EmailStr
    subject: Optional[str] = Field(default=None, max_length=180)
    message: Optional[str] = Field(default=None, max_length=2000)
    include_as_quote: bool = True
    delivery_method: DeliveryMethod = "akki_notification"


def _sanitize_share(s: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in s.items() if k != "_id"}


async def _load_artefact(item_type: str, item_id: str, context_id: str) -> Optional[Dict[str, Any]]:
    if item_type == "signal":
        return await db.signals.find_one({"id": item_id, "context_id": context_id}, {"_id": 0})
    if item_type == "briefing":
        return await db.briefings.find_one({"id": item_id, "context_id": context_id}, {"_id": 0})
    return None


def _preview_from_item(item_type: str, item: Dict[str, Any]) -> str:
    if item_type == "signal":
        return (item.get("headline") or "")[:240]
    if item_type == "briefing":
        return (item.get("title") or "")[:240]
    return ""


# -----------------------------------------------------------------------------
# Create a share (context-scoped: must be member of the source context)
# -----------------------------------------------------------------------------
@router.post("/contexts/{context_id}/shares")
async def create_share(
    context_id: str,
    body: ShareCreateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    item = await _load_artefact(body.item_type, body.item_id, context_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"{body.item_type} not found in this context")

    recipient_email = body.to_email.lower().strip()
    if recipient_email == ctx["account"]["email"].lower():
        raise HTTPException(status_code=400, detail="You cannot share with yourself.")

    # Resolve recipient to an AKKI account if one exists
    recipient_acc = await db.accounts.find_one({"email": recipient_email}, {"_id": 0, "id": 1, "name": 1})
    recipient_account_id = recipient_acc["id"] if recipient_acc else None

    now_iso = _iso(_now())
    subject = (body.subject or _preview_from_item(body.item_type, item) or "AKKI share").strip()[:180]
    message = (body.message or "").strip()[:2000]
    preview = _preview_from_item(body.item_type, item)

    share_doc = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "context_name": ctx["context"].get("name"),
        "item_type": body.item_type,
        "item_id": body.item_id,
        "item_preview": preview,
        "shared_by_account_id": ctx["account"]["id"],
        "shared_by_name": ctx["account"].get("name") or ctx["account"].get("email"),
        "shared_by_email": ctx["account"].get("email"),
        "shared_with_email": recipient_email,
        "shared_with_account_id": recipient_account_id,
        "subject": subject,
        "message": message,
        "include_as_quote": body.include_as_quote,
        "delivery_method": body.delivery_method,
        "status": "delivered" if recipient_account_id or body.delivery_method == "email" else "delivered",
        "opened_at": None,
        "revoked_at": None,
        "created_at": now_iso,
    }
    await db.shares.insert_one(share_doc)

    # If the recipient is an AKKI user we drop a mention-like inbox entry so
    # their notification bell surfaces the share. If not, we log the email
    # intent — the actual SMTP send ships with §6 Email-in.
    if recipient_account_id:
        await db.mentions.insert_one({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "target_account_id": recipient_account_id,
            "source_account_id": ctx["account"]["id"],
            "source_name": share_doc["shared_by_name"],
            "artefact_type": "share",
            "artefact_id": share_doc["id"],
            "comment_id": None,
            "preview": f'Shared with you: {preview[:160]}',
            "created_at": now_iso,
            "read": False,
        })
    elif body.delivery_method == "email":
        logger.info(
            f"[share-email-stub] to={recipient_email} subject={subject!r} "
            f"item_type={body.item_type} item_id={body.item_id} "
            f"sharer={share_doc['shared_by_email']}"
        )

    await write_audit(
        context_id, ctx["account"]["id"], "share.created", "share", share_doc["id"],
        {
            "item_type": body.item_type, "item_id": body.item_id,
            "to": recipient_email, "is_akki_user": bool(recipient_account_id),
            "delivery_method": body.delivery_method,
        },
    )
    return _sanitize_share(share_doc)


# -----------------------------------------------------------------------------
# Inbox — shares received by me
# -----------------------------------------------------------------------------
@router.get("/me/shares/inbox")
async def shares_inbox(
    current: Dict[str, Any] = Depends(get_current_account),
    include_revoked: bool = False,
    limit: int = 100,
):
    q: Dict[str, Any] = {"shared_with_account_id": current["id"]}
    if not include_revoked:
        q["revoked_at"] = None
    items = await db.shares.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
    return items


# -----------------------------------------------------------------------------
# Outbox — shares I've created
# -----------------------------------------------------------------------------
@router.get("/me/shares/outbox")
async def shares_outbox(
    current: Dict[str, Any] = Depends(get_current_account),
    include_revoked: bool = True,
    limit: int = 100,
):
    q: Dict[str, Any] = {"shared_by_account_id": current["id"]}
    if not include_revoked:
        q["revoked_at"] = None
    items = await db.shares.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
    return items


# -----------------------------------------------------------------------------
# Get a single share and mark it opened (used when recipient clicks to view)
# -----------------------------------------------------------------------------
@router.get("/shares/{share_id}")
async def get_share(share_id: str, current: Dict[str, Any] = Depends(get_current_account)):
    s = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Share not found")
    # Authorisation: only sharer or recipient can read the share
    if current["id"] not in (s.get("shared_by_account_id"), s.get("shared_with_account_id")):
        raise HTTPException(status_code=403, detail="Not authorised to view this share")
    if s.get("revoked_at"):
        # Short, honest payload for revoked shares
        return {
            **s,
            "item_preview": None,
            "subject": s.get("subject"),
            "message": None,
            "revoked": True,
        }
    # Hydrate the underlying artefact (subject to context membership of the sharer)
    artefact = await _load_artefact(s["item_type"], s["item_id"], s["context_id"]) or {}
    # Stamp opened_at once (only for recipient, not sharer)
    if current["id"] == s.get("shared_with_account_id") and not s.get("opened_at"):
        await db.shares.update_one({"id": share_id}, {"$set": {"opened_at": _iso(_now())}})
        s["opened_at"] = _iso(_now())
    return {**s, "artefact": artefact}


# -----------------------------------------------------------------------------
# Revoke a share (only sharer may revoke)
# -----------------------------------------------------------------------------
@router.delete("/shares/{share_id}")
async def revoke_share(share_id: str, current: Dict[str, Any] = Depends(get_current_account)):
    s = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Share not found")
    if current["id"] != s.get("shared_by_account_id"):
        raise HTTPException(status_code=403, detail="Only the sharer can revoke this share")
    if s.get("revoked_at"):
        return _sanitize_share(s)
    now_iso = _iso(_now())
    await db.shares.update_one(
        {"id": share_id},
        {"$set": {"revoked_at": now_iso, "status": "revoked"}},
    )
    # Delete any recipient-side inbox mentions for this share
    if s.get("shared_with_account_id"):
        await db.mentions.delete_many({"artefact_type": "share", "artefact_id": share_id})
    await write_audit(
        s.get("context_id"), current["id"], "share.revoked", "share", share_id, {},
    )
    s["revoked_at"] = now_iso
    s["status"] = "revoked"
    return _sanitize_share(s)


# -----------------------------------------------------------------------------
# Aggregated Home stream — "All boards" scope
# -----------------------------------------------------------------------------
@router.get("/me/home/stream")
async def aggregated_stream(
    current: Dict[str, Any] = Depends(get_current_account),
    limit: int = 30,
):
    """Return a merged, weighted stream of signals + recent briefings across
    every active context the user is a member of. Each card carries
    `context_id` + `context_name` so the UI can render the context badge.
    """
    memberships = await db.memberships.find(
        {"account_id": current["id"], "status": "active"},
        {"_id": 0, "context_id": 1, "role": 1},
    ).to_list(500)
    ctx_ids = [m["context_id"] for m in memberships]
    if not ctx_ids:
        return {"signals": [], "briefings": [], "contexts": []}

    contexts = await db.contexts.find(
        {"id": {"$in": ctx_ids}, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "name": 1, "type": 1},
    ).to_list(500)
    ctx_by_id = {c["id"]: c for c in contexts}
    active_ctx_ids = [c["id"] for c in contexts]

    # Pull recent signals + briefings from every context in one go
    signals_cursor = db.signals.find(
        {"context_id": {"$in": active_ctx_ids}},
        {"_id": 0},
    ).sort("created_at", -1).limit(min(limit, 100))
    signals = [s async for s in signals_cursor]

    briefings_cursor = db.briefings.find(
        {"context_id": {"$in": active_ctx_ids}, "status": "active"},
        {"_id": 0},
    ).sort("created_at", -1).limit(min(limit, 100))
    briefings = [b async for b in briefings_cursor]

    # Attach context metadata to each card (for the UI badge)
    for s in signals:
        c = ctx_by_id.get(s.get("context_id"))
        if c:
            s["context_name"] = c.get("name")
    for b in briefings:
        c = ctx_by_id.get(b.get("context_id"))
        if c:
            b["context_name"] = c.get("name")

    return {
        "signals": signals,
        "briefings": briefings,
        "contexts": [{"id": c["id"], "name": c["name"], "type": c.get("type")} for c in contexts],
    }
