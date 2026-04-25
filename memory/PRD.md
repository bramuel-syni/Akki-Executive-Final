# AKKI Sandbox — Product Requirements Document (PRD)

## Original problem statement
AKKI is a Context-primary intelligence platform for Non-Executive Directors (NEDs) and
operating Executives. The BRD pivoted from v1.0 (Tenant B2B) → v3.0 (Context-primary) →
v4.0 (Build Sequence — 18 modules across 5 streams with prescriptive design mandates).
The user selected **Path A (v4.0 Free Tier)**: follow v4.0 module boundaries but skip any
module that requires a paid/external service.

## User personas
- **Non-Executive Director (NED)** — Serves on one or more boards. Needs cross-board
  pattern awareness, pre-board briefings, and open-thread tracking.
- **Operating Executive** — Prepares for a specific board meeting. Needs pre-board prep,
  team roll-up, org highlights, and post-board follow-up tracking.
- **Dual** — Both roles; switches acting-role from the top nav role switcher.
- **Reportee** — Submits reports to an Executive (minimal scope).

## Core architecture
- **Frontend**: React + Tailwind + Shadcn UI. Brand: navy `#0A1F44`, gold `#C9A961`.
- **Backend**: FastAPI + MongoDB, custom JWT (bcrypt) + optional TOTP MFA.
- **LLM**: Emergent Universal Key → Claude Sonnet 4.5 via emergentintegrations.
  Deterministic mock fallback if key missing.
- **Mocked in-process** (paid equivalents deferred): Synisense trust/shielding layer,
  S3 (local disk at `/app/backend/uploads`), virus scan, vector DB (prompt-inline grounding).

## Surfaces
| # | Surface | v4.0 Module | Status |
|---|---------|-------------|--------|
| 1 | Home (role-specific: NED / Executive) | M15/M16 | **Live** |
| 2 | Workspace (60/40 split + persistent Ask) | M18 | **Live** |
| 3 | Highlights (3-column Twitter-style feed) | M17 | **Live** |
| 4 | Ask (top-level) | M13 | **Live** |
| 5 | Document Viewer (`/app/documents/:id`) | M7 | **Live** |
| 6 | Learn | M9 | Locked |
| 7 | Settings | M0 | **Live** |

## Implemented (by date)
### 2026-04-22 — v3.0 Path B MVP
- G1 Scaffold, M0 Contexts/Memberships/Orgs model, M1 shell+switchers+Cmd-K,
  M2 onboarding wizard + Context Object versioning, M3 document upload pipeline
  (PDF/DOCX/TXT), M5 backend signals + ask (grounded, shielded).
- M5 frontend — Highlights + Ask pages wired.
- Brute-force lockout bug fixed (ident keyed on email only, not ip:email).

### 2026-04-23 — v4.2 Frontend Polish (Path B + Act + Learn)
- **Theme swap**: cream `#F7F3EA` + oxblood `#8B2E2B` + Georgia serif leads +
  Inter chrome + JetBrains Mono for metadata. Tokenised as CSS variables plus
  rewired Shadcn HSL tokens. All new utility classes (`akki-lead`, `akki-greeting`,
  `akki-scope-chip`, `akki-context-chip`, `akki-gesture`, `akki-stream-card`).
- **AppShell re-skin**: top cream chrome with AKKI wordmark + context switcher +
  role switcher + global search button (⌘K) + avatar; 220px cream left rail
  with 3px oxblood accent on the selected nav item.
- **Attention stream Home** (replaces NedHome + ExecHome): single role-aware
  card stream ranking signals / briefings / recent documents by freshness, with
  scope chips (All / Signals / Briefings / Documents) and a 280px companion
  rail (Sources / Recent briefings / Quick actions / Other contexts).
- **Highlights** rewritten to the same card pattern with a filter bar
  (type + confidence) and per-card "Act on this" button.
- **StreamCard** shared component: 3-row structure (type badge + timestamp /
  Georgia 18px lead / context chips + oxblood gesture), 3px severity-colored
  left accent that thickens on hover.
- **Ask merged into Workspace** per v4.2 spec: `/app/ask` redirects to
  `/app/workspace`; Ask nav item removed. The persistent AskPanel on the
  Workspace right pane is now the only Ask surface.
