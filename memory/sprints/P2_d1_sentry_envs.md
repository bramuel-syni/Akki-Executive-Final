# P2 D.1 — Sentry env list (2026-02)

**Status:** Shipped (backend + frontend wiring; both default to
no-op when DSN unset).

## Required env vars

### Backend (`backend/.env`)

| Var                              | Purpose                                                |
|----------------------------------|--------------------------------------------------------|
| `SENTRY_DSN`                     | Required to enable. Absent → no-op.                    |
| `SENTRY_ENVIRONMENT`             | `production` / `staging` / `development`.              |
| `SENTRY_TRACES_SAMPLE_RATE`      | Float 0..1. Default `0.0` — no perf data.              |
| `SENTRY_PROFILES_SAMPLE_RATE`    | Float 0..1. Default `0.0` — no profiling.              |
| `SENTRY_RELEASE`                 | Optional release tag (`akki@2026.02.01` etc.).         |

### Frontend (`frontend/.env`)

| Var                                          | Purpose                                                |
|----------------------------------------------|--------------------------------------------------------|
| `REACT_APP_SENTRY_DSN`                       | Required to enable. Absent → no-op.                    |
| `REACT_APP_SENTRY_ENVIRONMENT`               | `production` / `staging` / `development`.              |
| `REACT_APP_SENTRY_TRACES_SAMPLE_RATE`        | Float 0..1. Default `0` — no perf data.                |
| `REACT_APP_SENTRY_RELEASE`                   | Optional release tag.                                  |

## PII scrubbing

ON by default and not configurable. Both backend and frontend
init paths force `send_default_pii: false` AND register a
`before_send` hook (backend) / `beforeSend` (frontend) that walks
the event body and replaces any field whose key contains one of
the PII tokens with `"[scrubbed]"`:

```
email, password, password_hash, magic_link_token,
reset_password_token, code_verifier, Authorization,
cookie, set-cookie, first_name, last_name, full_name
```

If the scrubber raises, the event is DROPPED rather than sent
un-scrubbed.

## Where to get a DSN

1. Create a Sentry project at https://sentry.io for `akki-backend`
   (Python · FastAPI) and another for `akki-frontend` (JavaScript ·
   React).
2. Copy the DSN from "Settings → Projects → Client Keys (DSN)".
3. Paste into the matching env var.

## Verification

| Probe                                              | Result |
|----------------------------------------------------|--------|
| Boot log line: `sentry: noop (SENTRY_DSN unset)`   | ✓ Present in current environment (no DSN configured). |
| Boot log line: `sentry: live env=<env>`            | Will appear once DSN is set. |
| Frontend boot console line                         | `[sentry] noop (REACT_APP_SENTRY_DSN unset)` ✓ |
| ErrorBoundary `componentDidCatch` → captureException| Wired. No-op when SDK is in noop mode. |

## Activation steps (operator)

1. Set `SENTRY_DSN` in `backend/.env` and `REACT_APP_SENTRY_DSN` in
   `frontend/.env`.
2. Restart backend (env reload). Frontend picks up on next yarn
   build / next dev server restart.
3. Confirm both boot logs show `live` mode.
4. Trigger a test event from both surfaces (e.g. force a 5xx for
   backend, force a render error in frontend).
5. Confirm both events arrive in the Sentry dashboard with the
   scrubbed payload.
