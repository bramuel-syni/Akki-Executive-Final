# A Implementation Log — J1-J4 Onboarding sprint

**Chunk:** A — J1-J4 Onboarding sprint (Step 1: inventory + spec, no code changes)
**Started:** 2026-05-25
**Spec contract (in-flight):** `/app/memory/AKKI_ONBOARDING_SPEC.md` v1.0 (this chunk creates it).
**Hold scope:** Inventory + Spec only — NO code changes until orchestrator dispatches build chunks.

---

## Pre-chunk hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-a` → commit at sprint start (local-only) | 2026-05-25T10:42Z |
| Mongo dump | `/app/backup/pre_a_20260525T104255Z/` (68 MB, 240 collections) | 2026-05-25T10:42:55Z |

---

## 1. J1-adjacent code inventory (on disk, 2026-05-25)

### 1.1 LIVE — already shipped, not dormant

The handoff summary slightly misrepresented the state. There IS a live, mounted, end-to-end onboarding flow on disk today — referred to in code as "First Session", not "J1". It is the post-auth, intake-driven, 4-step state machine that ships under `/app/first-session` and is guarded into every protected route via `FirstSessionGuard`.

| Path | Lines | Status | What it does |
| --- | --- | --- | --- |
| `backend/routers/first_session.py` | 382 | LIVE (mounted in `server.py:234`) | State machine `intake → door → working → done`; 6 endpoints `GET ""`, `POST /start`, `POST /intake`, `POST /choose-door`, `POST /complete`, `POST /skip`; writes audit per transition |
| `backend/routers/auth.py` | 278 | LIVE | `/auth/register` auto-provisions a default context via `provision_default_context()`; `/auth/login` rate-limits 5 attempts → 15-min lock; `/auth/me` auto-grandfathers users with completed legacy `context_object` into `first_session.status="skipped"` |
| `backend/routers/sandbox.py` | 1518 | LIVE (mounted) | Pre-auth Sandbox v2 flow — 4 questions → 60-sec narrative → disposable account + seeded sandbox context; `POST /convert` upgrades sandbox to a real account |
| `backend/core.py:367` | — | LIVE | `provision_default_context(account, name)` — single source of truth for fresh context creation; sets `progress_state: {"onboarding_step": 0, "onboarding_completed": False}` on every context |
| `frontend/src/pages/FirstSession.jsx` | 681 | LIVE (routed `/app/first-session`) | 4-step UI shell; editorial register (cream + oxblood + Georgia serif); skip link present |
| `frontend/src/pages/SignUp.jsx` | 216 | LIVE (routed `/signup`) | Email/password registration; includes sandbox-conversion branch |
| `frontend/src/pages/SignIn.jsx` | 184 | LIVE (routed `/signin`) | Email/password sign-in |
| `frontend/src/pages/SandboxV2.jsx` | 258 | LIVE (routed `/legacy-sandbox` + `/legacy-sandbox/resume`) | Sandbox v2 top-level reducer |
| `frontend/src/pages/NewWorkspace.jsx` | 306 | LIVE | Manual new-context creation surface |
| `frontend/src/pages/InviteAccept.jsx` | 121 | LIVE (routed `/invite/:token`) | Team-invite acceptance |
| `frontend/src/App.js:151-168` | — | LIVE | `FirstSessionGuard` short-circuits all `/app/*` to `/app/first-session` until `first_session.status ∈ {completed, skipped}` |

**Verdict on LIVE state:** the bones of J1 are already shipped. What's missing is **NOT** building from zero — it's connecting the existing First Session shell to (a) the T1-T5 reshaped surfaces, (b) Shield's first-byte routing on the very first document upload, and (c) the Trust Center introduction.

### 1.2 REVERTED — preserved at commit `b48ee23`, restoration recipe documented

`J1_PRESERVED_STATE.md` (in this same directory) documents J1 work that was reverted before T1-T5 began. The revert was deliberate — the UI it described would have needed rewriting after T1-T5 anyway. Restoration is a single `git cherry-pick b48ee23` + manual reconciliation of 5 surgical edits against the post-T5 `AppShell.jsx` + `TrustCenter.jsx`.

| Path | State | Restoration impact |
| --- | --- | --- |
| `backend/routers/onboarding_status.py` | DELETED at revert | Restorable from `b48ee23` |
| `backend/tests/test_j1_onboarding.py` | DELETED at revert | 9 wire-level tests with positive content assertions; never ran pre-revert (revert happened mid-build) |
| `backend/server.py` | reverted to `074a79c` | Surgical re-edit — restore the `import + include_router` lines |
| `frontend/src/App.js` | reverted to `074a79c` | Surgical re-edit — restore `/trust-center` alias route |
| `frontend/src/components/layout/AppShell.jsx` | reverted to `074a79c` | Surgical re-edit — re-add `BookOpen` import, `onbStatus` hook, banner JSX, tooltip wrappers |
| `frontend/src/pages/TrustCenter.jsx` | reverted to `074a79c` | Surgical re-edit — re-add `showIntroCard` + `acknowledgeIntro` + intro-card JSX |

**Schema fields the J1 restoration adds back to `db.accounts`:**

