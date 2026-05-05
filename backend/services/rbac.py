"""rbac.py — Role-based privilege check primitive (Phase A).

Single source of truth for the (user, context) → role binding the
new product memo (Item 5) requires. Replaces the implicit, JWT-cached
role posture of the pre-Phase-A code.

## Contract

Every authenticated endpoint that has role-gated behaviour MUST use
the `require_role(*roles)` dependency. The dependency:

  1. Resolves the current account via `core.get_current_account`.
  2. Reads the `X-Active-Context` request header. Missing header on
     a membership-required route → 400 with code
     `ACTIVE_CONTEXT_REQUIRED` (D-005). The server does NOT default
     to the user's first/oldest membership — the client picks.
  3. Looks up the membership row keyed by `(account_id, context_id,
     status="active")`. Missing membership → 403 with code
     `MEMBERSHIP_REVOKED`.
  4. Asserts the membership's `role` is in the `*roles` allowlist.
     Wrong role → 403 with code `ROLE_FORBIDDEN`.
  5. Writes a privilege-check audit row to `db.audit_log` with
     action `"rbac.privilege_check"` and a metadata blob containing
     `{role, route, outcome}`.
  6. Returns
        {"account": <full account row>,
         "context_id": <X-Active-Context>,
         "role": <"executive" | "ned" | ...>,
         "membership": <full membership row>}

The role lookup is **fresh on every request** — never cached in the
JWT (D-004). The JWT carries identity; `db.memberships` carries
authority.

## Public exports
- `require_role(*roles)`   — dependency factory (use in routers)
- `resolve_active_role(...)` — bare helper (no audit write) for
  internal call paths that don't sit behind a router
- `RBACError`              — base exception
- `ACTIVE_CONTEXT_HEADER`  — the header name (`X-Active-Context`)

## Compatibility
This module does NOT replace `core.require_context_membership` —
that dependency takes `context_id` from the URL path and is correct
for per-context routes (`/api/contexts/{cid}/...`). `require_role`
is for membership-required routes that don't have `context_id` in
the path (e.g. `/api/me/...` flows that need to know the active
role for the calling user).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from fastapi import Depends, HTTPException, Request

from core import db, get_current_account, write_audit

logger = logging.getLogger("akki.rbac")

ACTIVE_CONTEXT_HEADER = "X-Active-Context"

# Role enum. Today the seeded membership rows carry only "executive"
# and "ned"; the memo's broader list ("Company Secretary", etc.) is
# accepted by `require_role` as a string allowlist. We don't enforce
# a closed enum at this layer — that is a Phase D follow-up.
KNOWN_ROLES: tuple = ("executive", "ned", "secretary", "observer")


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────
class RBACError(HTTPException):
    """Base — wraps an HTTPException with a stable code so the SPA
    can branch on it without parsing English."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": detail})
        self.code = code


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _read_active_context(request: Request) -> Optional[str]:
    """Read the `X-Active-Context` header (case-insensitive) — returns
    the trimmed value or `None` if absent / blank."""
    raw = request.headers.get(ACTIVE_CONTEXT_HEADER)
    if not raw:
        return None
    return raw.strip() or None


async def _lookup_membership(account_id: str, context_id: str) -> Optional[Dict[str, Any]]:
    return await db.memberships.find_one(
        {
            "account_id": account_id,
            "context_id": context_id,
            "status": "active",
        },
        {"_id": 0},
    )


async def resolve_active_role(
    account_id: str,
    context_id: str,
) -> Optional[Dict[str, Any]]:
    """Bare helper — looks up the membership row for
    (account_id, context_id, status="active") and returns:
        {"context_id": str, "role": str, "membership": dict}
    Returns None if no active membership exists (caller decides
    whether to 403 or do something else)."""
    m = await _lookup_membership(account_id, context_id)
    if not m:
        return None
    return {
        "context_id": context_id,
        "role": m.get("role"),
        "membership": m,
    }


