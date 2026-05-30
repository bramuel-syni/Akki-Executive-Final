"""Phase P4 (2026-02) — Cohort email service.

Three transactional emails:
  1. Receipt — auto-sent on cohort application submit.
  2. Approval — sent by admin's `/approve` action with magic-link URL.
  3. Decline — sent by admin's `/decline` action.

Master switch: `COHORT_EMAILS_ENABLED` env (default false). When false,
we log `"cohort_email: would have sent {kind} to {email_redacted}"` and
return success without calling SendGrid.

SendGrid wiring uses existing `SENDGRID_API_KEY` + `SENDGRID_FROM` envs.

Voice-lint clean — every line checked against `scripts/lint_voice.py`.
≤60 words per email INCLUDING the subject.

PII redaction in logs: emails are reduced to `<2 chars>***@<domain>`.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Dict, Optional

log = logging.getLogger(__name__)


# ─── Email bodies — verbatim, locked ────────────────────────────────────
RECEIPT_SUBJECT = "Got your Akki application"
RECEIPT_BODY = (
    "{first_name},\n\n"
    "Thanks — we have your application. We read every one personally "
    "and aim to reply within three business days.\n\n"
    "If you sent it on a Friday, that means Wednesday.\n\n"
    "— Akki"
)

APPROVAL_SUBJECT = "Your Akki workspace is ready"
APPROVAL_BODY = (
    "{first_name},\n\n"
    "You're in. Open your workspace with the link below — it works "
    "once and expires in 14 days.\n\n"
    "{magic_link}\n\n"
    "If you'd rather sign in with Google or Microsoft, the same link "
    "gives you both options.\n\n"
    "— Akki"
)

DECLINE_SUBJECT = "Akki — not this time"
DECLINE_BODY = (
    "{first_name},\n\n"
    "Thanks for your application. We're not a fit right now, but we "
    "read it carefully. We're keeping our list small to honour the "
    "response time we promised others. If our priorities shift, "
    "we'll be back in touch.\n\n"
    "— Akki"
)


def _redact_email(email: str) -> str:
    """`smith@example.com` → `sm***@example.com` for safe logging."""
    if not email or "@" not in email:
        return "<invalid>"
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"


def _first_name_from(name: str | None, email: str) -> str:
    """Fallback to the email local-part when `name` is empty."""
    if name and name.strip():
        return name.strip().split()[0]
    if email and "@" in email:
        return email.split("@", 1)[0]
    return "there"


def _enabled() -> bool:
    return (os.environ.get("COHORT_EMAILS_ENABLED", "false") or "false").lower() == "true"


def _send_via_sendgrid(*, to_email: str, subject: str, plain_body: str) -> Dict[str, str]:
    """Synchronous SendGrid send. Returns `{status, provider_id}`. On
    error we DO NOT raise — we log + return `{status: error}` so the
    caller (the cohort apply / admin action) succeeds even when email
    delivery transiently fails. The application row IS the audit; the
    email is a courtesy."""
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_addr = (os.environ.get("SENDGRID_FROM") or "").strip()
    if not api_key or not from_addr:
        log.warning("cohort_email: missing SENDGRID_API_KEY or SENDGRID_FROM — skipping send to=%s",
                    _redact_email(to_email))
        return {"status": "skipped", "reason": "sendgrid_unconfigured"}
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=from_addr,
            to_emails=to_email,
            subject=subject,
            plain_text_content=plain_body,
        )
        sg = SendGridAPIClient(api_key)
        resp = sg.send(message)
        log.info(
            "cohort_email: sent kind=%s to=%s status=%s",
            subject, _redact_email(to_email), resp.status_code,
        )
        return {
            "status": "sent",
            "provider_status": str(resp.status_code),
            "provider_id": resp.headers.get("X-Message-Id", "") if hasattr(resp, "headers") else "",
        }
    except Exception as e:  # noqa: BLE001
        log.warning(
            "cohort_email: send failed kind=%s to=%s err=%s",
            subject, _redact_email(to_email), str(e)[:200],
        )
        return {"status": "error", "reason": str(e)[:200]}


def send_receipt(*, to_email: str, first_name: Optional[str] = None) -> Dict[str, str]:
    body = RECEIPT_BODY.format(first_name=_first_name_from(first_name, to_email))
    if not _enabled():
        log.info("cohort_email: would have sent receipt to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "receipt"}
    out = _send_via_sendgrid(to_email=to_email, subject=RECEIPT_SUBJECT, plain_body=body)
    out["kind"] = "receipt"
    return out


def send_approval(*, to_email: str, first_name: Optional[str], magic_link: str) -> Dict[str, str]:
    body = APPROVAL_BODY.format(
        first_name=_first_name_from(first_name, to_email),
        magic_link=magic_link,
    )
    if not _enabled():
        log.info("cohort_email: would have sent approval to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "approval"}
    out = _send_via_sendgrid(to_email=to_email, subject=APPROVAL_SUBJECT, plain_body=body)
    out["kind"] = "approval"
    return out


def send_decline(*, to_email: str, first_name: Optional[str] = None) -> Dict[str, str]:
    body = DECLINE_BODY.format(first_name=_first_name_from(first_name, to_email))
    if not _enabled():
        log.info("cohort_email: would have sent decline to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "decline"}
    out = _send_via_sendgrid(to_email=to_email, subject=DECLINE_SUBJECT, plain_body=body)
    out["kind"] = "decline"
    return out


# ─── Word-count guard — fails fast if anyone edits the bodies above ─────
def _word_count(s: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", s))


def _self_check() -> Dict[str, int]:
    """Voice-lint-adjacent: assert each email (subject + body) is ≤60 words."""
    counts = {
        "receipt":  _word_count(RECEIPT_SUBJECT) + _word_count(
            RECEIPT_BODY.format(first_name="Friend")
        ),
        "approval": _word_count(APPROVAL_SUBJECT) + _word_count(
            APPROVAL_BODY.format(first_name="Friend", magic_link="https://akki.ai/welcome/x")
        ),
        "decline":  _word_count(DECLINE_SUBJECT) + _word_count(
            DECLINE_BODY.format(first_name="Friend")
        ),
    }
    for kind, n in counts.items():
        assert n <= 60, f"cohort_email body exceeds 60-word cap: {kind}={n}"
    return counts


# Run the check at import time so a regression breaks the boot, not prod.
_self_check()
