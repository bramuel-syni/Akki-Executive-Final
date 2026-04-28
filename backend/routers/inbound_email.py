"""Inbound email — Postmark webhook receiver.

Allows users to forward emails (with attachments) into AKKI. Each user gets a
unique inbound address of the form:

    inbound+<account_token>@<INBOUND_DOMAIN>
    inbound+<account_token>.<context_token>@<INBOUND_DOMAIN>   ← context-scoped

When Postmark receives an email at this address it POSTs a JSON payload to
this endpoint. We verify the call (via Basic-Auth in the URL or a shared
secret in the path), look up the recipient by mailbox-hash, parse the body
+ attachments into a `documents` row, and run the standard text-extraction
pipeline so the email becomes a first-class AKKI document.

Postmark's official inbound JSON shape — including the `MailboxHash`
plus-addressing field, base64-encoded `Attachments`, and headers — is
documented at https://postmarkapp.com/developer/webhooks/inbound-webhook.
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from core import db, iso, now, write_audit
from documents_service import (
    extract_text,
    make_preview,
    save_to_storage,
    virus_scan_stub,
)

logger = logging.getLogger("akki.inbound")

router = APIRouter(prefix="/api/inbound", tags=["inbound"])


# ---------------------------------------------------------------------------
# Auth — Postmark signs nothing, so we rely on a shared secret in the URL
# (passed as ?secret=…). Postmark stores this in their server config and
# replays it on every webhook call. The token is held in env as
# POSTMARK_WEBHOOK_SECRET. If it's not configured, we fall back to the
# server token itself (so single-key setups still work).
# ---------------------------------------------------------------------------
def _expected_secret() -> str:
    return (
        os.environ.get("POSTMARK_WEBHOOK_SECRET")
        or os.environ.get("POSTMARK_SERVER_TOKEN")
        or ""
    ).strip()


def _verify_secret(provided: Optional[str]) -> None:
    expected = _expected_secret()
    if not expected:
        # No secret configured at all — refuse to accept inbound mail.
        raise HTTPException(status_code=503, detail="Inbound mail not configured.")
    if not provided or not secrets.compare_digest(provided.strip(), expected):
        raise HTTPException(status_code=401, detail="Invalid inbound secret.")


# ---------------------------------------------------------------------------
# Mailbox-hash → (account_id, context_id?) resolution.
# Forward addresses look like:
#   inbound+<account_token>@…              → personal inbox, no context
#   inbound+<account_token>.<ctx_token>@…  → routed to a specific context
# Tokens are 8-char URL-safe slugs we mint on first use and persist on
# `accounts.inbound_token` and `contexts.inbound_token`.
# ---------------------------------------------------------------------------
async def _resolve_mailbox(mailbox_hash: str) -> Dict[str, Any]:
    raw = (mailbox_hash or "").strip().lower()
    if not raw:
        raise HTTPException(status_code=400, detail="Missing MailboxHash.")
    parts = raw.split(".", 1)
    account_token = parts[0]
    context_token = parts[1] if len(parts) > 1 else None

    account = await db.accounts.find_one(
        {"inbound_token": account_token},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "inbound_token": 1},
    )
    if not account:
        raise HTTPException(status_code=404, detail="Unknown inbound recipient.")

    context: Optional[Dict[str, Any]] = None
    if context_token:
        context = await db.contexts.find_one(
            {"inbound_token": context_token, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1, "name": 1, "inbound_token": 1},
        )
        if not context:
            # Context-scoped address that no longer resolves — fall back to
            # the user's default context rather than dropping the email.
            context = None

    if context is None:
        # Pick the user's first active membership context as fallback.
        m = await db.memberships.find_one(
            {"account_id": account["id"], "status": "active"},
            {"_id": 0, "context_id": 1},
            sort=[("created_at", 1)],
        )
        if not m:
            raise HTTPException(status_code=404, detail="Recipient has no contexts.")
        context = await db.contexts.find_one(
            {"id": m["context_id"]},
            {"_id": 0, "id": 1, "name": 1},
        )
        if not context:
            raise HTTPException(status_code=404, detail="Recipient context missing.")

    # Verify membership before ingesting (defence-in-depth).
    membership = await db.memberships.find_one(
        {"account_id": account["id"], "context_id": context["id"], "status": "active"},
        {"_id": 0, "role": 1},
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Recipient is not a member of that context.")

    return {"account": account, "context": context}


# ---------------------------------------------------------------------------
# Token mint endpoint — returns the user's personal inbound address (and a
# context-scoped one if a context_id is supplied). Idempotent: tokens are
# minted once and reused.
# ---------------------------------------------------------------------------
def _mint_token() -> str:
    # 8 chars URL-safe, lowercase only (mailbox-hash is case-insensitive).
    return secrets.token_urlsafe(6).lower().replace("_", "").replace("-", "")[:8].rjust(8, "x")


def _inbound_domain() -> str:
    return os.environ.get("POSTMARK_INBOUND_DOMAIN", "inbound.akki.ai").strip().lower()


@router.get("/address")
async def get_inbound_address(request: Request, context_id: Optional[str] = Query(None)):
    """Return the user's forwarding address (and a context-scoped variant)."""
    from core import get_current_account
    account = await get_current_account(request)

    account_token = (account.get("inbound_token") or "").strip()
    if not account_token:
        account_token = _mint_token()
        await db.accounts.update_one(
            {"id": account["id"]}, {"$set": {"inbound_token": account_token}}
        )

    domain = _inbound_domain()
    base = f"inbound+{account_token}@{domain}"

    ctx_address = None
    if context_id:
        # Confirm membership.
        m = await db.memberships.find_one(
            {"account_id": account["id"], "context_id": context_id, "status": "active"},
            {"_id": 0, "role": 1},
        )
        if not m:
            raise HTTPException(status_code=403, detail="Not a member of that context.")
        ctx = await db.contexts.find_one(
            {"id": context_id}, {"_id": 0, "id": 1, "inbound_token": 1, "name": 1}
        )
        if ctx:
            ctx_token = (ctx.get("inbound_token") or "").strip()
            if not ctx_token:
                ctx_token = _mint_token()
                await db.contexts.update_one(
                    {"id": context_id}, {"$set": {"inbound_token": ctx_token}}
                )
            ctx_address = f"inbound+{account_token}.{ctx_token}@{domain}"

    return {
        "address": base,
        "context_address": ctx_address,
        "domain": domain,
        "configured": bool(_expected_secret()),
    }


