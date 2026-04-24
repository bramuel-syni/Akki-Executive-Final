"""AKKI Sandbox — M0 Foundations backend (v3.0 BRD).

Implements account + context (NED/Executive) model with:
  - JWT auth (bcrypt) + MFA TOTP
  - Context-primary isolation (not tenant-primary)
  - Accounts with declared_role (ned / executive / dual / undeclared)
  - Organisations (for sponsored seats)
  - Memberships with role + data_ownership + provisioning
  - Consent decisions (stub collection, immutable)
  - Invitations (context-scoped)
  - Audit log, telemetry events, data export
  - LLM proxy scaffolding (mock, with Synisense shielding contract)
"""
from __future__ import annotations

from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import io  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import secrets  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from typing import Any, Dict, List, Literal, Optional  # noqa: E402

import bcrypt  # noqa: E402
import jwt  # noqa: E402
import pyotp  # noqa: E402
import qrcode  # noqa: E402
from fastapi import (  # noqa: E402
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from pydantic import BaseModel, EmailStr, Field  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from llm_service import call_llm as llm_call_llm, parse_json_response  # noqa: E402
from briefings_service import build_briefing_prompt, render_pdf, render_docx  # noqa: E402
from documents_service import (  # noqa: E402
    ACCEPT_EXT, MAX_BYTES, virus_scan_stub, save_to_storage, read_from_storage,
    delete_from_storage, extract_text, make_preview,
)
from core import (  # noqa: E402
    db, now as _now, iso as _iso, write_audit,
    get_current_account, require_context_membership,
    gather_context_object as _gather_context_object,
    docs_overall_trust as _docs_overall_trust,
    create_access_token, create_refresh_token,
    JWT_SECRET, JWT_ALGO, ACCESS_TOKEN_TTL_MIN, REFRESH_TOKEN_TTL_DAYS, APP_NAME,
)
from routers import briefings as briefings_router  # noqa: E402
from routers import learn as learn_router  # noqa: E402
from routers import committees as committees_router  # noqa: E402
from routers import simulate as simulate_router  # noqa: E402
from routers import comments as comments_router  # noqa: E402
from routers import signals_ask as signals_ask_router  # noqa: E402
from routers import lens as lens_router  # noqa: E402
from routers import pipeline as pipeline_router  # noqa: E402
from routers import audit as audit_router  # noqa: E402
from routers import synisense as synisense_router  # noqa: E402

# -----------------------------------------------------------------------------
# Config — most constants come from core.py via the import block above.
# -----------------------------------------------------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# db + logger come from core.py
client = None  # legacy placeholder; core.client is the actual connection

logger = logging.getLogger("akki")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# -----------------------------------------------------------------------------
# Types
# -----------------------------------------------------------------------------
AccountRole = Literal["ned", "executive", "dual", "undeclared"]
ContextType = Literal[
    "ned_personal", "ned_sponsored", "executive_personal", "executive_enterprise"
]
MembershipRole = Literal["ned", "executive", "reportee"]
DataOwnership = Literal["account", "organisation"]
Provisioning = Literal["personal", "sponsored"]


# -----------------------------------------------------------------------------
# Helpers (auth-scoped — shared helpers live in core.py)
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
    return {
        "id": a["id"],
        "email": a["email"],
        "name": a.get("name", ""),
        "declared_role": a.get("declared_role", "undeclared"),
        "mfa_enabled": bool(a.get("mfa_enabled", False)),
        "default_context_id": a.get("default_context_id"),
        "preferences": a.get("preferences") or {},
        "created_at": a.get("created_at"),
    }


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
        "created_at": c.get("created_at"),
    }


# -----------------------------------------------------------------------------
# Pydantic schemas
# -----------------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    context_name: Optional[str] = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ContextCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: ContextType = "executive_personal"
    industry: Optional[str] = None
    jurisdiction: Optional[str] = None
    sector: Optional[str] = None


class ContextRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class DeclareRoleIn(BaseModel):
    declared_role: AccountRole


class ContextObjectIn(BaseModel):
    # Basics (set at start of onboarding)
    industry: Optional[str] = None
    sector: Optional[str] = None
    jurisdiction: Optional[str] = None
    role: Optional[MembershipRole] = None  # audit-role variant (ned or executive)
    # Free-form answers (7 questions); schema differs by role
    answers: Dict[str, Any] = Field(default_factory=dict)
    # Progress
    step: int = 0
    completed: bool = False


class AccountUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    declared_role: Optional[AccountRole] = None
    preferences: Optional[Dict[str, Any]] = None


class SetDefaultContextIn(BaseModel):
    context_id: str


class InvitationIn(BaseModel):
    email: EmailStr
    role: MembershipRole = "executive"
    sub_role: Optional[str] = None


class MFAVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class LLMProbeIn(BaseModel):
    module: str
    query: str


class TelemetryEventIn(BaseModel):
    event_name: str
    event_version: str = "1.0"
    context_id: Optional[str] = None
    session_id: Optional[str] = None
    surface: Optional[str] = None  # home / workspace / highlights / ask / learn / settings
    properties: Dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# App & router
# -----------------------------------------------------------------------------
app = FastAPI(title=APP_NAME)
api = APIRouter(prefix="/api")


