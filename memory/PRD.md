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

## Iter37/38 — Login alias · Influence Digest cron · Admin Health Dashboard (Apr 2026)
7/7 backend + 8/8 frontend GREEN
(`/app/test_reports/iteration_37.json`,
`/app/backend/tests/test_iter37_38.py`):

### Login URL aliases
- `/sign-in`, `/login`, `/log-in` → `/signin`
- `/sign-up`, `/register` → `/signup`
- Root cause was a routing gap, not auth logic. Fixed in `App.js`.

### Weekly Influence Digest
- New APScheduler job `influence_digest_weekly` — Monday 08:00 UTC,
  beats the Tuesday Exco360 (10:00 UTC) into the inbox.
- `POST /api/cron/weekly-digest` (X-Cron-Secret guarded) iterates
  every active context, builds the 7-day Influence Map per context,
  emails each executive member their own roll-up. Honours
  `digest_opt_out` flag on context_members.
- `POST /api/contexts/{cid}/influence-map/digest` — manual fire for
  the calling user only. Used by the admin tile + tested directly.
- Editorial email body: top-5 influencers + most-engaged docs +
  totals strip + open-the-full-map CTA. Cream + oxblood + Georgia.

### Admin Health Dashboard (`/admin/health`)
- Superadmin-only one-click pre-deploy / pre-demo green light.
- `GET /api/admin/health/full` runs 6 checks in parallel via
  `asyncio.gather`:
  - **mongo** — ping + insert/delete round-trip on
    `db.health_check`
  - **llm** — 1-token Emergent call, claude-haiku-4-5
  - **resend** — API-key shape + sender-domain config check
    (no email sent)
  - **stripe** — read-only `/v1/balance` probe, distinguishes test
    vs live key
  - **scheduler** — `app.state.scheduler.running` + jobs registered
    with next_run_time
  - **cron_secret** — env presence + length sanity
- Each check returns `{status: pass|warn|fail|skip, evidence|error|
  note, latency_ms?}`; overall is the worst.
- Frontend: auto-runs on mount, manual refresh, 4-status colour grid.
  Live grid currently surfaces two real pre-launch items the user
  should swap before going live: **Stripe (FAIL — placeholder key
  `sk_test_emergent` rejected by Stripe)** and **Resend (WARN —
  sandbox sender; verify a domain)**. Both are env-only swaps.



### Login was broken for users hitting `/sign-in` (with hyphen)
The app's internal links use `/signin`, but external bookmarks, search
engines, old emails, and muscle memory commonly reach for `/sign-in`,
`/login`, or `/log-in`. The catch-all route was silently bouncing
those to `/` (the marketing landing page), which from the user's
perspective looked exactly like "the login is broken." Reproduced
end-to-end: typing `/sign-in` rendered the landing hero, the form
testid never resolved.

### Fix
Added explicit aliases in `/app/frontend/src/App.js`:
- `/sign-in`, `/login`, `/log-in` → `<Navigate to="/signin" replace />`
- `/sign-up`, `/register` → `<Navigate to="/signup" replace />`

Verified end-to-end: typing `/sign-in` now redirects to `/signin`,
form renders, login returns 200, lands on `/app` with token
persisted, dashboard renders, **role-scoped nav correctly hides
Cycle + Workflows in NED mode** (the iter36 surgical fix).


12/12 backend + 100% frontend GREEN
(`/app/test_reports/iteration_36.json`,
`/app/backend/tests/test_iter36.py`):

### Chat — bank-grade audit pack export
- New `GET /api/chats/{cid}/audit/export.zip` — returns a 5-file zip:
  `manifest.txt`, `chat.json`, `messages.json`, `audit_chain.json`,
  `verify.py`. Messages carry `content_sha256` only — raw content is
  never bundled.
- `verify.py` is stdlib-only; runs `python3 verify.py` against the
  unzipped chain and exits 0 ('OK — verified N rows. Chain intact.')
  on integrity, 1 ('hash mismatch') on tampering.
- The export itself appends an `audit.exported` row to the chain.

### Share Evolution Diff CTA (extension of iter34)
- `/api/shares` `item_type` extended with `doc_evolution`; gated on
  cached `evolution_diff.diff.what_changed` + `related_doc_id`.
- Email body now renders the LLM diff blocks: What changed · Added or
  strengthened · Weakened or removed · Put on the table.
- Share gesture mounted on `<DocumentEvolutionPanel />`.

### Influence Map (last open P1)
- New `routers/influence_map.py` aggregates over `document_engagement`
  + `shares` (doc-targeted) + `collab_comments` + `mentions`. Edge
  weights: read=1, share=3, comment=4, mention=5.
- `GET /api/contexts/{cid}/influence-map?days=N` returns nodes
  (people + docs), edges (source/target/kind/weight/last_at), and
  rolled-up `people` / `top_docs` / `totals`.
- New `/app/influence` page — editorial bipartite matrix (people × docs)
  with cell intensity scaling 5 levels of cream → oxblood, glyphs
  ·/◐/●/★ per kind, top-influencers and most-engaged-docs panels,
  7d/30d/90d/1y window picker.

### Role-separation surgical fix
- `NAV[i].roles` flag in `AppShell`. `Cycle` and `Workflows` scoped to
  `executive` only — NEDs no longer see them in the rail. Smallest
  safe change to address the loudest bleed without breaking either
  flow.

### Landing copy
- New `05 · The chat` feature block: "One subscription. Every model.
  Bank-grade audit." Heading updated to "Five surfaces. One discipline."

### Open / deferred — Slice 11+
- Monitor "green stick" — needs user pointer.
- Status bar redesign on Signals page — needs user pointer.
- Deeper role-separation across Highlights, Briefings, Workspace,
  Simulate, Lens (currently identical for both roles).
- Production swap: Stripe live key + Resend verified sender domain
  (env-only, no code).


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

## Iter43 — Tier-A · Strategic Addendum: Quick-Results + Validation chip + Differentiator copy (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_43.json`,
`/app/backend/tests/test_iter43_quick_results.py`):
- **§1.1 Sandbox Quick-Results journey** — new
  `/app/quick-results/:contextId/:docId` page. After a sandbox upload,
  the user lands on a focused screen with **3 doc-bound use-cases**
  (Read me the summary · What does the board need to notice? · Draft
  a briefing for my next meeting). One-click each, output renders
  inline. After ANY result completes, a single "Want more? — Open my
  full sandbox" CTA reveals. Replaces the previous flood-the-stream
  pattern with a "client seeks, client gets" moment. SandboxPackDrop
  now redirects here on successful upload.
- **§4.2 / §5 ValidatedBadge** — `<ValidatedBadge />` chip
  (`Validated by an independent model`) surfaced on briefings header,
  document summary panel (top of summary content), every signal card
  row (after the type chip), and the QuickResults hero. Hover/click
  reveals an editorial methodology popover explaining the second-model
  countercheck. Methodology grounded on the existing Synisense-shielded
  pass; backend-side real second-model validator is a deferred
  follow-up per user steer.
- **§5 Differentiator sublines in Sandbox streaming reveal** — woven
  into existing STREAMING_STAGES (no new stages):
  · stage 0/1 — multi-LLM avatar + "GPT, Claude and Gemini through one
    secure surface"
  · stage 3 — "Wiring AKKI's email handle so it can send checklists"
  · stage 5 — "A separate model counterchecks every claim"
  · stage 8 — "Each section will carry the 'Validated by an
    independent model' mark"


## Iter42 — Cycle drawer fix + Workflow spine + Home metrics + Act-on KPI (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_42.json`,
`/app/backend/tests/test_iter42_signal_kpi.py`):
- **Cycle drawer overlap bug fix** — TabsList swapped from
  `overflow-x-auto` → `flex-wrap` so tabs reflow onto a second row at
  tablet widths instead of sliding under the right portfolio rail.
  PortfolioRail given a soft left-edge shadow as a visual separator.