# ---------------------------------------------------------------------------
# Webhook receiver. Postmark POSTs JSON; we 200 even on soft-errors so the
# retry storm doesn't pile up — errors are logged for ops review.
# ---------------------------------------------------------------------------
def _detect_minutes(subject: str, attachment_names: List[str]) -> bool:
    s = (subject or "").lower()
    if any(k in s for k in ["minutes", "board minutes", "minute of", "mom "]):
        return True
    for n in attachment_names:
        if "minute" in (n or "").lower():
            return True
    return False


def _pick_primary_attachment(attachments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pick the most useful attachment to materialise as the document body.
    Prefer pdf/docx/txt over images; otherwise return the first."""
    if not attachments:
        return None
    pref = ("application/pdf", "application/vnd.openxmlformats-officedocument", "text/")
    for prefix in pref:
        for a in attachments:
            ct = (a.get("ContentType") or "").lower()
            if ct.startswith(prefix):
                return a
    return attachments[0]


@router.post("/postmark")
async def receive_postmark_inbound(request: Request, secret: Optional[str] = Query(None)):
    _verify_secret(secret)

    try:
        payload = await request.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Postmark inbound: invalid JSON: %s", e)
        # Return 200 so Postmark doesn't retry; log for ops.
        return {"ok": False, "error": "invalid_json"}

    mailbox_hash = (payload.get("MailboxHash") or "").strip()
    subject = (payload.get("Subject") or "").strip() or "(no subject)"
    text_body = (payload.get("TextBody") or "").strip()
    html_body = (payload.get("HtmlBody") or "").strip()
    from_email = (payload.get("From") or "").strip().lower()
    from_name = (payload.get("FromName") or "").strip()
    message_id = (payload.get("MessageID") or "").strip()
    attachments_raw = payload.get("Attachments") or []

    if not mailbox_hash:
        # Try ToFull[0].MailboxHash as a fallback.
        to_full = payload.get("ToFull") or []
        if to_full and isinstance(to_full, list):
            mailbox_hash = (to_full[0] or {}).get("MailboxHash", "")

    try:
        resolved = await _resolve_mailbox(mailbox_hash)
    except HTTPException as e:
        logger.warning(
            "Postmark inbound: unresolved mailbox %r from %s — %s",
            mailbox_hash, from_email, e.detail,
        )
        # 200 OK — no retry.
        return {"ok": False, "error": "unresolved_recipient", "mailbox": mailbox_hash}

    account = resolved["account"]
    context = resolved["context"]

    # Idempotency — if we've already ingested this MessageID, return early.
    if message_id:
        existing = await db.documents.find_one(
            {"context_id": context["id"], "inbound_message_id": message_id},
            {"_id": 0, "id": 1},
        )
        if existing:
            return {"ok": True, "duplicate": True, "doc_id": existing["id"]}

    # Materialise the document. If there's a primary attachment we use that
    # as the body; otherwise we fall back to the email text itself.
    primary_att = _pick_primary_attachment(attachments_raw)
    doc_id = str(uuid.uuid4())
    created_at = iso(now())

    if primary_att:
        try:
            data = base64.b64decode(primary_att.get("Content") or "")
        except Exception as e:  # noqa: BLE001
            logger.error("Postmark inbound: base64 decode failed: %s", e)
            await write_audit(
                context["id"], account["id"],
                "inbound_email.rejected", "inbound", message_id or "(no-id)",
                {"reason": "bad_attachment", "from": from_email, "subject": subject},
            )
            return {"ok": False, "error": "bad_attachment"}
        filename = primary_att.get("Name") or "attachment"
        clean, reason = virus_scan_stub(data, filename)
        if not clean:
            logger.warning("Postmark inbound: rejected attachment (%s) — %s", filename, reason)
            await write_audit(
                context["id"], account["id"],
                "inbound_email.rejected", "inbound", message_id or "(no-id)",
                {"reason": "virus_scan", "scan_reason": reason,
                 "from": from_email, "subject": subject, "filename": filename},
            )
            return {"ok": False, "error": "virus_scan", "reason": reason}
        storage_key = save_to_storage(context["id"], doc_id, filename, data)
        text, err = extract_text(data, filename, primary_att.get("ContentType") or "")
        size = len(data)
        mime = primary_att.get("ContentType") or "application/octet-stream"
        original_filename = filename
        display_name = subject or filename
    else:
        # No attachment — write the body to disk as a .txt so the standard
        # viewer can render it.
        body = text_body or html_body or "(empty email)"
        data = body.encode("utf-8", errors="replace")
        filename = f"email-{(message_id or doc_id)[:24]}.txt"
        storage_key = save_to_storage(context["id"], doc_id, filename, data)
        text, err = extract_text(data, filename, "text/plain")
        size = len(data)
        mime = "text/plain"
        original_filename = filename
        display_name = subject

    is_minutes = _detect_minutes(subject, [a.get("Name") or "" for a in attachments_raw])

    doc = {
        "id": doc_id,
        "context_id": context["id"],
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
        "uploaded_by": account["id"],
        "uploaded_by_email": account.get("email"),
        "mentioned_account_ids": [],
        "related_doc_id": None,
        "relation_type": None,
        "error": err,
        "created_at": created_at,
        "updated_at": created_at,
        # Inbound-specific provenance
        "source": "inbound_email",
        "inbound_message_id": message_id or None,
        "inbound_from_email": from_email or None,
        "inbound_from_name": from_name or None,
        "inbound_subject": subject,
        "inbound_attachment_count": len(attachments_raw),
        "doc_type": "minutes" if is_minutes else None,
    }
    await db.documents.insert_one(doc)

    await write_audit(
        context["id"], account["id"],
        "document.inbound_email", "document", doc_id,
        {
            "from": from_email,
            "subject": subject,
            "attachments": len(attachments_raw),
            "minutes": is_minutes,
        },
    )

    logger.info(
        "Postmark inbound: ingested message %s from %s into ctx=%s as doc=%s",
        message_id, from_email, context["id"], doc_id,
    )

    return {
        "ok": True,
        "doc_id": doc_id,
        "context_id": context["id"],
        "account_id": account["id"],
        "minutes": is_minutes,
    }
