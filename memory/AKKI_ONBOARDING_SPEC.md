# AKKI Onboarding Spec v1.0

**Status:** v1.1 — ratified by orchestrator on user authority — 2026-05-25. All 19 gap-fills (G13-G31) approved verbatim.
**Authored:** 2026-05-25.
**Boundary:** This document defines the J1-J4 onboarding sprint contract. T1-T5 + backlog-b + chunk (d) are CLOSED — see `/app/memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` for that contract.
**Scope discipline:** spec-verbatim + DOM-unconditional + import-survival + DOM-unconditional scope clarification (closeout §§5.1-5.7).

---

## 1. Source-of-truth statement

This spec is **derived**, not transcribed from a QA dossier. No user-supplied onboarding QA report exists at the level of the four 24-May surface QA reports. Inputs:

1. **Existing dormant J1 code on disk** — `routers/first_session.py` (LIVE), `pages/FirstSession.jsx` (LIVE), the reverted commit `b48ee23` (preserved with restoration recipe in `J1_PRESERVED_STATE.md`).
2. **Product needs implied by T1-T5 shipped surfaces** — a user must reach Document Journal / Cycle Manager / Work Studio / Monitor / Trust Center with valid context, role, and at least minimal data. T5 (Cycle Manager) explicitly requires a primary org name and a role; T4 (Work Studio compile) requires at least one source document.
3. **The Synisense Shield promise** — any sensitive data uploaded during onboarding routes through Shield (`deidentifier.deidentify()`) + the central `llm_router` from the first byte. Onboarding is the moment we EARN trust; the de-identification floor cannot wait.
4. **Existing inventory audit** — `/app/memory/sprints/ONBOARDING_INVENTORY.md` (2026-05-24, read-only). All gaps listed there are reflected in §6.

---

## 2. Personas

| Persona | Description | First-touch surface |
| --- | --- | --- |
| **Executive (Exec)** | CEO, CFO, COO, or equivalent operating exec. Default persona — opts for breadth over governance specificity. | Standard 4-step First Session. Stage 2 emits an `executive_personal` context. |
| **Non-Executive Director (NED)** | Independent board member. Reads board packs, attends meetings, contributes to cycle compilations. Privacy-walled from exec data by default. | Standard 4-step First Session with the NED door surfaced first in Stage 6. Stage 2 emits an `ned_personal` context. |
| **Chair** | Board chair (NED-elected role). Treated as NED for context-provisioning purposes; only Stage 6 starter copy differs. | NED path. |
| **Dual** | An individual who sits both as an Executive at one org AND as a NED at another. Stage 2 prompts for the **primary** context name first; the other context is added later via the existing context switcher. | Stage 2 emits whichever context-type the user picks as primary. |
| **Admin** | Org-level admin (not an end user themselves) — invites the Exco, manages billing, owns the audit-export entitlement. Out of scope for J1-J4 v1.0; bumped to backlog. | (Future) Stage 7 admin onboarding. |

**No public / anonymous onboarding** — all roads pass through `/signup` or `/sandbox` (which auto-creates a disposable account). Onboarding always operates on an authenticated subject.

---

## 3. Six-stage journey

Sequenced strictly. A user is on exactly one stage at any moment. Skipping a stage is allowed only where explicitly noted.

### Stage 1 — Sign-up / Authentication

**Goal:** an authenticated session backed by a real `accounts` row with hashed password (or SSO) and a fresh access+refresh token pair.

**Entry point:** `/signup` (or `/signin` for existing accounts). Sandbox conversion (`/legacy-sandbox` → `POST /api/sandbox/convert`) is an alternative entry.

**Steps (verbatim derivable from current code):**
1. User lands on `/signup` (`frontend/src/pages/SignUp.jsx`).
2. Form fields: email, password, name, optional tenant_name. (G14 — see §6.)
3. Submit → `POST /api/auth/register` (`backend/routers/auth.py:57`).
4. Server creates `accounts` row with `declared_role: "undeclared"`, password-hashes via bcrypt, auto-provisions a default context via `provision_default_context(account_doc, context_name)`.
5. Server returns `{account, contexts: [...], access_token}`. Refresh token set via cookie.
6. Client redirects to `/app` → `FirstSessionGuard` immediately punts to `/app/first-session`.

