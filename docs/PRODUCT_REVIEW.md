# AKKI · Product Features & Functionality Review

_A documentation snapshot of the codebase at `/app` (GitHub: `bramuel-syni/Akki-Executive`, branch `main`). Read-only. No code was changed to produce this review._

---

## Executive Summary

AKKI is an editorial workspace for board-grade work. It is built for two readers: the operating executive (CEO, CFO, CHRO, CTO, COO) and the non-executive director (Chair, NED, observer). The promise on the landing page is exact: _"AKKI reads the pack so you can read the room."_

The product is a single full-stack application — a React 19 frontend backed by a FastAPI + MongoDB monolith — that has been built incrementally across roughly 70 internal iterations and seven UX advisory phases. The most recent shipped phase is the **Governance (Trust) panel** (Advisory 7, v1.7). The active phase is **Studio Composition** (Advisory 9): a backend block composer sits at `/app/backend/routers/studio_blocks.py` (528 lines) but it is **not wired into `server.py`**, and there is no frontend `BlockComposer.jsx`. Phase 8 is therefore code-resident but not user-reachable.

What is genuinely shipped and used:

- A nine-modality information architecture (Home, Reading, Chat, Daily Review, First Session, Cycle, Governance, Depth, Studio).
- Real LLM grounding through the Emergent Universal Key, with a real second-model validator (Gemini 2.5 Flash) on briefings only.
- A real distribution loop on Studio: deck/report/briefing → tracked share email via Resend → re-open by external recipient → exposure score updates.
- A real inbound-email pipeline through Postmark with per-account and per-context mailboxes and a queue triage surface.
- A deterministic, regex-based sensitivity classifier that runs on every saved Studio artefact and surfaces a `PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED` chip.

What is mocked, stubbed or partial:

- Virus scanning on every uploaded document (`virus_scan_stub` in `documents_service.py`).
- Live Synisense de-identification (regex-only today; live URL swap waiting).
- Stripe billing on the Solve Pro tier (test-mode key; webhook receives but the plan flip on solve-pro entitlement is incomplete).
- Independent-validator coverage on Decks, Reports and Solve syntheses (badge present, second LLM call absent — only Briefings carry a real validator pass).
- Public read-only Chair view for non-AKKI recipients of shared artefacts — endpoint exists for tracked redirect but landing on `/app/decks/:id` bounces an unauthenticated visitor to `/signin`.

The product's centre of gravity is **trust**: every consequential answer cites a source, every artefact carries a sensitivity score, every read is logged, every LLM call passes through a shielding layer. The biggest near-term gap is composition: the Studio's editing surface is still a flat-text editor.

---

## Product Positioning

AKKI is positioned in the gap between Friday and Tuesday. A pack lands on a director's desk on a Friday. The committee meets on a Tuesday. Today, that gap is filled by the executive reading the pack alone, taking notes alone, and walking into the room with conviction that depends on how much sleep they got. AKKI is the colleague who reads with them: a workspace that ingests the pack, surfaces what changed, drafts the brief, fact-checks the brief against an independent model, and tracks who else read what before the meeting.

Three editorial commitments shape every surface:

1. **Editorial, not transactional.** Cream background, oxblood and navy accents, Georgia serif for headlines, Inter for chrome, JetBrains for metadata. No SaaS gradients, no progress bars, no streaks, no badges, no emojis in copy. The voice is the FT leader column.
2. **AKKI as the third party.** Outbound emails are addressed _from_ AKKI _on behalf of_ the principal; replies go to the principal, never to AKKI. The tool is the colleague, not the sender.
3. **Trust-first chrome.** A "Shielded" chip in the top bar, a Trust panel reachable from anywhere in the user menu, source citations on every grounded answer, a cryptographically-chained audit pack on chat exports.

The buyer is abstracted to a single archetype on the homepage — _operating executives and non-executive directors at listed and pre-IPO companies_ — and only role-shaped where telemetry justifies it.

---

## Personas & Roles

| Persona | Where they live in the product | What they want |
|---|---|---|
| **Seasoned NED / Chair** | Multi-context portfolio (`/app/contexts`); Catch-up briefs (`/app/prepare`); Cross-board Home river (`/app`) | One screen showing what changed across every board they sit on, before Tuesday |
| **Executive (CEO / CFO / CHRO)** | Single primary context; Cycle strip; Studio for board-pack production; Solve for one-pause diagnostics | Get the cycle done without losing the thread; a defensible report; a place to think |
| **Sandbox visitor** | `/sandbox` → `/sandbox/generating/:id` → `/app?tutorial=1` (HomeExecutive). Drop-a-real-pack uploads land on `/app/quick-results/:cid/:docId` post-extraction. | A 60-second proof that AKKI handles _their_ sector, then a focused conversion moment if they upload their own document |
| **External recipient (Chair / SID)** | Receives a tracked share email; lands on `/app/decks/:id` or `/app/prepare#brief-:id` | Read the artefact; their open is recorded |
| **Superadmin / operator** | `/admin/*`: health, sandbox KPI, signal KPI, LLM spend, auth events, blog admin | Operational visibility; cost; abuse signals |

`declared_role` on the account is one of `executive`, `ned`, `dual`, `undeclared`. Membership `role` per context is independent (`executive`, `ned`) and may differ from the account's declared role. Sub-roles are `admin` or `member`.

---

## Feature Reviews

Each section below covers a canonical feature. Routes refer to the running app; file paths are absolute under `/app`.

### 1. AKKI Solve — four-phase structured pause

- **What it is.** A guided diagnostic for one nagging board-grade problem, run as a four-phase state machine: Surface → Depth → Synthesis → Lock-in.
- **User value.** The NED or executive sitting with one ticking concern ("our top-3 credit concentration keeps creeping") gets a structured 25-minute pause, three anonymised comparables, and three handoff artefacts (brief, deck outline, cycle questions) ready to dispatch. Replaces the back-of-envelope.
- **How it works today.** Backend `routers/solva_engine.py` (renamed from `solve_engine.py` in Phase 13.1) exposes `POST /api/solva/sessions`, `.../turn`, `.../restart`, `.../abandon`, `.../handoff/{brief|decks|cycle}`, `.../export.pdf`. Legacy `/api/solve/*` URLs return HTTP 308 to the canonical Solva path (preserves method + body). Mongo collections retain the `solve_` prefix for historical stability: `solve_sessions`, `solve_clusters` (taxonomy seeded from `solve_clusters_seed.py`), `solve_comparables` (27 curated diagnoses keyed on cluster + sector tag), `solve_handoffs`, `solve_free_grants` (one row per (account, month) for the free-tier monthly deep-synthesis grant). LLM calls go through the deep tier (Claude Opus by default, configurable via `LLM_MODEL_DEEP`). Frontend at `/app/solva` (`pages/AppSolva.jsx`) and the marketing landing `/solva` (`pages/SolvaLanding.jsx`); legacy `/app/solve` and `/solve` are `<Navigate replace />` aliases.
- **State.** Shipped.
- **Gaps / risks.** Stripe → Solve Pro entitlement flip is incomplete (per `AUDIT_iter68.md`, P1). Validator badge appears on Synthesis but no real second-model pass runs there; only Briefings get a real validator call. PDF export is real (`solve_pdf.py`) but is not signed or hash-chained.
- **Open decisions.** —

