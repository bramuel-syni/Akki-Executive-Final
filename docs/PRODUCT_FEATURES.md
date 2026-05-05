# AKKI — Product Features & Functionality

Internal product status, as built. Last reviewed: 4 May 2026 · branch `main` · commit `332a423`.

AKKI is an intelligence layer for corporate governance. It serves two primary personas — non-executive directors (NEDs) who sit on multiple boards, and C-suite executives who run reporting cycles into those boards — and one secondary persona, the reportee, a line executive who feeds information upward through AKKI. The product is built around three editorial principles: privacy by default (anything leaving a surface is de-identified first), grounded output (nothing asserted without a traceable source), and a dry, specific voice closer to the Financial Times than to a productivity app.

This document is the internal view of what has been built, what is partially built, and what is not yet in code. It is not marketing copy.

### How to read this document

Status legend:

- **Shipped** — present in code, exercised by tests or user flows, usable today.
- **Partial** — the contract exists and the happy path works, but sub-capabilities from the roadmap are not yet coded.
- **Pending** — not in code. Reserved nomenclature only.
- **Placeholder** — UI surface exists so users discover the feature, but the engine is not built.

Anything marked Pending or Placeholder must not be described to prospects as a current capability.

## At-a-glance status matrix

| Feature | Status | One-line summary | Phase |
|---|---|---|---|
| Synisense Shield | Shipped | Three-layer PII de-identification with AES-GCM shield maps and surface-scoped TTLs | 12 |
| Solva v1 (4-phase engine) | Read-only forensic | POSTs retired in Phase A; six GETs preserved at `/api/solva/*` for historical session inspection | 11 / Phase A |
| Solva v2 (engine) | Shipped | Reasoning tier, four sub-modules, tension detector, grounding contract, guardrail ladder, reflection layer | 15.0–15.3.5 |
| Solva v3 (UI rebuild) | Shipped | Single-column Guided Flow at `/app/solva/session/*`, 4-card centred landing, composed artefact with animated probability bars, PDF + DOCX export, refusal artefact, WCAG AA contrast | Phase I (2026-05-05) |
| Work Studio | Shipped | Block editor with deterministic sensitivity and exposure scoring | 13.3 |
| Cycle Manager | Shipped | Briefs, Signals, Minutes, Actions and Reports under one surface | 13.2 |
| Akki Pulse | Placeholder | Holding page only; aggregator and Privacy Wall unbuilt | 14 |
| Privacy Wall | Pending | No metadata-only projection guard in cross-context reads | 14 |
| Daily Review | Shipped | Batched approval queue for AKKI-generated artefacts | pre-Phase-12 (iter-level) |
| Reportee Accounts (tokenised contacts) | Shipped | Email-token reportees with public reply endpoint | 13.2 |
| Reportee Accounts (sub-accounts with login) | Pending | Full schema, reduced surface, billing | 16 |
| Contexts model | Shipped | Four board-seat types with embedded committees | pre-Phase-12 (iter-level) |
| Redacted Read-Only / Share-with-the-Chair | Shipped | Public token routes with hard 500-guard on redaction contract | 11 / 12.2 |
| Chat & LLM routing | Shipped | Tiered Claude / Gemini / GPT via Emergent Universal Key | 11 |
| Auth, MFA, RBAC | Shipped | JWT + refresh, TOTP MFA, context-membership RBAC | pre-Phase-12 (iter-level) |
| Billing (Stripe) | Partial | Wired end-to-end; disabled via `BILLING_ENABLED=false` | 16 |
| Outbound email (Resend) | Partial | Integrated; noop mode because key unset | 18 |
| Inbound email (Postmark) | Shipped | Per-context tokens, webhook ingestion, triage queue | 9–10 |
| File storage + ClamAV | Shipped | S3/MinIO via boto3; ClamAV scan is a hard precondition | 10 |
| Observability (Sentry) | Pending | DSN commented out; no SDK initialisation | 18 |
| Scheduling | Shipped | APScheduler in-process; single-replica caveat | 18 leader election |

"pre-Phase-12 (iter-level)" denotes work completed across the iter-numbered history before the current 12→19 phasing was adopted.

## Synisense Shield

### What it does

