"""Phase P2 B.2 (2026-02) — Rate limiting.

Per-IP + per-user limiter built on the `limits` library directly (no
slowapi decorator wrap — that pattern breaks FastAPI Pydantic body
resolution under PEP 563 `from __future__ import annotations`).

Surfaces opt in via FastAPI dependency injection:

    from services.rate_limit import rate_limit
    @router.post("/auth/login")
    async def login(_rl: None = Depends(rate_limit("auth_login")), ...):
        ...

Limits (tunable via env; see `P2_b2_rate_limits.md`):

| Surface                                   | env override                  | default          |
|-------------------------------------------|-------------------------------|------------------|
| POST /api/auth/login                      | RL_AUTH_LOGIN                 | 10/minute        |
| POST /api/auth/register                   | RL_AUTH_REGISTER              | 5/minute         |
| POST /api/auth/forgot-password            | RL_AUTH_FORGOT                | 5/minute         |
| POST /api/auth/reset-password/{token}     | RL_AUTH_RESET                 | 10/minute        |
| POST /api/auth/password/change            | RL_AUTH_PWCHANGE              | 10/minute        |
| POST /api/cohort/applications             | RL_COHORT_APPLY               | 5/minute         |
| GET  /api/public/observability/*          | RL_PUBLIC_TILE                | 60/minute        |
| POST /api/solva/*                         | RL_SOLVA                      | 30/minute        |

Storage: in-memory `MemoryStorage` from the `limits` library. Per-pod;
acceptable for single-replica deploys. For multi-replica deployments,
swap to `RedisStorage` by setting `RATE_LIMIT_REDIS_URL`.

Disable with `RATE_LIMIT_DISABLED=1`.
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import HTTPException, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from core import JWT_SECRET, JWT_ALGO


def _env(name: str, default: str) -> str:
    return (os.environ.get(name, "") or "").strip() or default


LIMITS = {
    "auth_login":      _env("RL_AUTH_LOGIN",      "10/minute"),
    "auth_register":   _env("RL_AUTH_REGISTER",   "5/minute"),
    "auth_forgot":     _env("RL_AUTH_FORGOT",     "5/minute"),
    "auth_reset":      _env("RL_AUTH_RESET",      "10/minute"),
    "auth_pwchange":   _env("RL_AUTH_PWCHANGE",   "10/minute"),
    "cohort_apply":    _env("RL_COHORT_APPLY",    "5/minute"),
    "public_tile":     _env("RL_PUBLIC_TILE",     "60/minute"),
    "solva":           _env("RL_SOLVA",           "30/minute"),
}

DISABLED = os.environ.get("RATE_LIMIT_DISABLED", "0").strip() == "1"

_storage = MemoryStorage()
_strategy = MovingWindowRateLimiter(_storage)
_parsed = {k: parse(v) for k, v in LIMITS.items()}


def _client_key(request: Request) -> str:
    """Per-user when we can decode the JWT, per-IP otherwise."""
    auth = request.headers.get("Authorization", "")
    raw: Optional[str] = None
    if auth.startswith("Bearer "):
        raw = auth[7:].strip()
    else:
        raw = request.cookies.get("access_token")
    if raw:
        try:
            payload = jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALGO])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:  # noqa: BLE001
            pass

    # IP fallback: trust X-Forwarded-For first hop (Kubernetes ingress
    # sets this). Falls back to client.host.
    xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if xff:
        return f"ip:{xff}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def rate_limit(bucket: str):
    """FastAPI dependency factory. Use as:

        async def endpoint(_rl: None = Depends(rate_limit('auth_login'))):
            ...
    """
    if bucket not in _parsed:
        raise KeyError(f"Unknown rate-limit bucket: {bucket!r}. Available: {list(LIMITS)}")

    async def _check(request: Request) -> None:
        if DISABLED:
            return None
        limit_item = _parsed[bucket]
        key = _client_key(request)
        if not _strategy.hit(limit_item, bucket, key):
            window_stats = _strategy.get_window_stats(limit_item, bucket, key)
            retry_after = max(0, int(window_stats.reset_time - _now_epoch()))
            raise HTTPException(
                status_code=429,
                detail={
                    "code":    "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Try again shortly.",
                    "limit":   LIMITS[bucket],
                    "bucket":  bucket,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return None

    return _check


def _now_epoch() -> int:
    import time
    return int(time.time())
