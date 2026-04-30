"""Early access registration — public form intake.

Endpoints:
  POST /api/early-access/register       public, rate-limited per IP (5/hour)
  GET  /api/early-access/registrations  superadmin-only, paginated

Dedupes on lower-cased email — first registration's `created_at` is
preserved across subsequent updates so we can measure first-touch
accurately.

Rate limit is in-memory and per-process. For multi-replica deploys,
replace `_recent` with a Mongo-backed counter or front the API with an
edge rate limiter.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from core import db, get_current_account, iso, now

logger = logging.getLogger("akki.early_access")

router = APIRouter(prefix="/api/early-access", tags=["early-access"])

# ---------------------------------------------------------------------------
# In-memory per-IP rate limit. 5 requests / hour.
# ---------------------------------------------------------------------------
_RATE_WINDOW_S = 3600
_RATE_LIMIT = 5
_recent: Dict[str, Deque[float]] = defaultdict(deque)


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP is below the limit; False if exceeded."""
    now_ts = time.time()
    bucket = _recent[ip]
    while bucket and now_ts - bucket[0] > _RATE_WINDOW_S:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT:
        return False
    bucket.append(now_ts)
    return True


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


Role = Literal["executive", "ned", "chair", "other"]


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: Optional[str] = Field(default=None, max_length=200)
    company: Optional[str] = Field(default=None, max_length=200)
    role: Optional[Role] = None
    board_count: Optional[int] = Field(default=None, ge=0, le=50)
    message: Optional[str] = Field(default=None, max_length=2000)


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request) -> Dict[str, Any]:
    ip = _client_ip(request)
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again in an hour.",
        )

    email = body.email.lower().strip()
    user_agent = (request.headers.get("user-agent") or "")[:300]
    ip_hash = _hash_ip(ip)
    created_at = iso(now())

    update_fields: Dict[str, Any] = {
        "email": email,
        "full_name": (body.full_name or "").strip() or None,
        "company": (body.company or "").strip() or None,
        "role": body.role,
        "board_count": body.board_count,
        "message": (body.message or "").strip() or None,
        "ip_hash": ip_hash,
        "user_agent": user_agent,
        "updated_at": created_at,
    }

    existing = await db.early_access_registrations.find_one(
        {"email": email}, {"_id": 0, "id": 1, "created_at": 1},
    )
    if existing:
        # Preserve the original created_at; update everything else.
        await db.early_access_registrations.update_one(
            {"email": email},
            {"$set": update_fields},
        )
    else:
        update_fields["id"] = str(uuid.uuid4())
        update_fields["created_at"] = created_at
        await db.early_access_registrations.insert_one(update_fields)
        logger.info("Early-access registration: %s (role=%s)", email, body.role)

    return {"ok": True}


@router.get("/registrations")
async def list_registrations(
    limit: int = 50,
    offset: int = 0,
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    total = await db.early_access_registrations.count_documents({})
    cursor = (
        db.early_access_registrations
        .find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )
    items = await cursor.to_list(limit)
    return {"total": total, "limit": limit, "offset": offset, "items": items}