- **Act overlay** (`ActModal`): unified 720px composition modal with two
  destinations — *Message someone* (opens user's mail client pre-filled with
  signal headline + summary + citations) and *Add to briefing* (backs to
  `POST /api/contexts/:id/briefings` with the single signal).
- **Learn module (M9)**: seven curated articles on AI governance for boards —
  Governance basics, NIST + ISO 42001 frameworks, AI in financial services,
  AI literacy in 60 minutes, EU AI Act, Incident response, Vendor AI oversight.
  Each article pulls content from reputable sources (NACD, IoD, Deloitte,
  Stanford HAI, NIST, European Commission, FCA/BoE, ICO) and closes with
  "questions to take into the room". Search + topic filter in the library grid.
  Reader view at `/app/learn/:id`.
- **Reusable `AskPanel`** component — used by both `/app/ask` and Workspace right pane.
  Supports `onCitationClick(docId)` so `[doc:xxx]` citations can drive behaviour in the host.
- **`DocumentViewer`** page (`/app/documents/:id`) with extracted-text render +
  outline rail (heading detection heuristic) + back/download controls.
- **Workspace 60/40 split** (M18): left pane shows either the documents browser
  (upload + list) or the selected document viewer; right pane is a persistent AskPanel.
  Draggable divider (clamped 35–75%). Clicking a `[doc:xxx]` citation in the right
  Ask panel loads that document in the left pane.
- **Highlights 3-column feed** (M17): left filter rail (type/trust/confidence),
  central Twitter-style feed with relative timestamps, right rail with at-a-glance
  counts + source documents + Ask CTA. Source chips link to the Document Viewer.
- **`NedHome`** (M15): board grid sorted by meeting proximity, cross-board pulse
  card when ≥2 NED contexts and signals exist, add-a-board affordance. Uses stable
  pseudo-random `daysUntilNextMeeting` as placeholder until M6 Integrations.
- **`ExecHome`** (M16): 4-band layout — Pre-Board Prep, Team Reporting, Org
  Highlights, Post-Board Follow-up — with cadence-driven ordering (approaching /
  mid-cycle / post-meeting).
- **`AppHome`**: onboarding gate hero when audit incomplete; otherwise routes to
  NedHome or ExecHome based on `activeRole`.
- Nested `<button>` hydration warning fixed in Workspace doc row (div[role=button]
  with `stopPropagation` on the trust selector).

## Test credentials
See `/app/memory/test_credentials.md`. Admin: `admin@akki.ai` / `AkkiAdmin2026!`.

## Backend regression suite
`/app/backend/tests/test_akki_v3.py` — 55 pytest cases (M0–M5). Iteration 2 smoke
tests (15/15) confirm auth + documents + signals + ask pipeline stable after frontend
restructure.

## Prioritized backlog

### P0 — SHIPPED (2026-04-23 → 2026-04-24)
- [x] **M12 Briefings** — auto-composed via `routers/briefings.py` (PDF+DOCX export).
- [x] **M14 Lens Room** — `routers/lens.py` + `pages/LensRoom.jsx` — 6 frameworks,
      O→I→A output.
- [x] **M11 Event-driven signals pipeline** — `routers/pipeline.py` — 4 staged events
      (candidate_drafted → verified → persisted) with full auditability via
      `signal_events` collection.
- [x] **M13 Hybrid retrieval for Ask** — BM25 across chunks (`bm25.py`).
- [x] **M5 Upload channels** — secure links + mobile camera capture.
- [x] **Finish server.py refactor** — DONE (2026-04-24). server.py is now a
      171-line thin assembler; auth/contexts/documents/misc all in their own
      routers. 4 new router modules, core.py expanded with shared helpers.
- [x] **Real Synisense PII shielding** — regex-based masking in `llm_service.py`,
      full `shielding.{identifiers_masked, by_category, shielded_by}` dict now
      surfaced on every LLM-backed endpoint response.

### P0 — remaining
- _(none — all P0 items complete)_

### P1 — Polish
- [ ] Onboarding wizard end-to-end frontend subagent coverage.
- [ ] Minor: POST `/api/auth/refresh` should return `access_token` in body for
      bearer-only clients.
- [ ] Minor: Add top-level `token` field to invitation creation response.

