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
import hashlib
import hmac as _hmac
import logging
import os
import secrets
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

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

# Phase B (2026-05-21) — back-compat endpoint at `/api/webhooks/postmark/inbound`.
# Operators can re-point the Postmark dashboard from
# `/api/inbound/postmark` to this URL with no behavioural change.
# Both routes resolve to the same `receive_postmark_inbound` handler.
backcompat_router = APIRouter(prefix="/api", tags=["inbound"])


# ---------------------------------------------------------------------------
# Inbound webhook auth — three accepted modes, default HMAC.
#
# Phase G2 (2026-05-11) — the URL `?secret=` mode is a legacy/dev
# fallback only. Production accepts EITHER:
#   1. HMAC-SHA256 of the raw request body in header `X-Postmark-Signature`
#      (or alias `Postmark-Signature`), keyed by POSTMARK_WEBHOOK_SECRET.
#      This is what we want once a signing proxy (or future Postmark
#      feature) sits in front of the webhook.
#   2. HTTP Basic-Auth in `Authorization: Basic …` — Postmark's
#      native inbound auth option (https://postmarkapp.com/developer/
#      webhooks/webhooks-overview#basic-authentication). The password
#      MUST equal POSTMARK_WEBHOOK_SECRET; the username is ignored.
# The URL-secret legacy path is enabled ONLY when:
#   POSTMARK_USE_HMAC=false  AND  AKKI_ENV != "production"
# A boot guard in server.py enforces "AKKI_ENV=production implies
# POSTMARK_USE_HMAC!=false" — see `_verify_inbound_boot_guard`.
# ---------------------------------------------------------------------------
POSTMARK_USE_HMAC_DEFAULT = "true"


def _expected_secret() -> str:
    return (
        os.environ.get("POSTMARK_WEBHOOK_SECRET")
        or os.environ.get("POSTMARK_SERVER_TOKEN")
        or ""
    ).strip()


def _hmac_mode_enabled() -> bool:
    return (
        os.environ.get("POSTMARK_USE_HMAC", POSTMARK_USE_HMAC_DEFAULT)
        .strip().lower()
        in ("true", "1", "yes")
    )


def _is_production() -> bool:
    return (os.environ.get("AKKI_ENV") or "").strip().lower() == "production"


def _verify_inbound_boot_guard() -> None:
    """Called at app startup. Refuses boot if production env is
    accepting URL-secret fallback."""
    if _is_production() and not _hmac_mode_enabled():
        raise RuntimeError(
            "AKKI_ENV=production but POSTMARK_USE_HMAC is disabled. "
            "Refusing to boot — HMAC/Basic auth is mandatory in prod."
        )


def _verify_hmac(raw_body: bytes, sig_header: Optional[str]) -> bool:
    secret = _expected_secret()
    if not (secret and sig_header):
        return False
    expected = _hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256,
    ).hexdigest()
    # Accept either hex digest (most common) or base64 — some signing
    # proxies emit base64 instead of hex. Constant-time compare both.
    provided = sig_header.strip().lower()
    if provided.startswith("sha256="):
        provided = provided[7:]
    if secrets.compare_digest(provided, expected):
        return True
    # base64 variant
    expected_b64 = base64.b64encode(
        _hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
    ).decode("ascii").strip()
    if secrets.compare_digest(sig_header.strip(), expected_b64):
        return True
    return False


def _verify_basic_auth(authz_header: Optional[str]) -> bool:
    """Verify Postmark Basic-Auth.

    Phase B (2026-05-21) — optionally validates the username too via
    `POSTMARK_BASIC_AUTH_USER`. When that env is unset, the server
    accepts any username with a matching password (the historical
    behaviour). When it is set, BOTH must match.

    The password is always validated against `POSTMARK_WEBHOOK_SECRET`
    (a 64-char hex value, see `.env`). One secret across HMAC + Basic-
    Auth keeps the operator-facing config surface minimal.
    """
    secret = _expected_secret()
    if not (secret and authz_header):
        return False
    if not authz_header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(authz_header[6:].strip()).decode("utf-8")
    except Exception:  # noqa: BLE001
        return False
    if ":" not in decoded:
        return False
    user, _, pw = decoded.partition(":")
    expected_user = os.environ.get("POSTMARK_BASIC_AUTH_USER", "").strip()
    if expected_user and not secrets.compare_digest(user, expected_user):
        return False
    return secrets.compare_digest(pw, secret)


