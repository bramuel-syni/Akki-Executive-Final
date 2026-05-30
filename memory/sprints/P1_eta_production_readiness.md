# P1 η — Production-readiness audit

**Date:** 2026-02
**Scope:** Concrete pass/fail checklist for production-grade MVP launch.
**Tier:** Each item is **pass** / **fail** / **partial** / **unknown** / **N/A**.

## Summary table

| Category | Status | Notes |
|---|---|---|
| Secrets hygiene | **partial** | env-only, no rotation runbook, no scrubbing in logs |
| Security headers | **fail** | no global HSTS / CSP / X-Frame-Options / Referrer-Policy / Permissions-Policy middleware |
| Rate limiting | **partial** | brute-force on auth/login only; no per-route, per-IP, per-user rate limit |
| CORS scoping | **pass** | explicit allow_origins from env; preflight handled |
| Frontend error boundaries | **fail** | no top-level ErrorBoundary in active code; archived one exists |
| Backend 500/422 surfaces | **pass** | FastAPI default; validators surface structured payloads |
| Observability — logs | **partial** | logging present; no structured JSON shipping |
| Observability — traces | **fail** | no OpenTelemetry / Sentry / Highlight wired |
| Backup/restore (Mongo) | **fail** | no scheduled backup pipeline, no restore drill |
| GDPR/DPA copy on public Trust | **partial** | Trust Center has policy bullets; no formal DPA/SCC |
| Accessibility (WCAG AA) | **partial** | testids + ARIA labels in admin portal; no audit |
| Perf budget (LCP/INP/CLS p75) | **unknown** | no in-place perf measurement |
| Solva SSE load test at N concurrent | **fail** | no load test exists |
| Audit-log retention | **partial** | written but no TTL/index policy declared |
| Abuse controls (signup/email throttle) | **partial** | cohort form has per-IP rate limit; no signup throttle |
| Secret rotation runbook | **fail** | no document |
| Service health endpoints | **partial** | `/api/health` returns 200; not aggregated |

## Detailed audit

### Secrets hygiene — **partial**

| Item | State | Evidence | Gap |
|---|---|---|---|
| All secrets via .env | pass | `/app/backend/.env` houses `MONGO_URL` + 19 *_KEY/_SECRET/_TOKEN vars | — |
| `.env` not committed | pass | `.gitignore` excludes; `git diff` confirms | — |
| Secrets scrubbed from logs | partial | `_ms_audit_filter()` removes secrets in MS OAuth audit logging; not enforced suite-wide | Audit `log.info/error` calls for token/key leakage |
| Rotation runbook | fail | none | Write runbook (see κ) |
| Secret expiry / rotation | unknown | no `*_EXPIRES_AT` env vars | Add 90-day rotation for OAuth client secrets |

### Security headers — **fail**

No global middleware sets HSTS / CSP / X-Frame-Options / Referrer-Policy / Permissions-Policy.
Some routes (`/api/product/features`) set `X-Content-Type-Options: nosniff` per-response, but
this isn't applied globally. **Recommended fix:** add a `SecurityHeadersMiddleware`
that sets these headers on every response. Estimated 30 LOC + 1 test.

### Rate limiting — **partial**

- ✓ `/api/auth/login` — brute-force gate, 429 after N failed attempts (`auth.py:104`).
- ✓ `/api/cohort/applications` — per-IP rate-limit on submit.
- ✗ No global per-IP or per-user limiter (e.g. SlowAPI).
- ✗ No per-route ceilings on Solva, Work Studio, Trust observability.

**Recommended fix:** mount SlowAPI on the app with sane defaults (200 req/IP/min,
40 req/account/min on `/api/solva/*` SSE start endpoints).

### CORS — **pass**

`server.py:406` mounts `CORSMiddleware` with explicit `allow_origins` from env
(not `*`). Preflight handled per Starlette default; credentials supported.

### Frontend error boundaries — **fail**

No active `<ErrorBoundary>` wraps `<App />`. An archived boundary exists in
`_archived_legacy/components/cycle/ReportsTab.jsx.archived`. **Recommended:**
add a `<RootErrorBoundary>` to `App.js` that logs to the observability stack
and surfaces a user-readable fallback. Estimated 60 LOC + 1 test.