**Acceptance:**
- New row in `db.accounts`, `db.contexts`, `db.memberships`.
- HTTP 200 response with valid JWT.
- `FirstSessionGuard` resolves `first_session.status === "not_started"` and redirects to `/app/first-session`.

**Edge cases / errors:**
- Email already registered → 409 Conflict with verbatim message *"Email already registered"* (already shipped).
- Login failure → 5 attempts then 15-minute lockout per `email` (already shipped, `auth.py:104`).
- Password reset → **NOT IMPLEMENTED** — gap G15.
- Email verification → **NOT IMPLEMENTED** — gap G16.
- OAuth / SSO → **NOT IMPLEMENTED** — gap G17 (Emergent-managed Google Auth available as integration).

**Guardrail touchpoints:**
- bcrypt password hashing via `core.hash_password`.
- Rate-limit on `login_attempts` collection.
- Audit row: `auth.register` (currently not emitted — gap G19) and `auth.login.success` / `auth.login.failure` (already shipped via existing audit chain).

**Status:** **Existing live** for password auth; **New work** for verification + reset + OAuth gaps (G15-G17, deferred from J1 v1.0 unless PO upgrades).

---

### Stage 2 — Org / Context creation + Role declaration

**Goal:** the new account has a single named context with a declared role (Exec / NED / Chair / Dual) and a one-sentence "top of mind" hint for personalisation.

**Entry point:** `/app/first-session` (auto-redirected from Stage 1).

**Steps (verbatim derivable from `routers/first_session.py:68-93`):**
1. `GET /api/me/first-session` returns the `INTAKE_QUESTIONS` catalogue + current state.
2. Three questions, sequential, single-column editorial layout:
   - **Q1**: *"Which best describes your role?"* — single-select from `{executive, ned, chair, dual}`.
   - **Q2**: *"What's the primary board or company you sit on?"* — free text, max 80 chars.
   - **Q3**: *"What's on your mind for the next meeting? One sentence."* — free text, max 240 chars.
3. Submit → `POST /api/me/first-session/intake` writes:
   - A `context_objects` row v1 with `step: 1, completed: false` and the 3 answers in `answers.first_session`.
   - The context row is renamed to the Q2 answer (`progress_state.first_session_intake_captured: true`).
   - `accounts.declared_role` is set per the role-mapping (chair → ned, dual → dual, etc.).
4. Audit row: `first_session.intake`.
5. State transitions to `current_step: "door"`.

**Acceptance:**
- `context_objects` row exists with `version: 1, completed: false` and intake answers.
- `contexts.{id}.name` matches Q2.
- `accounts.declared_role` is one of `{executive, ned, dual}`.
- `first_session.intake` audit row written.

**Edge cases / errors:**
- Invalid role → 400 with *"Invalid role."* (literal).
- All three fields are required — the front-end "Next" button is disabled until they're non-empty (DOM-unconditional validation banner per closeout §5.1).
- User hits "Skip first session" link → `POST /api/me/first-session/skip` → status `skipped`, lands on `HomeUndeclared` (existing).

**Guardrail touchpoints:**
- Q3 ("top of mind") is free text — **routes through `deidentifier.deidentify()` before any storage** if it includes named people / numbers. (G18 — needs confirmation; current code does NOT de-identify intake answers because they go straight to `context_objects.answers`. This is a gap.)
- Audit chain: `first_session.intake` action with `resource_type: account`.

**Status:** **Existing live** for the 3-question intake; **New work** for the Shield de-identification of intake answers (G18) and the NED-vs-Exec context-type emission (currently always `executive_personal` — gap G20).

---

### Stage 3 — First Cycle invitation (or "Try the demo")

**Goal:** the user lands in the Cycle Manager with either a freshly-created cycle of their own OR a one-click pre-seeded demo cycle (`DEMO_T5_BACKLOG`).

**Entry point:** After Stage 2 intake completes, the First Session "door" card surface (`frontend/src/pages/FirstSession.jsx`).

**Steps (proposed — refines the existing 3-door pattern):**
1. The "door" step currently offers `email | upload | solve` (`routers/first_session.py:47`).
2. **Replace with a 4-door layout** (gap G21):
   - **Door A — "Create your first cycle"** → routes to the T5 Cycle Setup Wizard (`/app/cycle?wizard=1`) with `?intake_seed=1` so the wizard pre-fills `cycleName` from the Q2 answer.
   - **Door B — "Upload a document"** → routes to the Document Journal upload sheet (the T3.4 flow).
   - **Door C — "Ask Akki something"** → routes to the home chat surface with the Q3 answer pre-typed.
   - **Door D — "Try the demo"** → routes to `/app/cycle` AND auto-attaches the user's account to the `DEMO_T5_BACKLOG` rows by stamping `seed_marker_visible_for: [account_id]` on those rows. (Idempotent — same pattern as backlog-b.)