def _verify_url_secret(provided: Optional[str]) -> bool:
    secret = _expected_secret()
    if not (secret and provided):
        return False
    return secrets.compare_digest(provided.strip(), secret)


async def _verify_inbound(request: Request, url_secret: Optional[str]) -> bytes:
    """Verify the inbound POST and return the raw request body so the
    caller can parse it as JSON without re-reading the stream."""
    secret = _expected_secret()
    if not secret:
        raise HTTPException(status_code=503, detail="Inbound mail not configured.")
    raw = await request.body()
    sig = (
        request.headers.get("x-postmark-signature")
        or request.headers.get("postmark-signature")
        or request.headers.get("x-webhook-signature")
    )
    if _verify_hmac(raw, sig):
        return raw
    if _verify_basic_auth(request.headers.get("authorization")):
        return raw
    # Legacy URL-secret — only when explicitly disabled HMAC AND not prod.
    if (not _hmac_mode_enabled()) and (not _is_production()):
        if _verify_url_secret(url_secret):
            logger.warning(
                "inbound auth via URL-secret legacy path (not prod). "
                "Set POSTMARK_USE_HMAC=true and switch to HMAC/Basic."
            )
            return raw
    raise HTTPException(status_code=401, detail="Invalid inbound credentials.")


# Kept for any third-party callers that may still import this name.
def _verify_secret(provided: Optional[str]) -> None:  # noqa: D401 — legacy
    """Deprecated — use `_verify_inbound(request, secret)` instead.
    Retained as a stub for back-compat; raises 401 if the URL secret
    does not match. Will be removed once all callers migrate."""
    if not _verify_url_secret(provided):
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
    """Resolve a Postmark MailboxHash into the routing target.

    Phase B (2026-05-21) extends the historical `<account_token>` /
    `<account_token>.<context_token>` taxonomy with three optional
    prefix verbs that produce deep-link routing:

      session-<sid>.<account_token>[.<ctx>]   → attach to Solva /
                                                Cycle session `sid`
      doc-<docid>.<account_token>[.<ctx>]    → attach as a new
                                                version of document `docid`
      notify.<account_token>[.<ctx>]         → fire notification only;
                                                do NOT persist a document
      <account_token>[.<context_token>]      → existing taxonomy
                                                (unchanged)

    The prefix is detected by leading-token shape and stripped before
    the existing `account_token` / `context_token` resolution runs.
    Resolution failures on a prefixed target collapse to the plain
    routing path (e.g. an unknown `session-<id>` lands as if no prefix
    was set, with the routing intent surfaced in the return dict for
    the caller to dispatch on).

    Returns:
      {
        "account":  <account doc>,
        "context":  <context doc>,
        "route":    "session" | "doc" | "notify" | "default",
        "target_id": <sid|docid|None>,
        "route_note": <str|None>,   # explains a fallback if one occurred
      }
    """
    raw = (mailbox_hash or "").strip().lower()
    if not raw:
        raise HTTPException(status_code=400, detail="Missing MailboxHash.")
    parts = raw.split(".")

    route = "default"
    target_id: Optional[str] = None
    route_note: Optional[str] = None

    # Detect prefix verb (Phase B). The verb must be a clean leading
    # token. Anything ambiguous falls through to the default path.
    if parts and parts[0].startswith("session-") and len(parts) >= 2:
        route = "session"
        target_id = parts[0][len("session-"):]
        parts = parts[1:]  # strip the verb
    elif parts and parts[0].startswith("doc-") and len(parts) >= 2:
        route = "doc"
        target_id = parts[0][len("doc-"):]
        parts = parts[1:]
    elif parts and parts[0] == "notify" and len(parts) >= 2:
        route = "notify"
        parts = parts[1:]

    if not parts:
        raise HTTPException(status_code=400, detail="MailboxHash missing account token.")
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

    # If a prefix verb was set but the target doesn't resolve within
    # this account's data, demote to default routing with a note so the
    # caller can audit/notify. The actual target-row check happens in
    # the dispatcher; here we just surface a route-note for "session"
    # and "doc" routes when target_id is empty/malformed.
    if route in {"session", "doc"} and not target_id:
        route_note = f"{route}-prefix-missing-target-id"
        route = "default"

    return {
        "account": account,
        "context": context,
        "route": route,
        "target_id": target_id,
        "route_note": route_note,
    }


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




