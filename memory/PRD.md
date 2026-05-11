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


## §AKKI Solve — Wave 2 (Handoff Trio) + Wave 3 (Triangulation v2) + Pricing (2026-04-29, iter62)

### Wave 3 — Triangulation v2 corpus
- New `/app/backend/solve_comparables_seed.py` — **27 curated anonymised
  comparables** across all 12 clusters (≥2 per cluster after the iter62
  top-up). Each carries `cluster_id`, `sector_tag`, `scale_tag`,
  `diagnosis_summary`, `what_worked`, `what_didnt`, `source_type`. Strict
  rule: no real company names; every comparable closes with a verdict
  (worked/didn't) so the LLM grounds the diagnosis in lived board
  experience rather than abstractions.
- `db.solve_comparables` indexed on `id` (unique) +
  `(cluster_id, sector_tag)`. Idempotent seeding on startup.
- Engine helper `_pick_comparables(cluster_id, sector_tag)` picks closest
  3 with preference order: same cluster + matching sector → same cluster
  + 'any' sector → same cluster + any sector. Sector pulled from session
  context's `sector` or `industry` field.
- Synthesis prompt now embeds the picked comparables under a
  `CURATED COMPARABLES` block instructing the LLM to reference at most
  one or two inline ('A comparable mid-cap bank…', 'In one industrials
  case…') without naming companies.
- Persisted to `synthesis.comparables[]` for the UI side panel.

### Wave 2 — Handoff Trio (Solve → Brief, Decks, Cycle)
- Three new endpoints on completed Solve sessions
  (`require_completed_session` gate — must have synthesis AND lock-in):
  - `POST /api/solve/sessions/{sid}/handoff/brief` — creates a
    `db.briefings` row with synthesis as `opening_paragraph` and lock-in
    parsed into Decide / Watch / Walk-in items. Tagged with
    `solve_session_id` + `mode='solve_handoff'`.
  - `POST /api/solve/sessions/{sid}/handoff/decks` — seeds a
    `db.deck_outlines` row with intent = synthesis + lock-in summary,
    research_question = original Solve intent, and 5 starter slides
    (Diagnosis · Comparables · Decide · Watch · Walk in with). User
    refines and commits the deep-tier render via the existing decks
    pipeline — Solve handoff does NOT consume deck quota.
  - `POST /api/solve/sessions/{sid}/handoff/cycle` — inserts 1-3 questions
    into `db.questions` derived from lock-in lines (Walk-in → lead
    question, Watch → trigger probe, Decide → block check). Source field
    set to `AKKI Solve · <cluster_label>`.
- All three are **idempotent within a session** — second call returns
  `already_exists: true` with the original artefact id. Recorded in
  `db.solve_handoffs` (compound natural key on `session_id + target`)
  AND denormalised into `solve_sessions.handoffs[]` for fast list reads.
- `_parse_lockin_lines` tolerates markdown bold and bullet prefixes
  (`**Decide:**`, `- Decide:` all parse cleanly).
- Membership gate: Solve handoffs require active membership of the
  destination context (`_ensure_membership`).
- New `GET /api/solve/sessions/{sid}/handoffs` for inspection.

### Pricing — Solve Pro bundled into existing Pro plan
- Per user direction ("less friction, high stickiness"):
  - Pro plan ($29/mo) and Team plan unlock unlimited deep synthesis
    (gated by existing `solve` daily quota of 4 in `llm_tier_quota`).
  - **Free users get 1 free deep synthesis per UTC month** via
    `db.solve_free_grants` (compound unique index on
    `(account_id, month_utc)`). First click of the Pro toggle as a free
    user atomically claims the grant; subsequent calls in the same
    month fall through to the standard tier (transparent downgrade —
    `synthesis.free_grant_used: true`).
- New `_user_is_pro()` checks `account.plan in (pro, team)` OR explicit
  `account.solve_pro=true` flag (legacy / manual override).
- Frontend Pro toggle copy now communicates: "Pro plan gets unlimited
  deep synthesis; on the free plan you get 1 free deep synthesis per
  month".

### Frontend — AppSolve UX
- `HandoffStrip` component on completed sessions: 3 tile buttons (Brief
  / Decks / Question Bank), context picker (auto-selected when user has
  one context), per-target emerald-state when handoff already exists.
  Toasts on success; inline error rendering.
- `ComparablesPanel` rewritten to render the new corpus shape: sector +
  scale tag overline, serif diagnosis line, accent-tagged Worked / muted
  Didn't lines. Backwards-compatible string fallback.
- Picker adds a second list — **'Completed — hand off ready'** — so
  users can return to the handoff strip after navigating away.
- `solve_sessions.handoffs[]` denormalised array consumed by
  HandoffStrip for first-render emerald state.

### Tests
- iter62: backend **11/11 pytest pass** against live LLM
  (~3:26 wall-time). Frontend 100% verified end-to-end.
- Pytest file: `/app/backend/tests/test_iter62_solve_wave2_wave3.py`.
- Report: `/app/test_reports/iteration_62.json`.

### Open / deferred (post-Wave 2/3)
- Pro billing surface: Stripe checkout flow specifically for Solve Pro
  upgrade (currently piggybacks on existing Settings → Billing tab).
- Wave 4: Solve session export as PDF (briefing-style narrative).
- Comparable corpus expansion (currently 27; aim for 40+ across
  English / European / US board cases as adoption broadens).
- `/app/decks` context-switch quirk (orthogonal pre-existing P1 — may
  not be reproducible now after the role-isolation work in iter46).
- Defence-in-depth: `_consume_free_grant` race-safe via duplicate-key;
  consider promoting to `find_one_and_update` upsert pattern.
- Cycle handoff: question text currently echoes the lock-in line
  verbatim (with "How do we hold ourselves to:" prefix). A short LLM
  pass to phrase as a sharp board question would polish further.



## §AKKI Solve — Wave 4 (PDF) + P1/P2 cleanup batch (2026-04-29, iter63)

### Wave 4 — narrative PDF export
- New `/app/backend/solve_pdf.py` — reportlab-driven A4 portrait
  one-pager: PRIVATE · AKKI SOLVE overline, intent as serif title,
  cluster + completion meta, **THE DIAGNOSIS** (synthesis body, markdown
  bold/italic stripped), **COMPARABLE DIAGNOSES** (sector + scale tag
  overline, anonymised summary, oxblood "Worked:" + muted "Didn't:"
  lines), **LOCK-IN** (Decide / Watch / Walk in with as a 2-column
  table), Synisense-shielded footer with last-8 of session id.
- New endpoint `GET /api/solve/sessions/{sid}/export.pdf` — returns
  `application/pdf` with `Content-Disposition: inline; filename=akki_solve_<intent_slug>.pdf`.
  Rejects sessions without synthesis (409) and unknown sessions (404).
- Frontend `solve-session-pdf` button on the SessionView header (right
  of "Back", left of "Pause for later"). Authenticated download via
  fetch + blob → object URL so the browser doesn't open the raw stream.

### Free-grant race-safety hardening
- `_consume_free_grant` rewritten from try/except DuplicateKeyError to
  atomic `find_one_and_update` with `$inc: count` + `$setOnInsert` on
  `first_used_at` + upsert. The post-increment count tells us if this
  is the first call (allow) or a subsequent one (deny). Race-safe
  even if the unique compound index regresses. 8-way `asyncio.gather`
  yields exactly 1 allowed=True.

### Cycle handoff polish — LLM-sharpened questions
- New `_draft_cycle_questions` helper — single STANDARD-tier LLM call
  (`module=solve.cycle_handoff`, `response_format=json`) takes the
  cluster label + intent + synthesis + lock-in (Decide/Watch/Walk-in)
  and returns 1-3 sharp board questions phrased to be answerable
  yes/no/with-a-number. No more verbatim "How do we hold ourselves to:"
  echoes. Falls back to the deterministic derivation if the LLM call
  fails or returns nothing — preserves the iter62 baseline behaviour.

### Pro upgrade CTA + pro-status endpoint
- New `GET /api/solve/pro-status` — returns
  `{is_pro, plan, free_grant: {claimed_this_month, month_utc, remaining}}`
  for the calling account. UI uses this to decide whether to render
  the Pro toggle as "1 free synthesis available" / "Pro account —
  unlimited" / "you've used your monthly free; upgrade for more".
- `IntentView` Pro toggle copy now switches dynamically based on
  `proStatus`. When a free user has claimed their grant and ticks the
  Pro toggle, an oxblood-bordered `solve-pro-upgrade-cta` card appears:
  "Subscribe to Pro for unlimited deep synthesis. $29/mo… You'll still
  get the standard tier on this session at no charge." with a deep
  link to `/app/settings?tab=billing`.
- `_user_is_pro` continues to derive Pro from `account.plan in (pro,
  team)` OR explicit `solve_pro` flag.

### Smart "Recommended" handoff pill
- `HandoffStrip` now picks the most useful UNDONE handoff target based
  on context type:
  - NED context → cycle (board-room follow-up) → brief → decks
  - Executive context with open questions → cycle → brief → decks
  - Executive context, no questions yet → brief → cycle → decks
  - The pill cascades — once the primary recommendation is done, it
    promotes the next undone target. Pill hidden when contextId is
    empty or all three handoffs are done.
- Recommended target's tile gets an oxblood ring + Sparkles icon for
  unmistakable focus. Pill text reads `RECOMMENDED FOR THIS CONTEXT:
  <Label>` (data-testid `solve-handoff-recommendation`).

### Decks context-switch state reset (P1 fix)
- `Decks.jsx` `useEffect([cid])` now clears `view`, `outline`, `deck`,
  `history` BEFORE the new context's data loads. Prevents the old
  context's deck from briefly rendering under the new context's name
  during a switch. Pre-existing P1 bug — closed.

### Comparable corpus expansion
- `/app/backend/solve_comparables_seed.py` topped up from 18 → **27
  curated comparables**. Every cluster now ships ≥2 (most ship 3).
  New entries cover sparse clusters: people_conduct (industrials +
  financial_services), ma_thesis (financial_services + tech_saas),
  board_dynamics (any · 2), founder_transition (tech_saas +
  consumer_goods), performance_management (tech_saas), capital_allocation
  (financial_services), regulatory_change (tech_saas),
  tech_debt_or_outage (financial_services), strategy_drift (tech_saas).

### Tests
- iter63: backend **11/11 pytest pass** (~62s). Frontend: Decks
  context-switch reset visually confirmed; PDF button + Pro upgrade
  CTA + recommended pill all interactively validated by main agent
  post-testing-agent.
- Pytest file: `/app/backend/tests/test_iter63_solve_p1p2.py`.
- Report: `/app/test_reports/iteration_63.json`.

### Open / deferred (post-Wave 4)
- `solve_engine.py` is now ~1080 lines — split Wave 2 handoffs into
  `/app/backend/routers/solve_handoffs.py` before Wave 5.
- Comparable corpus aim for 40+ entries with European / US / African
  board cases as adoption broadens.
- "Recommended" pill could honour `account.preferences.preferred_handoff`
  for users who consistently pick the same target.
- Stripe-driven Solve Pro upgrade CTA could route through a dedicated
  `/api/solve/upgrade` flow (today it deep-links into the existing
  Settings → Billing tab).



## §iter64 — Studio (Decks + Reports merge) + Catch-up rename + Marketing redesign brief (2026-04-29)

### User feedback that drove this iteration
> "Combine Decks and Workflow — this is where the user comes to produce
> reports and presentation. Workflow keeps a record of generated reports
> and decks and scores their confidentiality and sensitivity for awareness
> once it's generated or saved. Enterprise version - Documents generated
> from this section have some type of electronic marker that can track
> who has read it to track information exposure score."
>
> "Change 'Prepare' to 'Catch-up'."
>
> "Akki is so powerful and needed but the website is not doing it justice.
> A lot of the conversion driving features are not surfaced, and there
> is long-winded copy that takes long to land the value promise. Tone
> should target seasoned and emerging executives and non-executive
> directors interested in tools, frameworks or mindsets that grow or
> preserve value for their shareholders. People love the look and feel."

### A · "Prepare" → "Catch-up" rename
- Sidebar entry (AppShell.jsx) renamed from "Prepare" to "Catch-up".
- /app/prepare page header rewritten: "Catch-up · {context}" /
  "Catch up on what's next."
- QuickActions home surface: "Read & catch-up for tomorrow".
- Route URL kept as /app/prepare for back-compat — only labels changed.

### B · Decks + Workflows merge → "Decks + Reports" Studio
- Sidebar primary nav: "Decks" → "Decks + Reports". "Workflows"
  removed from primary nav (deep link /app/plays still works for
  in-flight Board Pack journeys; the home WorkflowsHub widget keeps
  the tabbed in-progress view).
- /app/decks header rewritten to position the Studio surface as the
  unified place to produce material:
    Decks + Reports · Studio
    Produce board-grade material with your own data.
    Decks + Reports is the secure place you draft material that
    leaves your hands. Every saved artefact is auto-classified —
    Public · Internal · Confidential · Restricted — and tracks
    who's read it so you know your information exposure before
    you share.

### C · Auto-sensitivity scoring on every saved artefact (decks + briefings)
- New `/app/backend/studio_sensitivity.py` — deterministic regex
  scorer with 9 rules covering M&A, conduct/HR, litigation, financial
  figures, restructure, MNPI/insider, customer concentration,
  pre-announcement, leadership succession. Score 0-100 mapped to
  4-tier classification:
    0-24 → Public · 25-49 → Internal · 50-74 → Confidential ·
    75-100 → Restricted
- Reasons[] array surfaces what triggered each bump so users can
  sanity-check the classification.
- Hooks into:
  - `routers/decks.py` line ~365 — auto-score on `decks/{outline_id}/generate`
  - `routers/briefings.py` line ~143 — auto-score on briefing create
  - `routers/solve_engine.py` line ~554 — auto-score on Solve →
    brief handoff
- Idempotent backfill endpoint
  `POST /api/contexts/{cid}/studio/backfill_sensitivity` for
  pre-iter64 artefacts. Backfilled 14 existing decks + briefings
  for Tuli NED context on first call.
- Frontend `SensitivityChip` component (Decks.jsx) — emerald for
  public, amber for internal, orange for confidential, red for
  restricted. Tooltip surfaces reasons. Rendered top-right of every
  history row + DeckStep header.

### D · Real read-receipt tracking + exposure score
- New `routers/studio.py` — Studio cross-artefact endpoints:
  - `POST /studio/{kind}/{id}/view` — atomic upsert keyed on
    `(artefact_kind, artefact_id, account_id, day_utc)`. Same-day
    repeat views return `deduped: true`. Owner views tracked but
    excluded from `unique_readers`.
  - `GET  /studio/{kind}/{id}/engagement` — full engagement summary
    with `view_count`, `unique_readers`, `readers[]` (with display
    names / emails / first/last viewed), `share_count`,
    `external_share_count`, `exposure {score, band, inputs}`.
  - `POST /studio/{kind}/{id}/share` — records a share with
    `to_email`, `to_name`, `external` flag.
  - `POST /studio/{kind}/{id}/rescore` — re-runs the scorer.
  - `GET  /studio/history` — merged decks + briefings desc by
    created_at with sensitivity + exposure folded in (single round-trip).
- `kind` enum: `deck` | `briefing`.
- Exposure score (0-100):
    raw = unique_readers·12 + share_count·18 + external_shares·22
    raw += 10 if days_since_creation > 14
    capped at 100; bands low/moderate/high.
- Frontend `ExposurePill` — muted/amber/red by band. Rendered
  alongside SensitivityChip on history rows + DeckStep header.
- DeckStep auto-fires `POST /view` on mount + fetches engagement
  to render the readers strip.
- New collections + indexes:
  - `db.studio_views`: unique compound on
    `(artefact_kind, artefact_id, account_id, day_utc)`, plus
    `(context_id, artefact_kind)`.
  - `db.studio_shares`: indexes on `(artefact_kind, artefact_id)`
    and `(context_id, created_at)`.
  - Top-up indexes on `db.decks` and `db.briefings` for the history
    sort.

### E · Studio history strip on /app/decks
- `StudioHistoryStrip` component renders below the IntentStep when
  the user has any prior artefacts. Shows merged decks + briefings
  desc by created_at with sensitivity chip + exposure pill per row.
- "Re-score sensitivity" button hits the backfill endpoint —
  idempotent, useful when the scorer rules evolve.
- Click a deck row → opens the DeckStep view (loadDeck pattern).
- Briefings rows currently view-only in this strip — Wave 5 will
  add briefing deep-link.

### F · Marketing/landing redesign — design brief shipped
- Called `design_agent_full_stack` with the user's exact constraints:
  cream/oxblood preserved, executive navy `#0A1F44` accent spots
  added, audience = seasoned + emerging executives and NEDs, three
  pillars to lead with (Solve, Cross Board Pulse, Decks + Reports),
  punchy editorial copy.
- Output: `/app/design_guidelines.json` — section-by-section
  architecture, copy library, three-pillar visual system, navy
  placement strategy, component-level recommendations, mobile
  considerations, data-testid pattern.
- IMPLEMENTATION DEFERRED to iter65 (next user message) — this
  iteration covered backend/frontend Studio + rename only.

### Tests
- iter64: testing agent v3 — backend **14/14 pytest pass** (~1.8s,
  no LLM calls in scorer tests). Frontend **100% of assertions**:
  sidebar rename, /app/plays deep link still works, /app/prepare
  Catch-up header, /app/decks Studio header, studio-history strip,
  data-testid="studio-sensitivity-public" chip rendered, "Produce
  board-grade material with your own data" tagline.
- Pytest file: `/app/backend/tests/test_iter64_studio_sensitivity.py`.
- Report: `/app/test_reports/iteration_64.json`.

### Open / iter65 backlog
- **Marketing/landing implementation** (per the design_guidelines.json
  brief) — biggest remaining item; will materially lift conversion.
- Briefings deep-link from Studio history strip.
- Decks deep-link race condition (when navigating directly to
  /app/decks/:deckId, the [cid] effect's reset can race with the
  [cid, deepLinkDeckId] fetch — observed but not blocking).
- Workflows-as-journeys: when iter65's design-led IA settles, the
  home WorkflowsHub may migrate inside Studio as an "active workflows"
  rail.
- Sensitivity scorer accuracy could improve with an LLM tiebreaker
  pass for ambiguous text (today the rule list is intentionally
  deterministic and conservative).
- Add `/api/contexts/{cid}/studio/share` outbound email integration
  via existing Resend adapter so a share record actually emails the
  recipient with a tracked link.
- "Information exposure score" gating per plan tier — currently
  visible to everyone; landing-page copy claims it as an Enterprise
  feature so we should soft-gate the readers list (count visible
  free; full readers list locked behind plan check).



## §iter65 — Marketing landing redesign + live sensitivity demo + deep-link fixes (2026-04-29)

### A · Marketing/landing site redesign
- Per `/app/design_guidelines.json` (delivered by design_agent_full_stack
  in iter64). Cream/oxblood preserved; executive navy `#0A1F44`
  introduced as the third accent on conversion-driving CTAs.
- New components:
  - `HeroSection.jsx` — tightened value-promise that lands within the
    first viewport. "AKKI reads the pack so you can read the room."
    Subhead aimed at "executives and directors who grow and preserve
    shareholder value". Single dominant navy CTA: "Try AKKI in 60
    seconds" → /sandbox. Right-rail pull quote with navy attribution.
  - `ThreePillars.jsx` — bento grid: **Solve as the dominant card**
    (8/12 cols, dark, books photo) with the four phases and a
    "Start a Solve session" CTA. **Cross Board Pulse** sidebar (4/12,
    library photo) targeted at multi-board NEDs. **Decks + Reports
    preview row** (12/12) inviting a jump to the Enterprise band.
  - `EnterpriseFeature.jsx` — full-bleed navy band positioning the
    Decks + Reports Studio as the enterprise differentiator. Three
    bullets (auto-sensitivity, read-tracking, exposure score) + cream
    "Request a team workspace" CTA + outline "Security design" link.
    Hosts the LIVE SENSITIVITY DEMO.
- Removed long-winded sections per user feedback:
  - "Five surfaces / propositions" list — too verbose, replaced by
    Trust Strip (3 condensed guarantees).
  - Standalone "Closing call" section — folded into the final inline
    CTA block.
  - Dark "Assurance" block — folded into the Trust Strip.
  - Three-photo strip — one image now lives in Hero pull-quote rail.
- Editorial pull-quote rewritten: "Adopting tools that preserve value
  isn't operational — it is a fiduciary duty." Attribution chip uses
  Exco360 brand mark in navy.
- Audience cards (NED + Exec) condensed and tightened.
- Header masthead: Solve nav link routes to `#solve-pillar` anchor;
  "Request access" button uses navy.

### B · Live sensitivity demo on landing
- New public endpoint `POST /api/public/studio/sensitivity-demo` —
  no auth required. Accepts `{text: 4-4000 chars}`, returns the
  full sensitivity record `{score, classification, label, reasons[]}`
  plus `input_chars`. No DB write, no LLM call (regex scorer is
  microsecond-cost).
- Per-IP rate limit (1.5s window) using `X-Forwarded-For` first hop
  for k8s ingress-aware throttling (iter65 hardening from testing
  agent's RCA note). `request.client.host` fallback when XFF absent.
- Frontend `LiveSensitivityDemo` block inside EnterpriseFeature:
  textarea with `data-testid="enterprise-demo-input"`, "Use sample"
  button (`enterprise-demo-sample`), result panel
  (`enterprise-demo-result`) with classification chip, reasons list.
  Debounced 800ms after typing; immediate fire on sample. Shows
  "Slow down a moment…" on 429.
- Sample content: "Q3 board pack draft… framed customer-concentration
  story as macro-driven … £45m bolt-on acquisition." Scores
  Confidential · 50 with M&A / financial-figures / regulator triggers.

### C · Decks deep-link fix (cross-context)
- New endpoint `GET /api/decks/{deck_id}/context` — given just a
  deck_id, returns the context_id the deck belongs to (only if the
  caller has active membership). Powers cross-context deep-link
  resolution.
- `Decks.jsx` deep-link effect now fetches the deck under the active
  `cid` first; if the request fails (deck belongs to a different
  context), it calls `/decks/{id}/context` and `switchContext()` from
  AuthContext to pivot the user's active context. Subsequent re-render
  loads the deck cleanly.
- Race fix: when `deepLinkDeckId` is present, the [cid] effect skips
  resetting `view/outline/deck` so the deep-link can win the load
  race. Verified end-to-end: navigating to /app/decks/{id} from a
  fresh browser auto-switches context AND loads the DeckStep with
  sensitivity chip + exposure pill rendered.

### D · Briefings deep-link from Studio history
- Clicking a briefing row in StudioHistoryStrip now navigates to
  `/app/prepare#brief-{id}` (Catch-up surface). Brief routes lived
  there pre-iter64; the hash anchor lets that page scroll/select
  the specific briefing once iter66 wires the anchor handler.

### Tests
- iter65: testing agent v3 — backend **7/7 pytest pass** (~14s).
  Frontend **100% of assertions**: landing page + hero + pillars +
  enterprise + live demo (sample button + typed input both fire
  the API + render result), final CTA, trust strip, audience cards,
  /app/decks Studio regression, /app/prepare Catch-up regression,
  briefings deep-link navigation.
- Pytest file: `/app/backend/tests/test_iter65_landing_demo.py`.
- Report: `/app/test_reports/iteration_65.json`.
- Decks deep-link cross-context resolution verified manually after
  testing agent's run (the test account had no decks in active ctx).

### Open / iter66 backlog
- Catch-up page (`/app/prepare`) needs to handle the
  `#brief-{id}` hash anchor — scroll to and select the specific
  briefing. Today the navigation works but the briefing isn't
  highlighted on arrival.
- `Workflows`-as-journeys home widget could migrate inside Studio
  as an "active workflows" rail (deferred from iter64).
- Sensitivity scorer LLM tiebreaker for ambiguous text (today: pure
  regex, intentionally conservative — false-negatives on creative
  phrasings are the main miss).
- `/api/public/studio/sensitivity-demo` could be promoted to a
  fully-featured "Try the Studio" page with classification
  comparisons (Public vs Restricted side-by-side) and a "Save
  result as PDF" affordance.
- Plan-gated readers-list on engagement endpoint — currently
  readers[] visible to all members; gate full PII behind Enterprise
  plan with a count-only fallback for free.
- Exco360 Blog → Subscribe primary capture: the "Read the Exco360
  Blog" link should grow into a more conversion-shaped block once
  newsletter ESP is wired.



## §iter66/67 — Studio backlog clean-up: plan-gated readers, LLM tiebreaker, workflows rail, hash handler (2026-04-29)

### A · Plan-gated readers PII (Decks + Reports engagement)
- `/api/contexts/{cid}/studio/{kind}/{id}/engagement` now returns
  `plan` (free/pro/team) and `readers_locked` (boolean).
- For free accounts: `readers[] = []`, `readers_locked = true`,
  `unique_readers` count still populated (so users see the *number*
  of readers but not who).
- For Pro/Team accounts: `readers[]` carries the full PII (name,
  email, first_viewed_at, last_viewed_at, view_count). Same shape
  as before — Pro upgrade is invisible from the data side.
- Frontend DeckStep renders a `decks-readers-locked` block when
  `readers_locked && unique_readers > 0`: "X unique reader(s) so
  far · Upgrade to Pro to see who" with an oxblood "Upgrade to Pro"
  link to `/app/settings?tab=billing`.

### B · Sensitivity scorer LLM tiebreaker
- New `score_sensitivity_with_llm_tiebreaker(artefact, fallback_only=True)`
  in `studio_sensitivity.py`. Calls the regex scorer first; only
  escalates to a single STANDARD-tier LLM call when the regex result
  lands in the ambiguous "internal" band (25-49) AND the artefact
  text is ≥200 chars.
- LLM may bump to a HIGHER band (confidential/restricted) — never
  downgrades. Bumps are tagged with `llm_tiebreaker_used: true` and
  the reasons[] list gains an "LLM tiebreaker · <one-line>" entry.
- Endpoint: `POST /api/contexts/{cid}/studio/{kind}/{id}/rescore?use_llm=true`
  triggers the tiebreaker. Default (`use_llm=false`) keeps the
  cheap regex behavior. Verified on the live test deck — bumped
  from Internal (25) → Restricted (75) with NPL + control deficiency
  reasons.

### C · Workflows-as-journeys rail in Studio
- New `ActiveWorkflowsRail` component in Decks.jsx — renders above
  StudioHistoryStrip when the context has any active or paused
  Plays. Shows up to 4 tiles with play_type label, status chip
  (emerald=active / amber=paused), title + current step. Each tile
  click navigates to `/app/plays/{id}`.
- Pulls from existing `GET /api/contexts/{cid}/plays` endpoint; no
  new backend route. Fold-in keeps the legacy /app/plays page intact
  while surfacing in-progress journeys on the Studio surface where
  users actually produce material.

### D · Catch-up hash anchor handler (`#brief-{id}`)
- New useEffect in Prepare.jsx — when /app/prepare loads with a
  `#brief-{id}` hash, auto-switches to the Brief tab and opens the
  brief modal via `openBriefById`. Strips the hash via
  `history.replaceState` so reloads don't re-trigger.
- Iter66 first attempt had a TDZ (Temporal Dead Zone) ReferenceError
  because the hash effect referenced `openBriefById` before its
  `useCallback` declaration. Fixed in iter67 by reordering the
  declarations AND adding a `hashHandledRef` to prevent re-fire
  flakiness.
- Iter67 hardening: also listens for `hashchange` events on the
  window so client-side `<a href="#brief-x">` links work even when
  the user is already on /app/prepare.

### E · Briefings row → PDF export
- StudioHistoryStrip briefing-row click was originally routed to
  `/app/prepare#brief-{id}` but db.briefings (formal briefings) ≠
  db.briefs (orientation briefs that the Catch-up Brief tab shows).
- iter67 fix: briefing rows now open the briefing's PDF export
  directly in a new tab via authenticated blob fetch +
  `window.open(blob:url)`. Closes the loop on the Studio history
  strip so every artefact (deck OR briefing) lands in the right
  reader surface in one click.

### Tests
- iter66: 9/9 backend pytest GREEN; one frontend TDZ ReferenceError
  on hash route (FIXED).
- iter67: 15/15 backend pytest GREEN; 100% of frontend assertions
  GREEN: /app/prepare loads clean, invalid-hash no crash + stripped,
  valid-hash modal opens, briefing row opens blob PDF (verified on
  briefing 238b9d1e via window.open stub).
- Reports: `/app/test_reports/iteration_66.json` and
  `/app/test_reports/iteration_67.json`.

### Open / iter68 backlog
- Workflows-as-journeys rail tile testid migration to use
  `<Link>` instead of `window.location.assign` for SPA prefetch
  consistency (low-priority).
- Sensitivity scorer rule expansion as new content patterns surface.
- /try-studio standalone page (Public vs Restricted side-by-side
  comparisons + "Save result as PDF" affordance for the live demo).
- Exco360 newsletter ESP wiring + a real subscribe block.
- A/B test the navy primary CTA against oxblood — 2-week click-through
  count to settle which lands more conversions.


## §iter68 — Share with the Chair + Progress audit (2026-04-30)

### A · Share with the Chair (closes the Studio distribution loop)
- New backend endpoint `POST /api/contexts/{cid}/studio/{kind}/{aid}/share-email`
  (auth): records a `studio_shares` row with `external=true`, mints a
  JWT-signed tracking token (14-day TTL, algorithm HS256, purpose
  `studio_share`), and emails via Resend using a new editorial template
  (`_render_share_artefact_email_html`) that carries the sensitivity
  label chip and a cream/oxblood palette consistent with the checklist
  email.
- Public click tracker: `GET /api/public/studio/track/{token}` (no auth).
  Decodes the token, records a `studio_views` row keyed on a synthetic
  `account_id = external:<sha256(email)>` so repeat opens dedupe per
  recipient, marks `first_opened_at` / `last_opened_at` on the share
  record, and 302-redirects to the in-app deep link
  (`/app/decks/{id}` or `/app/prepare#brief-{id}`).
- Net effect: **external readers feed straight into the exposure score**.
  Smoke-tested live on Tuli NED briefing `238b9d1e`: share email sent
  via Resend (`mode=sent`), then a crafted token-click bumped
  `unique_readers` 0 → 1 and `exposure.score` 0 → 52 with
  `band=moderate`.
- Frontend:
  - New `components/studio/ShareArtefactModal.jsx` — recipient
    name/email/note fields, editorial register, success state with
    send-another affordance.
  - `DeckStep` header gets a `deck-share-btn` next to the Sensitivity
    + Exposure chips; opens the modal with `onShared` → refresh
    engagement.
  - `StudioHistoryStrip` rows get a `studio-history-share-{kind}-{id}`
    button (stopPropagation so it doesn't fire the row open); shared
    modal state at strip level.
- Cookie-sensitive endpoints are untouched — the tracker is cookie-less
  on purpose (non-AKKI recipients don't need an account to record a
  read).

### B · Progress audit + journey guide
- New doc: `/app/AUDIT_iter68.md` — honest walk through:
  11 experience rules (10 holding, 1 drift — validator not fanned out
  to decks/reports/solve), BRD v4.0 module coverage (14/18 live, 4
  deferred per Path A), canonical journeys (Sandbox→Signup→Solve→Studio
  and NED→Catch-up→Solve→Handoff→Share), and the P1/P2/P3 priority list
  for iter69.

### Open / iter69 backlog (P1 — real loops to close)
- Real Stripe → `solve_pro` state flip via the existing webhook.
- Real validator (Gemini 2.5 Flash) fan-out to decks, reports, Solve
  syntheses (briefs already covered from iter49).
- Cross-Board Pulse as a dedicated surface OR soften landing copy.
- Public read-only artefact view for non-AKKI share recipients
  (introduced as friction by iter68's Share with the Chair feature).

### Open / iter69 backlog (P2 — cosmetic)
- Rename "Briefings" → "Reports" in Studio history strip (avoid the
  briefs vs briefings collection collision).
- Collapse `/app/plays` into Studio's ActiveWorkflowsRail (today: 3
  entry points for the same thing).
- Promote sensitivity LLM tiebreaker to default-on (today: opt-in).



## §iter69 — Public read-only share viewer (closes iter68's friction loop) (2026-04-30)

### Why
Iter68 shipped "Share with the Chair" — the share email sends a tracked
link, and when the recipient clicks, their view bumps the artefact's
exposure score. But the redirect target was `/app/decks/:id` or
`/app/prepare#brief-:id`, which bounced non-AKKI directors (most
external recipients) straight into `/signin`. The iter68 audit flagged
this as the highest-impact friction to close.

### What shipped
- **Public read-only viewer page** (`/shared/:token`, new
  `pages/SharedArtefact.jsx`). Editorial cream/oxblood chrome (AKKI
  logo + "Shared with you · Synisense-shielded" in the topbar). Renders
  the artefact (deck slides OR briefing opening + items) as read-only
  with the sensitivity chip inline. Footer: "Your read has been
  recorded" + contextual CTA (authed: `Open in AKKI →`; anonymous:
  `Try AKKI in 60 seconds →` to `/sandbox`).
- **New backend endpoint** `GET /api/public/studio/read/{token}` (no
  auth). Decodes the share token, records an idempotent per-day view
  row under `account_id = external:<sha256(email)>`, marks the share
  record as opened, and returns public-safe content (title, slides
  for decks; title + opening_paragraph + items for briefings — we
  deliberately drop audience, missing_context, internal production
  metadata).
- **Legacy track endpoint updated**: `GET /api/public/studio/track/{token}`
  still 302-redirects, but now always to `/shared/:token` instead of
  the app deep links. Back-compat preserved for any shares sent during
  iter68.
- **Email template URL swapped** to `{FRONTEND_URL}/shared/{token}` so
  new shares land directly on the public viewer.

### Error states
- Expired token → 410 ("This share link has expired.")
- Invalid token → 400 ("Invalid share link.")
- Deleted artefact → 404 ("This document is no longer available.")
- All three surface as an editorial `<ErrorPanel>` on the viewer with
  a "reply to sender" nudge.

### Tests
- iter69: `tests/test_iter68_share_chair.py` — **8/8 GREEN** (end-to-end
  share-email + public-track redirect + public-read happy path + 410
  expired + 400 invalid + 404 missing + unique_readers increment with
  same-day dedupe).
- iter64/66/67 regression: **29/29 GREEN**, zero regressions.
- Frontend: programmatic smoke pass in Playwright confirmed title,
  "Restricted" sensitivity chip, 6 briefing items, footer, and the
  non-authed "Try AKKI" CTA all render on `/shared/:token` with a valid
  token.

### Files touched
- `/app/backend/routers/studio.py` — new `/api/public/studio/read/{token}`,
  track endpoint redirect updated, email template URL swapped.
- `/app/frontend/src/pages/SharedArtefact.jsx` — new file.
- `/app/frontend/src/App.js` — route `/shared/:token` registered (public).
- `/app/backend/tests/test_iter68_share_chair.py` — 8 regression cases.

### Still-open P1 (carry forward to iter70)
- Real Stripe → `solve_pro` state flip via the existing webhook.
- Real validator (Gemini 2.5 Flash) fan-out to decks, reports, Solve
  syntheses (briefs already covered from iter49).
- Cross-Board Pulse as a dedicated surface OR soften landing copy.

## §iter70 — Trust-tiered inbound email triage (2026-04-30)

### Why
Iter51 shipped Postmark inbound: a user gets a unique
`inbound+<token>.<ctx>@inbound.akki.ai` address; any email forwarded
there gets extracted and filed. But the pipeline ingested **anything**
that reached the mailbox — owner, reportee, or random spammer — with
no trust differentiation. Three journeys asked by the user:
  1. owner forwards → auto-ingest (was live)
  2. known reportee CCs → auto-ingest (worked mechanically, no trust stamp)
  3. unknown sender → queue for review (NOT built)

### What shipped
**Sender-tier classifier** in `routers/inbound_email.py` — exact email
match only (user direction 1a):
- `_classify_sender_tier(from_email, account, context)` → returns one
  of `owner`, `reportee` (with full reportee record), or `unknown`.
- **Tier A (owner)** → auto-ingest as before, now stamped with
  `inbound_trust_tier='owner'`.
- **Tier B (reportee)** → auto-ingest with `inbound_trust_tier='reportee'`,
  `inbound_reportee_id`, `inbound_reportee_name`, `inbound_reportee_title`.
- **Tier C (unknown)** → payload quarantined into new
  `db.inbound_queue` collection with `status='pending_review'`. Raw
  payload (base64 attachment + bodies) stored separately in
  `db.inbound_queue_raw` so list queries stay light.

**New router** `routers/inbound_queue.py`:
- `GET /api/contexts/{cid}/inbound-queue?status=all|pending_review|accepted|rejected`
- `GET /api/me/inbound-queue/counts` — aggregated across every workspace
  the caller is a member of. Powers the Home card.
- `GET /api/contexts/{cid}/inbound-queue/{qid}` — detail + decoded body
  preview + virus-scanned attachment-extract preview.
- `POST /api/contexts/{cid}/inbound-queue/{qid}/accept` — virus-scans,
  extracts, writes to storage, inserts a `documents` row with
  `inbound_trust_tier='unknown_promoted'` + `inbound_queue_id` pointing
  back to the queue row for full audit chain. Marks queue row as
  `accepted`. 409 on double-accept.
- `POST /api/contexts/{cid}/inbound-queue/{qid}/reject` — archives
  queue row with `reject_reason`. **No email sent to sender** per user
  direction 3c. 409 on double-reject.

**Frontend**:
- `pages/InboundQueue.jsx` — editorial review surface (cream/oxblood).
  Workspace switcher auto-selects the busiest pending workspace on
  first load (iter70 UX polish after the testing agent flagged this
  — landing on an empty workspace when another has pending items
  was friction). Detail modal → Accept (with note) or Reject (with
  reason) dialogs. All rows, modals, and confirm buttons carry
  data-testids.
- `components/home/InboundQueueCard.jsx` — Home card with both
  populated state (by-context breakdown + "Review" CTA) and quiet
  empty state ("Emails from you and your reportees file themselves…").
- `WorkflowsHub.jsx` — new `Inbound review` tab with count pill;
  defaults to this tab when `inboundCount > 0`.

**Document sanitisation**: `routers/documents.py::sanitize_doc` now
includes `source`, `inbound_from_email/name`, `inbound_subject`,
`inbound_trust_tier`, `inbound_reportee_*`, `inbound_queue_id`,
`inbound_promoted_*` fields so the frontend document viewer can
render the trust chain.

### Tests
- **15/15 backend pytest GREEN** (baseline 6 + 9 edge cases written
  by the testing agent). Covers all three tiers, accept/reject/double-
  accept/double-reject, idempotent replays, empty body + attachment-
  only ingests, multi-attachment summaries, count-shape validation.
- **52/52 regression GREEN** — iter64 through iter70 all pass together.
- **Frontend** — 100% green via `testing_agent_v3_fork/iter68.json`
  after a null-guard bug fix the testing agent authored directly
  (Dialog children rendered even when `open={false}`; detail
  comparisons now guard with `detail && detail.status !==` not
  `detail?.status !==`).

### Non-trivial behaviours (read before changing)
- External-reader dedup on Share-with-Chair (iter68) and queue-item
  dedup on Tier-C inbound both use synthetic IDs derived from the
  sender email. Replaying a Postmark MessageID does NOT create a
  second queue row — we dedupe on both `(context_id, message_id)`
  against documents AND against inbound_queue.
- Reject intentionally sends NO reply (user direction 3c). Ops audit
  log captures the decision instead. If we later want sender
  notifications, they should be opt-in per-workspace, not per-decision.
- Tier-B (reportee) matching is exact email only. If a reportee emails
  from a slightly different alias (e.g. `s.kamau@` vs `sarah.kamau@`),
  they fall to Tier C. The testing agent recommended considering
  domain-match fallback as a follow-up; we deferred that decision.

### Files touched
- `/app/backend/routers/inbound_email.py` — classifier + Tier-C branch
- `/app/backend/routers/inbound_queue.py` — new file
- `/app/backend/routers/documents.py` — sanitize_doc extended
- `/app/backend/server.py` — router include + 4 new indexes
- `/app/frontend/src/pages/InboundQueue.jsx` — new file
- `/app/frontend/src/components/home/InboundQueueCard.jsx` — new file
- `/app/frontend/src/components/home/WorkflowsHub.jsx` — Inbound tab
- `/app/frontend/src/App.js` — route registered
- `/app/backend/tests/test_iter70_inbound_triage.py` — 6 cases (main agent)
- `/app/backend/tests/test_iter70_inbound_edge.py` — 9 cases (testing agent)

### Still-open (carried forward from iter68/69 audit)
- Real Stripe → `solve_pro` webhook state flip
- Real validator (Gemini 2.5 Flash) fan-out to decks, reports, Solve
- Cross-Board Pulse as dedicated surface OR soften landing copy


---

## Sprint PRE / Website v7 — closure (2026-05-12)

Full rebuild of the public marketing surface to **Website Brief v7.0**. Bronze
removed; canonical 7-token palette is now the website's only design system.

- **Visual system**: parchment / parchment-light / ink / graphite / graphite-light /
  oxblood / oxblood-deep. Source Serif 4 + Inter + JetBrains Mono with credible
  fallbacks. Single-word oxblood italic lift per hero h1 (every page).
- **18 pages built/rewritten** at top-level routes (`/solva`, `/akki-chat`,
  `/work-studio`, `/cycle-manager`, `/monitor`, `/pulse`, `/document-journal`
  reinstated; `/pricing` reinstated; `/for-exco` retained).
- **Home**: 10-section v7 hierarchy — Hero / Evidence Strip / Tier 1 Safety /
  Tier 2 Workspace (no product names) / Tier 3 Inventions (Solva, Synisense,
  Agent Cycle) / Three Audiences + triptych / Cohort teaser / Inverted CTA.
- **5 images** at <120 KB each, anonymised graphite duotone editorial portraits.
- **Smoke**: 24/24 routes return 200 with valid v7 hero + Plausible + canonical.
- **Backend regression**: 29/29 trust-critical tests passing.
- **Perf**: LCP 404 ms, CLS 0, FCP 132 ms, TTI 489 ms (container-headless).
  Bundle weight 2.5 MB shared with /app SPA — marketing-chunk split is next sprint.
- **SEO**: sitemap.xml (24 URLs), robots.txt, OG/Twitter cards, per-page canonical
  to akki.syni.ai.
- **Plausible analytics** wired with `data-domain="akki.syni.ai"`.

### Out of scope (next sprints)
- App `index.css` v7 palette migration (kept aliased — `--navy → var(--ink)`,
  `--chrome → var(--ink)`, `--cream → var(--cream)` etc.)
- Marketing-route code-splitting (to hit <500 KB landing budget)
- Self-hosted woff2 for Source Serif 4 / Inter / JetBrains Mono
- `/about` named team portraits (G6 requires real photography)
- Cohort + Organisation application form workstreams

### Files
- New: `frontend/src/website/style.css`, `WebsiteShell.jsx`, `WebsiteNav.jsx`,
  `WebsiteFooter.jsx`, `copy/index.js`, `components/PagePrimitives.jsx`,
  18 page files in `pages/` and `pages/product/`, 5 `assets/v7/*.webp`,
  `public/{robots.txt,sitemap.xml}`.
- Removed: `pages/ProductHub.jsx`, `components/EvidencePanel.jsx`.
- Modified palette only: `frontend/src/sandbox/style.css`.
- Closure: `/app/docs/sprints/PRE_v7_website.md`.

---

## Sprint HOME — closure (2026-05-12)

Post-sign-in Home surface upgrade: full v7 palette migration into `index.css`,
ExCo as a grouping function (NEW), Portfolio state indicators, role calibration
on the top-nav.

- **App `index.css` v7 migration**: 7-token palette canonical, legacy
  `--paper/--cream/--accent/--severity/--navy/--chrome` preserved as aliases →
  `var(--<v7-token>)`. Source Serif 4 + Inter + JetBrains Mono via `@font-face
  local()`. Calibri removed.
- **ExCo (new collection)**: `db.exco_teams` per-context grouping with 7
  endpoints (`POST/GET/PATCH/DELETE /api/contexts/{cid}/exco-teams`,
  member add/remove, archive). Owner/admin gating, audit rows on every
  mutation, soft-delete only. `ExcoTeamsCard` on HomeExecutive + HomeDual.
- **`GET /api/me/portfolio`**: per-membership cycle / goals-at-risk /
  pending-followups / unread-signals / last-active state with 30-second
  in-memory cache. Portfolio cards render state badges (oxblood for attention,
  graphite-light for quiet).
- **Role kicker on top-nav**: derives `Executive` / `Non-Executive Director`
  / `Executive · NED` / appends `· ExCo` when the account is in any ExCo team
  in the active context.
- **Tests**: 35/35 passing (29 trust-critical + 6 new `test_exco_teams.py`).

### Files
- New: `backend/routers/{exco_teams,portfolio}.py`, `backend/tests/test_exco_teams.py`, `frontend/src/components/home/ExcoTeamsCard.jsx`.
- Modified: `backend/server.py`, `frontend/src/index.css`, `frontend/public/index.html`, `pages/home/{HomeExecutive,HomeDual}.jsx`, `pages/ContextPortfolio.jsx`, `components/layout/CycleContextIndicator.jsx`.
- Closure: `/app/docs/sprints/HOME.md`.

### Deferred
- Self-hosted woff2 files in `public/fonts/` (chains ready, files awaited)
- Module-surface palette refinement (separate sprint per module)
- Cross-board "dual" auto-detection (still relies on `account.declared_role`)

---

## Sprint CHAT — closure (2026-05-12)

Trust-First Chat refinement: light v7 palette pass on chat surfaces,
inline per-message Synisense badge, provider transparency line, Trust
Panel cross-link from AuditDialog, K5 streaming transition on first
chat open.

- **v7 palette light pass**: `MarkdownMessage.css` + `ModelAvatar.jsx`
  migrated off legacy hex literals (`--accent: #8b1d2c`, `--gold: #C9A961`)
  to canonical v7 tokens (`--oxblood`, `--graphite`). `Chat.jsx` resolves
  through HOME-sprint alias chains.
- **Batched per-message Synisense**: new `POST /api/chats/{cid}/messages/synisense-runs/batch`
  endpoint replaces the N+1 pattern. `useMessagesSynisense` hook + 30s
  polling + invalidation on chat change. `PerMessageSynisenseBadge`
  renders inline next to model label, mono 10px oxblood, hover tooltip
  with three-layer breakdown.
- **Provider transparency**: `ProviderLine` reads `provider_used` +
  `fallback_triggered` from the message record; italic when fallback,
  hover tooltip resolves the chain (e.g., "Direct Anthropic SDK →
  Emergent universal proxy").
- **Trust Panel cross-link**: tertiary v7 button at bottom of
  AuditDialog dispatches global `akki:open-trust-panel` event;
  AppShell listens and opens the panel without prop-drilling.
- **Streaming transition**: Chat wrapped in `WorkspaceEntryGate` so
  first navigation TO `/app/chat` per session shows the editorial scene
  (4-5s, prefers-reduced-motion respected).
- **Tests**: 35/35 passing — no regressions.

### Files
- New: `frontend/src/hooks/useMessagesSynisense.js`, `frontend/src/components/chat/{PerMessageSynisenseBadge,ProviderLine}.jsx`.
- Modified: `backend/routers/synisense_metrics.py` (+batch endpoint), `frontend/src/pages/Chat.jsx`, `frontend/src/components/chat/{MarkdownMessage.css,ModelAvatar.jsx}`, `frontend/src/components/layout/AppShell.jsx` (event listener).
- Closure: `/app/docs/sprints/CHAT.md`.

### Out of scope (deferred)
- Editorial chat redesign (letter format, no bubbles)
- Export redaction record PDF (move to TRUST sprint)
- Hash chain changes (frozen)
- Module-specific tests for batch endpoint (covered by shared aggregation pipeline)

---

## Sprint SOLVA — closure (2026-05-12)

Editorial pass on Solva surfaces: v7 palette/typography sweep, per-section
Synisense badge with audit storyline, export template v7 migration with
preserved byte-determinism, `placeholder_stub` deletion, v2→v3 UI brand
sweep (code namespace preserved).

- **v7 palette sweep**: `tokens.js` migrated to v7 `var(--*)` references;
  5 component files patched (69 hex literals → 0). Banned-vocab clean.
- **Per-section Synisense breakdown**: new endpoint `GET /api/solva/v2/sessions/{sid}/synisense-breakdown`
  + `session_id` threaded through pipeline. `PerSectionSynisenseBadge.jsx`
  + audit storyline at top of `SolvaArtefact.jsx`. Legacy sessions fall
  back to surface + time-window query.
- **Export templates**: HTML (WeasyPrint) palette → v7; DOCX colors → oxblood;
  font runs preserved (determinism). DOCX + PDF rebuild produces identical
  SHA-256 across runs.
- **placeholder_stub deleted** from `SHIELD_BYPASS_REASONS` (zero live callers).
- **v2→v3 UI brand sweep**: zero UI-visible "Solva v2" matches; CODE
  namespace + DB collections + audit-chain surfaces untouched.
- **Tests**: 35/35 trust-critical preserved; 112/132 Solva v2 (20 failures
  pre-date this sprint, confirmed via `git stash` retest).

### Files
- New: `frontend/src/components/solva/artefact/PerSectionSynisenseBadge.jsx`.
- Modified: `frontend/src/components/solva/flow/tokens.js`, 5 Solva surface files,
  `backend/routers/solva_v2.py` (+endpoint), `backend/services/synisense/pipeline.py`,
  `backend/services/solva_v2/llm_adapter.py`, `backend/solva_artefact_export.py`,
  `backend/templates/solva_*.html`.
- Closure: `/app/docs/sprints/SOLVA.md`.

### Deferred
- DOCX font runs (Source Serif 4 / Inter) — pending hash-chain version bump
- Solva ExCo association (Q2(c))
- Export-redaction-record cross-link from Solva artefact (S-27 → TRUST sprint)
- Pre-existing Solva v2 test failures (schema drift in synthesis cluster path)

---

## Sprint STUDIO — closure (2026-05-12)

Work Studio editorial pass + per-artefact audit visibility + export
template v7 + CI determinism.

- **v7 palette sweep**: 67 hex literals → 0 across `pages/WorkStudio.jsx`,
  `pages/StudioComposerPage.jsx`, `pages/Decks.jsx`, `components/studio/`.
  Banned-vocab clean.
- **Per-artefact Synisense breakdown**: new endpoint
  `GET /api/work_studio/artefacts/{kind}/{id}/synisense-breakdown`.
  `artefact_id` threaded through `synisense/pipeline.py`. Frontend
  `PerArtefactSynisenseBadge.jsx` renders inline at the top of the
  artefact drawer with audit storyline.
- **Export-footer stamp**: `Brief.audit_summary` optional field; when
  set, DOCX + PDF render an italic mono footer line and PPTX appends a
  dedicated `AUDIT` slide. None by default — preserves byte-determinism
  for legacy callers.
- **Export template v7**: DOCX + PPTX + PDF palette migrated to v7
  oxblood/ink/graphite. Font runs preserved (Georgia/Calibri) to
  maintain hash-stamped reproducibility.
- **CI determinism test**: new `backend/tests/test_render_determinism.py`
  with 6 tests — DOCX, PPTX, PDF deterministic across two renders;
  report kind shares pipeline; audit-summary variant deterministic;
  citation-index W-23 regression.
- **W-22 (failure persistence)**: `llm_pass1` + `llm_pass2` (+ raw text
  heads) now persisted on every failure row via `partial` capture
  attached to the exception.
- **W-23 (citation validator)**: phantom citation indices now dropped
  silently with a WARNING log row — no longer fails the whole render.

### Files
- New: `backend/tests/test_render_determinism.py`,
  `frontend/src/components/studio/PerArtefactSynisenseBadge.jsx`.
- Modified: `backend/services/{synisense/pipeline.py,work_studio_export.py}`,
  `backend/routers/work_studio_export.py`, `backend/work_studio/{brief,docx_generator,pptx_generator,pdf_generator}.py`,
  `frontend/src/pages/{WorkStudio,StudioComposerPage,Decks}.jsx`,
  `frontend/src/components/studio/*.jsx`.
- Closure: `/app/docs/sprints/STUDIO.md`.

### Deferred
- Auto-compose `audit_summary` from synisense_runs at export time
- ExCo association on Studio artefacts (Q4(b) → CYCLE sprint)
- Deck PDF renderer (`render_deck_pdf` NotImplementedError)

---

## CYCLE sprint — Assignment Handoff (2026-02)

**Brief:** `/app/memory/sprints/CYCLE_MANAGER_BRIEF.md` (APPROVED-FOR-BUILD).
**Verify doc:** `/app/memory/sprints/CYCLE_MANAGER_VERIFY.md`.
**Architectural lock:** C3 resolved → ASSIGNMENT HANDOFF (not push, not pull).

### What shipped

- **`services/cycle_permissions.py`** — `can_submit_for_board(account, context, membership)` and `permission_reason(...)`. Owner only for individual workspaces; owner + admin + chief_of_staff + ExCo team members for team workspaces; NED contexts never permitted.
- **`routers/cycle_assignments.py`** — 7 new endpoints under `/api`:
  - `POST .../briefs/{bid}/submit-for-board` (draft → submitted)
  - `POST .../briefs/{bid}/assignments` (fan-out, ned_ids XOR cohort_id)
  - `GET .../briefs/{bid}/assignments` (creator-side list)
  - `DELETE .../cycle-assignments/{aid}` (cancel pending)
  - `GET /api/ned/inbox/assignments` (NED inbox; strict whitelist)
  - `POST /api/ned/assignments/{aid}/accept` (privacy-wall ingest; idempotent; flips brief → shipped)
  - `POST /api/ned/assignments/{aid}/decline` (no ingest)
  - `GET /api/me/submitted-briefs` (submitter rollup view)
- **`routers/ned/__init__.py`** — marker module documenting that PRODUCT_SPEC §5.6 ("NED has zero code") is out of date; keep-code decision recorded.
- **`email_service.notify_ned_assignment_stub`** — MOCKED IN DEV. Resend is in test mode in the preview env; the call site is wired so production can flip without code change.
- **New collections + indexes:** `db.cycle_assignments` (unique partial index on `(brief_id, ned_id)` where status ∈ {pending, accepted, declined}; secondary indexes by NED + by context+cycle + by submitter), `db.ned_packs` (unique by `assignment_id`), plus a `work_studio_briefs.{submitter_account_id, board_status, submitted_at}` secondary index for the rollup view.
- **Frontend — new:**
  - `pages/ned/NedInbox.jsx` (`/app/ned/inbox`) — tabs Pending / Accepted / Declined, accept/decline dialogs, streaming reveal first visit.
  - `components/cycle/CycleStatusBadge.jsx` — v7 status badge (draft/submitted/shipped + pending/accepted/declined/cancelled).
  - `components/cycle/BoardSubmitPanel.jsx` — ship-step UX, submit + assign + cancel + roster.
  - `components/cycle/NedInboxTile.jsx` — HomeNed indicator with pending count.
- **Frontend — edited:**
  - `pages/Cycle.jsx` — 4 hex literals removed; `BoardSubmitPanel` wired into Compilation step.
  - `pages/ned/NedMeeting.jsx` — 2 hex literals removed.
  - `pages/home/HomeNed.jsx` — `NedInboxTile` mounted.
  - `components/transitions/WorkspaceEntryScene.jsx` — `ned_inbox` workspace lines.
  - `App.js` — `/app/ned/inbox` route.
  - `routers/cycle_manager.py` — compile response now surfaces `cycle_id`, `agenda_id`, `board_status` for the ship-step UI.

### Privacy-wall enforcement

`tests/test_cycle_assignment_privacy_wall.py` (3 tests, all green):

1. Strict-whitelist enforcement on NED inbox even with deliberately polluted source rows.
2. `ned_packs` row schema locked to 7 keys; sentinel scan over every value.
3. Defensive guard — accept path is monkey-patched to fail loudly if it reads `cycle_agendas` / `cycle_contributions` / `cycle_team` / `cycle_followups`.

### Acceptance — automated

`pytest tests/test_privacy_wall.py tests/test_phase_g_privacy_wall_sentinel.py tests/test_privacy_wall_phase_2c.py tests/test_universal_search.py tests/test_exco_teams.py tests/test_render_determinism.py tests/test_cycle_assignment_handoff.py tests/test_cycle_assignment_privacy_wall.py -q`

→ **66 passed** (41 baseline + 25 new).

### Acceptance — manual

See `/app/memory/sprints/CYCLE_MANAGER_VERIFY.md` for the §D + §E walkthroughs.

### Hex-literal sweep

`grep -rE '#[0-9a-fA-F]{3,8}\b' pages/Cycle.jsx pages/CycleSettings.jsx pages/ned/ components/cycle/ | grep -v 'color:var'` → **0 hits**.

### Deferred (Should-have, not done)

- Should-have S1 audit log entries beyond submit/assign/accept/decline (those four are wired).
- Could-have items 1–3 (reminder pings, cohort builder UI, CSV export) not started.

### Files index

See `CYCLE_MANAGER_VERIFY.md` §"Files touched in this sprint".