### 2. Daily Review — batched approval queue

- **What it is.** A single keyboard-first surface at `/app/review` where the user approves, edits or rejects everything that needs human sign-off in one sitting. The load-bearing modality.
- **User value.** Removes inline approval toasts from the rest of the product. The user does not get pinged in Workspace or Chat asking "approve this draft?" — every draft surfaces here. Phase A (live) covers inbound docs awaiting file-attach plus briefings awaiting review. Phase B (deferred) is drafted emails and extracted cycle questions.
- **How it works today.** Backend `routers/daily_review.py` exposes `GET /api/me/review-queue`, `.../counts`, and `POST .../items/{kind}/{item_id}/{approve|reject|edit}`. Frontend `pages/DailyReview.jsx`, components `review/ReviewItemCard.jsx`, `review/ReviewQueueStrip.jsx`, badge `layout/ReviewBadge.jsx` polls counts every 60 s. Keyboard map: ⏎ approve, `e` edit, `x` reject, ↑/↓ navigate, `esc` exit.
- **State.** Shipped (Phase A).
- **Gaps / risks.** Phase B is backend-blocked — drafted emails depend on cycle reply ingestion, extracted cycle questions depend on a pipeline that is currently a stub. No bulk-approve path; every action is one-by-one.
- **Open decisions.** **Bulk approve vs. strict one-by-one.** Today the rule is one item, one ⏎. The argument for bulk-approve is throughput on a 30-item Friday; the argument against is that approval is the audit anchor for the chain-of-custody contract and bulk approval dilutes that. See _Open Questions_ at the end.

### 3. Reading Viewer — paragraph-level citations

- **What it is.** The canonical document surface at `/app/documents/:id`. Body text on the left, commentary rail on the right (bottom drawer on mobile). Every signal, ask answer, briefing or chat message that cites a passage from a document deep-links into the exact paragraph.
- **User value.** "Cite every number to the page it came from" is the marketing promise. The Reading Viewer is where that promise becomes interaction: click a citation chip → scroll to anchor → the cited paragraph highlights briefly.
- **How it works today.** Backend `routers/documents.py` `GET .../paragraphs` (lazy-compute; cron sweep at `POST /api/cron/paragraph-anchors-sweep`, daily 03:00 UTC). Anchor IDs are stable hashes of the paragraph text plus an order index, persisted on `db.documents.paragraphs[]` with an `anchors_version` field for cache invalidation. Frontend `pages/ReadingView.jsx` plus components `reading/ReadingBody.jsx`, `reading/ReadingRail.jsx`, `reading/CitationChip.jsx`, `reading/CommentaryDrawer.jsx`, hooks `useDocumentParagraphs.js`, `useReadingScrollSync.js`. The `?v=2` flag from the Phase 1 transition has been retired — `ReadingView` is the only document viewer left.
- **State.** Shipped.
- **Gaps / risks.** Paragraph-level LLM prompts are deferred: today the LLM still receives a chunked document blob and the citation back-resolves to a paragraph. Validator-confirmed-signal in the rail is deferred (only Briefings carry a real validator pass).
- **Open decisions.** —

### 4. Cycle Strip — board cycle timeline

- **What it is.** A horizontal six-phase ribbon pinned at the top of Home and `/app/cycle`: _Pack arriving · Reading week · Pre-board · Meeting · Minutes · Follow-up_.
- **User value.** Tells a director where in the rhythm they are. Click a phase, get a Sheet with what's awaiting them in that phase. Tenants can rename, reorder and time the phases on `/app/settings/cycle`.
- **How it works today.** Backend `routers/cycle_config.py`: `GET/PUT /api/contexts/{cid}/cycle-config`, `POST .../advance`, `POST .../reset`, `GET .../phases/{phase_id}/summary`. Mongo collection `cycle_configs` keyed per context. Frontend `components/cycle/CycleStrip.jsx`, `cycle/CyclePhaseSheet.jsx`, page `pages/CycleSettings.jsx`. Mobile: scroll-snap; Sheet downgrades to a bottom drawer.
- **State.** Shipped.
- **Gaps / risks.** No previous-cycle history (cycle_offset < 0) and no full-filtered Workspace view from the phase summary — both deferred to v2.
- **Open decisions.** —

### 5. Depth Disclosure — Lens / Simulate / Influence Map / Strategic Goals / Plays

- **What it is.** Five "depth" surfaces — Lens, Simulate, Influence Map, Strategic Goals, Plays — that do not appear in the primary nav until the user crosses an evidence threshold of three documents ingested or one briefing generated.
- **User value.** The new user is not flooded with every feature on day one. The seasoned user gets the toolbox unlocked the moment the corpus justifies it. Pro-gated items (Lens, Simulate) carry an inline _Pro_ pill and open the upgrade modal on click; URLs remain reachable so bookmarks never break.
- **How it works today.** Backend `routers/depth.py`: `GET /api/me/depth-status`, `POST /api/me/depth-status/dismiss`. Eligibility computed across the user's active contexts. Sector → suggested lens map: Banking/FS/Fintech → Risk; SaaS/Tech → Growth; Healthcare/Pharma → Compliance; everything else → Audit Committee. Frontend `hooks/useDepthStatus.js`, `components/depth/DepthOfferCard.jsx`, `depth/ProPill.jsx`, `depth/UpgradeModal.jsx`. Lens runs at `routers/lens.py`; Simulate at `routers/simulate.py`; Influence Map at `routers/influence_map.py` with a Monday 08:00 UTC weekly digest; Strategic Goals at `routers/strategic_goals.py`; Plays at `routers/plays.py`.
- **State.** Shipped.
- **Gaps / risks.** _Cross-Board Pulse_ is a marketing pillar but is implemented as a toggle on Home's aggregated stream rather than a dedicated surface. Per `AUDIT_iter68.md` (P1) the call is to either build the surface or soften the landing copy.
- **Open decisions.** —

### 6. Studio — briefings, decks, reports + sensitivity scoring

> **Phase 10 / Phase 11 update — 2026-05-02.** The Phase 8 block composer
> is now wired and reachable. `routers/studio_blocks.py` is registered
> at `server.py:76,140`; the frontend editor lives at
> `frontend/src/components/studio/BlockComposer.jsx`; the host page is
> `frontend/src/pages/StudioComposerPage.jsx`; the route
> `/app/studio/composer/:kind/:artefactId` is live in `App.js:192`.
> Phase 11 adds: hard public-read redaction assertion
> (`_assert_public_safe` in `studio.py`), watermarked `/share/:token`
> alias, and an independent-validator pass on Decks (`generate_deck`)
> and Reports (`send_report_up`) and Solve syntheses (`post_turn`),
> persisted as a `validation` payload that gates `<ValidatedBadge />`
> rendering on each surface.

