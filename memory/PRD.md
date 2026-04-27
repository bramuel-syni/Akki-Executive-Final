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
- **2026-04-25 Sprint 16 / iter21** — Reports PDF + LLM polish + Committees scoping for Reportees.
  - **Reports PDF export** — new `reports_service.py` builds an A4 portrait PDF with editorial cream/oxblood/Georgia palette, body rendered from markdown, a **chain-of-custody back page** with timestamped tier table (Tier · Role · Name & email · Action · When · Note), an **event log** of every chain action, and the trust footer. Endpoint `GET /api/contexts/{cid}/reports/{rid}/export.pdf` available to context members + named reviewers (same gate as `get`); allowed for `draft`, `in_review`, and `finalised`.
  - **LLM polish** — new `POST /api/contexts/{cid}/reports/{rid}/polish` returns a polished body (does NOT auto-save; executive reviews then commits via patch). Author-or-current-reviewer only. Strips stray `\`\`\`` fences the LLM might add.
  - **Committee scoping for Reportees** — `committee_id` field added to ReporteeIn + reportees `list` accepts `committee_id` query param; new `GET /api/contexts/{cid}/cycle/committees` lists the context's committees so the Cycle UI can scope work. Reportee form gets a Committee Select; visible cards show a `[var(--chrome)]`-tinted committee chip; new filter strip above the list lets the executive scope to All / Unscoped / specific committee.
  - **Question Bank `committee_id`** also accepted as a list filter (already on the schema; now exposed on the GET endpoint) — sets the foundation for committee-chair-scoped checklists in a follow-up.
  - **Editor footer redesigned** to surface five distinct actions: Close · Download PDF · Polish with AKKI · Save edits · Send up / Approve & forward / Send back. Sparkle icon on Polish, Download icon on PDF.

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
- **2026-04-25** (iter21) — `sanitize_account()` was silently dropping `is_superadmin`,
  blocking the BlogAdmin gate. Fixed in `/app/backend/core.py`. Verified via
  `/api/auth/me` returning `account.is_superadmin=true` for `admin@akki.ai`.
- **2026-04-23** — Workspace doc row nested-button hydration warning: outer wrapper
  converted to `<div role="button" tabIndex={0}>` with keyboard handler; TrustChip
  wrapped in a `stopPropagation` span so changing trust doesn't open the document.
- **2026-04-22** — Brute-force login lockout: was keyed on `ip:email`; changed to
  email-only because Kubernetes ingress rotates `request.client.host`. Verified
  5×401 → 429 on 6th attempt.

## §12.x Final UI polish batch (iter19–21, 2026-04-25)
- **PolishDiffModal** (`/app/frontend/src/components/cycle/PolishDiffModal.jsx`)
  — word-level diff (LCS over whitespace tokens) showing red strike-through for
  removed words and green highlight for added. Wired into `ReportsTab` so
  "Polish with AKKI" no longer silently overwrites the body — instead it opens
  the diff and lets the executive **Accept** or **Reject** before saving. If the
  LLM returns identical text, a "no changes" toast fires and the modal stays
  closed. Verified end-to-end on a 588-word draft fixture.
- **Committee scope strip** on `/app/cycle` Checklists tab. When the active
  context has ≥1 committee, a chip strip renders ("Whole context" + one chip
  per committee). Selecting a committee scopes both the reportee match AND the
  question pool to that committee for the next `/checklists/generate` POST.
  Verified end-to-end on Tuli ned ctx with the iter19 seed (Audit + Risk
  committees, Ruth Kamau audit-scoped reportee, 6 audit-scoped questions).
- **Copy for Medium** in BlogAdmin (`/app/blog-admin`). Both the live draft
  preview tile-grid AND each row of All Posts now have a Medium button. Per-row
  click fetches the full post body via the new admin endpoint
  `GET /api/blog/admin/posts/{slug}` (gated by `_require_admin`) and writes a
  Medium-ready markdown payload to the clipboard:
  `**KICKER**\n\n# Title\n\n> Dek\n\nbody...\n\n_Tags: ..._`.
- **Seed script** `/app/backend/scripts/seed_iter19_e2e.py` (idempotent) —
  seeds the committee + reportee + question + rich-draft fixtures the E2E
  tests rely on.

## §M4 Stripe Billing + Schedule cron + polish (2026-04-25, iter22)
- **Stripe Billing M4** — Free / Pro ($29/mo) / Team ($99/mo) plans, fixed
  server-side. Settings → Billing tab (`/app/settings?tab=billing` or
  `/app/settings/billing`). Backend: `/api/billing/{plans,me,checkout,status/{sid}}`
  + webhook `/api/webhook/stripe`. Uses `emergentintegrations.payments.stripe.checkout.StripeCheckout`.
  `STRIPE_API_KEY=sk_test_emergent` in `/app/backend/.env`.
  - Checkout creates real `https://checkout.stripe.com/c/pay/cs_test_...` URLs.
  - Status endpoint degrades gracefully (returns persisted `payment_status`)
    when the test-mode SDK can't retrieve the just-created session — the UI
    poll loop never crashes.
  - `payment_transactions` collection holds every initiated session;
    `accounts.plan` is flipped on `paid`. Webhook + poll both apply once.
  - Sanitize_account now surfaces `plan` + `subscription_status` so the UI
    can gate paid features (e.g. recurring schedule, dispatch).

