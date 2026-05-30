# P3 Security MVP+ memo (2026-02)

## CSRF strategy

**Double-submit-cookie with HMAC-signed token.** Reasons:

- Stateless. The token is `<nonce>.<issued_at>.<HMAC-SHA256(secret, nonce.issued_at)>`. No DB roundtrip on every state-changing request.
- Cookie is non-HttpOnly so the SPA can read + send it as a header; the value is HMAC-signed so it can't be forged.
- Plays cleanly with our existing JWT-in-cookie session model (httpOnly access_token + refresh_token, separate non-HttpOnly csrf_token).
- Test bypass is a single env switch (`CSRF_TEST_BYPASS_HEADER=1` + per-request header `X-CSRF-Test-Bypass: 1`). Production never sets this env.

## Wired surfaces

- Backend: `services/csrf.py` middleware + `routers/csrf.py` mint endpoint.
- Frontend: `lib/api.js` axios interceptor — auto-fetches the token on first state-changing call, caches in memory + cookie, retries once on 403 csrf_token_*.
- Allowlist: `/api/csrf`, `/api/billing/webhook/`, OAuth callbacks (GET only anyway, so not in scope).

## Cookie attributes (P3.2)

| Cookie         | HttpOnly | Secure | SameSite | Path |
|----------------|----------|--------|----------|------|
| access_token   | ✓        | ✓ (env-gated `COOKIE_SECURE=1`) | Strict | / |
| refresh_token  | ✓        | ✓        | Strict | / |
| csrf_token     | ✗ (JS readable for double-submit) | ✓ | Lax | / |

Domain: not pinned to a wildcard subdomain — defaults to the request host (which on Kubernetes ingress is the public preview / prod host).

## Session timeout (P3.4)

| Limit       | Default | Env override                    |
|-------------|---------|----------------------------------|
| Absolute    | 12 h    | `SESSION_ABSOLUTE_HOURS`         |
| Idle        | 30 min  | `SESSION_IDLE_MINUTES`           |
| Silent refresh window | 1 h | `SESSION_SILENT_REFRESH_HOURS` |
| Escape hatch | —       | `SESSION_TIMEOUT_DISABLED=1`     |

Activity = any authenticated API call (any route that drives `get_current_account`). `last_activity_at` is bumped per request on the account doc; the middleware reads it on the next request and rejects with `session_idle_timeout` when stale.

Silent refresh: tokens older than 1 h but younger than 12 h are auto re-signed by the middleware with a fresh `exp` capped at 12 h from the **original** `iat`. The response carries `X-Token-Refreshed: 1` so the frontend can swap its in-memory copy if needed (cookie is rotated server-side either way).

## MFA (P3.3)

- TOTP via `pyotp` (existing dep). 6-digit codes, 1-step `valid_window` for clock skew.
- Recovery codes: 10 single-use, 12-char (XXXX-XXXX-XXXX), bcrypt-hashed at rest.
- Lockout: 5 consecutive failed codes → 15-minute lock. Distinct counter from per-route rate limit.
- Admin enforcement: super-admins NOT on the grace list get a 428 Precondition Required on `/api/admin/*` until enrolled. Grace doc at `P3_3_admin_mfa_grace.md`.
- Voice-clean copy on every user-facing string ("passcode" not "code-word", "sign-in" not "login").

## Endpoints landed

| Method | Path                                       | Purpose                              |
|--------|--------------------------------------------|--------------------------------------|
| GET    | /api/csrf                                  | Mint CSRF token + set cookie         |
| POST   | /api/auth/mfa/enroll/start                 | Mint pending TOTP secret + QR        |
| POST   | /api/auth/mfa/enroll/confirm               | Confirm 6-digit → enable + 10 codes  |
| POST   | /api/auth/mfa/verify                       | Verify TOTP/recovery during login    |
| POST   | /api/auth/mfa/disable                      | Disable MFA (requires password)      |
| POST   | /api/auth/mfa/recovery/regenerate          | Mint fresh recovery codes            |
| GET    | /api/auth/mfa/status                       | Read-only status for the UI panel    |

## CI (P3.5 / P3.6)

- `.github/workflows/gitleaks.yml` — gitleaks on every push/PR; allowlist at `.gitleaks.toml`. Local test: `gitleaks detect --source . --no-banner -v`.
- `.github/dependabot.yml` — weekly PRs for `pip`, `npm`, `github-actions`.
- `.github/workflows/dep-audit.yml` — `pip-audit` + `yarn audit --level high`. Currently fails the job on HIGH or CRITICAL.

## Files touched

- Backend (new): `services/csrf.py`, `routers/csrf.py`, `routers/mfa.py`, `services/session_timeout.py`.
- Backend (modified): `server.py` (3 middleware mounts + 2 router includes), `core.py` (`create_access_token` mfa_verified claim + `set_auth_cookies` SameSite=Strict), `routers/auth.py` (removed legacy MFA endpoints + delegated to new router), `routers/admin_users.py` (`_require_superadmin` MFA gate), `tests/conftest.py` (CSRF test bypass header auto-injection).
- Frontend (new): `components/SessionTimeoutGuard.jsx`.
- Frontend (modified): `lib/api.js` (CSRF interceptor + session-event dispatch), `pages/AccountSecurity.jsx` (recovery-code modal + password-gated disable), `components/layout/AppShell.jsx` (mount SessionTimeoutGuard).
- CI: `.github/workflows/gitleaks.yml`, `.github/workflows/dep-audit.yml`, `.github/dependabot.yml`, `.gitleaks.toml`.
- Tests (new): `tests/test_phase_p3_1_csrf.py`, `tests/test_phase_p3_2_cookie_hardening.py`, `tests/test_phase_p3_3_mfa.py`, `tests/test_phase_p3_4_session_timeout.py`.
- Memory: `sprints/P3_security_mvp_plus.md` (this file), `sprints/P3_3_admin_mfa_grace.md`.
