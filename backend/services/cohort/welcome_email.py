"""Phase R.2 (2026-05-27) — Founding Cohort welcome email composer + SendGrid send.

Locked autonomous-mode contract:
  - The welcome-email HTML body ships with the placeholder
    `[FOUNDER: edit before sending real invites]` in 4 spots that the
    founder must fill before going live (greeting personality, the
    "what AKKI is" explainer, the "what we ask of you" ask, and the
    sign-off voice).
  - A MANDATORY server-side guard (`assert_no_founder_placeholder`)
    refuses to send if any `[FOUNDER:` token still appears in the
    rendered HTML body or subject. The endpoint returns 422 with
    `{detail, founder_placeholders_remaining}`.
  - Send is via SendGrid (already wired across the codebase; SDK
    `sendgrid==6.12.5`, env vars `SENDGRID_API_KEY` / `SENDGRID_FROM_EMAIL`).
  - Send is async (BackgroundTasks). Success emits
    `cohort_welcome_sent: {...}` structured log; failure emits
    `cohort_welcome_failed: {...}` (admin can re-trigger via the
    `?send=1` query on the create endpoint).

This module exposes 3 public functions:
  - `build_welcome_html(invite_payload) -> {subject, html, text}`
  - `assert_no_founder_placeholder(rendered) -> None`  (raises 422)
  - `send_welcome_email_async(rendered, to_email, invite_id) -> None`
    (called from BackgroundTasks; never raises)
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from fastapi import HTTPException


log = logging.getLogger("akki.cohort.welcome_email")


# ─────────────────────────────────────────────────────────────────────
# Locked placeholder marker — exactly this prefix triggers the 422 guard.
# Future agents must NOT change the prefix without dispatching a new R
# sub-phase; the marker is part of the institutional contract.
# ─────────────────────────────────────────────────────────────────────
FOUNDER_PLACEHOLDER_PREFIX = "[FOUNDER:"


# ─────────────────────────────────────────────────────────────────────
# build_welcome_html — composes the welcome email HTML + plain-text fallback
# ─────────────────────────────────────────────────────────────────────
def build_welcome_html(payload: Dict[str, Any]) -> Dict[str, str]:
    """Compose subject + html + text from the SendGrid-ready payload
    that R.1 already produces on invite creation.

    R.5.b note: this function returns the DEFAULT template (with
    `[FOUNDER:]` placeholders). The consumer (`issue_invite`) calls
    `services.cohort.copy_overrides.get_slot_override('welcome_email')`
    + `overlay_slot(...)` to layer any founder-saved override before
    handing the rendered payload to the SendGrid client.

    The body is intentionally minimal — typography clean, no logos,
    no marketing gloss. AKKI's founder voice is paramount; the
    placeholder text is shipped pre-filled with a clearly-marked
    `[FOUNDER: …]` instruction so the founder edits it once before
    going live.

    Args:
      payload: `{ first_name, logo_name, cohort_tag, magic_link,
                  trial_length_days, trial_end_at, expires_at }`

    Returns:
      `{ subject, html, text }` — all strings.
    """
    first_name = payload.get("first_name") or "there"
    logo_name = payload.get("logo_name") or "your team"
    magic_link = payload["magic_link"]
    trial_length = payload.get("trial_length_days") or 30
    expires_at_iso = payload.get("expires_at") or ""
    # Render expires_at as a friendlier date string (best-effort; on
    # failure keep the ISO form).
    expires_at_pretty = expires_at_iso
    try:
        from datetime import datetime
        d = datetime.fromisoformat(expires_at_iso.replace("Z", "+00:00"))
        expires_at_pretty = d.strftime("%B %d, %Y")
    except Exception:
        pass

    subject = f"You're in — your AKKI founding-cohort access for {logo_name}"

    # The 4 [FOUNDER: …] placeholders the founder must edit before going live:
    #   1. Greeting personality (one sentence)
    #   2. "What AKKI is" (one paragraph)
    #   3. "What we ask of you" (one paragraph)
    #   4. Sign-off voice (signature line)

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
              <p style="margin:0 0 16px 0;font-family:'SF Mono',Menlo,monospace;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#6B6358;">AKKI — Founding Cohort</p>
              <h1 style="margin:0 0 24px 0;font-family:Georgia,serif;font-size:28px;line-height:1.25;font-weight:normal;color:#1F1C18;">Welcome, {first_name}.</h1>
              <p style="margin:0 0 16px 0;color:#3C3530;">{FOUNDER_PLACEHOLDER_PREFIX} write one sentence here in your voice that opens the email warmly without being twee — e.g. "It means a lot that you're trying this with us." Edit before sending real invites.]</p>

              <p style="margin:0 0 16px 0;color:#3C3530;">{FOUNDER_PLACEHOLDER_PREFIX} write a single paragraph (3-5 sentences) explaining what AKKI actually is in your founder voice. The colleague who reads everything with them. Boards, ops, monitoring, briefings, research. What you don't have time to read. What they asked the last six meetings. Edit before sending.]</p>

              <p style="margin:0 0 16px 0;color:#3C3530;">{FOUNDER_PLACEHOLDER_PREFIX} write a single paragraph asking what we need from them — that this is a 30-day founding cohort, that we'd love their unvarnished feedback, that you'll personally read every reply. Edit before sending.]</p>

              <p style="margin:24px 0 16px 0;color:#3C3530;">When you're ready, here's your private door:</p>
              <p style="margin:0 0 24px 0;">
                <a href="{magic_link}" style="display:inline-block;padding:14px 24px;background:#1F1C18;color:#FAF7F2;font-family:Georgia,serif;font-size:15px;text-decoration:none;border-radius:0;letter-spacing:0.02em;">Open AKKI for {logo_name} &rarr;</a>
              </p>
              <p style="margin:0 0 32px 0;font-size:13px;color:#6B6358;">This link works once and stays open until {expires_at_pretty}. Your trial runs for {trial_length} days from first sign-in.</p>

              <p style="margin:0 0 8px 0;color:#3C3530;">{FOUNDER_PLACEHOLDER_PREFIX} sign off in your own voice — first name, role, single line, no marketing gloss. Edit before sending.]</p>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px;border-top:1px solid #E8E2D5;font-size:11px;color:#6B6358;font-family:Georgia,serif;">
              <p style="margin:0 0 8px 0;">If this email landed unexpectedly, you can ignore it &mdash; the link below expires automatically.</p>
              <p style="margin:0;font-family:'SF Mono',Menlo,monospace;font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:#8A8378;">Synisense-shielded &middot; AKKI &middot; akki.ai</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    text = f"""Welcome, {first_name}.