- **Recurring Cycle Schedule (cron)** — single schedule per context.
  - `GET/PUT/DELETE /api/contexts/{cid}/cycle/schedule` (auth + membership).
  - `POST /api/cycle/cron/run-schedules` gated by `X-Cron-Secret` =
    `AKKI_CRON_SECRET`. Idempotent (advances `next_run_at` after each run).
  - Frontend "Schedule recurring" button on Cycle → Checklists tab opens a
    modal (cadence, weekday, cycle name template with tokens
    `{month}|{date}|{iso_week}|{year}`, deadline offset days, committee scope).
    Verified end-to-end: a forced-past `next_run_at` yields 1 draft for the
    audit-scoped reportee with cycle name "April 2026 report".

- **Frontend polishes** (P2 backlog cleared in this iteration):
  - `PolishDiffModal` wordDiff is now paragraph-chunked → bounded LCS
    memory even on long appendices.
  - `BlogAdmin` caches the full post body per slug after the first per-row
    Medium fetch (no repeat round-trips).
  - `ReportEditor` shows an "Unsaved changes" badge above the body textarea
    when title/body/polish-accept has dirtied the local state, and
    `window.confirm` blocks an accidental close-without-save.

## §13 Plays — choreography over existing surfaces (2026-04-26, iter24)

### Why
After a CFO/CEO demo, the user observed AKKI's value was present but the
*journey* to it was not — the executive had to know to go to Settings →
configure cycle → Workspace → start a Report → Cycle → approve dispatch.
Per Build Addendum v4.4, **Plays** are introduced as a third structural
layer (Surfaces, Artefacts, **Plays**) — named, staged journeys that
*compose* existing features into a coherent flow.

### Cadence (non-negotiable)
- Quiet, not noisy. Editorial, not transactional. Trust-first.
- **No** progress bars / percentages / step counters / "Stage 2 of 6" /
  checklist marks / celebratory animations.
- Stage transitions = name fade + a single editorial phrase.
- Pause-and-resume native — full state persists.

### Slice 1 shipped
- **Backend** (`/app/backend/routers/plays.py`):
  - `GET /api/plays/library` — 6 plays, only `board_pack` available.
  - `POST /api/contexts/{cid}/plays` — start (idempotent: returns the same
    active/paused play if one exists for the same type).
  - `GET /api/contexts/{cid}/plays` — list (sorted by activity).
  - `GET /api/contexts/{cid}/plays/{pid}` — full play state.
  - `POST .../advance` — bumps current_stage; entering the last stage
    flips `status='completed'` + sets `completed_at`.
  - `POST .../jump` — backwards free; forward requires `confirm=true`
    (returns 409 otherwise).
  - `POST .../pause`, `.../resume`, `.../exit`.
  - `PATCH .../state` — shallow-merge per-stage bindings (e.g.
    `report_id`, `schedule_id`).
- **Frontend**:
  - `/app/plays` — `PlaysLibrary.jsx`. 6 cards in two sections (executive,
    NED). Stubs render as "Coming next" lock state.
  - `/app/plays/:id` — `PlayView.jsx`. 64px Play header (kicker + stage
    name with fade), 60/40 split, right-side "Stages" overlay panel with
    forward-jump confirm.
  - `BoardPackStages.jsx` — 6 stage components (Setting the cycle, Where
    the gaps are, Consolidation, Your review, Distribution, Done) — each
    reuses the existing Cycle/Reports/Schedule/Submissions surfaces.
  - `PlaysInProgressStrip.jsx` on Home — restrained chips that bring the
    executive back to active choreography.
  - Side-nav entry `Plays` between Cycle and Learn (Compass icon).

### Backend tests
- 14/14 new pytests in `/app/backend/tests/test_iter24_plays.py` GREEN.
- 26/26 prior regression (iter19 polish/committee/medium + iter22
  billing/schedule) STILL GREEN. Plays add a layer; nothing existing was
  modified.

### Frontend self-test
- All 6 stages cadence-clean (no STAGE N counters; replaced with bare
  editorial headlines).
- Pause→Resume→Pause toggles correctly via optimistic update (was
  flagged in iter24).

## §13 Plays — Slice 2 (2026-04-26, iter25)

### Schedule auto-launch hook
- `_run_one_schedule` in `/app/backend/routers/cycle.py` now calls
  `_spawn_auto_launched_play` after drafting checklists. The spawned (or
  resumed) Board Pack Play is positioned at stage 1 ("Where the gaps are")
  with `auto_launched=true`, `auto_launch_seen=false`, and
  `state.cycle_name` / `state.deadline` / `state.auto_launched_schedule_id`
  carried through. **Re-running the cron resets `auto_launch_seen=false`**
  so a fresh PLAY READY card surfaces every cycle, while keeping the same
  `play_id` (idempotent).

