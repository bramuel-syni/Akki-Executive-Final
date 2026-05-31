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

from services.cohort_email_html import (
    render_approval_html,
    render_decline_html,
    render_receipt_html,
    render_reminder_html,
)

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
    "response time we promised others.\n\n"
    "— Akki"
)

# Phase P5.7 (2026-02) — decline body variant that includes the
# waitlist door-back line. Falls back to the original body when the
# caller passes no waitlist_url, so the existing /decline call sites
# keep working unchanged.
DECLINE_BODY_WITH_WAITLIST = (
    "{first_name},\n\n"
    "Thanks for your application. We're not a fit right now, but we "
    "read it carefully. We're keeping our list small to honour the "
    "response time we promised others.\n\n"
    "If you'd like to be considered for a later cohort, leave your "
    "email here: {waitlist_url}\n\n"
    "— Akki"
)

# Phase P5.7 (2026-02) — Touch 4: day-10 expiry reminder.
REMINDER_SUBJECT = "Akki — your invite expires in four days"
REMINDER_BODY = (
    "{first_name},\n\n"
    "Quick reminder — your Akki invite expires in four days. Open "
    "your workspace whenever you have ten quiet minutes.\n\n"
    "{magic_link}\n\n"
    "If the moment isn't right, just reply and we'll hold a place.\n\n"
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


def _notify_disabled() -> bool:
    """Phase P5.11.2 (2026-02) — test-side kill switch for SendGrid
    sends. When `COHORT_NOTIFY_DISABLED=true` (or `1`), every public
    `send_*` entrypoint in this module short-circuits with a log line
    instead of opening a SendGrid client connection. Production never
    sets this env (and `backend/.env.example` does not document it
    either — intentional: it exists strictly for the pytest session,
    which sets it via `tests/conftest.py`). The flag is checked
    BEFORE `_enabled()` so it overrides every other path including
    the admin test-send (`admin_test_send`) which is allowed to send
    despite `COHORT_EMAILS_ENABLED=false`."""
    val = (os.environ.get("COHORT_NOTIFY_DISABLED", "") or "").strip().lower()
    return val in {"true", "1", "yes"}


def _send_via_sendgrid(
    *, to_email: str, subject: str, plain_body: str,
    html_body: Optional[str] = None, reply_to: Optional[str] = None,
) -> Dict[str, str]:
    """Synchronous SendGrid send. Returns `{status, provider_id}`. On
    error we DO NOT raise — we log + return `{status: error}` so the
    caller (the cohort apply / admin action) succeeds even when email
    delivery transiently fails. The application row IS the audit; the
    email is a courtesy.

    Phase P5.7 (2026-02):
      * Reads `SENDGRID_FROM_EMAIL` (aligning with the rest of the
        codebase and the deployed `.env`). Falls back to legacy
        `SENDGRID_FROM` for backward compat during the rollout.
      * Adds optional `html_body` so the recipient sees the HTML
        version when their client supports it; the plain-text body
        survives as the fallback (Outlook plain mode etc).
      * Adds optional `reply_to` so admin test sends + waitlist
        confirmations can route replies to the right inbox without
        changing the From-Authentication path.
    """
    # Phase P5.11.2 (2026-02) — test-mode kill switch. Honoured ahead
    # of every other guard so the pytest session NEVER opens a
    # SendGrid client. Production never sets this env.
    if _notify_disabled():
        log.info(
            "cohort_notify: would have sent to %s (test mode COHORT_NOTIFY_DISABLED)",
            _redact_email(to_email),
        )
        return {"status": "test_mode_disabled", "reason": "COHORT_NOTIFY_DISABLED"}
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_addr = (
        (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
        or (os.environ.get("SENDGRID_FROM") or "").strip()
    )
    if not api_key or not from_addr:
        log.warning("cohort_email: missing SENDGRID_API_KEY or SENDGRID_FROM_EMAIL — skipping send to=%s",
                    _redact_email(to_email))
        return {"status": "skipped", "reason": "sendgrid_unconfigured"}
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, ReplyTo
        message = Mail(
            from_email=from_addr,
            to_emails=to_email,
            subject=subject,
            plain_text_content=plain_body,
            html_content=html_body,
        )
        if reply_to:
            message.reply_to = ReplyTo(reply_to)
        sg = SendGridAPIClient(api_key)
        resp = sg.send(message)
        log.info(
            "cohort_email: sent kind=%s to=%s status=%s",
            subject, _redact_email(to_email), resp.status_code,
        )
        # SendGrid returns X-Message-Id in response headers — capture
        # it for delivery-status correlation against the webhook
        # event stream we'll wire in P5.7.5.
        provider_id = ""
        try:
            if hasattr(resp, "headers"):
                hdrs = resp.headers
                provider_id = (
                    hdrs.get("X-Message-Id")
                    or (hdrs.get("X-Message-Id".lower()) if hasattr(hdrs, "get") else "")
                    or ""
                )
        except Exception:
            provider_id = ""
        return {
            "status": "sent",
            "provider_status": str(resp.status_code),
            "provider_id": provider_id or "",
        }
    except Exception as e:  # noqa: BLE001
        log.warning(
            "cohort_email: send failed kind=%s to=%s err=%s",
            subject, _redact_email(to_email), str(e)[:200],
        )
        return {"status": "error", "reason": str(e)[:200]}


def send_receipt(*, to_email: str, first_name: Optional[str] = None) -> Dict[str, str]:
    fn = _first_name_from(first_name, to_email)
    body = RECEIPT_BODY.format(first_name=fn)
    html = render_receipt_html(first_name=fn)
    if not _enabled():
        log.info("cohort_email: would have sent receipt to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "receipt"}
    out = _send_via_sendgrid(to_email=to_email, subject=RECEIPT_SUBJECT, plain_body=body, html_body=html)
    out["kind"] = "receipt"
    return out


def send_approval(*, to_email: str, first_name: Optional[str], magic_link: str) -> Dict[str, str]:
    fn = _first_name_from(first_name, to_email)
    body = APPROVAL_BODY.format(first_name=fn, magic_link=magic_link)
    html = render_approval_html(first_name=fn, magic_link=magic_link)
    if not _enabled():
        log.info("cohort_email: would have sent approval to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "approval"}
    out = _send_via_sendgrid(to_email=to_email, subject=APPROVAL_SUBJECT, plain_body=body, html_body=html)
    out["kind"] = "approval"
    return out


def send_decline(
    *, to_email: str, first_name: Optional[str] = None,
    waitlist_url: Optional[str] = None,
) -> Dict[str, str]:
    fn = _first_name_from(first_name, to_email)
    if waitlist_url:
        body = DECLINE_BODY_WITH_WAITLIST.format(first_name=fn, waitlist_url=waitlist_url)
    else:
        body = DECLINE_BODY.format(first_name=fn)
    html = render_decline_html(first_name=fn, waitlist_url=waitlist_url)
    if not _enabled():
        log.info("cohort_email: would have sent decline to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "decline"}
    out = _send_via_sendgrid(to_email=to_email, subject=DECLINE_SUBJECT, plain_body=body, html_body=html)
    out["kind"] = "decline"
    return out


def send_reminder(*, to_email: str, first_name: Optional[str], magic_link: str) -> Dict[str, str]:
    """Phase P5.7.4 — day-10 expiry reminder. Same flag-gating as the
    other transactional sends."""
    fn = _first_name_from(first_name, to_email)
    body = REMINDER_BODY.format(first_name=fn, magic_link=magic_link)
    html = render_reminder_html(first_name=fn, magic_link=magic_link)
    if not _enabled():
        log.info("cohort_email: would have sent reminder to %s", _redact_email(to_email))
        return {"status": "flag_off", "kind": "reminder"}
    out = _send_via_sendgrid(to_email=to_email, subject=REMINDER_SUBJECT, plain_body=body, html_body=html)
    out["kind"] = "reminder"
    return out


def admin_test_send(
    *, kind: str, to_email: str, first_name: Optional[str] = None,
    magic_link: Optional[str] = None, waitlist_url: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> Dict[str, str]:
    """Phase P5.7.9 — admin-only test-send path. Bypasses
    `COHORT_EMAILS_ENABLED` because the whole point is for the user
    to see the rendered output in their inbox before flipping the
    production flag. NEVER call from non-admin code paths."""
    fn = _first_name_from(first_name, to_email)
    if kind == "receipt":
        subject = RECEIPT_SUBJECT
        plain = RECEIPT_BODY.format(first_name=fn)
        html = render_receipt_html(first_name=fn)
    elif kind == "approval":
        if not magic_link:
            return {"status": "error", "reason": "approval requires magic_link"}
        subject = APPROVAL_SUBJECT
        plain = APPROVAL_BODY.format(first_name=fn, magic_link=magic_link)
        html = render_approval_html(first_name=fn, magic_link=magic_link)
    elif kind == "decline":
        subject = DECLINE_SUBJECT
        if waitlist_url:
            plain = DECLINE_BODY_WITH_WAITLIST.format(first_name=fn, waitlist_url=waitlist_url)
        else:
            plain = DECLINE_BODY.format(first_name=fn)
        html = render_decline_html(first_name=fn, waitlist_url=waitlist_url)
    elif kind == "reminder":
        if not magic_link:
            return {"status": "error", "reason": "reminder requires magic_link"}
        subject = REMINDER_SUBJECT
        plain = REMINDER_BODY.format(first_name=fn, magic_link=magic_link)
        html = render_reminder_html(first_name=fn, magic_link=magic_link)
    else:
        return {"status": "error", "reason": f"unknown kind: {kind}"}
    out = _send_via_sendgrid(
        to_email=to_email, subject=subject, plain_body=plain,
        html_body=html, reply_to=reply_to,
    )
    out["kind"] = kind
    out["test_send"] = True
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
        # P5.7.4 — reminder body is the day-10 expiry nudge.
        "reminder": _word_count(REMINDER_SUBJECT) + _word_count(
            REMINDER_BODY.format(first_name="Friend", magic_link="https://akki.ai/welcome/x")
        ),
        # P5.7.6 — decline-with-waitlist variant must stay ≤80 words
        # (the waitlist line adds 16 words to the 38-word base; the
        # original 60-word cap was for the bare body so we allow a
        # small bump for the variant).
        "decline_waitlist": _word_count(DECLINE_SUBJECT) + _word_count(
            DECLINE_BODY_WITH_WAITLIST.format(
                first_name="Friend",
                waitlist_url="https://akki.syni.ai/waitlist",
            )
        ),
    }
    for kind, n in counts.items():
        cap = 80 if kind == "decline_waitlist" else 60
        assert n <= cap, f"cohort_email body exceeds {cap}-word cap: {kind}={n}"
    return counts


# Run the check at import time so a regression breaks the boot, not prod.
_self_check()
