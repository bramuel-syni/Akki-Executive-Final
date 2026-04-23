"""Shared core for AKKI backend: db, config, helpers, and FastAPI dependencies.

Both server.py and routers/* import from here. Keeping this module narrow —
no business logic, only infra + reusable auth/context dependencies.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
ACCESS_TOKEN_TTL_MIN = 60 * 8  # 8h executive session
REFRESH_TOKEN_TTL_DAYS = 7
APP_NAME = os.environ.get("APP_NAME", "AKKI Sandbox")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


# -----------------------------------------------------------------------------
# Time helpers
# -----------------------------------------------------------------------------
def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime) -> str:
    return d.isoformat()


# -----------------------------------------------------------------------------
# Audit log
# -----------------------------------------------------------------------------
async def write_audit(
    context_id: Optional[str],
    account_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    await db.audit_log.insert_one(
        {
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "account_id": account_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "created_at": iso(now()),
        }
    )


# -----------------------------------------------------------------------------
# Auth dependencies
# -----------------------------------------------------------------------------
async def get_current_account(request: Request) -> Dict[str, Any]:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    account = await db.accounts.find_one({"id": payload["sub"]}, {"_id": 0})
    if not account:
        raise HTTPException(status_code=401, detail="Account not found")
    return account


def require_context_membership(owner_only: bool = False):
    """Dependency: validates current account has active membership in context_id."""
    async def _dep(
        context_id: str,
        current: Dict[str, Any] = Depends(get_current_account),
    ) -> Dict[str, Any]:
        ctx = await db.contexts.find_one({"id": context_id}, {"_id": 0})
        if not ctx:
            raise HTTPException(status_code=404, detail="Context not found")
        membership = await db.memberships.find_one(
            {"context_id": context_id, "account_id": current["id"], "status": "active"},
            {"_id": 0},
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this context")
        if owner_only:
            is_owner = ctx.get("owner_account_id") == current["id"]
            if not is_owner and membership.get("sub_role") != "admin":
                raise HTTPException(status_code=403, detail="Owner privilege required")
        return {"account": current, "context": ctx, "membership": membership}
    return _dep


# -----------------------------------------------------------------------------
# Cross-domain helpers (used by signals, ask, briefings)
# -----------------------------------------------------------------------------
async def gather_context_object(context_id: str) -> Optional[Dict[str, Any]]:
    return await db.context_objects.find_one(
        {"context_id": context_id, "completed": True},
        {"_id": 0}, sort=[("version", -1)],
    )


def docs_overall_trust(docs: List[Dict[str, Any]]) -> str:
    if not docs:
        return "unrated"
    buckets = [d.get("data_trust", "mixed") for d in docs]
    if "weak" in buckets:
        return "weak"
    if all(b == "trusted" for b in buckets):
        return "trusted"
    return "mixed"


# Grounding helpers used by signals and ask endpoints.
MAX_DOC_CHARS_PER_PROMPT = 40_000
MAX_DOCS_PER_PROMPT = 10


async def gather_documents_for_grounding(context_id: str) -> List[Dict[str, Any]]:
    docs = await db.documents.find(
        {"context_id": context_id, "status": {"$in": ["extracted"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(MAX_DOCS_PER_PROMPT)
    return docs


def docs_as_grounding_block(docs: List[Dict[str, Any]]) -> str:
    budget = MAX_DOC_CHARS_PER_PROMPT
    parts: List[str] = []
    for d in docs:
        if budget <= 500:
            break
        text = (d.get("extracted_text") or "")[: max(800, budget // max(1, len(docs)))]
        trust = d.get("data_trust", "mixed")
        parts.append(
            f"----\n[doc:{d['id']}] name: {d.get('name')} · trust: {trust}\n{text}\n"
        )
        budget -= len(text) + 200
    if not parts:
        return "[No extracted documents in this context yet.]"
    return "\n".join(parts)


# JWT token creators — auth-only helpers (kept in core so auth endpoints can
# stay alongside the rest of the auth family in server.py without duplication).
def create_access_token(account_id: str, email: str) -> str:
    return jwt.encode(
        {
            "sub": account_id, "email": email, "type": "access",
            "exp": now() + timedelta(minutes=ACCESS_TOKEN_TTL_MIN),
            "iat": now(),
        },
        JWT_SECRET, algorithm=JWT_ALGO,
    )


def create_refresh_token(account_id: str) -> str:
    return jwt.encode(
        {
            "sub": account_id, "type": "refresh",
            "exp": now() + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
            "iat": now(),
        },
        JWT_SECRET, algorithm=JWT_ALGO,
    )