# ─────────────────────────────────────────────────────────────────────
# Phase F.5 (2026-05-26) — Task contributor email-reply handler
# ─────────────────────────────────────────────────────────────────────
def _strip_email_signature(body: str) -> str:
    """Heuristic — best effort. Strips quoted history (>) lines, common
    sig delimiters (-- and __ followed by newlines), and "On … wrote:"
    forwards. Anchored to the END of the body so the contribution
    content survives."""
    if not body:
        return ""
    import re
    lines = body.split("\n")
    # Drop trailing block after "On <date> <name> wrote:" forwards.
    cut = None
    for i, ln in enumerate(lines):
        if re.match(r"^On\s+.+?\s+wrote:\s*$", ln.strip()):
            cut = i
            break
    if cut is not None:
        lines = lines[:cut]
    # Drop trailing signature delimited by "-- " or "__".
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s == "--" or s == "-- " or s.startswith("__"):
            lines = lines[:i]
            break
    # Drop quoted-history lines (start with >).
    lines = [ln for ln in lines if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()


async def _handle_task_contributor_reply(
    *, payload: Dict[str, Any], token_hash: str,
    from_email: str, from_name: str, subject: str,
    text_body: str, html_body: str, message_id: str,
    attachments_raw: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Phase F.5 — contributor replied to a task-<token>@... address.
    Token alone identifies the task + contributor. Validates the
    sender's email matches the token's contributor_email."""
    import base64
    from datetime import datetime, timezone
    from core import db
    row = await db.task_contributor_tokens.find_one(
        {"token": token_hash, "used": False}, {"_id": 0},
    )
    if not row:
        # Log to inbound stream and quietly drop.
        try:
            await db.task_inbound_emails.insert_one({
                "id":             str(uuid.uuid4()),
                "token":          token_hash[:24] + "…",
                "from":           from_email,
                "subject":        subject,
                "parse_status":   "token_unknown_or_expired",
                "received_at":    datetime.now(timezone.utc).isoformat(),
                "message_id":     message_id,
                "provider":       payload.get("_provider", "postmark"),
            })
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "error": "token_unknown_or_expired"}

    # Sender authority check — From: must match the token's contributor.
    if from_email != (row.get("contributor_email") or "").lower():
        try:
            await db.task_inbound_emails.insert_one({
                "id":             str(uuid.uuid4()),
                "task_id":        row["task_id"],
                "from":           from_email,
                "subject":        subject,
                "parse_status":   "sender_mismatch",
                "expected_email": row.get("contributor_email"),
                "received_at":    datetime.now(timezone.utc).isoformat(),
                "message_id":     message_id,
                "provider":       payload.get("_provider", "postmark"),
            })
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "error": "sender_mismatch"}

    # Body — prefer plain text, strip signatures.
    cleaned_body = _strip_email_signature(text_body or html_body or "")

    # Attachments → docs.
    created_doc_ids: List[str] = []
    for att in attachments_raw[:10]:
        try:
            name = (att.get("Name") or att.get("name") or "attachment").strip()
            content_type = att.get("ContentType") or att.get("content_type") or "application/octet-stream"
            b64 = att.get("Content") or att.get("content") or ""
            raw_bytes = base64.b64decode(b64) if b64 else b""
            if not raw_bytes:
                continue
            did = f"doc-{uuid.uuid4().hex[:10]}"
            await db.documents.insert_one({
                "id":                did,
                "task_id":           row["task_id"],
                "account_id":        row["task_account_id"],
                "contributor_email": row["contributor_email"],
                "contributor_id":    row.get("contributor_id"),
                "contributor_token": token_hash,
                "name":              name,
                "original_filename": name,
                "mime_type":         content_type,
                "size_bytes":        len(raw_bytes),
                "state":             "draft",
                "origin":            "email_receipt",
                "status":            "ready",
                "source": {
                    "sender":       from_email,
                    "subject":      subject,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "message_id":   message_id,
                },
                "extracted_text":    raw_bytes.decode("utf-8", errors="replace") if (content_type or "").startswith("text/") else "",
                "created_at":        datetime.now(timezone.utc).isoformat(),
            })
            created_doc_ids.append(did)
        except Exception as e:  # noqa: BLE001
            logger.warning("attachment ingest failed: %s", e)

    # Add the cleaned body as a contributor comment on the task.
    if cleaned_body:
        try:
            await db.tasks.update_one(
                {"id": row["task_id"]},
                {"$push": {"contributor_comments": {
                    "id":         str(uuid.uuid4()),
                    "reviewer":   row["contributor_email"],
                    "comment":    cleaned_body[:4000],
                    "kind":       "email_body",
                    "subject":    subject,
                    "doc_ids":    created_doc_ids,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }}},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("contributor_comments push failed: %s", e)

    # Flip status to "submitted" + recompute readiness.
    t = await db.tasks.find_one({"id": row["task_id"]}, {"_id": 0})
    if t:
        team = list(t.get("team") or [])
        target = row["contributor_email"]
        idx = next(
            (i for i, m in enumerate(team) if (m.get("email") or "").lower() == target),
            None,
        )
        if idx is not None and team[idx].get("status") not in ("approved",):
            team[idx] = {**team[idx], "status": "submitted"}
            try:
                from services.tasks.intelligence_service import readiness_breakdown
                rb = readiness_breakdown({**t, "team": team})
                await db.tasks.update_one(
                    {"id": row["task_id"]},
                    {"$set": {"team": team,
                              "readiness_score": rb["score"],
                              "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("post-email readiness update failed: %s", e)

    # Audit + inbound log.
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "account_id":    row["task_account_id"],
            "action":        "task.contribution.submitted_via_email",
            "resource_type": "task",
            "resource_id":   row["task_id"],
            "metadata": {
                "contributor_email": from_email,
                "subject":           subject,
                "n_attachments":     len(created_doc_ids),
                "doc_ids":           created_doc_ids,
                "message_id":        message_id,
            },
            "created_at":    datetime.now(timezone.utc).isoformat(),
        })
        await db.task_inbound_emails.insert_one({
            "id":             str(uuid.uuid4()),
            "task_id":        row["task_id"],
            "from":           from_email,
            "subject":        subject,
            "parse_status":   "ingested",
            "doc_ids":        created_doc_ids,
            "comment_len":    len(cleaned_body),
            "received_at":    datetime.now(timezone.utc).isoformat(),
            "message_id":     message_id,
            "provider":       payload.get("_provider", "postmark"),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning("post-email audit failed: %s", e)

    # Best-effort confirmation reply (queued; failure non-fatal).
    try:
        from email_service import send_email
        await send_email(
            to=from_email,
            subject=f"Got it — we received your contribution to {(t or {}).get('name', 'the task')}",
            text=f"Thanks {from_name or ''}. We received your reply and {len(created_doc_ids)} attachment(s). The task owner has been notified.\n",
            html=f"<p>Thanks {from_name or ''}. We received your reply and {len(created_doc_ids)} attachment(s). The task owner has been notified.</p>",
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        "ok":             True,
        "task_id":        row["task_id"],
        "doc_ids":        created_doc_ids,
        "comment_len":    len(cleaned_body),
    }


@router.post("/postmark")
async def receive_postmark_inbound(request: Request, secret: Optional[str] = Query(None)):
    """DEPRECATED (2026-05-26) — Postmark inbound has been replaced by
    SendGrid Inbound Parse. This route returns 410 Gone with a migration
    note. Re-point the inbound webhook in your provider dashboard to
    `/api/inbound/sendgrid` (multipart/form-data, optional HTTP Basic
    Auth). Will be removed in the next release cycle.
    """
    return JSONResponse(
        status_code=410,
        content={
            "ok": False,
            "error": "endpoint_retired",
            "migration": {
                "from": "/api/inbound/postmark (Postmark JSON)",
                "to":   "/api/inbound/sendgrid (SendGrid Inbound Parse multipart/form-data)",
                "since": "2026-05-26",
                "docs":  "/app/memory/sprints/DEPLOY_READINESS.md#sendgrid-setup",
            },
            "note": (
                "Postmark inbound webhook is retired. Configure SendGrid "
                "Inbound Parse and point the parse URL at the new endpoint."
            ),
        },
    )


async def _dispatch_inbound_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Provider-agnostic inbound dispatch.

    Accepts a Postmark-shape dict (the historic internal contract).
    The SendGrid endpoint normalizes its multipart payload into this
    shape before calling this worker. Returns the same response shape
    the legacy Postmark handler returned.
    """
    # Phase P5.8.2 (2026-02) — admin inbox capture. Runs BEFORE the
    # provider-specific routing so every inbound is visible in the
    # admin surface regardless of how dispatch handles it (task,
    # quarantine, drop, error). Errors are swallowed in the helper —
    # capture must never block dispatch.
    try:
        from routers.admin_inbox import capture_for_admin_inbox
        admin_inbox_id = await capture_for_admin_inbox(
            payload, routing_result="pending",
        )
    except Exception:  # noqa: BLE001
        admin_inbox_id = ""

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

    # Phase F.5 (2026-05-26) — task contributor email-reply branch.
    # The MailboxHash for these is `task-<32-byte-url-safe-token>`. The
    # token alone is the credential; sender authority comes from
    # matching token.contributor_email vs the From: header. No
    # account_token suffix required (the contributor doesn't have an
    # Akki account).
    if mailbox_hash.startswith("task-"):
        return await _handle_task_contributor_reply(
            payload=payload,
            token_hash=mailbox_hash[len("task-"):],
            from_email=from_email, from_name=from_name,
            subject=subject, text_body=text_body, html_body=html_body,
            message_id=message_id, attachments_raw=attachments_raw,
        )

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
    route = resolved.get("route", "default")
    target_id = resolved.get("target_id")
    route_note = resolved.get("route_note")

    # iter70 — classify the sender tier. Unknown senders get quarantined
    # into db.inbound_queue for the owner to review; known senders
    # (owner or reportee) continue to the live ingest path as before.
    tier_info = await _classify_sender_tier(from_email, account, context)
    tier = tier_info["tier"]
    reportee = tier_info.get("reportee")

    # Phase B (2026-05-21) — prefix-verb routing for trusted senders.
    # `session-<sid>` and `doc-<docid>` attach the inbound payload to
    # an existing target row; `notify` fires an audit + return without
    # persisting a document. Unknown senders still flow through the
    # quarantine path below regardless of prefix (privacy invariant).
    if route == "notify" and tier != "unknown":
        await write_audit(
            context["id"], account["id"],
            "inbound_email.notify", "notify", message_id or f"notify-{uuid.uuid4().hex[:10]}",
            {"from": from_email, "subject": subject,
             "attachments": len(attachments_raw)},
        )
        return {"ok": True, "route": "notify", "trust_tier": tier,
                "message_id": message_id or None}

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
            scan_result = await clamav_service.scan(data, filename, file_id=message_id, user_id=account["id"])
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

    # Phase B (2026-05-21) — prefix-verb routing for session-attach and
    # doc-version-attach. The document is always persisted (a forensic
    # record + a single content-of-record); the prefix verb adds the
    # attachment relationship + (for doc-version) the `related_doc_id`
    # link. Unresolved targets fall back to the default ingest path and
    # carry an `inbound_route_note` flag so the operator can replay.
    route_attached_to_session_id: Optional[str] = None
    route_attached_to_doc_id: Optional[str] = None
    route_attach_note: Optional[str] = route_note
    if route == "session" and target_id:
        sess = await db.solva_phase_d_sessions.find_one(
            {"id": target_id, "context_id": context["id"]},
            {"_id": 0, "id": 1},
        )
        if sess:
            route_attached_to_session_id = target_id
        else:
            route_attach_note = "session-target-not-found-in-context"
    elif route == "doc" and target_id:
        parent = await db.documents.find_one(
            {"id": target_id, "context_id": context["id"]},
            {"_id": 0, "id": 1},
        )
        if parent:
            route_attached_to_doc_id = target_id
        else:
            route_attach_note = "doc-target-not-found-in-context"

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
        # Phase B (2026-05-21) — prefix-route attachment provenance
        "inbound_route": route,                 # 'default' | 'session' | 'doc' | 'notify'
        "inbound_route_target_id": target_id,
        "inbound_route_attached_session_id": route_attached_to_session_id,
        "inbound_route_attached_doc_id": route_attached_to_doc_id,
        "inbound_route_note": route_attach_note,
        # If the prefix verb was `doc-<id>` and the target resolved, set
        # `related_doc_id` so the document journal renders this row as
        # a new version of the parent. Default ingest leaves both None.
        "related_doc_id": route_attached_to_doc_id,
        "relation_type": "inbound_version" if route_attached_to_doc_id else None,
    }
    await db.documents.insert_one(doc)

    # Phase B — if attached to a Solva session, write an attachment row
    # so the session view can list inbound docs without scanning the
    # whole documents collection.
    if route_attached_to_session_id:
        await db.solva_session_attachments.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": route_attached_to_session_id,
            "context_id": context["id"],
            "doc_id": doc_id,
            "source": "inbound_email",
            "from_email": from_email or None,
            "subject": subject,
            "created_at": created_at,
        })

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
            "route": route,
            "route_target_id": target_id,
            "route_note": route_attach_note,
        },
    )

    logger.info(
        "Postmark inbound: ingested (tier=%s route=%s) message %s from %s into ctx=%s as doc=%s",
        tier, route, message_id, from_email, context["id"], doc_id,
    )

    return {
        "ok": True,
        "doc_id": doc_id,
        "context_id": context["id"],
        "account_id": account["id"],
        "minutes": is_minutes,
        "trust_tier": tier,
        "reportee_id": (reportee or {}).get("id") if reportee else None,
        "route": route,
        "route_target_id": target_id,
        "route_note": route_attach_note,
        "attached_session_id": route_attached_to_session_id,
        "attached_doc_id": route_attached_to_doc_id,
    }



