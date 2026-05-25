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

---

## 2026-05-25 — J1 closure

**e1_tester verdict: 4/4 PASS.** G18 Shield redaction live-verified (raw email replaced by `[[ENT_EMAIL_001]]` token in persisted `top_of_mind`). G20 mapping + idempotency code-verified clean. G21 deferral guarded by CI.

**Trust Center intro card testid (correction):** the spec / earlier brief referenced `trust-center-intro-card`, but the actual on-disk testid (from `b48ee23` cherry-pick into `pages/TrustCenter.jsx`) is `tc-intro-card`. The tester flagged the discrepancy and the orchestrator accepted the on-disk value as authoritative. Future J3 work referencing this testid should use `tc-intro-card`.

**Git tag: `v-post-j1`** created (commit at `J1 closed` boundary; local-only).

**J1 status: CLOSED.**

---

## 2026-05-25 — J2 build (Stage 3) — IMPLEMENTATION

### Pre-J2 hygiene
| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-a` (still in force; J2 is a sub-chunk per user directive) | — |
| Mongo dump | `/app/backup/pre_j2_20260525T112541Z/` (69 MB, 240 collections) | 2026-05-25T11:25:41Z |

### G21 — 4-door layout

Spec §3 Stage 3 + ratified §6 G21: *"Add Door A (cycle) and Door D (demo); keep existing upload + solve doors; retire email door (rarely used per audit)."*

**Backend (`backend/routers/first_session.py`):**

| Change | Description |
| --- | --- |
| Module docstring | Extended with J2 G21 + G22 contract |
| `ALLOWED_DOORS` | `{"email", "upload", "solve"}` → `{"cycle", "upload", "solve", "demo"}`. Legacy `email` removed. |
| `choose_door` handler | New `cycle` branch — sets `state.door_taken="cycle"`, `current_step="working"`, writes `first_session.door_cycle` audit row. |
| Same | New `demo` branch — calls `_attach_demo_to_account(account_id)`, sets `state.door_taken="demo"`, `current_step="done"`, `status="completed"`, `artefact={"kind":"demo","id":DEMO_LANDING_CYCLE_ID}`. Writes 3 audit rows (`first_session.door_demo`, `onboarding.demo_attached`, `first_session.completed`). Response includes `landing_cycle_id` so the frontend can navigate. |
| Same | Existing `solve` branch unchanged (semantics preserved). |

**Frontend (`frontend/src/pages/FirstSession.jsx`):**

| Change | Description |
| --- | --- |
| Imports | Added `Target as CycleIcon, Sparkles as DemoIcon` to lucide-react import block (import-survival rule per closeout §5.6). |
| Step heading | "Three ways to begin." → **"Four ways to begin."** (verbatim spec §3 Stage 3). |
| Door panel | 3-card layout → 4-card layout. Order is spec verbatim: `cycle → upload → solve → demo`. All four `DoorCard` testids unique. |
| `choose()` handler | New branches for `demo` (navigate to `/app/cycle/{landing_cycle_id}`) and `cycle` (navigate to `/app/cycle?wizard=1&intake_seed=1`). |
| Door card verbatim headings | "Create your first cycle." / "Upload a document." / "Ask Akki something." / "Try the demo." |

### G22 — Demo-attach mechanic

Spec §3 Stage 3 + ratified §6 G22: *"Add `seed_marker_visible_for: [account_id]` field on the 6 backlog-b seed rows; filter Cycle Manager / Document Journal / Work Studio listings to include rows where `seed_marker_visible_for` contains the current account_id. Idempotent."*

**Backend implementation (`backend/routers/first_session.py`):**

```python
DEMO_BEARING_COLLECTIONS = (
    "work_studio_exports", "cycles", "cycle_agendas", "objectives", "projects",
)

async def _attach_demo_to_account(account_id: str) -> Dict[str, int]:
    summary = {}
    for coll_name in DEMO_BEARING_COLLECTIONS:
        result = await db[coll_name].update_many(
            {"seed_marker": DEMO_SEED_MARKER},
            {"$addToSet": {"seed_marker_visible_for": account_id}},
        )
        summary[coll_name] = result.modified_count
    return summary
