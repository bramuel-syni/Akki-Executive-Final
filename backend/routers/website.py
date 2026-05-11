"""Phase I1 — Pre-login website endpoints (May 2026).

Endpoints
---------
- POST /api/website/early-access — applies to the founding cohort.
- POST /api/website/contact      — generic contact form submission.

Both persist to a small collection + send a confirmation to the
applicant (when Resend has a verified domain) + a notification to
the operator email in `EARLY_ACCESS_NOTIFY_EMAIL` /
`CONTACT_NOTIFY_EMAIL` env vars.

Privacy
-------
- Truncated IP hash (SHA-256 first 16 chars) stored — never raw IP.
- User agent stored verbatim for diagnostics.
- No third-party tracking on this endpoint.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import db

router = APIRouter(prefix="/api/website", tags=["website"])
logger = logging.getLogger("akki.website")


def _ip_hash(request: Request) -> str:
    """SHA-256 of the first IP in X-Forwarded-For, truncated to 16 chars.
    Truncation removes correlation potential while retaining duplicate-
    detection utility within a single ops window."""
    fwd = request.headers.get("x-forwarded-for") or ""
    raw = (fwd.split(",")[0].strip()
           if fwd else (request.client.host if request.client else "0.0.0.0"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class EarlyAccessApplication(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    work_email: EmailStr
    company: str = Field(..., min_length=1, max_length=160)
    role_title: str = Field(..., min_length=1, max_length=160)
    role_type: str = Field(..., min_length=1, max_length=40)
    linkedin_url: Optional[str] = Field(None, max_length=300)
    valuable_text: Optional[str] = Field(None, max_length=2000)
    cohort_understood: bool


@router.post("/early-access")
async def submit_early_access(body: EarlyAccessApplication, request: Request) -> Dict[str, Any]:
    """Record an application + notify ops + acknowledge applicant."""
    if not body.cohort_understood:
        raise HTTPException(
            status_code=400,
            detail={"code": "CONSENT_REQUIRED",
                    "message": "Please confirm you understand the cohort terms."},
        )

    submission_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "id": submission_id,
        "type": "early_access",
        "first_name": body.first_name.strip(),
        "last_name": body.last_name.strip(),
        "work_email": body.work_email.lower().strip(),
        "company": body.company.strip(),
        "role_title": body.role_title.strip(),
        "role_type": body.role_type.strip(),
        "linkedin_url": (body.linkedin_url or "").strip() or None,
        "valuable_text": (body.valuable_text or "").strip() or None,
        "cohort_understood": True,
        "ip_hash": _ip_hash(request),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "created_at": now_iso,
        "status": "new",
    }
    await db.early_access_applications.insert_one(row)
    logger.info("[early-access] new applicant id=%s email=%s company=%s role=%s",
                submission_id, row["work_email"], row["company"], row["role_type"])

    # Best-effort email sends; both calls are async-safe and never raise.
    try:
        from email_service import send_email
        notify_to = os.environ.get("EARLY_ACCESS_NOTIFY_EMAIL")
        if notify_to:
            await send_email(
                to=[notify_to],
                subject=f"[Akki cohort] New application — {row['first_name']} {row['last_name']} ({row['company']})",
                text=(
                    f"New founding-cohort application.\n\n"
                    f"Name: {row['first_name']} {row['last_name']}\n"
                    f"Work email: {row['work_email']}\n"
                    f"Company: {row['company']}\n"
                    f"Role: {row['role_title']} ({row['role_type']})\n"
                    f"LinkedIn: {row['linkedin_url'] or '—'}\n\n"
                    f"What would Akki need to do for them to call it valuable?\n"
                    f"  {row['valuable_text'] or '—'}\n\n"
                    f"Submission id: {submission_id}\n"
                    f"Received at: {now_iso}\n"
                ),
            )
        await send_email(
            to=[row["work_email"]],
            subject="Thank you — your Akki founding-cohort application",
            text=(
                f"Hello {row['first_name']},\n\n"
                f"Thank you for applying to the Akki founding cohort. We've received "
                f"your application (ref {submission_id[:8]}) and will be in touch personally "
                f"within a few business days.\n\n"
                f"The cohort is small and we read every application. If you'd like to add "
                f"anything before we get back to you, simply reply to this email.\n\n"
                f"— The Akki team"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[early-access] email send failed for %s — %s",
                       submission_id, exc)

    return {"ok": True, "submission_id": submission_id}


class ContactSubmission(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    work_email: EmailStr
    company: Optional[str] = Field(None, max_length=160)
    message: str = Field(..., min_length=1, max_length=4000)


@router.post("/contact")
async def submit_contact(body: ContactSubmission, request: Request) -> Dict[str, Any]:
    submission_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "id": submission_id,
        "type": "contact",
        "name": body.name.strip(),
        "work_email": body.work_email.lower().strip(),
        "company": (body.company or "").strip() or None,
        "message": body.message.strip(),
        "ip_hash": _ip_hash(request),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "created_at": now_iso,
        "status": "new",
    }
    await db.early_access_applications.insert_one(row)
    logger.info("[contact] new submission id=%s from=%s",
                submission_id, row["work_email"])

    try:
        from email_service import send_email
        notify_to = (os.environ.get("CONTACT_NOTIFY_EMAIL")
                     or os.environ.get("EARLY_ACCESS_NOTIFY_EMAIL"))
        if notify_to:
            await send_email(
                to=[notify_to],
                subject=f"[Akki contact] {row['name']} — {row['company'] or 'no company'}",
                text=(
                    f"New contact form submission.\n\n"
                    f"Name: {row['name']}\n"
                    f"Email: {row['work_email']}\n"
                    f"Company: {row['company'] or '—'}\n\n"
                    f"Message:\n{row['message']}\n\n"
                    f"Submission id: {submission_id}\n"
                    f"Received at: {now_iso}\n"
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[contact] notify failed: %s", exc)

    return {"ok": True, "submission_id": submission_id}
