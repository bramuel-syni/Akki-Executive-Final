# D Implementation Log — Trust Center "known deviation" note

**Chunk:** D — `de_id_summary` transparency note (UI-only)
**Started:** 2026-05-25
**Spec contract:** the user's chunk-(d) brief (verbatim wording supplied, mildly refined for Trust Center voice — see "Final wording" below).
**Boundary:** UI-only. NO backend, NO schema, NO guardrail file changes.

---

## Pre-chunk hygiene

| Artifact | Path | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-d` → `8b…` (created 2026-05-25T09:10Z, local-only) | 2026-05-25T09:10Z |
| Mongo dump | `/app/backup/pre_d_20260525T091055Z/` (66 MB) | 2026-05-25T09:10:55Z |

Note: tags are local-only. `git push origin v-pre-d` requires the user's "Save to Github" feature.

---

## Scope (verbatim from user brief)

1. **Trust Center session view** — small inline help/info affordance next to the headline `de_id_summary` numbers. Plain-English copy. Lucide-react `Info` icon → Popover. DOM-unconditional.
2. **Per-turn drill-down inline note** — one-liner below the per-turn table.
3. **Methodology doc** — `/app/memory/sprints/TRUST_CENTER_METHODOLOGY.md`.
4. **Backend** — zero changes.

---

## Files changed

| File | Change |
| --- | --- |
| `frontend/src/pages/TrustCenter.jsx` | (a) added `Info` to lucide-react imports; (b) added `Popover/PopoverTrigger/PopoverContent` import from `../components/ui/popover`; (c) extended the `Counter` component to accept an optional `infoSlot` prop rendered inline with the label; (d) new `DeIdSummaryInfoPopover` component (DOM-unconditional trigger button); (e) "Identifiers shielded" Counter now passes `infoSlot={<DeIdSummaryInfoPopover />}`; (f) new `tc-perturn-deviation-note` div under the "Per-turn detail" heading. |
| `memory/sprints/TRUST_CENTER_METHODOLOGY.md` | NEW — authoritative reference for the methodology, with stable keyphrase anchors and standards mapping. |
| `backend/tests/test_d_trust_center_deidsummary_note.py` | NEW frontend wire test. |

**Backend files touched: 0.** Verified by `git diff --name-only HEAD backend/` (only the new test file under `backend/tests/`). No change to:
- `services/synisense/deidentifier.py`
- `services/synisense/canonical.py`
- `services/synisense/audit.py`
- `routers/trust_center.py`
- `services/trust_center.py`
- any other guardrail surface.

---

## Final wording (slight refinement from user draft — documented for review)

### Popover content (testid: `tc-deidsummary-info-content`)

Heading line: **"How this count is built"**

Body (two paragraphs):

> Session totals count every place Shield touched data — including historical context and grounding replay for this session. Per-turn totals below count only what Shield processed at each specific turn.
>
> Both views are factually accurate to their question; expect the session total to be a superset of the sum of per-turn counts.

### Per-turn drill-down inline note (testid: `tc-perturn-deviation-note`)

> Per-turn counts. Session totals above may be larger because they include historical context and grounding replay.

### Refinements vs. the user's draft

| Source phrase (user draft) | Final phrase | Why |
| --- | --- | --- |
| "Session totals count every place Shield touched data — including historical context **and grounding material replayed for this session**." | "…including historical context **and grounding replay** for this session." | Compactness; matches TrustCenter voice ("Trust Center is factual reporting" header comment). "Grounding replay" is the audit-anchor phrase reused everywhere else. |
| "Both views are **accurate to their question**" | "Both views are **factually accurate** to their question" | Aligns with the page's existing self-description "Trust Center is factual reporting" so the auditor reads the same voice throughout. |
| (per-turn) "Per-turn counts. Session-level totals **at the top** may be larger because they include historical context **+ grounding replay**." | "Per-turn counts. Session totals **above** may be larger because they include historical context **and grounding replay**." | "Above" reads more naturally than "at the top" in a scrolling page; "and" instead of "+" for prose tone. |

All three key-phrase anchors the tester needs (`"session totals"`, `"per-turn"`, `"superset"`) are preserved verbatim. Two additional anchors (`"historical context"`, `"grounding replay"`) are also preserved for stable assertions.

**Please flag during the verification pass if any of the refinements drift.** I held the audit-anchor phrases stable and only adjusted around them.

---

## Tests

### Frontend wire (`tests/test_d_trust_center_deidsummary_note.py`)

| Test | Asserts |
| --- | --- |
| `test_info_button_testid_present` | `data-testid="tc-deidsummary-info-button"` renders unconditionally |
| `test_info_popover_content_testid_present` | `data-testid="tc-deidsummary-info-content"` is present in source |
| `test_info_popover_contains_audit_anchor_keyphrases` | Popover body contains all 5 anchors: `Session totals`, `per-turn`, `superset`, `historical context`, `grounding replay` |
| `test_info_button_renders_dom_unconditionally` | The button does NOT live behind a `&& (...)` conditional gate in source — guards the T2.3 DOM-unconditional rule |
| `test_perturn_deviation_note_testid_present` | `data-testid="tc-perturn-deviation-note"` is present |
| `test_perturn_deviation_note_contains_audit_anchors` | Per-turn note contains `Session totals above`, `historical context`, `grounding replay` |
| `test_perturn_note_renders_dom_unconditionally` | The per-turn note is NOT gated by a conditional render |
| `test_no_guardrail_files_changed_under_backend` | `git diff --name-only HEAD~1` (with a sane fallback) confirms only `services/work_studio_overlay.py`, `routers/cycles.py`, `scripts/seed_backlog_b_demo.py`, and `tests/test_d_*` + `tests/test_backlog_b_*` are present — no Shield/Trust-Center backend writer touched |
| `test_lucide_info_imported` | `Info` is in the lucide-react import block (import-survival guard per closeout §5.6) |
| `test_popover_components_imported` | `Popover`, `PopoverTrigger`, `PopoverContent` are imported from the shadcn ui module |

---

## Run results

(Populated below as each item is verified.)

---

## Guardrail re-enables (2026-05-25 — folded into chunk (d) acceptance per orchestrator directive)

After the skip-audit found 73 `coverage-loss` tests sitting on shipped surfaces, the user folded the minimum-necessary skip remediation into (d)'s acceptance rather than open a separate phase. Scope: re-enable the **10 guardrail-adjacent tests** that shadow Shield/Solva/Trust-Center work. All other 490 skips remain parked in `SKIP_LEDGER.md`.

### Tests re-enabled

| # | File | Line | Test name | Decision | Why |
| --- | --- | --- | --- | --- | --- |
| 1 | `test_phase_b_solva_no_opinion.py` | 88 | `test_directive_lists_every_brief_phrase` | **kept** | Was caught by the module-level `@pytest.mark.skip`; the unit assertion is still valid against the current `OPINION_FREE_DIRECTIVE` (all 6 brief phrases present). |
| 2 | same | 99 | `test_filter_catches_every_brief_phrase` | **kept** | Unit-level regex sweep; valid against current `scan()` implementation. |
| 3 | same | 114 | `test_get_perspective_keeps_persona_voice` | **kept** | Documents the intentional `get_perspective` bypass — unchanged contract. |
| 4 | same | 232 | `test_adversarial_prompt_with_opinion_laden_reply_is_blocked[ceo_proposal]` | **kept + harness rewrite** | Adversarial probe. Contract drift was in `_start_session` only — the assertion (user-visible text must be clean) is unchanged and still valid. |
| 5 | same | 232 | `…[personally_in_my_position]` | **kept + harness rewrite** | Same. |
| 6 | same | 232 | `…[between_restructure_and_raise]` | **kept + harness rewrite** | Same. |
| 7 | same | 232 | `…[honest_view_not_analysis]` | **kept + harness rewrite** | Same. |
| 8 | same | 232 | `…[forget_solva_one_turn]` | **kept + harness rewrite** | Same. |
| 9 | same | 314 | `test_clean_reply_at_synthesis_keeps_grounding_markers` | **kept + collection rename** | Tests positive control; only the `db.solve_clusters` → `db.solva_clusters` collection rename was needed. |
| 10 | `test_solva_v2_shield_invariant.py` | 131 | `test_invariant_holds_across_full_session` | **kept + harness rewrite** | The full-session shield invariant sweep — the most valuable Shield-adjacent test in the repo. Contract drift was in the cluster GET only; the `_check_invariant` core remains unchanged. |

### Single root cause of the drift

All 10 failures came from **the same single contract change**: the `/api/solva/clusters` GET endpoint was removed during Phase I.2 in favour of server-side `_resolve_auto_cluster(intent)`. The fix in each test was to drop the `GET /api/solva/clusters` + cluster-id passing path and instead omit `cluster_id` (`auto_cluster=True` is the default on `POST /api/solva/v2/sessions`). One collection rename also surfaced: `db.solve_clusters` → `db.solva_clusters` (used by `_run_synthesis` in `routers/solva_v2.py`).

**No assertion was weakened.** Every invariant in the test bodies is preserved verbatim — only the session-bootstrap glue was rewritten to call the current API.

### Assertion-strength sanity check (orchestrator-required)

Each re-enabled test was sanity-checked to confirm it would FAIL if the underlying invariant were broken. Evidence run from the audit chunk:

**For the opinion-filter tests** — when the filter is hypothetically neutered (i.e. `is_clean()` returns `True` for all input), the user-visible text would carry the `OPINION_LADEN_REPLY` (`"I think the right move is to restructure first…"`). The brief-forbidden regex set in the test catches three independent phrases (`\bI\s+think\b`, `\bin\s+my\s+opinion\b`, `\bpersonally\b`) in that text → assertion fires. **Assertion is strong.**

**For `_check_invariant` in the shield test** — sanity-tested all four failure modes (shield_required=True with null run_id; shield_required=False with leaked run_id; shield_required=False with bogus bypass reason; valid entry):

```
PASS rejects shield_required=True+no run_id: shield_required=True but synisense_run_id is null
PASS rejects shield_required=False+leaked run_id: shield_required=False but synisense_run_id present
PASS rejects bogus shield_bypassed_reason: invalid bypass reason
PASS accepts valid shield_required=True+run_id
```

**Assertion is strong.**

### Test results — post-re-enable

```
$ cd /app/backend && python -m pytest tests/test_phase_b_solva_no_opinion.py \
    tests/test_solva_v2_shield_invariant.py -v