3. Whichever door the user picks, `POST /api/me/first-session/choose-door` flips `current_step` to `working` (for email/upload/solve) or `done` (for solve, per existing logic).
4. **For doors A and D**, the user is considered onboarded to Stage 3 once the cycle is reachable; `first_session` transitions to `completed` with `door_taken: "cycle"` or `door_taken: "demo"` (gap G22 — new door values).

**Acceptance:**
- For Door A: a `cycles` row exists owned by the user, in their primary context.
- For Door D: the user can navigate to `/app/cycle/demo-t5backlog-cycle-001` and see the seeded compilation chips.
- Audit row: `first_session.door_<value>` (already shipped pattern).

**Edge cases / errors:**
- User backs out of Cycle Setup Wizard mid-flow → cycle is NOT created; First Session state stays at `current_step: door` (G4 validation applies; "Next" disabled until valid — already shipped).
- Demo door fails (seed rows missing) → fallback toast *"Demo unavailable right now. Try uploading a document instead."* (verbatim; G23).

**Guardrail touchpoints:**
- Cycle Setup Wizard's intake_seed path must NOT bypass G4/G5 validation (the email regex + dupe warning apply equally).
- Demo door visibility-stamp is auditable: `audit_log` action `onboarding.demo_attached` with `resource_type: cycle` and `target_id: demo-t5backlog-cycle-001`.

**Status:** **New work** — current first-session door is `email|upload|solve`; the new 4-door layout (G21) + demo-attach mechanic (G22) are not on disk.

---

### Stage 4 — First document upload (Shield from the first byte)

**Goal:** the user has uploaded at least one document, and the document was scanned by ClamAV + de-identified by Shield before any LLM read.

**Entry point:** Either Door B from Stage 3 or any post-onboarding upload sheet (Document Journal, Compile modal nested upload, Add to Work Studio modal).

**Steps:**
1. User picks a file via the Document Journal upload sheet (the T3 / G9 surface).
2. Browser POSTs to `/api/contexts/{cid}/documents/upload` (existing endpoint).
3. **Server side, in order:**
   a. ClamAV scan via `services/clamav_service.scan()` — reject + verbatim G9 toast *"We couldn't upload that file. It was rejected by virus scanning."* if INFECTED.
   b. Text extraction (pdf2text / docx / xlsx / pptx) via existing pipelines.
   c. **Shield first-pass de-identification** via `deidentifier.deidentify(text)` — emits `synisense_audit_log.de_id_summary` for this document with the standard 5-anchor methodology (closeout §5.7 + `TRUST_CENTER_METHODOLOGY.md`).
   d. Document stored with the SHIELDED text body; original bytes encrypted at rest.
   e. `audit_log.document.uploaded` written, sensitivity band assigned.
4. User sees the document card in Document Journal with the standard sensitivity badge.

**Acceptance:**
- `documents` row exists.
- `synisense_audit_log.de_id_summary` row exists with non-zero counter (assuming the doc has ANY identifiers).
- Trust Center / `/api/trust-center/sessions/<sid>/promise` shows the upload-derived counter against the user's first session.

**Edge cases / errors:**
- ClamAV unreachable → graceful 503 with toast *"Upload failed. Please try again."* (verbatim G9 fallback).
- Empty document (no extractable text) → 400 with *"That file doesn't have any text we can read. Please upload a different file."* (verbatim G24).
- File too large (>50 MB) → 413 with *"That file is larger than 50 MB. Please split it or upload a smaller version."* (verbatim G25).

**Guardrail touchpoints:**
- **G9 verbatim** ClamAV reject toast.
- **Shield first-byte routing** — `llm_router` MUST refuse to call any model on un-de-identified text. Onboarding documents are NOT exempt.
- Audit chain: every step writes one entry; chain HMAC remains valid.

**Status:** **Existing live** for upload + ClamAV + Shield + audit (T3.4 + G9); **New work** is the post-upload Trust Center prompt (Stage 5).

---

### Stage 5 — Trust Center introduction