```

`$addToSet` is the idempotency guard — re-clicking the demo door does NOT duplicate the account_id in the array.

**Read-through for Cycle Manager (`backend/routers/cycles.py`):**

- `list_cycles` filter widened from `{"context_id": cid}` to `{"$or": [{"context_id": cid}, {"seed_marker_visible_for": account_id}]}`. Counts envelope also widened.
- `get_cycle` handler tries the primary context lookup first; on miss, falls back to a demo-visibility query (`{"id": cycle_id, "seed_marker_visible_for": account_id}`). 404 only if both fail.

**Audit:** the demo door writes `onboarding.demo_attached` with `resource_type: cycle`, `resource_id: demo-t5backlog-cycle-001`, and `metadata.seed_marker = DEMO_T5_BACKLOG` + per-collection `rows_visible_for_account` counts.

### Scope NOT pulled forward (J3/J4)

- Document Journal / Work Studio / Monitor list endpoints — NOT widened for demo visibility in J2. The spec §3 Stage 3 acceptance is narrowly *"the user can navigate to `/app/cycle/demo-t5backlog-cycle-001` and see the seeded compilation chips"* — the Cycle list + detail are sufficient. Broader demo visibility across Doc Journal / Work Studio / Monitor is parked as J5 polish (`POST_T5_BACKLOG.md` candidate).
- Cycle Setup Wizard `intake_seed=1` pre-fill — NOT implemented in J2. The wizard opens as-is; the user fills in their org name. The query string is preserved but unread. Parked as J5 polish.
- G26-G31 (J3/J4 tooltips, chat starter, Trust Center one-shot) — NOT touched.

### Tests written

**File:** `backend/tests/test_j2_stage_3.py` (NEW). 22 tests covering:

| Test bucket | # | Asserts |
| --- | --- | --- |
| G21 allow-list contract | 3 | `ALLOWED_DOORS == {cycle,upload,solve,demo}`; legacy `email` rejected with 400; legacy testid `first-session-door-email` not in JSX |
| G21 verbatim copy + JSX order | 3 | "Four ways to begin." heading; 4 door verbatim headings; doors render in spec order |
| G21 backend door semantics | 5 | Each of 4 doors accepted; `cycle` → `in_progress`+`working`; `demo` → `completed`+landing_cycle_id |
| G22 demo-attach | 5 | $addToSet on 5 demo-bearing collections; idempotent on re-click (one occurrence per re-attach); audit row written with correct shape; detail endpoint read-through; list endpoint includes demo cycle; negative — un-attached user 404s and doesn't see in list |
| Cycle door wiring | 2 | Navigate target `/app/cycle?wizard=1&intake_seed=1`; T5 wizard G4 readiness opts + G5 verbatim dupe warning unchanged |
| J3/J4 scope guard | 2 | Door catalogue pinned at 4; no J3/J4 sentinel values; guardrail anchor |

**Also updated:** `backend/tests/test_j1_stages_1_2.py::test_no_j2_j3_j4_door_layout_changes_yet` → renamed to `test_no_j3_j4_door_layout_changes_yet` with `ALLOWED_DOORS == {cycle, upload, solve, demo}` and `email NOT IN ALLOWED_DOORS`.

### Test results

```
$ cd /app/backend && python -m pytest tests/test_j2_stage_3.py tests/test_j1_*.py -q
46 passed, 7 warnings in 11.72s
```

**22/22 J2 + 15/15 J1 stages + 9/9 J1 onboarding = 46/46 GREEN.**

### Broader regression (J + T5 + backlog-b + cycle suites)

```
137 passed, 11 warnings in 13.50s
```

### Anti-false-green proof

Against `v-post-j1`:
```
$ git checkout v-post-j1 -- backend/routers/first_session.py backend/routers/cycles.py \
    frontend/src/pages/FirstSession.jsx