- **What it is.** The composition surface for board-grade artefacts. Three artefact kinds — Briefing, Deck, Report — each with a flat-text editor, sensitivity auto-classification on save, read-receipt tracking, and a tracked share email loop.
- **User value.** A defensible, sensitivity-tagged board pack with end-to-end visibility on who has read what. The exposure pill on every artefact moves in real time as readers open it.
- **How it works today.** Three backend routers carry it: `routers/briefings.py` (briefing lifecycle + speaking notes + export), `routers/decks.py` (outline → generate → quality_check → feedback), `routers/cycle.py` for reports (composed from cycle submissions, polished, sent up, exported as PDF or deck-style PDF). The unifying surface is `routers/studio.py`: `POST .../view` (logs read, dedupes per (artefact, account, day)), `GET .../engagement`, `POST .../share`, `POST .../rescore` (re-runs the sensitivity classifier), `POST .../backfill_sensitivity`, `GET /api/contexts/{cid}/studio/history`, `POST .../share-email` (Resend), `GET /api/public/studio/track/{token}` (signed JWT, 14-day TTL, redirects to deep link), `GET /api/public/studio/read/{token}`. The classifier itself lives in `studio_sensitivity.py` — deterministic regex ladder (PUBLIC 0–24 / INTERNAL 25–49 / CONFIDENTIAL 50–74 / RESTRICTED 75–100) with reason codes, plus an opt-in LLM tiebreaker for the ambiguous internal band. Public sensitivity demo for the marketing site at `POST /api/public/studio/sensitivity-demo`. Mongo collections: `briefings`, `decks`, `reports` (under `cycle.py`), `studio_views`, `studio_shares`. Frontend: `pages/Decks.jsx`, `pages/Prepare.jsx` (briefings tab), `components/studio/ShareArtefactModal.jsx`.
- **State.** Shipped. The Phase 8 block composer (paragraph / heading_2 / heading_3 / callout / citation / signal_card / divider) ships behind `/app/studio/composer/:kind/:artefactId`; image blocks upload through the ClamAV + S3/MinIO pipeline introduced in Phase 10.
- **Gaps / risks.** Validator coverage on Decks, Reports and Solve syntheses landed in Phase 11 (an independent Gemini 2.5 Flash pass with a per-surface daily soft cap). The public read-only Chair view now lands non-AKKI directors on `/share/:token` (alias of `/shared/:token`) with a watermarked, redacted, read-only render — no signin wall. Outstanding: the Stripe → Solve Pro entitlement flip (latent while `BILLING_ENABLED=false`).
- **Open decisions.** **Studio composer scope.** Should v1 of the block composer be briefings-only behind `?composer=v2` for seven days and then default-on, or should it ship straight to all three artefact kinds? See _Open Questions_.

### 7. Sandbox — 60-second pre-auth fictional workspace

- **What it is.** A no-signup demo: pick a sector + role + objective on `/sandbox`, watch a 10-stage streaming narrative on `/sandbox/generating/:sessionId`, land on `/app?tutorial=1` (the role-aware home) with the sandbox banner, sample-doc-drop CTA, and three quick-action cards ready to click. If the prospect drops their own pack via `SandboxPackDrop`, they then land on `/app/quick-results/:cid/:docId` once extraction completes.
- **User value.** The marketing-to-product bridge. A buyer who is not yet ready to give an email gets to feel the product on their own sector inside one minute. Conversion is captured later via `/app/contexts/{cid}/capture-email` and `POST /api/sandbox/convert` which keeps the sandbox context alive as a working context post-signup.
- **How it works today.** Backend `routers/sandbox.py` (~900 lines): seed + 10-stage streaming generation, six polished sector templates in `sandbox_templates.py`, sample doc swap-in (`.../sample-doc/accept`), an `objective_check` 24-hour follow-up card, conversion handoff that pre-fills First Session via `prefill_first_session`. Frontend pages `Sandbox.jsx`, `SandboxGenerating.jsx`, `QuickResults.jsx`; components in `components/sandbox/`. The `/admin/sandbox-kpi` panel watches conversion.
- **State.** Shipped.
- **Gaps / risks.** Sandbox accounts use a cookie + Bearer combo; iter59 fixed a stale-cookie poisoning bug there. **Sandbox uploads go through the same strict ClamAV-or-bypass precondition as the rest of the product** (`virus_scan_stub` was retired in Phase 10; live ClamAV in `services/clamav_service.py`). Dev pods without the clamd binary set `ALLOW_UNSAFE_UPLOADS=true` — see `docs/RUNBOOKS/DEV_POD_CAVEATS.md`. Phase G owns the permanent fix (clamd + freshclam in the container image).
- **Open decisions.** —

### 8. Governance Panel — audit logs, shielding status, model usage

- **What it is.** A right-side Sheet (bottom on mobile) launched from the user menu's _Trust_ item. Five sections: Audit log (with ZIP export), De-identification status, Inbound email address, Connected models, Sensitivity at a glance.
- **User value.** Quiet system-utility for the enterprise buyer or the curious NED. Read-only. Editorial register, no oxblood emphasis, no spinners.
- **How it works today.** Backend `routers/governance.py`: `GET /api/me/governance`, `GET /api/me/governance/audit?action=&since=&until=&cursor=&limit=`, `POST /api/me/governance/audit/export` (ZIP with `audit_log.csv` and `manifest.txt`). Connected models read from `SUPPORTED_MODELS` in `routers/chat.py` so the list does not drift. Frontend `components/governance/TrustPanel.jsx`. No new collections — reads `audit_log`, `accounts`, `contexts`, `studio_sensitivity` aggregates.
- **State.** Shipped.
- **Gaps / risks.** Live de-identification badge on shielding is deferred (regex-only today; live Synisense URL swap in v2).
- **Open decisions.** —

### 9. Contexts — boards / company seats

- **What it is.** A first-class isolation boundary. Every membership, document, signal, briefing, deck, audit row, comment and play lives inside one context. Switching context rebuilds the experience. NEDs sitting on multiple boards live across multiple contexts.
- **User value.** A Chair on three boards sees three separate corpora, not a blended one. Sharing across contexts is explicit, never implicit.
- **How it works today.** Backend `routers/contexts.py`: full CRUD, members, invitations (`POST .../invitations`, `GET /api/invitations/by-token/{token}`, `POST /api/invitations/{token}/accept`), context-object onboarding (`GET/POST .../context-object`). Committees nested under each context (`routers/committees.py`). Multi-context portfolio at `pages/ContextPortfolio.jsx`; new-context flow at `pages/NewWorkspace.jsx`; tenant settings at `pages/TenantSettings.jsx`; per-context cycle settings at `pages/CycleSettings.jsx`. Membership enforcement runs through `core.require_context_membership(owner_only=False|True)` on every protected route.
- **State.** Shipped.
- **Gaps / risks.** Cross-context aggregation (Cross-Board Pulse) is a Home toggle, not a dedicated surface — see Depth gaps.
- **Open decisions.** —

### 10. Chat — Claude-shape with citation chips and mode selector

