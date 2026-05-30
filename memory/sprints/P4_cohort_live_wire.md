# P4 — Cohort live-wiring (2026-02)

## Slices shipped

| Slice | Status | Notes |
|---|---|---|
| P4.A receipt email | SHIP | Auto-fires on `POST /api/cohort/applications`. Flag-gated by `COHORT_EMAILS_ENABLED` (default false → logs `cohort_email: would have sent receipt to <redacted>`). Voice-clean. ≤60 words. |
| P4.B admin approve/decline/hold | SHIP | New endpoints under `/api/admin/cohort/applications/{id}/{approve\|decline\|hold}`. CSRF + MFA-gated. Audit row written to `cohort_application_audit`. Approve issues magic link + sends approval email (flag-gated). Decline sends decline email (flag-gated). Hold sends no email. |
| P4.C magic-link | SHIP | New collection `cohort_magic_links`. `POST /api/auth/magic-link/issue` (admin), `GET /api/auth/magic-link/preview/{token}` (public), `POST /api/auth/magic-link/consume` (public, CSRF). 32-byte tokens, bcrypt-hashed at rest, 14-day expiry, single-use. Reissue invalidates priors. |
| P4.D /welcome/{token} | SHIP | Public React route. 5 states (loading / valid / expired / consumed / not_found / consumed_ok). 3 CTAs on valid (password / Google / Microsoft). Layout passes 1280/1024/820/414 with zero horizontal overflow. |

## Endpoints landed

| Method | Path | Surface |
|---|---|---|
| POST | /api/auth/magic-link/issue | admin-only, idempotent per application_id |
| GET | /api/auth/magic-link/preview/{token} | public, returns first_name+org+expires_at OR 410 (expired/consumed) OR 404 |
| POST | /api/auth/magic-link/consume | public, mode=password\|google\|microsoft, sets session cookies + returns redirect target |
| POST | /api/admin/cohort/applications/{id}/approve | admin+MFA, issues link + queues approval email |
| POST | /api/admin/cohort/applications/{id}/decline | admin+MFA, queues decline email |
| POST | /api/admin/cohort/applications/{id}/hold | admin+MFA, no email |
| GET | /api/admin/cohort/applications | admin+MFA, list with optional status filter |

## Mongo collections

| Collection | Purpose |
|---|---|
| `cohort_applications` | Funnel rows (existing; status enum extended with `held`, `declined`, `approved`, `approved_redeemed`). |
| `cohort_magic_links` | NEW. {id, application_id, token_hash, issued_at, expires_at, consumed_at, consumed_by_user_id, issued_by, consumed_reason} |
| `cohort_application_audit` | NEW. {id, application_id, action, actor_admin_id, prev_status, new_status, timestamp} |

## Voice-lint state

`voice_lint: clean across customer-copy surfaces.` — receipt + approval + decline bodies all pass.

## Feature flag

`COHORT_EMAILS_ENABLED` stays **false** at end of phase. When false:
- Receipt apply path logs `cohort_email: would have sent receipt to <redacted>`
- Admin approve/decline returns `email: {status: "flag_off", kind: "approval"|"decline"}`

The admin UI surfaces the magic-link URL in the success toast (and copies to clipboard) so the admin can deliver it out-of-band while the flag stays off.

## Word counts (≤60 cap)

Computed at import time inside `services/cohort_email.py::_self_check()` and asserted in `test_phase_p4_cohort_funnel.py::test_p4_a_receipt_email_word_counts_under_60`. Current values:

| Kind | Subject + body word count |
|---|---|
| Receipt | well under 60 |
| Approval | well under 60 |
| Decline | well under 60 |

(Exact counts re-verified on every test run.)

## Sentry events emitted

| Event | When |
|---|---|
| `cohort.magic_link.issued` | admin issues a link |
| `cohort.magic_link.consumed` | applicant consumes |
| (cohort_email logger lines flow through to Sentry breadcrumbs) | always |

PII scrubbing per P3 wiring — emails are reduced to `<2chars>***@<domain>` in logs.

## Files touched

- Backend NEW: `services/cohort_email.py`, `routers/cohort_magic_link.py`, `routers/admin_cohort_applications.py`, `tests/test_phase_p4_cohort_funnel.py`.
- Backend MOD: `server.py` (2 router includes), `routers/cohort_applications.py` (receipt email background task).
- Frontend NEW: `pages/WelcomePage.jsx`, `pages/admin/AdminCohortApplications.jsx`.
- Frontend MOD: `App.js` (2 lazy imports + 2 routes).
- Memory: `sprints/P4_cohort_live_wire.md` (this file).
- Trace scripts: `/tmp/p4_e2e_trace.py`, `/tmp/p4_trace_admin_ui.py`.

## Removal/handover when going live

1. User reviews verbatim bodies (surfaced top of return).
2. User flips `COHORT_EMAILS_ENABLED=true` in backend/.env.
3. `sudo supervisorctl restart backend` (env reload).
4. Confirm a smoke send via the admin "Approve" action — toast shows `Email status: sent` instead of `flag_off`.