**Goal:** the user has seen the Trust Center surface at least once, with their own first-document's Shield counters live, and understands the methodology (chunk (d)).

**Entry point:** Triggered automatically on the first navigation away from Stage 4 if the user has at least one uploaded document AND has not previously visited `/app/trust-center`. The trigger is a one-shot Trust Center tooltip on the top-bar (gap G26 — currently dormant from `b48ee23`).

**Steps:**
1. After Stage 4 completes, on the next route change the AppShell top-bar renders a one-shot tooltip pointing at the Trust Center icon (re-enable from `b48ee23`).
2. Tooltip copy: *"This is your Trust Center. We've recorded what Shield touched on your first upload — take a look."* (verbatim G27.)
3. User clicks → `/app/trust-center` → the page renders, with the user's first session selected by default (already shipped if there's exactly one).
4. The new (d) info popover and per-turn note are present (already shipped).
5. Tooltip auto-dismisses on click OR after the user closes it; `POST /api/users/me/onboarding-status/tooltips/trust-center/dismiss` flips `accounts.trust_center_tooltip_dismissed_at` to now-ISO.

**Acceptance:**
- `accounts.trust_center_tooltip_dismissed_at` is set.
- Trust Center page renders with the user's session preselected.
- The chunk-(d) `tc-deidsummary-info-button` testid is reachable from the SessionDetail panel (DOM-unconditional scope per closeout §5.7).

**Edge cases / errors:**
- User has uploaded 0 documents and tries to navigate to Trust Center directly → empty-state copy: *"No sessions yet. Upload a document or chat with Akki to begin."* (verbatim G28).
- The tooltip MUST NOT re-appear after `dismissed_at` is set (per `J1_PRESERVED_STATE.md`).

**Guardrail touchpoints:**
- Re-uses the chunk (d) UI methodology + `TRUST_CENTER_METHODOLOGY.md` — no behaviour change.
- Re-enables one of the 5 schema fields preserved at `b48ee23` (`accounts.trust_center_tooltip_dismissed_at`).

**Status:** **New work** (restoration from `b48ee23` + reconciliation against post-T5 `AppShell.jsx`); chunk (d) ships the underlying UI methodology.

---

### Stage 6 — First Akki Chat / Solva session

**Goal:** the user has had at least one round-trip with Akki — either a chat reply or a Solva Wave 1 question — seeded by their Stage 2 `top_of_mind` answer.

**Entry point:** Either Door C from Stage 3 (immediate) OR the home chat surface accessible from `/app` after Stage 5 completes.

**Steps:**
1. The home chat surface receives a `?starter=<intake_top_of_mind>` query param from First Session's Door C OR auto-populates from `accounts.first_session.intake.top_of_mind` on home mount.
2. User adjusts (or accepts) the starter prompt and submits.
3. Backend routes through `llm_router.invoke()` (Shield-routed) → returns answer.
4. The answer renders in chat with the standard Shield audit-anchor pattern.
5. After the FIRST answer renders, the AppShell top-bar's Help tooltip surfaces (re-enable from `b48ee23`).
6. Tooltip copy: *"Tap Help any time. Akki has a built-in tour of every screen."* (verbatim G29.)
7. Tooltip dismiss → `POST /api/users/me/onboarding-status/tooltips/help/dismiss`.

**Acceptance:**
- A `chats` row exists for the user.
- A `synisense_audit_log` row was written by the `llm_router` call.
- `accounts.help_tooltip_dismissed_at` is set after the tooltip dismiss.

**Edge cases / errors:**
- LLM call fails → standard failure toast (already shipped).
- User skips Stage 6 → no enforced re-entry; the Help tooltip can re-appear only if `dismissed_at` is null AND user has had at least one chat (idempotent).

**Guardrail touchpoints:**
- `llm_router` + `deidentifier` — first chat goes through Shield like any other.
- Audit row: `chat.first_message` action.

**Status:** **Existing live** for the chat surface; **New work** is the starter-prompt seeding (G30) and the Help tooltip restoration (G31).

---

## 4. J1-J4 mapping onto the 6 stages

