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
    """Authenticate the request.

    Tries every credential the request carries and accepts the first one
    that decodes to a valid access token. Order tried:
      1) Authorization: Bearer header (used by the anonymous sandbox flow
         and any client that prefers explicit auth).
      2) access_token cookie (the regular signed-in session).

    Iter59 — fixed cookie-first ordering bug. Previously a stale or
    expired access_token cookie from a prior session would short-circuit
    the lookup with a 401, even when the request also carried a perfectly
    valid Bearer JWT (sandbox handoff). The user would then be bounced
    to /signin and stuck because the bad cookie continued to poison
    every subsequent request. Trying every token until one works makes
    the auth path self-healing for clients with mixed credentials.

    Iter61 — sampled observability. The iter59 bug existed in plain sight
    because the auth dependency had no signal. We now sample 1% of
    attempts (configurable via AKKI_AUTH_OBSERVE_RATE) and write a row
    to `auth_events` so /admin/auth/events can surface failure trends
    before a user reports them.
    """
    candidates: list[tuple[str, str]] = []
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer = auth_header[7:].strip()
        if bearer:
            candidates.append(("bearer", bearer))
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        candidates.append(("cookie", cookie_token))

    if not candidates:
        await _record_auth_event(request, ok=False, reason="no_credentials",
                                 credentials=[], dual_mismatch=False)
        raise HTTPException(status_code=401, detail="Not authenticated")

    last_error: HTTPException | None = None
    failed_sources: list[str] = []
    for source, token in candidates:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        except jwt.ExpiredSignatureError:
            last_error = HTTPException(status_code=401, detail="Token expired")
            failed_sources.append(f"{source}:expired")
            continue
        except jwt.InvalidTokenError:
            last_error = HTTPException(status_code=401, detail="Invalid token")
            failed_sources.append(f"{source}:invalid")
            continue
        if payload.get("type") != "access":
            last_error = HTTPException(status_code=401, detail="Invalid token type")
            failed_sources.append(f"{source}:wrong_type")
            continue
        # Phase J (2026-05-27) — JTI revocation check. If the token's `jti`
        # is in the `revoked_jtis` collection, treat as invalid (logout
        # killed it, or an admin issued a session-revoke). Tokens minted
        # pre-Phase-J have no `jti` — those skip the check (legacy
        # tolerance window; tokens expire within 8h of Phase J landing).
        jti = payload.get("jti")
        if jti:
            revoked = await db.revoked_jtis.find_one({"jti": jti}, {"_id": 0, "jti": 1})
            if revoked:
                last_error = HTTPException(status_code=401, detail="Token revoked")
                failed_sources.append(f"{source}:revoked")
                continue
        account = await db.accounts.find_one({"id": payload["sub"]}, {"_id": 0})
        if not account:
            last_error = HTTPException(status_code=401, detail="Account not found")
            failed_sources.append(f"{source}:no_account")
            continue
        # Phase J (2026-05-27) — Account-wide session revocation
        # check. If an admin called /api/admin/auth/revoke-all/{id},
        # any token with `iat < sessions_revoked_after` is rejected.
        sra = account.get("sessions_revoked_after")
        if sra:
            iat_val = payload.get("iat")
            if iat_val:
                try:
                    iat_dt = (
                        iat_val
                        if isinstance(iat_val, datetime)
                        else datetime.fromtimestamp(int(iat_val), tz=timezone.utc)
                    )
                    sra_dt = datetime.fromisoformat(sra.replace("Z", "+00:00")) \
                             if isinstance(sra, str) else sra
                    if sra_dt.tzinfo is None:
                        sra_dt = sra_dt.replace(tzinfo=timezone.utc)
                    if iat_dt.tzinfo is None:
                        iat_dt = iat_dt.replace(tzinfo=timezone.utc)
                    if iat_dt < sra_dt:
                        last_error = HTTPException(
                            status_code=401, detail="Sessions revoked by admin",
                        )
                        failed_sources.append(f"{source}:admin_revoked")
                        continue
                except Exception:
                    pass  # malformed dates fall through (defence-in-depth)
        # Phase V (2026-05-27) — Suspended-account gate. If a superadmin
        # has suspended the account via `POST /api/admin/users/{id}/suspend`,
        # all auth-gated requests must 401 with the locked detail so the
        # frontend can show the suspended-account screen instead of
        # silently logging the user out. Soft-restore by the superadmin
        # via `/restore` flips status back to "active".
        if account.get("status") == "suspended":
            last_error = HTTPException(
                status_code=401,
                detail={"code": "ACCOUNT_SUSPENDED", "message": "Account suspended"},
            )
            failed_sources.append(f"{source}:suspended")
            continue
        # First credential that fully validates wins. We deliberately
        # don't track which source authenticated the request — both are
        # equally trusted once the JWT signature checks out.
        creds_seen = [s for s, _ in candidates]
        # Dual-mismatch = both credentials present but they disagreed on
        # auth outcome (one valid, the other not). Useful early signal
        # that a user has a stale cookie poisoning their session.
        dual_mismatch = len(candidates) >= 2 and len(failed_sources) >= 1
        await _record_auth_event(
            request, ok=True, reason=None,
            credentials=creds_seen,
            dual_mismatch=dual_mismatch,
            authed_via=source,
        )
        return account

    # All candidates failed; bubble up the last error so logs are useful.
    assert last_error is not None
    await _record_auth_event(
        request, ok=False, reason=last_error.detail,
        credentials=[s for s, _ in candidates],
        dual_mismatch=False,
    )
    raise last_error