### Pre-Board Play (NED, available)
- Backend: `PRE_BOARD_PLAY` definition + `POST /api/contexts/{cid}/plays/{pid}/pre_board/read`
  endpoint. Calls Claude Sonnet 4.5 via the Emergent LLM key with
  `module="pre_board.read"`, `response_format="json"`. Returns 5 reading
  notes + 3-4 standouts (each `{label, detail, why}`).
- Frontend: 5 stage components in `/app/frontend/src/components/plays/PreBoardStages.jsx`:
  Arrival (paste pack), Reading (notes), Standouts (oxblood-bordered cards),
  Questions (textarea + standouts working set), Walking In (one-page brief).
- Self-verified output sample: *"Revenue growth of 14.2% is flattering a
  balance sheet that has deteriorated across three core ratios in six months."*

### PLAY READY trigger card on Home
- `/app/frontend/src/components/home/PlayReadyCards.jsx` — renders cards for
  any play where `auto_launched && !auto_launch_seen`. Editorial layout:
  oxblood "PLAY READY · Board Pack Play" kicker, Georgia headline
  ("April 2026 report just dispatched."), italic transition phrase,
  "Open the Play →" + "Not now" affordances. Click 'Not now' → POST `/seen` →
  card disappears. Opening the play also fires `/seen` automatically.
- `POST /api/contexts/{cid}/plays/{pid}/seen` — idempotent, used by both UI
  paths and by PlayView's load() to mark auto-launched plays as seen.

### Backend tests
- 13/13 new pytests in `/app/backend/tests/test_iter25_plays_slice2.py` GREEN
  (after testing-agent fixed a `call_llm` kwargs bug). Existing 40+ tests
  still GREEN.

### Open / deferred — Slice 3+
- **Monthly Performance Play** (executive) — needs §4 Monitor service hooks.
- **Cross-Board Pulse Play** (NED) — needs cross-context signal aggregation.
- **Team Reporting Play** + **Open Threads Play** — implement after observing
  Slice 1+2 in real demos.
- Plays-aware M13 Ask context biasing.
- Workspace "Play context" right-panel section across all artefacts.
- Pre-Board "pick from Document Journal" — the Arrival stage links there but
  doesn't yet pull a doc into the play (textarea paste only for Slice 2).
- Replace shallow-merge `PATCH /state` with deep-merge.


## §13 Workflows — Slice 3 (2026-04-26, iter26): rename + simplification + Home redesign

### Why
After demo feedback, the user said: "I don't understand what the Play function is
supposed to do as it has been currently executed. The idea is simple — prepare,
review or submit submissions, as part of the quick action tabs." That broke the
simplification audit.

### What shipped
- Rename "Play" → "Workflow" everywhere user-facing.
- Board Pack collapsed from 6 stages to 5 — "Setting the cycle" + "Where the gaps are"
  merged into "Consolidate and review submissions". Pre-Board "When the pack arrives"
  → "Add the board pack".
