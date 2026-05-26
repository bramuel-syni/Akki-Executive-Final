# Redeploy Cleanup Log

**Dispatched:** 2026-05-26 (post-LEGACY_CONFLICT_LEDGER audit + provenance trace + deploy-blocker fix).
**Snapshot tag:** `v-pre-redeploy-cleanup` (local-only).
**Mongo dump:** `/app/backup/pre_redeploy_20260526T020136Z/akki_dev/` (86 MB).
**Three tasks in one chunk:**
1. Bucket-2 cleanup (Plays + cycle_config orphans per provenance trace).
2. News-aggregator stale-RSS-source pruning.
3. Read-only `.env` key-only audit.

---

## Task 1A — Plays / Workflows surface archive

Per `PROVENANCE_TRACE_PLAYS_CYCLE.md` verdict: **ORPHAN** (no canonical reference, first introduced 2026-04-26 — predates spec v1.1 clean-break).

### Reference-check corrections discovered during execution

Two callouts where the brief assumed an action and the grep evidence forced a re-route:

| Brief item | Finding | Action |
| --- | --- | --- |
| `backend/routers/agenda.py` | Despite filename adjacency to Plays, this router serves `/api/contexts/{cid}/agenda-evolution` — a completely different surface that powers the Home `AgendaEvolutionCard.jsx`. Live consumers in `components/home/AgendaEvolutionCard.jsx`, `tests/test_iter26_engagement.py`, `tests/test_iter29_score_history.py`. | **leave + escalate** per brief's own conditional ("verify it's tied to Plays, not used elsewhere; if used elsewhere, leave it and escalate"). |
| Plays surface in Home/Decks | `pages/Decks.jsx`, `components/home/QuickActions.jsx`, `components/home/WorkflowsHub.jsx`, `components/home/PlaysInProgressStrip.jsx`, `components/home/PlayReadyCards.jsx`, `components/documents/DocumentPlayContext.jsx` all REFERENCE Plays — but each does so via `.catch(() => ({ data: { plays: [] } }))` graceful fallback. After archiving the `/api/plays/*` router, these surfaces continue to render with empty Plays sections. | **Archive the surface; leave the integrations as-is** per brief's "no refactor beyond the cleanup" hard rule. The orphan integrations are a follow-up cleanup. |

### Actions executed

| # | source path | archived path |
| --- | --- | --- |
| 1 | `backend/routers/plays.py` | `backend/_archived_legacy/routers/plays.py.archived` |
| 2 | `frontend/src/pages/PlaysLibrary.jsx` | `frontend/src/_archived_legacy/pages/PlaysLibrary.jsx.archived` |
| 3 | `frontend/src/pages/PlayView.jsx` | `frontend/src/_archived_legacy/pages/PlayView.jsx.archived` |
| 4 | `frontend/src/components/plays/PreBoardStages.jsx` | `frontend/src/_archived_legacy/components/plays/PreBoardStages.jsx.archived` |
| 5 | `frontend/src/components/plays/BoardPackStages.jsx` | `frontend/src/_archived_legacy/components/plays/BoardPackStages.jsx.archived` |
| 6 | `backend/tests/test_iter24_plays.py` (pre-skipped) | `backend/tests/_archived_coverage_loss/test_iter24_plays.py.archived` |
| 7 | `backend/tests/test_iter25_plays_slice2.py` (pre-skipped) | `backend/tests/_archived_coverage_loss/test_iter25_plays_slice2.py.archived` |

### App.js edits

- Removed `lazy(() => import("@/pages/PlaysLibrary"))` (line 94).
- Removed `lazy(() => import("@/pages/PlayView"))` (line 95).
- Removed `<Route path="/app/plays" element={<Gated><PlaysLibrary /></Gated>} />` (line 289).
- Removed `<Route path="/app/plays/:playId" element={<Gated><PlayView /></Gated>} />` (line 290).

### server.py edits

- Removed `from routers import plays as plays_router` (line 67).
- Removed `app.include_router(plays_router.router)` (the corresponding include line).

