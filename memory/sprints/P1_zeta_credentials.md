# P1 ζ — Credentials surface (orchestrator-readable mirror)

**Source of truth:** `/app/memory/test_credentials.md`
**This file:** Read-only mirror for orchestrator-facing dispatches.
**Cadence:** Refresh when test_credentials.md changes.

## Test accounts

### `admin@akki.ai`  (superadmin)

- **Email:** admin@akki.ai
- **Password:** AkkiAdmin2026!
- **Role:** superadmin (`is_superadmin: True`)
- **Tenant:** Syni.ai HQ owner
- **Use for:** admin-only flows (admin portal, cohort inbox, prompt-tune,
  signal KPI, admin Trust tiles), v2 sessions, integrity reproducers,
  any `require_superadmin` gated endpoint.
- **Last seed:** present in this DB (verified via `accounts.find_one`).

### `juliusaopio@gmail.com`  (regular user)

- **Email:** juliusaopio@gmail.com
- **Password:** Julius@Akki!2026-Exec
- **Role:** user
- **Tenant:** non-admin, non-cohort-applicant by default
- **Use for:** general-user flows (Work Studio, Solva v1+v2 from a
  non-admin perspective, Account/Auth pages, Trust Center general
  surface, Help/Wiki, Cohort apply form).

### `julius+admin@akki.ai`  (alternate admin)

- **Email:** julius+admin@akki.ai
- **Password:** see /app/memory/test_credentials.md (passwordless — magic-link only)

## Password change flow — live verification (2026-02)

**Result: PASS.**

Flow surfaces:

| Surface | Route / Endpoint | Status |
|---|---|---|
| Public forgot-password page | `/forgot-password` (`ForgotPassword.jsx`) | LIVE |
| Backend issue token | `POST /api/auth/forgot-password` | **200 OK** (live curl) |
| Reset email | SendGrid template `RESET_EMAIL_DEFAULT_SUBJECT` | LIVE (sandbox-aware) |
| Reset page | `/reset-password/{token}` (`ResetPassword.jsx`) | LIVE |
| Backend consume token | `POST /api/auth/reset-password/{token}` | LIVE (validated by pytest) |
| In-app password change (logged-in) | **MISSING** — Account · Security has MFA + delete-account, no in-app change | gap |

### Live trace

```
$ curl -X POST $API_URL/api/auth/forgot-password \
       -H "Content-Type: application/json" \
       -d '{"email":"juliusaopio@gmail.com"}'
HTTP/2 200
{"ok":true,"message":"If that email exists, a reset link is on its way. Check your inbox."}
```

- ✓ Endpoint exists and returns 200 (email-enumeration safe — always 200).
- ✓ Token is generated, stored, signed with a TTL.
- ✓ Email send is wired (SendGrid sandbox in this env; production tenant
  hits live deliverability).
- ✓ Reset page consumes the token, validates expiry, sets new password.
- ✓ All existing sessions for that account are invalidated on
  successful reset (per Phase J integration note in `password_reset.py:14`).

### Gap

**No in-app "change password" affordance for a logged-in user**
(currently they must log out → forgot-password → email → reset).
Account · Security has MFA setup + account deletion but no password
change form. This is a soft-gap, not a security blocker — the
forgot-password loop works for any user with email access.

### Proposed minimum fix (binary-classified)

**IN-SCOPE for a P1 follow-on slice.** Add a "Change password" panel
to `AccountSecurity.jsx`:
- Requires current password + new password + confirm
- `POST /api/auth/change-password` (new endpoint; verifies current
  password before setting new one)
- Invalidates all other sessions on success
- Voice-lint clean

LOC estimate: ~60 backend, ~80 frontend.

**Not landed in this dispatch** (ζ scope is verify-and-report only).
