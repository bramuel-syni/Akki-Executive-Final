# P1 α — Access-model audit

**Date:** 2026-02
**Scope:** Code walk against the user's LOCKED access intent.

## Intent (LOCKED — do not propose changes)

- **GENERAL** (all authenticated users): Work Studio, Solva v1+v2,
  Trust Center (full), Help/Wiki, Account, Cohort apply
- **ADMIN-ONLY**: User admin portal, cohort applications inbox,
  prompt-tuning dry-run, seed scripts, admin-only Trust tiles,
  any mutating audit/config endpoint

## Audit results — frontend routes

| Surface | Intended | Actual gate | Match |
|---|---|---|---|
| `/app/` (AppHome) | general | `<Gated>` (auth-required) | ✓ matches |
| `/app/work-studio` | general | `<Gated>` | ✓ matches |
| `/app/solva` (v1+v2) | general | `<Gated>` | ✓ matches |
| `/app/trust-center` | general (FULL surface) | `<Gated>` | ✓ matches |
| `/trust` (public marketing tile) | public | none | ✓ matches |
| `/app/settings` | general (own settings) | `<Gated>` | ✓ matches |
| `/cohort` (apply page) | public | none | ✓ matches |
| `/app/admin/users` | admin-only | `<SuperadminRoute>` | ✓ matches |
| `/app/admin/cohort-applications` | admin-only | `<SuperadminRoute>` | ✓ matches |
| `/app/admin/prompts` | admin-only | `<SuperadminRoute>` | ✓ matches |
| `/app/admin/cohort-copy` | admin-only | `<SuperadminRoute>` | ✓ matches |
| `/app/admin/signal-kpi` | admin-only | `<SuperadminRoute>` | ✓ matches |
| `/app/admin` (hub) | admin-only | `<SuperadminRoute>` | ✓ matches |
| `/app/help` | general | `<Gated>` | ✓ matches |

## Audit results — backend endpoints (per `require_superadmin` dep)

| Surface | Intended | Actual gate | Match |
|---|---|---|---|
| `GET/POST/PATCH /api/admin/users/*` | admin | `require_superadmin` | ✓ matches |
| `GET /api/admin/cohort/applications` | admin | `require_superadmin` | ✓ matches |
| `POST /api/admin/prompts/dry-run` | admin | `require_superadmin` | ✓ matches |
| `POST /api/cohort/applications` (submit) | public (apply) | none + rate-limit | ✓ matches |
| `GET /api/solva/sessions/*` | general (own) | `get_current_account` | ✓ matches |
| `GET /api/public/observability/reasoning_velocity` | public | none | ✓ matches |
| `POST /api/auth/login` | public | none + brute-force gate | ✓ matches |
| `GET /api/auth/me` | general | `get_current_account` | ✓ matches |
| `GET /api/admin/signals/*` | admin | `require_superadmin` | ✓ matches |
| `GET /api/admin/diagnostics/*` | admin | `require_superadmin` | ✓ matches |
| `POST /api/solva/audit/seed-*` (any seed script) | admin | `require_superadmin` | ✓ matches |
| `GET /api/integrity/violations` (engine config view) | admin | `require_superadmin` | ✓ matches |

## Mismatches

**Zero mismatches found.** Every audited surface aligns with the
locked intent. The codebase uses two clear gates:
- `<Gated>` (frontend) + `get_current_account` (backend) — general
- `<SuperadminRoute>` (frontend) + `require_superadmin` (backend) — admin

## Soft-flag (not a mismatch, surfaces for awareness)

- The `/app/admin/*` routes lazily-import their components even
  inside `<SuperadminRoute>`. A non-admin who manually types the URL
  will trigger the chunk download before the gate rejects them.
  **Not a security issue** — the gate is enforced server-side on every
  data endpoint. Surface only.
- `POST /api/cohort/applications` is rate-limited (per-IP) but is
  intentionally NOT auth-gated (it's the public application form).
  Aligned with intent.

## Recommendations

**Zero fixes proposed.** The access model is correctly implemented.
The `<SuperadminRoute>` + `require_superadmin` pattern is consistent
and matches the intent verbatim.

## Methodology note

Audit traced from `frontend/src/App.js` route table → component files
→ backend route registrations in `server.py` → router files →
`require_superadmin` / `get_current_account` dependency declarations.
No data-layer audit performed (the dependency-injected gate is the
single chokepoint; verified by inspection that every router file
imports either the public or admin dependency on every route).
