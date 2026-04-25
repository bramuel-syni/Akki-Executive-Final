"""Shared core for AKKI backend: db, config, helpers, and FastAPI dependencies.

Both server.py and routers/* import from here. Keeping this module narrow —
no business logic, only infra + reusable auth/context dependencies.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response
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


# -----------------------------------------------------------------------------
# Password hashing + cookie helpers (moved from server.py for re-use in routers)
# -----------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        "access_token", access, httponly=True, secure=True, samesite="none",
        max_age=ACCESS_TOKEN_TTL_MIN * 60, path="/",
    )
    response.set_cookie(
        "refresh_token", refresh, httponly=True, secure=True, samesite="none",
        max_age=REFRESH_TOKEN_TTL_DAYS * 86400, path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def sanitize_account(a: Dict[str, Any]) -> Dict[str, Any]:
    out = {
        "id": a["id"],
        "email": a["email"],
        "name": a.get("name", ""),
        "declared_role": a.get("declared_role", "undeclared"),
        "mfa_enabled": bool(a.get("mfa_enabled", False)),
        "is_superadmin": bool(a.get("is_superadmin", False)),
        "plan": a.get("plan") or "free",
        "subscription_status": a.get("subscription_status"),
        "default_context_id": a.get("default_context_id"),
        "preferences": a.get("preferences") or {},
        "created_at": a.get("created_at"),
    }
    # Surface sandbox markers only when present — non-sandbox accounts stay
    # lean. Lets the frontend key off account.is_sandbox if it wants to.
    if a.get("is_sandbox"):
        out["is_sandbox"] = True
        if a.get("sandbox_session_id"):
            out["sandbox_session_id"] = a["sandbox_session_id"]
    return out


def sanitize_context(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": c["id"],
        "name": c["name"],
        "type": c.get("type", "executive_personal"),
        "industry": c.get("industry"),
        "jurisdiction": c.get("jurisdiction"),
        "sector": c.get("sector"),
        "sponsoring_org_id": c.get("sponsoring_org_id"),
        "owner_account_id": c.get("owner_account_id"),
        "status": c.get("status", "active"),
        "progress_state": c.get("progress_state", {"onboarding_step": 0}),
        "committees": c.get("committees") or [],
        "sandbox_metadata": c.get("sandbox_metadata"),
        "created_at": c.get("created_at"),
    }


async def provision_default_context(account: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Create the account's first personal context (executive_personal by default)."""
    ctx_id = str(uuid.uuid4())
    _now_iso = iso(now())
    ctx_doc = {
        "id": ctx_id,
        "name": name,
        "type": "executive_personal",  # refined at onboarding (M2)
        "industry": None,
        "jurisdiction": None,
        "sector": None,
        "sponsoring_org_id": None,
        "owner_account_id": account["id"],
        "status": "active",
        "progress_state": {"onboarding_step": 0},
        "created_at": _now_iso,
    }
    await db.contexts.insert_one(ctx_doc)
    await db.memberships.insert_one(
        {
            "id": str(uuid.uuid4()),
            "account_id": account["id"],
            "context_id": ctx_id,
            "role": "executive",  # refined at onboarding
            "sub_role": "admin",
            "provisioning": "personal",
            "data_ownership": "account",
            "status": "active",
            "created_at": _now_iso,
        }
    )
    await db.accounts.update_one(
        {"id": account["id"]}, {"$set": {"default_context_id": ctx_id}}
    )
    await write_audit(ctx_id, account["id"], "context.created", "context", ctx_id, {"name": name})
    ctx_doc.pop("_id", None)
    return ctx_doc