- **Workflow 4-step spine** — page heading rewritten as
  "Receive · Consolidate · Generate · Submit." A new
  `cycle-spine-strip` renders 4 stages above the tabs with the active
  tab's stage highlighted (`tracker`→none, `reportees|bank|checklists`
  →receive, `inbox`→consolidate, `reports`→generate).
- **Home editorial metrics strip** — replaces the "too SaaS-tile"
  pattern with a single horizontal row of serif numerals separated
  visually by spacing (Signals · Briefings · Documents · Companies ·
  Shared with you). Hidden on empty contexts.
- **Act-on heatmap** (improvement, `/admin/signal-kpi`,
  superadmin-only):
  - `GET /api/admin/signals/action-heatmap` —
    `{by_bucket: [{bucket, acted, shared, recommendations:
    [{label, picks}]}], totals: {acted, shared, share_recipients},
    recent_actions[≤25]}`. Custom (no-rec-idx) acts collapse to
    "(custom — composer)" so the heatmap stays legible.
  - Frontend: per-bucket cards with horizontal pick bars +
    most-recent-25 timeline.


## Iter41 — Tier 2.5 batch (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_41.json`,
`/app/backend/tests/test_iter41_signal_actions.py`):
- **Simulate horizontal scenario rows** — replaced 3-column vertical grid
  with full-width `<ScenarioRow>` (label gutter + body running across at
  ~70-char measure). Best / Base / Stress on stacked horizontal rows.
  Prominent "New simulation" button (`simulate-new-btn`) at the top of
  the viewer.
- **Document Journal — 3 panels → 2** — Summary + Evolution stacked in
  the right rail; Outline moved to a header popover
  (`doc-outline-toggle` + `doc-outline-popover`). Conditionally rendered
  when headings.length > 0.
- **Signals · Act vs Share differentiation** — new
  `signal_actions` collection, `_RECS_BY_TYPE` templates indexed by
  signal bucket (risk / opportunity / gap / neutral), heuristic
  classifier on tone/kind/headline keywords.
  `GET  /api/contexts/{cid}/signals/{sid}/recommendations` →
  `{bucket, recommendations[3]}`.
  `POST /api/contexts/{cid}/signals/{sid}/actions` (acted | shared) —
  resolves `recommendation_label` server-side from idx; persists
  recipients + note.
  `GET  /actions` returns `{actions[], summary: {acted,
  last_acted_label, shared_count, shared_with}}` — `shared_count`
  de-dupes recipients.
  Frontend: 'Act on this' opens a 3-recommendation dropdown
  (`signal-act-menu-{id}` + `signal-act-rec-{id}-{idx}`); 'Something
  else' escape opens the existing ActModal. After action, button flips
  to "Acted on" + indicator chip (`signal-acted-badge-{id}`,
  `signal-shared-badge-{id}`) renders below the summary. Share success
  auto-logs a shared action via `ShareModal.onShared` callback +
  cross-component `akki:signal-action` event-bus.


## Iter40 — Strategic Goals card overhaul + Sandbox KPI dashboard (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_40.json`,
`/app/backend/tests/test_iter40_goals_kpi.py`):
- **Strategic Goals card overhaul** per user spec:
  - `category` field added (revenue | customer | product | people |
    operations | compliance) — top-left chip, color-coded.
  - `initiatives_count` (0–99) — small layered icon + count in the
    secondary row.
  - Conic dials replaced with slim horizontal **progress bars** sitting
    side-by-side on a single row to the right of the title, equal
    spacing.
  - **Narrative under each bar** ("At risk. Drift is real but
    recoverable." / "Plausible — assumes the current trajectory
    holds.") — answers "what does a 78 mean".
  - Tight whitespace — title row + secondary row, two clean editorial
    lines.
  - "How is this calculated?" hoisted to the panel header (single
    instance, not per-row).
  - LLM extraction prompt updated to populate both new fields;
    backend whitelist-clamps invalid values.
- **Sandbox Conversion KPI dashboard** (`/admin/sandbox-kpi`,
  superadmin-only) — closes the Q5 measurement loop:
  - `GET /api/admin/sandbox/kpi` — totals (captured / answered / yes /
    partial / no / skipped + answer-rate-% + delivery-rate-%) +
    per-sector breakdown sorted by volume.
  - `GET /api/admin/sandbox/objectives?limit=&sector=&answer=` —
    most-recent-first list with answer + free-text note, server-side
    filtered.
  - Aggregation handles BOTH sandbox-typed and seeded real contexts
    (sandbox_metadata vs seeded_metadata via `_flatten_meta`).
  - Frontend: 4 stat tiles + sector table + objectives list with
    sector + answer filters; non-superadmin redirected to /app.


## Iter39 — Tier 1 gap-plug + Tier 2 quick wins (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_39.json`,
`/app/backend/tests/test_iter39_briefings_objective_check.py`):
- **24-hour objective-check follow-up** — `GET/POST
  /api/sandbox/contexts/{id}/objective-check`. Surfaces ~24h after
  generation, captures yes/partial/no + optional note (or `skip`).
  Works on both sandbox + seeded real contexts.
  `<ObjectiveCheck />` rendered on AppHome below the tutorial card.
- **Briefings read tracking** — `briefing_reads` collection (Mongo
  upsert per (briefing_id, account_id)). `POST
  /api/contexts/{cid}/briefings/{bid}/mark-read` with
  `via: "manual"|"scroll"`. List endpoint annotates each row with
  `is_read` / `read_via` / `read_at` for the caller. Frontend:
  Mark-as-read button in the viewer header + auto-mark on ≥70%
  scroll-depth + read-state indicator on rail rows + total/unread
  count in rail header.
- **Monitor green sparkline removed** — replaced with a discreet
  "How is this calculated?" methodology popover so a sceptical user
  can audit the score's machine-generated derivation.
- **The Lens — Apply repositioned** — picker row now holds only the
  two dropdowns; Apply moved BELOW the input description. Natural
  read → apply flow.
- **Cycle deadline picker** — replaced free-text deadline input with
  `<input type="date">`; YYYY-MM-DD is converted to "DD Month YYYY"
  for the dispatch email body (UTC-explicit to avoid TZ drift).
- **Compose Report tile** — `<ComposeReportTile />` replaces the
  inline corner button. Surfaces contextual notes:
  "AKKI has all the information you need." (all reportees in) /
  "N direct reports haven't responded to AKKI yet." (pending) /
  "No reportees set up yet." (empty roster).
- **Tutorial copy** — sector-narrative framing per the doc:
  "A story shaped to what you came here for."


## Iter38 — Tier 1 · Sandbox conversion overhaul (Apr 2026)
100% backend + 100% frontend GREEN
(`/app/test_reports/iteration_38.json`,
`/app/backend/tests/test_iter38_sandbox_tier1.py`):
- **Capture testing objective** — Sandbox + Add Company now ask Q5
  ("What would make this trial feel like time well spent?"). Stored
  on `sandbox_metadata.objective` / `seeded_metadata.objective`.
- **Tutorial-style first-run card** — `/api/sandbox/contexts/{id}/tutorial`
  returns objective recap + first seeded brief + first signal headline +
  3 step links + suggested chat opener. `<SandboxTutorial />` renders on
  AppHome; dismiss persists via `/tutorial/dismiss`.
- **Hybrid serif streaming reveal** — Generation page redesigned. Each
  stage now has `headline` + `sublines[]` (1–3 italic Georgia lines that
  reveal one-by-one inside the stage window). Paper-tape scrolls upward
  with serif headlines + italic sublines. No terminal/code aesthetic.
- **Other-sector free-text** — Picking "Other" reveals `other_sector_name`
  + `other_sector_description`; `resolve_stage_texts` substitutes the
  user's named sector into the streaming narrative.