# -----------------------------------------------------------------------------
# Context provisioning
# -----------------------------------------------------------------------------
async def provision_default_context(account: Dict[str, Any], name: str) -> Dict[str, Any]:
    """Create the account's first personal context (executive_personal by default)."""
    ctx_id = str(uuid.uuid4())
    now = _iso(_now())
    ctx_type: ContextType = "executive_personal"  # refined at onboarding (M2)
    ctx_doc = {
        "id": ctx_id,
        "name": name,
        "type": ctx_type,
        "industry": None,
        "jurisdiction": None,
        "sector": None,
        "sponsoring_org_id": None,
        "owner_account_id": account["id"],
        "status": "active",
        "progress_state": {"onboarding_step": 0},
        "created_at": now,
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
            "created_at": now,
        }
    )
    await db.accounts.update_one(
        {"id": account["id"]}, {"$set": {"default_context_id": ctx_id}}
    )
    await write_audit(ctx_id, account["id"], "context.created", "context", ctx_id, {"name": name})
    return ctx_doc


# -----------------------------------------------------------------------------
# Auth endpoints
# -----------------------------------------------------------------------------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower().strip()
    existing = await db.accounts.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    account_id = str(uuid.uuid4())
    now = _iso(_now())
    account_doc = {
        "id": account_id,
        "email": email,
        "name": body.name.strip(),
        "declared_role": "undeclared",
        "password_hash": hash_password(body.password),
        "mfa_enabled": False,
        "mfa_secret": None,
        "default_context_id": None,
        "created_at": now,
    }
    await db.accounts.insert_one(account_doc)

    context_name = (body.context_name or f"{body.name.split()[0]}'s Context").strip()
    ctx = await provision_default_context(account_doc, context_name)

    access = create_access_token(account_id, email)
    refresh = create_refresh_token(account_id)
    set_auth_cookies(response, access, refresh)

    refreshed = await db.accounts.find_one({"id": account_id}, {"_id": 0})
    return {
        "account": sanitize_account(refreshed),
        "contexts": [sanitize_context(ctx)],
        "access_token": access,
    }