- PlayHeader chrome stripped (no more "BOARD PACK PLAY" kicker on the workflow page).
- Permanent right-side PortfolioRail on every /app/* page with green dot on the
  active context. Top-bar context + role dropdowns removed.
- Home redesign: QuickActions (3 intent tiles) + InSummaryTiles (4 hot-data tiles).
- Cycle Tracker tab (default): reportee × latest cycle × status × AKKI is missing
  × intervention button.
- Demo seed `/app/backend/scripts/seed_iter26_demo.py` — 16 signals, 4 reportees,
  6 questions, 2 checklists (1 responded, 1 outstanding), 3 briefings, 1 board pack.

## §13.x Agenda Evolution + Document Engagement (2026-04-26, iter26b)

### Agenda Evolution card on Home
- New `routers/agenda.py` → `GET /api/contexts/{cid}/agenda-evolution`. Composes
  from existing collections (last committed/published report → "the meeting",
  submissions/checklists/reports/briefings since → "since then" narrative,
  next dispatched checklist → "next up"). Caps the narrative at 6 lines.
- New `components/home/AgendaEvolutionCard.jsx` — sister card to "Ready for you".
  Editorial (cream + Calendar icon, no progress bars).
- `AppHome.jsx` lines 170-173: `home-ready-row` grid (`grid-cols-1 md:grid-cols-2`)
  pairs `PlayReadyCards` + `AgendaEvolutionCard` 50/50.
- `PlayReadyCards.jsx` now renders an empty placeholder (`home-play-ready-empty`)
  when no auto-launched workflow is waiting, so the grid doesn't collapse.
- `CycleTracker.jsx` copy: "awaiting approval" → "Awaiting your sign-off" with a
  full explanation paragraph at the top of the table (line 132-135).

### Document Engagement Metrics
- New `routers/document_engagement.py` with three endpoints:
  - `POST /contexts/{cid}/documents/{did}/view` — read receipt, deduped per-account
    per-UTC-day (upsert on `(doc_id, account_id, day)`). Owner views are flagged
    but excluded from `unique_readers`.
  - `POST /contexts/{cid}/documents/{did}/share` (body: `{to_email, to_name?, message?}`)
    — records a share intent in `document_shares`.
  - `GET /contexts/{cid}/documents/{did}/engagement` — returns
    `{view_count, unique_readers, readers[], share_count, shares[], linked_count,
    linked_documents[]}`. Linked = ancestors (via `related_doc_id`) + descendants.
- New `components/documents/DocumentEngagement.jsx` panel in the DocumentViewer
  outline rail. Three stat tiles (reads/shares/linked), Read-by/Shared-with/Linked
  lists, and a "Share by email" CTA → in-app modal. Auto-refreshes after submit.
- `DocumentViewer.jsx` fires `POST /view` on viewer mount.
- New indexes (server.py startup): `document_views` unique on `(doc_id, account_id, day)`
  + secondary on `(doc_id, viewed_at desc)`; `document_shares` on `(doc_id, created_at desc)`.

### Tests
- 9/9 new pytests in `test_iter26_engagement.py` GREEN. iter26 frontend critical
  flows verified live (50/50 grid, doc engagement panel, share modal submit).

### Open / deferred — Slice 4+
- Document distribution/engagement: ~~read receipts~~ ✅ ~~share counter~~ ✅
  ~~linked-docs map~~ ✅ — DONE iter26b. SMTP send for share recipients (deferred).
- NED document evolution chain: thread pack → questions → answers → follow-up docs.
- Monthly Performance Workflow + Cross-Board Pulse Workflow (need §4 Monitor hooks).

## §4 Monitor + UX polish (2026-04-26, iter27)

### §4 Monitor — role-adaptive mission-critical touchpoints
- New `routers/monitor.py` → `GET /api/contexts/{cid}/monitor?function=ceo|cfo|coo|commercial|ned|other`.
  Composes from existing collections — signals (filtered by role-relevant categories),
  cycle (overdue + awaiting approval + in-flight checklists, reportees fuzzy-matched
  by area-of-ownership keywords), reports pending the caller, recent briefings,
  document engagement (your-uploaded docs read in last 30 days). NED gets an extra
  `ned` block with `open_threads` + `recent_mentions`.
- New page `/app/monitor` (`Monitor.jsx`). Light editorial layout:
  - Function chip strip (CEO/CFO/COO/Commercial/Other) for executives,
    persisted in `localStorage.akki_monitor_function` so the user lands on
    the same view next session. NED users see no chip strip — single view.
  - 4 tiles in a responsive 2-column grid: Signals · Cycle · Reports awaiting you
    · Document engagement (or Open threads when function=ned).
  - Each tile carries a kicker, headline that summarises the count, sub-content,
    and a single outbound CTA to the relevant detail surface.
- Sidebar entry "Monitor" (Activity icon) wired into `AppShell.jsx` between
  Cycle and Workflows. Route registered in `App.js`.

### Other polish
- **Landing page marketing nav** — added 4 links (About / Features / Security /
  Exco360) to the landing header so the public site's nav matches what's on
  About/Features/Security/Blog pages. Original anchor links and Sign-in/Request
  Access buttons preserved.
- **PortfolioRail role-scoped filter** — the rail now filters contexts by the
  user's `activeRole`. NED users see only NED boards; executives see only
  their executive contexts. Falls back to `c.type` prefix when `my_role` is
  absent (legacy contexts).
- **Learn page horizontal layout** — articles, news, case studies, and videos
  now render in a single `space-y-4 max-w-2xl` column (was a `grid-cols-1
  xl:grid-cols-2` 2-up grid). VideoCard refactored to a horizontal layout
  with a compact `w-40 aspect-video` thumbnail on the left + content on the
  right; play button shrunk from `w-14` to `w-9`.

### Tests
- 15/15 new pytests in `test_iter27_monitor.py` GREEN. Frontend critical flows
  100% verified live (Monitor tiles + chip persistence, nav-monitor present,
  PortfolioRail role filter, Landing nav hrefs, Learn grid layout).

### Open / deferred — Slice 5+
- **Influence Map** (suggested follow-up) — week-over-week reading momentum
  on every doc + "going dark" signals on key decision-makers.
- **NED document evolution chain** — thread pack → questions → answers
  → follow-up docs.
- **Backend prefs persistence for Monitor function** — currently localStorage;
  move to account.preferences for cross-device continuity.
- **Monitor v2** — on-demand LLM commentary per tile ("AKKI, why is this red?").

## §4 Monitor v2 — Strategic Goals tracker (2026-04-26, iter28)

### Why
After demoing Monitor v1 the user clarified the actual mental model:
"Monitor reports on actual operational targets vs success metrics — Strategic
KPIs being tracked at board level (e.g. migrate to new ERP by Dec 2026,
revenue target growth)." And critically: **the user cannot pick their own
function** — the system populates based on profile. NEDs see a scorecard
view (expectation list + score + probability).

### What shipped
- New `routers/strategic_goals.py` with full CRUD + LLM extract:
  - `GET/POST/PATCH/DELETE /api/contexts/{cid}/strategic-goals` (department filter)
  - `POST /api/contexts/{cid}/strategic-goals/extract` reads a context document
    via Claude Sonnet 4.5 (Emergent LLM key, JSON response_format, module
    `strategic_goals.extract`) and seeds 5–12 measurable board-level goals
    tagged to a department (`ceo|cfo|coo|commercial|board`).
- Schema: `{title, description, department, owner_name, target_metric,
  target_value, target_date, current_value, current_score (0-100),
  probability (0-100), status (on_track|at_risk|off_track|achieved|
  abandoned), source_doc_id, source_doc_name}`. Numeric fields clamped via
  Pydantic `conint(ge=0, le=100)`.
- New `components/monitor/StrategicGoalsPanel.jsx` — primary tile on Monitor.
  Goals grouped by department with score + probability dials per row, inline
  edit (status/score/probability/current_value) for executives, read-only
  for NEDs. Empty-state CTA opens the `goals-extract-modal` document picker.
- `Monitor.jsx` rewritten:
  - **Function chip strip removed.** Function is now derived from
    `account.preferences.executive_function` (CEO default if unset). A small
    read-only "Chief Financial (CFO)" chip + "change" pencil opens a
    `FunctionPickerModal` that PATCHes `/accounts/me`.
  - StrategicGoalsPanel is the headline tile; signals/cycle/reports/engagement
    moved to a smaller "Around the goals" secondary section below.
  - **NED scorecard mode** — single read-only view: "Board scorecard.
    What's expected. Where it stands." Goals from every department visible,
    no edit affordances, no extract CTA.
- `PATCH /api/accounts/me` was already accepting arbitrary `preferences`
  (shallow-merge); we just added a new well-known key.

### Landing & Learn polish
- **Landing**: removed the two in-page anchor links ("What it does", "How it's
  trustworthy") since the same content sits in the page. Renamed the marketing
  nav "Security" → "Security Design". Added two stock photo placements:
  - `hero-photo` — sepia-duotoned editorial portrait below the testimonial.
  - `landing-photo-strip` — three-figure section after the rubric strip
    (boardroom · preparation · post-meeting), each with an italic caption.
- **Learn**: tile heights cut by ~50%. ArticleCard switched from
  `akki-stream-card` to compact `px-4 py-3` rounded-md with line-clamp-2
  summary. VideoCard thumbnail halved (`w-40 → w-20`), play button
  `w-9 → w-5`, summary line-clamp-1, vertical density reduced. Grid container
  changed to `space-y-2 max-w-2xl`.

### Tests
- 12/12 new pytests in `test_iter28_strategic_goals.py` GREEN (1 skipped for
  unavailable seed data on the empty-text 400 path — main agent can address
  in a follow-up). Frontend critical flows 100% verified live.

### Open / deferred — Slice 6+
- LLM extract happy-path E2E (currently smoke-tested manually).
- Friendly UX message when extract returns 0 goals.
- First-time exec onboarding banner when `executive_function` is unset.
- Influence Map (still open).
- NED document evolution chain (still open).
- target_date normalization to ISO month for proper sort order.

## §4 Monitor v2.1 + Landing rewrite (2026-04-26, iter29)

### Score history sparkline (improvement suggestion shipped)
- `strategic_goals` rows now carry `score_history: [{score, recorded_at}]`,
  capped at the last 12 entries.
- `POST /strategic-goals` seeds one history point when `current_score` is set.
- `PATCH /strategic-goals/{id}` appends a history point only when
  `current_score` actually changes value (no churn on identical updates).
- `POST /strategic-goals/extract` seeds history on each LLM-extracted goal.
- New `components/monitor/Sparkline.jsx` — pure-SVG 60×20 trend line, stroke
  colour-keyed to the latest score (green ≥70, amber 40-69, red <40).
  Renders an em-dash placeholder when <2 points exist.
- `StrategicGoalsPanel.GoalRow` wraps `ScoreDial + Sparkline` in a
  `goal-score-block-{id}` flex column so the trend sits beneath the score.

### Landing rewrite — direct, executive, creative-director voice
- New headline: "AKKI reads the pack / so you can **read the room.**"
- Old prose paragraph replaced with a numbered three-bullet explainer:
  - 01 — Track strategic goals against where you actually are. Not where the deck says.
  - 02 — Consolidate your team's submissions into board-ready reports. Without chasing.
  - 03 — Cite every number to the page it came from. No unsourced claims.
- Primary CTA: "See it on your sector in 60 seconds" (was "Try AKKI in 60 seconds").
- Tightened first-run, audience, rubric, and closing copy throughout.

### Photo replacement — non-human editorial imagery
- Hero: open historical pages on a desk (1532153975070).
- Strip 1: empty boardroom with leather chairs (1497366216548) — "The room you walk into."
- Strip 2: cathedral-style library (1481627834876) — "Every claim cites a document."
- Strip 3: neoclassical columns at dusk (1521587760476) — "Built for institutions that endure."
- All photos use a `sepia(0.2) saturate(0.85) contrast(1.05)` filter to
  stay inside the cream/oxblood palette without dominating.

### P2 polish shipped
- ExtractFromDocModal now shows a friendly toast.message when the LLM
  returns 0 goals: "AKKI couldn't find board-level goals in that document.
  Try a strategic plan, three-year roadmap, or a board OKR pack." Modal
  stays open so the user can pick a different doc.
- Monitor: `monitor-fn-nudge` inline banner appears when an executive's
  `account.preferences.executive_function` is unset, prompting a one-click
  function pick. Auto-dismisses once set.

### Tests
- 11/11 new pytests in `test_iter29_score_history.py` GREEN. Frontend
  critical flows 100% verified live.

### Open / deferred — Slice 7+
- **NED document evolution chain** (still open) — thread pack → questions
  → answers → follow-up docs.
- **Influence Map** (still open) — week-over-week reading momentum on every
  doc + "going dark" signals on key decision-makers.
- **SMTP send for `document_shares`** (still open) — currently records
  intent only; no email actually goes out.
- target_date ISO normalization for proper sort order.

## §UX big-batch (2026-04-26, iter30)

Eight pieces shipped. Verified by testing agent (9/9 backend + 100%
frontend critical claims).

### Brand & navigation
- **AKKI top-bar** now reads "AKKI" with an italic muted "for Executives"
  (`brand-subtitle`) on screens ≥640 px.
- **Marketing nav** "Security" → "Security Design"; footer
  "Context never leaves your account" → "Your data never leaves your account".

### Score visualisation
- `ScoreDial` rewritten as a conic-gradient ring with banded colours:
  red < 65 (off-track), amber 65–80 (at-risk), green > 80 (on-track).
  Empty state is a dashed circle. Title attribute carries plain-language
  status. Testids `score-dial-red|amber|green`.

### Context → Company rename (UI labels only — not code)
- PortfolioRail "Add context" → "Add company".
- Inactive aria-label "Inactive context" → "Inactive company".
- AppHome "This context" → "This company"; "Your context" → "Your company".
- Marketing footer copy refreshed.

### Role / company switch confirm dialog
- New `switch-confirm-dialog` AlertDialog wraps every `rail-context-{id}`
  and `rail-role-{role}` click. Title and body adapt to the kind of
  switch. Cancel = "Stay where I am". Proceed = "Switch role" / "Switch
  company". Stops accidental loss of context when the user is two clicks
  away from a different board.

### Security marketing copy rewrite
- 4 new promise cards in the user's voice — "Your data stays yours" /
  "Identities are scrubbed" / "Receipts on every claim" / "Leave clean
  any time". H1: "Four things you should be able to verify yourself."
  Posture details rewritten to match the same direct register.

### "See in The Lens" CTA
- `Highlights.jsx` line 386 — "See this through all six lenses" →
  "See in The Lens". One-line copy nudge that clarifies what the CTA does.

### Learn recency tabs
- New `learn-recency-tabs` row below the search bar with three buttons:
  All / Fresh (≤ 5 days) / Stayed a bit (> 5 days OR undated). Counts
  per bucket shown inline. "Stayed a bit" includes undated items so seed
  content remains discoverable.

### Medium-style Blog + RSS + auto-cron
- `Blog.jsx` redesigned Medium-style: featured hero (latest issue) above
  a 2-column reading-list grid. Author byline, kicker, dek, read-time,
  and category surfaced consistently per Medium recommended-stories
  pattern. Subscribe card carries a "Subscribe via RSS →" link.
- New `GET /api/blog/rss` returns Atom XML of the most recent 30
  published posts. Importable into Medium Stories Import.
- New APScheduler cron in `server.py` startup — fires
  `/api/blog/cron/weekly` every Tuesday 10:00 UTC. Logs
  "Exco360 weekly scheduler armed (Tue 10:00 UTC)." on boot.
- `/cron/weekly` upgraded with the user-supplied **PERSONA_PROMPT**
  (Medium ghostwriter persona, 4-phase intake → structure → draft →
  self-critique). Emails superadmins via Resend with a "Review and
  publish →" link instead of auto-publishing (per choice D.c).
- New `POST /api/blog/seed/launch-10` admin endpoint composes 10 launch
  drafts on opportunity / risk / compliance / adoption / growth.
  Idempotent on `topic_seed`. BlogAdmin gets a `seed-launch-banner`
  with one-click CTA.
- BlogAdmin row actions now include **Copy MD** + **Publish to Medium**
  (the Medium API was deprecated in 2023; "Publish to Medium" copies
  the markdown to clipboard and opens medium.com/new-story for paste).

### Tests
- `test_iter30_blog_lens.py` — 9/9 backend GREEN. Frontend 100% on all 8
  batch claims; one minor Learn-recency bucketing issue fixed in-batch
  (undated items now bucket into "Stayed a bit").

## The Lens redesign + Resend send-out + slim Briefing (2026-04-26, iter31)

### The Lens — full redesign
- Two modes share one lens picker:
  - **Stress-test** — input-kind chips (Signal / Claim / Proposal / Question)
    + lens chips above a single textarea. "Apply lens" → existing run
    engine returns Observation → Implication → Action + question-for-management.
  - **Coach** — multi-turn chat through the chosen lens. Lens chips remain
    above the input so the user can switch lenses mid-thread.
- Unified left rail shows **Stress-tests** + **Coaching threads** in one
  timeline of "thinking with AKKI".
- Five new endpoints (POST/GET/GET/POST/DELETE) on
  `/api/contexts/{cid}/lens/coach/sessions`. New `db.lens_coach_sessions`
  collection.

### Resend send-out wired
- `POST /api/contexts/{cid}/shares` (delivery_method=email) AND
  `POST /api/contexts/{cid}/documents/{did}/share` now actually email
  recipients via Resend. Persists `email_send_id`, `email_send_mode`,
  `status` on the share record. Failures are logged; share-intent record
  still persists.

### Briefings — explainer banner (slim-down step 1)
- Page header: "Your 90-second pre-meeting one-pagers" + one-liner
  pointing to Reports for the long-form. Full board-deck migration
  remains queued.

### Learn recency — Fresh bucket populates
- `synthesizedAge()` hash bucketing tuned: ~33/33/33 across Fresh (0-4d),
  mid-Stayed (5-14d), old-Stayed (15-29d).

### Tests
- `test_iter31_lens_coach_email.py` — 11/11 backend GREEN. Frontend 100%
  on Lens redesign + Briefings explainer + regression. Archived-session
  GET tightened post-review (now 404s correctly).

## Iter35 — Login fix + Standalone Chat + Home metrics (Apr 2026)
13/13 backend + 100% frontend e2e GREEN
(`/app/test_reports/iteration_35.json`,
`/app/backend/tests/test_iter35_chat.py`):

### Login bug fix
- `AuthContext.afterAuth` now persists `data.access_token` to
  `localStorage['akki_access_token']` so the Bearer interceptor can
  recover when cross-site cookies are blocked (Safari 16+ ITP, Brave
  shields, Firefox strict, deployed-on-different-domain scenarios).
- `bootstrap()` clears stale tokens on `/auth/me` failure so a
  poisoned token can't loop the user back to the landing page.

### Standalone Chat surface (NEW · `/app/chat`)
- Untethered from any company context — privacy-shielded multi-model
  AI workspace. Replaces the need for separate ChatGPT/Claude/Gemini
  subscriptions.
- 5 models: Claude Sonnet 4.5, Claude Haiku 4.5, GPT-5.2,
  Gemini 2.5 Pro, Gemini 2.5 Flash (via `EMERGENT_LLM_KEY`).
- Conversations persist by default (1a). Per-conversation shielding
  policy: auto (default) · always · off.
- **Auto policy** detects identifiers via `shield_payload()` and
  shields BEFORE sending to provider, then rehydrates the reply.
  Multi-turn references survive shielding (verified live).
- **Policy=off footgun guard**: sensitive content + no acknowledgement
  → 409 `shielding_acknowledgement_required`. User must explicitly
  confirm via bypass dialog; the bypass + reason is audited.
- **Bank-grade audit log** (`chat_audit_log` collection):
  - Append-only (insert only, no updates/deletes from app code)
  - SHA256-chained: each row's `row_hash` = SHA256 of canonical JSON
    of `(prev_hash, id, at, account_id, chat_id, action, payload, ip,
    ua_sha)`. Tampering with any row breaks every downstream hash.
  - Captures IP and `ua_sha` (truncated SHA of user-agent) per event.
  - Never stores raw message content — uses `content_sha256` as a
    fingerprint so auditors can prove existence without exposure.
  - GET `/api/chats/{cid}/audit` returns the chain plus the
    verification recipe.
- Cross-account isolation: every read/write filters on `account_id`
  → 404 on attempts to read another user's chats or audit.

### Home metrics (filling the iter33 gap)
- Six tiles (was four): Signals · Briefings · Cycle · **Reports
  (sent + total drafted)** · Document Journal · **Network (companies +
  team members)**. Grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-6`.

### Open / deferred — Slice 10+
- **Influence Map** — last open P1.
- **Share Evolution Diff CTA** — small extension of `doc_summary`
  share to also share the LLM-generated drift summary across cycles.
- **Role-separation bleed sweep** — NED ↔ Exec UI bleed
  (needs user pointers).
- **Monitor "green stick"** — needs user clarification.
- **Status bar redesign on Signals page** — needs user pointer.
13/13 backend + iter33 regression GREEN. Frontend e2e GREEN
(`/app/test_reports/iteration_34.json`):
- **Share Document Summary** — new `doc_summary` item type on
  `POST /api/contexts/{cid}/shares`. Email body carries TL;DR +
  numbered "What matters" + italicised "Walk in asking" quotes plus
  a deep link to the workspace doc. AKKI-internal recipients still
  get a mention row. Wired into `<DocumentSummaryPanel />` as a
  `Send` gesture next to `Re-read`.
- **Movable home cards** — native HTML5 DnD via
  `useDraggableSections('home', …)` hook. Order persists per user
  to `localStorage['akki:section-order:home']`; reconciliation on
  mount handles added / removed sections. Drag handle appears on
  hover only so the page stays editorial. Reset gesture surfaces
  only after a reorder.
- **NED Document Evolution Chain** — `PATCH /…/documents/{did}` now
  also accepts `related_doc_id` (null to unlink) with self-link,
  cycle, and cross-context guards. New
  `POST /…/documents/{did}/evolution-diff` returns LLM-powered
  what-changed (added_or_strengthened / weakened_or_removed /
  questions_for_management) cached on the doc record. Frontend
  surfaces it as `<DocumentEvolutionPanel />` in the Document Viewer
  right rail with chain ribbon + diff body + LinkVersionDialog
  (filter + unlink).

### Open / deferred — Slice 9+
- **Influence Map** — visualise who's read / shared / commented on
  what. Engagement records already exist (`document_engagement`,
  `shares`, `mentions`); needs an aggregator endpoint + a node-link
  visualisation.
- **Learn refresh agent** — periodic primary-source content puller.
- **LinkedIn API posting scaffold** — manual copy/paste fallback exists.
- target_date ISO sort.

## Iter34 — Three follow-on items (Apr 2026)
13/13 backend + iter33 regression GREEN. Frontend e2e GREEN
(`/app/test_reports/iteration_34.json`):
- **Share Document Summary** — new `doc_summary` item type on
  `/api/shares` with TL;DR + numbered "What matters" + "Walk in
  asking" quotes plus deep link.
- **Movable home cards** — native HTML5 DnD via
  `useDraggableSections('home', …)` hook, persisted to
  `localStorage['akki:section-order:home']`, drag handle on hover.
- **NED Document Evolution Chain** — `PATCH related_doc_id` (with
  self-link / cycle / context guards) +
  `POST /…/documents/{did}/evolution-diff` LLM endpoint returning
  drift (added/weakened/questions). `<DocumentEvolutionPanel />` in
  Document Viewer right rail with chain ribbon + LinkVersionDialog.

## Iter33 — User feedback batch (Apr 2026)
9 page redesigns shipped in one batch, 7/7 backend + 11/11 frontend
verified by testing agent (`/app/test_reports/iteration_33.json`):
- **Lens** — renamed kicker to "In the Lens"; replaced the cluttered top
  rail with a single horizontal picker (Lens dropdown · Test-us dropdown
  · Apply); single textarea labelled by what the user is testing.
- **Home** — InSummaryTiles moved to TOP for at-a-glance scan; fixed
  signal breakdown bug (was bucketing on s.severity which doesn't
  exist; now buckets on s.type → risk/opp/gap); consolidated
  PlayReadyCards + AgendaEvolutionCard + PlaysInProgressStrip +
  QuickActions into one tabbed `<WorkflowsHub />` so the page no longer
  reads as walls of text.
- **Documents/Journal** — replaced upload chalkboard with a stats hero
  (`<DocumentJournalStats />`) showing total / trust split / extracted;
  upload drawer auto-collapses when docs exist; selecting a document
  generates an AKKI summary in the right rail
  (`<DocumentSummaryPanel />`) with TL;DR + What matters + Walk in
  asking. New endpoint
  `POST /api/contexts/{cid}/documents/{did}/summary` (cached on the
  doc record; ?refresh=true bypasses).
- **Signals** — header copy changed to "Risks. Opportunities. Gaps.";
  decorative donut replaced by `<HighlightsStats />` carrying actual
  informational mass (% breakdown bars + 14-day volume sparkline +
  confidence split); generator collapsed to a single quiet line.
- **Briefing** — added a `briefing-journey` block at the top of every
  briefing answering Before / During / After (what this is about · cycle
  & company · what to do once briefed).
- **Compose Report** — new optional `description` field
  (`compose-description-input`) lets the author tell AKKI the angle;
  surfaced as a quoted "What the author asked for" header at the top of
  the starter draft. Backend persists the field on the report record.
- **Simulate** — input-first redesign: hero explains hypothesis testing
  in two lines, journey strip numbers the 01/02/03 input → run → output
  flow, large input card is the obvious thing to use, starters card
  shows when input is empty.
- **Monitor** — renamed Score → Performance Score and Probability →
  Success Probability; aligned the two dials on the same horizontal
  line with the sparkline beneath spanning both; removed the edit
  pencil (the score is machine-generated, not user-editable).
- **Cycle** — tab order reorganised around the 4-step spine: Overview ·
  1·Your team · 2·Question bank · 3·Send checklists · 4·Receive
  submissions · 5·Consolidate & send up. Header copy "Receive ·
  Consolidate · Send up." reinforces the spine.

