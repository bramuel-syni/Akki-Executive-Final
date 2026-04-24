"""Authentication: register, login, logout, refresh, me, declare-role, MFA.

Moved out of server.py to keep the monolith thin. No behavioural changes.
"""
from __future__ import annotations

import base64
import io
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

import jwt
import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, now as _now, iso as _iso, write_audit,
    get_current_account,
    create_access_token, create_refresh_token,
    hash_password, verify_password,
    set_auth_cookies, clear_auth_cookies,
    sanitize_account, sanitize_context,
    provision_default_context,
    JWT_SECRET, JWT_ALGO, APP_NAME,
)

router = APIRouter(prefix="/api")


AccountRole = Literal["ned", "executive", "dual", "undeclared"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    context_name: Optional[str] = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class DeclareRoleIn(BaseModel):
    declared_role: AccountRole


class MFAVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


@router.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower().strip()
    existing = await db.accounts.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    account_id = str(uuid.uuid4())
    created_at = _iso(_now())
    account_doc = {
        "id": account_id,
        "email": email,
        "name": body.name.strip(),
        "declared_role": "undeclared",
        "password_hash": hash_password(body.password),
        "mfa_enabled": False,
        "mfa_secret": None,
        "default_context_id": None,
        "created_at": created_at,
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


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    email = body.email.lower().strip()
    # Key rate-limit on email only (ingress proxy host is not stable).
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


@router.post("/auth/logout")
async def logout(response: Response, _: Dict[str, Any] = Depends(get_current_account)):
    clear_auth_cookies(response)
    return {"ok": True}


@router.post("/auth/refresh")
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


@router.get("/auth/me")
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


@router.post("/auth/declare-role")
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


# -----------------------------------------------------------------------------
# MFA (TOTP)
# -----------------------------------------------------------------------------
@router.post("/auth/mfa/setup")
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
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"otpauth_url": otpauth, "qr_data_url": data_url, "secret": secret}


@router.post("/auth/mfa/verify")
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


@router.post("/auth/mfa/disable")
async def mfa_disable(current: Dict[str, Any] = Depends(get_current_account)):
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"mfa_enabled": False}, "$unset": {"mfa_secret": "", "mfa_secret_pending": ""}},
    )
    return {"ok": True, "mfa_enabled": False}