Synisense Shield is AKKI's in-house de-identification pipeline. Before text leaves any surface — a chat turn sent to a model, a draft deck serialised for review, an artefact published to an external chair — Shield removes or tokenises PII and commercially sensitive content. Where reversibility is needed, Shield stores an encrypted envelope keyed to the run so the original can be recovered server-side. Nothing un-redacted crosses an external boundary.

### How it works today

Three layers run in sequence: a regex fast-path with nine surgical patterns (IBAN, email, phone, credit card, SSN, NHS, IP, URL, exact dates), a Presidio layer backed by spaCy `en_core_web_sm`, and an LLM fallback that classifies only low-confidence Presidio hits. The fallback is capped at 20 spans per document, concurrency-limited, and timeout-bounded at 2 seconds. Replacement tokens are deterministic within a single run: the same match in the same document always gets the same token.

Reversible shields land in `synisense_shield_maps` with AES-GCM envelope encryption and a TTL index — one hour for `public_read`, 24 hours by default, seven days hard maximum. Every run writes an audit row to `synisense_runs` carrying only the SHA-256 of the input, never the original text. A perf ring buffer feeds `/api/admin/synisense/perf`. Seven surfaces are wired: chat, ingest, briefing, deck, report, solva, public_read. On boot the service refuses to start in production without `SYNISENSE_MASTER_KEY`; a dev escape hatch (`SYNISENSE_ALLOW_INSECURE=true`) prints a stderr warning every 60 seconds.

### What's still pending

The engine is complete against its Phase 12.1 contract. Outstanding work: the Phase 12.3 marketing-honesty pass in `docs/SYNISENSE_SCOPE.md`, and extended pattern coverage as design partners surface new sensitive-entity classes.

## Solva

### What it does

Solva is AKKI's decision-support surface. A Solva session takes an executive through a structured diagnostic on one question — a strategic knot, a risk call, a capital-allocation decision. It surfaces the question, deepens it with grounded context, synthesises a position, and locks in next steps that can be handed to a briefing, a deck, or a reporting cycle.

### How it works today (v3 UI on the v2 engine)

The **Solva v3 UX** is shipped (Phase I, 2026-05-05). The user-facing flow is now a single-column, linear Guided Flow:

```
LANDING (4 picker cards, centred, collapsible Recent Sessions)
  → FRAMING (one prompt: "Tell me about the situation you're trying to think through.")
  → Q1 → Q2 → Q3        (round 1 of grounding questions)
  → DEPTH_Q1 → DEPTH_Q2 → DEPTH_Q3   (deeper round, against tinted background)
  → PREPARING (centered "Putting this together." interstitial)
  → ARTEFACT (the composed read)
  → REFLECT_1 → REFLECT_2 → REFLECT_3   (opt-in side-trip from the artefact)
  → COMPLETE (returns to artefact with "Session saved" toast)
```

The cluster picker is gone from the UI. The backend resolves a cluster from the framing intent via the new `_resolve_auto_cluster` keyword heuristic when `auto_cluster=true` (default). Card 04 user-facing label is **"See Different Perspectives"**; the backend submodule key remains `get_perspective`. Refusal sessions interrupt the flow and route to a 4-section refusal artefact (`SolvaRefusalArtefact.jsx`) in place of the standard composition.

The composed **artefact** has 5 fixed sections:
1. **Masthead** — sub-module label, persona (when applicable), one-line framing, date · duration · cluster label, top-right Download dropdown (PDF / DOCX).
2. **Primary diagnosis** — the synthesis paragraphs with `[T:tier]` markers stripped, rendered in Georgia 18pt.
3. **Scenarios** — animated probability bars (600 ms ease-out, instant under `prefers-reduced-motion`) with confidence-interval extension and ARIA labels.
4. **Sensitivity drivers** callout (CREAM background, accent rules) — what would change this read.
5. **Surfaced tensions** callout (CREAM_DEEP background, left accent rule) — where framing and evidence diverge.

The "How Solva reasoned this" expandable below pulls a shaped projection of `reasoning_audit_log` from `GET /api/solva/v2/sessions/{sid}/artefact-reasoning` into 4 sub-sections (candidates / triangulation / weighting breakdown / full audit log table).

