# Onboarding Inventory (read-only audit, 2026-05-24)

## Verdict
**Robust journey exists** — two distinct paths converge into the app:
1. **Pre-auth Sandbox v2** (`/sandbox`) — a four-step, narrative-driven product tour for prospects who haven't signed up yet (`pages/SandboxV2.jsx`).
2. **Post-auth First Session** (`/app/first-session`) — a backend-enforced 3-question intake + 3-door pick + artefact-generation flow for newly-registered accounts (`routers/first_session.py` + `pages/FirstSession.jsx`).

A `FirstSessionGuard` short-circuits every `/app/*` route to `/app/first-session` until the new user completes or skips it (`frontend/src/App.js:133-165`). After completion, an undeclared-role user lands on `HomeUndeclared` for an inline NED/Exec/Dual role picker (`pages/home/HomeUndeclared.jsx`), then onwards to `Home1`/`Home2`.

---

## Existing surfaces

### 1. Signup / registration flow
| Surface | Citation |
|---|---|
| `/signup` route (public-only) | `frontend/src/App.js:254` — `<Route path="/signup" element={<PublicOnlyRoute allowSandbox><SignUp /></PublicOnlyRoute>} />` |
| `/signin` route (public-only) | `frontend/src/App.js:253` |
| `SignUp.jsx` page — email/password/name/tenant_name form, includes a "convert from sandbox" branch | `frontend/src/pages/SignUp.jsx:13-45` |
| `POST /api/auth/register` — creates account, password-hashes, provisions a **default context** named `"{first_name}'s Context"` if not provided, returns access+refresh tokens | `backend/routers/auth.py:57-91` |
| `POST /api/auth/login` — brute-force rate-limited (5 attempts → 15 min lock) | `backend/routers/auth.py:94-130` |
| `POST /api/sandbox/convert` — converts an anonymous sandbox account into a real account, optionally keeping the sandbox context as a frozen workspace | `backend/routers/sandbox.py` + `frontend/src/pages/SignUp.jsx:35-43` |
| `POST /api/auth/declare-role` — NED / Executive / Chair / Dual role declaration, called from `HomeUndeclared` and `first-session/intake` | `backend/routers/auth.py:223-235` |

**Email verification / magic link / OAuth**: NOT IMPLEMENTED. Manual email/password registration only (no `verify-email`, no `magic-link`, no `oauth` routes found).

**MFA**: TOTP via `setup/verify/disable` exists (`backend/routers/auth.py:240-271`) but is OPT-IN, not required during signup.

**Default context**: auto-provisioned on register via `provision_default_context()` in `core.py`. Name defaults to `"{first_name}'s Context"` unless caller passes `context_name`.

### 2. First-login experience
| Surface | Citation |
|---|---|
| `FirstSessionGuard` redirects unfinished users to `/app/first-session` | `frontend/src/App.js:147-165` |
| `FirstSession.jsx` 4-step state machine: **intake** (3 questions) → **door** (3 cards) → **working** (artefact polling) → **done** | `frontend/src/pages/FirstSession.jsx:1-15` |
| Backend state machine on `db.accounts.{id}.first_session` with status `not_started` / `in_progress` / `completed` / `skipped`; current_step `intake` / `door` / `working` / `done` | `backend/routers/first_session.py:6-15` |
| Intake questions: role (4 options), `primary_context_name`, `top_of_mind` (1 sentence, max 240 chars) | `backend/routers/first_session.py:68-93` |
| Three "doors" (artefact-generation options): `email` / `upload` / `solve` | `backend/routers/first_session.py:47-62` |
| Endpoints: `GET ""` `POST /start` `POST /intake` `POST /choose-door` `POST /complete` `POST /skip` | `backend/routers/first_session.py:205-369` |
| Every transition writes an audit row `first_session.{step}` | `backend/routers/first_session.py:17-18` |
| Skip path exists (`SkipLink` component) — user can bail and still reach the app | `frontend/src/pages/FirstSession.jsx:69-80` |

