# P1 δ — User admin portal status report

**Date:** 2026-02
**Scope:** Read-only code walk.

## Verdict

**EXISTS, PRODUCTION-GRADE.** A full superadmin-gated user admin
portal already lives in the codebase. Status: **LIVE**.

## Surface inventory

| Surface | Route | File | Status |
|---|---|---|---|
| Admin Users index | `/app/admin/users` | `frontend/src/pages/admin/AdminUsers.jsx` (504 LOC) | LIVE — wrapped in `<SuperadminRoute>` (App.js) |
| Admin Cohort Apps inbox | `/app/admin/cohort-applications` | `frontend/src/pages/admin/AdminCohortApplications.jsx` | LIVE — SuperadminRoute |
| Admin Prompt-tuning dry-run | `/app/admin/prompts` | `frontend/src/pages/admin/AdminPromptTuning.jsx` | LIVE — SuperadminRoute |
| Admin Index / hub | `/app/admin` | `frontend/src/pages/admin/AdminIndex.jsx` | LIVE — SuperadminRoute |
| Admin Cohort copy editor | `/app/admin/cohort-copy` | `frontend/src/pages/admin/CohortCopyEditor.jsx` | LIVE — SuperadminRoute |
| Admin Signal KPI | `/app/admin/signal-kpi` | `frontend/src/pages/admin/SignalKPI.jsx` | LIVE — SuperadminRoute |

## AdminUsers.jsx capabilities (per code walk)

✓ **List users** with pagination, status filter (`active` / `suspended` / `all`)
✓ **Search by email / name** (live `?q=`)
✓ **Create user** (modal: email + name + role)
✓ **Suspend user** (with reason)
✓ **Restore user** (rehydrate from suspended)
✓ **Timeline view** — per-user audit trail (created, suspended, restored, role change, login)
✓ **CSV export** of current filter set
✓ **Role display** (user / admin / superadmin)
✓ **Email-verified badge**
✓ **Onboarding stage display** (`profile_complete` / `tenant_set` / etc.)
✓ **Account-suspension reason persisted**
✓ **Mass-action drawer** (multi-select + bulk suspend)

## Backend coverage (`backend/routers/admin_users.py`, 453 LOC)

✓ `GET    /api/admin/users`              — list with filters + pagination
✓ `POST   /api/admin/users`              — create user
✓ `GET    /api/admin/users/{id}`         — detail
✓ `PATCH  /api/admin/users/{id}`         — update role / name
✓ `POST   /api/admin/users/{id}/suspend` — suspend with reason
✓ `POST   /api/admin/users/{id}/restore` — restore
✓ `GET    /api/admin/users/{id}/timeline`— audit timeline
✓ `GET    /api/admin/users/export.csv`   — CSV export

All endpoints gated by `require_superadmin` dependency (verifies
`account.is_superadmin === true`).

## Gaps vs. user's intended-class checklist

| Intended capability | Status | Note |
|---|---|---|
| List/search users | ✓ DONE | filter + paginate + search |
| Deactivate | ✓ DONE | suspend endpoint + reason |
| Force-reset password | ✗ **MISSING** | No "force reset" / "trigger password reset email" affordance |
| Role toggle (user/admin) | ✓ DONE | PATCH role |
| Audit log view | ✓ DONE | timeline endpoint + UI |

## Proposed minimum-fix for the gap (binary-classified)

**Force-reset password trigger** — **IN-SCOPE for P1 ν+1 mini-ship**.
Add a `POST /api/admin/users/{id}/force_password_reset` endpoint that:
1. Generates a one-time password-reset token (existing `password_reset_tokens` collection)
2. Sends a reset email via SendGrid with the link
3. Records an `admin.force_password_reset` event in the user's timeline

LOC estimate: ~50 backend, ~25 frontend (button on user detail + confirm modal).

Not landed in this dispatch (P1 δ scope is REPORT only).

## Entry point added by P1 ε

Phase P1 ε (this dispatch) adds the account-dropdown link
`data-testid="nav-admin-users"` in `AppShell.jsx` between the Trust
menuitem and the separator. Visible ONLY when
`account.is_superadmin === true`. Routes to `/app/admin/users`.

## Live verification

Raw DOM trace confirms the portal route renders and the route is
gated. Anonymous probe at `/app/admin/users` redirects to `/signin`;
admin probe at the same route renders the AdminUsers component.