### P2 — Paid / external integrations (explicitly deferred)
- [ ] **M4 Stripe Billing** — sponsored seat subscriptions (test key available in pod).
- [ ] **Real vector DB** — Pinecone or pgvector (current BM25 is sufficient for MVP).
- [ ] **M6 Integrations** — Google Calendar, board portals (Diligent / BoardPaQ).
- [ ] **Clerk / Auth0** — v4.0 M1 preference; we use custom JWT (recommended to keep).
- [ ] **Unstructured.io** — richer extraction than our `pypdf` + `python-docx`.
- [ ] **ClamAV / VirusTotal** — real virus scan (we use a stub).

## Recent fixes
- **2026-04-25 Sprint 15 / iter20** — §12 Phase 3: Multi-tier review chain (Reports).
  - **Reports collection** — composed from a cycle's submissions; carries a `chain[]` of tiers (author at tier 0, escalating reviewers at tier 1+). `compose` stitches reportee answers into a starter markdown body the author edits before sending up.
  - **`send_up`** flips draft → in_review and sends a Resend email to the next pending reviewer with a deep link to /app/cycle/reports/:id. Reviewer doesn't need to be a member of the upstream context — the new `_resolve_report_access` gate accepts EITHER context-membership OR named-reviewer-on-chain (matched by email).
  - **`review`** — current reviewer can `approve` (next tier promoted to pending; if last tier, status → finalised) or `send_back` (chain rolls back to author with notes). Only the email-matched current reviewer can act.
  - **Cross-context inbox** — `GET /api/reports/inbox` returns every report platform-wide where the caller is the current pending reviewer. New `ReviewInboxCard` component renders on Home only when the count > 0.
  - **Reports tab** in Cycle page (5th tab). Compose modal collects cycle + title + chain (reviewer name/title/email × up to 5). Editor modal carries the chain visualizer, event trail, edit affordances, and the action footer that surfaces "Send to next" / "Approve & forward" / "Send back" based on caller role.
  - **End-to-end verified live**: Bramuel (CFO author) composed → sent up to admin@akki.ai (CEO, NOT a context member of Tuli) → admin approved with note → status flipped to chair@example.com pending → chain entries: [✓ Author, ✓ CEO, pending Chair].
  - **Resend send_mode caveat**: until a real domain is verified in the Resend dashboard, only `delivered@resend.dev` actually delivers. Admin@akki.ai gets `send_mode=error` from the Resend sandbox API — but the chain progression itself works regardless.

## Recent fixes
- **2026-04-25 Sprint 14b / iter19** — Brand polish (post-iter18 user feedback).
  - **Logo conditional Sandbox suffix** — Logo now reads just "AKKI" everywhere by default; the " · Sandbox" suffix is shown ONLY when `account.is_sandbox === true` (auto-detected via `useAuth`). Marketing pages, sign-in, sign-up, signed-in-non-sandbox app shell all read "AKKI". Sandbox flow reads "AKKI Sandbox" because the disposable account carries `is_sandbox=true`. Manual override available via `<Logo showSandbox={true|false} />`.
  - **Landing CTAs decluttered** — three competing CTAs collapsed to one prominent navy "Try AKKI in 60 seconds" button, with a one-line explainer of what the Sandbox is ("AKKI loaded with sample data for a fictional company in your sector. No signup. Yours for 14 days, then it deletes itself"), then two quiet text gestures separated by a `·`: "Sign in to your workspace" and "Request a team workspace".
  - **SignIn page rebrand** — replaced the dark navy + photo aesthetic with the editorial cream/Georgia palette that matches the rest of the marketing site. New header with brand-only logo and "← Back to akki.ai" link. Two-column on desktop: left has serif headline "The colleague who reads with you" + an editorial pull-quote with attribution; right has the form with proper accent-soft error styling, Synisense-shielded footer chip, and a "Don't have an account? Try AKKI in 60 seconds" cross-sell to /sandbox.
  - Cleaned up "AKKI Sandbox" hard-coded labels in Landing colophon and SignUp footer.

