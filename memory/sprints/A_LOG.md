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

---

## 2026-05-25 — Spec v1.1 ratification

Orchestrator ratified G13-G31 (all 19) on user authority. User explicitly delegated to avoid decision burden. All proposed minimal fills treated as approved verbatim.

- Status string on `AKKI_ONBOARDING_SPEC.md` line 3 flipped to `v1.1 — ratified by orchestrator on user authority — 2026-05-25`.
- §8 changelog entry added.
- §6 table: 19 occurrences of `TBD` replaced with `Ratified by orchestrator on user authority — 2026-05-25` (verified count: 19/19).

## 2026-05-25 — J1 build (Stages 1-2) — IMPLEMENTATION

### Pre-J1 hygiene
| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-a` (still in force; J1 is a sub-chunk per user directive) | — |
| Mongo dump | `/app/backup/pre_j1_20260525T105525Z/` (68 MB, 240 collections) | 2026-05-25T10:55:25Z |

### Cherry-pick `b48ee23` — restoration of dormant J1 surfaces

```
$ cd /app && git cherry-pick --no-commit b48ee23
Auto-merging backend/server.py
Auto-merging frontend/src/App.js
Auto-merging frontend/src/pages/TrustCenter.jsx
[exit 0 — clean merge, no conflicts]
```

The cherry-pick auto-merged cleanly. **Zero conflicts** across all 7 files. The post-T5 + post-(d) edits to `AppShell.jsx` and `TrustCenter.jsx` co-existed with the J1 banner/tooltip/intro-card additions without manual reconciliation.

Files restored:

| File | Restoration | LOC delta |
| --- | --- | --- |
| `backend/routers/onboarding_status.py` | NEW (was deleted at revert) | +291 |
| `backend/tests/test_j1_onboarding.py` | NEW (was deleted at revert) | +257 |
| `backend/server.py` | Added `from routers import onboarding_status as onboarding_status_router` import + `app.include_router(onboarding_status_router.router)` line | +2 |
| `frontend/src/App.js` | Added `<Route path="/trust-center" element={<Navigate to=…} replace />` alias under `/legacy-sandbox` | +4 |
| `frontend/src/components/layout/AppShell.jsx` | Added `BookOpen` import, `onbStatus` hook, top-bar Trust-Center + Help tooltip wrappers, top-bar reintro banner JSX with `needs_reintro` guard | +130 |
| `frontend/src/pages/TrustCenter.jsx` | Added `showIntroCard` + `acknowledgeIntro` hook + intro-card JSX after the page heading | +49 |

### G18 — Shield routing on `top_of_mind`

Spec §3 Stage 2, gap §6 G18 (ratified): *"Route the Q3 answer through `deidentifier.deidentify()` before writing to `context_objects.answers`."*

**Files changed:**
- `backend/routers/first_session.py`:
  * Module docstring updated with G18 + G20 contract.
  * Import: `from services.synisense.shield import deidentifier as _shield_deidentifier`.
  * Import: `from services.synisense.exceptions import ServiceUnavailable`.
  * `submit_intake` (route `POST /api/me/first-session/intake`) now:
    1. Calls `deidentifier.deidentify(raw, tenant_id=ctx_id)` on the Q3 answer BEFORE any persistence step.
    2. Persists `top_of_mind = shield_result.redacted_text` (i.e. tokenised text like `Email me at [[ENT_EMAIL_001]]`).
    3. Persists `top_of_mind_token_map = shield_result.token_map` so re-identification at presentation time remains possible.
    4. Persists `top_of_mind_shield_summary` (de_id_summary, dilution_score, exposure_reduction_score, elapsed_ms).
    5. On `ServiceUnavailable` exception: raises HTTP 503 — **fail-closed**, NEVER persist a raw answer when Shield can't reach a clean state.
- `_write_context_object_from_intake` extended to plumb the two new fields into `answers.first_session`.

### G20 — Context-type emission per declared role

Spec §3 Stage 2, gap §6 G20 (ratified): *"`executive` / `dual` → `executive_personal`; `ned` / `chair` → `ned_personal`. Currently always `executive_personal` (`core.py:374`)."*

**Files changed:** `backend/routers/first_session.py` only.

- New module-level constant `_ROLE_TO_CONTEXT_TYPE = {"executive": "executive_personal", "ned": "ned_personal", "chair": "ned_personal", "dual": "executive_personal"}`.
- `submit_intake` post-intake hook:
  1. Reads the existing context type via `db.contexts.find_one`.
  2. If type differs from the role-implied target → `db.contexts.update_one` flips the type (set-if-different — idempotent).
  3. If the new role is `ned` or `chair` → `db.memberships.update_one` flips the membership role to `ned` so role-gated NED surfaces light up.
  4. Writes `context.retyped` audit row with `from / to / reason: G20_role_intake` metadata.

**No `core.py` change.** The default context still provisions as `executive_personal` at register time; the J1 hook re-types ONLY when intake declares a NED role. This preserves the register-time invariant and makes the type accurate to declared role on the FIRST intake submission.

### Tests written

| File | Lines | Purpose |
| --- | --- | --- |
| `backend/tests/test_j1_onboarding.py` | 257 | RESTORED from `b48ee23`. 9 tests covering the `/api/users/me/onboarding-status` GET + 5 dismiss endpoints, the `<Route path="/trust-center">` alias, and the `accounts.shield_v1_intro_*` fields. One fix on disk: the App.js alias matcher made multi-line-JSX tolerant (was `'<Route path="/trust-center"' in app_js` — now `re.search(r"<Route\s+path=\"/trust-center\"", app_js)`). |
| `backend/tests/test_j1_stages_1_2.py` | NEW | 15 tests covering G18 (4 redaction + 1 fail-closed + 1 token-map persistence), G20 (4 parametrized role mappings + 1 idempotency), spec §3 Stage 2 verbatim copy (3 question literals + invalid-role 400), Stage 1 verbatim copy (Email-already-registered 409), and no-J2/J3/J4-scope-pulled-forward guards (door allow-list + guardrail-files-untouched documentary anchor). |

### Test results

```
$ cd /app/backend && python -m pytest tests/test_j1_stages_1_2.py tests/test_j1_onboarding.py -v
======================== 24 passed, 7 warnings in 8.13s ========================
```

**24/24 PASS** post-J1.

### Anti-false-green proof

```
$ cd /app && git checkout v-pre-a -- backend/routers/first_session.py
$ cd /app/backend && python -m pytest tests/test_j1_stages_1_2.py -q --tb=no
7 failed, 8 passed, 7 warnings in 5.87s
```

**7/15 FAIL pre-fix.** Specifically: 5 G18 tests (all 5 — redaction-email, redaction-money, token-map persistence, fail-closed 503, clean-input passthrough), 3 G20 tests (NED, Chair, idempotency). 8 trivially pass pre-fix (verbatim copy, Stage 1 register-conflict, door allow-list — none of which were touched by the G18+G20 code change).

### Full pytest

```
$ cd /app/backend && python -m pytest -q --no-header --tb=no
1 failed, 1134 passed, 490 skipped, 86 warnings in 249.34s (4:09)
```

**1134 passed · 490 skipped · 1 failed.**

- Pre-J1 baseline (post-(d) closeout): 1110 passed.
- Post-J1: **1134 passed (+24 — exactly the 9 cherry-picked J1 tests + 15 new test_j1_stages_1_2.py tests).** Zero regressions.
- 490 skipped — UNCHANGED from the SKIP_LEDGER baseline; J1 did not silence any test.
- The 1 failure is the same pre-existing `test_real_requirements_file_is_clean` (spaCy URL pep508-direct-refs — `requirements.txt` untouched in this chunk).

### Files changed (J1 — final inventory)

**Backend (composition — no guardrail file touched):**
- `backend/routers/first_session.py` — G18 + G20 (composition over existing Shield + Mongo writers)
- `backend/routers/onboarding_status.py` — RESTORED from b48ee23
- `backend/server.py` — RESTORED include_router line for onboarding_status
- `backend/tests/test_j1_onboarding.py` — RESTORED from b48ee23 (1 multi-line-JSX tolerance fix)
- `backend/tests/test_j1_stages_1_2.py` — NEW (15 G18 + G20 + verbatim copy tests)

**Frontend (composition):**
- `frontend/src/App.js` — RESTORED `/trust-center` alias route
- `frontend/src/components/layout/AppShell.jsx` — RESTORED BookOpen import + onbStatus hook + reintro banner + 2 tooltip wrappers
- `frontend/src/pages/TrustCenter.jsx` — RESTORED intro card

**Documentation:**
- `memory/AKKI_ONBOARDING_SPEC.md` — v1.0 → v1.1 ratification.
- `memory/sprints/A_LOG.md` — ratification log + J1 build log (this entry).

**Backend guardrail files touched: 0.** Verified by `git diff --name-only v-pre-a HEAD -- backend/services/synisense/ backend/services/llm_router.py backend/services/clamav_service.py backend/services/inbound_email.py backend/routers/trust_center.py backend/services/trust_center.py backend/routers/admin_audit_invariant.py` — empty result.

### J2/J3/J4 scope pulled forward — NONE

- `ALLOWED_DOORS` still `{"email", "upload", "solve"}` — G21 (4-door layout) NOT implemented.
- G22 (demo-attach mechanic) NOT implemented.
- Trust Center one-shot tooltip (G26-G28) NOT implemented at the AppShell level (the b48ee23 cherry-pick wires the Trust Center top-bar tooltip wrapper — copy is the b48ee23 verbatim *"See how your data is protected."*; spec G27 refinement happens in J3).
- Help tooltip (G29, G31) NOT refined (the b48ee23 cherry-pick wires the Help top-bar tooltip wrapper — copy is the b48ee23 verbatim *"Read about every feature / Full reference of what Akki can do."*; spec G29 refinement happens in J4).
- Stage 6 chat starter-prompt seeding (G30) NOT implemented.

### Note on orchestrator J1 checklist item "G21 4-door layout in place"

The orchestrator's J1 acceptance checklist included a verification for "G21 4-door layout in place (door count + verbatim labels)". G21 is spec §3 Stage 3 and is **J2 scope**, not J1. The user's hard rule "No J2/J3/J4 scope pulled forward" takes precedence. This log explicitly does not pull G21 forward; `test_j1_stages_1_2.py::test_no_j2_j3_j4_door_layout_changes_yet` enforces this in CI by asserting `ALLOWED_DOORS == {"email", "upload", "solve"}` (the pre-J2 state) and that `"cycle"` + `"demo"` are NOT in the allow-list yet.