{FOUNDER_PLACEHOLDER_PREFIX} write one sentence in your voice that opens the email warmly. Edit before sending real invites.]

{FOUNDER_PLACEHOLDER_PREFIX} write a single paragraph explaining what AKKI is in your founder voice. Edit before sending.]

{FOUNDER_PLACEHOLDER_PREFIX} write a single paragraph asking what we need from them. Edit before sending.]

When you're ready, here's your private door to AKKI for {logo_name}:
{magic_link}

This link works once and stays open until {expires_at_pretty}. Your trial runs for {trial_length} days from first sign-in.

{FOUNDER_PLACEHOLDER_PREFIX} sign off in your own voice. Edit before sending.]

AKKI — Synisense-shielded — akki.ai
"""

    return {"subject": subject, "html": html, "text": text}


# ─────────────────────────────────────────────────────────────────────
# assert_no_founder_placeholder — the locked 422 guard
# ─────────────────────────────────────────────────────────────────────
def assert_no_founder_placeholder(rendered: Dict[str, str]) -> None:
    """Raise HTTPException(422) if any `[FOUNDER:` marker still appears
    in the rendered subject, html, or text. The error payload carries
    `founder_placeholders_remaining` (count) so the admin can act.

    R.2.1 (queued separately) will add a preview endpoint that returns
    the rendered body WITHOUT sending — so founders can iterate on
    copy before flipping `send_email=1`."""
    matches: list[str] = []
    for field in ("subject", "html", "text"):
        s = rendered.get(field, "") or ""
        for m in re.finditer(re.escape(FOUNDER_PLACEHOLDER_PREFIX), s):
            # Capture a short window so the admin sees which placeholder is left.
            start = m.start()
            window = s[start:start + 80].replace("\n", " ")
            matches.append(f"{field}:{window}")
            if len(matches) >= 8:
                break
        if len(matches) >= 8:
            break
    if matches:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "founder_placeholder_present",
                "message": (
                    "Welcome email refuses to send while `[FOUNDER:` "
                    "placeholders are still in the body. Edit "
                    "`services/cohort/welcome_email.py::build_welcome_html` "
                    "(replace all 4 placeholders) and redeploy before sending."
                ),
                "founder_placeholders_remaining": len(matches),
                "examples": matches[:3],
            },
        )


# ─────────────────────────────────────────────────────────────────────
# send_welcome_email_async — the actual SendGrid send (BackgroundTasks)
# ─────────────────────────────────────────────────────────────────────
def send_welcome_email_async(
    *,
    rendered: Dict[str, str],
    to_email: str,
    invite_id: str,
    cohort_tag: str,
) -> None:
    """Fire the SendGrid send. NEVER raises — failures emit a
    `cohort_welcome_failed: {...}` log line so the admin can re-send
    manually via the existing `?send=1` mechanism.

    Called from FastAPI's BackgroundTasks (sync function — SendGrid's
    Python SDK is sync; BackgroundTasks runs sync fns in a threadpool).
    """
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_email = (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
    sandbox = os.environ.get("SENDGRID_SANDBOX_ONLY", "0").strip() == "1"

    base_log = {
        "invite_id": invite_id,
        "to": to_email,
        "cohort_tag": cohort_tag,
        "subject": rendered.get("subject", ""),
        "sandbox": sandbox,
    }

    if not api_key or not from_email:
        log.error("cohort_welcome_failed: %s", {
            **base_log,
            "code": "sendgrid_not_configured",
            "error": "SENDGRID_API_KEY or SENDGRID_FROM_EMAIL missing",
        })
        return

    try:
        from sendgrid import SendGridAPIClient  # type: ignore
        from sendgrid.helpers.mail import (  # type: ignore
            Mail, Email, To, Content, MailSettings, SandBoxMode,
        )
    except Exception as e:  # noqa: BLE001
        log.error("cohort_welcome_failed: %s", {
            **base_log,
            "code": "sendgrid_sdk_not_importable",
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
            log.info("cohort_welcome_sent: %s", {**base_log, "status": status})
        else:
            log.error("cohort_welcome_failed: %s", {
                **base_log,
                "code": "sendgrid_non_2xx",
                "status": status,
            })
    except Exception as e:  # noqa: BLE001
        log.error("cohort_welcome_failed: %s", {
            **base_log,
            "code": "sendgrid_exception",
            "error": str(e)[:200],
        })
