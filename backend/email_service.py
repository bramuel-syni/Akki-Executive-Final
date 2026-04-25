"""Resend transactional email service.

Single entry point for all outbound mail from AKKI. Sender format follows
the iter18 governance posture: 'AKKI for <Executive Name> <noreply@akki.ai>'
with reply-to set to the executive's real email address — so AKKI's role is
explicit while replies route back to the principal naturally.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import resend

logger = logging.getLogger("akki.email")

_RESEND_KEY = os.environ.get("RESEND_API_KEY")
_DEFAULT_FROM = os.environ.get("RESEND_FROM_EMAIL") or "onboarding@resend.dev"
_DEFAULT_FROM_NAME = os.environ.get("RESEND_FROM_NAME") or "AKKI"

if _RESEND_KEY:
    resend.api_key = _RESEND_KEY


def configured() -> bool:
    """Return True iff Resend is wired (allows callers to fall back to mailto)."""
    return bool(_RESEND_KEY)


def _format_from(executive_name: Optional[str]) -> str:
    """Compose the From header per iter18 Q3=b: 'AKKI for Bramuel <noreply@...>'.
    Falls back to plain 'AKKI <noreply@...>' if no executive name provided."""
    if executive_name:
        clean = executive_name.replace('"', "").strip()
        if clean:
            return f'"AKKI for {clean}" <{_DEFAULT_FROM}>'
    return f'"{_DEFAULT_FROM_NAME}" <{_DEFAULT_FROM}>'


async def send_email(
    *,
    to: List[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
    reply_to: Optional[str] = None,
    from_executive_name: Optional[str] = None,
    tags: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Send a transactional email via Resend.

    Returns `{ok, id, mode}` where mode is 'sent' on success, 'noop' if Resend
    is not configured (caller can fall back), or 'error' on failure. Never
    raises — email failures must not crash a UX flow."""
    if not _RESEND_KEY:
        logger.warning("Resend not configured — email to %s skipped", to)
        return {"ok": False, "id": None, "mode": "noop", "error": "RESEND_API_KEY not set"}

    params: Dict[str, Any] = {
        "from": _format_from(from_executive_name),
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

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"ok": True, "id": result.get("id"), "mode": "sent"}
    except Exception as e:  # noqa: BLE001 — Resend wraps all errors
        logger.exception("Resend send failed")
        return {"ok": False, "id": None, "mode": "error", "error": str(e)[:300]}


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