@api.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower().strip()
    # Key rate-limit on email only. `request.client.host` is the ingress proxy in
    # our deploy and is not stable enough to use as part of the identifier.
    ident = email

    attempts_doc = await db.login_attempts.find_one({"identifier": ident}, {"_id": 0})
    if attempts_doc and attempts_doc.get("locked_until"):
        locked_until = datetime.fromisoformat(attempts_doc["locked_until"])
        if locked_until > _now():
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again shortly.")

    account = await db.accounts.find_one({"email": email}, {"_id": 0})
    if not account or not verify_password(body.password, account["password_hash"]):
        count = (attempts_doc or {}).get("count", 0) + 1
        update: Dict[str, Any] = {"identifier": ident, "count": count, "last_at": _iso(_now())}
        if count >= 5:
            update["locked_until"] = _iso(_now() + timedelta(minutes=15))
            update["count"] = 0
        await db.login_attempts.update_one({"identifier": ident}, {"$set": update}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_one({"identifier": ident})

    access = create_access_token(account["id"], email)
    refresh = create_refresh_token(account["id"])
    set_auth_cookies(response, access, refresh)

    memberships = await db.memberships.find(
        {"account_id": account["id"], "status": "active"}, {"_id": 0}
    ).to_list(200)
    context_ids = [m["context_id"] for m in memberships]
    contexts = await db.contexts.find({"id": {"$in": context_ids}}, {"_id": 0}).to_list(200)

    return {
        "account": sanitize_account(account),
        "contexts": [sanitize_context(c) for c in contexts],
        "access_token": access,
    }


@api.post("/auth/logout")
async def logout(response: Response, _: Dict[str, Any] = Depends(get_current_account)):
    clear_auth_cookies(response)
    return {"ok": True}


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    account = await db.accounts.find_one({"id": payload["sub"]}, {"_id": 0})
    if not account:
        raise HTTPException(status_code=401, detail="Account not found")
    new_access = create_access_token(account["id"], account["email"])
    new_refresh = create_refresh_token(account["id"])
    set_auth_cookies(response, new_access, new_refresh)
    return {"ok": True}


@api.get("/auth/me")
async def me(current: Dict[str, Any] = Depends(get_current_account)):
    memberships = await db.memberships.find(
        {"account_id": current["id"], "status": "active"}, {"_id": 0}
    ).to_list(200)
    context_ids = [m["context_id"] for m in memberships]
    contexts = await db.contexts.find({"id": {"$in": context_ids}}, {"_id": 0}).to_list(200)
    mem_by_ctx = {m["context_id"]: m for m in memberships}
    decorated: List[Dict[str, Any]] = []
    for c in contexts:
        d = sanitize_context(c)
        m = mem_by_ctx.get(c["id"], {})
        d["my_role"] = m.get("role")
        d["my_sub_role"] = m.get("sub_role")
        d["provisioning"] = m.get("provisioning", "personal")
        d["data_ownership"] = m.get("data_ownership", "account")
        decorated.append(d)
    return {"account": sanitize_account(current), "contexts": decorated}


@api.post("/auth/declare-role")
async def declare_role(
    body: DeclareRoleIn, current: Dict[str, Any] = Depends(get_current_account)
):
    """Account-level role declaration (NED / Executive / Dual). Refined during M2 onboarding."""
    await db.accounts.update_one(
        {"id": current["id"]}, {"$set": {"declared_role": body.declared_role}}
    )
    await write_audit(None, current["id"], "account.role_declared", "account", current["id"],
                      {"declared_role": body.declared_role})
    refreshed = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return {"account": sanitize_account(refreshed)}


@api.patch("/accounts/me")
async def update_account(
    body: AccountUpdateIn, current: Dict[str, Any] = Depends(get_current_account)
):
    updates: Dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.declared_role is not None:
        updates["declared_role"] = body.declared_role
    if body.preferences is not None:
        # merge, don't clobber
        merged = {**(current.get("preferences") or {}), **body.preferences}
        updates["preferences"] = merged
    if not updates:
        return {"account": sanitize_account(current)}
    await db.accounts.update_one({"id": current["id"]}, {"$set": updates})
    await write_audit(None, current["id"], "account.updated", "account", current["id"], updates)
    refreshed = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return {"account": sanitize_account(refreshed)}


@api.post("/accounts/me/default-context")
async def set_default_context(
    body: SetDefaultContextIn, current: Dict[str, Any] = Depends(get_current_account)
):
    mem = await db.memberships.find_one(
        {"context_id": body.context_id, "account_id": current["id"], "status": "active"}
    )
    if not mem:
        raise HTTPException(status_code=404, detail="You are not a member of that context")
    await db.accounts.update_one(
        {"id": current["id"]}, {"$set": {"default_context_id": body.context_id}}
    )
    refreshed = await db.accounts.find_one({"id": current["id"]}, {"_id": 0})
    return {"account": sanitize_account(refreshed)}


@api.post("/contexts/{context_id}/leave")
async def leave_context(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    ctx_id = ctx["context"]["id"]
    account_id = ctx["account"]["id"]
    if ctx["context"]["owner_account_id"] == account_id:
        raise HTTPException(status_code=400, detail="Context owner cannot leave — archive the context instead.")
    res = await db.memberships.update_one(
        {"context_id": ctx_id, "account_id": account_id, "status": "active"},
        {"$set": {"status": "left", "left_at": _iso(_now())}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Membership not found")
    # If user's default context was this one, clear it
    if ctx["account"].get("default_context_id") == ctx_id:
        await db.accounts.update_one({"id": account_id}, {"$set": {"default_context_id": None}})
    await write_audit(ctx_id, account_id, "member.left", "account", account_id, {})
    return {"ok": True}


# Privacy / consent decisions (stub — populated during sponsored-invite consent in M4)
@api.get("/accounts/me/consent-decisions")
async def list_consent_decisions(current: Dict[str, Any] = Depends(get_current_account)):
    decisions = await db.consent_decisions.find(
        {"account_id": current["id"]}, {"_id": 0}
    ).sort("decided_at", -1).to_list(200)
    return decisions


# -----------------------------------------------------------------------------
# Industry presets (hardcoded reference data for M2 onboarding)
# -----------------------------------------------------------------------------
INDUSTRY_PRESETS = [
    {"id": "banking", "label": "Banking & Capital Markets", "sectors": ["Retail", "Corporate", "Investment", "Private"]},
    {"id": "insurance", "label": "Insurance", "sectors": ["Life", "General", "Health", "Reinsurance"]},
    {"id": "retail", "label": "Retail & Consumer", "sectors": ["Grocery", "Apparel", "Electronics", "Multi-category"]},
    {"id": "fintech", "label": "Fintech", "sectors": ["Payments", "Lending", "Wealth", "Infra"]},
    {"id": "telco", "label": "Telecommunications", "sectors": ["Mobile", "Broadband", "Enterprise"]},
    {"id": "energy", "label": "Energy & Utilities", "sectors": ["Oil & Gas", "Power", "Renewables", "Water"]},
    {"id": "healthcare", "label": "Healthcare & Pharma", "sectors": ["Provider", "Payor", "Pharma", "Devices"]},
    {"id": "logistics", "label": "Logistics & Transport", "sectors": ["Freight", "Passenger", "Last-mile"]},
    {"id": "mining", "label": "Mining & Resources", "sectors": ["Metals", "Commodities", "Services"]},
    {"id": "agriculture", "label": "Agriculture & Agribusiness", "sectors": ["Primary", "Processing", "Distribution"]},
    {"id": "manufacturing", "label": "Manufacturing", "sectors": ["FMCG", "Industrial", "Automotive"]},
    {"id": "public_sector", "label": "Public Sector / NGO", "sectors": ["Government", "Non-profit", "Multilateral"]},
]

JURISDICTION_PRESETS = [
    "Nigeria", "Kenya", "South Africa", "Ghana", "Egypt", "Morocco", "Ethiopia",
    "Tanzania", "Uganda", "Rwanda", "Pan-African", "Global",
]


@api.get("/presets/industries")
async def list_industries(_: Dict[str, Any] = Depends(get_current_account)):
    return INDUSTRY_PRESETS


@api.get("/presets/jurisdictions")
async def list_jurisdictions(_: Dict[str, Any] = Depends(get_current_account)):
    return JURISDICTION_PRESETS


# -----------------------------------------------------------------------------
# Context Object (versioned)
# -----------------------------------------------------------------------------
@api.get("/contexts/{context_id}/context-object")
async def get_context_object(ctx: Dict[str, Any] = Depends(require_context_membership())):
    latest = await db.context_objects.find_one(
        {"context_id": ctx["context"]["id"]},
        {"_id": 0},
        sort=[("version", -1)],
    )
    return latest  # None if not yet created


@api.post("/contexts/{context_id}/context-object")
async def upsert_context_object(
    body: ContextObjectIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    context_id = ctx["context"]["id"]
    account_id = ctx["account"]["id"]

    latest = await db.context_objects.find_one(
        {"context_id": context_id}, {"_id": 0}, sort=[("version", -1)]
    )
    new_version = (latest["version"] + 1) if latest else 1
    now = _iso(_now())
    doc = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "version": new_version,
        "industry": body.industry,
        "sector": body.sector,
        "jurisdiction": body.jurisdiction,
        "role": body.role,
        "answers": body.answers,
        "step": body.step,
        "completed": body.completed,
        "created_by": account_id,
        "created_at": now,
        "updated_at": now,
    }
    await db.context_objects.insert_one(doc)
    doc.pop("_id", None)

    # Mirror onto context for quick reads
    ctx_updates = {
        "progress_state": {
            "onboarding_step": body.step,
            "onboarding_completed": body.completed,
            "context_object_version": new_version,
        },
    }
    if body.industry:
        ctx_updates["industry"] = body.industry
    if body.jurisdiction:
        ctx_updates["jurisdiction"] = body.jurisdiction
    if body.sector:
        ctx_updates["sector"] = body.sector
    await db.contexts.update_one({"id": context_id}, {"$set": ctx_updates})

    await write_audit(
        context_id, account_id,
        "context_object.saved" if body.completed else "context_object.progress",
        "context_object", doc["id"],
        {"version": new_version, "completed": body.completed, "step": body.step},
    )
    return doc


# -----------------------------------------------------------------------------
# MFA (TOTP)
# -----------------------------------------------------------------------------
@api.post("/auth/mfa/setup")
async def mfa_setup(current: Dict[str, Any] = Depends(get_current_account)):
    secret = pyotp.random_base32()
    otpauth = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current["email"], issuer_name=APP_NAME
    )
    await db.accounts.update_one(
        {"id": current["id"]}, {"$set": {"mfa_secret_pending": secret}}
    )
    img = qrcode.make(otpauth)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    import base64
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"otpauth_url": otpauth, "qr_data_url": data_url, "secret": secret}


@api.post("/auth/mfa/verify")
async def mfa_verify(body: MFAVerifyIn, current: Dict[str, Any] = Depends(get_current_account)):
    pending = current.get("mfa_secret_pending")
    if not pending:
        raise HTTPException(status_code=400, detail="No MFA setup in progress")
    totp = pyotp.TOTP(pending)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"mfa_enabled": True, "mfa_secret": pending}, "$unset": {"mfa_secret_pending": ""}},
    )
    return {"ok": True, "mfa_enabled": True}