- **Add Company unified flow** — `NewWorkspace.jsx` rewritten to mirror
  the Sandbox 5-question editorial journey. Submits to new
  `POST /api/sandbox/contexts/seeded` which provisions a real
  (executive_personal/ned_personal) context, seeds the matching sector
  template, and returns the new context for `switchContext()`.
- **Dropdown contrast bug** — `select.jsx` SelectTrigger now sets
  `text-foreground` so selected values render in dark ink (was white-on-
  white in some pages).
- **Chat ?prompt= deeplink** — `/app/chat?prompt=…` pre-fills the
  composer, then strips the param. Used by tutorial card "Open in Chat".


## Iter36 — Audit pack · Influence Map · Share evolution diff · Role bleed (Apr 2026)
12/12 backend + 100% frontend GREEN
(`/app/test_reports/iteration_36.json`):
- **Chat audit pack export** — `GET /api/chats/{cid}/audit/export.zip`
  returns 5-file zip (manifest + chat + messages + chain + verify.py).
  Stdlib-only verifier; passes on integrity, fails on tampering.
- **Share Evolution Diff CTA** — `/api/shares` `item_type='doc_evolution'`
  with full LLM-diff email body. Wired into `<DocumentEvolutionPanel />`.
- **Influence Map** — `routers/influence_map.py` aggregator across
  engagement + shares + comments + mentions; `/app/influence` page with
  editorial bipartite matrix view + top-influencers/top-docs panels.
- **Role-separation surgical fix** — `NAV[i].roles=['executive']` on
  Cycle + Workflows; NEDs no longer see them.
- **Landing copy** — `05 · The chat` block + heading "Five surfaces.
  One discipline."

## Iter35 — Login fix + Standalone Chat + Home metrics (Apr 2026)
13/13 backend + 100% frontend GREEN
(`/app/test_reports/iteration_35.json`,
`/app/backend/tests/test_iter35_chat.py`):
- **Login fix** — `AuthContext.afterAuth` now persists `access_token`
  to localStorage as a Bearer fallback for browsers blocking
  cross-site cookies (Safari ITP, Brave, Firefox strict). `bootstrap()`
  clears stale tokens on `/auth/me` failure.
- **Standalone Chat surface** at `/app/chat` — privacy-shielded
  multi-model AI workspace untethered from any company context. 5
  models via `EMERGENT_LLM_KEY`. Bank-grade audit log
  (`chat_audit_log` collection, SHA256-chained, IP + UA-hash
  captured, content stored as `content_sha256` only).
- **Home metrics** — added Reports (sent + total drafted) and
  Network (companies + team members) tiles. 6 tiles total.

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


## §UX iter49 — Real validator + Mark-as-read + Plays-aware Ask + Workflow rail (2026-04-28)

### Why
Burn down the iter48 backlog so only architectural Tier-C work remains.

### What shipped
- **Mark-as-read on Activity timeline** (`/app/activity?cat=*`) —
  per-user, per-context, persisted in `localStorage` under
  `akki.activity.read.{cid}`. Read items render italic + muted, no
  unread dot. New "Mark all read" button.
- **Real second-LLM validator** — `llm_service.validate_independent`
  (Gemini 2.5 Flash) runs after Claude drafts a brief, returns
  `{verdict, confidence, notes[], validator_provider, validator_model}`.
  Persisted on the brief record. ValidatedBadge accepts a `validation`
  prop and renders a verdict-coloured chip with a hover popover showing
  the validator's notes and identity. Soft-fails closed
  (verdict='qualified', 'Validator unavailable') so the brief endpoint
  is never gated by validator outage.
- **Plays-aware M13 Ask** — the `/ask` prompt now includes an
  `[ACTIVE WORKFLOWS]` block listing up to 3 currently-active plays for
  the context so answers frame themselves in the user's working state.
- **Workspace 'Workflow context' panel** — third right-rail section on
  the Document Journal listing active plays in the company with click-
  through to `/app/plays/{id}`. Light-touch link today; ready to upgrade
  when play↔doc linkage ships.
- **Polish**: `_target_date_sort_key` lifted to module scope in
  `strategic_goals.py` (no per-request regex compile). Deprecated the
  redundant `validated: True` boolean on briefs in favour of
  `validation.verdict`. Stable `prepare-brief-history-{id}` testid on
  the past-brief rail rows.

### Tests
- iteration_49.json — backend 6/6, frontend 95% (all features
  verified; one minor click-target selector stability nit fixed in
  the same iteration).

### Open / deferred — Tier-C only
- Minutes as first-class entity (large architectural — needs new doc
  type, extractor, linkage to Cycle/Monitor; will plug into Prepare's
  right rail as a third tab).
- Personal vs Enterprise tier split (largest — separate billing + data
  models; needs scoping conversation with the user).
- Inbound email parsing/receiving (needs Postmark or Resend Inbound
  API key from the user).
- Concurrency optimisation: issue Gemini validator concurrently with
  audit-log writes via `asyncio.gather` to keep p50 brief latency
  under 30s once warm.
- framer-motion stagger first-paint nit on AppShell NAV.


## §UX iter48 — Activity grouped + Sandbox accept-upload + Backlog burn-down (2026-04-28)

### Why
Two new user asks added to the queue, and the user instructed "ensure
all pending requests are tracked and the backlog is not significant".
Iter48 ships both new asks plus the small/medium backlog items so only
genuinely architectural Tier-C work remains.

### What shipped
- **Activity feed regrouped** (`RecentActivity.jsx`) — five category
  tiles instead of a chronological list: Briefings & meetings ·
  Questions answered · Signals surfaced · Documents added · Sent your
  way. Each tile shows count + verb + latest title + "View timeline →".
  Tiles with zero count render disabled. AppHome now also fetches
  `/contexts/{cid}/briefs` so "Questions answered" reflects saved briefs.
- **Activity timeline page** (`/app/activity?cat={key}`) — chronological
  day-grouped list for the chosen category, category-pill switcher,
  back-to-Home link.
- **Sandbox accept-upload** — new `GET /api/sandbox/contexts/{cid}/sample-doc`
  returns a tailored "this could be your board pack" preview;
  `POST /api/sandbox/contexts/{cid}/sample-doc/accept` materialises it
  as a real document and stamps `sandbox_metadata.sample_doc_accepted`.
  Frontend: `SandboxSampleDoc` card on AppHome (sandbox-only, hidden
  once accepted). Sits ABOVE the existing drop-your-own affordance.
- **BriefDetailModal Continue-in-Chat chip** — navigates to
  `/app/chat?prompt=…&new=1&seed_title=…`. Chat now auto-creates a fresh
  conversation with the title, seeds the composer with the brief body,
  and strips the query params after consumption.
- **InSummary Portfolio aggregation** — pending_actions now folds in
  `c.pending_actions` across the role-scoped portfolio (max of portfolio
  aggregate vs active-context number).
- **Strategic-goals sort** — list endpoint now sorts by a normalised
  target_date key (handles `YYYY-MM-DD`, `Q1-Q4 YYYY`, `Mmm YYYY`,
  null-last). Editorial sort order on the Strategic Goals card is now
  deterministic.

### Tests
- iteration_48 — backend 6/6 (after testing agent fixed a bad
  `write_audit` call in `sandbox_sample_doc_accept` — wrong kwargs +
  missing `await`), frontend 95% (Continue-in-Chat testid was reachable
  by code but not by data; main agent then seeded a brief for Bramuel
  so it is now exercisable).

### Open / deferred — Tier-C only
- Minutes as first-class entity (will become a third tab in Prepare's
  right rail).
- Personal vs Enterprise tier split.
- Inbound email parsing/receiving.
- Real second-LLM ValidatedBadge pass.
- Plays-aware M13 Ask context biasing.
- Workspace "Play context" right-panel section.

### Cleanups parked (not blocking)
- framer-motion stagger on AppShell NAV (mild first-paint nit).
- Lift `_sort_key` regex compilation out of `list_goals` to module scope.


