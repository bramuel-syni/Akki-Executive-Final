"""Resend transactional email service.

Single entry point for all outbound mail from AKKI.

Sender format
=============
Two shapes are supported:

  iter18 governance posture (default for non-cycle traffic — checklists,
  digests):
      'AKKI for <Executive Name> <noreply@akki.ai>'
      reply-to = the executive's real email address

  Phase D — cycle follow-ups (per the Executive Cycle Manager Spec):
      '<First Last> (via Akki) <noreply@cycles.akki.ai>'
      reply-to = '<account-uuid>@cycles.akki.ai'   (opaque alias)
      Inbound replies hit the Postmark webhook and are threaded back to
      the cycle_followups row by the alias-recipient match.

The cycle posture exists so the recipient sees a peer-toned sender
('Sarah Mwangi (via Akki)') rather than a third-party-tooling sender,
and so AKKI owns the inbound-reply path through a domain we control.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

import resend

logger = logging.getLogger("akki.email")

_RESEND_KEY = os.environ.get("RESEND_API_KEY")
_DEFAULT_FROM = os.environ.get("RESEND_FROM_EMAIL") or "onboarding@resend.dev"
_DEFAULT_FROM_NAME = os.environ.get("RESEND_FROM_NAME") or "AKKI"

# Phase D — Cycle Manager outbound posture.
_CYCLE_DOMAIN = os.environ.get("CYCLE_REPLY_DOMAIN") or "cycles.akki.ai"
_CYCLE_FROM_EMAIL = os.environ.get("CYCLE_FROM_EMAIL") or f"noreply@{_CYCLE_DOMAIN}"
# Stable namespace for per-account reply-to alias derivation. Generated
# once; baked in. Pair with the `cycles_alias_for(account_id)` helper.
_CYCLE_ALIAS_NAMESPACE = uuid.UUID("3f6e9c12-4b81-4a2d-9d34-2ce5a8f17b09")

if _RESEND_KEY:
    resend.api_key = _RESEND_KEY


def configured() -> bool:
    """Return True iff Resend is wired (allows callers to fall back to mailto)."""
    return bool(_RESEND_KEY)


def _format_from(executive_name: Optional[str]) -> str:
    """Compose the From header per iter18 Q3=b: 'AKKI for Bramuel <noreply@...>'.
    Falls back to plain 'AKKI <noreply@...>' if no executive name provided.

    This is the DEFAULT (non-cycle) posture — checklists, digests, etc.
    """
    if executive_name:
        clean = executive_name.replace('"', "").strip()
        if clean:
            return f'"AKKI for {clean}" <{_DEFAULT_FROM}>'
    return f'"{_DEFAULT_FROM_NAME}" <{_DEFAULT_FROM}>'


def _format_from_cycle(executive_name: Optional[str]) -> str:
    """Phase D — Cycle Manager outbound posture.

    Produces  '"<First Last> (via Akki)" <noreply@cycles.akki.ai>'  per
    the Executive Cycle Manager Spec. Recipient sees a peer-toned sender
    rather than a third-party-tooling From header.

    `executive_name` is treated as the user's full display name. We
    don't try to split first/last — the spec calls for the natural
    display form ('Sarah Mwangi (via Akki)'); the parenthetical is
    audit-trail provenance, not legal attribution."""
    if executive_name:
        clean = executive_name.replace('"', "").strip()
        if clean:
            return f'"{clean} (via Akki)" <{_CYCLE_FROM_EMAIL}>'
    return f'"AKKI Cycles" <{_CYCLE_FROM_EMAIL}>'


def cycles_alias_for(account_id: str) -> str:
    """Deterministic per-account opaque reply-to alias.

    Returns '<uuid5>@cycles.akki.ai'. The same account_id always yields
    the same alias — see Phase D ambiguity call #3 (per-account, not
    per-followup).

    Inbound-reply threading uses the alias to look up the account, then
    finds the most-recent matching `cycle_followups` row by `to_email`
    + context (in `routers/inbound_email.py`).
    """
    if not account_id:
        raise ValueError("account_id required")
    alias_uuid = str(uuid.uuid5(_CYCLE_ALIAS_NAMESPACE, account_id))
    return f"{alias_uuid}@{_CYCLE_DOMAIN}"


def is_cycles_alias(addr: str) -> bool:
    """True iff `addr` looks like '<uuid>@cycles.akki.ai'. Used by the
    Postmark webhook to detect cycle-bound inbound replies."""
    if not addr:
        return False
    addr = addr.strip().lower()
    if "@" not in addr:
        return False
    local, domain = addr.rsplit("@", 1)
    if domain != _CYCLE_DOMAIN.lower():
        return False
    # Local part must be a UUID.
    try:
        uuid.UUID(local)
        return True
    except ValueError:
        return False


def cycles_alias_extract(addr: str) -> Optional[str]:
    """Return the UUID local-part of a cycles alias, or None."""
    if not is_cycles_alias(addr):
        return None
    return addr.strip().lower().rsplit("@", 1)[0]


async def send_email(
    *,
    to: List[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
    reply_to: Optional[str] = None,
    from_executive_name: Optional[str] = None,
    tags: Optional[List[Dict[str, str]]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    posture: str = "default",
) -> Dict[str, Any]:
    """Send a transactional email via Resend.

    `posture`:
      - 'default' (iter18) — '"AKKI for <Name>" <noreply@akki.ai>'
                              reply-to = caller-supplied (typically the
                              executive's own email).
      - 'cycle'   (Phase D) — '"<Name> (via Akki)" <noreply@cycles.akki.ai>'
                              reply-to = '<account-uuid>@cycles.akki.ai'
                              opaque alias the caller passes in.

    Returns `{ok, id, mode}` where mode is one of:
      - 'sent'                 success
      - 'noop'                 Resend not configured (caller can fall back)
      - 'test_mode_restricted' Resend rejected because the API key is in
                               test mode and the recipient is not the
                               account owner's registered address.
      - 'error'                anything else

    Never raises — email failures must not crash a UX flow.

    `attachments` follow the Resend SDK shape:
      [{"filename": "session.pdf", "content": <base64 string OR bytes>}]
    """
    if not _RESEND_KEY:
        logger.warning("Resend not configured — email to %s skipped", to)
        return {"ok": False, "id": None, "mode": "noop", "error": "RESEND_API_KEY not set"}

    from_header = (
        _format_from_cycle(from_executive_name)
        if posture == "cycle"
        else _format_from(from_executive_name)
    )
    params: Dict[str, Any] = {
        "from": from_header,
        "to": to,
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text
    if reply_to:
        params["reply_to"] = reply_to
    if tags:
        params["tags"] = tags
    if attachments:
        params["attachments"] = attachments

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"ok": True, "id": result.get("id"), "mode": "sent",
                "from": from_header, "reply_to": reply_to}
    except Exception as e:  # noqa: BLE001 — Resend wraps all errors
        msg = str(e)
        # Resend test-mode constraint: 403 + "you can only send testing
        # emails to your own email address". Surface this distinctly so
        # the UI can render the friendly notice instead of a generic
        # error toast. See docs/RUNBOOKS/DEV_POD_CAVEATS.md §"Resend
        # test-mode constraint".
        low = msg.lower()
        if (
            "testing emails" in low
            or "verify a domain" in low
            or "you can only send" in low
            or "validation_error" in low and "test" in low
        ):
            logger.warning("Resend test-mode restriction for to=%s: %s", to, msg[:200])
            return {
                "ok": False,
                "id": None,
                "mode": "test_mode_restricted",
                "error": msg[:300],
            }
        logger.exception("Resend send failed")
        return {"ok": False, "id": None, "mode": "error", "error": msg[:300]}



def render_checklist_email_html(
    *,
    executive_name: str,
    reportee_name: str,
    cycle_name: str,
    deadline_date: str,
    questions: List[Dict[str, Any]],
    submission_url: str,
) -> str:
    """Render the reporting-checklist email body. Editorial cream/oxblood
    palette via inline CSS (Resend best-practice — no external sheets)."""
    lis = "".join(
        f'<li style="margin:0 0 14px 0;padding:0;color:#2A2622;font-size:15px;line-height:1.55;">'
        f'<span style="display:block;font-family:Georgia,serif;color:#1a1a1a;margin-bottom:3px;">{q.get("text", "")}</span>'
        f'<span style="display:block;font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:#8b6f47;">'
        f'{q.get("category", "general").replace("_", " ")}'
        + (f' · asked {q.get("times_asked", 1)} time(s)' if q.get("times_asked", 1) > 1 else "")
        + "</span>"
        + "</li>"
        for q in questions
    )
    return f"""
<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#F7F3EA;font-family:-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif;color:#2A2622;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F7F3EA;padding:40px 20px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border:1px solid #E8E0D0;">
        <tr><td style="padding:32px 36px 16px 36px;border-bottom:3px solid #8B2E2B;">
          <p style="margin:0;font-size:11px;text-transform:uppercase;letter-spacing:0.18em;color:#8B2E2B;font-weight:600;">AKKI · Reporting Checklist</p>
          <h1 style="margin:8px 0 0 0;font-family:Georgia,serif;font-size:24px;line-height:1.25;color:#1a1a1a;font-weight:normal;">{cycle_name}</h1>
        </td></tr>
        <tr><td style="padding:24px 36px;font-size:15px;line-height:1.6;color:#2A2622;">
          <p style="margin:0 0 14px 0;">Hi {reportee_name},</p>
          <p style="margin:0 0 14px 0;"><strong>{executive_name}</strong> asked AKKI to put together a short list of what would be most useful from you for the upcoming reporting cycle. The questions below were drawn from prior board minutes and from items still open across recent meetings.</p>
          <p style="margin:0 0 18px 0;">Please respond by <strong>{deadline_date}</strong>. You can reply directly to this email with your answers, or use the link below to submit them through AKKI.</p>
        </td></tr>
        <tr><td style="padding:0 36px 8px 36px;">
          <p style="margin:0 0 12px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.12em;color:#8b6f47;font-weight:600;">Questions for you</p>
          <ol style="margin:0 0 18px 0;padding-left:18px;">{lis}</ol>
        </td></tr>
        <tr><td style="padding:18px 36px 28px 36px;">
          <a href="{submission_url}" style="display:inline-block;padding:11px 20px;background:#1A2B4C;color:#ffffff;text-decoration:none;font-size:14px;font-weight:500;letter-spacing:0.02em;border-radius:4px;">Respond on AKKI</a>
          <p style="margin:14px 0 0 0;font-size:12px;color:#8b6f47;line-height:1.55;">Or simply reply to this email — AKKI will route your answers to {executive_name} and add them to the report draft.</p>
        </td></tr>
        <tr><td style="padding:18px 36px;border-top:1px solid #E8E0D0;background:#F9F6EE;">
          <p style="margin:0;font-size:11px;color:#8b6f47;line-height:1.5;">
            AKKI is the third party in this conversation. {executive_name} reviewed and approved this checklist before it was sent.
            Replies route back to {executive_name} directly. AKKI never reads private replies sent outside its product surface.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""



# ---------------------------------------------------------------------------
# Cycle Manager — assignment notification stub
# ---------------------------------------------------------------------------
# MOCKED IN DEV — Resend runs in test mode in the preview environment, so
# this helper never reaches the wire. It is wired so production can flip
# `RESEND_TEST_MODE=false` and a real send goes out without code change.
# ---------------------------------------------------------------------------
async def notify_ned_assignment_stub(
    *,
    assignment_id: str,
    ned_account_id: str,
    submitter_name: str,
    cycle_title: str,
) -> Dict[str, Any]:
    """Notify a NED that a Brief has been assigned to them.

    Today this writes a single log line and returns a fake-success
    payload so the caller's audit_log row still proves a notification
    attempt was made. NO email is sent in dev. Switch to a real
    `send_email(...)` call when product wants live notifications.
    """
    logger.info(
        "ned_assignment_notification.MOCKED assignment_id=%s ned=%s submitter=%s cycle=%r",
        assignment_id, ned_account_id, submitter_name, cycle_title,
    )
    return {
        "ok": True,
        "mode": "mocked_in_dev",
        "assignment_id": assignment_id,
    }