- **What it is.** A conversation surface with a mode selector (`Ask · Solve · Draft`) above the input. Every corpus-grounded turn ends with citation chips that deep-link into Reading at the cited paragraph.
- **User value.** Free-form thinking on top of the corpus, with a defensible audit pack on every chat (SHA-256-chained, exportable as a ZIP).
- **How it works today.** Backend `routers/chat.py`: `POST /api/chats`, `GET /api/chats`, `GET/PATCH/DELETE /api/chats/{id}`, `POST /api/chats/{id}/messages`, `GET /api/chats/{id}/audit`, `GET /api/chats/{id}/audit/export.zip` (ships `verify.py` for offline chain verification). Models surfaced via `GET /api/chat/models`. Frontend `pages/Chat.jsx`, `components/chat/ModelAvatar.jsx`. Recent chats live as a top-right "Recent" dropdown (max 8) — there is no chat-history sidebar competing with Home, by design.
- **State.** Shipped.
- **Gaps / risks.** No voice input, no image generation, no plugins (explicit non-goals per Advisory 3). The shielding override is per-message (`db.chat_messages.shielding_override`); the live de-id badge is deferred.
- **Open decisions.** —

### 11. Adjacent surfaces — for completeness

The following are real and shipping but were not on the canonical feature list. They are summarised in one line each:

- **First Session** (`pages/FirstSession.jsx`, `routers/first_session.py`): three-question intake + three doors (forward email, upload, run Solve) ending with one AKKI-generated artefact. Grandfathered users auto-skip via `/auth/me`.
- **Catch-up Brief / Prepare** (`pages/Prepare.jsx`, `routers/prepare.py`): the brief surface for "I have a meeting in two hours." Different collection (`db.briefs`) from the formal `db.briefings` — see _Known Mocks & Stubs_.
- **Inbound Queue** (`pages/InboundQueue.jsx`, `routers/inbound_queue.py`): triage surface for emails received via Postmark; trust-tiered review.
- **Plays / Workflows** (`pages/PlaysLibrary.jsx`, `pages/PlayView.jsx`, `routers/plays.py`): cadenced multi-stage workflows (Board Pack Play, Pre-Board Play, etc.).
- **Lens / Simulate / Influence Map / Monitor (Strategic Goals)**: depth surfaces, all real, gated by Depth Disclosure.
- **Marketing site** (`pages/marketing/*`): About, Features, Security, Plans, Enterprise, EarlyAccess, Blog (with a Tuesday 10:00 UTC weekly Exco360 cron job).
- **Admin** (`pages/admin/*`): Health, SandboxKPI, SignalKPI, LLMSpend, AuthEvents, AdminIndex.

---

## Integrations Inventory

| Integration | Used for | Implementation | State |
|---|---|---|---|
| **LLM gateway (Claude / OpenAI / Gemini via Emergent Universal Key)** | Briefings, Decks, Reports, Solve, Chat, Lens, Simulate, Signals, Sandbox narrative, Blog | `llm_service.py` wraps `emergentintegrations`. Tier model env vars: `LLM_MODEL_DEEP=claude-opus-4-6`, `LLM_MODEL_STANDARD=claude-sonnet-4-5-20250929`, `LLM_MODEL_FAST=gemini-2.5-flash`. Per-account-per-surface daily quota via `db.llm_deep_usage` (race-safe via unique compound index). Per-tenant spend roll-up at `/admin/llm-spend`. | **Real.** Deterministic fallback (`mode: "no-key-fallback"`) when `EMERGENT_LLM_KEY` is unset so dev never breaks. |
| **Independent validator (Gemini 2.5 Flash)** | Second-LLM countersign on briefings | `llm_service.py` `validate_with_second_model()` returns `{verdict, confidence, notes, validator_provider, validator_model}`. Soft-fails to `qualified` on outage. Called from `routers/prepare.py`. | **Real on briefings.** Cosmetic on Decks, Reports, Solve syntheses — badge present, second call absent. (P1 in `AUDIT_iter68.md`.) |
| **Resend (transactional email)** | Outbound checklists, share-with-Chair, sample handoffs, weekly Exco360 newsletter | `email_service.py` reads `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `RESEND_FROM_NAME`. Returns `{ok, id, mode}`. | **Real**, with `mode: "noop"` when the key is unset. |
| **Postmark (inbound email)** | Per-account and per-context inbound mailboxes; queue triage | `routers/inbound_email.py` exposes `POST /api/inbound/postmark` — secret in query string. Hash-token routing, Postmark mailbox-hash lookup. Idempotency via the queue collection. | **Real.** Default domain `inbound.akki.ai`; configurable. |
| **Stripe (billing)** | Plan billing + Solve Pro checkout | `routers/billing.py`: `GET /api/billing/plans`, `GET /api/billing/me`, `POST /api/billing/checkout`, `GET .../status/{session_id}`, `POST /api/webhook/stripe`. Uses `emergentintegrations` Stripe wrapper. Default key is `sk_test_emergent`. | **Partial / test-mode.** Webhook receives events; the plan flip on `account.plan` works; the Solve Pro entitlement flip on the toggle is incomplete. (P1.) |
| **APScheduler (in-process cron)** | Tuesday 10:00 UTC weekly Exco360 article; Monday 08:00 UTC Influence Digest; Daily 03:00 UTC paragraph anchors sweep | `server.py` startup; gated by `AKKI_CRON_SECRET`; calls localhost endpoints with `X-Cron-Secret`. | **Real.** Single-replica only; HA needs an external scheduler hitting the same endpoints. |
| **Local disk storage** | All uploaded documents + generated PDFs | `documents_service.py` `save_to_storage / read_from_storage / delete_from_storage` writing under `/app/backend/uploads/{document_id}/`. | **Stub for cloud storage.** No S3 / GCS. Survives container restarts because the directory is on the persistent volume. |
| **Synisense (de-identification)** | Per-message and per-context PII shielding | `routers/synisense.py`: `GET /api/synisense/status`, `POST /api/synisense/dryrun`. Today the shielding ladder is regex-based inside `llm_service.py`. The endpoint surface exists for a future live URL swap. | **Stub / regex-only.** Live URL swap deferred to v2. |
| **BM25 retrieval** | ⌘K local search, Ask grounding | `bm25.py`. Pure-Python BM25 over extracted text. | **Real but capped.** Quality ceiling expected at ~50 documents per context; vector DB upgrade explicitly deferred (Path A constraint). |
| **Virus scan** | Every uploaded document | `documents_service.virus_scan_stub`. | **Stub.** Returns clean for valid file types; rejects only on extension/size mismatch. |

---

## Trust & Governance

The trust contract is consistent across surfaces:

1. **Citations.** Every grounded LLM answer (briefings, signals, ask, chat) returns a `references[]` array with optional `paragraph_id`. The frontend renders these as chips that deep-link into the Reading viewer at the exact paragraph anchor (`reading/CitationChip.jsx`).
2. **Sensitivity scoring.** Every Studio artefact is auto-scored on save by `studio_sensitivity.classify()`. The score (0–100) maps to one of `PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED` and surfaces as a chip on every artefact card and an aggregate tile in the Trust panel. The classifier is deterministic so users can audit it; an LLM tiebreaker is opt-in for the ambiguous internal band (P2 to promote to default-on).
3. **Audit ledger.** `core.write_audit()` writes to `db.audit_log` on every consequential mutation (membership change, artefact create/edit/delete, share, classification change, deletion). The Governance panel offers a filterable view and a ZIP export with `audit_log.csv` plus a `manifest.txt` recording the actor and the filter window. The chat audit pack adds a SHA-256 chain and a `verify.py` so the export is verifiable offline.
4. **Shielding.** Every LLM call passes through the regex-based shielding layer in `llm_service.py`. The response includes `shielding: {identifiers_masked, by_category, shielded_by}`. The shielding chip in the top bar is "SHIELDED · REGEX" today; it dims to a muted grey when a per-message override is active.
5. **Read-receipts and exposure.** Every Studio artefact view is upserted into `db.studio_views` (unique on `artefact_kind + artefact_id + account_id + day_utc`). External readers collapse to a synthetic `account_id = external:<sha256(email)>`, so a Chair re-opening the deck dedupes correctly. The exposure score (0–100) climbs with unique readers, share count, external share count, and information staleness.

---

## Design System Notes

- **Palette.** Cream `#F7F3EA`, oxblood `#8B2E2B`, executive navy `#0A1F44`. Text `#111827` primary, `#4B5563` secondary. Cream-on-navy for the enterprise full-bleed band only.
- **Typography.** Georgia serif for headlines (sentence case, left-aligned, `tracking-tight`). Inter for body and chrome. JetBrains for monospace metadata. No new tokens introduced after Phase 1.
- **Iconography.** Lucide only. No emojis in copy. No exclamation marks in body.
- **Loading copy.** Editorial: _"Reading the pack…"_, _"Comparing across documents…"_, _"Reading your trust ledger…"_. Never a spinner alone.
- **Empty states.** One sentence + one action. Never a feature tour.
- **Errors.** Honest, not cute. _"AKKI couldn't reach the document. The source link may have expired."_
- **Component lineage.** Radix UI primitives (`@radix-ui/*`) as the base; `tailwind-merge` and `class-variance-authority` for class composition; `framer-motion` for restrained motion only; `sonner` for toasts (right-aligned, used sparingly — never for approvals); `recharts` for the few quantitative panels (Sandbox KPI, LLM Spend, Strategic Goals, Monitor sparklines); `react-resizable-panels` for the Reading two-pane.
- **Patterns inherited from peers.** Claude (citation chips, model avatars in Chat); Linear (the keyboard-first Daily Review); Notion (the planned block composer). The product deliberately avoids gradient-heavy SaaS aesthetics, AI mascots, gamification badges and progress bars.