# ─────────────────────────────────────────────────────────────────────
# Phase B (2026-05-21) — back-compat endpoint (now also 410).
# Wires `/api/webhooks/postmark/inbound` to a 410 response. Both
# Postmark routes are retired in favour of SendGrid Inbound Parse.
# ─────────────────────────────────────────────────────────────────────
@backcompat_router.post("/webhooks/postmark/inbound", include_in_schema=False)
async def receive_postmark_inbound_backcompat(
    request: Request,
    secret: Optional[str] = Query(None),
):
    return await receive_postmark_inbound(request, secret=secret)


# ═════════════════════════════════════════════════════════════════════
# SendGrid Inbound Parse — 2026-05-26 — replaces Postmark inbound.
#
# SendGrid posts multipart/form-data (NOT JSON). Fields:
#   to / from / subject / text / html      string
#   attachments                              integer count (string)
#   attachment-info                          JSON metadata
#   email                                    raw MIME source
#   dkim / SPF / envelope                    strings
#   attachment1, attachment2, …              multipart file parts
#
# Reply-to address shape:
#   task-<token>@inbound.<SENDGRID_INBOUND_DOMAIN>
#   <account-uuid>@cycles.akki.ai            (cycle alias, unchanged)
#   inbound+<account_token>[.<ctx_token>]@inbound.<SENDGRID_INBOUND_DOMAIN>
#
# Auth: optional HTTP Basic Auth (SendGrid Inbound Parse settings).
# Env vars:
#   SENDGRID_INBOUND_AUTH_USERNAME (optional)
#   SENDGRID_INBOUND_AUTH_PASSWORD (optional)
# When both are unset, the endpoint accepts unauthenticated POSTs (DEV).
# When set, the endpoint requires Basic Auth matching them.
# ═════════════════════════════════════════════════════════════════════