| Field | Type | Purpose |
| --- | --- | --- |
| `shield_v1_intro_acknowledged_at` | ISO 8601 string | One-time lock for re-intro banner |
| `shield_v1_intro_dismissals_count` | int (0-3) | Caps at MAX_DISMISSALS=3 |
| `shield_v1_intro_last_dismissed_at` | ISO 8601 string | Most recent dismissal timestamp |
| `trust_center_tooltip_dismissed_at` | ISO 8601 string | One-shot Trust Center tooltip |
| `help_tooltip_dismissed_at` | ISO 8601 string | One-shot Help tooltip |

**Endpoints the J1 restoration adds back:**

```
GET    /api/users/me/onboarding-status
POST   /api/users/me/onboarding-status/dismiss
POST   /api/users/me/onboarding-status/acknowledge
POST   /api/users/me/onboarding-status/tooltips/trust-center/dismiss
POST   /api/users/me/onboarding-status/tooltips/help/dismiss
```

### 1.3 ADJACENT — utilities the onboarding sprint reuses

| Path | Lines | What it does |
| --- | --- | --- |
| `backend/services/synisense/deidentifier.py` | — | The Shield de-identification layer that every upload + LLM call MUST route through |
| `backend/services/llm_router.py` | — | Central LLM router (forces Shield + audit) |
| `backend/services/clamav_service.py` | 283 | ClamAV scan integration (env-gated — clamd sidecar is STOPPED in this preview env) |
| `backend/routers/work_studio_render.py` | 287 | T4.1 DOCX/PDF/PPTX render endpoint — reusable for any onboarding artefact |
| `backend/scripts/seed_backlog_b_demo.py` | — | The DEMO_T5_BACKLOG seed pattern — reusable for an onboarding "Try the demo" branch |
| `frontend/src/components/layout/AppShell.jsx` | — | Post-T1-T5 top-bar surface where the banner + tooltips re-land |
| `frontend/src/pages/TrustCenter.jsx` | 776 | Post-(d) Trust Center page with the new methodology popover; J1 re-intro card re-lands here |

---

## 2. What's NOT on disk (must be designed)

Per `ONBOARDING_INVENTORY.md` §"Gaps vs a reasonable v1 onboarding journey":

| Gap | Status | Sprint impact |
| --- | --- | --- |
| Email verification | ABSENT | Stage 1 spec-decision |
| Password-reset flow | ABSENT | Stage 1 spec-decision |
| OAuth / SSO | ABSENT (Emergent-managed Google Auth available) | Stage 1 spec-decision |
| Team invitations from UI | ABSENT (`InviteAccept` page exists but no `POST /api/contexts/{id}/invite` invitation-generation route) | Stage 2 spec-decision |
| `/help` discoverability | Page exists; no top-bar link | Stage 5/6 spec-decision |
| Post-first-session tour | ABSENT | Stage 3-6 spec-decision |
| Re-engagement nudge after N days | ABSENT | Backlog (post-J4) |
| Re-prompt for skipped users | ABSENT | Stage 1 spec-decision |
| NED-specific onboarding walkthrough | ABSENT | Stage 2/3 spec-decision (NED is a distinct persona) |

---

## 3. Spec deliverable

Created `/app/memory/AKKI_ONBOARDING_SPEC.md` v1.0 — see that file for the canonical journey definition. This A_LOG records inventory + decisions; the spec records the contract.

## 4. Proposed J1-J4 build sequence

| Chunk | Stages covered | Effort | Why this order |
| --- | --- | --- | --- |
| **J1** | Stages 1-2 (Sign-up / Auth · Org / Context creation) | S-M | Lowest dependency. Restores `onboarding_status.py` + the 5 re-intro surfaces from commit `b48ee23`, surgically reconciled against post-T5 files. Adds the **Stage 2 NED/Exec role refinement step** to the existing intake. |
| **J2** | Stage 3 (First-cycle invitation OR "Try the demo") | M | Builds on T5 (Cycle Manager) + backlog-b (DEMO_T5_BACKLOG seed). Wires a "Start your first Cycle" CTA into First Session's `upload`/`solve` door alternatives. The "Try the demo" path reuses the seed. |
| **J3** | Stages 4-5 (First document upload · Trust Center introduction) | M | Builds on T3 (Add to Work Studio modal nested upload + G9 ClamAV toast) + (d) (Trust Center methodology). Wires the upload-from-first-session path through Shield's first-byte routing + surfaces a one-time Trust Center tooltip post-upload. |
| **J4** | Stage 6 (First Akki Chat / Solva session) | S | Wires First Session's `solve` door into the live Solva v2 endpoint with a context-aware starter prompt seeded from `intake.top_of_mind`. |

**Total estimated effort:** 1 build chunk per J (4 build chunks). Each chunk gets its own `Jx_LOG.md` with the same per-tier discipline used in T1-T5.

---

## 5. Reporting back

- Inventory of dormant J1 code: **`onboarding_status.py` + `test_j1_onboarding.py` reverted at commit b48ee23, recipe in `J1_PRESERVED_STATE.md`**. Other onboarding-adjacent code (`first_session.py`, `FirstSession.jsx`, `sandbox.py`, etc.) is LIVE, not dormant.
- Path to the spec: **`/app/memory/AKKI_ONBOARDING_SPEC.md` v1.0**
- Number of `GAP — proposed fill` entries: **see spec §6** (currently 8 gaps with proposed minimal fills)
- Proposed build sequence: **J1 (S-M) → J2 (M) → J3 (M) → J4 (S)**, mapping onto 6 stages

**Onboarding spec v1.0 ready. Awaiting orchestrator dispatch of build chunks.**