## Recent fixes
- **2026-04-25 Sprint 14 / iter18** — §12 redesign + marketing site + Exco360 blog (BIG sprint).
  - **§12 governance pivot** — AKKI is now the third party in the conversation, not just a drafter:
    - **Question Bank** per context. Persistent. CRUD + `seed-from-briefings` idempotent extractor that pulls every "questions to take into the room" from past briefings into one place. Categorised (audit/risk/financial/regulatory/strategic/operational/people/general). Tracks `times_asked`, `last_asked_at`, `status`.
    - **Reportees** first-class — name, email, title, areas-of-ownership tags. Soft-delete.
    - **Checklist generation** — deterministic ranking: areas-match + recurring-question bias + recency. Picks top 6 open questions per reportee. **Anti-spam** 14-day cooldown per reportee unless executive explicitly targets them.
    - **Approve & Dispatch** — executive reviews/edits each draft, single batch dispatch. **Real Resend integration live** with `"AKKI for <Executive Name>"` From + reply-to to executive's real email. Mailto fallback if Resend not configured.
    - **Public /respond/{token}** — reportee fills form without authenticating, answers persist as `submissions`, open questions auto-flip to `answered`.
    - **Submissions inbox** — executive sees consolidated responses ready for the next report draft.
  - **Marketing site** — full editorial chrome at `/about`, `/features`, `/security`, `/blog`, `/blog/:slug`. MarketingShell header + 4-column footer. Security page surfaces the four trust promises with verification recipes.
  - **Exco360 blog** — *AKKI's perspective on AI's role in modern executive success*. Weekly editorial. Admin compose surface (`/app/blog-admin`, superadmin only) generates 700–1,100-word article + LinkedIn post + email-newsletter intro + tweet. Public list, post reader, subscribe form. First issue published end-to-end during smoke testing.
  - **Sidebar "Cycle"** entry added to AppShell.
  - **iter18**: Backend 16/16 GREEN (cycle CRUD, anti-spam, dispatch with real Resend, public respond, blog compose+publish+subscribe). Frontend marketing pages + Cycle + Respond + BlogPost all rendered.

