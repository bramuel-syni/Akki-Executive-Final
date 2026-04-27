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
from email_service import send_email

logger = logging.getLogger("akki.shares")

router = APIRouter(prefix="/api")


ItemType = Literal["signal", "briefing", "brief", "doc_summary", "doc_evolution"]
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
    if item_type == "brief":
        # Lightweight Prepare-tab brief (collection: briefs). Authoring-user-
        # scoped is enforced upstream via require_context_membership; the
        # brief itself is owned by an account but anyone in the context can
        # forward it on (matches the "send a colleague this brief" flow).
        return await db.briefs.find_one({"id": item_id, "context_id": context_id}, {"_id": 0})
    if item_type == "doc_summary":
        # The artefact is the document — but we only allow sharing once an
        # AKKI summary has been generated. Otherwise there's nothing
        # readable to send.
        d = await db.documents.find_one({"id": item_id, "context_id": context_id}, {"_id": 0})
        if d and d.get("akki_summary", {}).get("tldr"):
            return d
        return None
    if item_type == "doc_evolution":
        # Need both: an evolution_diff cached AND a related_doc_id link.
        d = await db.documents.find_one({"id": item_id, "context_id": context_id}, {"_id": 0})
        if d and d.get("evolution_diff", {}).get("diff", {}).get("what_changed") and d.get("related_doc_id"):
            return d
        return None
    return None