### Backend engine (Solva v2 — unchanged in Phase I)

The reasoning engine is the four-layer state machine `framing → grounding → [hypothesis] → synthesis → reflection`, with 4 named sub-modules (`seek_clarity`, `develop_strategy`, `simulate_hypothesis`, `get_perspective`), a 5-tier grounding contract, the tension detector, the guardrail ladder, the no-opinion filter, and the validator pass. Implementation in `backend/services/solva_v2/`. Tiering follows account plan (free: Sonnet 4.5; Pro: Opus against a separate budget). Handoffs are first-class — at completion a session can convert into a briefing draft, a deck outline, or a cycle question set via `POST /api/solva/v2/sessions/{sid}/handoff/cycle`. The session document persists `synthesis.body`, `synthesis.claims[]`, `reasoning_audit_log[]`, and `reflection.responses[]`.

### Export

Both the standard artefact and the refusal artefact export to PDF (WeasyPrint, ~30 KB typical) and DOCX (python-docx, ~37 KB typical) via:

- `GET /api/solva/v2/sessions/{sid}/export.pdf`
- `GET /api/solva/v2/sessions/{sid}/export.docx`

Endpoints are auth-gated; refusal sessions return `X-Solva-Artefact: refusal` so downstream tooling can branch. Implementation in `backend/solva_artefact_export.py` + `backend/templates/solva_artefact.html` and `solva_refusal_artefact.html`.

### Solva v1 (read-only forensic)

The pre-v2 engine remains accessible read-only for historical session inspection: 6 `GET /api/solva/*` endpoints (clusters, sessions, handoffs, export.pdf). All v1 POSTs were retired in Phase A.

## Work Studio

### What it does

Work Studio is the surface where executives write. It merges what used to be Decks, Reports and Briefings into a single block-based editor with a lifecycle state machine and automatic sensitivity and exposure scoring at save time.

### How it works today

The composer lives at `/app/work-studio` and `/app/studio/composer/:kind/:artefactId`. Blocks are CRUD-managed under `/api/studio/{kind}/{artefactId}/blocks` with move, reorder, upload-image and lifecycle endpoints. Lifecycle is explicit: draft → submit-review → approve → send. On save, the composer passes the flat text through Synisense Shield and stores both the original and the redacted projection (`body_redacted`). Every downstream path that serves content externally reads `body_redacted` and nothing else.

The sensitivity engine in `backend/studio_sensitivity.py` is deterministic. It scores 0–100 against a rules ladder — M&A language (+20), conduct/HR (+20), litigation/regulator (+15), unannounced financial figures (+15), restructure/redundancy (+15), insider/MNPI (+10), customer/contract concentration (+10), named executives (+5), unannounced dates in the next 90 days (+5) — capped at 100. The score maps to a four-class ladder matching NACD/IoD convention:

- 0–24 PUBLIC
- 25–49 INTERNAL
- 50–74 CONFIDENTIAL
- 75–100 RESTRICTED

An LLM is used only as a tiebreaker when keyword signals are ambiguous, so the classification is auditable and reproducible. Exposure is scored separately from unique readers, share count, external-share count and staleness.

### What's still pending

Per-deck detail editing still routes to the legacy `pages/Decks.jsx` component; migrating it into the block composer is a Phase 13 tail item. Per-slide (rather than per-artefact) Synisense redaction is not persisted — public-read surfaces serve the flat redacted body in a single slide.

## Cycle Manager

### What it does

Cycle Manager is the structural surface for executives running reporting cycles: quarterly board preparation, monthly ExCo packs, regulatory filings, committee papers. It consolidates Prepare, Highlights, Briefings and the old Cycle surface into one five-tab hub: Briefs, Signals, Minutes, Actions, Reports.

### How it works today

The shell at `frontend/src/pages/Cycle.jsx` renders the tabs; each tab is a self-contained component in `frontend/src/components/cycle/tabs/`. The Actions tab is backed by a Phase 13.2 aggregator at `GET /api/contexts/{cid}/cycle/actions` that merges three existing data sources — open signal actions, in-flight plays, pending cycle submissions — without introducing new collections.