def _verify_sendgrid_basic_auth(authz_header: Optional[str]) -> bool:
    """Verify SendGrid Inbound Parse HTTP Basic Auth.

    If `SENDGRID_INBOUND_AUTH_USERNAME` AND `SENDGRID_INBOUND_AUTH_PASSWORD`
    are BOTH set, the request must include matching Basic auth.
    Otherwise auth is OPTIONAL (the parse URL is the credential).
    """
    expected_user = (os.environ.get("SENDGRID_INBOUND_AUTH_USERNAME") or "").strip()
    expected_pw   = (os.environ.get("SENDGRID_INBOUND_AUTH_PASSWORD") or "").strip()
    if not (expected_user and expected_pw):
        return True  # auth not configured → accept (URL secrecy is the credential)
    if not authz_header or not authz_header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(authz_header[6:].strip()).decode("utf-8")
    except Exception:  # noqa: BLE001
        return False
    if ":" not in decoded:
        return False
    user, _, pw = decoded.partition(":")
    return (
        secrets.compare_digest(user, expected_user)
        and secrets.compare_digest(pw, expected_pw)
    )


def _extract_email_addr(raw: str) -> str:
    """Extract the bare `name@domain` from a `"Name" <name@domain>` header
    or pass through a bare address. Lower-cased."""
    if not raw:
        return ""
    s = raw.strip()
    if "<" in s and ">" in s:
        s = s[s.rindex("<") + 1 : s.rindex(">")]
    return s.strip().lower()