async def _record_auth_event(
    request: Request,
    *,
    ok: bool,
    reason: str | None,
    credentials: list[str],
    dual_mismatch: bool,
    authed_via: str | None = None,
) -> None:
    """Sampled write — best effort. Errors here MUST never leak to the request."""
    try:
        rate_str = os.environ.get("AKKI_AUTH_OBSERVE_RATE", "0.01")
        try:
            rate = float(rate_str)
        except ValueError:
            rate = 0.01
        # Always sample failures (we want every 401 in the log); sample
        # successes at the configured rate.
        if ok and rate < 1.0:
            import random
            if random.random() > rate:
                return
        from datetime import datetime as _dt, timezone as _tz
        await db.auth_events.insert_one({
            "at": _dt.now(_tz.utc).isoformat(),
            "ok": ok,
            "reason": reason,
            "credentials": credentials,
            "authed_via": authed_via,
            "dual_mismatch": dual_mismatch,
            "path": str(request.url.path),
            "method": request.method,
        })
    except Exception:  # noqa: BLE001
        # Observability MUST be best-effort. A logging failure here would
        # cascade into request failures and is unacceptable.
        pass


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
    # Phase J (2026-05-27) — `jti` (uuid4) added so individual access
    # tokens can be revoked server-side via the `revoked_jtis` collection
    # (see `get_current_account` below + `routers/auth.py::logout`).
    return jwt.encode(
        {
            "sub": account_id, "email": email, "type": "access",
            "jti": uuid.uuid4().hex,
            "exp": now() + timedelta(minutes=ACCESS_TOKEN_TTL_MIN),
            "iat": now(),
        },
        JWT_SECRET, algorithm=JWT_ALGO,
    )


def create_refresh_token(account_id: str) -> str:
    # Phase J — refresh tokens also carry a JTI for symmetry and future
    # refresh-revocation work, even though revocation only checks access
    # tokens in v1 of the blocklist.
    return jwt.encode(
        {
            "sub": account_id, "type": "refresh",
            "jti": uuid.uuid4().hex,
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
        "first_session": a.get("first_session") or {"status": "not_started"},
    }
    # Surface sandbox markers only when present — non-sandbox accounts stay
    # lean. Lets the frontend key off account.is_sandbox if it wants to.
    if a.get("is_sandbox"):
        out["is_sandbox"] = True
        if a.get("sandbox_session_id"):
            out["sandbox_session_id"] = a["sandbox_session_id"]
    # Phase R.1 (2026-05-27) — Cohort markers surface only when present.
    # Non-cohort accounts stay lean. R.5 cohort console will read these
    # to render trial countdown / status; for R.1 the only consumer is
    # the sr-only DOM hook in AppShell that the Playwright probe reads.
    for k in ("trial_status", "trial_start_at", "trial_end_at",
              "cohort_tag", "first_name", "logo_name",
              "grandfathered_price_locked"):
        if a.get(k) is not None:
            out[k] = a[k]
    # Phase X (2026-02 fork-resume) — Self-service deletion markers.
    # Surfaced so the frontend Danger Zone can render the "scheduled
    # for deletion" banner + cancel CTA without an extra round-trip.
    if a.get("status"):
        out["status"] = a["status"]
    for k in ("deletion_requested_at", "deletion_scheduled_for"):
        if a.get(k) is not None:
            out[k] = a[k]
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