## §UX iter47 — Prepare 2-col rail + Dynamic Workflow dock + Recent activity (2026-04-28)

### Why
Targeted user feedback after iter46 acceptance:
  1. Move Document Journal up in the sidebar (was last).
  2. Drop the word "consumed" from the Reports InSummary attribute.
  3. Make the Workflow dock dynamic — surface most popular / unused / new
     features / "Monitor your performance" by relevance, not statically.
  4. The bottom four-tab block on Home was duplicating the InSummary
     above — propose a better hook.
  5. Restore the visual stats dock from the old standalone Signals page
     onto Prepare → Signals.
  6. Add a right-side list rail to Prepare with topic + timeline filters
     that swaps brief↔signal based on the active tab.

### What shipped
- **Sidebar reordered** — Home → Document Journal → Chat → Prepare → …
- **Reports tile** — first attribute now reads "submissions" (not "submissions consumed").
- **Dynamic Workflow dock (`QuickActions.jsx`)** — every tile carries a
  `priority(state)` function. We compute scores from the user's actual
  data (unread briefings, pending reports, in-progress plays, recent
  docs, signal count) and surface the top 3. New tiles: "Monitor your
  performance" (steady mid-priority, links /app/monitor), "Catch up on
  briefings" (only when unread > 0), "Surface signals on something"
  (boosted when totalSignals = 0; opens /app/prepare?tab=signals).
- **RecentActivity (`components/home/RecentActivity.jsx`)** — single
  chronological feed merging signals + briefings + documents + shared
  items into one editorial timeline ("DOCUMENT ADDED · 3d ago"). All-
  boards / This-company toggle is now wired to AppHome's existing scope
  state (was label-only — now genuinely behaviour-changing). Replaced
  the four-tab summary repeater entirely.
- **Prepare 2-col layout** — main column (form + tab section header) at
  left; new `PrepareSideRail` at right with topic search + 7d/30d/All
  timeline chips. Rail tab swaps brief↔signal based on active tab. Lifted
  briefs/signals fetch state to the page so the rail can refresh after
  a generate event.
- **Brief / Signal detail modals** kept inline (no extra route). New
  Delete affordance added to BriefDetailModal next to Send-to-colleague.
- **HighlightsStats restored** — the standalone-Signals visual the user
  remembered (sparkline + risk/opportunity/gap breakdown bars +
  confidence summary) is now mounted on Prepare → Signals when at
  least one signal exists. Brief tab keeps the calmer PrepareStatsDock
  with the three progress-bar cards.
- **Prepare deep-link** — `/app/prepare?tab=signals` lands directly on
  the Signals tab (used by the new Quick Action tile).

### Tests
- iteration_47.json — 11/11 frontend acceptance items pass at 100%.
  Two minor reviewer nits addressed in the same iteration (scope toggle
  no longer label-only; try_signals tile lands on Signals tab via deep
  link).

### Open / deferred
- Tier-C: Minutes as first-class entity (will plug into Prepare's right
  rail as a third tab).
- Tier-C: Personal vs Enterprise tier split.
- Tier-C: Inbound email parsing.
- Real second-LLM ValidatedBadge pass.


## §UX iter46 — Role isolation + InSummary redesign + Sidebar reorder (2026-04-28)

### Why
User feedback batch: workflow dock was getting truncated; intro copy
needed updating; explicit role toggle (NED/Exec) needed; strict role
isolation rule across the entire system; sidebar reorder + renames;
InSummary tile metrics rewritten; Prepare page lacked visual lift.

### What shipped
- **Sidebar reorder + renames** (`AppShell.jsx`):
  Home → Chat → Prepare → Workflows (exec) → The Lens (POV) → Test
  Hypothesis (was Simulate) → Reporting Cycle (was Cycle, exec) →
  Monitor → Learn → Influence Map → Document Journal.
- **ContextChooser**: new copy "You work in X companies as NED and Y as
  Executive. Where would you like to start?" with role-toggle buttons
  (`home-role-ned`, `home-role-executive`). Filter only shows contexts
  for the active role.
- **Strict role isolation** (`AuthContext.switchRole` + `QuickActions`):
  Switching role rebuilds the experience — if active context's
  `my_role` mismatches new role, redirect to `/app` and pick a same-org
  fallback if available. QuickActions tile filter no longer exposes the
  other role's tiles.
- **`my_role` enrichment** (`AuthContext.enrichContexts`): /auth/me
  sometimes omits `my_role`; we now derive it from `c.type` (`ned_*` →
  ned, `executive_*` → executive) so every consumer has a single source
  of truth.
- **InSummaryTiles fully rewritten**: each tile carries hero number +
  3 attribute lines per spec (Signals/Briefings/Reporting Cycle/Reports/
  Documents/Portfolio).
- **Workflow dock truncation fix**: removed `overflow-hidden` on the
  AppHome content wrapper that was clipping Quick Actions cards on
  narrower viewports.
- **PrepareStatsDock**: new component above the line tabs with three
  progress-bar cards (Brief coverage, Signal pulse, Briefing rhythm).

### Tests
- iteration_46.json — frontend: sidebar order + renames, role toggle,
  context-chooser intro, InSummary structure, Prepare stats dock,
  WorkflowsHub truncation all pass.
- After my_role enrichment fix verified manually:
  intro = "You work in 6 companies as NED and 5 as Executive."
  Portfolio attrs = "6 acting as NED · 5 acting as Exec · 0 pending".
  NED chip list = 6 chips. Switching to Exec → 5 chips, right rail
  swaps to Exec-only contexts, sidebar gains Workflows + Reporting
  Cycle.

### Known nits / follow-ups
- "0 pending actions" on Portfolio when scoped to a single context;
  could aggregate across all contexts a user holds the active role on.
  Deferred — current scope is "today's focus".
- True same-org context-switch on role change requires `org_id` on
  ContextRecord, which isn't always populated. Falls through to "any
  context with new role" gracefully.

### Next (Tier-C — sized for separate sessions)
- Minutes as first-class entity
- Personal vs Enterprise tier split
- Inbound email parsing
- Real second-LLM ValidatedBadge pass


## §UX iter45 — Prepare redesign + Send-to-colleague + Tier-B pills (2026-04-27)

### Why
User feedback after iter44: "Replace [the line-tab inline blurbs] with
'Generate Brief' and 'Generate Signals'. Describe the section beneath the
selection line before the input box. Redesign the section under the line
tab dock. Organise input, output and list nicely." Plus: ship the full
backlog and the suggested improvement (send-to-colleague chip).

### What shipped
- **Prepare page redesigned** — line tabs now carry just labels (Brief /
  Signals). Below the tabs: a section kicker ("Generate Brief" /
  "Generate Signals") + descriptive serif blurb. Form box reorganised into
  three zones — **Step 1** (kind / focus chips) → **Step 2** (objective /
  focus textarea with character counter and inline help) → **Action** (the
  validated-by-independent-model badge on the left, primary button on the
  right). Recent items list now sits under a proper section divider with
  an "X saved" tabular count.
- **Send to a colleague** chip on `BriefDetailModal` — opens the existing
  `ShareModal` with `itemType="brief"`. Backend `routers/shares.py`
  extended to accept `brief` as an `ItemType`; cross-context 404 guard
  intact.
- **Continue with [doc] topbar pill** (Tier-B) — new
  `components/layout/ContinueWithPill.jsx`. Records the last document
  the user opened (in QuickResults or DocumentViewer) into
  `localStorage.akki_continue_with`. The pill renders in the AppShell
  topbar across every authed page, hidden on `/app/workspace` and
  `/app/quick-results/*` where it would be redundant. Stale > 7 days
  auto-clears. Click takes the user back to QuickResults; X dismisses.