The cycle workflow is intact. Reportees are managed under `/api/contexts/{cid}/reportees`. Checklists are drafted LLM-tailored per reportee and dispatched via email (noop today — see Outbound email). Reportees respond through a public tokenised route `/api/respond/{token}` requiring no login. Submissions land in an inbox, compose into reports, go through review and send-up, and export as PDF or slide-deck PDF. A weekly cron at `/api/cycle/cron/run-schedules` advances scheduled cycles automatically. Legacy URLs redirect cleanly: `/app/prepare`, `/app/highlights`, `/app/briefings` land on the appropriate tab.

### What's still pending

Functionally complete against Phase 13.2. Outstanding operational items: retire legacy redirect targets in Phase 14, move schedule leader-election off in-process APScheduler in Phase 18.

## Akki Pulse

### What it does (the contract Phase 14 must honour)

Pulse is the cross-board lens. For an NED sitting on three or more boards, Pulse surfaces patterns appearing across boards — capital pressure, succession risk, regulatory drift, cyber exposure — with source attribution back to the originating board. Pulse is the surface where Privacy Wall is load-bearing: aggregation reads metadata only (severity, topic, timestamps), never content, because content is bound to the board it came from. For executives rather than NEDs, Pulse inverts: within-organisation change detection across reportee submissions, cycle deltas, and inbound triage.

### How it works today

It does not. `/app/pulse` renders `frontend/src/pages/PulsePlaceholder.jsx`, an honest holding page explaining the feature is deferred to Phase 14 and linking the user to `Cycle Manager → Signals` for per-board equivalents. The nav slot is wired so users discover Pulse rather than 404. No aggregator endpoint exists. No cross-context projection code exists. No `PulseDigest` cron exists.

Worth noting: today's `GET /api/me/home/stream` aggregates cross-context shares purely by membership. It does not enforce a content-vs-metadata split. That plumbing is Privacy-Wall-unsafe in its current form and must be refactored before Phase 14 can wire a real aggregator on top.

### What's still pending

Everything: the aggregator, the metadata-only projection guard, the LLM-classified entity taxonomy (cyber, capital, succession, regulatory), the NED cross-board view with source attribution, the executive within-org view, the 07:00 UTC daily `PulseDigest`, and the non-blocking in-app toast for new Pulse items.

## Daily Review

### What it does

Daily Review is the batched approval queue. AKKI generates a volume of draft artefacts — suggested briefings, signal classifications, edits — and the executive approves, rejects or edits them in one sitting rather than being interrupted per item.

### How it works today

The router at `/api/me/review-queue` exposes the queue, per-kind counts, and approve/reject/edit handlers. The page at `/app/review` is reachable at any time and is carved out of the First-Session guard so a new user can act on review items during onboarding. Items are typed: briefings, signals, recommendations, edits to drafted reports. Hook-level state is held in `useReviewQueue` and `useReviewCounts`.

### What's still pending

No headline gaps. New item types land here naturally as new generators ship.

## Reportee Accounts

The current shape of this feature is narrower than the word "account" implies, and it is worth stating plainly.

### What ships today

A reportee is a tokenised email contact stored in `db.reportees`, scoped to a context. The executive manages reportees under `/api/contexts/{cid}/reportees`. Checklists are drafted per reportee from the open question bank, dispatched over email with a submission URL of the form `/respond/{token}`, and the reportee replies through a public route that requires no login. Replies thread back into the submissions inbox.

This model is deliberate for v1. It means AKKI can onboard reportees with zero friction — no password, no MFA, no license — while still collecting structured, attributable submissions. It also means reportees are not users: no home page, no Work Studio surface, no cross-board view.

### What's still pending (Phase 16)

A full sub-account model under a parent executive:

- `reportee_accounts` schema with login credentials.
- Reduced-surface UI limited to Work Studio and Pulse, with Solva, Cycle Manager and Monitor hidden.
- Provisioning flow from the parent executive's Cycle Manager.
- Stripe billing at $49 per reportee per month; annual and three-year discounts; 90-day export-and-delete on cancel.

## Contexts model

### What it does

Every piece of work in AKKI belongs to a context. A context is a board seat or an operating line — the unit of separation that Privacy Wall will enforce. There are four types:

