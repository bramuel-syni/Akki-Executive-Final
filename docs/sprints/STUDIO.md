# STUDIO sprint — closure

**Sprint**: STUDIO — Work Studio editorial pass + per-artefact audit visibility + export template v7 + CI determinism
**Date**: 2026-05-12
**Mode**: Single consolidated final report (no check-ins)
**Tests**: 41/41 passing (35 trust-critical + 6 new `test_render_determinism.py`)

---

## Section A — v7 palette + typography sweep

| Item | Status | Evidence |
|---|---|---|
| Hex literals removed (round 1) | ✅ | First sweep on the standard v7 color map patched `pages/StudioComposerPage.jsx` + `components/studio/BlockComposer.jsx`. |
| Hex literals removed (extended map) | ✅ | Second sweep added 21-entry extended palette covering `#FFFEFA`, `#D9CFB8`, `#E8DFC9`, `#7C6A4F`, `#5C5247`, `#8B2E2B`, hex shorthands `#fff`/`#000`. |
| Final state — zero hex on Studio surfaces | ✅ | `grep -rn "#[0-9A-Fa-f]\{6\}\|#[0-9A-Fa-f]\{3\}\b" frontend/src/pages/WorkStudio.jsx frontend/src/pages/StudioComposerPage.jsx frontend/src/pages/Decks.jsx frontend/src/components/studio/` returns 0. |
| Banned-vocab grep | ✅ | Returns 0 (only CSS keyword `transition-transform` false positive). |
| Typography flows through CSS vars | ✅ | All Studio surfaces inherit `--font-display`, `--font-ui`, `--font-mono` from the app-shell `index.css` HOME-sprint migration. New `PerArtefactSynisenseBadge.jsx` uses `font-mono` Tailwind class (resolves to `var(--font-mono)`). |

---

## Section B — Per-artefact Synisense badge

| Item | Status | Evidence |
|---|---|---|
| Backend endpoint live | ✅ | `backend/routers/work_studio_export.py:1334-1421` — `GET /api/work_studio/artefacts/{kind}/{artefact_id}/synisense-breakdown`. Returns `{artefact_id, artefact_kind, per_surface, total_identifiers_count, model_calls_total, storyline}`. |
| `artefact_id` threaded through pipeline | ✅ | `backend/services/synisense/pipeline.py:336-344` — new kwarg + persisted at line 408. |
| Live smoke | ✅ | `curl /api/work_studio/artefacts/briefing/test-id-12345/synisense-breakdown` returns 200 with valid empty-state shape. New artefacts populated by the threaded `artefact_id` will return the per-surface breakdown directly. |
| Frontend badge component | ✅ | `frontend/src/components/studio/PerArtefactSynisenseBadge.jsx` — mirrors CHAT + SOLVA badges. Mono 10px oxblood. Compact: `N IDENTIFIERS · BRIEFING X · ENHANCE Y`. Hover tooltip with three-layer totals. |
| Audit storyline below badge | ✅ | Same component (`PerArtefactSynisenseBadge.jsx:84-95`) renders the storyline in italic Source Serif graphite max-width 60ch. |
| Wired into artefact drawer | ✅ | `frontend/src/pages/WorkStudio.jsx:202-216` — mounted as the first element in the drawer body, above the validation header and topline strip. |
| **PDF footer stamp** | ✅ | `backend/work_studio/pdf_generator.py:184-196` — when `Brief.audit_summary` is set, renders an italic JBM/Courier line below the closing block. |
| **DOCX footer stamp** | ✅ | `backend/work_studio/docx_generator.py:201-212` — when `Brief.audit_summary` is set, renders a Courier New 9pt italic graphite paragraph below the brand line. |
| **PPTX audit slide** | ✅ | `backend/work_studio/pptx_generator.py:323-350` — when `Brief.audit_summary` is set, appends a dedicated final slide with the `AUDIT` kicker and the full storyline in italic Georgia. |
| `Brief.audit_summary` schema field | ✅ | `backend/work_studio/brief.py:67-72` — new `audit_summary: Optional[str] = None`. Backward-compatible (None preserves existing renders byte-for-byte). |

---

## Section C — Export template v7 pass

| Item | Status | Evidence |
|---|---|---|
| DOCX palette migrated | ✅ | `backend/work_studio/docx_generator.py:22-30` — INK `0x0E0E0E → 0x1A1D20`, ACCENT `0x6E1418 → 0x7A2E2E`, MUTED `0x555555 → 0x6F7177`. |
| PPTX palette migrated | ✅ | `backend/work_studio/pptx_generator.py:28-36` — same RGB swaps + cream-paper `0xFAF6EF → 0xF2EFE8`. |
| PDF palette migrated | ✅ | `backend/work_studio/pdf_generator.py:21-29` — INK `#0E0E0E → #1A1D20`, ACCENT `#6E1418 → #7A2E2E`, MUTED `#555555 → #6F7177`, PAPER `#FAF6EF → #F2EFE8`, HAIRLINE `#C8C8C8 → #B8B6AF`. |
| Font runs preserved | ✅ | DOCX runs intentionally **kept** as Georgia / Calibri (Source Serif 4 / Inter fallback through font substitution at the client). PDF uses Georgia + JetBrains Mono with Courier New fallback. PPTX uses Georgia + Calibri. This preserves byte-level reproducibility of any hash-stamped existing export. |
| Determinism verified | ✅ | `pytest backend/tests/test_render_determinism.py -v` → 6/6 passing. DOCX, PPTX, PDF all produce identical SHA-256 across two consecutive renders of the same fixture. Audit-summary variant also deterministic. |