- **Chat model avatar visual** (Tier-B) — new
  `components/chat/ModelAvatar.jsx`. Provider-coloured monograms
  (oxblood C for Claude, ink G for GPT, gold ✦ for Gemini). Wired into
  the model picker trigger, dropdown rows, and every assistant message
  bubble so the executive sees at a glance which model produced which
  reply.
- **Helper extracted** — `helpers/llm_json.py:safe_parse_json` consolidates
  the fence-strip + prose-fallback logic that was duplicated in
  `prepare.py` + `plays.py`. Behaviour-equivalent.
- **Cleanup** — removed the now-unrouted `pages/Highlights.jsx` and
  `pages/Briefings.jsx` files.

### Tests
- `test_iter45_shares_brief.py` — 9/9 backend GREEN (brief share happy
  path, 404, regression on existing share types, safe_parse_json
  regression via brief CRUD).
- `test_iter44_prepare.py` — 12/12 STILL GREEN.
- Frontend 100% on Prepare redesign, ContinueWithPill, ModelAvatar
  picker + bubbles, sidebar Prepare entry, redirect from /app/highlights
  and /app/briefings.

### Open / deferred — Tier-C and beyond
- Minutes as first-class entity (anchor for Cycle + Monitor) — needs new
  doc type, extraction, linkage. Sized for its own session.
- Personal vs Enterprise tier split (`akki.ai/personal` vs
  `akki.ai/enterprise`) — separate billing/data models. Sized for its
  own session.
- Inbound email parsing/receiving integration — needs an external
  inbound provider (Postmark / Resend Inbound).
- Upgrade `ValidatedBadge` to a real second-LLM validation pass
  (currently re-uses Synisense shielding).


## §UX iter44 — Prepare consolidation + tone polish (2026-04-27)

### Why
Per Apr-2026 user feedback: "Combine Signal and Briefing into one section.
Use line tabs to separate the two. When loading these pages, do NOT
pre-populate them with data. Prompt the user to generate." The Strategic
Addendum also asked for a calmer, less-marketing post-login register.

### What shipped
- **Sidebar consolidation** — Signals + Briefings nav entries replaced with a
  single **Prepare** entry (`AppShell.jsx` line 33).
- **Routing** — `/app/prepare` registered in `App.js`. `/app/highlights`
  and `/app/briefings` now `<Navigate>` to `/app/prepare` (no link rot).
- **Backend router** — `prepare_router` now mounted in `server.py`. The
  `prepare.py` LLM JSON parser was hardened with a fence-strip pass + prose
  fallback (was 502'ing when Claude wrapped the JSON in a code fence).
- **Frontend `Prepare.jsx`** — two line-tabs (Brief / Signals). Brief tab is
  on-demand: pick a kind chip (claim/proposal/topic/period/report), state
  your objective, generate, save. The result opens **inline as a Dialog**
  (no separate route — saves one URL surface). Signals tab follows the same
  filter + focus + generate pattern; results refresh in place.
- **Cross-link migration** — every `/app/highlights` and `/app/briefings`
  string in `MentionInbox`, `ActModal`, `SandboxTutorial`, `InSummaryTiles`,
  `AppHome`, `QuickResults`, `Monitor` migrated to `/app/prepare`. The old
  URLs still resolve via redirect.
- **Tone polish** — softened a handful of slightly-promotional strings:
  - SandboxBanner: "Ready to use AKKI on your real data?" → "When you're
    ready, AKKI will read your real pack the same way."
  - Manage page H1: "Keep your team and your companies tidy." → "Your
    team and your companies." Sub: "Quiet, no ceremony."
  - HealthDashboard H1: "One-click green light." → "Pre-flight, in one
    read."

### Tests
- iteration_44: 12/12 backend tests in `test_iter44_prepare.py` GREEN.
  Frontend 100% (Prepare flow + redirect verification + sidebar entry).
  No regressions. Test report: `/app/test_reports/iteration_44.json`.

### Open / deferred — Slice 8+
- Tier-B: persistent "Continue with [doc]" topbar pill (Quick-Results in
  product).
- Tier-B: multi-LLM model switcher in standalone Chat + avatar visual.
- Tier-C: Minutes as first-class entity (anchor for Cycle + Monitor).
- Tier-C: Personal vs Enterprise tier split (`akki.ai/personal` vs
  `akki.ai/enterprise`).
- Tier-C: Inbound email parsing/receiving integration.
- Upgrade `ValidatedBadge` from a Synisense-shielded re-skin to an actual
  second-LLM validation pass.
- Refactor: extract `_safe_parse_json` helper out of `prepare.py` +
  `plays.py` into a shared `helpers/llm_json.py` (review note).
- Delete-orphaned: `/app/frontend/src/pages/Highlights.jsx` and
  `/app/frontend/src/pages/Briefings.jsx` are no longer routed but the
  files remain (kept in case the user wants to roll back). Remove after a
  stability window.

### 2026-04-28 — iter51/52 · Tier-C: Postmark inbound + Minutes extractor + Personal-Enterprise split
**Postmark inbound email**
- New router `/app/backend/routers/inbound_email.py`. Endpoints:
  - `GET /api/inbound/address[?context_id=…]` — auth-required. Mints / returns
    the user's `inbound+<account_token>@inbound.akki.ai` address (and a
    `inbound+<account>.<ctx>@…` context-scoped variant). Tokens are 8-char
    URL-safe slugs persisted on `accounts.inbound_token` /
    `contexts.inbound_token`.
  - `POST /api/inbound/postmark?secret=<TOKEN>` — Postmark webhook receiver.
    Verifies shared secret (env: `POSTMARK_WEBHOOK_SECRET`, falls back to
    `POSTMARK_SERVER_TOKEN`), parses `From / Subject / TextBody / Attachments`,
    routes by `MailboxHash`, picks the most useful attachment (PDF > DOCX >
    TXT > first), runs through the existing `extract_text` pipeline, writes a
    fully-fledged `documents` row tagged `source: 'inbound_email'`. Idempotent
    on `(context_id, inbound_message_id)`. Auto-tags `doc_type='minutes'` if
    subject contains "minutes" or any attachment filename does.
- Settings → Integrations now wired (was M6-locked) and renders
  `InboundEmailPanel` showing the personal + ctx-scoped forwarding addresses
  with copy-to-clipboard buttons.
- `POSTMARK_SERVER_TOKEN` added to `/app/backend/.env`.

**Minutes extractor end-to-end**
- Fixed `prepare.py:extract_minutes` — `call_llm` was being called with
  wrong kwargs (`system_message`/`user_message`); switched to the actual
  signature (`module / user_query / system_override / response_format`).
- Prepare → Minutes UI (`Prepare.jsx`) now renders an "Extract" button per
  row when `minutes_meta` is missing, and a "Show extract" toggle when it
  exists. The expanded detail surfaces attendees / decisions / actions /
  open questions inline.

**Personal vs Enterprise (light-split, option 1a)**
- New backend router `/app/backend/routers/enterprise.py`:
  - `POST /api/enterprise/interest` (auth) — captures `{use_case, company_size, timing}`.
  - `GET /api/enterprise/interest/me` — returns latest submission.
- New frontend page `/app/enterprise` (`Enterprise.jsx`) — calm, editorial
  lead-gen surface. Form flips to a thank-you state once submitted.
- AppShell: a small "Akki for Enterprise" pill renders in the left rail
  (above Settings) **only** when the active context type is `ned_personal`
  or `executive_personal`. Click → `/app/enterprise`. No structural code
  split; same login, same shell.

**Header trust badge**
- Centred and reordered to "INTERNAL · SECURE · CONFIDENTIAL" in `AppShell.jsx`.
  "Internal" remains oxblood (`var(--accent)`); "Secure" + "Confidential"
  use the muted text colour. Centred via `absolute left-1/2 -translate-x-1/2`.

### Tests
- iteration_51 — backend: 16/16 new + 6/6 iter50 regression GREEN.
- iteration_52 — frontend: 5/5 surfaces (trust badge, Settings →
  Integrations, /app/enterprise, Minutes Extract toggle, upsell pill).
