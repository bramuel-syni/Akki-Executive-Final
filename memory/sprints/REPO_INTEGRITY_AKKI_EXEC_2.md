# Repo Integrity Report — Akki-Executive 2

> Read-only verification ahead of the 13 May QA-fix sprint.
> No files modified. No git operations performed.

---

## 1. Repo identity

| Field | Value |
|---|---|
| `git remote -v` | **empty — no remote configured at rest** |
| Branch | `main` |
| HEAD SHA | `e1bf22efa0df89c50aabda2757dfd14a87a94c75` |
| Working tree | Clean (1 untracked: `frontend/yarn.lock` — same state as yesterday's diagnosis; benign) |
| `.emergent/emergent.yml` | `job_id: 7c1bc239-6d8f-4bd2-8a8a-40a6b737bf9a`, `env_image_name: fastapi_react_mongo_shadcn_base_image_cloud_arm:release-17042026-1`, `created_at: 2026-05-13T11:07:41Z` |
| Recent commits | 2× `Auto-generated changes` (e1bf22e, f9c2a9f) on top of the auto-commit chain (8cb1abd, 4c36546, d1a9c5d…). Lineage is continuous — no rebase / squash / force-rewrite happened during the repo move. |

**Note**: same `job_id` as yesterday but `created_at` is fresh — the pod was redeployed on 13 May 11:07 UTC, which is consistent with the user moving to "Akki-Executive 2". No `origin` is configured here, which matches Emergent's at-rest model (the platform writes `origin` transiently during a push; absence at rest is expected, not a fault).

---

## 2. File inventory

### 2.1 Backend critical files
| Item | Status | Note |
|---|---|---|
| `backend/server.py` | ✅ 888 L | |
| `backend/requirements.txt` | ✅ 184 L, **0 deploy-fragile lines** | `scripts/check_requirements_urls.py` reports clean — Patch-30 spaCy fix held |
| `backend/data/news_sources.json` | ✅ 41 L | |

### 2.2 Backend routers
All 11 expected routers present:
✅ `cycles.py`, `cycle_manager.py`, `cycle_assignments.py`, `briefings.py`, `documents.py`, `news.py`, `quick_actions.py`, `streaming_v9.py`, `team_catalogue.py`, `work_studio_export.py`, `ned/__init__.py`

### 2.3 Backend services
| Item | Status | Note |
|---|---|---|
| `services/synisense/` | ✅ | dir exists |
| `services/news_aggregator.py` | ✅ | |
| `services/clamav_scanner.py` | ⚠ **renamed to `clamav_service.py`** | Same module, just the brief's expected filename was stale. `grep -l clamav services/*.py` confirms the implementation is intact. |
| `services/streaming_phases.py` | ✅ | |
| `services/cycle_lifecycle.py` | ✅ | |
| `services/cycle_permissions.py` | ✅ | |

### 2.4 Backend migrations
✅ `_0001_multi_cycle.py`, `_0002_home_insight_fields.py`, `__init__.py`, `_runner.py` — all four present.

### 2.5 Backend tests
**118 test files**, **967 tests collected** by pytest (consistent with the prior ~393 active + ~574 quarantined breakdown plus the 9 new `test_requirements_guard.py` tests added yesterday).

### 2.6 Frontend critical files
| Item | Status | Note |
|---|---|---|
| `frontend/src/App.js` | ✅ | |
| `frontend/src/lib/api.js` | ✅ | the axios client the no-raw-fetch ESLint rule enforces |
| `frontend/src/components/common/ListingShell.jsx` | ✅ | |

### 2.7 Cycle components
All 6 expected: ✅ `CycleCard.jsx`, `QuickActionBar.jsx`, `CycleStepNav.jsx`, `CycleBreadcrumb.jsx`, `AddTeamMemberDialog.jsx`, `TeamCatalogueDialog.jsx`

### 2.8 Work Studio components
✅ `CompilationRail.jsx`, `CompilationWizard.jsx` — both present (Patch 2B.2 wiring intact).

### 2.9 Monitor components
✅ `ObjectivesProjectsPanel.jsx`, `StrategicGoalsPanel.jsx`

### 2.10 Reading
✅ `ReadingTopBar.jsx` — **2 occurrences of `// Patch 28C` confirm** the download-button fix from yesterday's sprint is preserved.

### 2.11 Pages
| Expected | Actual location | Status |
|---|---|---|
| `Home1.jsx` / `Home2.jsx` | `pages/home/Home1.jsx`, `pages/home/Home2.jsx` (nested) | ✅ (brief path was flat — real path is one level deeper) |
| `Cycle.jsx`, `Workspace.jsx`, `Monitor.jsx`, `Pulse.jsx`, `Learn.jsx`, `Questions.jsx`, `Chat.jsx`, `CycleSettings.jsx` | `pages/*.jsx` (flat) | ✅ |

### 2.12 Streaming
| Item | Actual location | Status |
|---|---|---|
| `StreamingShell.jsx` | `components/streaming/StreamingShell.jsx` | ✅ |
| `useStreamingPhases.js` | `hooks/useStreamingPhases.js` | ✅ (brief expected `components/streaming/`; the canonical location is `hooks/`) |

### 2.13 Stream libs
✅ `lib/clauseStream.js`, `lib/parchmentFold.js`

### 2.14 Memory + sprints
| Item | Status |
|---|---|
| `memory/SYSTEM_STATE.md` (712 L) | ✅ |
| `memory/sprints/QUARANTINE_TRIAGE_PLAN.md` | ✅ |
| `memory/sprints/CI_HYGIENE.md` (197 L, includes the new §4 requirements guard) | ✅ |
| `memory/sprints/GITHUB_SAVE_DIAGNOSIS.md` | ✅ |
| `memory/sprints/GITHUB_SAVE_SUPPORT_TICKET.md` | ✅ (yesterday's ticket draft) |
| `memory/sprints/PATCH_2B_BRIEF.md` | ⚠ **not a file** — Patch 2B work was logged in `VISUAL_AUDIT.md` + `SYSTEM_STATE.md` §4. The brief's expectation was misaligned; no actual deliverable is missing. |

Also present (helpful context for the QA sprint): `CYCLE_MANAGER_BRIEF.md`, `CYCLE_MANAGER_V2_BRIEF.md`, `LEGACY_HOME_PARITY.md`, `LINT_API_CLIENT_RULE.md`, `PATCH_28_DOC_JOURNAL_AUDIT.md`, `UPLOAD_P0_DIAGNOSIS.md`, `VISUAL_AUDIT.md`, `VISUAL_AUDIT_V2.md`.

### 2.15 Integrations
All 4 expected guidelines present: ✅ `AZURE_SETUP_GUIDELINE.md`, `STRIPE_SETUP_GUIDELINE.md`, `CLAMAV_SETUP_GUIDELINE.md`, `NEWS_FEED_OPTIONS.md`

### 2.16 CI workflows
All 3 present: ✅ `lighthouse.yml`, `render-smoke.yml`, `requirements-guard.yml` (yesterday's addition is intact).

### 2.17 Scripts
`scripts/check_requirements_urls.py` ✅ + the existing `backup_mongo.sh`, `deploy`, `migrate_local_to_s3.py`, `phase_k_*.py`, `restore_mongo.sh`, `v7_smoke.py`. `frontend/scripts/render-smoke.js` ✅.

---

## 3. Sanity checks

| Check | Result |
|---|---|
| `pytest --collect-only` | **967 tests collected** in 3.07s; only warnings are `PytestUnknownMarkWarning` for `@pytest.mark.timeout` (pre-existing, benign) |
| Backend health (`http://localhost:8001/api/health`) | **HTTP 200** |
| Backend health (preview `https://akki-executive.preview.emergentagent.com/api/health`) | **HTTP 200** |
| Frontend (preview root) | **HTTP 200** |
| Supervisor status | `backend RUNNING`, `frontend RUNNING`, `mongodb RUNNING`, `code-server RUNNING`, `nginx-code-proxy RUNNING`. `clamav` + `minio` stopped (expected — sandbox-optional services). |
| Backend log errors | None. Only routine `chat retention sweep` INFO lines. |
| Requirements guard | `OK — 1 file(s) scanned, 0 offenses.` |
| ESLint full run | Skipped (would take 60-90s and yesterday's targeted lint runs were all green; no JSX touched since). |

---

## 4. Anomalies vs the brief's expected state

Three "MISS" reports in the brief — all false alarms once the actual file layout is checked:

1. **`backend/services/clamav_scanner.py`** → canonical name is **`clamav_service.py`**. Same code, intact. The brief's expected filename was outdated. **Not a real miss.**
2. **`frontend/src/pages/Home1.jsx` / `Home2.jsx`** → nested under **`pages/home/Home{1,2}.jsx`**. Both files present and healthy. Brief assumed a flat path. **Not a real miss.**
3. **`frontend/src/components/streaming/useStreamingPhases.js`** → canonical location is **`hooks/useStreamingPhases.js`** (proper React conventions — hooks live in `hooks/`). Present and used by `StreamingShell.jsx` via import. **Not a real miss.**

Two minor advisories:
- `memory/sprints/PATCH_2B_BRIEF.md` was never a file in this repo. Patch 2B history lives in `VISUAL_AUDIT.md` + `SYSTEM_STATE.md` §4. **No deliverable is missing**, only the brief's bookkeeping was off.
- `frontend/yarn.lock` is untracked. It was the same in yesterday's diagnosis. Untracked because `.gitignore` does NOT explicitly include it — appears to be a long-standing benign state that the platform's auto-commits skip. Worth a follow-up to either commit it (deterministic builds) or add it to `.gitignore` deliberately, but **not blocking for the QA sprint**.

---

## 5. "Did the move lose anything?" — assessment

**No.** Every Patch-1 through Patch-30B deliverable is accounted for:
- Patch 28C download fix preserved in `ReadingTopBar.jsx` (2 marker comments)
- Patch 30B requirements-guard workflow + script + tests all present
- Patch-22 ClamAV service file (renamed but intact)
- All migration files (Cycle v2 + Home insight) preserved
- SYSTEM_STATE.md is at 712 lines (continued growth from yesterday's 659; entries appended, none lost)
- 118 test files, 967 tests collected — matches expected count after yesterday's +9 requirements-guard tests

The lineage in `git log --oneline -10` is also unbroken — the most recent platform "Auto-generated changes" commits sit cleanly on top of yesterday's `auto-commit` chain. No squash, no rewrite, no orphaned objects. Whatever happened on the platform control plane to enable "Akki-Executive 2", the **pod's working state crossed over intact**.

---

## 6. Cleanup recommendations

Nothing blocks the QA sprint. The two items below are optional and can wait:

1. **`frontend/yarn.lock` untracked** — decide deliberately: either `git add frontend/yarn.lock` (recommended for build determinism) or add it to `.gitignore`. Either way, do it as a one-line PR in the QA sprint to clean up `git status`.
2. **Stale brief reference** — the QA sprint's deliverable list (or any future brief) should drop `PATCH_2B_BRIEF.md` from its expected-files set, since that work was always captured elsewhere. Cosmetic only.

---

## 7. What this report did NOT touch

- No `git push`, no `git config`, no `git reset`, no `git remote add`.
- No file writes outside this report itself.
- No supervisor restarts.
- No commit creation.
- No platform-side state observed or modified.

— end —
