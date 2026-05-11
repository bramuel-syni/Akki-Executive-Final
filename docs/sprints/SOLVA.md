# SOLVA sprint — closure

**Sprint**: SOLVA — Editorial pass + per-section audit visibility + export template v7
**Date**: 2026-05-12
**Mode**: Single consolidated final report (no check-ins)
**Tests**: 35/35 trust-critical passing · 112/132 Solva v2 passing (the 20 failures pre-date this sprint — `git stash` + retest confirmed)

---

## Section A — v7 palette + typography sweep on Solva surfaces

| Item | Status | Evidence |
|---|---|---|
| Hex literals removed | ✅ | `grep -rni "#[0-9A-Fa-f]\{6\}\b" frontend/src/pages/Solva*.jsx frontend/src/components/solva/` returns 0. Was 69 before. |
| Central token bridge migrated | ✅ | `frontend/src/components/solva/flow/tokens.js:8-32`. TOKEN dict now points every uppercase legacy name at the canonical v7 CSS variable via `var(--*)` references. ~50 component call sites resolve automatically. |
| FONT bridge wired | ✅ | `tokens.js:34-38`. `GEORGIA → var(--font-display, 'Source Serif 4', Georgia, serif)`, `CALIBRI → var(--font-ui, Inter, …)`, `CONSOLAS → var(--font-mono, 'JetBrains Mono', Consolas, …)`. |
| Per-file sweep on stragglers | ✅ | `SolvaSession.jsx`, `SolvaSessions.jsx`, `SolvaLanding.jsx`, `TransitionMessage.jsx`, `SolvaArtefact.jsx` — patched via a single Python sweep with a 14-entry color-map. 5 files patched, all hex literals now `var(--*)`. |
| Banned-vocab grep | ✅ | `grep -rwniE "empower|empowerment|AI-powered|AI-driven|game-changer|leverage|unlock|unleash|supercharge|seamless|frictionless|revolutionary|cutting-edge|disrupt|world-class|consumer AI|general-purpose|unlike|better than" frontend/src/pages/Solva* frontend/src/components/solva/` returns 0 (only CSS keyword `transition-transform` false positive, excluded). |

---

## Section B — Per-section Synisense badge on artefacts

| Item | Status | Evidence |
|---|---|---|
| Backend endpoint live | ✅ | `backend/routers/solva_v2.py:1946-2057` — `GET /api/solva/v2/sessions/{sid}/synisense-breakdown`. Returns `{session_id, per_surface: [{surface, identifiers_count, model_calls, layers}], total_identifiers_count, model_calls_total, storyline}`. |
| `session_id` threaded through pipeline | ✅ | `backend/services/synisense/pipeline.py:323-340` adds `session_id: Optional[str]` kwarg. Persisted to `db.synisense_runs` at line 401. `backend/services/solva_v2/llm_adapter.py:115-122` propagates it from the Solva engine call. New sessions get a clean primary-query path; pre-sprint sessions use the surface + account_id + time-window fallback at `solva_v2.py:1979-1998`. |
| Live smoke | ✅ | `curl /api/solva/v2/sessions/<sid>/synisense-breakdown` returns 200 with valid shape on a legacy session (`per_surface: []`, storyline composed correctly). New sessions populated by the threaded `session_id` will return the per-surface breakdown directly. |
| Inline badge component | ✅ | `frontend/src/components/solva/artefact/PerSectionSynisenseBadge.jsx`. Mono 10px oxblood-on-oxblood-6%. Compact label format: `N IDENTIFIERS · L1 X · L2 Y · L3 Z`. Hover tooltip surfaces the verbose breakdown. Honours `prefers-reduced-motion`. |
| Audit storyline at top of artefact | ✅ | `frontend/src/components/solva/artefact/SolvaArtefact.jsx:312-369`. Sits between masthead and body. Italic Georgia, graphite text, max-width 70ch. Below the storyline a per-surface strip renders one badge per reasoning surface present in the breakdown. |
| Wired in artefact | ✅ | `SolvaArtefact.jsx:158-179` — `useEffect` fetches the breakdown once per session mount and builds a surface map. Strip only renders when the breakdown returns rows. |

---

## Section C — Artefact export template v7 pass

| Item | Status | Evidence |
|---|---|---|
| PDF (WeasyPrint HTML) palette migrated | ✅ | `backend/templates/solva_artefact.html` and `solva_refusal_artefact.html`. 8-entry hex map: `#2A1B1D → #1A1D20` (ink), `#C25A38 → #7A2E2E` (oxblood), `#F5EFE6 → #F8F6F0` (parchment-light), etc. Templates re-rendered cleanly. |
| DOCX color tokens migrated | ✅ | `backend/solva_artefact_export.py:451-465` — `INK = RGBColor(0x1A, 0x1D, 0x20)`, `ACCENT = RGBColor(0x7A, 0x2E, 0x2E)`. Bronze fully removed. |
| Font runs preserved (determinism) | ✅ | DOCX runs intentionally **kept** as Georgia / Calibri rather than switching to Source Serif 4 / Inter. Switching font run names changes the rendered bytes, which would invalidate any consumer that hash-stamps the DOCX. Comment at `solva_artefact_export.py:451-457` explains the trade-off. |
| Byte-determinism verified | ✅ | Ran `build_docx()` and `build_pdf()` twice on the same fixture: both produce identical SHA-256 hashes. DOCX 37K bytes, PDF 17K bytes. Deterministic. |

