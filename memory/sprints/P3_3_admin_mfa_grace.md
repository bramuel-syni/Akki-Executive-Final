# P3.3 — Admin MFA grace bypass (2026-02)

**Status:** ACTIVE for `admin@akki.ai` only. Slated for removal in
the next security pass.

## What this is

The seeded super-admin account `admin@akki.ai` is exempt from the
forced-MFA-enrolment gate that fires on `/api/admin/*` calls. This
bypass is gated by the env `MFA_ADMIN_GRACE_EMAILS` (comma-separated
list of email addresses to grace-exempt).

## Why we have it

The dispatch explicitly authorised a phase-only grace for the seeded
admin so the active engineering team isn't locked out of the admin
surface while building the MFA flow. Removing the grace before the
MFA UI shipped would have created a chicken-and-egg situation where
the only path to enrol MFA on the seeded admin is to first reach the
admin surface — and the admin surface requires MFA.

## When to remove it

Remove the bypass as soon as:
  1. The MFA enrolment UI is verified live for the seeded admin
     account.
  2. The seeded admin has personally enrolled MFA + saved recovery
     codes.

Removal is a one-line change: drop `MFA_ADMIN_GRACE_EMAILS` from the
env (defaults to empty when unset → no graces).

## Other super-admins

ANY new super-admin account is enforced — they cannot use any
`/api/admin/*` route until they enrol MFA. The forced-enrolment
surface fires a 428 Precondition Required with
`{ code: "mfa_enrolment_required", enrol_url: "/app/security" }`.

## Audit

Each forced-enrolment failure is logged via the standard error
pipeline; once Sentry DSN is wired the events surface there.