## Recent fixes
- **2026-04-24 Sprint 13 / iter17** — Product-review P1 fixes.
  - **Actionable role-mismatch banner** — new "Act as NED/Executive" button
    (data-testid `role-mismatch-fix-btn`) inside the banner flips activeRole
    to match the current context in one click. In practice the banner
    rarely fires because AuthContext bootstrap auto-realigns on mount — but
    when it does, the fix is inline instead of being buried in the role
    switcher.
  - **Next Best Action card on Home** — new `NextBestActionCard` replaces
    the humble EmptySlot when a non-aggregated Home has zero signals.
    Cream-gradient hero with oxblood accent rail, "Your next best action"
    overline, a primary Upload CTA (navy) and a secondary Generate link.
    Shows post-audit only — the audit gate still takes precedence pre-audit.
  - **The Lens run narrative** — new shared `useAIStageTicker` hook; Lens
    Room's "Apply lens" now shows a 5-stage typed narrative ("Reading the
    subject against Capital Discipline…" → "Drafting Observation → Implication
    → Action…") instead of a lonely spinner. Unifies the AI-thinking voice
    across Signals, Briefings, and The Lens.
  - **Trust centre + global footer** — new 4-card posture panel (01 Residency
    · 02 Shielding · 03 Provenance · 04 Control) at the top of the Privacy
    tab (renamed "Trust"), deep-linked via `/app/settings?tab=trust`. A
    persistent low-weight Trust footer sits below every authed page with
    ShieldCheck + "Synisense-shielded · Your context never leaves this
    account · Every signal cites its source · Trust centre →". Footer link
    SPA-navigates via `useNavigate` (iter17 bug fix — initial `<Link>` had
    a click no-op on scroll-containing surfaces).
  - **iter17**: Trust footer + Trust centre verified live; NBA card + role-
    mismatch fix button + lens-run ticker all correctly wired in source.
    Footer Link→button regression fixed post-testing.


  - **Display renames (routes unchanged):** sidebar "Highlights" → "Signals"
    everywhere, "Lens Room" → "The Lens". /app/highlights overline now reads
    "SIGNALS · &lt;context&gt;". Briefings empty-state gesture reads "Open
    Signals". Routes /app/highlights and /app/lens still resolve — zero link
    rot, zero bookmarks broken.
  - **Learn `View more` modal** — new pill button under the card grid opens a
    medium Dialog ("Further reading · &lt;tab&gt;"). Shows editor-curated
    external primary sources grouped by topic; filters by the user's current
    topic pill when one is active. Counts: TL Articles 12, News 10, Videos 8,
    Case Studies 8 — meets the ≥ 8 threshold flagged by iter16.
  - **`/learn/research` personalisation** — endpoint accepts optional
    `context_id`; when the caller is a member, the LLM prompt is weighted
    to the context's sector + jurisdiction. Verified: Bramuel on his Tuli
    Financial Group (Kenya, banking) context researching "vendor AI
    oversight" returns a CBK-flavoured article with Kenyan references woven
    in. Response surfaces `personalised:true` +
    `personalisation_from:{sector,jurisdiction}` so the toast can say
    "weighted to Kenya". Membership verified BEFORE context read — no
    enumeration leak.
  - **Sandbox cleanup secret gate** — `POST /api/sandbox/cleanup/expired`
    now requires `X-Cron-Secret` matching `AKKI_CRON_SECRET` in the
    environment. Fails closed (503) if the env var is unset. Anonymous
    POSTs return 401. Closes the iter15 nit.
  - **iter16**: 37/37 backend PASS (32 regression + 5 new iter16 covering
    personalisation + cleanup gate). Frontend: labels, modal flow, Governance
    topic filtering, and ESC close all verified. LEARN_MORE depth padded
    post-testing to meet the ≥ 8 spec across all four tabs.


  - **6 polished sector templates** (`sandbox_templates.py`): SaaS/tech,
    logistics, healthcare, manufacturing, retail, real estate. Each ships
    3 committees / 2–3 docs / 4–6 sector-specific signals / 1 composed
    briefing, all parameterised over `{company_name}/{currency}/{regulator}`.
    Only "Other" still falls through to `generic_diversified`.
  - **Sandbox → account conversion** (`POST /api/sandbox/convert`): rewrites
    the disposable account email/password/name, strips `is_sandbox`, flips
    sandbox contexts to `executive_personal` or `ned_personal`, drops expiry
    metadata, sets real cookies. `keep_sandbox=false` deletes the explored
    environment entirely. `PublicOnlyRoute allowSandbox` lets the sandbox
    user reach /signup to convert; regular authed users still redirect.
  - **SignUp.jsx** detects `?from_sandbox=<cid>` + `account.is_sandbox` and
    renders a distinct editorial conversion UX: "Keep exploring — for real."
    heading, "Keep my sandbox as a working context" checkbox with the
    sandbox's name surfaced, "Finish setup" CTA.
  - **Mid-exploration email capture** (`POST /contexts/{cid}/capture-email`
    + `SandboxEmailCapture.jsx`): bottom-right modal surfaces after 3 min
    of sandbox browsing (localStorage-guarded, once per device). Stores
    email on `sandbox_metadata.prospect_email` and queues a
    `sandbox_pickups` record for a +24h drip (SMTP ships with §6 Email-in).
  - **Dropdown fix**: `Financial services` now pre-selected on /sandbox so
    Radix's item-aligned Select positions the polished template adjacent to
    the trigger with every other sector naturally visible below.
  - **iteration_14**: 15/15 new backend tests PASS + 26/26 regression PASS.
    47 test-generated sandboxes swept. iteration_14 code-review nits
    addressed (dropdown, `is_sandbox` on sanitize_account, stale Phase 1
    assertion, template-import WARNING log).