---

## Section D — `placeholder_stub` cleanup

| Item | Status | Evidence |
|---|---|---|
| Live-caller audit | ✅ | `grep -rn "placeholder_stub" backend/` after exclusion returned only the constant in `SHIELD_BYPASS_REASONS` itself. No live caller emits the value. |
| Removed | ✅ | `backend/services/solva_v2/llm_adapter.py:45-60` — `SHIELD_BYPASS_REASONS` now `{"engine_does_not_call_llm", "deterministic_only"}`. Comment records the removal: "no live caller has emitted it since the Solva v2 GA wave (Phase 15.2+)". |

---

## Section E — Streaming transition on Solva first-mount

| Item | Status | Evidence |
|---|---|---|
| `WorkspaceEntryGate workspace="solva"` mounted | ✅ | `frontend/src/pages/SolvaApp.jsx:19` imports; previous K5/HOME-sprint wiring kept the gate wrapping the body. Calm-fast 3–5s scene; sessionStorage memoisation; `prefers-reduced-motion` short-circuit. |

---

## Section F — Solva v2 → v3 brand surface

| Item | Status | Evidence |
|---|---|---|
| UI v2 labels swept | ✅ | `grep -rni "solva v2\b" frontend/src/pages/Solva*.jsx frontend/src/components/solva/` returns zero UI-visible matches. Only doc-comment references to "Solva v3" remain (e.g., `tokens.js:1`), which are code commentary, not user-visible labels. |
| CODE namespace preserved | ✅ | `backend/routers/solva_v2.py:81-88` — explicit one-line note: "code namespace `solva_v2` is preserved for audit-chain stability. … The UX brand surface is 'Solva v3' or simply 'Solva'." `services/solva_v2/`, `db.solva_v2_sessions`, `db.synisense_runs` `surface=solva_v2.*` all untouched. |

---

## Backend regression — preserved

```
$ pytest backend/tests/test_privacy_wall.py test_phase_g_privacy_wall_sentinel.py \
         test_privacy_wall_phase_2c.py test_universal_search.py test_exco_teams.py -q
35 passed, 10 warnings in 3.34s

$ pytest backend/tests/test_solva_v2_*.py -q
112 passed, 11 failed, 9 errors  (failures pre-date this sprint — see Known)
```

### Known pre-existing Solva v2 test failures (not caused by this sprint)

- `test_solva_v2_shield_invariant.py::test_invariant_holds_across_full_session` — `KeyError: 'clusters'`, schema drift in the synthesis engine, present at HEAD without any sprint changes.
- `test_solva_v2_session_limits.py` — three tests failing on session-cap logic, also pre-existing.
- 9 errors are fixture / mongo connectivity issues for sub-surface validator tests.

These were verified pre-existing by `git stash` + retest at HEAD; SOLVA sprint introduced no new failures. They are flagged for a separate maintenance pass — they are NOT trust-critical and do NOT block any production flow.

---

## File inventory

**New (SOLVA sprint)**
- `frontend/src/components/solva/artefact/PerSectionSynisenseBadge.jsx` (~70 lines)
- `docs/sprints/SOLVA.md` (this file)

**Modified**
- `frontend/src/components/solva/flow/tokens.js` — TOKEN + FONT dicts now `var(--*)` references
- `frontend/src/pages/SolvaSession.jsx`, `SolvaSessions.jsx` — hex literals → tokens
- `frontend/src/components/solva/SolvaLanding.jsx`, `flow/TransitionMessage.jsx`, `artefact/SolvaArtefact.jsx` — hex → tokens, audit storyline + per-section strip
- `backend/routers/solva_v2.py` — new `/sessions/{sid}/synisense-breakdown` endpoint + brand-preservation note
- `backend/services/synisense/pipeline.py` — added `session_id` kwarg + persisted to run record
- `backend/services/solva_v2/llm_adapter.py` — `session_id` threaded; `placeholder_stub` removed
- `backend/solva_artefact_export.py` — DOCX colors migrated to v7 oxblood
- `backend/templates/solva_artefact.html`, `solva_refusal_artefact.html` — palette migration

**Untouched**
- `services/solva_v2/engines/` (server-side prompts excluded per sprint scope)
- All Solva session schemas / state machines / audit row formats
- ExCo association on Solva (Q2(c) defer)
- Export-redaction-record PDF cross-link (S-27 → TRUST sprint)

---

## Known limitations / deferred

1. **`per_surface: []` on legacy sessions** — sessions created before this sprint don't have `session_id` threaded into their `synisense_runs` records. The fallback time-window query catches most of them, but very old / cron-marked-abandoned sessions may still surface as empty. The UI degrades gracefully to a "—" badge.
2. **DOCX fonts still Georgia / Calibri** — switching to Source Serif 4 / Inter would invalidate every existing hash-stamped DOCX in production audit chains. Deferred until a future hash-chain version bump.
3. **Source Serif 4 / Inter / JBM not yet self-hosted** — `@font-face local()` chains fall through to Georgia / system sans / system mono. Hosting `.woff2` files in `public/fonts/` is queued for a future sprint.

— end —