| Chunk | Stages | Sprint deliverable |
| --- | --- | --- |
| **J1** | 1-2 | Restore `b48ee23` Shield re-intro banner + Trust Center intro card; reconcile against post-T5 `AppShell.jsx` + `TrustCenter.jsx`; surface 5 `accounts.*` fields; add `auth.register` audit emit (G19); plus the Stage 2 Shield de-identification of intake answers (G18) and NED-vs-Exec context-type emission (G20) |
| **J2** | 3 | Replace 3-door first-session step with 4-door layout (G21); add the cycle-setup intake_seed pre-fill; add demo-attach mechanic (G22); add door fallback toast (G23) |
| **J3** | 4-5 | Re-confirm Stage 4 wiring (already live); restore Trust Center one-shot tooltip from `b48ee23` (G26-G28); add empty-state Trust Center copy (G28); validate Shield first-byte routing via integration test |
| **J4** | 6 | Add chat starter-prompt seeding from `intake.top_of_mind` (G30); restore Help tooltip from `b48ee23` (G29, G31); add `chat.first_message` audit action |

**Per chunk:** same per-tier discipline as T1-T5 — pre-tier git tag, mongodump, per-chunk LOG.md, anti-false-green pre-fix test runs, full pytest after fix, e1_tester dispatch by orchestrator.

---

## 5. Cross-cutting guardrails (binding for J1-J4)

1. **Shield from the first byte.** No LLM call escapes Shield. No document is stored unscanned. (Already binding for T1-T5; J1-J4 inherits.)
2. **Audit-chain integrity.** Every state transition writes one audit row. Chain HMAC must remain valid.
3. **DOM-unconditional rendering rule** (closeout §5.1) — structural sections within the FirstSession shell emit DOM regardless of inner data; only inner content varies.
4. **DOM-unconditional scope clarification** (closeout §5.7) — onboarding affordances (banner, tooltips) co-locate with the data they describe (Trust Center icon, Help icon). They do NOT live at page-chrome level just to be "ubiquitous".
5. **Import-survival rule** (closeout §5.6) — every JSX identifier introduced by J1-J4 must be in the import block at file head.
6. **Verbatim-spec-copy invariant** (closeout §5.3) — every toast, button label, tooltip copy, validation message in this spec is treated as a literal. Re-wording (even slightly) is treated as a regression. Test assertions use `assert "<literal>" in src`.
7. **No guardrail file changes** (`services/synisense/*`, `services/llm_router.py`, `services/clamav_service.py`, `services/trust_center.py`, `routers/trust_center.py`). J1-J4 reads Shield/Trust-Center but never writes to those modules.

---

## 6. Open gaps for PO ratification (G13-G31)

Numbered to continue the G1-G12 sequence from the product spec. Each gap has a proposed minimal fill that the PO can `approve / amend / reject` quickly.