**No tour, no tooltips, no percent-complete bars, no spinners** — explicit decision documented in `FirstSession.jsx:13-14`: "Editorial register throughout: oxblood CTAs, cream serif heads."

### 3. Role-specific onboarding
| Role | Path | Citation |
|---|---|---|
| `undeclared` | Inline 3-button role picker on home | `frontend/src/pages/home/HomeUndeclared.jsx:1-40` |
| `executive` (default) | `Home1` (portfolio) → `Home2` (active-context home) | `frontend/src/pages/AppHome.jsx:1-23` |
| `ned` | Same dispatcher; NED-specific routes added: `/app/ned/inbox`, `/app/ned/meeting/:id`, `/app/ned/committee/...` | `frontend/src/App.js:273-275` |
| `dual` | Same dispatcher; both NED + Exec affordances on the dual home | (Legacy `HomeDual` deleted in Patch 17 — now goes through unified `Home2`) |
| `chair` | Same as executive | (declared via first_session; no chair-specific route) |

**No role-aware help text or starter prompts beyond the first-session intake question itself**.

### 4. Context onboarding
| Surface | Citation |
|---|---|
| New context creation auto-provisions a `context_object` (the "AKKI Brief") stub | `backend/routers/first_session.py:180-200` (sets `progress_state.onboarding_step: 1`) |
| Sandbox contexts come **pre-seeded** with `sandbox_metadata` containing an objective + sample briefing + sample signal | `backend/routers/sandbox.py:436-510` |
| Tutorial card endpoint for sandbox contexts (3 steps: "Read your first briefing" → "Ask AKKI one sharp question" → "Scan the signals") | `backend/routers/sandbox.py:498-509` |
| Tutorial dismiss flag persisted on context | `backend/routers/sandbox.py:509-535` |
| Real (non-sandbox) contexts: minimal seeding — just the empty `context_object` stub | `backend/routers/first_session.py:172-200` |

### 5. Empty-state handling
| Surface | Citation |
|---|---|
| `ListingShell` accepts an `emptyState` prop for declarative empty-states | `frontend/src/components/common/ListingShell.jsx:102, 236` |
| Cycle list empty state with editorial copy | `frontend/src/pages/cycle/CycleList.jsx:137` |
| Strategic Goals panel empty state | `frontend/src/components/monitor/StrategicGoalsPanel.jsx:105, 649` |
| Ask panel empty state | `frontend/src/components/ask/AskPanel.jsx:204` |
| Solva landing empty state | `frontend/src/components/solva/SolvaLanding.jsx:208` |
| Questions / WorkStudio / Reading view empty states | `frontend/src/pages/Questions.jsx:413`, `WorkStudio.jsx:686`, `ReadingView.jsx:369` |
| `PrepareSideRail` renders empty-state stubs for missing minutes | `frontend/src/components/prepare/PrepareSideRail.jsx:13` |

Every major surface has explicit empty-state copy; no blank-screen failures.

### 6. Help / docs in-app
| Surface | Citation |
|---|---|
| `/help` route renders `HelpFeatures.jsx` which fetches `AKKI_FEATURES_AND_FUNCTIONALITY.md` from `/api/help/features` (no auth) | `frontend/src/App.js:215` + `frontend/src/pages/HelpFeatures.jsx:1-32` |
| **Only one in-app link to `/help`** — in `HelpFeatures.jsx:71` (the page links to itself as breadcrumb). No top-bar link, no first-session link, no empty-state CTA points to `/help`. | grep result: `to="/help"` appears only in HelpFeatures.jsx |
| Markdown download link `/api/help/features.md` for offline reading | `frontend/src/pages/HelpFeatures.jsx:218` |