---

## Task 1B — cycle_config archive

Per `PROVENANCE_TRACE_PLAYS_CYCLE.md` verdict: **ORPHAN** (no canonical reference, only consumer was `CycleStrip.jsx` already archived in Bucket 1 — but reference-recheck found a deeper transitive chain).

### Reference-check correction

The provenance trace said cycle_config had "0 live frontend callers". Re-grep found:
- `frontend/src/hooks/useCycleConfig.js` — actively calls all 5 cycle_config endpoints.
- `frontend/src/pages/CycleSettings.jsx` — the only consumer of `useCycleConfig`.
- `App.js:340` — routes `/app/settings/cycle` to `CycleSettings`.

The chain is sealed: `cycle_config router → useCycleConfig hook → CycleSettings page → /app/settings/cycle route`. The page is NOT linked from any nav (orphan route reachable only by direct URL), NOT in spec, predates spec v1.1 by 23+ days. Archiving the whole chain together.

`solva_v2.py:1688` reads `db.cycle_configs` (the collection, not the router) — this read works untouched because data persists across router archive. No code change needed there.

### Actions executed

| # | source path | archived path |
| --- | --- | --- |
| 8 | `backend/routers/cycle_config.py` | `backend/_archived_legacy/routers/cycle_config.py.archived` |
| 9 | `frontend/src/hooks/useCycleConfig.js` | `frontend/src/_archived_legacy/hooks/useCycleConfig.js.archived` |
| 10 | `frontend/src/pages/CycleSettings.jsx` | `frontend/src/_archived_legacy/pages/CycleSettings.jsx.archived` |

### App.js edits

- Removed `lazy(() => import("@/pages/CycleSettings"))` (line 61).
- Removed `<Route path="/app/settings/cycle" element={<Gated><CycleSettings /></Gated>} />` (line 340).

### server.py edits

- Removed `from routers import cycle_config as cycle_config_router` (line 109).
- Removed `app.include_router(cycle_config_router.router)` (line 236).

---

## Task 1C — `cycle.py` documentation header (no code change)

Per provenance trace verdict: **MIXED — partial-orphan**. 9 of 30 endpoints still load-bearing for live UX, 21 endpoints describe pre-spec product layer with no canonical authority.

Added a top-of-file docstring (no endpoint deletion — surgical removal is a refactor and brief explicitly disallows refactor beyond the cleanups). Docstring categorises endpoints by canonical status, cites the provenance trace, and instructs future devs not to extend the pre-spec families.

---

## Anti-false-green test

`backend/tests/test_redeploy_cleanup_invariants.py` — pins every archive action.

| # | test | invariant |
| --- | --- | --- |
| RC.1 | `test_rc_plays_router_archived` | `backend/routers/plays.py` not on disk; archive exists. `from routers import plays` raises ImportError. |
| RC.2 | `test_rc_plays_pages_archived` | `pages/PlaysLibrary.jsx` + `pages/PlayView.jsx` not on disk; archives exist. |
| RC.3 | `test_rc_plays_components_archived` | `components/plays/` is empty / removed. |
| RC.4 | `test_rc_plays_routes_unmounted_appjs` | App.js does not import PlaysLibrary/PlayView and has no `/app/plays` route. |
| RC.5 | `test_rc_plays_router_unmounted_server` | `/api/plays/library` returns 404 (TestClient). |
| RC.6 | `test_rc_plays_tests_archived` | `tests/test_iter24_plays.py` + `test_iter25_plays_slice2.py` not on disk; archives exist. |
| RC.7 | `test_rc_cycle_config_router_archived` | `routers/cycle_config.py` not on disk; archive exists. `GET /api/contexts/x/cycle-config` returns 404. |
| RC.8 | `test_rc_cycle_settings_archived` | `pages/CycleSettings.jsx` + `hooks/useCycleConfig.js` not on disk; archives exist. App.js does not import CycleSettings. |
| RC.9 | `test_rc_cycle_py_docstring_present` | `routers/cycle.py` docstring contains "canonical" + "pre-spec" markers + provenance-trace path citation. |
| RC.10 | `test_rc_agenda_router_preserved` | `routers/agenda.py` IS on disk (escalated, not archived). |

