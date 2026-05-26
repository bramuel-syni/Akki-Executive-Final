"""Phase F.5 — Contributor invitation orchestration (2026-05-26).

Handles the on-commission email fan-out for all 3 contributor modes:

  Mode 1 — `akki_account`  : look up Akki user by email, fire transactional
                             email with deep-link to /app/task-manager?task_id=…
  Mode 2 — `magic_link`    : mint a 30-day url-safe token, persist to
                             `task_contributor_tokens`, fire transactional
                             email with /contribute/<token> link
  Mode 3 — `email_reply`   : fire transactional email with a `reply_to`
                             address of `task-<token>@<CYCLE_REPLY_DOMAIN>`.
                             Same token shape as magic-link — Postmark
                             inbound webhook resolves token → contributor.

A contributor may have `email_reply=True` AS A FALLBACK alongside
mode 1 or mode 2 — set via `allow_email_reply: True` on the team row.
In that case BOTH emails fire and whichever submission arrives first
wins (the other becomes a no-op confirmation).

If Postmark send fails for any reason, the magic-link token is still
persisted; the audit row records `send_failed`. The user can be given
the link manually (visible on the Contributions tab's row).
"""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


log = logging.getLogger("akki.tasks.contrib")


CONTRIB_TOKEN_TTL_DAYS = 30
# SendGrid Inbound Parse domain (preferred). Falls back to the legacy
# `CYCLE_REPLY_DOMAIN` for environments that haven't migrated. The
# domain MUST have MX records pointing at SendGrid AND a matching
# Inbound Parse webhook configured in the SendGrid dashboard.
_INBOUND_DOMAIN = (
    os.environ.get("SENDGRID_INBOUND_DOMAIN")
    or os.environ.get("CYCLE_REPLY_DOMAIN")
    or "akki.syni.ai"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_token() -> str:
    return secrets.token_urlsafe(32)


def _resolve_app_base(provided: Optional[str]) -> str:
    if provided and provided.startswith(("http://", "https://")):
        return provided
    return os.environ.get("PUBLIC_BASE_URL") or os.environ.get("REACT_APP_BACKEND_URL") or ""


# ═════════════════════════════════════════════════════════════════════
# Token persistence
# ═════════════════════════════════════════════════════════════════════
async def mint_contributor_token(
    db, *, task_id: str, contributor_email: str,
    contributor_id: Optional[str], task_account_id: str,
    revoke_existing: bool = True,
) -> Dict[str, Any]:
    """Mint a contributor magic-link token. By default any prior token
    on the same (task_id, contributor_email) is revoked so Re-invite
    rotates cleanly."""
    if revoke_existing:
        await db.task_contributor_tokens.update_many(
            {"task_id": task_id, "contributor_email": contributor_email.lower(), "used": False},
            {"$set": {"used": True, "revoked_at": _now_iso(),
                       "revoked_reason": "rotated_on_reinvite"}},
        )
    token = _gen_token()
    expires = datetime.now(timezone.utc) + timedelta(days=CONTRIB_TOKEN_TTL_DAYS)
    row = {
        "id":                  str(uuid.uuid4()),
        "token":                token,
        "task_id":              task_id,
        "task_account_id":      task_account_id,
        "contributor_email":    contributor_email.strip().lower(),
        "contributor_id":       contributor_id,
        "expires_at":           expires.isoformat(),
        "used":                 False,
        "created_at":           _now_iso(),
    }
    await db.task_contributor_tokens.insert_one(dict(row))
    return row


# ═════════════════════════════════════════════════════════════════════
# Per-mode dispatch
# ═════════════════════════════════════════════════════════════════════
async def _send(*, to: str, subject: str, text: str, html: str,
                reply_to: Optional[str] = None) -> Dict[str, Any]:
    try:
        from email_service import send_email
        return await send_email(to=to, subject=subject, text=text, html=html, reply_to=reply_to)
    except Exception as e:  # noqa: BLE001
        log.warning("email send failed (to=%s): %s", to, e)
        return {"mode": "send_failed", "error": str(e)[:200]}


async def invite_akki_account(
    db, *, task: Dict[str, Any], contributor: Dict[str, Any], app_base: str,
) -> Dict[str, Any]:
    """Mode 1 — the contributor already has an Akki account."""
    deep_link = f"{app_base.rstrip('/')}/app/task-manager?task_id={task['id']}"
    subject = f"You've been added to a task in Akki — {task.get('name', '')}"
    text = (
        f"{contributor.get('name') or 'Hi'},\n\n"
        f"You've been added as a contributor on the task: {task.get('name', '')}.\n\n"
        f"Your contribution: {contributor.get('contribution') or '(see task brief)'}\n"
        + (f"Due: {contributor.get('due_date')}\n" if contributor.get("due_date") else "")
        + f"\nOpen the task: {deep_link}\n"
    )
    html = (
        f"<p>Hi {contributor.get('name') or ''},</p>"
        f"<p>You've been added as a contributor on the task: <b>{task.get('name', '')}</b>.</p>"
        f"<p><b>Your contribution:</b> {contributor.get('contribution') or '(see task brief)'}</p>"
        + (f"<p><b>Due:</b> {contributor.get('due_date')}</p>" if contributor.get("due_date") else "")
        + f"<p><a href='{deep_link}' style='display:inline-block;padding:8px 16px;background:#7A2E2E;color:white;text-decoration:none;border-radius:2px'>Open the task</a></p>"
    )
    return await _send(to=contributor["email"], subject=subject, text=text, html=html)


async def invite_magic_link(
    db, *, task: Dict[str, Any], contributor: Dict[str, Any], app_base: str,
) -> Dict[str, Any]:
    """Mode 2 — mint a token + send the /contribute/<token> link."""
    row = await mint_contributor_token(
        db,
        task_id=task["id"],
        contributor_email=contributor["email"],
        contributor_id=contributor.get("contributor_id") or contributor.get("email"),
        task_account_id=task["account_id"],
    )
    token = row["token"]
    deep_link = f"{app_base.rstrip('/')}/contribute/{token}"
    subject = f"Action requested — {task.get('name', '')}"
    text = (
        f"{contributor.get('name') or 'Hi'},\n\n"
        f"You've been asked to contribute to: {task.get('name', '')}.\n\n"
        f"Your contribution: {contributor.get('contribution') or '(see task brief)'}\n"
        + (f"Due: {contributor.get('due_date')}\n" if contributor.get("due_date") else "")
        + f"\nNo account needed — open the contributor portal:\n  {deep_link}\n\n"
        f"Link expires in {CONTRIB_TOKEN_TTL_DAYS} days.\n"
    )
    html = (
        f"<p>Hi {contributor.get('name') or ''},</p>"
        f"<p>You've been asked to contribute to: <b>{task.get('name', '')}</b>.</p>"
        f"<p><b>Your contribution:</b> {contributor.get('contribution') or '(see task brief)'}</p>"
        + (f"<p><b>Due:</b> {contributor.get('due_date')}</p>" if contributor.get("due_date") else "")
        + "<p>No account needed — open the contributor portal:</p>"
        + f"<p><a href='{deep_link}' style='display:inline-block;padding:8px 16px;background:#7A2E2E;color:white;text-decoration:none;border-radius:2px'>Open contributor portal</a></p>"
        + f"<p style='color:#888;font-size:12px'>Link expires in {CONTRIB_TOKEN_TTL_DAYS} days.</p>"
    )
    result = await _send(to=contributor["email"], subject=subject, text=text, html=html)
    return {**result, "token": token, "url": deep_link}


async def invite_email_reply(
    db, *, task: Dict[str, Any], contributor: Dict[str, Any], app_base: str,
    reuse_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Mode 3 — mint a token (or reuse from a paired magic-link invite),
    set `reply_to` to `task-<token>@<CYCLE_REPLY_DOMAIN>`."""
    token = reuse_token
    if not token:
        row = await mint_contributor_token(
            db,
            task_id=task["id"],
            contributor_email=contributor["email"],
            contributor_id=contributor.get("contributor_id") or contributor.get("email"),
            task_account_id=task["account_id"],
        )
        token = row["token"]
    reply_to = f"task-{token}@{_INBOUND_DOMAIN}"
    subject = f"Action requested — {task.get('name', '')}"
    text = (
        f"{contributor.get('name') or 'Hi'},\n\n"
        f"You've been asked to contribute to: {task.get('name', '')}.\n\n"
        f"Your contribution: {contributor.get('contribution') or '(see task brief)'}\n"
        + (f"Due: {contributor.get('due_date')}\n" if contributor.get("due_date") else "")
        + "\nJust reply to this email with your contribution attached. Akki "
          "will pick it up automatically and notify the task owner.\n"
    )
    html = (
        f"<p>Hi {contributor.get('name') or ''},</p>"
        f"<p>You've been asked to contribute to: <b>{task.get('name', '')}</b>.</p>"
        f"<p><b>Your contribution:</b> {contributor.get('contribution') or '(see task brief)'}</p>"
        + (f"<p><b>Due:</b> {contributor.get('due_date')}</p>" if contributor.get("due_date") else "")
        + "<p>Just <b>reply to this email</b> with your contribution attached. Akki "
          "will pick it up automatically and notify the task owner.</p>"
    )
    result = await _send(to=contributor["email"], subject=subject, text=text, html=html,
                          reply_to=reply_to)
    return {**result, "token": token, "reply_to": reply_to}


# ═════════════════════════════════════════════════════════════════════
# Fan-out + audit
# ═════════════════════════════════════════════════════════════════════
async def fan_out_invitations(
    db, *, task: Dict[str, Any], app_base: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fire one invitation per team member according to their
    contribution_mode + allow_email_reply flag. Returns a list of
    per-contributor status records.

    Coexistence rule: if `mode != "email_reply"` AND
    `allow_email_reply == True`, fire BOTH emails. Whichever arrives
    first wins — the other becomes a no-op confirmation (the
    token-revocation check inside the public endpoints handles this)."""
    app_base = _resolve_app_base(app_base)
    out: List[Dict[str, Any]] = []
    for member in (task.get("team") or []):
        email = (member.get("email") or "").strip().lower()
        if not email:
            continue
        mode = (member.get("contribution_mode") or "akki_account").lower()
        allow_reply = bool(member.get("allow_email_reply"))
        emails_fired: List[Dict[str, Any]] = []

        if mode == "akki_account":
            r = await invite_akki_account(db, task=task, contributor={**member, "email": email},
                                          app_base=app_base)
            emails_fired.append({"channel": "akki_account", **r})
            if allow_reply:
                r2 = await invite_email_reply(db, task=task, contributor={**member, "email": email},
                                                app_base=app_base)
                emails_fired.append({"channel": "email_reply_fallback", **r2})

        elif mode == "magic_link":
            r = await invite_magic_link(db, task=task, contributor={**member, "email": email},
                                         app_base=app_base)
            emails_fired.append({"channel": "magic_link", **r})
            if allow_reply:
                # Pair the email-reply invite to the same token so a reply
                # OR a portal submission both resolve to the same
                # contributor record.
                r2 = await invite_email_reply(db, task=task, contributor={**member, "email": email},
                                                app_base=app_base, reuse_token=r.get("token"))
                emails_fired.append({"channel": "email_reply_fallback", **r2})

        elif mode == "email_reply":
            r = await invite_email_reply(db, task=task, contributor={**member, "email": email},
                                          app_base=app_base)
            emails_fired.append({"channel": "email_reply", **r})

        else:
            emails_fired.append({"channel": "unknown_mode", "mode": "send_failed"})

        # Audit row per contributor.
        try:
            await db.audit_log.insert_one({
                "id":            str(uuid.uuid4()),
                "context_id":    task.get("context_id"),
                "account_id":    task["account_id"],
                "action":        "task.contributor.invited",
                "resource_type": "task",
                "resource_id":   task["id"],
                "metadata": {
                    "contributor_email": email,
                    "mode":              mode,
                    "allow_email_reply": allow_reply,
                    "channels":          [c.get("channel") for c in emails_fired],
                    "delivery_status":   [c.get("mode") for c in emails_fired],
                },
                "created_at":    _now_iso(),
            })
        except Exception as e:  # noqa: BLE001
            log.warning("contributor.invited audit failed: %s", e)

        out.append({"email": email, "mode": mode, "emails": emails_fired})
    return out