---

## Known Mocks & Stubs

> **Phase 10 / Phase 11 update — 2026-05-02.** Three rows previously
> listed here were retired: virus scanning is now real (ClamAV sidecar,
> `backend/services/clamav_service.py`); local-disk storage is replaced
> by an S3/MinIO-compatible backend (`backend/services/storage_service.py`,
> `STORAGE_BACKEND=s3|minio` in prod); the Stripe `sk_test_emergent`
> default is gone — billing is gated by `BILLING_ENABLED` with a boot
> guard (`server.py:219-227`). The Phase 8 block-composer "drafted but
> not exposed" row is also retired — it is wired and reachable.

| Item | File path(s) | Why it's a stub | Risk |
|---|---|---|---|
| Virus scan on uploads | ~~`/app/backend/documents_service.py` (`virus_scan_stub`)~~ — **retired Phase 10**: real ClamAV sidecar via `services/clamav_service.py` (INSTREAM TCP socket, scanner-unreachable → 503, signature match → 422) | n/a — no longer a stub | n/a |
| Live Synisense de-identification | `/app/backend/routers/synisense.py`, `/app/backend/llm_service.py` | Live service URL swap deferred to v2 | Low — regex ladder is sufficient for shielding the LLM call; surface chip is honest ("REGEX") |
| Public read-only Chair view | ~~`/app/backend/routers/studio.py:707`~~ — **retired Phase 11 ITEM A**: `/share/:token` alias + watermarked + denylist-asserted public read | n/a — no longer a stub | n/a |
| Independent validator on Decks, Reports, Solve | ~~`/app/backend/routers/decks.py`, `/app/backend/routers/cycle.py`, `/app/backend/routers/solve_engine.py`~~ — **retired Phase 11 ITEM B**: real Gemini 2.5 Flash second-pass; `validation` payload persisted on each artefact; `<ValidatedBadge />` gated on real verdict; daily soft cap counter (`db.llm_validator_usage`) | n/a — no longer a stub | n/a |
| Stripe → Solve Pro entitlement flip | `/app/backend/routers/billing.py`, plus solve_pro gating in `routers/solve_engine.py` | Webhook receives, plan flips, but solve-pro toggle on the affordance does not | High if monetisation push happens before fix |
| ~~Phase 8 block composer~~ | ~~`/app/backend/routers/studio_blocks.py`~~ — **retired Phase 8 / Phase 11 update**: router registered (`server.py:76,140`), `BlockComposer.jsx` live, route `/app/studio/composer/:kind/:artefactId` reachable | n/a — no longer a stub | n/a |
| Cross-Board Pulse as a dedicated surface | Today implemented as a toggle on Home v2 (`/app/frontend/src/pages/HomeV2.jsx`) | Surface not built; landing copy implies it | Low — copy can be softened |
| Cloud object storage (S3 / GCS) | ~~`/app/backend/documents_service.py` (`save_to_storage` writes locally to `/app/backend/uploads/`)~~ — **retired Phase 10**: `backend/services/storage_service.py` switches on `STORAGE_BACKEND=local\|s3\|minio`; prod runs MinIO gateway over Azure Blob (`STORAGE_MIGRATION.md`) | n/a — no longer a stub | n/a |
| Vector DB | `/app/backend/bm25.py` | BM25 only | Low until ~50 docs per context |
| `db.briefings` vs `db.briefs` collision | `/app/backend/routers/briefings.py` (formal artefact) vs `/app/backend/routers/prepare.py` (Catch-up brief) | Two collections, two UX paths, similar names | Low but confusing — rename "Briefings" to "Reports" in Studio history is on the P2 list |
| Plays route duplication | `/app/frontend/src/pages/PlaysLibrary.jsx`, `pages/PlayView.jsx`, plus Home `PlayReadyCards.jsx`, plus Studio `ActiveWorkflowsRail` | Three entry points to the same workflow | Low — cosmetic |
| Phase B Daily Review (drafted emails, extracted cycle questions) | `/app/backend/routers/daily_review.py` | Backend pipelines for those item kinds are stubs | Med — promise of the modality is wider than today's reach |

---

## Open Questions

Two decisions are live for the operator. Each should be resolved before the next code change in the affected surface.

**1. Studio composer scope.** Phase 8 / Advisory 9 is in flight. The backend block schema (`db.studio_blocks`) and the seven-block library (paragraph, heading_2, heading_3, callout, citation, signal_card, divider) are drafted at `/app/backend/routers/studio_blocks.py` but the router is not registered and there is no frontend `BlockComposer.jsx`. The decision: ship v1 of the block composer **briefings-only**, gated by `?composer=v2` for seven days then default-on (lower risk, easier rollback, mirrors the Reading-Viewer Phase-1 cadence) — _or_ ship to all three artefact kinds (briefing + deck + report) at once (faster, fewer transitions, but a wider blast radius). The system prompt assumes briefings-only; the audit recommends confirming.