- Reports: `/app/test_reports/iteration_51.json`, `/iteration_52.json`.

### Open / deferred
- Optional polish on Enterprise: surface an "Update my note" affordance once
  a lead has been submitted (today the form short-circuits to thanks state).
- Optional ops-visibility: an `inbound_rejected` audit row when the webhook
  soft-fails (bad attachment, virus scan).
- Defence-in-depth: unique sparse index on `accounts.inbound_token` /
  `contexts.inbound_token` (currently uses _mint_token() collision-free in
  practice but lacks a DB-level guarantee).

### 2026-04-28 — iter53 · Deep-tier (Claude Opus 4.6) routing + per-surface daily quota + Minutes→Cycle one-click
**Tier system (`/app/backend/llm_service.py` + `/app/backend/llm_tier_quota.py`)**
- `call_llm()` now accepts `tier="fast" | "standard" | "deep"`. Model ids are
  read from env (`LLM_MODEL_FAST` / `LLM_MODEL_STANDARD` / `LLM_MODEL_DEEP`)
  so we can swap to Opus 4.7 the moment the Emergent key catalogue picks it
  up — no code change. Defaults today:
  - fast → `gemini-2.5-flash` (validation/extraction)
  - standard → `claude-sonnet-4-5-20250929` (today's default)
  - deep → `claude-opus-4-6` (long-form narrative, decks, blog)
- `llm_tier_quota.py` adds per-account-per-day quotas, persisted in
  `llm_deep_usage{account_id, surface, day_utc, count}`. Defaults (env-overridable
  via `AKKI_DEEP_QUOTA_<SURFACE>`):
    `brief=10`, `blog=5`, `deck=3`, `chat=30`, `validate=20`, `minutes=5`.
- `call_llm_with_tier(surface, account_id, requested_tier, call_args)` wraps
  the whole "check quota → consume → call → graceful fallback" flow. When a
  user is over their daily deep budget the call transparently downgrades to
  standard tier and the response carries
  `quota.{requested_tier, served_tier, downgraded, remaining, limit, used, reset_at}`.

**Surfaces wired**
- **Brief generation** (`POST /api/contexts/{cid}/briefs`) — accepts
  `deep:true` to opt in. UI exposes a "Deep mode" checkbox with a live
  "X/N today" indicator (`prepare-brief-deep-toggle`). Saved brief carries
  `tier` and `model_id` for audit.
- **ExCo360 blog generation** (`POST /api/blog/compose`, admin) — always
  deep tier. Quota state surfaced on response.
- **Minutes narrative** (NEW: `POST /api/contexts/{cid}/minutes/{doc_id}/narrative`)
  — 250–400 word editorial summary on the deep tier. Persisted at
  `documents.minutes_narrative.{body,model,tier,generated_at}` so re-renders
  are instant. Re-running silently overwrites.

**New endpoint: `GET /api/llm/quota[?surface=…]`** — auth-required.
Read-only; returns today's deep-tier usage so the UI can render an accurate
"X/N today" hint.

**Minutes → Cycle dispatch (one-click)**
- New endpoint: `POST /api/contexts/{cid}/minutes/{doc_id}/to_cycle`.
- Walks `minutes_meta.actions[]` and seeds one row per action into the
  `questions` collection with `source='minutes:<doc_id>'`,
  `source_label='<title> (<date>)'`, and best-effort assignment to a
  reportee whose `name` matches `action.who` (exact match → first-token
  match → unassigned).
- Idempotent on `(context_id, source, text)` — re-running on an unchanged
  doc adds zero duplicates.
- Returns `{seeded[], unmatched[], next:'/app/cycle?ctx=<id>'}` so the UI
  can show "5 matched · 2 unassigned · Continue to Cycle →".
- UI: 'Turn into checklist' button on the Minutes detail panel
  (`prepare-minutes-to-cycle-<id>`) + a 'Draft narrative summary' button
  (`prepare-minutes-narrative-<id>`) that calls the deep-tier endpoint.

### Tests
- iteration_53 — backend: 9/9 pass (live Opus call confirmed
  tier=deep / model_id=claude-opus-4-6 / quota auto-downgrades cleanly on
  exhaustion). Frontend smoke OK. No regressions on iter51/52.
- Report: `/app/test_reports/iteration_53.json`.

### Open / deferred
- When Emergent catalogue lists `claude-opus-4-7`, swap by setting
  `LLM_MODEL_DEEP=claude-opus-4-7` in `/app/backend/.env`. No code change.
- Race-tighten: `check_and_consume()` reads-then-upserts; on simultaneous
  deep requests at `used=N-1` two could both pass. Acceptable 1-call slop
  for now; switch to `find_one_and_update({count:{$lt:limit}}, $inc:{count:1})`
  if integrity becomes a concern.
- Decks surface — quota slot already reserved (`deck=3/day`). Build the
  generator when the design is ready.
- Optional: 'Regenerate narrative' affordance with a confirm-overwrite UX.

### 2026-04-28 — iter54 · Admin LLM-spend dashboard + race-safe quota + ops audit polish
**Admin · LLM Spend (`/admin/llm-spend`, superadmin-only)**
- New backend `routers/admin_llm_spend.py`. `GET /api/admin/llm/spend?days=N`
  rolls up `llm_deep_usage` into:
  - tiles: total calls / est cost / active accounts / window
  - by-surface bars (calls + accounts + default cap)
  - 14-day daily sparkline
  - top 20 accounts (email · top surface · calls · est cost)
- Unit cost configurable via env `AKKI_DEEP_UNIT_COST_USD` (default $0.045).
- Frontend `pages/admin/LLMSpend.jsx` with the same cream/oxblood editorial
  pattern as `/admin/health`, `/admin/sandbox-kpi`, `/admin/signal-kpi`.

**Race-safe deep quota**
- Added unique index on `llm_deep_usage(account_id, surface, day_utc)`.
- `check_and_consume()` reworked to two-pass atomic flow:
  1. `find_one_and_update({key, count<limit})` — if matched, $inc; allowed.
  2. Otherwise `insert_one({key, count:1})` — duplicate-key error means
     row already exists at cap → deny.
- iter54 verified: 5 parallel calls at cap=10 → count stays exactly 10.
  (Was overflowing by 1 in iter53.)

**Ops audit polish**
- `inbound_email.rejected` audit rows now written on Postmark soft-fails
  (`bad_attachment` / `virus_scan`). EICAR test-file path verified.
- Sparse indexes on `accounts.inbound_token` and `contexts.inbound_token`.

**Frontend polish**
- Enterprise page: 'Update my note →' affordance on the thanks state
  (testid `enterprise-update-note-btn`) returns to the form.
- Minutes narrative regenerate now `confirm()`s before overwriting.

### Tests
- iteration_54: backend 10/10 + frontend 100% + 4 admin screenshots captured
  (`/app/test_reports/screenshots_iter54/admin_*.jpg`). No regressions on
  iter51/52/53.

### Open / deferred
- LLMSpend "by surface" bar uses `pctOfTotal` so the top surface is always
  100%; consider switching to `max-of-window` for more legible distribution.
- For >100k seeded accounts, paginate `by_account_top` and pre-aggregate
  rather than scanning all rows.
- Inbound rejections without a MessageID share the literal `(no-id)` as
  audit resource_id — could collide; consider a uuid fallback.

### 2026-04-28 — iter55 · Decks pipeline + behaviour monitoring + admin index
**Decks generator (`/app/decks` + 4 backend endpoints)**
Three-step flow that prevents budget waste on weak prompts:
1. **Outline (STANDARD tier — free of deep budget)**
   - `POST /api/contexts/{cid}/decks/outline` body `{intent, audience?, target_slides?}`.
   - Sonnet plans the deck against actual context (40 most-recent docs, 30 signals, 20 briefs); returns `research_question`, `evidence_used[]`, `missing_context[]`,
     `context_sufficiency`, proposed `slides[]`. User reviews & may iterate
     (`parent_outline_id`) before any deep call fires.
2. **Generate (DEEP tier — 1 of 3 daily slots)**
   - `POST /api/contexts/{cid}/decks/{outline_id}/generate` body `{outline_id, confirmed:true, edits?}`.
   - 400 if `confirmed:false`; 409 if outline already consumed (forces iteration).
   - On budget exhaustion → graceful fallback to Sonnet with `quota.downgraded:true` and a UI banner.
3. **Quality check (FAST tier — free)**
   - `POST /api/contexts/{cid}/decks/{deck_id}/quality_check`.
   - Gemini Flash scores 0-100 across coherence / evidence / audience-fit and
     returns `free_refinements[]` (edits the user can make WITHOUT regenerating).
   - Recommends regen only when `score<55` AND issues can't be edited away.
4. **Feedback (free)** — `POST .../feedback` `{rating:'up'|'down', will_regenerate?}`.

**Behaviour monitoring**
- `deck_telemetry` collection captures outline iterations, sufficiency,
  quality_score, user_rating, will_regenerate.
- `GET /api/admin/llm/decks/quality?days=N` rolls up:
  decks_generated · outlines_drafted · outline_to_deck_ratio · avg_outline_iterations ·
  avg_quality_score · thumbs_up/down · satisfaction_pct ·
  user_will_regenerate_count · quality_recommends_regen_count ·
  insufficient_context_count · partial_context_count.
- Surfaced in `/admin/llm-spend` as the new "Deck quality · behaviour" panel
  (Avg quality / Outline → deck / Satisfaction / Insufficient ctx).

**Admin control room (`/admin`)**
- New landing page tying all five admin surfaces together with at-a-glance
  pills (Health: green / LLM spend: $32.64 7d / Deck quality: q94 · 4 decks / Sandbox: 0/0 / Signals: 0 acts).

**Backlog cleared**
- LLMSpend by-surface bars now use **max-in-window** (top fills track,
  others scaled to it) — fixes the always-100% top bar from iter54.
- Inbound rejection audit row now uses `no-id-<uuid8>` fallback when
  Postmark MessageID is missing.
- Enterprise "Update my note →" verified.
- Minutes-narrative regenerate confirm verified.

### Tests
- iteration_55: backend 11/11 functional pass + frontend testids verified +
  3 screenshots captured. End-to-end flow verified live: outline → confirmed
  generate → Opus 4.6 deck → quality 93/100 → feedback persisted.
- Screenshots: `/app/test_reports/screenshots_iter55/{decks_step1, admin_index, admin_llm_spend}.jpeg`.

### Open / deferred
- Decks step 2/3 e2e screenshots blocked by ingress 502 on long Opus calls
  during the testing pass (curl flow OK). Capture after 00:00 UTC reset
  with a fresh user.
- Optional: persist `outline.edits` so re-generation regenerates against the
  edited outline (today the edits ride on the generate call but aren't
  versioned).
- Optional: per-account daily deck-quality average alert threshold.

### Backlog tracker (P-bands)
P0: none.
P1: Postmark inbound stream URL one-time wire-up in Postmark dashboard (user task).
P2: Decks UI E2E retest after midnight; max-of-window label phrasing on
    LLMSpend; opt-in "auto-regenerate when quality<55".

### 2026-04-28 — iter56 · Final backlog clear · regen-reason learning loop + admin alerts
**Regen-reason learning loop**
- `FeedbackIn.regen_reason` enum added: `audience_drift | weak_research_question |
  missing_evidence | wrong_tone | other`. Persisted on `decks.user_feedback.regen_reason`
  and `deck_telemetry.user_regen_reason`.
- Frontend: clicking 👎 on a deck now opens a reason-chips panel
  (`decks-regen-reason-panel`) before submitting feedback. Each click
  records the feedback with regen_reason set.
- **The actual learning loop**: `create_outline()` now queries the user's
  most-recent regen_reason (scoped to the same context) and folds it into
  the planner prompt as a `LEARNING FROM THIS USER'S PRIOR DECKS` block.
  The new outline persists `learning_hint_used` for telemetry visibility.
- Verified live: feedback `weak_research_question` → next outline returns
  `learning_hint_used: "the research question was too weak — user said: …"`
  → planner produces a tighter research_question (zero deep budget).

**Outline-edit versioning**
- `generate()` now persists `edits_applied: {...}` AND snapshots the
  post-edit `research_question / slides / audience_assumed` onto the
  outline record. Admin views & history now show what was actually
  generated, not just what was originally proposed.

**Admin alerts & coaching list**
- `GET /api/admin/llm/decks/quality` now returns:
  - `alerted_accounts[]` — users with ≥3 of last 5 decks scoring <55.
    Each entry: `{account_id, email, name, weak_count, window, avg_score}`.
  - `top_regen_reasons[]` — sorted reason counts so ops can see whether
    failures cluster on audience/question/evidence/tone.
  - `alert_threshold:55, alert_window:5, alert_min_hits:3` — env-overridable later.
- Frontend `/admin/llm-spend`:
  - **`llm-spend-deck-alerts`** amber panel — coaching list, "ned X · 47/100 · 5 of last 5 weak".
  - **`llm-spend-regen-reasons`** panel — top-N reasons with counts.

**Cosmetic**
- LLMSpend by-surface bar label now reads "X% of total · Y% of top".
  Bar geometry already used max-of-window from iter55.

### Tests
- iteration_56: backend 7/7 + admin panels verified live + 2 admin
  screenshots captured. Regen-chip UI structurally verified in source
  (testing agent flagged a pre-existing context-switch quirk on /app/decks
  that blocked live click; backend persistence proven via API).
- Reports: `/app/test_reports/iteration_56.json`,
  `/app/test_reports/screenshots_iter56_*.jpg`.

### Open / deferred (P2, low)
- **Context-switch on /app/decks**: clicking a NED context from the
  portfolio sidebar while on /app/decks doesn't always re-filter sidebar
  to that role. Pre-existing; orthogonal to the deck pipeline. Worth a
  separate small investigation — likely AppShell role state sticky.
- **Auto-regenerate when quality<55 (opt-in)**: telemetry now captures
  the signal but we haven't built a one-click "regenerate with the lesson
  baked in" yet. Easy follow-up: button on the deck quality panel that
  drafts a new outline + immediately confirms-and-generates if quota
  available.
- **Per-account quality-score threshold env-override**: hard-coded as
  `QUALITY_ALERT_THRESHOLD=55, WINDOW=5, MIN_HITS=3`. Promote to env vars
  (`AKKI_QUALITY_ALERT_*`) when ops want to tune.

### 2026-04-29 — iter58 · AKKI Solve surfacing + Walk-in card + backlog clear
**Branding & positioning**
- "Solve" → **"AKKI Solve"** everywhere. Tagline locked:
  *"For the board problems that don't have tidy answers."*
- Public landing page (`/`) now has a dedicated dark-themed Solve section
  (`landing-solve-section`) anchored after the three-guarantees rubric;
  eyebrow nav button (`landing-nav-solve`) makes it the first thing a
  returning visitor sees.
- New public marketing page **`/solve`** (SolveLanding.jsx): hero, 4-phase
  framework explainer, vs-Chat comparison, two CTAs.
- New in-app placeholder **`/app/solve`** (AppSolve.jsx) with
  notify-when-ready interest capture. Sidebar nav item placed between Chat
  and Workflows with a "Preview" pill.

**Walk-in question card (the iter57 improvement, shipped)**
- New backend endpoint `POST /api/walkin {kind,artefact_id,context_id}`.
  Sonnet-tier (free of deep budget). Cached on the artefact under
  `walkin_question`. Idempotent: subsequent calls return `cached:true`.
- `POST /api/walkin/regenerate` clears cache and re-runs.
- Supports `kind ∈ {brief, minutes, deck}`. Membership-gated.
- Frontend `<WalkInCard>` component wired into:
  - `/app/decks` (after slides),
  - `/app/prepare → BriefDetailModal` (under brief body),
  - `/app/prepare → MinutesExtractDetail` (under narrative).
- Each card shows: "Walk in with this question" (oxblood overline) →
  the question in serif italics → a why-line → "New" + "Continue in Chat" actions.
- Verified live: deck question came back as
  *"If our highest-risk AI model failed silently today, how many days
  until someone in this room would know — and who would tell us?"*

**Backlog cleared**
- **Decks outline iteration chip**: when `outline.iteration ≥ 2`, surface
  "Iteration N · still no deep slot used" + "Tightened from your last
  feedback" if learning_hint_used is set (`decks-outline-iteration-chip`).
- **Activity weekly grouping**: when timeline span ≥ 7 days, day headers
  collapse to "Week of <Mon date>" instead of `Friday, 28 April`. Span <7
  keeps day-of-week labels.
- **Deck deep-link routing**: `/app/decks/:deckId` opens the deck review
  surface directly. Falls back silently to intent if not found.
- **`app-solve-thanks` testid** added to AppSolve.jsx thanks state.

### Tests
- iter58: backend 12/12 + frontend 5/5 (after testing-agent fixed a
  duplicate `Layers` import that crashed the whole app — caught early,
  fixed in the same iteration).
- Reports: `/app/test_reports/iteration_58.json`,
  `/app/test_reports/screenshots_iter58_*.jpg`.

### Open / deferred
- AKKI Solve full module build (waves 1-3) — APPROVED with these
  refinements:
  - Pushback 1 (integrations): all approved.
  - Pushback 2 (cost): build a **Pro tier budget model** — paid users
    get the highest-quality model, free users get Sonnet-streamed
    synthesis with Opus opt-in via existing deep quota.
  - Pushback 3 (triangulation): MUST be in v1 scope; user OK with
    evolutionary build (start simple, sharpen).
  - Pushback 4 (cluster expansion at 200+ sessions): approved.
  - Q2 (save/resume): users get BOTH continue-where-they-were AND
    start-over options.
  - Q3 (MVP-of-MVP): ship full framework with all clusters, optimize
    around the model.
- ESLint `no-redeclare` rule should be added to CI to prevent the kind
  of duplicate-import regression iter58 hit.
- `/admin/llm-spend?panel=decks` deep-link routing (admin-side analog
  of the deck deep-link we just added).

### 2026-04-29 — iter59/60 · Sandbox cookie-poisoning bug fixed
**RCA**
- `get_current_account()` in `core.py` checked the `access_token` cookie
  *before* the Authorization header, then short-circuited 401 on the
  first credential that failed to decode. A returning visitor with an
  expired session cookie would land on /sandbox, complete the form,
  receive a fresh Bearer JWT in the handoff — and still get 401'd on
  /api/auth/me because the stale cookie was inspected first. AuthContext
  caught the 401, wiped the localStorage Bearer, set account=false →
  ProtectedRoute on /app bounced them to /signin. Symptom user
  reported: "after the sandbox relationship is set, it goes to /signin".

**Fix (two layers, belt-and-braces)**
1. `core.py::get_current_account` — now tries every credential the
   request carries (Bearer first, then cookie), accepting the first
   that decodes valid. Self-heals against any client with mixed credentials.
2. `routers/sandbox.py::generation_status` — when the sandbox is ready,
   `Set-Cookie: access_token` and `refresh_token` are written on the
   /status response itself. The fresh cookies overwrite any stale ones
   in the browser before the next request goes out.
3. `AuthContext.bootstrap` catch — also POSTs `/auth/logout` (best
   effort) on failure so a poisoned cookie clears server-side too.

**Verified end-to-end (browser repro):**
- Phase A (clean sandbox flow) ✅
- Phase B (stale `access_token` cookie planted before /sandbox) ✅
- Phase C (post-handoff /app/settings?tab=account navigation) ✅
- iter60 testing-agent report: 3/3 phases pass; bug closed.

**Tests / reports:**
- `/app/test_reports/iteration_59.json` — RCA + repro
- `/app/test_reports/iteration_60.json` — fix verified

### 2026-04-29 — iter61 · AKKI Solve Wave 1 + auth observability + walk-in context hint
**AKKI Solve · Wave 1 SHIPPED**
- 12-cluster taxonomy seeded into `solve_clusters` (idempotent — operator
  edits survive redeploy). Clusters: revenue_underperformance,
  ceo_succession, strategy_drift, risk_blindspot, performance_management,
  capital_allocation, regulatory_change, tech_debt_or_outage,
  people_conduct, ma_thesis, board_dynamics, founder_transition.
- 4-phase state machine engine (`routers/solve_engine.py`):
  Surface → Depth → Synthesis → Lock-in → completed. Each phase: one
  user turn + one Solve turn; phase advances on each turn submission.
  Synthesis and Lock-in bodies persisted on `session.synthesis` /
  `session.lockin` for fast re-render.
- Pro-tier deep synthesis: when `account.solve_pro=true` AND user opts
  in via `pro_tier:true`, synthesis routes to Opus (tier=deep) and
  consumes a slot from the new `solve` quota surface (4/day default,
  isolated from decks/brief budgets).
- Save/resume: continue OR start-over (per iter58 user direction).
  Restart abandons old session and clones cluster+intent.
- Endpoints: GET /api/solve/clusters, POST/GET /api/solve/sessions,
  GET /api/solve/sessions/{sid}, POST /api/solve/sessions/{sid}/turn,
  POST .../restart, POST .../abandon.
- Frontend: `/app/solve` rebuilt as 3-view module — PickerView (12
  clusters + resume list), IntentView (textarea + Pro toggle + use-example),
  SessionView (phase stepper + turns + composer + completed banner).

**Walk-in card "in this context" hint (iter58 improvement)**
- `/api/walkin` now folds the active context name + 3 most recent
  un-archived signals into the prompt. Same Sonnet tier — questions
  feel like they come from someone who sits on this board, not a
  generic helper.

**Admin · Auth observability (iter60 improvement)**
- `core.py::get_current_account` now records sampled auth events
  (failures always; successes at AKKI_AUTH_OBSERVE_RATE, default 0.01).
  Captures: timestamp, ok/fail, reason, credentials carried, dual_mismatch,
  authed_via, path, method.
- New endpoint `GET /api/admin/auth/events?hours=N` (superadmin) rolls
  up failure rate, by_failure_reason, by_credential, top_paths,
  dual_credentials_seen/mismatched, recent 50 events.
- New page `/admin/auth-events` with 4 tiles + 3 panels + recent table.
  6th admin-tile added to /admin index.

**ESLint regression guard**
- Added `/app/frontend/.eslintrc.js` with explicit no-redeclare,
  no-dupe-keys, no-dupe-class-members, no-duplicate-imports rules.
  Catches the iter58 duplicate-Layers-import class of regression at
  lint time.

### Tests
- iter61: backend 12/12 pass + frontend Solve picker→intent→session→
  phase-advance verified end-to-end with real LLM (~100s).
- Pytest file: `/app/backend/tests/test_iter61_solve_engine.py`.
- Report: `/app/test_reports/iteration_61.json`.

### Open / deferred (post-Wave 1)
- Wave 2: Solve→Brief / Solve→Deck / Solve→Cycle handoff (per iter58
  pushback 1). Synthesis lock-in commitments seed Cycle questions.
- Wave 3: triangulation v2 — curated comparable corpus with sector +
  scale matching (currently uses cluster-level placeholders).
- Pro account UI: subscription affordance to flip `solve_pro=true`.
  Today the flag is set manually in Mongo for testing.
- Walk-in card test for admin-side render in panel `prepare-minutes-narrative-body-<id>`.