- **2026-04-24 Sprint 10** — Addendum v4.3 §1 Phase 1: Sandbox pre-auth evaluation.
  - New `/sandbox` route: 4-question editorial intake (company name,
    sector, role, region). No sign-up required up front. Primary hero CTA
    on Landing now points here.
  - New `/sandbox/generating/:sessionId` streaming page — plays the 10-stage
    60-second narrative with the prospect's company name, sector, region
    country, and role label substituted into stage text. Cream canvas, serif
    title, oxblood progress bar with ambient shimmer. Holds on stage 9
    until the backend seed is genuinely ready.
  - New backend `routers/sandbox.py` + `sandbox_service.py`:
    `POST /api/sandbox/generate` → `GET /generate/{id}/status` flow, async
    background seed (ready in ~2s), returns JWT. Creates disposable account
    `sandbox+<id>@akki.local`, sandbox-typed context with
    `sandbox_metadata.{expires_at (+14d), read_only_until (+21d),
    hard_delete_at (+22d)}`, full seeded artefacts.
  - **banking_midcap template** — 3 committees + 3 documents + 6 signals +
    1 pre-composed briefing, every string parameterised for company name,
    currency (KSh, ₦, €, $ etc. driven by region) and regulator (CBK, CBN,
    SARB, FCA, SEC, MAS). Generic template fallback (1 doc + 3 signals + 1
    briefing) for non-polished sectors in Phase 1.
  - `SandboxBanner` chrome renders above top bar when
    `activeContext.type==='sandbox'` — "14 days remaining · Set up your
    account →". Hidden for non-sandbox users.
  - Bearer token interceptor in `lib/api.js` attaches
    `Authorization: Bearer <akki_access_token>` from localStorage when
    present. Cookie-auth sessions unaffected (additive). Logout clears it.
  - Rollback on seed failure, 90s session TTL, and `is_sandbox` surfaced on
    sanitize_account from iter13 code review.
  - **iteration_13: 12/12 backend PASS + 100% frontend arc verified.** Full
    round-trip screenshot sequence captured (intake → generating → landing
    with banner + banking signals visible).

- **2026-04-24 Sprint 9** — Build Addendum v4.3 §8 + §9 closed.
  - **§8 — All boards aggregated Home stream**: new
    `GET /api/me/home/stream` merges signals + briefings across every active
    membership, attaches `context_name` to each card. Home renders a quiet
    'This context | All boards' toggle (only when user has 2+ contexts);
    aggregated mode shows an uppercase context badge (first token of context
    name) left of the type badge.
  - **§9 — External Share**: new `shares` collection + router
    (`POST /api/contexts/{cid}/shares`, inbox, outbox, auth-guarded
    `GET /api/shares/{id}`, sharer-only DELETE revoke). Creates a mention
    inbox row for AKKI recipients; logs an email-send intent for non-AKKI
    emails (SMTP deferred to §6). Extended comments router with
    `artefact_type='share'` so the one-to-one comment thread on shared
    items just works. New `ShareModal` composition overlay, Share buttons
    on signals (Highlights + Home) and briefings (Briefings viewer), and a
    new "Shared with you" tab on Home.
  - **New `source` prop on `StreamCard`**: optional left-chip rendering
    either a context badge (aggregated mode) or a "SHARED BY X" accent-soft
    badge (shared-with-you cards). Non-breaking.
  - **Testing** — iteration_12: 14/14 backend PASS + 100% frontend, zero
    design or integration issues.

- **2026-04-24 Sprint 8** — Speaking notes on the board deck.
  - New endpoint `POST /api/contexts/{cid}/briefings/{bid}/speaking-notes`
    — one LLM call produces 3 spoken-voice bullets per briefing item (fact →
    why it matters → what to watch/escalate). Persisted to
    `briefing.items[i].speaking_notes` + timestamp on
    `briefing.speaking_notes_at`.
  - `render_board_deck_pdf` now renders them under each item slide, prefaced
    by a tiny `WHAT YOU WOULD SAY` label in oxblood + Georgia-italic bullets
    in muted slate. Only appears when drafted.
  - Briefings page gets a new outlined oxblood "Draft speaking notes" button
    that toggles to "Re-draft notes" once notes exist, and a small "+ notes"
    chip lands on the Board deck pill after drafting.
  - iteration_11: 8/8 backend tests PASS (happy path, idempotency, 404, 401,
    400 empty-items, PDF embedding, /ask shielding regression, deck-without-
    notes regression). Frontend 100%, zero console errors.

