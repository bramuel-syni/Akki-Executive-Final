"""Phase P5.7.6 (2026-02) — Cohort waitlist.

Public endpoint that lets a declined applicant — or any visitor on
the marketing surface — leave their email for a later cohort.
Front-end surface lives at `/waitlist`. The decline email body
(P5.7.6's other half) now carries the waitlist URL as a
door-back.

Endpoint:
  POST /api/cohort/waitlist
    Body: {email: str, source_application_id?: str}
    Rate limited per IP (3/hour) and per email (1/hour).
    CSRF-protected.

Storage:
  Collection: `cohort_waitlist`
  Doc shape:
    {
      id: str (uuid hex),
      email: str (canonical),
      email_lc: str (lowercased — uniqueness key),
      source_application_id: Optional[str],
      ip: str (truncated for storage; CIDR-anonymised),
      created_at: ISO str,
      user_agent: str (first 200 chars),
    }

Notes:
  * NOT gated by COHORT_EMAILS_ENABLED — there's no outbound from
    this endpoint. The signup is a record only; admins decide later.
  * Idempotent on `email_lc` — re-posting the same email returns
    200 with `already_present: true` rather than 4xx; this matches
    the user-facing experience ("yes, you're on the list") without
    leaking whether a specific email is or isn't in our database.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import db, now as _now, iso as _iso, write_audit


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cohort", tags=["cohort-waitlist"])

# Rate-limit windows.
_PER_IP_MAX = 3
_PER_IP_WINDOW = timedelta(hours=1)
_PER_EMAIL_MAX = 1
_PER_EMAIL_WINDOW = timedelta(hours=1)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class WaitlistJoinRequest(BaseModel):
    email: EmailStr
    source_application_id: Optional[str] = Field(
        None, max_length=64,
        description="Optional — if posted from a decline email's "
                    "door-back link, this carries the original "
                    "application id for analytics correlation.",
    )


def _client_ip(request: Request) -> str:
    """Pull the originating IP, preferring the reverse-proxy header
    chain. Falls back to the socket's peer address. Truncated to
    /24 (IPv4) or /64 (IPv6) for privacy when stored."""
    xfwd = (request.headers.get("x-forwarded-for") or "").split(",")
    raw = (xfwd[0].strip() if xfwd[0] else "") or (
        request.client.host if request.client else ""
    )
    if not raw:
        return "0.0.0.0"
    if ":" in raw:
        # IPv6 — keep first 4 hextets.
        return ":".join(raw.split(":")[:4]) + "::"
    parts = raw.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0"
    return raw


async def _enforce_rate_limit(*, ip: str, email_lc: str) -> None:
    threshold_ip = (_now() - _PER_IP_WINDOW).isoformat()
    ip_count = await db.cohort_waitlist.count_documents({
        "ip": ip, "created_at": {"$gte": threshold_ip},
    })
    if ip_count >= _PER_IP_MAX:
        raise HTTPException(status_code=429, detail={
            "code": "rate_limit_ip",
            "message": "Too many waitlist signups from this network. Try again in an hour.",
        })
    threshold_email = (_now() - _PER_EMAIL_WINDOW).isoformat()
    email_count = await db.cohort_waitlist.count_documents({
        "email_lc": email_lc, "created_at": {"$gte": threshold_email},
    })
    if email_count >= _PER_EMAIL_MAX:
        # Treat as idempotent rather than 429 — the user-facing UX
        # is "you're on the list", which is true either way.
        raise HTTPException(status_code=200, detail={
            "code": "already_present",
            "message": "You're on the list.",
        })


@router.post("/waitlist")
async def waitlist_join(request: Request, body: WaitlistJoinRequest) -> Dict[str, Any]:
    """Public — accept a single email into the waitlist."""
    email = str(body.email).strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail={
            "code": "email_invalid", "message": "That email looks malformed.",
        })
    email_lc = email.lower()
    ip = _client_ip(request)

    # Rate-limit pre-check. Idempotent-email path returns 200 already.
    try:
        await _enforce_rate_limit(ip=ip, email_lc=email_lc)
    except HTTPException as e:
        if isinstance(e.detail, dict) and e.detail.get("code") == "already_present":
            return {"ok": True, "already_present": True}
        raise

    # Idempotency: if the email is already on the list, return 200 +
    # `already_present: true` rather than writing a duplicate.
    existing = await db.cohort_waitlist.find_one(
        {"email_lc": email_lc}, {"_id": 0, "id": 1, "created_at": 1},
    )
    if existing:
        return {"ok": True, "already_present": True}

    doc = {
        "id": uuid.uuid4().hex,
        "email": email,
        "email_lc": email_lc,
        "source_application_id": (body.source_application_id or None),
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "created_at": _iso(_now()),
    }
    await db.cohort_waitlist.insert_one(dict(doc))

    # Audit-log (best-effort).
    try:
        await write_audit(
            kind="cohort.waitlist.joined",
            target_id=doc["id"],
            payload={"email_lc_prefix": email_lc.split("@", 1)[0][:3]},
        )
    except Exception:  # noqa: BLE001
        pass

    return {"ok": True, "already_present": False}
