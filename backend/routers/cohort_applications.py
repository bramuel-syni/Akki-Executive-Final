"""Sprint M.0c (2026-02 fork-resume v3) — Cohort applications scaffold.

Scaffold ONLY. Copy is placeholder (M.2 fills it). No Stripe wiring,
no JSX. The user-facing /cohort form (Sprint M.1) will POST here.

Endpoint:
  POST /api/cohort/applications
    body: { name, email, organisation, role, use_case, referral_source }
    → stores into `cohort_applications` Mongo collection with
      created_at + status="received". Idempotent on duplicate email
      within 24h (same email → same application id returned).
    → if FOUNDER_NOTIFY_EMAIL env is set, fires a SendGrid notification.
      Unset → no-op + warning log (never 500).
    → applicant auto-confirmation email scaffolded with COPY TBD
      placeholder; send is no-op until M.2 lands real copy.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import db
from services.rate_limit import rate_limit

log = logging.getLogger("akki.cohort.applications")
router = APIRouter(prefix="/api/cohort", tags=["cohort"])


class CohortApplicationIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    organisation: str = Field(..., min_length=1, max_length=200)
    role: str = Field(..., min_length=1, max_length=200)
    use_case: str = Field(..., min_length=1, max_length=2000)
    referral_source: Optional[str] = Field(None, max_length=200)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_founder_recipients(raw: str) -> list[str]:
    """Parse FOUNDER_NOTIFY_EMAIL as a comma-separated list. Whitespace
    is stripped per entry; empty entries are filtered. Returns [] when
    unset or comma-only."""
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _notify_founder(app_row: dict) -> None:
    """No-op if FOUNDER_NOTIFY_EMAIL / SENDGRID_* unset.
    Mirrors `services.cohort.welcome_email::send_welcome_email_async`
    error-handling shape — never raises, logs `cohort_application_*`.
    Multi-recipient: FOUNDER_NOTIFY_EMAIL accepts a comma-separated
    list; one SendGrid call goes to all recipients."""
    recipients = _parse_founder_recipients(
        os.environ.get("FOUNDER_NOTIFY_EMAIL") or ""
    )
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_email = (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
    if not recipients or not api_key or not from_email:
        log.warning("cohort_application_notify_skipped: %s", {
            "id": app_row["id"], "reason": "sendgrid_or_founder_email_unset",
            "recipient_count": len(recipients),
        })
        return
    try:
        from sendgrid import SendGridAPIClient  # type: ignore
        from sendgrid.helpers.mail import Mail, Email, To, Content  # type: ignore
    except Exception as e:  # noqa: BLE001
        log.error("cohort_application_notify_failed: %s", {
            "id": app_row["id"], "code": "sdk_unavailable", "error": str(e)[:200],
        })
        return
    try:
        mail = Mail(
            from_email=Email(from_email),
            to_emails=[To(addr) for addr in recipients],
            subject=f"Akki early access — new request from {app_row['organisation']}",
            plain_text_content=Content("text/plain",
                f"New Akki early-access request.\n\n"
                f"name: {app_row['name']}\n"
                f"email: {app_row['email']}\n"
                f"organisation: {app_row['organisation']}\n"
                f"role: {app_row['role']}\n"
                f"use_case: {app_row['use_case']}\n"
                f"referral_source: {app_row.get('referral_source') or ''}\n"
                f"id: {app_row['id']}\n"),
        )
        resp = SendGridAPIClient(api_key).send(mail)
        log.info("cohort_application_notify_sent: %s", {
            "id": app_row["id"], "status": resp.status_code,
            "recipient_count": len(recipients),
        })
    except Exception as e:  # noqa: BLE001
        log.error("cohort_application_notify_failed: %s", {
            "id": app_row["id"], "error": str(e)[:200],
            "recipient_count": len(recipients),
        })


@router.post("/applications", status_code=200)
async def submit_application(
    body: CohortApplicationIn, background: BackgroundTasks,
    _rl: None = Depends(rate_limit("cohort_apply")),
) -> dict:
    cutoff = (_now() - timedelta(hours=24)).isoformat()
    existing = await db.cohort_applications.find_one(
        {"email": body.email.lower(), "created_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "created_at": 1, "status": 1},
    )
    if existing:
        return {**existing, "deduplicated": True}
    row = {
        "id": str(uuid.uuid4()),
        "name": body.name.strip(),
        "email": body.email.lower(),
        "organisation": body.organisation.strip(),
        "role": body.role.strip(),
        "use_case": body.use_case.strip(),
        "referral_source": (body.referral_source or "").strip() or None,
        "status": "received",
        "created_at": _now().isoformat(),
        # Held 2026-02 dispatch 11; rewritten Sprint M.5 (2026-02) —
        # "early access" framing per user directive. No commitment
        # language; ≤80 words, voice-clean.
        "applicant_confirmation_body": (
            "Thank you for requesting access to Akki. We have your "
            "request on file and read every one personally. Akki is "
            "in early access; we will share the offer with you before "
            "launch."
        ),
    }
    await db.cohort_applications.insert_one(dict(row))
    background.add_task(_notify_founder, row)
    # Phase P4.A (2026-02) — receipt email to the applicant. Gated by
    # COHORT_EMAILS_ENABLED (default false). When false, logs the
    # would-have-sent line and returns flag_off.
    from services.cohort_email import send_receipt as _send_receipt
    background.add_task(_send_receipt, to_email=row["email"], first_name=row["name"])
    return {"id": row["id"], "created_at": row["created_at"],
            "status": row["status"], "deduplicated": False}