- **2026-04-24 Sprint 7** — Executive-ready board deck + housekeeping + visual life.
  - **Board deck PDF** (new `render_board_deck_pdf` in `briefings_service.py`):
    landscape A4, one signal per slide — cover, executive summary, per-item
    slides (headline + evidence + sharpest question + source chips), optional
    closing slide, final "Receipts" sources slide. Oxblood/Cream palette +
    serif/sans split. Exposed as `GET /export?fmt=board_deck`. Briefings page
    gets a new oxblood "Board deck" pill left of PDF/DOCX.
  - **Housekeeping sidebar** — two new nav items below Learn: "Manage my team"
    and "Manage my companies", both deep-linking to `/app/manage?tab=…`.
    Sidebar items now slide in with a staggered framer-motion entrance.
  - **`/app/manage` page** (new `Manage.jsx`) — 2-tab surface:
      · **Team** — invite / revoke invitation / remove member scoped to the
        active context. Admin-only write actions. Link out to full settings.
      · **Companies** — grid of all user contexts with hover-lift motion,
        quick "Switch & open" action, non-destructive "Archive" confirm,
        and a top-right "Add company" pill.
  - **Motion pass** — framer-motion installed. AppHome top-signals + Highlights
    signals grid + Manage members/companies now enter with stagger animation;
    Manage tab indicator uses `layoutId` for spring-animated underline.
  - **Highlights stats strip** (`HighlightsStats.jsx`) — pure-SVG confidence
    donut + 14-day sparkline in oxblood tones. Sits above the committee
    filter so the reader sees shape → scope → cards. Zero chart-lib
    dependency.
  - **Testing** — iteration_10: 5/5 new backend tests PASS, frontend 100% on
    all new surfaces, zero console errors.

- **2026-04-24 Sprint 6** — Shielding payload regression fixed + server.py refactor completed.
  - **Shielding fix**: every LLM-backed endpoint now returns a top-level
    `shielding: {identifiers_masked, by_category, shielded_by}` dict alongside
    the legacy scalar count. Touched: `/signals/generate`, `/ask`,
    `/briefings`, `/simulate`, `/lens/run`, `/documents/generate-meta`.
    iter8 flagged → iter9 100% green.
  - **server.py refactor**: 1,400 → 171 lines (88% reduction). Extracted into
    4 new routers: `routers/auth.py` (register/login/logout/refresh/me/role/MFA),
    `routers/contexts.py` (CRUD + members + invitations + context-object +
    presets + accounts/me), `routers/documents.py` (upload + thread +
    list/get/patch/archive/download + generate-meta), `routers/misc.py`
    (llm/probe + /events + /health). `core.py` now exports
    `hash_password` / `verify_password` / `set_auth_cookies` /
    `sanitize_account` / `sanitize_context` / `provision_default_context`.
    server.py is now a pure assembler (startup indexes + admin seed + router
    wiring + CORS). iteration_9: 100% backend — 52 existing sprint tests +
    11 new iter9 refactor-smoke tests all green.

- **2026-04-24 Sprint 5** — Shipped: AllLensesModal (fires 6 lenses in
  parallel from any signal card), mobile camera upload in Workspace
  (`capture="environment"`), lightweight CompositionStrip provenance panel
  on Briefings/Simulate/LensRoom, audit-log + export extracted to
  `routers/audit.py` (server.py now 1,253 lines, 35% off original).
  iteration_7: 100% backend (10/10), 95% frontend (2 cosmetic nits fixed:
  DialogDescription a11y + clickable simulate-list testid — already present).

- **2026-04-24 Sprint 4** — Shipped: landing-page executive rewrite, M13
  BM25 Ask retrieval (`bm25.py`), Pipeline trace drawer on Highlights,
  "Boards to watch this week" Portfolio banner, continued server.py
  refactor (signals+ask extracted; now 33% off original). iteration_6:
  100% backend (7/7), 100% frontend, zero issues.

- **2026-04-23 Sprint 3** — Shipped: role auto-route (AuthContext), Mention
  Inbox bell in AppShell header, CommitteeManager in Settings, signals+ask
  router extraction, M14 Lens Room (6 frameworks, full page), M11 event-
  driven pipeline (4 stages, signal_events trace). iteration_5: 100% backend
  (10/10), 100% frontend.