def _mailbox_hash_from_local_part(addr: str) -> str:
    """Extract the MailboxHash equivalent from a SendGrid `to` address.

    SendGrid does NOT support Postmark-style `+plus-addressing`. Instead
    the entire local-part (everything before `@`) IS the routing token.
    For our prefix-based routing (`task-<token>`, `inbound+...`, etc.)
    we return the local-part as the MailboxHash so the existing dispatch
    logic works unchanged.

    Cycle aliases (`<uuid>@cycles.akki.ai`) are detected separately by
    `is_cycles_alias` against the full address — we do NOT set a hash
    for those.
    """
    bare = _extract_email_addr(addr)
    if not bare or "@" not in bare:
        return ""
    local, _, _ = bare.partition("@")
    return local


def _parse_attachment_info(raw_json: str) -> Dict[str, Dict[str, Any]]:
    """SendGrid's `attachment-info` field is a JSON map keyed by the
    multipart part name (e.g. `attachment1`) with values describing
    each file (filename, type, charset). Returns `{}` on parse failure."""
    if not raw_json:
        return {}
    try:
        import json as _json
        data = _json.loads(raw_json)
        if isinstance(data, dict):
            return data
    except Exception:  # noqa: BLE001
        pass
    return {}


async def _sendgrid_form_to_payload(form) -> Dict[str, Any]:
    """Adapt a SendGrid Inbound Parse multipart form into the Postmark-
    shape dict the internal dispatcher consumes.

    `form` is a `starlette.datastructures.FormData` instance.
    """
    to_raw   = (form.get("to") or "").strip()
    from_raw = (form.get("from") or "").strip()
    subject  = (form.get("subject") or "").strip()
    text     = form.get("text") or ""
    html     = form.get("html") or ""

    # MailboxHash = local-part of the To address (e.g., `task-<token>` or
    # `inbound+<acct>.<ctx>`). The legacy Postmark code already handles
    # both shapes.
    mailbox_hash = _mailbox_hash_from_local_part(to_raw)

    # Bare email of the From address.
    from_email = _extract_email_addr(from_raw)
    # FromName: the bit before `<…>` if any.
    from_name = ""
    if "<" in from_raw:
        from_name = from_raw[: from_raw.rindex("<")].strip().strip('"')

    # Attachments. SendGrid posts each as a multipart file under
    # `attachment1`, `attachment2`, …. `attachment-info` carries metadata.
    attachments: List[Dict[str, Any]] = []
    info = _parse_attachment_info(form.get("attachment-info") or "")
    try:
        count = int((form.get("attachments") or "0").strip() or "0")
    except (ValueError, TypeError):
        count = 0
    for i in range(1, count + 1):
        key = f"attachment{i}"
        f = form.get(key)
        if f is None:
            continue
        # `f` is a starlette `UploadFile` for files.
        try:
            content_bytes = await f.read()
        except Exception:  # noqa: BLE001
            continue
        meta = info.get(key) or {}
        attachments.append({
            "Name":         meta.get("filename") or getattr(f, "filename", None) or key,
            "ContentType":  meta.get("type")     or getattr(f, "content_type", None) or "application/octet-stream",
            "Content":      base64.b64encode(content_bytes).decode("ascii"),
            "ContentLength": len(content_bytes),
        })

    # Cycle-alias detection: SendGrid doesn't carry an `OriginalRecipient`
    # header in the form payload, but the cycle alias IS the `to`. Pass
    # the full to-address through `OriginalRecipient` so the cycle-alias
    # path in `_dispatch_inbound_payload` resolves it.
    original_recipient = _extract_email_addr(to_raw)
    to_full = [{"Email": original_recipient, "MailboxHash": mailbox_hash}]

    return {
        # `From` is the BARE email (lowercased) — matches Postmark's
        # field semantics. The display-name lives in `FromName`/`FromFull`.
        "From":               from_email,
        "FromFull":           {"Email": from_email, "Name": from_name},
        "FromName":           from_name,
        "To":                 to_raw,
        "ToFull":             to_full,
        "Subject":            subject,
        "TextBody":           text,
        "HtmlBody":           html,
        "MailboxHash":        mailbox_hash,
        "MessageID":          (form.get("MessageID") or form.get("message-id") or "").strip(),
        "Attachments":        attachments,
        "OriginalRecipient":  original_recipient,
        # Provenance — forensics row records this for future-proofing.
        "_provider":          "sendgrid",
    }