# ─────────────────────────────────────────────────────────────────────
# require_role — the dependency factory
# ─────────────────────────────────────────────────────────────────────
def require_role(*roles: str):
    """Dependency factory. Use as:

        @router.get("/api/me/foo")
        async def foo(ctx = Depends(require_role("executive", "ned"))):
            # ctx["role"] is "executive" or "ned"; ctx["context_id"] is set;
            # ctx["account"] is the full account row.
            ...

    `roles` may be empty → every active membership role is allowed
    (use this when you only need "is a member of the active context"
    semantics, regardless of role).
    """
    allowed = set(roles) if roles else None

    async def _dep(
        request: Request,
        current: Dict[str, Any] = Depends(get_current_account),
    ) -> Dict[str, Any]:
        # 1. Active-context header is mandatory on membership routes.
        context_id = _read_active_context(request)
        if not context_id:
            raise RBACError(
                status_code=400,
                code="ACTIVE_CONTEXT_REQUIRED",
                detail=(
                    "Missing X-Active-Context header. The SPA must attach "
                    "the active context ID from sessionStorage on every "
                    "membership-required call. See docs/MEMO_DECISIONS.md "
                    "(D-005)."
                ),
            )

        # 2. Resolve role fresh from `db.memberships`.
        m = await _lookup_membership(current["id"], context_id)
        if not m:
            # Outcome: deny. Audit anyway — denied attempts matter.
            await _write_privilege_check_audit(
                current["id"], context_id, role=None,
                route=str(request.url.path), outcome="MEMBERSHIP_REVOKED",
            )
            raise RBACError(
                status_code=403,
                code="MEMBERSHIP_REVOKED",
                detail=(
                    f"You no longer have membership at context "
                    f"{context_id}. Use the company switcher to pick "
                    f"another context."
                ),
            )

        role = m.get("role")
        if allowed is not None and role not in allowed:
            await _write_privilege_check_audit(
                current["id"], context_id, role=role,
                route=str(request.url.path), outcome="ROLE_FORBIDDEN",
            )
            raise RBACError(
                status_code=403,
                code="ROLE_FORBIDDEN",
                detail=(
                    f"Your role at this context ({role}) is not "
                    f"permitted to perform this action. Allowed roles: "
                    f"{sorted(allowed)}."
                ),
            )

        # 3. Allowed — write the success audit row and return.
        await _write_privilege_check_audit(
            current["id"], context_id, role=role,
            route=str(request.url.path), outcome="ALLOWED",
        )
        return {
            "account": current,
            "context_id": context_id,
            "role": role,
            "membership": m,
        }

    return _dep


# ─────────────────────────────────────────────────────────────────────
# Audit log
# ─────────────────────────────────────────────────────────────────────
async def _write_privilege_check_audit(
    account_id: str,
    context_id: str,
    *,
    role: Optional[str],
    route: str,
    outcome: str,
) -> None:
    """Write a single audit row per privilege check.

    Volume note: this fires once per protected request. On the
    busy-but-not-pathological operating range we expect (~10 RPS
    per active session), audit_log will grow at ~10 rows/sec while
    a session is active. The collection has no TTL today; if write
    pressure becomes a problem we'll revisit at Phase H.
    """
    try:
        await write_audit(
            context_id=context_id,
            account_id=account_id,
            action="rbac.privilege_check",
            resource_type="route",
            resource_id=route,
            metadata={"role": role, "outcome": outcome},
        )
    except Exception as exc:  # noqa: BLE001 — audit MUST NOT 500 the request
        logger.warning(
            "rbac audit write failed account=%s context=%s outcome=%s err=%s",
            account_id, context_id, outcome, exc,
        )


async def write_context_switched_audit(
    *,
    account_id: str,
    from_context_id: Optional[str],
    from_role: Optional[str],
    to_context_id: str,
    to_role: str,
) -> None:
    """Single helper used by the active-context switch endpoint to
    log the transition. Separate function from the privilege-check
    audit because the schema (before/after pair) and consumer (the
    switch UI) are different."""
    try:
        await write_audit(
            context_id=to_context_id,
            account_id=account_id,
            action="context.switched",
            resource_type="context",
            resource_id=to_context_id,
            metadata={
                "from_context_id": from_context_id,
                "from_role": from_role,
                "to_context_id": to_context_id,
                "to_role": to_role,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("context.switched audit write failed: %s", exc)