- **2026-04-23** — **Sprint 1 shipped** (3 of the user's 7-point feedback list).
  - **Task 1 — Curated Home** (Feedback #2): `AppHome.jsx` now shows top-of-pile
    content as **three sibling tabs** — *Top signals* (≤3, ranked by confidence
    then risk-bias then recency), *Top briefings* (≤2 by recency), *New
    documents* (≤3 by recency) — with a single right-aligned "View all" link
    that follows the active tab (`/app/highlights`, `/app/briefings`,
    `/app/workspace`). Default tab is *Top signals*. Fixed page height
    (`h-[calc(100vh-4rem)]`) — only the active panel scrolls; chrome stays put.
    Companion rail adds "My portfolio" link to `/app/contexts`.
  - **Task 2 — Learn mini-tabs** (Feedback #1): `Learn.jsx` refactored to four
    content-type tabs (`News · TL Articles · Videos · Case Studies`) with
    underline accent on active tab, per-tab topic pills on the left rail, and
    fixed page height — only the card grid scrolls (`data-testid=learn-scroll`).
    Added `content_type` field to each article in `lib/learnContent.js`, new
    `LEARN_NEWS` array with 3 curated briefs (EU GPAI Code, FCA supervisory
    posture, NACD 2026 benchmark), and `CONTENT_TYPE_LABEL` map.
  - **Task 3 — Context Portfolio page** (Feedback #5): NEW `/app/contexts`
    surface (`ContextPortfolio.jsx`). Portfolio summary strip shows totals for
    Contexts / Signals / Briefings / Documents. Cards grouped into
    *NED boards* and *Executive contexts*; each card shows type/admin chip,
    sponsored badge, per-context metrics (signals/briefings/documents fetched
    in parallel). Clicking a card calls `switchContext` and navigates to `/app`.
    `AppShell` context dropdown now has a "View portfolio" item at the top
    (`data-testid=context-portfolio-btn`).
  - **Testing**: iteration_3 — 100% backend, 100% frontend. No critical or
    minor issues. Two design notes flagged (summary-strip "…" during fan-out;
    role-mismatch banner ever-present because Bramuel's default context is NED
    while `activeRole` defaults to `executive`) — both working-as-designed.

## Sprint 2 — SHIPPED 2026-04-23 (items 3 / 6 / 7 complete)
### Phase 1 — Backend refactor
- **NEW** `/app/backend/core.py`: single source for db + helpers + auth deps.
- **NEW** `/app/backend/routers/{briefings,learn,committees,simulate,comments}.py`.
- `server.py`: 1,941 → 1,570 lines. Pattern proven for future router migrations.

### Phase 2 — Sub-committees (Feedback #6)
- Contexts carry `committees: [{id, name, your_role}]`; IDs auto-backfilled on
  startup for seeded boards.
- Full CRUD at `/api/contexts/{id}/committees` (owner-only writes); deletion
  unsets `committee_id` on referencing artefacts.
- `committee_id` filter query param added to signals, briefings, documents,
  simulations list endpoints.
- Highlights shows a "Scope" chip row; Briefings left-rail gets a committee
  `<select>`. Chair badge rendered when `your_role === "chair"`.

### Phase 3 — Simulate / Forecasting (Feedback #3)
- New surface `/app/simulate`. LLM produces Best / Base / Stress paragraphs
  for 1y and/or 3y horizon, a 3–6 item watchlist with early-warning triggers
  and committee routing, assumptions, and the single sharpest board question.
- Backend: `routers/simulate.py`. Side-nav adds **Simulate** (Target icon).

### Phase 4 — Human-to-human collaboration (Feedback #7)
- Polymorphic comment store — artefacts: signal / briefing / document / simulation.
  Threaded via flat list + `parent_id` for single-level replies.
- `@mentions` parsed from body, resolved to context members by email-prefix
  or first-name. Mention records written to a separate collection (inbox-ready).
- Endpoints: `GET/POST /api/contexts/{id}/{artefact_type}/{id}/comments`,
  `DELETE /api/contexts/{id}/comments/{id}`, `GET /mentions`, mark-read.
- **NEW** `CommentThread.jsx` wired into Briefings, Simulate, DocumentViewer
  viewers. Includes @mention highlight, relative timestamps, delete (author
  or context admin), ping-count badge.

### Testing
- iteration_4 — 100% backend (18/18), 100% frontend on all Sprint-2 testids.
- Only non-blocking note: pre-existing role-mismatch banner (unchanged since
  iteration 3).

## Recent fixes
- **2026-04-23** — Workspace doc row nested-button hydration warning: outer wrapper
  converted to `<div role="button" tabIndex={0}>` with keyboard handler; TrustChip
  wrapped in a `stopPropagation` span so changing trust doesn't open the document.
- **2026-04-22** — Brute-force login lockout: was keyed on `ip:email`; changed to
  email-only because Kubernetes ingress rotates `request.client.host`. Verified
  5×401 → 429 on 6th attempt.