@api.post("/auth/mfa/disable")
async def mfa_disable(current: Dict[str, Any] = Depends(get_current_account)):
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"mfa_enabled": False}, "$unset": {"mfa_secret": "", "mfa_secret_pending": ""}},
    )
    return {"ok": True, "mfa_enabled": False}


# -----------------------------------------------------------------------------
# Contexts
# -----------------------------------------------------------------------------
@api.post("/contexts")
async def create_context(body: ContextCreateIn, current: Dict[str, Any] = Depends(get_current_account)):
    ctx_id = str(uuid.uuid4())
    now = _iso(_now())
    ctx_doc = {
        "id": ctx_id,
        "name": body.name.strip(),
        "type": body.type,
        "industry": body.industry,
        "jurisdiction": body.jurisdiction,
        "sector": body.sector,
        "sponsoring_org_id": None,
        "owner_account_id": current["id"],
        "status": "active",
        "progress_state": {"onboarding_step": 0},
        "created_at": now,
    }
    await db.contexts.insert_one(ctx_doc)
    # Derive membership role from context type
    role: MembershipRole = "ned" if body.type.startswith("ned") else "executive"
    await db.memberships.insert_one(
        {
            "id": str(uuid.uuid4()),
            "account_id": current["id"],
            "context_id": ctx_id,
            "role": role,
            "sub_role": "admin",
            "provisioning": "personal",
            "data_ownership": "account",
            "status": "active",
            "created_at": now,
        }
    )
    await write_audit(ctx_id, current["id"], "context.created", "context", ctx_id, {"name": body.name, "type": body.type})
    return sanitize_context(ctx_doc)


@api.get("/contexts/{context_id}")
async def get_context(ctx: Dict[str, Any] = Depends(require_context_membership())):
    out = sanitize_context(ctx["context"])
    out["my_role"] = ctx["membership"].get("role")
    out["my_sub_role"] = ctx["membership"].get("sub_role")
    out["provisioning"] = ctx["membership"].get("provisioning")
    out["data_ownership"] = ctx["membership"].get("data_ownership")
    return out


@api.patch("/contexts/{context_id}")
async def rename_context(
    context_id: str,
    body: ContextRenameIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    await db.contexts.update_one({"id": context_id}, {"$set": {"name": body.name.strip()}})
    await write_audit(context_id, ctx["account"]["id"], "context.renamed", "context", context_id, {"to": body.name})
    c = await db.contexts.find_one({"id": context_id}, {"_id": 0})
    return sanitize_context(c)


@api.delete("/contexts/{context_id}")
async def archive_context(
    context_id: str, ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True))
):
    await db.contexts.update_one({"id": context_id}, {"$set": {"status": "archived", "archived_at": _iso(_now())}})
    await write_audit(context_id, ctx["account"]["id"], "context.archived", "context", context_id, {})
    return {"ok": True, "status": "archived"}