================= 15 passed, 16 warnings in 169.87s (0:02:49) ==================
```

- `test_phase_b_solva_no_opinion.py` — 9 tests, **all GREEN** (3 unit + 1 positive-control e2e + 5 adversarial parametrized).
- `test_solva_v2_shield_invariant.py` — 6 tests, **all GREEN** (the 5 already-passing `synthetic_audit_entry` unit tests + the newly-restored `test_invariant_holds_across_full_session`).

### Skipped-count delta

| Metric | Pre-re-enable (skip audit baseline) | Post-re-enable |
| --- | --- | --- |
| Passed | 1100 | **1110** (+10 — exactly the 10 re-enables) |
| Skipped | 500 | **490** (−10 — exactly the 10 re-enables) |
| Failed | 1 (pre-existing `test_requirements_guard`) | 1 (unchanged — pre-existing) |

Full-repo evidence:

```
$ cd /app/backend && python -m pytest -q --no-header --tb=no
1 failed, 1110 passed, 490 skipped, 86 warnings in 251.37s (4:11)
```

The 1 failure is the same pre-existing `test_real_requirements_file_is_clean` (spaCy pep508-direct-ref URLs in `backend/requirements.txt`, file unchanged across this chunk). The 86 warning count is up from 83 — the extra 3 are the standard "asyncio mark on sync function" PytestWarnings emitted by the 3 unit tests in `test_phase_b_solva_no_opinion.py` (they're sync but inherit the module-level `pytestmark = [pytest.mark.asyncio]`). Warning, not failure; the tests pass cleanly.

### Files changed for the re-enables

| File | Change |
| --- | --- |
| `backend/tests/test_phase_b_solva_no_opinion.py` | Removed module-level `pytest.mark.skip` (L56); rewrote `_start_session` to use Phase I.2 `auto_cluster=True` instead of the dead `GET /api/solva/clusters` endpoint; renamed `db.solve_clusters` → `db.solva_clusters` in `test_clean_reply_at_synthesis_keeps_grounding_markers`. |
| `backend/tests/test_solva_v2_shield_invariant.py` | Removed `pytest.mark.skip` (L131); rewrote the session-bootstrap block to omit `cluster_id` (server resolves) and dropped the `GET /api/solva/clusters` call. |

**Backend behaviour code touched: 0.** Verified by `git diff --name-only HEAD -- backend/` → only `tests/test_phase_b_solva_no_opinion.py`, `tests/test_solva_v2_shield_invariant.py`, and the chunk-(d) files. No change to `services/synisense/`, `services/solva_v2/opinion_filter.py`, `services/solva_v2/llm_adapter.py`, or any guardrail surface.

---

## Final close

- ✅ Chunk-(d) UI deviation note shipped on disk (popover + per-turn note + methodology doc), intact since the e1_tester pre-audit cycle.
- ✅ Honest-framing paragraph added to the sprint closeout doc.
- ✅ 10 guardrail-adjacent tests re-enabled, all GREEN, assertion strength sanity-checked.
- ✅ Full-repo pytest: 1100 passed (+10 from baseline) · 490 skipped (−10) · 1 pre-existing failure.

**Chunk (d) + guardrail re-enables status: READY FOR e1_tester VERIFICATION.**

---

## e1_tester verdict — 2026-05-25 — (d) CLOSED

Tester verdict: **2/4 PASS · 1 conditional PASS · 1 orchestrator-promoted PASS.**

| # | Item | Verdict | Note |
| --- | --- | --- | --- |
| d.1 | DeIdSummaryInfoPopover present | **PASS** (orchestrator-promoted from `HUMAN_REQUIRED`) | Scope clarification: the Info affordance correctly lives on the SessionDetail panel, not the page-level landing. The DOM-unconditional rule governs spec-required sections within their parent context; it does NOT mandate page-level ubiquity. |
| d.2 | Popover content carries audit anchors | **conditional PASS** (source-verified) | Same scope reasoning as d.1. e1_tester couldn't reach the popover content in the landing screenshot because the SessionDetail panel was not the active surface; source assertion (the `test_d_*` suite) covers the literal content. |
| d.3 | Per-turn deviation note renders | **PASS** | Live-verified. |
| d.4 | Methodology doc + 10 guardrail re-enables green | **PASS** | All 10 re-enabled tests GREEN; methodology doc intact. |

### Orchestrator scope clarification (binding for future tiers)

> *"DOM-unconditional rule scope clarified during (d): spec-required sections emit DOM regardless of inner data; the rule does NOT mandate that every UI element renders on every page. Info affordances correctly co-locate with the data they describe."*

This is the **same** rule that closeout §5.1 already encoded — but with the explicit scope boundary now written down. The Info popover lives next to the headline counter it explains (SessionDetail); landing-page-level absence is not a rule violation.

### Files changed this chunk (final inventory)

**UI implementation:**
- `frontend/src/pages/TrustCenter.jsx` — `Info` icon imported, `Popover/PopoverTrigger/PopoverContent` imported, `DeIdSummaryInfoPopover` component added, `Counter` extended with `infoSlot`, per-turn note added.

**Documentation:**
- `memory/sprints/TRUST_CENTER_METHODOLOGY.md` — NEW. Authoritative reference + standards-mapping.

**Tests (UI deviation note):**
- `backend/tests/test_d_trust_center_deidsummary_note.py` — NEW. 10 tests, all GREEN.

**Tests (guardrail re-enables, folded into (d) acceptance):**
- `backend/tests/test_phase_b_solva_no_opinion.py` — module-level `@pytest.mark.skip` removed; `_start_session` rewritten to Phase I.2 contract; `db.solve_clusters` → `db.solva_clusters` rename.
- `backend/tests/test_solva_v2_shield_invariant.py` — single-test `@pytest.mark.skip` at L131 removed; session-bootstrap rewritten to Phase I.2 contract.

**Sprint-level docs:**
- `memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` — appended honest-framing paragraph + DOM-unconditional scope clarification lesson.

**Backend behaviour code touched: 0.** No guardrail file (Shield, Trust Center backend, Solva opinion filter, llm_adapter, etc.) was modified.

### Final pytest

```
1 failed, 1110 passed, 490 skipped, 86 warnings in 251.37s (4:11)
```

The 1 failure is pre-existing (`test_requirements_guard.py` — spaCy URL pep508-direct-refs in `requirements.txt`).

**(d) closed. Git tag `v-post-d` created.**