| # | Gap | Surface | Proposed fill (minimal) | PO decision |
| --- | --- | --- | --- | --- |
| **G13** | Single tenant_name vs personal_context distinction | Stage 1 SignUp form | Keep single `tenant_name` field as-is (currently used to override the default `"{first_name}'s Context"`). Don't ask org-name twice. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G14** | Should SignUp require a non-empty tenant_name? | Stage 1 SignUp form | Keep optional — falls back to `"{first_name}'s Context"`. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G15** | Password-reset flow | Stage 1 | Defer to J1 v1.1 (out of scope for J1). Add `POST /auth/forgot-password` + magic-link email later. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G16** | Email verification before activation | Stage 1 | Defer to J1 v1.1. (Currently registration is immediately active.) | Ratified by orchestrator on user authority — 2026-05-25 |
| **G17** | OAuth / SSO | Stage 1 | Defer to J1 v1.1. Emergent-managed Google Auth available when added. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G18** | Shield de-identification of `top_of_mind` intake answer | Stage 2 | Route the Q3 answer through `deidentifier.deidentify()` before writing to `context_objects.answers`. One-line server-side change in `routers/first_session.py:248`. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G19** | `auth.register` audit row | Stage 1 | Emit `audit_log` action `auth.register` with `resource_type: account`, `target_id: new_account_id`, `metadata: {email_domain, tenant_name}`. Backfill not required. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G20** | Context type emission per role | Stage 2 | `executive` / `dual` → `executive_personal`; `ned` / `chair` → `ned_personal`. Currently always `executive_personal` (`core.py:374`). | Ratified by orchestrator on user authority — 2026-05-25 |
| **G21** | First-session door layout 3→4 doors | Stage 3 | Add Door A (`cycle`) and Door D (`demo`); keep existing `upload` + `solve` doors; retire `email` door (rarely used per audit). | Ratified by orchestrator on user authority — 2026-05-25 |
| **G22** | Demo-attach mechanic | Stage 3 | Add `seed_marker_visible_for: [account_id]` field on the 6 backlog-b seed rows; filter Cycle Manager / Document Journal / Work Studio listings to include rows where `seed_marker_visible_for` contains the current account_id. Idempotent. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G23** | Demo door fallback toast | Stage 3 | Verbatim *"Demo unavailable right now. Try uploading a document instead."* | Ratified by orchestrator on user authority — 2026-05-25 |
| **G24** | Empty-document upload error | Stage 4 | Verbatim *"That file doesn't have any text we can read. Please upload a different file."* | Ratified by orchestrator on user authority — 2026-05-25 |
| **G25** | Oversized-file upload error | Stage 4 | Verbatim *"That file is larger than 50 MB. Please split it or upload a smaller version."* | Ratified by orchestrator on user authority — 2026-05-25 |
| **G26** | Trust Center one-shot tooltip restoration | Stage 5 | Cherry-pick `b48ee23` reconciled against post-T5 `AppShell.jsx`. Surface = top-bar Trust Center icon. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G27** | Trust Center tooltip copy | Stage 5 | Verbatim *"This is your Trust Center. We've recorded what Shield touched on your first upload — take a look."* | Ratified by orchestrator on user authority — 2026-05-25 |
| **G28** | Trust Center empty-state copy | Stage 5 | Verbatim *"No sessions yet. Upload a document or chat with Akki to begin."* | Ratified by orchestrator on user authority — 2026-05-25 |
| **G29** | Help tooltip copy | Stage 6 | Verbatim *"Tap Help any time. Akki has a built-in tour of every screen."* | Ratified by orchestrator on user authority — 2026-05-25 |
| **G30** | Chat starter-prompt seeding | Stage 6 | Read `accounts.first_session.intake.top_of_mind` on home mount; pre-populate the chat composer. User can edit before submit. | Ratified by orchestrator on user authority — 2026-05-25 |
| **G31** | Help tooltip restoration | Stage 6 | Cherry-pick `b48ee23` Help tooltip JSX reconciled against post-T5 `AppShell.jsx`. | Ratified by orchestrator on user authority — 2026-05-25 |

---

## 7. Out of scope for v1.0

| Item | Why deferred | Backlog target |
| --- | --- | --- |
| Admin onboarding (org-level admins inviting an Exco) | Distinct persona, distinct surface; doesn't block end-user J1-J4. | J5 (future) |
| Re-engagement nudge after N days | UX research not done. | Backlog |
| NED-specific guided walkthrough | NED inbox / committee surfaces exist; tour design not specified by user. | J5 |
| Skip-path re-prompt | Once a user skips, they don't see the intake again. PO has not asked for a re-prompt. | Backlog |
| Team invitations (`POST /api/contexts/{id}/invite`) | InviteAccept page exists but invitation-generation route doesn't. | J5 |
| Email verification, password reset, OAuth | Deferred to J1 v1.1 (G15-G17). | J1.1 (future) |
| Sandbox-to-real-account conversion polish | The convert flow exists; polish (welcome email, retention nudge) is out of scope. | Backlog |

---

## 8. Spec versioning + change-control

- **v1.0** (2026-05-25): initial derived spec, 19 gap-fills G13-G31 pending PO ratification.
- **v1.1** (2026-05-25): orchestrator ratified G13-G31 on user authority. All 19 gap-fills approved verbatim. PO decision burden delegated by user.
- Any spec change after PO ratification is a v1.x bump and gets a one-line entry in `A_LOG.md`.
- Mid-build amendments require PO sign-off in chat; the spec file is updated immediately and the chunk LOG records the amendment in its run-results section.

---

## 9. Final orchestrator handoff

**Hold for orchestrator dispatch of build chunks.**

Once PO ratifies the gap-fills (G13-G31), the dispatch order is:
1. J1 → Stages 1-2 (S-M effort)
2. J2 → Stage 3 (M)
3. J3 → Stages 4-5 (M)
4. J4 → Stage 6 (S)

Each chunk gets its own LOG, git tag (`v-pre-J1`, `v-pre-J2`, etc.), and mongodump per the T1-T5 discipline.

**Spec status: v1.0 DRAFT, awaiting PO sign-off on G13-G31.**
