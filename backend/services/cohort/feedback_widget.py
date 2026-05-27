"""Phase R.4 (2026-05-27) — In-app feedback widget — auto-thanks email composer.

Locked autonomous-mode contract (mirrors R.2's `welcome_email.py`
pattern):
  - Fixed-position widget on every authenticated app surface POSTs
    `{text, tag, surface_path}` → `POST /api/feedback`.
  - Server emits a `feedback.submitted` feature_event AND queues an
    auto-thanks email to the user via BackgroundTasks.
  - Auto-thanks body ships with `[FOUNDER: thank-you copy here ...]`
    placeholder + MANDATORY server-side 422 guard refusing to send if
    the placeholder is still present (locked institutional pattern).
  - Tag taxonomy LOCKED to {"Broken", "Wrong", "Great"} — these
    surface in the cohort funnel as `tag` payload fields, NOT as
    distinct event_types (single funnel slot keeps R.5 console
    simple).

This module exposes:
  - `build_thanks_html(payload) -> {subject, html, text}`
  - The R.2 `assert_no_founder_placeholder` is REUSED (same prefix,
    same 422 contract).
  - `send_thanks_email_async(rendered, to_email, …)`
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict


log = logging.getLogger("akki.cohort.feedback_widget")


# ─────────────────────────────────────────────────────────────────────
# Locked tag taxonomy — R.4 widget uses ONLY these three. Future
# tag-taxonomy changes MUST dispatch a new R sub-phase per the
# institutional copy-lock pattern.
# ─────────────────────────────────────────────────────────────────────
FEEDBACK_TAGS = ("Broken", "Wrong", "Great")


# Reuse the R.2 placeholder marker so the guard contract stays unified.
from services.cohort.welcome_email import FOUNDER_PLACEHOLDER_PREFIX  # noqa: E402


def build_thanks_html(payload: Dict[str, Any]) -> Dict[str, str]:
    """Compose the auto-thanks email body. Carries 2 `[FOUNDER:`
    placeholders the founder must edit before going live (greeting
    voice + sign-off voice). Identical 422-guard contract to R.2.

    Args:
      payload: `{ first_name, tag, text, surface_path }`

    Returns:
      `{ subject, html, text }`
    """
    first_name    = payload.get("first_name") or "there"
    tag           = payload.get("tag") or ""
    text          = payload.get("text") or ""
    surface_path  = payload.get("surface_path") or ""

    subject = "We got your note — thank you"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#FAF7F2;color:#1F1C18;font-family:Georgia,serif;font-size:16px;line-height:1.6;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;width:100%;background:#FFFFFF;border:1px solid #E8E2D5;">
          <tr>
            <td style="padding:40px 40px 24px 40px;">
              <p style="margin:0 0 16px 0;font-family:'SF Mono',Menlo,monospace;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#6B6358;">AKKI &middot; Founding cohort</p>
              <h1 style="margin:0 0 24px 0;font-family:Georgia,serif;font-size:24px;line-height:1.3;font-weight:normal;color:#1F1C18;">Thank you, {first_name}.</h1>
              <p style="margin:0 0 16px 0;color:#3C3530;">{FOUNDER_PLACEHOLDER_PREFIX} write 2-3 sentences in your founder voice that acknowledges the feedback warmly and personally. Mention you read every reply. Edit before sending real auto-thanks.]</p>

              <div style="margin:24px 0;padding:16px 20px;border-left:3px solid #C4B89E;background:#FAF7F2;">
                <p style="margin:0 0 8px 0;font-family:'SF Mono',Menlo,monospace;font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:#6B6358;">Your note &mdash; tagged {tag}</p>
                <p style="margin:0;color:#3C3530;font-style:italic;">{text}</p>
                <p style="margin:8px 0 0 0;font-size:11px;color:#8A8378;">on {surface_path}</p>
              </div>

              <p style="margin:24px 0 16px 0;color:#3C3530;">{FOUNDER_PLACEHOLDER_PREFIX} sign off in your voice. One line, your name, your role. Edit before sending.]</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px;border-top:1px solid #E8E2D5;font-size:11px;color:#6B6358;font-family:Georgia,serif;">
              <p style="margin:0;font-family:'SF Mono',Menlo,monospace;font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:#8A8378;">Synisense-shielded &middot; AKKI &middot; akki.ai</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    text_body = f"""Thank you, {first_name}.

{FOUNDER_PLACEHOLDER_PREFIX} write 2-3 sentences acknowledging the feedback in your founder voice. Edit before sending.]

Your note (tagged {tag}):
"{text}"
on {surface_path}

{FOUNDER_PLACEHOLDER_PREFIX} sign off in your voice. Edit before sending.]

AKKI — Synisense-shielded — akki.ai
"""

    return {"subject": subject, "html": html, "text": text_body}


# ─────────────────────────────────────────────────────────────────────
# send_thanks_email_async — mirrors R.2's send pattern.
# ─────────────────────────────────────────────────────────────────────
def send_thanks_email_async(
    *,
    rendered: Dict[str, str],
    to_email: str,
    feedback_id: str,
    tag: str,
) -> None:
    """Fire the auto-thanks SendGrid send. NEVER raises."""
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_email = (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
    sandbox = os.environ.get("SENDGRID_SANDBOX_ONLY", "0").strip() == "1"

    base_log = {
        "feedback_id": feedback_id, "to": to_email, "tag": tag,
        "subject": rendered.get("subject", ""), "sandbox": sandbox,
    }

    if not api_key or not from_email:
        log.error("feedback_thanks_failed: %s", {
            **base_log, "code": "sendgrid_not_configured",
        })
        return

    try:
        from sendgrid import SendGridAPIClient  # type: ignore
        from sendgrid.helpers.mail import (  # type: ignore
            Mail, Email, To, Content, MailSettings, SandBoxMode,
        )
    except Exception as e:  # noqa: BLE001
        log.error("feedback_thanks_failed: %s", {
            **base_log, "code": "sendgrid_sdk_not_importable",
            "error": str(e)[:200],
        })
        return

    try:
        mail = Mail(
            from_email=Email(from_email),
            to_emails=To(to_email),
            subject=rendered["subject"],
            plain_text_content=Content("text/plain", rendered["text"]),
            html_content=Content("text/html", rendered["html"]),
        )
        if sandbox:
            ms = MailSettings()
            ms.sandbox_mode = SandBoxMode(enable=True)
            mail.mail_settings = ms

        sg = SendGridAPIClient(api_key)
        resp = sg.send(mail)
        status = int(getattr(resp, "status_code", 0) or 0)
        if 200 <= status < 300:
            log.info("feedback_thanks_sent: %s", {**base_log, "status": status})
        else:
            log.error("feedback_thanks_failed: %s", {
                **base_log, "code": "sendgrid_non_2xx", "status": status,
            })
    except Exception as e:  # noqa: BLE001
        log.error("feedback_thanks_failed: %s", {
            **base_log, "code": "sendgrid_exception", "error": str(e)[:200],
        })