- `ned_personal` — NED seat the user manages themselves.
- `ned_sponsored` — NED seat provisioned by the sponsoring organisation, with `sponsoring_org_id` set.
- `executive_personal` — line-executive's own working context.
- `executive_enterprise` — enterprise-provisioned executive context.

### How it works today

Contexts are created on signup — every account receives a default `executive_personal` context with an `admin` sub-role membership — and may be refined during First Session. Contexts carry committees as embedded sub-documents with stable IDs (backfilled on boot), a versioned `context_object` holding the strategy sketch, and an `inbound_token` for per-context email ingestion. Memberships record per-user role (`executive`, `ned`, `reportee`) and sub-role (`admin` or member) against each context. The RBAC dependency `require_context_membership(owner_only=...)` is applied per-endpoint wherever cross-context access is possible. Invitations are token-based; `/invite/:token` acceptance works end-to-end, though the invitation email itself is a log-only stub today.

### What's still pending

No structural gaps. Additional context types are additive changes to the existing discriminator.

## Redacted Read-Only — Share-with-the-Chair

### What it does

When an executive needs a non-AKKI-user to read an artefact — typically an external chair reviewing a board pack — AKKI issues a public tokenised URL (`/shared/:token` or `/share/:token`) that serves a redacted projection. Nothing under that URL carries original, un-redacted fields.

### How it works today

The public read path is hardened. `GET /api/public/studio/read/{token}` projects exclusively from `body_redacted`. If the redacted projection is missing despite `synisense_version > 0`, the endpoint returns `422 Pending review — redacted projection missing for this snapshot` rather than falling back to the original. More importantly, the response assembler runs a recursive walk over the outgoing payload before it leaves the server; if any internal un-redacted field is detected, the endpoint fires `500 Shared view redaction contract violated. Refusing to leak internal metadata.` This is a deliberate, hard, server-side contract guard — not a UI concern.

The same guarantees extend to engagement tracking (`/api/public/studio/track/{token}`), chair-email share (currently noop), and the public reportee reply form at `/respond/{token}`.

### What's still pending

Per-slide redaction is not persisted for decks; the flat redacted body is served as a single slide when a per-slide projection is requested. A product-quality improvement rather than a correctness gap.

## Chat & LLM routing

### What it does

AKKI ships a general-purpose chat surface and routes LLM work across providers based on the cost, latency, and reasoning profile of the task.

### How it works today

All provider calls go through the Emergent Universal Key (`EMERGENT_LLM_KEY`) via the `emergentintegrations` library, which normalises Anthropic, Google and OpenAI APIs behind a single interface. The catalog exposed at `/api/chat/models` contains five entries: `claude-sonnet-4-5`, `claude-haiku-4-5`, `gpt-5-2`, `gemini-2-5-pro`, `gemini-2-5-flash`.

The tier ladder in `llm_service.py` maps task profiles to providers:

- `fast` → Gemini 2.5 Flash — validation, extraction, cheap classification.
- `standard` → Claude Sonnet 4.5 — briefs, signals, default chat replies.
- `deep` → Claude Opus — long-form narrative, decks, ExCo-blog drafting.

A deliberate architectural choice is the independent-family validator: when a Claude Sonnet 4.5 draft needs to be checked for grounding or hallucination, the validator call goes to Gemini 2.5 Flash. Different provider family, different inference stack, no single-model grading itself. The validator has a soft-cap counter (`llm_validator_usage`) with a unique `(day_utc, surface)` index to prevent a runaway loop. Deep-tier usage is tracked per account, per surface, per day with a unique index that makes the quota path race-safe. An admin spend dashboard at `/admin/llm-spend` reports usage against budgets.

### What's still pending

Per-adapter circuit breakers and per-plan rate limits on `/chat`, `/solva`, `/prepare` are Phase 18. Structured JSON logs with request IDs threaded through LLM calls arrive alongside Sentry in the same phase.

## Cross-cutting capabilities

### Auth, MFA, RBAC

JWT sessions: 8-hour access, 7-day refresh, issued as HTTP-only cookies with Bearer-header fallback. MFA is TOTP rendered as a QR code. Password hashing is bcrypt. A sampled observability path writes to `auth_events` on a configurable fraction of successes and on every failure. Context-level RBAC is enforced by `require_context_membership`; owner-only endpoints check `sub_role == "admin"`. A superadmin flag on accounts gates the platform admin surfaces.