### 7. Onboarding-adjacent code
| Module | What it does | Citation |
|---|---|---|
| `routers/first_session.py` | The state machine + 6 endpoints | `backend/routers/first_session.py` |
| `pages/FirstSession.jsx` | 4-step UI shell + skip link | `frontend/src/pages/FirstSession.jsx` (681 lines) |
| `components/sandbox/v2/` | 9 files: `WelcomeStep`, `Step1SolvaWrapper`, `Step3StudioWrapper`, `Step4CycleSnapshot`, `StepReveal`, `ClosingStep`, `ProgressChrome`, `StepShell`, `tokens.js` | `frontend/src/components/sandbox/v2/` |
| `pages/SandboxV2.jsx` | Sandbox top-level reducer + step composer | `frontend/src/pages/SandboxV2.jsx:1-30` |
| `pages/admin/SandboxKPI.jsx` | Admin metrics for the sandbox funnel | `frontend/src/pages/admin/SandboxKPI.jsx` |
| `core.py:360` | `progress_state` default `{"onboarding_step": 0, "onboarding_completed": False}` on every context | `backend/core.py:360` |

**No third-party onboarding library** (no `pendo`, `intro.js`, `userguiding`, `react-joyride`, `shepherd` — grep returned 0 hits).

---

## Gaps vs a reasonable v1 onboarding journey

* **No email verification** — accounts go live immediately after `/auth/register`; trust signal absent.
* **No password-reset flow** — no `/auth/forgot-password` or `/auth/reset` endpoints in `backend/routers/auth.py`.
* **No OAuth / SSO** — Google/Microsoft sign-in not wired (despite Emergent-managed Google Auth being available as an integration option).
* **No team invitations** — first user creates a context; co-workers cannot be invited to it via UI (no `POST /api/contexts/{id}/invite` route surfaced).
* **No `/help` discoverability** — the help page exists but nothing during onboarding (or anywhere in the AppShell top-bar) links to it.
* **No tour after first-session completion** — Home1/Home2 don't carry a "try chat", "upload a document", "set up your team" checklist. The sandbox tutorial card pattern (`/api/sandbox/contexts/{id}/tutorial`) exists for sandbox contexts but is NOT reused for real new contexts.
* **No "what changed since you last logged in"** — no first-login-after-N-days re-engagement nudge.
* **No completion certificate / proof-of-first-value** — Trust Center / first artefact emitted by first-session is the closest thing.
* **No NED-specific onboarding** — NED inbox / meeting / committee routes exist but no guided "your first NED week" walkthrough.
* **First-session SKIP path = grandfathered forever** — a user who hits "Skip" never sees the intake again (line 152: `done = fs.status === "completed" || fs.status === "skipped"`). No re-prompt.

---

## Risks / observations

* **Mixed vocabulary**: `first_session`, `onboarding`, `tutorial`, `sandbox tutorial`, `welcome` all coexist in the codebase. A new contributor would have to read 5 files to understand which one is canonical for "the new-user journey".
* **Sandbox v2 ≠ First Session**: distinct features, distinct teams, distinct vocabularies. Sandbox is **pre-auth marketing/demo**; First Session is **post-auth product setup**. The transition between them is `POST /sandbox/convert` which optionally keeps the sandbox context.
* **Skip path is too easy**: a user who skips first-session lands on `HomeUndeclared` (still has to declare role) but then sees an empty Home with no contextual prompts to set things up. No nudge to come back to first-session.
* **`progress_state.onboarding_completed: false` on every context** (`core.py:360`) — this field exists, is initialised, but I see no UI that **reads** it. Looks like a leftover from an earlier onboarding scheme.
* **`grandfathered users`**: any account with a completed legacy `context_object` is auto-marked `first_session.status="skipped"` on `/auth/me` (per `App.js:144` comment). Means: existing users will NEVER see the current first-session intake, only new signups do.
* **Self-serve only via signup**: there's no admin-provisioning endpoint (`POST /api/admin/accounts/create`) that I can find — every user goes through `/signup` themselves. Production currently has 642 chats across multiple accounts so self-serve is working, but there's no "admin-creates-NED-account-on-behalf-of-board" path.
* **Sandbox tutorial pattern is reusable but unreused for real contexts**: `GET /api/sandbox/contexts/{id}/tutorial` returns a perfectly-shaped 3-step starter checklist for **sandbox** contexts. Real new contexts get an empty Home. Reusing this would close the biggest gap in v1 onboarding without new code.
