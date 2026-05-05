# AKKI — Memo Decisions Log

> The locked PM decisions on top of `docs/MEMO.md`. Every decision
> below was either explicit in the memo or signed off in chat with
> the founder. Items below are NOT up for re-debate during phase
> execution; if an implementer wants to revisit one, they raise it
> at the next planning round, not mid-phase.
>
> This document is append-only. New decisions go at the bottom with a
> dated heading. Do NOT edit historical entries.

---

## 2026-05-05 — Initial decisions seeded with the new roadmap

### D-001 · Cycle Manager forwarding alias (Memo Item 3)
**Decision.** Cohort users get a forwarding alias in the form
`akki+<slug>@syni.ai` (e.g. `akki+bram@syni.ai`). Inbound mail to
that alias lands in the user's Cycle Manager queue via the existing
Postmark inbound webhook.

**Deferred.** OAuth integrations to Gmail/Outlook calendar/mail are
deferred to the **Organisational tier** (post-Phase H). Reportee
calendar invites and meeting-pull are NOT in scope before that.

### D-002 · Workspace Export rendering (Memo Item 2)
**Decision.** Phase C (Workspace) ships the deterministic template
engine first — `python-pptx` + `python-docx` against a designed
template set. LLM-composed layout ships **later** behind an explicit
"creative" toggle. Default behaviour is the deterministic path.

**Why.** A board-pack export that gets the typography right every
time is the trust-building outcome; an LLM-composed layout that's
80% correct degrades trust. Determinism first, creativity behind a
flag.

### D-003 · NED-side Cycle Manager (Memo Item 3 founder override)
**Decision.** The memo puts NED-side Cycle Manager
out-of-scope for the Executive rebuild. Founder override: **the
NED-side journey gets a design document during this rebuild — design
only, not build.** Live engineering effort stays on the Executive
flow until the design ships.

**Deliverable.** During Phase D (Cycle Manager Executive flow),
produce `docs/NED_CYCLE_MANAGER_DESIGN.md` outlining:
- The NED catch-up journey (preparing for an upcoming board)
- The cycle-monitoring journey (post-meeting follow-up + minutes
  consumption)
- How NED-side surfaces consume the Executive Cycle's outputs
- What's deliberately deferred until a follow-on phase

The design document does NOT obligate any frontend or backend
implementation in Phase D.

### D-004 · Multi-tab role behaviour (Memo Item 5)
**Decision.** Each browser tab is its own session. Active context is
held **per-tab** in `sessionStorage` (NOT `localStorage`). Two tabs
in the same browser, in different contexts, operate independently.

**Server contract.** Authenticated SPA calls attach
`X-Active-Context` from sessionStorage. Server resolves role fresh
from `db.memberships` on every request keyed by
`(account_id, X-Active-Context)`. Role is **never** cached in the
JWT.

### D-005 · Header-only X-Active-Context, no cookie fallback (Memo Item 5 follow-up)
**Decision.** Header-only. No cookie fallback (a cookie would
silently break the multi-tab isolation in D-004). Public endpoints
(`/api/health`, `/api/docs`, `/api/openapi.json`, auth endpoints,
`/respond/{token}`) are unaffected — they have no membership
concept.

**Client behaviour.** If the SPA has no active context cached for
this tab, it calls `GET /api/me/contexts` first, then:
- 1 membership → auto-select, stash in sessionStorage, proceed
- 2+ memberships → redirect to a "Pick a context" screen (full-screen
  switcher)
- 0 memberships → log out with a clean message (only happens for a
  removed user)

**Server behaviour.** Membership-required routes that receive no
`X-Active-Context` header → `400` with code
`ACTIVE_CONTEXT_REQUIRED`. Server does NOT default to the user's
first/oldest membership — the client picks.

**Ops note.** curl probes and the OpenAPI "Try it out" Swagger UI
must send `X-Active-Context`. The header is documented in the
OpenAPI schema with a `parameters` entry.

### D-006 · Homepage "All documents" button — show count (Memo Item 1)
**Decision.** YES — include a count badge ("All documents · 47").
Light addition that increases discoverability without congesting the
surface.

### D-007 · Document Journal main-menu replacement (Memo Item 1)
**Decision.** Collapse the menu by one item. Do **NOT** promote
another item into the slot. The freed slot becomes whitespace; the
nav gets shorter, not denser.

**Phase note.** This decision lands in **Phase E** (Documents
Journal rewire), NOT Phase A. Phase 1's "Document Journal" nav entry
stays in place until Phase E moves it.

---

## How to add a new decision

1. Heading: `### D-NNN · <one-line title> (Memo Item X)` — increment NNN.
2. Body: short. Decision in 1–3 sentences. Why in 1–3 sentences if
   non-obvious. Deferrals listed explicitly.
3. Date the section above it. Never modify a previous entry.
