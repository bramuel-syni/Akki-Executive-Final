# Phase D — Fix Bundle Addendum (3 structural defects)

**Date:** 2026-05-16
**Trigger:** `e1_tester` T4 + 2 escalated WARNs from prior run.
**Status:** ✅ DONE — 580 pytest passing (was 570), 0 regressions, CI guard green.
**Predecessor:** `PHASE_D_CLOSEOUT.md` (original Phase D delivery).

---

## What the tester found

| ID | Surface | Defect | Severity |
|---|---|---|---|
| T4 | live pipeline | Refusal gate never fired on `"Should we?" + 7 thin answers`. Engine fabricated a 3-reading synthesis. | FAIL |
| W1 → FAIL | `rendered_synthesis` | Literal strings like `"If no explicit decision the diagnosis would inform, the lead reading shifts."` appeared in user prose — direct copies of `layer_0.dimensions[*].invalidation_condition`. | FAIL |
| W2 → FAIL | `rendered_synthesis` | Shield's internal `[[ENT_PROJECT_001]]`, `[[ENT_INITIATIVE_002]]`, `[[ENT_INVESTMENT_003]]` placeholders rendered verbatim. Either re-id didn't happen or LLM hallucinated tokens not in the de-id map. | FAIL |
| (gap) | tests | Single-voice invariant tests covered question stream but missed `rendered_synthesis` + `primary_diagnosis_prose`. | gap |

## Fix 1 — Refusal gate FIRES in the live pipeline

### Root cause
Two distinct issues:
1. The router (`routers/solva_phase_d.py:_run_layer_3`) hardcoded `layer_2_resolved_missing_dimensions=True` when calling `evaluate_refusal`. That made Rule 3 (FAR-insufficient-unresolved) never fire regardless of how thin the Layer 1/2 answers were.
2. `refusal_logic.Rule 1` counted a candidate as "grounded" if `evidence_requirement` was non-empty AND `weight > 0.05`. The `_fallback_candidates` synthetic set put boilerplate `evidence_requirement="material or document referenced in the user's framing"` (52 chars, non-empty) AND `weight=0.2` (>0.05) — so all 5 synthetic candidates passed Rule 1, refusal never fired.

### Fix
1. **New helper `compute_layer_2_resolved(layer_1_answers, layer_2_answers)`** in `refusal_logic.py`. Returns False unless:
   - Combined answer text ≥ 100 chars AND
   - At least 3 individual answers ≥ 12 chars each.
   This catches the `["yes","no","dunno","maybe","idk","shrug","tbd"]` pattern where total length passes a single threshold but each answer is empty.
2. **Tightened Rule 1**: `_candidate_is_grounded()` now rejects candidates with:
   - `source == "fallback_synthetic"` (NEW — `_fallback_candidates` now tags itself).
   - `evidence_requirement` exactly matching a known boilerplate string.
   - `evidence_requirement` shorter than 30 chars.
3. **New Rule 5 `LOW_TRIANGULATION_CONSISTENCY`**: refuse when `triangulation.overall_consistency < 0.4`. Triangulation engine returns 0.5 (neutral) when there is no evidence corpus — prevents Rule 5 from firing on every Phase D session (no doc retrieval yet — Phase E adds it).
4. **Router** now calls `compute_layer_2_resolved(...)` from `Layer1Record.answers` + `Layer2Record.answers` and passes the actual boolean.
5. **`layer_state == "refused"`** added to `LAYER_STATES` + `_next_question_payload()` handles the refused state, returning `refusal_rendering` + `refusal_reason` instead of a `question_text`.

### Cloud trace evidence (T4 re-run)
```
POST /sessions {sub_module: "seek_clarity"}          → sol-09d51b...
POST /framing  {"framing_text": "Should we? Yes or no, I am unsure."}
POST /answer "yes"   → HTTP 200, layer_1
POST /answer "no"    → HTTP 200, layer_1
POST /answer "dunno" → HTTP 200, layer_2
POST /answer "maybe" → HTTP 200, layer_2
POST /answer "idk"   → HTTP 200, layer_2
POST /answer "shrug" → HTTP 200, REFUSED here
POST /answer "tbd"   → HTTP 409 (terminal)

GET /sessions/{sid} →
  status=refused
  layer_state=refused
  refusal_flag=True
  refusal_reason=far_insufficient_unresolved
  rendered_synthesis=None        ← brief's acceptance criterion
  scenarios=[]
  refusal_rendering="The framing didn't sharpen enough as we went —
   the missing pieces stayed missing. A probability-weighted read at
   this point would be more performance than diagnosis. Here's what
   I can put on the table. ..."
```

