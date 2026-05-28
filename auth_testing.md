# Auth Testing Playbook — Phase U (OAuth/SSO)

This is the Emergent Auth playbook for OAuth (Google) sign-in. The
testing agent should read this before testing the OAuth sign-in flow.

## Phase U Backend Endpoints

- `GET /api/auth/oauth/google/start` — Returns `{redirect_url:
  "https://auth.emergentagent.com/?redirect=..."}`.
- `POST /api/auth/oauth/google/finish` — Body `{session_id}`. Backend
  calls Emergent's session-data endpoint, finds-or-creates the
  account (`auth_provider="google"`, `password_hash=None`), mints OUR
  JWT (same Phase J JTI revocation contract), sets cookies, returns
  `{token, account_id, email, is_new, next_url}`.
- `POST /api/auth/oauth/microsoft/start` — Returns 503 + locked
  payload `{error: "microsoft_oauth_not_configured", needs:
  "user-provided Application ID + Client Secret"}` until creds arrive.

## Test Flow

```bash
# 1. Frontend forwards to:
https://auth.emergentagent.com/?redirect=https://akki-executive.preview.emergentagent.com/oauth/callback

# 2. After Google auth, browser lands at:
https://akki-executive.preview.emergentagent.com/oauth/callback#session_id=<random>

# 3. Frontend `/oauth/callback` POSTs to backend:
curl -X POST "https://akki-executive.preview.emergentagent.com/api/auth/oauth/google/finish" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<random>"}'

# Returns: {token, account_id, email, is_new, next_url}
```

## JWT Contract

Phase U mints JWTs using the same `core.create_access_token` /
`create_refresh_token` helpers as the magic-link path. `auth_provider`
is stamped on the account doc so future flows (e.g. password reset
gating) can branch on whether the account has a password.

## Microsoft OAuth (deferred)

Microsoft route returns 503 until `MICROSOFT_OAUTH_CLIENT_ID` +
`MICROSOFT_OAUTH_CLIENT_SECRET` are added to backend/.env. The 503
payload is locked so the frontend can display "coming soon" UX.

## Acceptance Gates

- `GET /api/auth/oauth/google/start` → 200 with redirect_url
- `POST /api/auth/oauth/google/finish` invalid session_id → 400
- `POST /api/auth/oauth/google/finish` valid session_id:
  - creates new account if email novel (`auth_provider="google"`)
  - signs in existing account if email matches
  - mints a JWT that passes `get_current_account` validation
- `POST /api/auth/oauth/microsoft/start` → 503 with locked payload
- Sign-in page renders Google + Microsoft buttons at 1280/1024/768
- Clicking Google forwards to `auth.emergentagent.com`
- After Google auth, frontend `/oauth/callback` lands the user at
  `/app/`
- Zero new console errors on the callback path

## Test Identities

Use any Google account via Emergent Auth. The admin/test credentials
in `/app/memory/test_credentials.md` apply to password-based test
accounts; OAuth-created accounts are passwordless.