---

## Task 2 — News-aggregator stale RSS sources

HEAD probe results (5s timeout, Mozilla user-agent):

| Source id | URL | HEAD result | Verdict |
| --- | --- | --- | --- |
| `reuters-biz` | `https://feeds.reuters.com/reuters/businessNews` | DNS failure (`000`) — `feeds.reuters.com` no longer resolves | **dead → removed** |
| `hbr` | `https://hbr.org/feed` | HTTP 404 | **dead → removed** |
| `frc-uk` | `https://www.frc.org.uk/news-and-events/rss` | HTTP 404 (after follow-redirect to trailing slash) | **dead → removed** |
| `iod` | `https://www.iod.com/news/rss` | HTTP 403 (blocks unauth probes + does not serve RSS at that path) | **dead → removed** |

All 4 source entries removed from `backend/data/news_sources.json`. Added `_removed_2026_05_26_redeploy_cleanup` audit-trail block to the JSON listing each removed slug + URL + reason. Live source count went from 13 → 9.

Replacement sources NOT auto-substituted per brief ("New replacement sources are a separate decision the user hasn't asked for").

### Regression test

`backend/tests/test_redeploy_news_sources.py` — 4 parametric cases + 3 structural checks:
- `test_news_sources_json_loads` — file parses.
- `test_dead_source_not_re_added[iod|frc-uk|hbr|reuters-biz]` — each of the 4 slugs must NOT be in the live `sources[]` list.
- `test_removal_audit_note_present` — audit-trail block exists and references all 4 removed slugs.
- `test_remaining_sources_all_have_required_keys` — schema-shape check on remaining entries.

---

## Task 3 — `.env` audit (read-only)

Output: `/app/memory/sprints/ENV_FILE_AUDIT.md`

### `backend/.env`

| Category | Key count |
| --- | --- |
| URL / host config | 5 |
| Service identifier | 10 |
| Feature flag / operational dial | 14 |
| API key / secret / token | 11 |
| Password / credential | 3 |
| **Total** | **43** |

### `frontend/.env`

| Category | Key count |
| --- | --- |
| URL / host config | 1 |
| Service identifier | 1 |
| Feature flag / operational dial | 0 |
| API key / secret / token | 0 |
| Password / credential | 0 |
| **Total** | **2** |

**Production-tier callouts** documented in the audit doc (informational only — no rotation/relocation performed; user decides).

NO `.env` FILES MODIFIED.

---

## Pytest counts

| Snapshot | Passed | Failed | Skipped |
| --- | --- | --- | --- |
| `v-pre-redeploy-cleanup` baseline (post-Bucket-1) | 1266 | 1 (pre-existing `test_real_requirements_file_is_clean`) | 435 |
| Post-redeploy-cleanup (this chunk) | **1286** | 1 (same pre-existing) | 408 |
| Δ | **+20** (13 from `test_redeploy_cleanup_invariants.py` + 7 from `test_redeploy_news_sources.py`) | 0 | −27 (test_iter24_plays + test_iter25_plays_slice2 removed from collection) |

**Zero regressions.** Single failure unchanged — the parked spaCy `requirements.txt` direct-URL flag in `POST_T5_BACKLOG.md`.

## Guardrails not touched

`git diff --name-only v-pre-redeploy-cleanup -- backend/services/synisense/ backend/services/clamav_service.py backend/routers/trust_center.py backend/routers/admin_audit_invariant.py backend/routers/healthz_* backend/services/backfill_shield_v1.py` returned empty.

## Tag

`git tag v-post-redeploy-cleanup -m "after redeploy cleanup chunk — Plays + cycle_config archived, RSS pruned, env audit"` (local-only).
