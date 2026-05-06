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

## 2026-05-05 — Phase B.2 (chat two-pass) measurements

### D-010 · Phase B.2 latency budgets — measured baseline (Memo Item 8)
**Decision.** The brief's first-token budgets (trivial 500 ms,
light_substantive 800 ms, substantive_analytical 1.2 s,
strategic_deliverable silent 1.5 s, strategic_deliverable visible
2 s) describe the desired UX. The current chat infrastructure is
the **coarse-chunk fallback** documented in `routers/chat.py`
(comment lines ~1788–1791): the LLM SDK does not expose a streaming
primitive, so the server makes a one-shot synchronous LLM call and
chunks the completed reply at 220-char windows. Under that
architecture, "first-token" equals "first-chunk" equals roughly
the LLM call latency plus the classifier latency (≤ 1 ms heuristic
or ≤ 350 ms LLM-fallback) plus the Synisense pipeline cost. None
of the five classes meets the brief's first-token budget. The
budgets are aspirational for a future iteration that adopts true
SSE token streaming from the LLM SDK.

**Measured baseline (Phase B.2, 5 turns per class, admin account,
Claude Sonnet 4.5, dev preview):**

| Class                       | n | p50 first-token | p95 first-token | p50 total | p95 total |
|-----------------------------|---|-----------------|-----------------|-----------|-----------|
| trivial                     | 5 | 2 648 ms        | 3 055 ms        | ~2.7 s    | ~3.1 s    |
| light_substantive           | 5 | 2 646 ms        | 4 424 ms        | ~2.6 s    | ~4.4 s    |
| substantive_analytical      | 5 | 19 559 ms       | 49 686 ms       | ~19.6 s   | ~49.7 s   |
| strategic_deliverable silent | 5 | 20 655 ms       | 159 553 ms     | ~20.8 s   | ~159.8 s  |
| strategic_deliverable visible| 2 | 73 732 ms      | 235 159 ms     | ~74.9 s   | ~236.3 s  |

**Cause.** The two LLM-bound classes (`substantive_analytical`,
`strategic_deliverable`) are dominated by full-completion LLM
latency, not by classifier or Synisense work. `strategic_deliverable`
runs the canonical method as **two** LLM calls (Pass 1 reasoning
then Pass 2 deliverable) so the audit row always carries both
passes — this is correct per the memo, and a single-call
marker-based variant was tried first and rejected because Claude
Sonnet 4.5 omits the markers on roughly half of strategic turns.
Trivial and light_substantive are heuristic-classified in
sub-millisecond time; their first-token latency is also dominated
by the LLM call (Sonnet 4.5 even on "thanks" → ≥ 1.3 s).

**3 visible-mode runs in the latency table dropped due to a
transient `litellm.BadGatewayError 502` from the upstream provider
during the measurement window. The architecture itself functions
end-to-end on the runs that completed (pass_1_chars 9 136 and
10 637; show_pass_1=true; collapsible Pass 1 panel renders in the
UI).**

**Action.** Acceptance bar #8 ("If any class blows its budget, say
so verbatim") is fired: every class blows its budget under the
current coarse-chunk infrastructure. Recovery requires switching
to true SSE token streaming end-to-end, which is **out of scope
for B.2** — the existing B.1 chunking strategy was a deliberate
trade-off and replacing it is a separate phase. We log the
measurement honestly and ship.

---

### D-012 · Phase B.3 — true SSE token streaming (Memo Item 8 "token-level, not response-level")
**Decision.** Defer.

**Why.** The Emergent universal-key proxy (the only route the EMERGENT_LLM_KEY
is valid against) does not currently propagate token-level streaming — it
buffers the full LLM response and flushes all chunks at the end. Empirical
evidence: a 181-second Claude Sonnet 4.5 generation arrives as 126 chunks
within a 97 ms window at the end of the call (p50 inter-chunk interval =
0 ms). Direct provider routing (`litellm.acompletion(model="anthropic/...",
api_key=EMERGENT_LLM_KEY)`) returns 401 — the key is not a passthrough.
`emergentintegrations 0.1.0` exposes no streaming primitive. The integration
playbook does not document a streaming surface for the universal key.

**Implication.** Phase B.3's acceptance budgets (1.5 s / 2 s / 3 s p95
first-token) are structurally unmeetable on the current platform. Shipping
a litellm.acompletion(stream=True)-based path would replace one
buffered code path with another buffered code path while increasing
complexity in chat.py — the user-facing first-token latency would not
change.

**Path forward (one of):**
1. The user provides direct Anthropic + Google API keys in `backend/.env`.
   B.3 then becomes: keep `emergentintegrations` for non-chat surfaces,
   route chat through `anthropic.AsyncAnthropic.messages.stream(...)` and
   `google.generativeai.GenerativeModel.generate_content(stream=True)`
   directly. Keys add risk surface (per-provider rotation, per-provider
   spend visibility) but unlock real token streaming.
2. The Emergent platform team enables incremental forwarding on the
   `/llm` proxy. No code change on our side; we revisit this decision
   automatically.

Until either path lands, we keep the B.1 coarse-chunk fallback. The
audit chain, the Synisense surfaces, and the deterministic refusal path
all remain correct under the current model.

Standby keys held in `/app/.secrets/B3_standby_keys.md` (gitignored). Do not activate without explicit greenlight.

---

## How to add a new decision

1. Heading: `### D-NNN · <one-line title> (Memo Item X)` — increment NNN.
2. Body: short. Decision in 1–3 sentences. Why in 1–3 sentences if
   non-obvious. Deferrals listed explicitly.
3. Date the section above it. Never modify a previous entry.