@router.post("/sendgrid")
async def receive_sendgrid_inbound(request: Request):
    """SendGrid Inbound Parse webhook receiver.

    Reads multipart/form-data, normalizes to the internal Postmark-shape
    payload, and dispatches via `_dispatch_inbound_payload`.

    Phase P5.8.1 (2026-02) — gated behind `INBOUND_PROVIDER`. Default
    is `sendgrid` (sole accepting provider); `postmark` re-routes
    inbound to the legacy endpoint (which itself returns 410 unless
    its own retired-flag is lifted); `both` accepts here AND on the
    legacy endpoint for transition windows.
    """
    provider_flag = (os.environ.get("INBOUND_PROVIDER") or "sendgrid").strip().lower()
    if provider_flag not in ("sendgrid", "both"):
        raise HTTPException(status_code=410, detail={
            "error": "inbound_provider_disabled",
            "message": (
                f"INBOUND_PROVIDER={provider_flag!r} — SendGrid Inbound "
                f"Parse is not the configured provider. Set "
                f"INBOUND_PROVIDER=sendgrid (or both) to re-enable."
            ),
        })

    if not _verify_sendgrid_basic_auth(request.headers.get("authorization")):
        raise HTTPException(status_code=401, detail="Invalid inbound credentials.")

    try:
        form = await request.form()
    except Exception as e:  # noqa: BLE001
        logger.warning("SendGrid inbound: failed to parse multipart: %s", e)
        # 200 so SendGrid doesn't infinite-retry; log for ops.
        return {"ok": False, "error": "invalid_multipart"}

    try:
        payload = await _sendgrid_form_to_payload(form)
    except Exception as e:  # noqa: BLE001
        logger.exception("SendGrid inbound: payload adapter error: %s", e)
        return {"ok": False, "error": "adapter_error"}

    return await _dispatch_inbound_payload(payload)