### Billing (Stripe)

Wired end-to-end and currently disabled. `/api/billing/{plans, me, checkout, status/{sid}}` and `/api/webhook/stripe` are registered; `backend/services/stripe_webhook.py` establishes idempotency and dead-letter indexes at boot. In `.env`, `BILLING_ENABLED=false` and `STRIPE_SECRET_KEY` is commented out. The server boot-guards this: enabling billing without a key fails the process at startup. Locked pricing per `docs/ROADMAP.md`: NED $129, Executive $179, Dual $249, Reportee add-on $49. Annual 15% off, three-year 25% off. No free tier; Sandbox is the free surface. Live flip is a Phase 16 boundary decision.

### Outbound email (Resend)

Integrated and currently noop. `backend/email_service.py` wraps `resend` with an `{ok, id, mode}` envelope. When `RESEND_API_KEY` is absent, `send_email` returns `{ok: false, mode: "noop"}` and every caller inspects `mode` and degrades gracefully. The current `.env` carries no Resend key, so all outbound from Cycle dispatch, Studio share-email, Lens coach, and checklists is logged but not delivered. Tests explicitly accept `mode in {"sent", "noop", "error"}`.

Invitation emails are a narrower case: the invitation flow is broken end-to-end for any invitee not already on the same channel as the executive. `routers/contexts.py` only logs `[invite-email-stub]` and never calls `email_service.send_email`; the `/invite/:token` acceptance path is fully functional, but the recipient must receive the link out-of-band (Slack, manual paste, etc.). This is a Phase 16 dependency, not a deferrable polish item.

### Inbound email (Postmark)

`POST /api/inbound/postmark` is the webhook. Addresses are allocated per-account and per-context via sparse indexes on `accounts.inbound_token` and `contexts.inbound_token`. Incoming mail feeds a trust-tiered triage queue at `/api/contexts/{cid}/inbound-queue` with accept/reject endpoints and per-user counts. The raw payload is stored in `inbound_queue_raw` keyed to the queue item for replay.

### File storage and virus scanning

Uploads go through a boto3 client configured for S3 or MinIO — same client, MinIO in dev, S3 in prod. ClamAV is a hard precondition: if the scanner is down, uploads return 503. There is no silent fall-through to an un-scanned write path. A dev escape hatch (`ALLOW_UNSAFE_UPLOADS=true`) exists for local work and prints a stderr warning every 60 seconds.

### Audit log and governance

Every mutation writes a row to `audit_log` with context id, account id, action, resource type, resource id and a metadata blob. The governance surface at `/api/me/governance` rolls these up into a read-only report. Audit export sits at `/api/me/governance/audit/export`. Synisense runs and shield-map lifecycle events also land in audit log via the pipeline's write path, so the trust trail is a single stream.

### Observability (Sentry)

Pending. `SENTRY_DSN` is commented out in `.env`; there is no `sentry_sdk.init` call anywhere. Phase 18 brings Sentry for backend and frontend, structured JSON logs with request IDs threaded through LLM calls, rate limits, per-adapter circuit breakers, and a real dependency-check body at `/api/health`.

### Scheduling

APScheduler runs in-process, armed by `AKKI_CRON_SECRET`. Three jobs register today: Tuesday 10:00 UTC ExCo360 blog draft, Monday 08:00 UTC Influence Digest, daily 03:00 UTC paragraph-anchors sweep. The in-process design is correct only on a single replica. A comment in `server.py` flags this explicitly — a multi-replica deploy needs either external scheduled triggers or leader-election via Mongo lock, scheduled for Phase 18.

## Design system and interaction

### Palette

The CSS variables shipped in `frontend/src/index.css` are the source of truth.