# -----------------------------------------------------------------------------
# Members
# -----------------------------------------------------------------------------
@api.get("/contexts/{context_id}/members")
async def list_members(ctx: Dict[str, Any] = Depends(require_context_membership())):
    context_id = ctx["context"]["id"]
    memberships = await db.memberships.find(
        {"context_id": context_id, "status": "active"}, {"_id": 0}
    ).to_list(500)
    account_ids = [m["account_id"] for m in memberships]
    accounts = await db.accounts.find({"id": {"$in": account_ids}}, {"_id": 0}).to_list(500)
    by_id = {a["id"]: a for a in accounts}
    out = []
    for m in memberships:
        a = by_id.get(m["account_id"])
        if not a:
            continue
        out.append(
            {
                "account_id": a["id"],
                "email": a["email"],
                "name": a.get("name", ""),
                "role": m["role"],
                "sub_role": m.get("sub_role"),
                "provisioning": m.get("provisioning", "personal"),
                "joined_at": m.get("created_at"),
            }
        )
    return out


@api.delete("/contexts/{context_id}/members/{account_id}")
async def remove_member(
    context_id: str,
    account_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    if account_id == ctx["context"]["owner_account_id"]:
        raise HTTPException(status_code=400, detail="Cannot remove the context owner")
    res = await db.memberships.update_one(
        {"context_id": context_id, "account_id": account_id, "status": "active"},
        {"$set": {"status": "removed", "removed_at": _iso(_now())}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    await write_audit(context_id, ctx["account"]["id"], "member.removed", "account", account_id, {})
    return {"ok": True}


# -----------------------------------------------------------------------------
# Invitations (context-scoped)
# -----------------------------------------------------------------------------
@api.post("/contexts/{context_id}/invitations")
async def create_invitation(
    context_id: str,
    body: InvitationIn,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    email = body.email.lower().strip()
    existing_acc = await db.accounts.find_one({"email": email}, {"_id": 0})
    if existing_acc:
        existing_mem = await db.memberships.find_one(
            {"context_id": context_id, "account_id": existing_acc["id"], "status": "active"}
        )
        if existing_mem:
            raise HTTPException(status_code=409, detail="Account is already a member")
    existing_inv = await db.invitations.find_one(
        {"context_id": context_id, "email": email, "status": "pending"}
    )
    if existing_inv:
        raise HTTPException(status_code=409, detail="Invitation already pending for this email")

    token = secrets.token_urlsafe(32)
    inv = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "email": email,
        "role": body.role,
        "sub_role": body.sub_role,
        "token": token,
        "status": "pending",
        "invited_by": ctx["account"]["id"],
        "created_at": _iso(_now()),
        "expires_at": _iso(_now() + timedelta(days=7)),
    }
    await db.invitations.insert_one(inv)

    frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
    accept_url = f"{frontend_url}/invite/{token}" if frontend_url else f"/invite/{token}"
    logger.info(f"[invite-email-stub] to={email} context={ctx['context']['name']} link={accept_url}")

    await write_audit(
        context_id, ctx["account"]["id"], "member.invited", "invitation", inv["id"],
        {"email": email, "role": body.role},
    )
    return {
        "id": inv["id"],
        "email": email,
        "role": body.role,
        "status": "pending",
        "accept_url": accept_url,
        "expires_at": inv["expires_at"],
        "created_at": inv["created_at"],
    }


@api.get("/contexts/{context_id}/invitations")
async def list_invitations(ctx: Dict[str, Any] = Depends(require_context_membership())):
    invs = await db.invitations.find(
        {"context_id": ctx["context"]["id"], "status": "pending"}, {"_id": 0, "token": 0}
    ).to_list(200)
    return invs


@api.delete("/contexts/{context_id}/invitations/{invitation_id}")
async def revoke_invitation(
    context_id: str,
    invitation_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    res = await db.invitations.update_one(
        {"id": invitation_id, "context_id": context_id, "status": "pending"},
        {"$set": {"status": "revoked", "revoked_at": _iso(_now())}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Invitation not found")
    await write_audit(context_id, ctx["account"]["id"], "invitation.revoked", "invitation", invitation_id, {})
    return {"ok": True}


@api.get("/invitations/by-token/{token}")
async def preview_invitation(token: str):
    inv = await db.invitations.find_one({"token": token, "status": "pending"}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found or no longer valid")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < _now():
        raise HTTPException(status_code=410, detail="Invitation expired")
    ctx = await db.contexts.find_one({"id": inv["context_id"]}, {"_id": 0})
    return {
        "email": inv["email"],
        "role": inv["role"],
        "context_name": ctx["name"] if ctx else "Context",
        "context_type": ctx.get("type") if ctx else None,
    }


@api.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str, current: Dict[str, Any] = Depends(get_current_account)
):
    inv = await db.invitations.find_one({"token": token, "status": "pending"}, {"_id": 0})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not valid")
    if inv.get("expires_at") and datetime.fromisoformat(inv["expires_at"]) < _now():
        raise HTTPException(status_code=410, detail="Invitation expired")
    if current["email"].lower() != inv["email"].lower():
        raise HTTPException(
            status_code=403,
            detail=f"This invitation was sent to {inv['email']}. Sign in with that email to accept.",
        )
    existing = await db.memberships.find_one(
        {"context_id": inv["context_id"], "account_id": current["id"], "status": "active"}
    )
    if not existing:
        await db.memberships.insert_one(
            {
                "id": str(uuid.uuid4()),
                "account_id": current["id"],
                "context_id": inv["context_id"],
                "role": inv["role"],
                "sub_role": inv.get("sub_role"),
                "provisioning": "personal",  # sponsored flow handled in M4 with consent
                "data_ownership": "account",
                "status": "active",
                "created_at": _iso(_now()),
            }
        )
    await db.invitations.update_one(
        {"id": inv["id"]}, {"$set": {"status": "accepted", "accepted_at": _iso(_now())}}
    )
    await write_audit(
        inv["context_id"], current["id"], "member.joined", "account", current["id"],
        {"role": inv["role"]},
    )
    ctx = await db.contexts.find_one({"id": inv["context_id"]}, {"_id": 0})
    return {"ok": True, "context": sanitize_context(ctx)}



# -----------------------------------------------------------------------------
# Documents (M3 — upload pipeline)
# -----------------------------------------------------------------------------
def sanitize_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": d["id"],
        "context_id": d["context_id"],
        "name": d.get("name"),
        "description": d.get("description", ""),
        "original_filename": d.get("original_filename"),
        "mime_type": d.get("mime_type"),
        "size_bytes": d.get("size_bytes", 0),
        "status": d.get("status", "uploaded"),
        "preview": d.get("preview", ""),
        "extracted_chars": d.get("extracted_chars", 0),
        "data_trust": d.get("data_trust", "mixed"),
        "uploaded_by_email": d.get("uploaded_by_email"),
        "mentioned_account_ids": d.get("mentioned_account_ids", []),
        "related_doc_id": d.get("related_doc_id"),
        "relation_type": d.get("relation_type"),
        "error": d.get("error"),
        "created_at": d.get("created_at"),
    }


class DocumentTrustUpdate(BaseModel):
    data_trust: Literal["trusted", "mixed", "weak"]


class DocumentMetaGenerateIn(BaseModel):
    # Caller sends whichever they have; server fills in the other.
    filename: Optional[str] = None
    preview_text: Optional[str] = Field(default=None, max_length=8_000)


@api.post("/contexts/{context_id}/documents/generate-meta")
async def generate_document_meta(
    context_id: str, body: DocumentMetaGenerateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Lightweight meta helper — given a filename and optional preview text,
    asks the LLM to propose a short display name and ≤300-char description.
    Used by the upload modal when the user clicks 'Let AKKI name it'."""
    if not body.filename and not body.preview_text:
        raise HTTPException(status_code=400, detail="Send filename or preview_text.")
    sample = (body.preview_text or "")[:4000]
    prompt = (
        "Propose a short display name and a description for a board-pack "
        "document. Stay neutral, specific, no hype. Return JSON ONLY:\n"
        '{"display_name": "<=60 chars title-case declarative name", '
        '"description": "<=300 chars single-paragraph description"}\n\n'
        f"Filename: {body.filename or '(unknown)'}\n\n"
        f"First ~4KB of extracted text:\n{sample or '(no text extracted)'}"
    )
    out = await llm_call_llm(
        module="document.meta",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"docmeta-{context_id}"},
        data_trust={"overall": "unrated"},
        response_format="json",
    )
    parsed = parse_json_response(out.get("response", ""))
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail=f"LLM returned no meta. Mode={out.get('mode')}.")
    return {
        "display_name": (parsed.get("display_name") or "")[:60].strip(),
        "description": (parsed.get("description") or "")[:300].strip(),
        "mode": out.get("mode"),
    }


@api.post("/contexts/{context_id}/documents")
async def upload_document(
    context_id: str,
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    data_trust: Optional[str] = Form(None),
    mentioned_account_ids: Optional[str] = Form(None),  # comma-sep
    related_doc_id: Optional[str] = Form(None),
    relation_type: Optional[str] = Form(None),  # update | follow_up | additional_context | correction
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    filename = file.filename or "unnamed"
    ext = Path(filename).suffix.lower()
    if ext not in ACCEPT_EXT:
        raise HTTPException(status_code=415, detail=f"Unsupported file type {ext}. Accepted: {', '.join(sorted(ACCEPT_EXT))}")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_BYTES // 1024 // 1024}MB.")

    clean, reason = virus_scan_stub(data, filename)
    if not clean:
        raise HTTPException(status_code=400, detail=f"Rejected by virus scan: {reason}")

    # Validate relation_type if linking to another doc
    if related_doc_id:
        if relation_type not in ("update", "follow_up", "additional_context", "correction"):
            raise HTTPException(status_code=400, detail="Invalid relation_type. Expected: update | follow_up | additional_context | correction")
        related = await db.documents.find_one(
            {"id": related_doc_id, "context_id": context_id, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1},
        )
        if not related:
            raise HTTPException(status_code=404, detail="related_doc_id not found in this context")

    # Parse mentions — only keep ids that are actually context members
    mention_ids: List[str] = []
    if mentioned_account_ids:
        requested = [m.strip() for m in mentioned_account_ids.split(",") if m.strip()]
        if requested:
            valid = await db.memberships.find(
                {"context_id": context_id, "account_id": {"$in": requested}, "status": "active"},
                {"_id": 0, "account_id": 1},
            ).to_list(100)
            mention_ids = [v["account_id"] for v in valid]

    doc_id = str(uuid.uuid4())
    storage_key = save_to_storage(context_id, doc_id, filename, data)
    text, err = extract_text(data, filename, file.content_type or "")
    preview = make_preview(text)

    now = _iso(_now())
    trust = data_trust if data_trust in ("trusted", "mixed", "weak") else "mixed"
    doc = {
        "id": doc_id,
        "context_id": context_id,
        "name": (display_name or Path(filename).stem).strip() or "Untitled",
        "description": (description or "")[:300].strip(),
        "original_filename": filename,
        "mime_type": file.content_type or "application/octet-stream",
        "size_bytes": len(data),
        "storage_key": storage_key,
        "status": "extracted" if text and not err else ("failed" if err else "empty"),
        "extracted_text": text,
        "extracted_chars": len(text),
        "preview": preview,
        "data_trust": trust,
        "uploaded_by": ctx["account"]["id"],
        "uploaded_by_email": ctx["account"]["email"],
        "mentioned_account_ids": mention_ids,
        "related_doc_id": related_doc_id or None,
        "relation_type": relation_type if related_doc_id else None,
        "error": err,
        "created_at": now,
        "updated_at": now,
    }
    await db.documents.insert_one(doc)
    doc.pop("_id", None)

    # Emit mention pings — reuses the comments/mentions collection.
    for account_id in mention_ids:
        if account_id == ctx["account"]["id"]:
            continue
        await db.mentions.insert_one({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "target_account_id": account_id,
            "source_account_id": ctx["account"]["id"],
            "source_name": ctx["account"].get("name") or ctx["account"].get("email", ""),
            "artefact_type": "document",
            "artefact_id": doc_id,
            "comment_id": None,
            "preview": f"Tagged you on: {doc['name']}",
            "created_at": now,
            "read": False,
        })

    await write_audit(
        context_id, ctx["account"]["id"], "document.uploaded", "document", doc_id,
        {"name": doc["name"], "size_bytes": doc["size_bytes"], "status": doc["status"],
         "related_doc_id": related_doc_id, "relation_type": doc["relation_type"],
         "mentions": len(mention_ids)},
    )
    return sanitize_doc(doc)


@api.get("/contexts/{context_id}/documents/{doc_id}/thread")
async def document_thread(
    doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return the thread of linked documents for this doc — ancestors (the
    chain of related_doc_id pointers back to the origin) plus descendants
    (anything that points TO this doc). Used by the Document Journal UI to
    render a continuity thread."""
    context_id = ctx["context"]["id"]
    # Find ancestors by walking related_doc_id up
    ancestors: List[Dict[str, Any]] = []
    current_id: Optional[str] = doc_id
    seen: set = set()
    for _ in range(20):  # safety cap against loops
        if not current_id or current_id in seen:
            break
        seen.add(current_id)
        d = await db.documents.find_one(
            {"id": current_id, "context_id": context_id},
            {"_id": 0},
        )
        if not d:
            break
        ancestors.insert(0, sanitize_doc(d))
        current_id = d.get("related_doc_id")

    # Descendants — anything in this context pointing at doc_id or any ancestor
    ancestor_ids = [a["id"] for a in ancestors]
    descendants = await db.documents.find(
        {
            "context_id": context_id,
            "related_doc_id": {"$in": ancestor_ids},
            "id": {"$nin": ancestor_ids},
            "status": {"$ne": "archived"},
        },
        {"_id": 0},
    ).sort("created_at", 1).to_list(100)
    return {
        "ancestors": ancestors,          # oldest → self
        "descendants": [sanitize_doc(d) for d in descendants],
    }


@api.get("/contexts/{context_id}/documents")
async def list_documents(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 100,
    committee_id: Optional[str] = None,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"], "status": {"$ne": "archived"}}
    if committee_id:
        q["committee_id"] = committee_id
    docs = await db.documents.find(
        q, {"_id": 0, "extracted_text": 0, "storage_key": 0},
    ).sort("created_at", -1).to_list(min(limit, 500))
    return [sanitize_doc(d) for d in docs]


@api.get("/contexts/{context_id}/documents/{doc_id}")
async def get_document_detail(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id}, {"_id": 0, "storage_key": 0}
    )
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    out = sanitize_doc(d)
    # include full extracted text on detail fetch
    out["extracted_text"] = d.get("extracted_text", "")[:MAX_EXTRACT_CHARS_OUT]
    return out


MAX_EXTRACT_CHARS_OUT = 40000


@api.patch("/contexts/{context_id}/documents/{doc_id}")
async def update_document_trust(
    context_id: str, doc_id: str,
    body: DocumentTrustUpdate,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.documents.update_one(
        {"id": doc_id, "context_id": context_id},
        {"$set": {"data_trust": body.data_trust, "updated_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    await write_audit(context_id, ctx["account"]["id"], "document.trust_updated", "document", doc_id,
                      {"data_trust": body.data_trust})
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0, "storage_key": 0, "extracted_text": 0})
    return sanitize_doc(d)


@api.delete("/contexts/{context_id}/documents/{doc_id}")
async def archive_document(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    d = await db.documents.find_one({"id": doc_id, "context_id": context_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    # Only uploader or admin can archive
    if d.get("uploaded_by") != ctx["account"]["id"] and ctx["membership"].get("sub_role") != "admin":
        raise HTTPException(status_code=403, detail="Only the uploader or a context admin can archive this document.")
    await db.documents.update_one(
        {"id": doc_id},
        {"$set": {"status": "archived", "archived_at": _iso(_now())}},
    )
    try:
        delete_from_storage(d.get("storage_key", ""))
    except Exception as e:
        logger.warning(f"delete_from_storage failed: {e}")
    await write_audit(context_id, ctx["account"]["id"], "document.archived", "document", doc_id, {})
    return {"ok": True}


@api.get("/contexts/{context_id}/documents/{doc_id}/download")
async def download_document(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    d = await db.documents.find_one({"id": doc_id, "context_id": context_id})
    if not d or d.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        data = read_from_storage(d["storage_key"])
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Underlying file is no longer available")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=d.get("mime_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{d.get("original_filename", "download")}"'},
    )






@api.post("/contexts/{context_id}/llm/probe")
async def llm_probe(
    context_id: str,
    body: LLMProbeIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    # Also put llm_call_llm back onto the insert below — the probe still works
    # llm_call_llm imported above; place this comment to silence linter
    out = await llm_call_llm(
        module=body.module,
        user_query=body.query,
        context_object={"context_id": context_id, "context_type": ctx["context"].get("type")},
        session_context={"probe": True, "account_id": ctx["account"]["id"]},
        data_trust={"overall": "unrated"},
    )
    return out


# -----------------------------------------------------------------------------
# Telemetry
# -----------------------------------------------------------------------------
@api.post("/events")
async def record_event(
    body: TelemetryEventIn, current: Dict[str, Any] = Depends(get_current_account)
):
    if body.context_id:
        mem = await db.memberships.find_one(
            {"context_id": body.context_id, "account_id": current["id"], "status": "active"}
        )
        if not mem:
            raise HTTPException(status_code=403, detail="Not a member of this context")
    now = _iso(_now())
    doc = {
        "id": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "event_name": body.event_name,
        "event_version": body.event_version,
        "context_id": body.context_id,
        "account_id": current["id"],
        "session_id": body.session_id,
        "surface": body.surface,
        "properties": body.properties,
        "occurred_at": now,
        "received_at": now,
    }
    await db.telemetry_events.insert_one(doc)
    return {"ok": True}


# -----------------------------------------------------------------------------
# Health & root
# -----------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": APP_NAME, "status": "ok", "module": "M5", "brd_version": "3.0"}


@api.get("/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok", "db": "up"}
    except Exception as e:  # pragma: no cover
        return {"status": "degraded", "db": str(e)}


# -----------------------------------------------------------------------------
# Startup / shutdown
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    await db.accounts.create_index("email", unique=True)
    await db.accounts.create_index("id", unique=True)
    await db.contexts.create_index("id", unique=True)
    await db.contexts.create_index("owner_account_id")
    await db.memberships.create_index([("context_id", 1), ("account_id", 1)])
    await db.memberships.create_index("account_id")
    await db.invitations.create_index("token", unique=True)
    await db.invitations.create_index([("context_id", 1), ("email", 1)])
    await db.audit_log.create_index([("context_id", 1), ("created_at", -1)])
    await db.telemetry_events.create_index([("context_id", 1), ("occurred_at", -1)])
    await db.login_attempts.create_index("identifier")
    await db.consent_decisions.create_index([("account_id", 1), ("context_id", 1)])
    await db.organisations.create_index("id", unique=True)
    await db.documents.create_index([("context_id", 1), ("created_at", -1)])
    await db.documents.create_index("id", unique=True)
    await db.signals.create_index([("context_id", 1), ("created_at", -1)])
    await db.signals.create_index("id", unique=True)
    await db.ask_messages.create_index([("context_id", 1), ("created_at", -1)])

    # Backfill: ensure every committee on every context has a stable id.
    # Committees on existing contexts were seeded as {name, your_role} — we add
    # a deterministic slug id so signals/briefings/comments can reference it.
    async for c in db.contexts.find({"committees": {"$exists": True, "$ne": []}}, {"_id": 0, "id": 1, "committees": 1}):
        committees = c.get("committees") or []
        mutated = False
        for cm in committees:
            if not cm.get("id"):
                slug = "".join(
                    ch if ch.isalnum() else "-" for ch in (cm.get("name") or "").lower()
                ).strip("-")
                cm["id"] = slug or f"committee-{uuid.uuid4().hex[:6]}"
                mutated = True
        if mutated:
            await db.contexts.update_one({"id": c["id"]}, {"$set": {"committees": committees}})

    # Admin seed
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@akki.ai").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "AkkiAdmin2026!")
    existing = await db.accounts.find_one({"email": admin_email}, {"_id": 0})
    if not existing:
        admin_id = str(uuid.uuid4())
        now = _iso(_now())
        admin_doc = {
            "id": admin_id,
            "email": admin_email,
            "name": "AKKI Admin",
            "declared_role": "dual",
            "password_hash": hash_password(admin_password),
            "mfa_enabled": False,
            "mfa_secret": None,
            "default_context_id": None,
            "created_at": now,
            "is_superadmin": True,
        }
        await db.accounts.insert_one(admin_doc)
        await provision_default_context(admin_doc, "Syni.ai HQ")
        logger.info(f"Seeded admin account {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.accounts.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info("Admin password rotated from .env")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------
app.include_router(api)
app.include_router(briefings_router.router)
app.include_router(learn_router.router)
app.include_router(committees_router.router)
app.include_router(simulate_router.router)
app.include_router(comments_router.router)
app.include_router(signals_ask_router.router)
app.include_router(lens_router.router)
app.include_router(pipeline_router.router)
app.include_router(audit_router.router)
app.include_router(synisense_router.router)

cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if cors_origins_env.strip() == "*" and frontend_url:
    allow_origins = [frontend_url, "http://localhost:3000"]
else:
    allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    if frontend_url and frontend_url not in allow_origins:
        allow_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