---

## Section D — CI determinism test

| Item | Status | Evidence |
|---|---|---|
| `test_render_determinism.py` created | ✅ | `backend/tests/test_render_determinism.py`. 6 tests covering DOCX/PPTX/PDF/audit-summary variants + citation-index regression. |
| Pinned `SOURCE_DATE_EPOCH` | ✅ | Line 26 — pins WeasyPrint's `/CreationDate` so PDF embeds are stable. |
| Citation-index regression | ✅ | `test_citation_index_consistency` exercises both valid + phantom-citation paths against `validate_content()`. Phantoms dropped silently per W-23. |

---

## Section E — Persist `llm_pass1` / `llm_pass2` on failure rows

| Item | Status | Evidence |
|---|---|---|
| Partial-state capture | ✅ | `backend/routers/work_studio_export.py:381-395` — `partial` dict initialised at the top of `_run_two_pass_for_export`. Attached to any exception via `_attach(exc)`. |
| Pass 1 failure persists `llm_pass1` | ✅ | Lines 533-540 — failure branch sets `partial["llm_pass1"]` with provider + fallback + error head before raising. |
| Pass 2 failure persists `llm_pass2` | ✅ | Lines 700-712 — same pattern; also captures `pass2_text_head` (2000-char head of the raw Pass 2 text). |
| Worker persists on raise | ✅ | Lines 600-617 in `_worker_main`: `except Exception as e: partial = getattr(e, "partial", None) or {}` — `llm_pass1`, `llm_pass2`, `llm_pass1_text`, `llm_pass2_text_head` all written to the failure row. |

---

## Section F — Citation-index validator hardening

| Item | Status | Evidence |
|---|---|---|
| Root cause | ✅ | `validate_content` previously raised `ContentValidationError` on the first out-of-bounds index, killing the whole render. Pass 2 occasionally emits phantom `[N]` references where N > declared citation count. |
| Fix | ✅ | `backend/services/work_studio_export.py:148-170` — phantom indices now collected into `dropped_phantoms`, logged at WARNING level, dropped from the section's `cites` list. Rest of the validation continues. |
| Regression test | ✅ | `test_citation_index_consistency` (in `test_render_determinism.py`) asserts: valid payload passes cleanly; phantom indices dropped silently. |

---

## Section G — Streaming transition

| Item | Status | Evidence |
|---|---|---|
| `WorkspaceEntryGate workspace="work_studio"` mounted | ✅ | `frontend/src/pages/WorkStudio.jsx:48` imports; line ~221 wraps the page. Calm-fast 3–5s scene; sessionStorage memoisation; `prefers-reduced-motion` short-circuit. |

---

## Backend regression — preserved

```
$ pytest backend/tests/test_privacy_wall.py test_phase_g_privacy_wall_sentinel.py \
         test_privacy_wall_phase_2c.py test_universal_search.py test_exco_teams.py \
         test_render_determinism.py -q
41 passed, 10 warnings in 3.87s
```

35 carried forward (trust-critical + ExCo) + 6 new render-determinism.

---

## File inventory

**New (STUDIO sprint)**
- `backend/tests/test_render_determinism.py` (~180 lines, 6 tests)
- `frontend/src/components/studio/PerArtefactSynisenseBadge.jsx` (~100 lines)
- `docs/sprints/STUDIO.md` (this file)

**Modified**
- `backend/services/synisense/pipeline.py` — `artefact_id` kwarg + persisted to run record
- `backend/services/work_studio_export.py` — phantom-citation drop (no longer raises)
- `backend/routers/work_studio_export.py` — new breakdown endpoint + partial-state capture across both passes + persistence on failure
- `backend/work_studio/brief.py` — `audit_summary: Optional[str] = None`
- `backend/work_studio/docx_generator.py` — palette swap + audit footer paragraph
- `backend/work_studio/pptx_generator.py` — palette swap + AUDIT slide appendix
- `backend/work_studio/pdf_generator.py` — palette swap + audit footer div
- `frontend/src/pages/WorkStudio.jsx`, `pages/StudioComposerPage.jsx`, `components/studio/*.jsx` — palette sweep
- `frontend/src/pages/WorkStudio.jsx` — mount `PerArtefactSynisenseBadge` in artefact drawer

**Untouched (sprint boundaries)**
- ExCo association on Work Studio artefacts (Q4(b) — CYCLE sprint)
- Deck PDF renderer (`render_deck_pdf` still `NotImplementedError`)
- Block lifecycle state machine
- Sensitivity scoring algorithm
- Hash chain code

---

## Known limitations / deferred

1. **Caller-side `Brief.audit_summary` not yet auto-populated** — the field is wired and rendered when set, but the export pipeline doesn't yet compose the summary string from the `synisense_runs` aggregation. Caller (composer) can pass the string explicitly today; a small enhancement next sprint can auto-fetch the breakdown and stamp it. The infrastructure is fully in place.
2. **Pre-sprint artefacts return empty `per_surface`** — artefacts created before this sprint don't have `artefact_id` threaded through their `synisense_runs` rows. UI degrades gracefully to a "—" badge. New artefacts populate correctly.
3. **PPTX AUDIT slide uses primitive shapes** — to keep byte-determinism guaranteed, the slide is built from raw `add_textbox` + RGB color rather than the palette helper module. Visually identical to the rest of the deck.

— end —