**2. Daily Review — bulk approve vs. strict one-by-one.** Today every approval is one item, one keystroke. Throughput pressure on a thirty-item Friday is the case for a `Shift+⏎` bulk-approve on the visible queue. The case against: the audit ledger ("`approved_at`, `approved_by`, `evidence_at`") loses precision under bulk approval, and the load-bearing modality stops being load-bearing. The decision: keep strict one-by-one (audit purity wins, throughput remedy is to fix what produces thirty items rather than to approve them in a swipe) — _or_ allow bulk-approve scoped only to inbound-doc placeholders where evidence is the file-attach itself.

---

## Roadmap Snapshot

- **Current phase: Studio Composition (Advisory 9 / Phase 8).** Backend drafted, not wired. Frontend not started. Decision pending on scope (Q1 above).
- **Pending P1 from `AUDIT_iter68.md`:** Stripe → Solve Pro entitlement flip; real validator fan-out to Decks / Reports / Solve; Cross-Board Pulse as a dedicated surface or copy softened; public read-only artefact view for non-AKKI recipients.
- **Pending P2:** Rename "Briefings" → "Reports" in Studio history (resolves the briefs / briefings collision); collapse `/app/plays` into Studio's ActiveWorkflowsRail; promote sensitivity LLM tiebreaker to default-on; real virus scan; vector DB upgrade.
- **P3 / open-ended:** M6 integrations (calendar, board portals); Monthly Performance Workflow (executive); Cross-Board Pulse Workflow (NED).

---

## Appendix A — Backend Route Map

All routes share an `/api` prefix unless noted. Routes are grouped by router file under `/app/backend/routers/`.

| Router | Method · Path | Purpose |
|---|---|---|
| `auth.py` | POST `/auth/register` · POST `/auth/login` · POST `/auth/logout` · POST `/auth/refresh` · GET `/auth/me` · POST `/auth/declare-role` · POST `/auth/mfa/{setup,verify,disable}` | Account auth + MFA |
| `contexts.py` | POST `/contexts` · GET/PATCH/DELETE `/contexts/{cid}` · GET `/contexts/{cid}/members` · DELETE `.../members/{aid}` · POST/GET/DELETE `.../invitations[/{id}]` · GET/POST `/invitations/by-token/{token}` · POST `/invitations/{token}/accept` · GET/POST `.../context-object` · PATCH `/accounts/me` · POST `/accounts/me/default-context` · GET `/presets/{industries,jurisdictions}` | Contexts + memberships + invitations + onboarding object |
| `committees.py` | GET/POST/PATCH/DELETE `/contexts/{cid}/committees[/{id}]` | Per-context committees |
| `documents.py` | POST `/contexts/{cid}/documents` · GET/PATCH/DELETE `.../documents/{doc_id}` · GET `.../download` · GET `.../paragraphs` · POST `.../summary` · POST `.../evolution-diff` · POST `.../generate-meta` · GET `.../thread` · POST `/cron/paragraph-anchors-sweep` | Document upload, retrieval, paragraph anchors |
| `document_engagement.py` | POST `.../view` · POST `.../share` · GET `.../engagement` | Per-doc read tracking |
| `signals_ask.py` | POST `.../signals/generate` · GET/DELETE `.../signals[/{id}]` · POST/GET `.../ask` | Signals + Ask (LLM grounded) |
| `signal_actions.py` | GET `.../signals/{id}/recommendations` · POST/GET `.../signals/{id}/actions` | Signal action recommendations |
| `briefings.py` | POST/GET/DELETE `.../briefings[/{id}]` · POST `.../{id}/mark-read` · POST `.../{id}/speaking-notes` · GET `.../{id}/export` | Formal briefings + speaking notes |
| `prepare.py` | GET `/prepare/brief-kinds` · POST/GET/DELETE `.../briefs[/{id}]` · GET `.../minutes` · POST `.../minutes/{doc_id}/{extract,to_cycle,narrative}` | Catch-up briefs + minutes |
| `decks.py` | POST `.../decks/outline` · POST `.../decks/{outline_id}/generate` · POST `.../decks/{deck_id}/{quality_check,feedback}` · GET `.../decks[/{id}]` · GET `/decks/{id}/context` | Decks pipeline |
| `cycle.py` | GET/POST/PATCH `.../questions[/{qid}]` · POST `.../questions/seed-from-briefings` · GET/POST/DELETE `.../reportees[/{rid}]` · POST/GET/PATCH `.../checklists[/{cid}]` · POST `.../checklists/dispatch` · GET/POST `/respond/{token}` · GET `.../submissions` · POST/GET/PATCH `.../reports[/{rid}]` · POST `.../reports/{rid}/{send_up,review,polish}` · GET `/reports/inbox` · GET `.../reports/{rid}/{export.pdf,export.deck.pdf}` · GET `.../cycle/committees` · GET/PUT/DELETE `.../cycle/schedule` · POST `/cycle/cron/run-schedules` | Cycle: questions, reportees, checklists, submissions, reports, polish, schedule |
| `cycle_config.py` | GET/PUT `.../cycle-config` · POST `.../cycle-config/{advance,reset}` · GET `.../cycle-config/phases/{id}/summary` | Cycle phase strip config |
| `comments.py` | GET/POST/DELETE `.../{artefact_type}/{artefact_id}/comments[/{id}]` · GET `.../mentions` · POST `.../mentions/{id}/read` | Comments + mentions |
| `daily_review.py` | GET `/api/me/review-queue[/counts]` · POST `.../items/{kind}/{id}/{approve,reject,edit}` | Approval queue |
| `first_session.py` | GET `/api/me/first-session` · POST `.../start,intake,choose-door,complete,skip` | First Session flow |
| `depth.py` | GET `/api/me/depth-status` · POST `.../dismiss` | Depth disclosure |
| `governance.py` | GET `/api/me/governance` · GET `.../audit` · POST `.../audit/export` | Trust panel |
| `chat.py` | GET `/chat/models` · POST `/chats` · GET `/chats[/{id}]` · PATCH/DELETE `/chats/{id}` · POST `/chats/{id}/messages` · GET `/chats/{id}/audit[/export.zip]` | Chat with audit pack |
| `lens.py` | GET `/lens/catalog` · POST/GET/DELETE `.../lens/run[s][/{id}]` · POST/GET/DELETE `.../lens/coach/sessions[/{id}/messages]` | Lens runs + coach |
| `simulate.py` | POST/GET/DELETE `.../simulate[/{id}]` | What-if simulations |
| `monitor.py` | GET `.../monitor` | Strategic-goal monitor |
| `strategic_goals.py` | GET/POST/PATCH/DELETE `.../strategic-goals[/{id}]` · POST `.../strategic-goals/extract` | Strategic goals |
| `influence_map.py` | GET `.../influence-map` · POST `.../influence-map/digest` · POST `/cron/weekly-digest` | Influence map + Monday digest |
| `plays.py` | GET `/plays/library` · GET/POST `.../plays[/{id}]` · POST `.../plays/{id}/{advance,jump,pause,resume,seen,exit,pre_board/read}` · PATCH `.../plays/{id}/state` | Plays / workflows |
| `solva.py` | POST `/api/solva/interest` · GET `/api/solva/interest/me` · _(legacy `/api/solve/*` 308-aliased)_ | Solva early-access |
| `solve_engine.py` | GET `.../clusters` · GET `.../pro-status` · POST/GET `.../sessions[/{sid}]` · POST `.../{turn,restart,abandon}` · POST `.../handoff/{brief,decks,cycle}` · GET `.../handoffs` · GET `.../export.pdf` | Four-phase Solve engine |
| `studio.py` | POST `/api/public/studio/sensitivity-demo` · POST `.../{kind}/{aid}/{view,share,rescore,share-email}` · POST `.../backfill_sensitivity` · GET `.../studio/history[/{kind}/{aid}/engagement]` · GET `/api/public/studio/{track,read}/{token}` | Studio: views, shares, sensitivity, public tracking |
| `studio_blocks.py` | GET/POST/PATCH/DELETE `/api/studio/{kind}/{aid}/blocks[/{block_id}]` · POST `.../move` · POST `.../reorder` | **NOT WIRED.** Phase 8 block composer in `server.py` `include_router` list — absent |
| `synisense.py` | GET `/synisense/status` · POST `/synisense/dryrun` | De-identification status |
| `shares.py` | POST `/contexts/{cid}/shares` · GET `/me/shares/{inbox,outbox}` · GET/DELETE `/shares/{id}` · GET `/me/home/stream` | Cross-context shares + Home river |
| `audit.py` | GET `.../audit-log` · POST `.../export` | Per-context audit |
| `pipeline.py` | POST `.../pipeline/run` · GET `.../pipeline/events` | Ingest pipeline trace |
| `agenda.py` | GET `.../agenda-evolution` | Agenda evolution |
| `learn.py` | POST `/learn/research` | Learn surface |
| `walkin.py` | POST `/api/walkin` · POST `/api/walkin/regenerate` | Walk-in question on Catch-up |
| `inbound_email.py` | GET `/api/inbound/address` · POST `/api/inbound/postmark` | Inbound mailbox + Postmark webhook |
| `inbound_queue.py` | GET `.../inbound-queue[/{id}]` · GET `/api/me/inbound-queue/counts` · POST `.../accept,reject` | Triage queue |
| `enterprise.py` | POST `/api/enterprise/interest` · GET `.../me` | Enterprise lead capture |
| `early_access.py` | POST `/api/early-access/register` · GET `/api/early-access/registrations` | Early-access intake |
| `billing.py` | GET `/billing/{plans,me}` · POST `/billing/checkout` · GET `.../status/{sid}` · POST `/webhook/stripe` | Stripe checkout + webhook |
| `llm_quota.py` | GET `/llm/quota` | Per-account deep-tier quota |
| `admin_health.py` | GET `/admin/health/full` | Health dashboard |
| `admin_sandbox_kpi.py` | GET `/admin/sandbox/{kpi,objectives}` | Sandbox conversion KPIs |
| `admin_signal_kpi.py` | GET `/admin/signals/action-heatmap` | Signal action heatmap |
| `admin_llm_spend.py` | GET `/admin/spend` · GET `/admin/decks/quality` | LLM spend + deck quality roll-up |
| `admin_auth_events.py` | GET `/admin/auth/events` | Sampled auth observability |
| `blog.py` | GET `/blog/posts[/{slug}]` · POST `/blog/{subscribe,compose}` · POST `/blog/posts/{slug}/publish` · POST `/blog/cron/weekly` · POST `/blog/seed/launch-10` · DELETE `/blog/posts/{slug}` · GET `/blog/admin/posts/{slug}` · GET `/blog/subscribers` · GET `/blog/rss` | Editorial blog (Exco360) |
| `sandbox.py` | POST `/sandbox/generate` · GET `.../status` · GET `/sandbox/templates` · POST `/sandbox/cleanup/expired` · POST `.../capture-email` · GET/POST `.../tutorial[/dismiss]` · GET/POST `.../sample-doc[/accept]` · GET/POST `.../objective-check` · POST `/sandbox/convert` · POST `/sandbox/contexts/seeded` | Pre-auth sandbox |
| `product_features.py` | GET `/product-features[.md]` · GET `/ux-audit[.md]` · GET `/ux-advisories[.md]` | Self-published doc surface |
| `misc.py` | POST `.../llm/probe` · POST `/events` · GET `/` · GET `/health` | Probes + telemetry |