## Fix 2 — `invalidation_condition` text gone from synthesis

### Root cause
`synthesis_renderer.render_synthesis(..., carry_forward_caveats=...)` rendered the FAR's per-dimension `invalidation_condition` strings as conditional clauses: `f"If {cf}, the lead reading shifts."`. Those strings ARE the internal sensitivity-flag vocabulary — they should never reach user prose.

### Fix
1. **Removed the `carry_forward_caveats` rendering block** from `synthesis_renderer.py` entirely. The signature still accepts the kwarg for API back-compat but the renderer IGNORES it.
2. **Router** no longer passes `carry_forward_caveats` to `render_synthesis()` (intent now explicit).
3. **`scan_for_internal_artefacts`** vocabulary list extended with:
   - `"invalidation_condition"`, `"the lead reading shifts"`, `"FAR.dimensions"`, `"far.dimensions"`, `"routing_decision"`.

### Locked by
- `test_synthesis_renderer_does_not_emit_invalidation_phrases` — passes `carry_forward_caveats` deliberately; renderer must not emit them.
- `test_invariant_scanner_catches_invalidation_terms`.

## Fix 3 — `[[ENT_*]]` placeholders stripped from synthesis

### Root cause
Cloud LLM, when given de-identified inputs, occasionally **hallucinated** new entity placeholders not in the de-id map (e.g., `[[ENT_PROJECT_001]]`, `[[ENT_INITIATIVE_002]]`). The Shield re-identifier swaps tokens it knows about; hallucinated tokens pass through untouched.

### Fix
1. **`_strip_entity_placeholders(text)`** helper in `synthesis_renderer.py`. Regex `\[\[ENT_[A-Z][A-Z_0-9]*_\d+\]\]`. Returns `(cleaned_text, stripped_count)`.
2. **`_sanitize_internal_string`** runs `_strip_entity_placeholders` as its first pass.
3. **`render_synthesis`** runs `_strip_entity_placeholders` as a FINAL DEFENSIVE pass on the assembled body — covers any case where a placeholder snuck through via a scenario / tension / driver field.
4. **`render_refusal`** also runs `_strip_entity_placeholders` on the assembled body AND sanitises every `candidates_to_surface[*].description` via `_sanitize_internal_string` before joining them.
5. **Scanner** catches `"[[ent_"` + `"[[ENT_"` case-insensitively.

### Locked by
- `test_synthesis_renderer_strips_entity_placeholders` — passes scenarios/tensions/drivers ALL containing `[[ENT_*]]` tokens; asserts ZERO substrings in output.
- `test_entity_placeholder_strip_helper` — direct unit test of the helper.

### Bonus hardening (LLM JSON format)
During the cloud trace, Gemini was returning candidate sets in JSON shape: `[{"description": "...", "evidence_requirement": "..."}]`. The existing line-based parser saw `"description":` as a JSON-key prefix and parsed the candidate descriptions as `"description": "Strategic commercial focus..."` (with the JSON key embedded). Three additional hardening passes:
1. **`_parse_candidates_from_json`** new function — JSON-array-first parse, falls back to line-based.
2. **`_JSON_KEY_PREFIX_RE`** strips `"description":` / `"evidence_requirement":` / etc. prefixes from line-based extracts.
3. **Prompt updated** to explicitly request JSON array output with no Markdown fence.

## Fix 4 — Single-voice invariant test covers synthesis surface