def _preview_from_item(item_type: str, item: Dict[str, Any]) -> str:
    if item_type == "signal":
        return (item.get("headline") or "")[:240]
    if item_type == "briefing":
        return (item.get("title") or "")[:240]
    if item_type == "brief":
        return (item.get("title") or item.get("objective") or "Brief")[:240]
    if item_type == "doc_summary":
        # Lead with the document name; the TL;DR goes into the email body.
        return (item.get("name") or item.get("original_filename") or "Document summary")[:240]
    if item_type == "doc_evolution":
        return (item.get("name") or item.get("original_filename") or "Document evolution")[:240]
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
        "status": "delivered" if recipient_account_id else ("queued" if body.delivery_method == "email" else "delivered"),
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
        # Real send via Resend. The deck PDF or briefing PDF link is
        # included so the recipient can view it without an AKKI account.
        # Failures are logged but the share record still persists; the
        # sender can re-send from the outbox.
        try:
            if body.item_type == "briefing":
                artefact_path = "briefings"
                view_url = f"{__import__('os').environ.get('FRONTEND_ORIGIN', '').rstrip('/')}/app/{artefact_path}/{body.item_id}"
            elif body.item_type == "signal":
                artefact_path = "highlights"
                view_url = f"{__import__('os').environ.get('FRONTEND_ORIGIN', '').rstrip('/')}/app/{artefact_path}/{body.item_id}"
            else:  # doc_summary or doc_evolution — both link into workspace
                view_url = f"{__import__('os').environ.get('FRONTEND_ORIGIN', '').rstrip('/')}/app/workspace/{body.item_id}"

            # For doc_summary shares, surface AKKI's summary in the email body
            # so the recipient gets the read even before clicking through.
            summary_block = ""
            if body.item_type == "doc_summary":
                s = (item.get("akki_summary") or {})
                tldr = (s.get("tldr") or "").strip()
                highlights = [str(h) for h in (s.get("highlights") or []) if str(h).strip()]
                questions = [str(q) for q in (s.get("questions") or []) if str(q).strip()]
                if tldr:
                    summary_block += (
                        f"<p style=\"font-size:14.5px;line-height:1.7;color:#1a1f2e;"
                        f"font-style:italic;margin:0 0 18px 0;\">{tldr}</p>"
                    )
                if highlights:
                    summary_block += (
                        "<p style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;"
                        "color:#7a6a52;margin:0 0 8px 0;\">What matters</p>"
                        "<ol style=\"font-size:13.5px;line-height:1.6;color:#3a3a3a;margin:0 0 18px 0;padding-left:20px;\">"
                        + "".join(f"<li style=\"margin-bottom:6px;\">{h}</li>" for h in highlights[:7])
                        + "</ol>"
                    )
                if questions:
                    summary_block += (
                        "<div style=\"background:#f7eee0;border:1px solid #e5d5b8;padding:14px 16px;"
                        "margin:0 0 18px 0;border-radius:3px;\">"
                        "<p style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;"
                        "color:#722f37;margin:0 0 6px 0;\">Walk in asking</p>"
                        + "".join(
                            f"<p style=\"font-size:13.5px;line-height:1.55;color:#1a1f2e;"
                            f"font-style:italic;margin:0 0 4px 0;\">\"{q}\"</p>"
                            for q in questions[:3]
                        )
                        + "</div>"
                    )

            # Doc evolution: render the LLM diff (what changed / +stronger /
            # -weakened / questions for management) directly in the email.
            elif body.item_type == "doc_evolution":
                ev = ((item.get("evolution_diff") or {}).get("diff") or {})
                what_changed = (ev.get("what_changed") or "").strip()
                added = [str(x) for x in (ev.get("added_or_strengthened") or []) if str(x).strip()]
                weak  = [str(x) for x in (ev.get("weakened_or_removed") or []) if str(x).strip()]
                qs    = [str(x) for x in (ev.get("questions_for_management") or []) if str(x).strip()]
                if what_changed:
                    summary_block += (
                        "<p style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;"
                        "color:#7a6a52;margin:0 0 6px 0;\">What changed</p>"
                        f"<p style=\"font-size:14.5px;line-height:1.7;color:#1a1f2e;"
                        f"margin:0 0 18px 0;\">{what_changed}</p>"
                    )
                if added:
                    summary_block += (
                        "<p style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;"
                        "color:#047857;margin:0 0 8px 0;\">+ Added or strengthened</p>"
                        "<ul style=\"font-size:13.5px;line-height:1.6;color:#3a3a3a;margin:0 0 16px 0;padding-left:20px;\">"
                        + "".join(f"<li style=\"margin-bottom:5px;\">{x}</li>" for x in added[:5])
                        + "</ul>"
                    )
                if weak:
                    summary_block += (
                        "<p style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;"
                        "color:#b45309;margin:0 0 8px 0;\">− Weakened or removed</p>"
                        "<ul style=\"font-size:13.5px;line-height:1.6;color:#3a3a3a;margin:0 0 16px 0;padding-left:20px;\">"
                        + "".join(f"<li style=\"margin-bottom:5px;\">{x}</li>" for x in weak[:5])
                        + "</ul>"
                    )
                if qs:
                    summary_block += (
                        "<div style=\"background:#f7eee0;border:1px solid #e5d5b8;padding:14px 16px;"
                        "margin:0 0 18px 0;border-radius:3px;\">"
                        "<p style=\"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;"
                        "color:#722f37;margin:0 0 6px 0;\">Put on the table</p>"
                        + "".join(
                            f"<p style=\"font-size:13.5px;line-height:1.55;color:#1a1f2e;"
                            f"font-style:italic;margin:0 0 4px 0;\">\"{q}\"</p>"
                            for q in qs[:3]
                        )
                        + "</div>"
                    )

            html = (
                f"<div style=\"font-family:Georgia,serif;max-width:560px;margin:0 auto;padding:32px 24px;"
                f"background:#f5efe6;color:#1a1f2e;\">"
                f"<p style=\"font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#7a6a52;"
                f"margin:0 0 16px 0;\">{share_doc['shared_by_name']} shared this with you via AKKI</p>"
                f"<h1 style=\"font-size:22px;line-height:1.3;margin:0 0 14px 0;font-weight:normal;\">"
                f"{subject}</h1>"
                + (f"<blockquote style=\"font-style:italic;color:#3a3a3a;border-left:3px solid #722f37;padding-left:14px;margin:0 0 18px 0;\">{preview}</blockquote>" if body.include_as_quote and preview and body.item_type not in ("doc_summary", "doc_evolution") else "")
                + summary_block
                + (f"<p style=\"font-size:14px;line-height:1.7;color:#3a3a3a;margin:0 0 24px 0;\">{message}</p>" if message else "")
                + (f"<a href=\"{view_url}\" style=\"display:inline-block;background:#722f37;color:#fff;padding:11px 22px;text-decoration:none;font-size:13px;letter-spacing:0.05em;\">Open in AKKI &rarr;</a>" if view_url else "")
                + "<p style=\"font-size:11px;color:#7a6a52;margin:32px 0 0 0;\">Sent via AKKI · for executives</p>"
                + "</div>"
            )
            send_result = await send_email(
                to=recipient_email,
                subject=subject,
                html=html,
                text=f"{share_doc['shared_by_name']} shared this with you via AKKI:\n\n{subject}\n\n{message}\n\n{preview}",
            )
            share_doc["email_send_id"] = send_result.get("id")
            share_doc["email_send_mode"] = send_result.get("mode")
            await db.shares.update_one(
                {"id": share_doc["id"]},
                {"$set": {
                    "email_send_id": send_result.get("id"),
                    "email_send_mode": send_result.get("mode"),
                    "status": "sent" if send_result.get("id") else "queued",
                }},
            )
            share_doc["status"] = "sent" if send_result.get("id") else "queued"
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Share email failed to send: to=%s subject=%r err=%s",
                recipient_email, subject, e,
            )
            await db.shares.update_one(
                {"id": share_doc["id"]},
                {"$set": {"status": "send_failed", "send_error": str(e)[:500]}},
            )
            share_doc["status"] = "send_failed"

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
        {"context_id": {"$in": active_ctx_ids}, "status": {"$ne": "archived"}},
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