---

## Appendix B — Frontend Route Map

All routes resolved in `/app/frontend/src/App.js`. Every `/app/*` route is double-gated by `<ProtectedRoute>` and `<FirstSessionGuard>` unless noted.

| Path | Page | Notes |
|---|---|---|
| `/` | `Landing.jsx` | Marketing home |
| `/solve` | `SolveLanding.jsx` | Solve marketing |
| `/about`, `/features`, `/security`, `/plans`, `/enterprise`, `/early-access` | `marketing/*` | Marketing pages |
| `/blog`, `/blog/:slug` | `marketing/Blog.jsx`, `marketing/BlogPost.jsx` | Exco360 blog |
| `/methodology` | redirect → `/about#methodology` | |
| `/respond/:token` | `RespondToChecklist.jsx` | Public checklist response |
| `/shared/:token` | `SharedArtefact.jsx` | Public share landing |
| `/signin`, `/sign-in`, `/login`, `/log-in` | `SignIn.jsx` (others alias) | |
| `/signup`, `/sign-up`, `/register` | `SignUp.jsx` | Sandbox pass-through allowed |
| `/invite/:token` | `InviteAccept.jsx` | |
| `/sandbox`, `/sandbox/generating/:sessionId` | `Sandbox.jsx`, `SandboxGenerating.jsx` | Pre-auth |
| `/app/first-session`, `/onboarding` | `FirstSession.jsx` (alias redirect) | |
| `/app` | `AppHome.jsx` (flag-reader → `HomeV2.jsx` or `LegacyAppHome.jsx`) | |
| `/app/cycle` | `Cycle.jsx` | |
| `/app/monitor` | `Monitor.jsx` | |
| `/app/plays`, `/app/plays/:playId` | `PlaysLibrary.jsx`, `PlayView.jsx` | |
| `/app/blog-admin` | `marketing/BlogAdmin.jsx` | |
| `/app/workspace` | `Workspace.jsx` | Corpus browser + Ask |
| `/app/prepare` | `Prepare.jsx` | Catch-up briefs + briefings tabs |
| `/app/inbound-queue` | `InboundQueue.jsx` | |
| `/app/activity` | `Activity.jsx` | |
| `/app/highlights`, `/app/briefings` | redirects → `/app/prepare` | |
| `/app/ask` | redirect → `/app/workspace` | |
| `/app/simulate` | `Simulate.jsx` | Depth-gated |
| `/app/lens` | `LensRoom.jsx` | Depth-gated, Pro |
| `/app/chat` | `Chat.jsx` | |
| `/app/influence` | `InfluenceMap.jsx` | Depth-gated |
| `/admin/health,sandbox-kpi,signal-kpi,llm-spend,auth-events`, `/admin` | `admin/*` | Superadmin |
| `/app/quick-results/:contextId/:docId` | `QuickResults.jsx` | Sandbox handoff |
| `/app/learn`, `/app/learn/:id` | `Learn.jsx` | |
| `/app/manage` | `Manage.jsx` | |
| `/app/enterprise` | `Enterprise.jsx` | |
| `/app/decks`, `/app/decks/:deckId` | `Decks.jsx` | |
| `/app/solva` _(legacy `/app/solve` aliased)_ | `AppSolva.jsx` | |
| `/app/documents/:id` | `ReadingView.jsx` | Canonical reading |
| `/app/contexts`, `/app/contexts/new`, `/app/new-workspace` | `ContextPortfolio.jsx`, `NewWorkspace.jsx` | |
| `/app/settings`, `/app/settings/billing` | `TenantSettings.jsx` | |
| `/app/settings/cycle` | `CycleSettings.jsx` | |
| `/app/review` | `DailyReview.jsx` | Approval queue |
| `/app/security` | `AccountSecurity.jsx` | |
| `*` | redirect → `/` | Catch-all |

