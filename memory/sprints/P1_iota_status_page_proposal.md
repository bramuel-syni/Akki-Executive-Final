# P1 ι — Status page proposal

**Date:** 2026-02
**Scope:** Recommend a public/internal status page approach for Akki.

## Why this matters at MVP scale

Cohort applicants + early-access users will email or DM when
something feels off. A status page lets them self-serve "is it me or
is it down?" before the email lands. For trust-pillar alignment
(Akki refuses to invent; we also refuse to be opaque about outages),
a public status page is a meaningful signal.

## Options

### Option 1 — In-app `/status` page reading internal health checks

**Shape:**
- New route `/status` (public, no auth)
- Frontend reads from `GET /api/public/status` which returns:
  ```json
  {
    "overall": "operational" | "degraded" | "outage",
    "components": {
      "api": {"status": "operational", "p95_ms": 142},
      "solva_engine": {"status": "operational"},
      "llm_router": {"status": "operational", "provider_health": {...}},
      "mongo": {"status": "operational", "p95_ms": 12},
      "email_send": {"status": "operational"}
    },
    "last_incident": {...} | null,
    "updated_at": "2026-02-…"
  }
  ```
- Background task (every 60s) hits each component, writes status to
  Mongo, served by the public endpoint
- Frontend renders component cards + last-incident card

**Integration cost:** **Medium** — ~250 LOC backend + ~120 LOC frontend.

**Pros:**
- Zero third-party dependency
- Truthful by construction (reads real internal health)
- Lives at our domain (no `status.akki.io` cert issue)

**Cons:**
- We host the page that says we're down (if it's down, the page is too)
- No incident-history archive without extra work
- No subscriber notifications

### Option 2 — Hosted (Better Stack / Instatus / statuspage.io)

**Shape:**
- Sign up with a hosted status-page provider
- Configure each component (API / Solva / Mongo / LLM)
- Provider pings our public health endpoints + their own probes
- Public page lives at `status.akki.io` or provider subdomain

**Integration cost:** **Low** — ~30 min of dashboard config + 0 LOC code.

**Pros:**
- Off-domain (page survives our outage)
- Built-in incident management + post-mortems
- Subscriber email/SMS notifications
- Historical uptime metrics

**Cons:**
- Cost: Better Stack starts ~$29/mo, Instatus ~$20/mo, statuspage.io $99/mo
- Third-party telemetry surface (some probe data leaves our perimeter)
- Lock-in on incident timeline data

### Option 3 — Hybrid (in-app + public mirror)

**Shape:**
- Option 1's `/status` page on our domain for fast user check
- Option 2's hosted page (cheapest tier — Instatus ~$20/mo) for
  off-domain survivability + subscriber notifications
- Hosted provider polls our `GET /api/public/status` endpoint as
  source of truth — single update surface

**Integration cost:** **Medium** — Option 1 LOC + Option 2 dashboard config.

**Pros:**
- Best of both: fast in-app status + off-domain survivability
- Subscriber notifications
- Single source of truth (our endpoint)

**Cons:**
- Two surfaces to maintain
- Cost (~$20/mo)

## Recommendation

**Option 3 — Hybrid.**

**Rationale:**
1. **Survivability** — hosted off-domain mirror covers the cluster-down
   scenario; the in-app page covers everything else.
2. **Single update surface** — our `GET /api/public/status` is the
   only place we declare component state; the hosted provider just
   mirrors it. No drift.
3. **Subscriber notifications** — cohort applicants + early-access
   users can subscribe to incident emails without us writing the SMTP
   loop ourselves.
4. **Cheap** — ~$20/mo with Instatus, the value-per-dollar is high
   for a public-trust surface.

**Voice-lint constraint:** the status component labels MUST be
voice-clean ("operational" / "degraded" / "investigating" /
"resolved" — no "senior", no marketing puffery). Incident copy goes
through the same voice-lint CI gate as marketing content.

## Pre-conditions

- User confirms hosted-mirror choice (Instatus vs Better Stack)
- We expose `GET /api/public/status` (Option 1 portion is built first)
- Status component definitions are locked in code (`backend/services/
  status_components.py` with the canonical list of monitored services)

## Classification

**IN-SCOPE for a P1 follow-on slice.** User decides between Options
1-3; this dispatch surfaces them and recommends Option 3.

## Estimated implementation (Option 3, both halves)

| Slice | LOC | Risk |
|---|---|---|
| Backend `GET /api/public/status` + cached aggregator | 180 | Low |
| Background health-check task (60s interval) | 70 | Low |
| Frontend `/status` route + component cards | 120 | Low |
| Voice-lint coverage on incident copy generator | 30 | Low |
| Hosted-mirror webhook wiring (Instatus → our endpoint) | 0 | None |

**Total:** ~400 LOC + a one-time Instatus account setup.
