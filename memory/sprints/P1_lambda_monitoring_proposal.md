# P1 λ — Monitoring / alerting stack proposal

**Date:** 2026-02
**Scope:** Recommend an observability stack for Akki at MVP scale.

## Target shape

- Error tracking (JS + Python exceptions)
- Performance tracing (request → DB query → LLM call)
- Web-vitals (LCP / INP / CLS) p75 from real users
- Slack alerting on error spikes + p95 latency breaches
- Privacy-conscious (no PII leakage; founder + cohort applicants
  reasonably expect their session payloads NOT to surface in a
  third-party dashboard verbatim)

## Options

### Option 1 — Sentry (SaaS, hosted)

**Features:**
- JS + Python SDKs (well-supported)
- Distributed tracing
- Performance + web-vitals
- Slack/email/PagerDuty alerting
- Source map upload (deminified stack traces)
- Privacy controls — server-side PII scrubbing, sample rate

**Integration cost:** **Low** — 30 min wiring per service.
- Frontend: `@sentry/react` ~80 LOC + DSN env var
- Backend: `sentry-sdk[fastapi]` ~40 LOC + DSN env var
- Source map upload in CI pipeline

**Pricing tier (our load):** Team plan (~$26/mo) covers 50k errors + 100k spans.
Free tier (5k errors/mo) likely sufficient for the first 3 months.

**Deal-breakers:** None for MVP. SaaS-only (no on-prem). EU data
residency available on Business+ tier.

### Option 2 — Highlight (SaaS, hosted, session replay focus)

**Features:**
- Full session replay (DOM, console, network)
- Error tracking + tracing
- Modern UX dashboards
- Slack alerting

**Integration cost:** **Low** — single npm package + DSN
- Frontend: `highlight.run` ~30 LOC
- Backend: limited Python coverage vs Sentry

**Pricing (our load):** ~$50/mo for 10k sessions. Free tier 500 sessions/mo.

**Deal-breakers:**
- Session replay is privacy-heavy — captures DOM + form fields by
  default. For a founder + NED clientele where session content is
  literally board-pack material, **replay-by-default is wrong**.
- Server-side coverage thinner than Sentry.

### Option 3 — Self-hosted Glitchtip + Grafana stack

**Features:**
- Glitchtip = Sentry-API-compatible OSS, runs in our cluster
- Grafana + Loki for logs + metrics
- Tempo for distributed traces
- Slack via Alertmanager

**Integration cost:** **High** — 1–2 weeks setup + ops.
- Cluster provisioning (CPU/RAM allocation for Glitchtip + Grafana + Loki + Tempo)
- Backup of telemetry DB
- Ongoing maintenance / upgrades

**Pricing (our load):** Compute cost only (~$30/mo for a small node).
No per-event pricing.

**Deal-breakers:**
- Operational burden too high pre-revenue.
- Adds another piece of infra to own.
- No mature SDK distribution; we'd be on the same Sentry SDKs but
  pointing at our Glitchtip — works but is fragile on upgrade.

## Recommendation

**Option 1 — Sentry.**

**Rationale:**
1. **Lowest integration cost** — 30 min per service, well-supported
   Python + React SDKs.
2. **PII-conscious by default** — server-side scrubbing rules can be
   configured before any event ships; we keep board-pack data off the
   third-party dashboard.
3. **Free tier covers MVP** — 5k errors/mo is more than enough for
   pre-revenue load.
4. **Trace + web-vitals + errors in one place** — no stack juggling.
5. **Slack alerting native** — no separate Alertmanager configuration.
6. **EU data residency available** — when we hit the trigger that
   justifies the Business plan.

**Pre-conditions before wiring:**
- User confirms SaaS + EU/US data residency choice
- User provides Sentry Org Slug + creates the project
- User shares DSN secrets for frontend + backend
- We configure server-side PII scrubbing rules (default-deny on
  Solva session payload + cohort form fields)

**Classification:** **IN-SCOPE** (build, not propose). User decides
between Options 1-3; this dispatch surfaces them and recommends 1.

## Estimated implementation (Option 1)

| Slice | LOC | Risk |
|---|---|---|
| Backend `sentry-sdk` integration + DSN env var | 40 | Low |
| Frontend `@sentry/react` integration + DSN env var | 80 | Low |
| Server-side scrubbing rules (Solva payloads + cohort PII) | 30 | Low |
| Source-map upload script + GitHub Actions step | 50 | Low |
| Slack webhook configuration (Sentry-side, no code) | 0 | None |

**Total:** ~200 LOC + a one-time Sentry project setup.

**Voice-lint clean:** no user-facing copy introduced. Error fallbacks
in frontend ErrorBoundary will need voice-lint review.