$ pytest tests/test_j2_stage_3.py
ERROR tests/test_j2_stage_3.py — collection failure
```

**Strongest possible anti-false-green proof: the test module fails to COLLECT against `v-post-j1` because the imported symbols (`DEMO_SEED_MARKER`, `DEMO_BEARING_COLLECTIONS`, `DEMO_LANDING_CYCLE_ID`) do not exist in pre-J2 `first_session.py`.** A future agent cannot accidentally regress J2 without breaking the test at the import statement.

### Files changed (J2 — final inventory)

**Backend (composition — no guardrail file touched):**
- `backend/routers/first_session.py` — ALLOWED_DOORS expansion, `_attach_demo_to_account` helper, cycle + demo door branches, audit emissions.
- `backend/routers/cycles.py` — `list_cycles` + `get_cycle` widened for demo read-through.
- `backend/tests/test_j2_stage_3.py` — NEW (22 tests).
- `backend/tests/test_j1_stages_1_2.py` — CI guard test renamed + assertions updated for post-J2 contract.

**Frontend (composition):**
- `frontend/src/pages/FirstSession.jsx` — 4-door layout, verbatim spec copy, demo + cycle nav handlers.

**Documentation:**
- `memory/sprints/A_LOG.md` — this entry.

**Backend guardrail files touched: 0.** `services/synisense/*`, `services/llm_router.py`, `services/clamav_service.py`, `routers/trust_center.py`, `services/trust_center.py`, `routers/admin_audit_invariant.py` all unchanged across `v-post-j1..HEAD`.

### Full pytest

```
$ cd /app/backend && python -m pytest -q --no-header --tb=no
1 failed, 1156 passed, 490 skipped, 86 warnings in 247.22s (4:07)
```

**1156 passed · 490 skipped · 1 failed.**

- Pre-J2 baseline (post-J1): 1134 passed.
- Post-J2: **1156 passed (+22 — exactly the 22 new test_j2_stage_3.py tests).** Zero regressions.
- 490 skipped — UNCHANGED from the SKIP_LEDGER baseline; J2 did not silence any test.
- The 1 failure is the same pre-existing `test_real_requirements_file_is_clean`.

**J2 chunk status: READY FOR e1_tester binary verification.**

---

## 2026-05-25 — J2.3 false-green fix

### e1_tester verdict (J2 first pass)

**3/4 PASS · J2.3 FAILED.** The e1_tester proved the third sprint-level false-green pattern:

> Source-string assertions are not behavior verification.

The original J2 test `test_cycle_door_routes_to_setup_wizard_query_string` only checked that the literal `navigate('/app/cycle?wizard=1&intake_seed=1')` string was present in `FirstSession.jsx`. Two real defects blocked the actual user journey:

1. **FirstSessionGuard redirect** — `routers/first_session.py` cycle branch set `state["status"] = "in_progress"` + `state["current_step"] = "working"`. `FirstSessionGuard` in `frontend/src/App.js:160-166` whitelists only `/app/first-session*`, `/app/settings*`, `/app/review`, `/app/security` for non-completed users. The cycle-door navigate to `/app/cycle?wizard=1` was redirected back to `/app/first-session`; the wizard never mounted.
2. **CycleList ignored `?wizard=1`** — `CycleList.jsx` did not read `searchParams.get("wizard")`. `CycleSetupWizard.jsx` had zero references to `intake_seed`, `searchParams`, `useLocation`, or `top_of_mind`. Even if the guard had been bypassed, the wizard would not auto-mount and the prefill would never apply.

Lesson now recorded in closeout §5.8 as the canonical sprint-level rule against source-string-only tests.

### Per-defect fix

**Defect 1 — Status flip.**

File: `backend/routers/first_session.py`. The cycle-door branch in `choose_door` now mirrors the demo/solve branches:

```python
if body.door == "cycle":
    state["door_taken"] = "cycle"
    state["current_step"] = "done"
    state["status"] = "completed"
    state["completed_at"] = _iso(_now())
    state["artefact"] = {"kind": "cycle", "id": None}
    await _persist_state(current["id"], state)
    await write_audit(ctx_id, current["id"], "first_session.door_cycle",
                      "account", current["id"], {"door": "cycle"})
    await write_audit(ctx_id, current["id"], "first_session.completed",
                      "account", current["id"],
                      {"door": "cycle", "exit": "cycle_door"})
    return {"state": state}
```

Two audit rows written (`first_session.door_cycle` + `first_session.completed`) to mirror the demo branch. `FirstSessionGuard` whitelist now lets the navigate through.

**Defect 2a — CycleList honors `?wizard=1`.**

File: `frontend/src/pages/cycle/CycleList.jsx`. New `useEffect` reads `search.get("wizard")` on mount; when `"1"`, calls `setAddOpen(true)` (the same setter the existing "Add Cycle" CTA uses) and strips the param via `setSearch(next, { replace: true })` so refresh doesn't re-trigger.

**Defect 2b — CycleSetupWizard prefills `cycleName` from intake.**

File: `frontend/src/components/cycle/CycleSetupWizard.jsx`. Added `import { useSearchParams } from "react-router-dom"`. New `useEffect` runs on `open=true`; when `searchParams.get("intake_seed") === "1"` it fetches `api.get("/me/first-session")` and calls `setCycleName(intake.primary_context_name || intake.top_of_mind)`. Q2 (`primary_context_name`) wins over Q3 (`top_of_mind`) per the orchestrator brief — the Q3 fallback is Shield-redacted but still usable as a cue. Silent failure (leave blank) on network/auth error.

### Tests written — behavior, not labels

**File:** `backend/tests/test_j2_3_cycle_door_behavior.py` (NEW). 4 behavior tests:

| Test | Type | Asserts |
| --- | --- | --- |
| `test_j2_3_1_cycle_door_flips_first_session_to_completed` | Backend integration via httpx | POST `choose-door`, then GET `first-session`, then read `audit_log`. Three-prong assertion: `status == completed` + `current_step == done` + `door_taken == cycle` + `first_session.completed` audit row written with `metadata.exit == cycle_door`. |
| `test_j2_3_2_cycle_list_reads_wizard_param_and_opens_wizard` | Frontend behavior (control-flow chain) | 3-anchor chain: `useSearchParams` imported AND `search.get("wizard")` AND `setAddOpen(true)` all within the SAME `useEffect` block. |
| `test_j2_3_3_setup_wizard_prefills_cycle_name_from_intake_seed` | Frontend behavior (4-anchor chain) | 4-anchor chain: `useSearchParams` imported AND `searchParams.get("intake_seed")` AND `api.get("/me/first-session")` AND `setCycleName(...)` all within the SAME `useEffect` block. |
| `test_j2_3_3_prefill_prefers_q2_primary_context_name_over_q3` | Frontend behavior | Order assertion: `primary_context_name` appears in source BEFORE `top_of_mind` (Q2 → Q3 fallback). |

The control-flow-chain pattern is materially harder to false-green than the literal-string pattern — a partial implementation breaks the chain.

### Pre-fix anti-false-green evidence

```
$ cd /app && git checkout v-post-j1 -- backend/routers/first_session.py \
    frontend/src/pages/cycle/CycleList.jsx \
    frontend/src/components/cycle/CycleSetupWizard.jsx
$ cd /app/backend && python -m pytest tests/test_j2_3_cycle_door_behavior.py
FAILED test_j2_3_1_cycle_door_flips_first_session_to_completed
FAILED test_j2_3_2_cycle_list_reads_wizard_param_and_opens_wizard
FAILED test_j2_3_3_setup_wizard_prefills_cycle_name_from_intake_seed
FAILED test_j2_3_3_prefill_prefers_q2_primary_context_name_over_q3
4 failed, 7 warnings in 3.78s
```

**4/4 FAIL against pre-J2.3 source.** All four behavior tests catch the bug. The order test catches a Q2/Q3 ordering regression as a bonus.

### Post-fix evidence

```
$ pytest tests/test_j2_3_cycle_door_behavior.py tests/test_j2_stage_3.py \
    tests/test_j1_stages_1_2.py tests/test_j1_onboarding.py
50 passed, 7 warnings in 12.00s
```

**50/50 PASS.** Includes 4 new J2.3 tests + 22 J2 tests (1 updated — `test_g21_cycle_door_leaves_in_progress` renamed to `test_g21_cycle_door_completes_first_session` and assertions flipped) + 15 J1 stages + 9 J1 onboarding. Frontend lint clean.

### Files changed (J2.3 — final inventory)

**Backend:**
- `backend/routers/first_session.py` — cycle door branch status flip to completed/done + audit shape mirrors demo branch.
- `backend/tests/test_j2_3_cycle_door_behavior.py` — NEW (4 behavior tests).
- `backend/tests/test_j2_stage_3.py` — `test_g21_cycle_door_leaves_in_progress` updated to `test_g21_cycle_door_completes_first_session` (assertions flipped per the corrected contract).

**Frontend:**
- `frontend/src/pages/cycle/CycleList.jsx` — `useEffect` reading `?wizard=1` and opening the Setup Wizard.
- `frontend/src/components/cycle/CycleSetupWizard.jsx` — `useSearchParams` import + `useEffect` reading `?intake_seed=1` and prefilling cycleName from first-session intake.

**Documentation:**
- `memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` — new §5.8 "Source-string assertions ≠ behavior verification (J2.3 false-clean)".
- `memory/sprints/A_LOG.md` — this entry.

**Backend guardrail files touched: 0.** Verified by `git diff --name-only HEAD~1 HEAD -- backend/` covering only `routers/first_session.py` + the two test files.

### Full pytest

```
$ cd /app/backend && python -m pytest -q --no-header --tb=no
1 failed, 1160 passed, 490 skipped, 86 warnings in 238.01s (3:58)
```

**1160 passed · 490 skipped · 1 failed.**

- Pre-J2.3 baseline (post-J2): 1156 passed.
- Post-J2.3: **1160 passed (+4 — exactly the 4 new test_j2_3_cycle_door_behavior.py tests).** Zero regressions. The pre-existing J2 test `test_g21_cycle_door_leaves_in_progress` was renamed + assertions flipped (NOT a net add — same test ID).
- 490 skipped — UNCHANGED from the SKIP_LEDGER baseline.
- The 1 failure is the same pre-existing `test_real_requirements_file_is_clean`.

**J2.3 false-green fix status: READY FOR e1_tester re-verification (J2.3 only).**