- `--ink` `#1A1A1A`
- `--deep` `#2B2B2A`
- `--muted` `#6F6A5D`
- `--cream` `#F7F3EA`
- `--cream-deep` `#EFE9D9`
- `--warm-white` `#FAFAF5`
- `--rule` `#D9D3C1`
- `--accent` `#8B2E2B` (oxblood — risk, severity, editorial pull-quotes)
- `--accent-soft` `#F3E7E5`
- `--navy` `#0F1E3A` (wordmark and AKKI voice)
- `--chrome` `#1A2B4C` (primary CTAs, active nav, focus ring)
- `--chrome-soft` `#E6EAF1`
- Severity: `--risk` `#8B2E2B`, `--gap` `#A67C00`, `--opportunity` `#3D6F3D`, `--meeting` `#4A5568`, `--neutral` `#6F6A5D`

The "accent, maximum two uses per screen" rule is an editorial constraint enforced during review, not a CSS constraint.

### Typography

Georgia for editorial copy, Inter for interface copy, JetBrains Mono for code and audit dumps — all loaded from Google Fonts. This is an honest deviation from `docs/ROADMAP.md`, which specifies "Calibri (interface)". Inter was substituted during build; the roadmap has not yet been amended. The decision is binary and cheap: either update `frontend/src/index.css` to import Calibri (or a permitted fallback) and align with `docs/ROADMAP.md:51`, or amend the roadmap to lock Inter as the shipped interface face. Leaving the two out of sync erodes the design-system contract.

### Top navigation

Eight items, rendered horizontally in the 64-pixel fixed header. Active item is a 2-pixel accent underline — never a background fill. Order, as wired in `AppShell.jsx`:

`Home · Chat · Solva · Work Studio · Cycle Manager · Monitor · Pulse · Learn`

Below 1024 pixels the nav collapses to a hamburger. A cycle context indicator sits top-right; dual-role accounts see a role indicator.

### Surface types

Five, documented in `docs/SURFACE_TYPES.md`:

- **Stream** — Home, Pulse, Learn. Editorial cards ordered by recency and importance.
- **Workspace** — Work Studio, future Solva sub-modules. Three-column on desktop (materials / artefact / controls), one-column on mobile.
- **Reading** — document viewers, Pulse signal detail, briefings. Long-form focus, line-height 1.55–1.65.
- **Structural** — Cycle Manager, Monitor. Operational status views.
- **Conversational** — Chat. Natural-language module invocation.

### Keyboard shortcuts

Mounted globally in `AppShell` via `hooks/useKeyboardShortcuts.js`:

- `⌘/Ctrl-K` opens the command palette. Today the palette is a context-switcher with a placeholder reading "universal search unlocks at M7" — the search surface itself is unbuilt.
- `⌘/Ctrl-J` takes the focused artefact into Solva. The hook reads `data-solva-seed="kind:id"` from the focused element and navigates to `/app/solva?seed_kind=...&seed_id=...`. Without a seed, it drops the user on the Solva landing.
- `⌘/Ctrl-S` dispatches an `akki:save` event and suppresses the browser's Save-Page default. Composers subscribe.
- `?` opens the help overlay enumerating every shortcut.

Typing-sensitive keys skip when an input, textarea, or contenteditable element has focus.

### Accessibility posture

Target is WCAG 2.2 AA. `@axe-core/react` is lazy-imported in `frontend/src/index.js` for dev-time reporting and tree-shakes out of production. `pa11y-ci` runs against the manifest in `.pa11yci.json` via `yarn a11y:ci`. Lighthouse CI (`@lhci/cli`) runs against `lighthouserc.json` via `yarn perf:ci`. Ten known false-positive contrast violations are accepted as exceptions in `docs/ACCESSIBILITY.md`.

## Known gaps and risks