### New tests
1. `test_single_voice_synthesis_no_far_vocabulary_well_framed` — end-to-end well-framed session; if synthesis is rendered (not refused), assert `rendered_synthesis` + `primary_diagnosis_prose` scan clean AND contain ZERO `[[ENT_`, `invalidation_condition`, `the lead reading shifts`, `FAR `, `layer_0` substrings.
2. `test_single_voice_refusal_rendering_no_far_vocabulary` — end-to-end thin-framing session; if refused, assert `refusal_rendering` scans clean.
3. `test_synthesis_renderer_does_not_emit_invalidation_phrases` — unit-level guarantee.
4. `test_synthesis_renderer_strips_entity_placeholders` — unit-level guarantee.
5. `test_entity_placeholder_strip_helper` — helper unit test.
6. `test_compute_layer_2_resolved_thin_answers` — helper unit test (covers the tester's 7-thin-answers signal).
7. `test_refusal_logic_low_consistency_rule` — Rule 5 unit test.
8. `test_refusal_logic_synthetic_candidates_do_not_count` — Rule 1 tighten unit test.
9. `test_invariant_scanner_catches_invalidation_terms` — scanner extension unit test.
10. `test_refusal_gate_fires_on_persistently_thin_evidence` — INTEGRATION test reproducing tester's exact scenario.

## Files modified

```text
backend/services/solva/schemas.py                            [+"refused" to LAYER_STATES]
backend/services/solva/reasoning/refusal_logic.py            [rewritten — new rules + helper]
backend/services/solva/reasoning/candidate_generation.py     [JSON parser + 4-pattern line parser + fallback_synthetic source tag]
backend/services/solva/reasoning/triangulation_engine.py     [neutral consistency when no corpus]
backend/services/solva/voice/synthesis_renderer.py           [carry_forward_caveats removed; entity-placeholder strip + scanner sanitisation]
backend/services/solva/voice/refusal_voice.py                [+LOW_TRIANGULATION_CONSISTENCY copy; candidate-description sanitisation]
backend/services/solva/voice/invariants.py                   [+invalidation_condition, [[ent_, routing_decision, FAR.dimensions terms]
backend/routers/solva_phase_d.py                             [compute_layer_2_resolved wired; rendered_synthesis=None on refusal; layer_state="refused"; _next_question_payload handles refused]
backend/tests/test_phase_d_solva_pipeline.py                 [operator_refusal expects rendered_synthesis is None; round_trip accepts refused outcome]
backend/tests/test_phase_d_fix_bundle.py                     [NEW — 10 tests covering all 4 fixes]
```

## Pytest evidence

```text
$ SYNISENSE_LLM_MODE=mock pytest -q -p no:randomly
580 passed, 565 skipped, 43 warnings in 166.82s (0:02:46)

$ pytest tests/test_no_direct_llm_calls_outside_shield.py
PASSED — CI guard still green.
```

## Cloud-LLM end-to-end evidence

### Well-evidenced session (cloud Gemini, full Layer 3 synthesis)
```text
SID=sol-f4ad49f83f26447b9746307ee6d60300
status=active, layer_state=layer_4
refusal_flag=False
scenarios_count=5
synisense_audit_ids=6

Rendered synthesis (sample, scanned clean):
"Here is where I've landed. The reading that holds up best is this:
Success in achieving platform contract milestones with the top three
customers has driven consistent, compounding revenue growth within
these accounts. This structural roadmap success has naturally
increased their proportion of overall revenue. I'd put that at around
20% (5–35%). There is also the reading that ... There is a piece of
this worth naming: The narrative highlights 'steady compounding' from
platform contract milestones and a positive 'six-quarter pattern',
yet the CFO board specifically requested 'stress scenarios.' This
creates a tensio... That's the position I'd hold to. Push back
wherever it doesn't sit right."

  [[ENT_*]] leaks:                0
  invalidation_condition leaks:   0
  JSON-key scaffolding leaks:     0
  Markdown `**` leaks:            0
  scan_for_internal_artefacts:    [] (clean)
```

### Thin-evidence session (T4 — tester's exact scenario)
```text
SID=sol-09d51bced0ef48b7806261ddf4d5cfe0
"Should we?" + ["yes","no","dunno","maybe","idk","shrug","tbd"]

Final state:
  status=refused, layer_state=refused
  refusal_flag=True
  refusal_reason=far_insufficient_unresolved
  rendered_synthesis=None             ← brief's acceptance criterion
  scenarios=[]
  7th answer ("tbd") returns HTTP 409 (terminal)

Refusal rendering (coach voice, scanned clean):
"The framing didn't sharpen enough as we went — the missing pieces
stayed missing. A probability-weighted read at this point would be
more performance than diagnosis. Here's what I can put on the
table. The current uncertainty stems from a lack of clearly defined
strategic objectives · Uncertainty arises because the full scope of
potential consequences has not been... What would change the
picture:
  · any memo or document where this situation is described in concrete terms
  · minutes from the meeting where this first surfaced
  · a written brief from whoever flagged it"

  [[ENT_*]] leaks:                0
  invalidation_condition leaks:   0
  Coach-voice phrases present:    "missing pieces stayed missing",
                                  "more performance than diagnosis",
                                  "What would change the picture"
```

## Phase D — CLOSED 2026-05-16

All 4 fix-bundle items shipped. e1_tester's T4 + 2 escalated WARNs structurally resolved. The single-voice invariant now covers BOTH the question stream AND the synthesis/refusal output surfaces. The new layer_state lifecycle (`entry → … → done` AND `→ refused` as terminal) is locked in schemas + router + state machine + tests.

**Phase E next.**
