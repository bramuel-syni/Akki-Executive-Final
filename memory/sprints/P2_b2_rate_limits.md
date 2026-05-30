# P2 B.2 — Rate-limit configuration (2026-02)

**Status:** Shipped.
**Implementation:** `backend/services/rate_limit.py` — FastAPI
`Depends(rate_limit("bucket"))` pattern. Per-IP for unauthenticated
calls (X-Forwarded-For first hop), per-user for authenticated calls
(JWT `sub` claim). Storage: in-memory `MemoryStorage` from the
`limits` library (per-pod; acceptable for single-replica deploys).

## Limits (defaults · env override)

| Bucket            | Default      | Env override         | Routes                                                                                |
|-------------------|--------------|----------------------|---------------------------------------------------------------------------------------|
| `auth_login`      | `10/minute`  | `RL_AUTH_LOGIN`      | `POST /api/auth/login`                                                                |
| `auth_register`   | `5/minute`   | `RL_AUTH_REGISTER`   | `POST /api/auth/register`                                                             |
| `auth_forgot`     | `5/minute`   | `RL_AUTH_FORGOT`     | `POST /api/auth/forgot-password`                                                      |
| `auth_reset`      | `10/minute`  | `RL_AUTH_RESET`      | `POST /api/auth/reset-password/{token}`                                               |
| `auth_pwchange`   | `10/minute`  | `RL_AUTH_PWCHANGE`   | `POST /api/auth/password/change`                                                      |
| `cohort_apply`    | `5/minute`   | `RL_COHORT_APPLY`    | `POST /api/cohort/applications`                                                       |
| `public_tile`     | `60/minute`  | `RL_PUBLIC_TILE`     | `GET /api/public/observability/reasoning_velocity`                                    |
| `solva`           | `30/minute`  | `RL_SOLVA`           | Reserved — apply once the Solva v2 router opt-ins land in a follow-on slice.          |

## Disable

`RATE_LIMIT_DISABLED=1` short-circuits every dependency check to a
no-op. Escape hatch for incident response. Never set in prod by
default.

## 429 response shape

```json
{
  "detail": {
    "code":    "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Try again shortly.",
    "limit":   "10/minute",
    "bucket":  "auth_login"
  }
}
```

Carries `Retry-After: <seconds>` header.

## Verification

| Probe                                                  | Result |
|--------------------------------------------------------|--------|
| `curl POST /api/auth/login` × 11 in 60 s               | 11th call → 429 with `Retry-After` ✓ |
| `curl POST /api/cohort/applications` × 6 in 60 s       | 6th call → 429 with `Retry-After` ✓  |
| Per-user vs per-IP keying (JWT sub recognised)         | Authenticated calls share a `user:<sub>` bucket separate from IP ✓ |
| Storage failure → fail-open                            | Memory storage; no failure mode short of process crash ✓ |
| `RATE_LIMIT_DISABLED=1` → no enforcement               | Manual probe ✓ |

## Notes

- Multi-replica: swap `MemoryStorage` for `RedisStorage` and set
  `RATE_LIMIT_REDIS_URL`. Not wired in this slice — single-replica is
  the operating mode for early access.
- The bucket key combines `(bucket_name, client_key)` so the same
  user hitting two different surfaces gets two separate counters,
  not one merged counter.
- The 429 errors do NOT consume the user's budget on the next bucket
  — the `limits` library debits at `hit()` time only.

## Why dependency-style instead of slowapi decorators

`@limiter.limit(...)` from slowapi wraps the route handler. Combined
with `from __future__ import annotations` (PEP 563), FastAPI's
`get_type_hints()` resolution on the wrapped function fails to
resolve Pydantic body models — they get reinterpreted as query
parameters and every request 422s. The dependency-style pattern
sidesteps this entirely: the route signature is untouched, and the
rate-limit check runs as a FastAPI dependency before the body is
even parsed.