| Area | Gap | Impact | Phase |
|---|---|---|---|
| Akki Pulse | Aggregator, classifier, NED and executive views, `PulseDigest` cron — all unbuilt | Placeholder page only; feature cannot be demoed | 14 |
| Privacy Wall | No content-vs-metadata projection guard in cross-context reads | Plumbing not Privacy-Wall-safe; must refactor before Pulse wires on top | 14 |
| Solva v2 | No reasoning log, sub-modules, tension detector, grounding contract, refusal ladder | Current Solva is v1; v2 marketing cannot be honoured | 15 |
| Outbound email | Resend in noop mode; key unset | Workflows run end-to-end in dev; no email actually leaves the system | 18 (live keys) |
| Invitation email | `routers/contexts.py` logs a stub and does not call `email_service.send_email` | Invitees need the link delivered out of band | 18 |
| Billing | `BILLING_ENABLED=false`; keys commented out | Pricing locked, no live checkout; Phase 16 boundary decision | 16 |
| Sentry | No SDK init; DSN commented out | No server-side error capture; debugging relies on supervisor logs | 18 |
| `.env.example` | Missing at repo root and in `backend/` | Violates agent workflow rule in `docs/ROADMAP.md`; env changes are manually coordinated | 18 |
| Scheduling | APScheduler in-process; no leader election | Correct on single replica; multi-replica would fire jobs multiply | 18 |
| Data naming | Mongo collections remain `solve_*` after Solva rename | Deliberate; avoids a data migration for zero user benefit. Disclose externally | permanent |
| Typography | Code ships Inter; roadmap locks Calibri | Brand drift between doc and build; must converge | Doc-hygiene — immediate |
| Swagger UI | `FastAPI()` default exposes `/docs`, `/redoc`, `/openapi.json` at bare paths | If ingress routes only `/api/*`, these are not externally reachable; confirm and set `docs_url=None` in prod | 18 |
| Command palette | `⌘K` is a context switcher; placeholder reads "universal search unlocks at M7" | Shortcut discoverable but under-delivers vs user expectation | M7 |

## Roadmap alignment

`docs/ROADMAP.md` governs sequencing. The phases below paraphrase the roadmap, not invented.

**Phase 12 — Synisense Shield.** In flight through 12.3. Engine, AES-GCM envelopes, six-surface wiring and the marketing-honesty pass. Closes when `docs/SYNISENSE_SCOPE.md` reflects the shipped contract verbatim.

**Phase 13 — Nomenclature and navigation rebuild.** Four sub-phases (rename, Cycle Manager merger, nav and keyboard rebuild, accessibility and perf CI) land the surface-area changes throughout this file. 13.4 closed leaving the 10 known pa11y contrast exceptions on file.

**Phase 14 — Akki Pulse.** Cross-context aggregator, Privacy Wall enforcement, entity classifier, NED and executive views, daily digest. Placeholder page and nav slot already exist so discovery survives the gap.

**Phase 15 — Solva v2.** Three sub-phases: orchestration tier with `reasoning_audit_log` and grounding contract; four sub-modules with tension detection; guardrails, reflection, session resume, cross-module invocation. The largest single body of pending work.

**Phase 16 — Reportee accounts and billing enablement.** Sub-account schema, reduced surface, provisioning from Cycle Manager, Stripe live keys at locked pricing, 90-day export-and-delete on cancel. Billing go-live is the boundary decision.

**Phase 17 — Website rewrite.** Nine pages with locked copy, locked design tokens, Sandbox rebuilt to run an actual Solva session on a fictional context, banned-words lint in CI.

**Phase 18 — Observability.** Sentry, structured JSON logs, per-adapter circuit breakers, per-plan rate limits, real `/api/health` dependency body, APScheduler leader election, React error boundary per route.

**Phase 19 — Deployment topology.** Documentation only. Split `akki.ai` marketing from `app.akki.ai` app, finalise deploy runbook, tag CI/CD against ACR and Container Apps with Sentry release tagging.

## Glossary and nomenclature lock

Renames are canonical as of Phase 13.1. User-visible copy, URL paths, API prefixes and product documentation use the new names.

| Old | New |
|---|---|
| Solve | Solva |
| Studio | Work Studio |
| Signals (top-level surface) | Akki Pulse |
| Learn | Executive Learn |
| Prepare / Catch-up / Highlights | absorbed into Cycle Manager |

Mongo collections that predate the rename keep their original names — `solve_sessions`, `solve_clusters`, `solve_comparables`, `solve_handoffs`, `solve_free_grants`. Intentional: a collection rename is a data migration with rollback risk; the user-visible rename is the only one that delivers value. Documented at the top of `backend/routers/solva_engine.py` and in `docs/ROADMAP.md`.

---

Source of truth: `/app` codebase, branch `main`, commit at time of writing.

Companion docs: `docs/ROADMAP.md`, `docs/SYNISENSE_SCOPE.md`, `docs/SURFACE_TYPES.md`, `docs/PRODUCT_REVIEW.md`.