### Backend 500/422 surfaces — **pass**

FastAPI default exception handler emits structured 422 payloads on validation.
Integrity validators emit `ValidatorOffender` shape with location + revision_hint.
Solva v2 router returns 422 with `error: "integrity_validation_failed"` on block.

### Observability — partial / fail

- ✓ `logging.getLogger()` used in routers; structured-ish format.
- ✗ Not shipped to a central store (no Sentry, no Highlight, no OpenTelemetry).
- ✗ No trace IDs propagated across requests.

See `P1_lambda_monitoring_proposal.md` for the recommended stack.

### Backup/restore — **fail**

- No scheduled `mongodump` cron, no S3 / GCS backup target.
- No restore drill performed.

**Recommended:** nightly `mongodump --uri=$MONGO_URL --archive=/backups/$DATE.gz --gzip` →
ship to S3 with 30-day retention; weekly restore drill into a staging DB.

### GDPR/DPA on public Trust — **partial**

The public `/trust` page surfaces principle-level Trust pillars + the reasoning
velocity tile. No formal Data Processing Agreement, no SCC text, no cookie banner.

**Recommended:** add `/legal/privacy`, `/legal/dpa`, `/legal/terms` static pages
backed by `legal/*.md` content. Cookie banner via lightweight in-app component
(no third-party tracker).

### Accessibility — **partial**

- ✓ Buttons + inputs across admin portal have `data-testid` + `aria-label`.
- ✓ Trust Center back button (β) includes `aria-label="Back"` + `aria-hidden="true"` on arrow.
- ✓ Microsoft OAuth button has `aria-label` and proper `disabled` semantics.
- ✗ No formal Axe/Pa11y audit run.
- ✗ Keyboard navigation across the Work Studio editor unverified.
- ✗ Color contrast not formally measured at WCAG AA.

### Perf budget — **unknown**

- No `web-vitals` instrumentation, no Lighthouse CI gate, no p75 measurement.

**Recommended:** instrument `web-vitals` → ship metrics to the observability
stack; add Lighthouse CI on every PR with budget gates (LCP ≤2.5s, INP ≤200ms,
CLS ≤0.1).

### Solva SSE load test — **fail**

No load test exists. **Proposed N = 50 concurrent SSE streams** to cover
the realistic "small cohort + occasional NED visit" peak. Run via k6 or
Locust against a staging deployment, hold for 10 min, measure:
- SSE stream stall rate
- p95 TTFB on `/api/solva/sessions/{sid}/v2/stream`
- backend memory growth
- LLM router queue depth

### Audit-log retention — **partial**

- ✓ `chat_audit_log` and engine `reasoning_audit_log` are written.
- ✗ No TTL index. **Recommended:** 365-day TTL on `audit_log`; permanent on
  `reasoning_audit_log` (artefact integrity); 90-day on transient action logs.

### Abuse controls — **partial**

- ✓ Cohort form per-IP rate-limit.
- ✓ Auth brute-force gate.
- ✗ No signup throttle (sign-up not yet open to public — N/A until public sign-up).
- ✗ No mass-email throttle (SendGrid per-day quota enforced upstream, not in app).

### Secret rotation runbook — **fail**

None. See κ deliverable (5 runbooks added this dispatch; secret rotation
should be a P1 follow-on).

## Critical-path prioritisation

Top 5 fixes to land before "production-grade" claim is honest:

1. **Global SecurityHeadersMiddleware** (CSP + HSTS + X-Frame + Referrer + Permissions). LOC ~30.
2. **RootErrorBoundary in App.js** + ship errors to observability stack. LOC ~60 + monitoring wiring.
3. **Sentry-or-equivalent wiring** (see λ proposal). LOC ~80 + dashboards.
4. **Mongo backup pipeline** (cron + S3 ship + restore drill). Ops-only.
5. **Legal pages stack** — `/legal/privacy` + `/legal/dpa` + `/legal/terms` + cookie banner. ~250 LOC content + minor component.

None landed in this dispatch (η is report only).