---

## Appendix C — Mongo Collections / Key Fields

Indexes referenced are those declared in `/app/backend/server.py` `on_startup`.

| Collection | Key fields | Purpose | Notable indexes |
|---|---|---|---|
| `accounts` | `id`, `email`, `password_hash`, `mfa_enabled`, `default_context_id`, `is_superadmin`, `plan`, `first_session`, `depth_offer_dismissed_at`, `inbound_token` | User accounts | unique on `email`, `id`; sparse on `inbound_token` |
| `contexts` | `id`, `name`, `type`, `industry`, `jurisdiction`, `sector`, `owner_account_id`, `committees[]`, `progress_state`, `inbound_token`, `sandbox_metadata` | Boards / company seats | unique on `id`; index on `owner_account_id`; sparse on `inbound_token` |
| `memberships` | `account_id`, `context_id`, `role`, `sub_role`, `status` | Per-context access | compound on `(context_id, account_id)`; on `account_id` |
| `invitations` | `token`, `context_id`, `email`, `expires_at`, `status` | Outbound invites | unique on `token`; compound on `(context_id, email)` |
| `audit_log` | `id`, `context_id`, `account_id`, `action`, `resource_type`, `resource_id`, `metadata`, `created_at` | Append-only audit ledger | compound `(context_id, created_at desc)` |
| `telemetry_events` | `context_id`, `account_id`, `event`, `payload`, `occurred_at` | UI telemetry | compound `(context_id, occurred_at desc)` |
| `login_attempts` | `identifier`, `attempts`, `locked_until` | Brute-force lockout (5 + 15 min) | on `identifier` |
| `consent_decisions` | `account_id`, `context_id`, `decisions` | Onboarding consent | compound |
| `organisations` | `id`, `name`, `domain` | Sponsoring orgs | unique on `id` |
| `documents` | `id`, `context_id`, `name`, `extracted_text`, `paragraphs[]`, `anchors_version`, `data_trust`, `storage_key`, `status`, `created_at` | Uploaded + ingested documents | unique on `id`; compound `(context_id, created_at desc)` |
| `signals` | `id`, `context_id`, `kind`, `references[]`, `created_at` | LLM-extracted signals | unique on `id`; compound |
| `ask_messages` | `context_id`, `messages[]`, `created_at` | Ask conversations | compound |
| `briefings` | `id`, `context_id`, `body`, `validator_*`, `status`, `created_at` | Formal briefings | compound `(context_id, status, created_at desc)` |
| `briefs` | (Catch-up briefs) | Implicit collection used by `routers/prepare.py` — distinct from `briefings` | — |
| `decks` | `id`, `context_id`, `outline`, `slides[]`, `quality`, `created_at` | Decks pipeline | compound |
| `reports` | (under `routers/cycle.py`) | Composed reports per cycle | — |
| `studio_views` | `artefact_kind`, `artefact_id`, `account_id`, `day_utc` | Read-receipt dedup | unique compound |
| `studio_shares` | `artefact_kind`, `artefact_id`, `context_id`, `created_at` | Share log | compound |
| `studio_blocks` | `artefact_id`, `artefact_kind`, `context_id`, `blocks[]` | **Phase 8 — drafted but not exposed.** | — |
| `inbound_queue` | `id`, `context_id`, `inbound_message_id`, `status`, `created_at` | Postmark triage | unique on `id`; compound; sparse |
| `inbound_queue_raw` | `queue_id` | Raw payload backup | unique |
| `comments` | (per-artefact) | Threaded comments | — |
| `mentions` | `account_id`, `read_at` | @-mention inbox | — |
| `chats`, `chat_messages` | `id`, `account_id`, `context_id`, `messages[]`, `shielding_override` | Chat + per-message override | — |
| `solve_sessions` | `id`, `account_id`, `cluster_id`, `phase`, `state`, `updated_at` | Solve four-phase state | compound `(account_id, updated_at desc)`, `(cluster_id, started_at desc)` |
| `solve_clusters` | `id`, `name`, `prompts[]` | Cluster taxonomy (seeded) | unique on `id` |
| `solve_comparables` | `id`, `cluster_id`, `sector_tag`, `body` | 27 anonymised diagnoses | unique on `id`; compound |
| `solve_handoffs` | `account_id`, `session_id`, `target`, `created_at` | Brief / decks / cycle handoffs | compound |
| `solve_free_grants` | `account_id`, `month_utc` | Monthly free-tier grant | unique compound |
| `llm_deep_usage` | `account_id`, `surface`, `day_utc` | Race-safe deep-tier quota | unique compound |
| `auth_events` | `at`, `ok`, `reason`, `credentials`, `dual_mismatch`, `path`, `method` | Sampled auth observability | desc on `at` |
| `cycle_configs` | `context_id`, `phases[]`, `current_phase` | Cycle strip per-context | — |
| `document_views` | `doc_id`, `account_id`, `day` | Per-doc dedup | unique compound |
| `document_shares` | `doc_id`, `created_at` | Per-doc share log | compound |
| `shares` | `id`, `shared_with_account_id`, `shared_by_account_id`, `created_at` | Cross-context shares | unique on `id`; compounds |
| `early_access_registrations` | `email`, `created_at` | Marketing intake | unique on `email`; desc on `created_at` |
| `lens_runs`, `simulations`, `plays`, `strategic_goals`, `monitor_*`, `blog_posts`, `blog_subscribers`, `agenda_evolution`, `pipeline_events`, `walkin_questions` | (referenced by their routers; indexes per file) | Feature-specific stores | — |

---

_End of review. Generated read-only against `/app` on this branch. The Studio block composer (`/app/backend/routers/studio_blocks.py`) is the only feature on this snapshot whose code exists but does not run; everything else listed as Shipped is reachable from the running app._
