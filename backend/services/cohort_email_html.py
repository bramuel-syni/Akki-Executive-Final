"""Phase P5.7 (2026-02) — Cohort transactional email HTML rendering.

The original P4 implementation sent plain-text only. P5.7 extends every
template to a multipart message: plain-text fallback (unchanged) plus
an HTML body matching the recipient's mail-client expectations.

Single-column, max-width 560px container. Brand wordmark "Akki for
Executives" at the top, body content in deep ink (#1F1F1F) on warm
white (#FBFAF7), serif voice (Georgia / Iowan / Times), oxblood accent
on the magic-link CTA only (#5A0E22). All inline styles — no external
fonts, no script, no remote images. Outlook-safe.

Voice-lint clean across every template surface.

The renderers here are PURE (no side effects, no env reads); the send
pipeline in `cohort_email.py` consumes them.
"""
from __future__ import annotations

from html import escape
from typing import Optional


# ─── Brand constants ──────────────────────────────────────────────────
_INK = "#1F1F1F"
_PAPER = "#FBFAF7"
_HAIRLINE = "#E5DDD3"
_MUTED = "#65615B"
_OXBLOOD = "#5A0E22"
_FONT = "Georgia, 'Iowan Old Style', 'Times New Roman', serif"


def _shell(title: str, body_html: str) -> str:
    """Wrap a body in the standard table-based container. Mail clients
    that strip <head> still get a coherent visual via inline styles."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:{_PAPER};font-family:{_FONT};color:{_INK};">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:{_PAPER};">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;width:100%;background:#FFFFFF;border:1px solid {_HAIRLINE};">
        <tr>
          <td style="padding:32px 36px 12px 36px;border-bottom:1px solid {_HAIRLINE};">
            <div style="font-family:{_FONT};font-size:18px;font-weight:700;letter-spacing:0.5px;color:{_INK};">Akki <span style="font-weight:400;color:{_MUTED};">for Executives</span></div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 36px 32px 36px;font-family:{_FONT};font-size:16px;line-height:1.55;color:{_INK};">
            {body_html}
          </td>
        </tr>
        <tr>
          <td style="padding:18px 36px 24px 36px;border-top:1px solid {_HAIRLINE};font-family:{_FONT};font-size:12px;line-height:1.5;color:{_MUTED};">
            Akki — a private reading room for board papers, briefings and memos. Your data never leaves your account.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def _para(text: str) -> str:
    """Plain paragraph block."""
    return f'<p style="margin:0 0 16px 0;font-family:{_FONT};font-size:16px;line-height:1.55;color:{_INK};">{escape(text)}</p>'


def _signoff() -> str:
    return f'<p style="margin:24px 0 0 0;font-family:{_FONT};font-size:16px;line-height:1.55;color:{_INK};">— Akki</p>'


# ─── Receipt ──────────────────────────────────────────────────────────
def render_receipt_html(*, first_name: str) -> str:
    body = (
        _para(f"{first_name},")
        + _para("Thanks — we have your application. We read every one personally and aim to reply within three business days.")
        + _para("If you sent it on a Friday, that means Wednesday.")
        + _signoff()
    )
    return _shell("Got your Akki application", body)


# ─── Approval ─────────────────────────────────────────────────────────
def render_approval_html(*, first_name: str, magic_link: str) -> str:
    link = escape(magic_link, quote=True)
    cta = (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:20px 0 8px 0;"><tr>'
        f'<td style="background:{_OXBLOOD};border-radius:2px;">'
        f'<a href="{link}" target="_blank" rel="noopener" '
        f'style="display:inline-block;padding:12px 22px;font-family:{_FONT};'
        f'font-size:15px;font-weight:600;color:#FFFFFF;text-decoration:none;'
        f'letter-spacing:0.3px;">Open your workspace</a>'
        f'</td></tr></table>'
    )
    fallback = (
        f'<p style="margin:6px 0 14px 0;font-family:{_FONT};font-size:13px;'
        f'line-height:1.5;color:{_MUTED};word-break:break-all;">'
        f'If the button doesn\'t work, paste this into your browser:<br>'
        f'<a href="{link}" target="_blank" rel="noopener" '
        f'style="color:{_OXBLOOD};">{link}</a>'
        f'</p>'
    )
    body = (
        _para(f"{first_name},")
        + _para("You're in. Open your workspace with the button below — it works once and expires in 14 days.")
        + cta
        + fallback
        + _para("If you'd rather sign in with Google or Microsoft, the same link gives you both options.")
        + _signoff()
    )
    return _shell("Your Akki workspace is ready", body)


# ─── Decline ──────────────────────────────────────────────────────────
def render_decline_html(*, first_name: str, waitlist_url: Optional[str] = None) -> str:
    body = (
        _para(f"{first_name},")
        + _para("Thanks for your application. We're not a fit right now, but we read it carefully. We're keeping our list small to honour the response time we promised others.")
    )
    if waitlist_url:
        link = escape(waitlist_url, quote=True)
        body += (
            f'<p style="margin:0 0 16px 0;font-family:{_FONT};font-size:16px;'
            f'line-height:1.55;color:{_INK};">If you\'d like to be considered for '
            f'a later cohort, leave your email on the waitlist: '
            f'<a href="{link}" target="_blank" rel="noopener" style="color:{_OXBLOOD};">{link}</a></p>'
        )
    body += _signoff()
    return _shell("Akki — not this time", body)


# ─── Day-10 expiry reminder (Touch 4) ─────────────────────────────────
def render_reminder_html(*, first_name: str, magic_link: str) -> str:
    link = escape(magic_link, quote=True)
    cta = (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:20px 0 8px 0;"><tr>'
        f'<td style="background:{_OXBLOOD};border-radius:2px;">'
        f'<a href="{link}" target="_blank" rel="noopener" '
        f'style="display:inline-block;padding:12px 22px;font-family:{_FONT};'
        f'font-size:15px;font-weight:600;color:#FFFFFF;text-decoration:none;'
        f'letter-spacing:0.3px;">Open your workspace</a>'
        f'</td></tr></table>'
    )
    body = (
        _para(f"{first_name},")
        + _para("Quick reminder — your Akki invite expires in four days. Open your workspace whenever you have ten quiet minutes.")
        + cta
        + _para("If the moment isn't right, just reply and we'll hold a place.")
        + _signoff()
    )
    return _shell("Akki — your invite expires in four days", body)
