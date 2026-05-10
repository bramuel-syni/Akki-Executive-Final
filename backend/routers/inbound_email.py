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
)
from services import clamav_service
from services.clamav_service import ClamAVUnreachable
import email_service

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


# ---------------------------------------------------------------------------
# Sender-tier classifier — iter70 trust-tiered inbound triage.
#
#   Tier A · owner     → sender email == account.email (exact)
#                         → auto-ingest into db.documents.
#   Tier B · reportee  → sender matches db.reportees for this context (exact email)
#                         → auto-ingest with trust_tier='reportee' stamp +
#                            reportee name/title chip on the doc.
#   Tier C · unknown   → neither the owner nor a known reportee for this ctx
#                         → write to db.inbound_queue (NOT db.documents)
#                            with status='pending_review'. Owner reviews +
#                            accepts/rejects on /app/inbound-queue.
#
# Exact match only per user direction (1a). Domain-match relaxation is a
# follow-up if false-negatives show up in ops.
# ---------------------------------------------------------------------------
async def _classify_sender_tier(
    from_email: str,
    account: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    em = (from_email or "").strip().lower()
    if not em:
        return {"tier": "unknown", "reason": "missing_sender", "reportee": None}
    if em == (account.get("email") or "").strip().lower():
        return {"tier": "owner", "reason": "owner_email_match", "reportee": None}
    reportee = await db.reportees.find_one(
        {"context_id": context["id"], "email": em, "archived_at": {"$exists": False}},
        {"_id": 0},
    )
    if reportee:
        return {"tier": "reportee", "reason": "reportee_email_match", "reportee": reportee}
    return {"tier": "unknown", "reason": "sender_not_recognised", "reportee": None}


# ---------------------------------------------------------------------------
# Phase D.2 — Cycle Manager reply threading
# ---------------------------------------------------------------------------
async def _handle_cycle_reply(
    *,
    payload: Dict[str, Any],
    recipient_alias: str,
    from_email: str, from_name: str,
    subject: str, text_body: str, html_body: str,
    message_id: str,
) -> Dict[str, Any]:
    """Postmark inbound replies that hit a `<uuid>@cycles.akki.ai` alias.

    Threading: alias UUID → account_id → most-recent unanswered cycle_followups
    row whose `to_email` matches the From header (case-insensitive). We
    prefer rows that already record the alias on send (`reply_to_alias`);
    fallback recomputes the alias from `account_id` for legacy rows.

    Side effects:
      1. Append the reply onto cycle_followups.replies[] with the parsed body.
      2. Set last_reply_at and bump status from 'sent' → 'replied'.
      3. write_audit('cycle.followup.reply_received', ...).
      4. Idempotent on Postmark MessageID — repeats become a no-op.

    Inbound-only attachments are NOT processed in this branch — the
    cycle-reply use-case is a follow-up answer, not a document drop.
    """
    alias_local = email_service.cycles_alias_extract(recipient_alias)
    if not alias_local:
        logger.warning("cycle reply: alias not extractable from %s", recipient_alias)
        return {"ok": False, "error": "alias_unparseable"}

    candidate_followups = await db.cycle_followups.find(
        {"to_email": {"$regex": f"^{from_email}$", "$options": "i"},
         "status": {"$in": ["sent", "replied"]}},
        {"_id": 0, "id": 1, "context_id": 1, "account_id": 1,
         "reply_to_alias": 1, "to_email": 1, "sent_at": 1},
    ).sort("sent_at", -1).to_list(50)

    matching = None
    for fu in candidate_followups:
        if (fu.get("reply_to_alias") or "").lower() == recipient_alias.lower():
            matching = fu
            break
        try:
            alias = email_service.cycles_alias_for(fu.get("account_id") or "")
            if alias.lower() == recipient_alias.lower():
                matching = fu
                break
        except ValueError:
            continue

    if not matching:
        # Phase D.2 — alias recognised by domain shape but no followup
        # for THIS sender. Could be: (a) reportee replied from a
        # different email than the one we sent to, (b) shoulder-tap reply
        # from a third party, (c) replay after the followup row was
        # archived. Drop into db.inbound_queue with a distinct
        # source='cycles_alias_unmatched' so the owner can still
        # inspect it. Recover account/context provenance by
        # cross-referencing the alias against historical
        # cycle_followups.reply_to_alias (works for any past followup
        # that used the same alias — the alias is deterministic per
        # account).
        any_prior = await db.cycle_followups.find_one(
            {"reply_to_alias": {"$regex": f"^{recipient_alias}$", "$options": "i"}},
            {"_id": 0, "id": 1, "context_id": 1, "account_id": 1, "sent_at": 1},
            sort=[("sent_at", -1)],
        )
        if not any_prior:
            logger.warning(
                "cycle reply: alias %s does not match any historical "
                "cycle_followups row — dropping without queueing.",
                recipient_alias,
            )
            return {"ok": False, "error": "unknown_alias",
                    "alias": recipient_alias, "from": from_email}

        queue_id = str(uuid.uuid4())
        queue_rec = {
            "id": queue_id,
            "context_id": any_prior["context_id"],
            "account_id": any_prior["account_id"],
            "status": "pending_review",
            "source": "cycles_alias_unmatched",
            "review_reason": "cycles_alias_unmatched",
            "inbound_message_id": message_id or None,
            "inbound_from_email": from_email or None,
            "inbound_from_name": from_name or None,
            "inbound_subject": subject,
            "inbound_text_preview": (text_body or html_body or "")[:800],
            "inbound_attachment_count": 0,
            "inbound_attachment_summary": [],
            "has_raw_payload": False,
            "via_alias": recipient_alias,
            "alias_recovered_account_id": any_prior["account_id"],
            "alias_recovered_via_followup": any_prior["id"],
            "created_at": iso(now()),
        }
        try:
            await db.inbound_queue.insert_one(queue_rec)
        except Exception:
            logger.exception("cycle reply: inbound_queue insert failed (non-fatal)")
        try:
            await write_audit(
                any_prior["context_id"], any_prior["account_id"],
                "cycle.followup.reply_unmatched", "inbound_queue", queue_id,
                {"alias": recipient_alias, "from": from_email,
                 "subject": subject[:200]},
            )
        except Exception:
            pass
        logger.info(
            "cycle reply: dropped into inbound_queue queue_id=%s "
            "alias=%s from=%s ctx=%s",
            queue_id, recipient_alias, from_email, any_prior["context_id"],
        )
        return {"ok": True, "queued": True, "queue_id": queue_id,
                "source": "cycles_alias_unmatched",
                "alias": recipient_alias, "from": from_email}

    followup_id = matching["id"]
    context_id = matching["context_id"]
    account_id = matching["account_id"]

    if message_id:
        already = await db.cycle_followups.find_one(
            {"id": followup_id,
             "replies": {"$elemMatch": {"message_id": message_id}}},
            {"_id": 0, "id": 1},
        )
        if already:
            return {"ok": True, "duplicate": True, "followup_id": followup_id}

    reply_doc = {
        "id": str(uuid.uuid4()),
        "message_id": message_id or None,
        "from_email": from_email,
        "from_name": from_name or None,
        "subject": subject,
        "body_text": text_body[:20000],
        "body_html_excerpt": html_body[:8000],
        "received_at": iso(now()),
    }

    await db.cycle_followups.update_one(
        {"id": followup_id, "context_id": context_id},
        {"$push": {"replies": reply_doc},
         "$set": {"status": "replied", "last_reply_at": reply_doc["received_at"]}},
    )

    try:
        await write_audit(
            context_id, account_id,
            "cycle.followup.replied", "cycle_followup", followup_id,
            {"from": from_email, "subject": subject[:200],
             "message_id": message_id or None, "via_alias": recipient_alias,
             "body_chars": len(text_body)},
        )
    except Exception:
        logger.exception("cycle reply: audit write failed (non-fatal)")

    return {"ok": True, "followup_id": followup_id,
            "context_id": context_id, "via_alias": recipient_alias}




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

    # Phase D.2 — if the recipient is a cycles.akki.ai alias, this is a
    # cycle follow-up reply. Route by alias→account match BEFORE the
    # legacy MailboxHash flow.
    original_recipient = (payload.get("OriginalRecipient") or "").strip().lower()
    to_full_list = payload.get("ToFull") or []
    candidate_recipients = [original_recipient] + [
        (e or {}).get("Email", "").strip().lower() for e in (to_full_list or [])
    ]
    cycle_alias_recipient = next(
        (r for r in candidate_recipients if email_service.is_cycles_alias(r)),
        None,
    )
    if cycle_alias_recipient:
        return await _handle_cycle_reply(
            payload=payload,
            recipient_alias=cycle_alias_recipient,
            from_email=from_email, from_name=from_name,
            subject=subject, text_body=text_body, html_body=html_body,
            message_id=message_id,
        )

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

    # iter70 — classify the sender tier. Unknown senders get quarantined
    # into db.inbound_queue for the owner to review; known senders
    # (owner or reportee) continue to the live ingest path as before.
    tier_info = await _classify_sender_tier(from_email, account, context)
    tier = tier_info["tier"]
    reportee = tier_info.get("reportee")

    # Idempotency — if we've already ingested this MessageID, return early.
    if message_id:
        existing = await db.documents.find_one(
            {"context_id": context["id"], "inbound_message_id": message_id},
            {"_id": 0, "id": 1},
        )
        if existing:
            return {"ok": True, "duplicate": True, "doc_id": existing["id"],
                    "trust_tier": "pre_iter70"}
        # Also dedupe quarantined payloads so a replay doesn't double-queue.
        existing_q = await db.inbound_queue.find_one(
            {"context_id": context["id"], "inbound_message_id": message_id},
            {"_id": 0, "id": 1, "status": 1},
        )
        if existing_q:
            return {"ok": True, "duplicate": True, "queue_id": existing_q["id"],
                    "status": existing_q.get("status")}

    # ───────────────────────────────────────────────────────────────────────
    # TIER C · unknown sender — quarantine into db.inbound_queue and return
    # early. We persist the base64 content WITHOUT writing to disk so a
    # rejected ingest leaves no storage trace. The quarantine record carries
    # enough provenance to render a review card.
    # ───────────────────────────────────────────────────────────────────────
    if tier == "unknown":
        queue_id = str(uuid.uuid4())
        primary = _pick_primary_attachment(attachments_raw)
        queue_rec = {
            "id": queue_id,
            "context_id": context["id"],
            "account_id": account["id"],
            "status": "pending_review",
            "review_reason": tier_info.get("reason") or "sender_not_recognised",
            "inbound_message_id": message_id or None,
            "inbound_from_email": from_email or None,
            "inbound_from_name": from_name or None,
            "inbound_subject": subject,
            "inbound_text_preview": (text_body or html_body or "")[:800],
            "inbound_attachment_count": len(attachments_raw),
            "inbound_attachment_summary": [
                {"name": (a.get("Name") or "")[:160],
                 "content_type": a.get("ContentType") or "",
                 "size_bytes": len((a.get("Content") or ""))}
                for a in attachments_raw[:10]
            ],
            # Raw payload lives in a separate collection keyed on queue_id
            # so inbound_queue stays light for list queries.
            "has_raw_payload": True,
            "created_at": iso(now()),
        }
        await db.inbound_queue.insert_one(queue_rec)
        # Stash the raw attachment base64 + body separately. Only consulted
        # during a review-accept promotion.
        await db.inbound_queue_raw.insert_one({
            "id": str(uuid.uuid4()),
            "queue_id": queue_id,
            "context_id": context["id"],
            "text_body": text_body,
            "html_body": html_body,
            "primary_attachment": primary,  # base64 intact
            "created_at": iso(now()),
        })
        await write_audit(
            context["id"], account["id"],
            "inbound_email.quarantined", "inbound_queue", queue_id,
            {"from": from_email, "subject": subject,
             "reason": queue_rec["review_reason"],
             "attachments": len(attachments_raw)},
        )
        logger.info(
            "Postmark inbound: QUARANTINED msg=%s from %s into ctx=%s queue=%s",
            message_id, from_email, context["id"], queue_id,
        )
        return {
            "ok": True,
            "quarantined": True,
            "queue_id": queue_id,
            "trust_tier": "unknown",
            "review_reason": queue_rec["review_reason"],
        }

    # ───────────────────────────────────────────────────────────────────────
    # TIER A / B · trusted sender (owner or known reportee) — auto-ingest.
    # ───────────────────────────────────────────────────────────────────────

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
                "inbound_email.rejected", "inbound", message_id or f"no-id-{uuid.uuid4().hex[:10]}",
                {"reason": "bad_attachment", "from": from_email, "subject": subject},
            )
            return {"ok": False, "error": "bad_attachment"}
        filename = primary_att.get("Name") or "attachment"
        try:
            scan_result = clamav_service.scan(data, filename)
        except ClamAVUnreachable as e:
            # For the Postmark webhook we must return 200 (Postmark retries
            # on non-2xx and we don't want infinite replays) but we record
            # the block in the audit ledger so an operator can find and
            # replay the payload once the scanner is back.
            logger.warning("Postmark inbound: clamd unreachable — %s", e)
            await write_audit(
                context["id"], account["id"],
                "inbound_email.rejected", "inbound", message_id or f"no-id-{uuid.uuid4().hex[:10]}",
                {"reason": "scanner_unavailable", "error": str(e)[:200],
                 "from": from_email, "subject": subject, "filename": filename},
            )
            return {"ok": False, "error": "scanner_unavailable"}
        if not scan_result.clean:
            logger.warning("Postmark inbound: rejected attachment (%s) — %s", filename, scan_result.signature)
            await write_audit(
                context["id"], account["id"],
                "inbound_email.rejected", "inbound", message_id or f"no-id-{uuid.uuid4().hex[:10]}",
                {"reason": "virus_scan", "signature": scan_result.signature,
                 "from": from_email, "subject": subject, "filename": filename,
                 "size_bytes": len(data), "scan_ms": scan_result.scan_ms},
            )
            return {"ok": False, "error": "virus_scan", "signature": scan_result.signature}
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
        # iter70 — trust tiering provenance
        "inbound_trust_tier": tier,  # 'owner' | 'reportee'
        "inbound_trust_reason": tier_info.get("reason"),
        "inbound_reportee_id": (reportee or {}).get("id") if reportee else None,
        "inbound_reportee_name": (reportee or {}).get("name") if reportee else None,
        "inbound_reportee_title": (reportee or {}).get("title") if reportee else None,
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
            "trust_tier": tier,
            "reportee_id": (reportee or {}).get("id") if reportee else None,
        },
    )

    logger.info(
        "Postmark inbound: ingested (tier=%s) message %s from %s into ctx=%s as doc=%s",
        tier, message_id, from_email, context["id"], doc_id,
    )

    return {
        "ok": True,
        "doc_id": doc_id,
        "context_id": context["id"],
        "account_id": account["id"],
        "minutes": is_minutes,
        "trust_tier": tier,
        "reportee_id": (reportee or {}).get("id") if reportee else None,
    }
