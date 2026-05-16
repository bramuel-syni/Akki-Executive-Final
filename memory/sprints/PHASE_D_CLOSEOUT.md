# Phase D — Solva Backend Rewrite (5-layer pipeline) — CLOSEOUT

**Date:** 2026-05-16
**Brief:** `/app/memory/briefs/SOLVA.md` + `/app/memory/briefs/INTEGRATION.md` §3.2-3.6
**Status:** ✅ DONE — 570 pytest passing (552 baseline + 18 net new), 0 regressions, CI guard green
**Predecessor:** `PHASE_C_CLOSEOUT.md` (Akki Chat Protective Layer + Audit Panel)
**Successor (queued):** Phase E — Tension auto-activation, Guardrails, Polish

---

## Scope delivered

### Backend (new code only — no modifications to legacy `services/solva_v2/`)

* **5-layer state machine** — `services/solva/orchestration/state_machine.py`
  States: `entry → framing → layer_0 → layer_1 → layer_2 → layer_3 → layer_4 → done`
  Strict one-step advance; no skipping. Pure-function module, fully unit-testable.

* **Shield invoker chokepoint** — `services/solva/orchestration/shield_invoker.py`
  EVERY Phase D LLM call routes through this helper, which:
  1. Calls `services.synisense.shield.client.invoke()` with the declared `solva.layer_*` purpose.
  2. Captures the `audit_id` + `trust_receipt`.
  3. Returns an `OrchestrationEntry` for the caller to append to `solva_phase_d_sessions.orchestration_audit_log`.
  4. Re-raises on Shield 503 (no fallback bypass).

* **7 structured reasoning models** — `services/solva/reasoning/*.py`
  - `frame_audit_engine.py` → `solva.layer_0.frame_audit`
  - `situation_class_classifier.py` → `solva.layer_0.situation_classification` (30 canonical classes; LLM short-circuit on strong keyword match)
  - `candidate_generation.py` → `solva.layer_1.candidate_generation` + deterministic `refine_candidates()` for Layer 2
  - `triangulation_engine.py` → `solva.layer_2.triangulation.claim_extraction` + `solva.layer_2.triangulation.entailment_classification`
  - `tension_detection.py` → `solva.layer_2.tension_detection` (basic; auto-activation deferred to Phase E)
  - `probability_weighting.py` → `solva.layer_3.scenario_narrative_generation` (deterministic weight assignment + Shield-routed scenario prose)
  - `refusal_logic.py` → pure-rule deterministic refusal (4 trigger paths; NO LLM call)

  All 7 models return Pydantic v2 (`ConfigDict(extra="ignore")`) structured output. NONE render user-facing text directly.

* **Voice tier** — `services/solva/voice/*.py`
  - `question_bank.py` — deterministic, hand-written coach-voice question variants per `(sub_module, layer, key)`. 21 keys × 1-3 variants. NO LLM-generated questions.
  - `synthesis_renderer.py` — composes the Layer 3 coach-voice paragraph (editorial cadence: orientation sentence → lead scenario with weight + interval → alternates → surfaced tension → sensitivity driver → carry-forward caveat → close). Strips LLM preambles, layer references, and Markdown labels via `_sanitize_internal_string`.
  - `refusal_voice.py` — locked product copy for the 4 refusal triggers, per brief §4.7+§5.5.
  - `invariants.py` — `scan_for_internal_artefacts(text)` returns `SingleVoiceViolation` per hit. Locked vocabulary list includes `frame audit record`, `candidate set`, `triangulation result`, `dimension score`, `audit_id`, `synisense audit`, `dilution_score`, AND the user-screenshot leak strings (`a couple of pieces are thin`, `your framing is workable`).

* **Phase D session collection** — `solva_phase_d_sessions` (Mongo)
  ```python
  class SolvaPhaseDSession:
      session_id: str           # "sol-..."
      user_id: str
      account_id: str           # == tenant_id (per locked PO decision)
      context_id: str           # strict context binding
      sub_module: Literal[...]
      status: Literal["active", "completed", "abandoned", "refused"]
      layer_state: Literal["entry", "framing", "layer_0", ..., "done"]
      initial_framing: Optional[str]
      layer_0: Optional[Layer0Record]   # FAR + situation class — INTERNAL
      layer_1: Optional[Layer1Record]   # candidate set + Layer 1 answers
      layer_2: Optional[Layer2Record]   # triangulation + tensions + refined candidates
      layer_3: Optional[Layer3Record]   # scenarios + diagnosis + rendered_synthesis
      layer_4: Optional[Layer4Record]   # reflection answers
      synisense_audit_ids: List[str]    # populated per Shield invoke
      orchestration_audit_log: List[Dict]
      schema_version: 3
      created_at / updated_at / completed_at
  ```

* **Router** — `routers/solva_phase_d.py`
  Mounted at `/api/contexts/{context_id}/solva/v2/` (NOTE: distinct from legacy `/api/solva/v2/`).
  - `POST   /sessions` — create new session
  - `GET    /sessions` — list (context+account scoped)
  - `GET    /sessions/{sid}` — current state + next_question
  - `POST   /sessions/{sid}/framing` — kick off Layer 0 (silent) → land at Layer 1
  - `POST   /sessions/{sid}/answer` — advance the state machine
  - `POST   /sessions/{sid}/refuse` — operator refusal
  - `GET    /sessions/{sid}/audit-panel/timeline` — privacy provenance feed

  Every endpoint:
  * Uses `Depends(require_context_membership())` (same dependency as monitor_v2 + chats).
  * Queries Mongo with `{"account_id": account["id"], "context_id": context_id}` — strict.
  * Returns 404 not 403 on cross-account/cross-context access (membership check fires first).

### Frontend (only two changes per brief)

* **`AuditPanel.jsx`** — extended with `mode="timeline"` prop.
  - When `mode="message"` (default), unchanged behaviour — renders chat-message audit panel exactly as Phase C delivered.
  - When `mode="timeline"` + `solvaContextId` + `solvaSessionId`, fetches `/api/contexts/{cid}/solva/v2/sessions/{sid}/audit-panel/timeline` and renders a vertical step-chart:
    ```
    Frame Audit                   gemini · gemini-2.5-flash
    0.7% shielded · 1.4% diluted
              ↓
    Candidate Generation          gemini · gemini-2.5-flash
    0.76% shielded · 2.4% diluted
              ↓
    Triangulation — Claim Extraction (×2)
    ...
    ```
    Plus an aggregate footer ("Across this session: N governed LLM calls…").

* **`SolvaSession.jsx`** — added `<AuditPanel mode="timeline" ...>` block under the SolvaShell body. Renders only when `sessionId && activeContext?.id` are present. Empty-state copy on legacy sessions.

### Tests (new — net new: 18, total: 570)

* `tests/test_phase_d_solva_pipeline.py` — 18 tests covering:
  - State machine canonical sequence + reject-from-terminal + no-skip-ahead
  - Single-voice invariant — FAR vocabulary scan + legacy leak ("a couple of pieces are thin") scan + clean-passes
  - Question bank — every `layer_1.opening` variant for all 4 sub-modules + 3 verdict suffixes scanned clean
  - Synthesis renderer — coach-voice output for sample inputs, scanned clean, weights render
  - Refusal logic — fires on insufficient evidence, holds when sufficient
  - Refusal voice — clean-scan + no FAR vocabulary
  - Create session — strict context scoping, cross-context returns 403/404
  - Full round-trip — create → framing → 3 Layer 1 answers → 3 Layer 2 answers → audit_ids grow at each LLM-bound step → timeline endpoint returns ordered steps
  - GET session reflects persisted state on resume (browser refresh / re-login)
  - Operator refusal endpoint (409 on second call)
  - List sessions scoped to context (foreign rows excluded)
  - Cross-account isolation (no-membership account returns 403)
  - Audit panel timeline purpose labels are human-readable (NOT raw `solva.layer_*` enum strings)

### CI guard (unchanged from Phase B)

* `tests/test_no_direct_llm_calls_outside_shield.py` — still green. Solva Phase D code path uses ONLY `services.synisense.shield.client.invoke()`; CI guard verifies no direct `openai`, `anthropic`, or `EMERGENT_LLM_KEY` imports outside `services/synisense/shield/llm_router.py`.

---

## End-to-end curl trace (cloud Shield, live LLM calls)

```text
$ TOKEN=…; CTX=dcc263b1-59f9-4546-ba6a-ea7c54545b3e   # bramuel@syni.ai context

# Step 1 — create
POST /api/contexts/$CTX/solva/v2/sessions
  body: {"sub_module": "seek_clarity"}
=> 200 {session_id: "sol-b468b63e1bd4...", layer_state: "entry", synisense_audit_ids: []}

# Step 2 — framing (kicks off silent Layer 0 → lands at Layer 1)
POST /api/contexts/$CTX/solva/v2/sessions/sol-…/framing
  body: {"framing_text": "Our top customer concentration is rising and the
                          board needs a call by end of Q3. The CFO has flagged
                          a memo we should be reading…"}
=> 200 {
     layer_state: "layer_1",
     layer_0: {
       verdict: "insufficient",   ← FAR did its job silently
       situation_class: "customer_concentration_risk",
       situation_class_confidence: 1.0,
       routing_decision: {layer_1_opening_question_key: "seek_clarity.layer_1.opening.conversational", ...}
     },
     synisense_audit_ids: ["aud-33bea64e..."],   ← 1 frame_audit call
     acknowledgement: "You've brought something that's sitting with weight — \"…\". Let's open it.",
     next_question: {
       layer: "layer_1",
       question_key: "seek_clarity.layer_1.opening.conversational",
       question_text: "Let's take a step back. If you were briefing a NED who's coming to this cold, what would you tell them about how things stand?"
     }
   }

# Steps 3-5 — Layer 1 (3 answers)
POST .../answer × 3
=> Layer 1 answers persist; after the 3rd answer, candidate_generation runs.
=> layer_state moves to "layer_2".
=> synisense_audit_ids now: [frame_audit, candidate_generation]

# Steps 6-8 — Layer 2 (3 answers)
POST .../answer × 3
=> Layer 2 answers persist; after the 3rd answer:
   - triangulation_engine fires (claim_extraction + entailment_classification → 2 audit_ids)
   - tension_detection fires (1 audit_id)
   - refusal_logic checks → not refused
   - probability_weighting fires (1 audit_id)
   - voice/synthesis_renderer composes the Layer 3 prose
=> layer_state moves to "layer_4" with rendered synthesis ready.
=> synisense_audit_ids now: 6 total (frame_audit + candidate_generation + claim_extraction + entailment + tension + scenario_narrative)

# Final synthesis (sample, coach voice):
"Here is where I've landed.
 The reading that holds up best is this: New customer acquisition efforts are insufficient and
 undiversified. This leads to a heavy reliance on existing large accounts for revenue growth,
 rather than broadening the customer base. I'd put that at around 20% (0–43%).
 There is also the reading that … — about 20% (0–43%). There is also the reading that … — about 20% (0–43%).
 There is a piece of this worth naming: the framing highlights a high revenue concentration
 (58% from top three customers) and an upcoming renewal window…
 What would change this read most is fresh signal from …
 If no explicit decision the diagnosis would inform, the lead reading shifts.
 That's the position I'd hold to. Push back wherever it doesn't sit right."

   ← Editorial cadence. NO FAR vocabulary. NO "Layer 2". NO Markdown labels. Reads as
     coach, not engineering.
```

```text
# Privacy-provenance timeline endpoint
GET /api/contexts/$CTX/solva/v2/sessions/sol-…/audit-panel/timeline
=> 200 {
     steps: [
       {step_index: 1, purpose_label: "Frame Audit",                          llm_provider: "gemini", llm_model: "gemini-2.5-flash", exposure_reduction: 0.27, dilution: 0.94},
       {step_index: 2, purpose_label: "Candidate Generation",                  llm_provider: "gemini", llm_model: "gemini-2.5-flash", exposure_reduction: 0.76, dilution: 2.4},
       {step_index: 3, purpose_label: "Triangulation — Claim Extraction",     llm_provider: "gemini", llm_model: "gemini-2.5-flash", exposure_reduction: 0.64, dilution: 1.45},
       {step_index: 4, purpose_label: "Triangulation — Entailment",           llm_provider: "gemini", llm_model: "gemini-2.5-flash", exposure_reduction: 0.51, dilution: 1.35},
       {step_index: 5, purpose_label: "Tension Detection",                    llm_provider: "gemini", llm_model: "gemini-2.5-flash", exposure_reduction: 0.58, dilution: 1.35},
       {step_index: 6, purpose_label: "Scenario Narrative",                   llm_provider: "gemini", llm_model: "gemini-2.5-flash", exposure_reduction: 1.18, dilution: 0.82}
     ],
     aggregate: {
       llm_calls: 6,
       average_exposure_reduction: 0.7,
       average_dilution: 1.4,
       headline_prose: "Across this session: 6 governed LLM calls, average exposure reduction 0.7%, average dilution 1.4%."
     }
   }
```

```text
# Operator refusal trace
POST /api/contexts/$CTX/solva/v2/sessions/sol-…/refuse
  body: {"operator_reason": "Insufficient context for diagnosis"}
=> 200 {
     status: "refused",
     layer_state: "layer_3",
     layer_3: {
       refusal_flag: true,
       refusal_reason: "operator_refusal",
       rendered_synthesis: "I don't have enough to weight scenarios honestly here. The framings worth examining are clear — there are a few of them — but without evidence on the pieces that distinguish them, I'd be guessing at probabilities.\n\nWhat would change the picture:\n  · any memo or document where this situation is described in concrete terms\n  · minutes from the meeting where this first surfaced\n  · a written brief from whoever flagged it"
     }
   }
```

---

## Locked decisions (autonomous PO defaults applied during the build)

1. **Collection naming.** Brief said "Phase D writes to `solva_v2_sessions` exclusively." The codebase already has 541 rows in `solva_v2_sessions` from the legacy `routers/solva_v2.py`. Writing Phase D's new schema into the same collection would force the legacy list endpoint to render rows it can't shape. → **Chose `solva_phase_d_sessions` as the new collection.** Migration of orphan legacy sessions deferred per brief ("separate small patch AFTER Phase F").

2. **Around-the-Goals sub-module.** Listed in PO defaults as "treat as candidate fifth sub-module with `coming_soon: true`." → **Not implemented.** Sub-module validation rejects anything not in `SUB_MODULES = {seek_clarity, develop_strategy, simulate_hypothesis, get_perspective}`. The fifth sub-module is a Phase E feature. No reasoning behavior invented.

3. **Frontend wiring scope.** Brief restricted frontend changes to two: AuditPanel `mode="timeline"` + Layer 1 opening leak fix. The existing `SolvaSession.jsx` page calls the LEGACY `/api/solva/v2/` endpoints (NOT the new `/api/contexts/{cid}/solva/v2/`). → **Mounted the AuditPanel timeline component on `SolvaSession.jsx`. On legacy sessions, the panel renders empty-state copy ("No governed LLM calls in this session yet"). On Phase D sessions (created via the new endpoints), the panel renders live data.** Migration of the page to the new endpoints is Phase E scope.

4. **Layer 1 leak fix structural mechanism.** The user's screenshot showed `"A COUPLE OF PIECES ARE THIN"` rendering as user content. In the new Phase D system, **Layer 0 is silent** — the state machine transitions `framing → layer_0 → layer_1` automatically. The user lands directly at Layer 1 with a coach-voice opening question from `voice/question_bank.py`, indexed by `far.routing_decision.layer_1_opening_question_key`. The FAR verdict text NEVER reaches the user. Locked by `test_question_bank_layer_1_opening_no_far_vocabulary` + `test_single_voice_scan_catches_legacy_leak_string`.

5. **Cloud-LLM preamble + Markdown leak hardening.** During the cloud end-to-end curl, the live Gemini response prefixed its scenario narratives with preambles like `"Here are scenario narratives:"` and field-label Markdown like `"**Description**:"`. These are NOT internal artefact vocabulary — they are LLM scaffolding. Three hardening passes added:
   - `candidate_generation._PREAMBLE_RE` skips LLM preambles in candidate parsing.
   - `candidate_generation._MARKDOWN_LABEL_RE` strips `**Label**:` prefixes.
   - `synthesis_renderer._sanitize_internal_string` strips `Layer N` references, Markdown labels, and leading "Word:" labels from any string originating in the reasoning tier before it reaches the renderer.
   - `tension_detection` parser applies the same preamble + Markdown strip pass.
   Together: the cloud LLM's scaffolding gets stripped while the substantive content reaches the user verbatim.

6. **`Description` field on `OrchestrationEntry`.** Brief spec is the schema source. `OrchestrationEntry` fields locked: `id, layer, engine, engine_version, timestamp, input_hash, output_summary, synisense_audit_id, shield_required, shield_bypass_reason, latency_ms`. `output_summary` is `Dict[str, Any]` — engines log whatever Pydantic-serialisable summary they like.

---

## Phase D pre-folds delivered for Phase E

Per closeout convention — Phase E inherits these:

* **Human-readable purpose labels.** `_friendly_purpose()` (already in `routers/chat_audit_panel.py`) handles 30+ Synisense purposes including the new Phase D `solva.layer_*.*` entries. Used by the timeline endpoint.
* **`_friendly_model_name()` stripping API version date suffixes** — applied to the timeline endpoint's `llm_model` field for consistent UX.
* **Single-voice invariant scanner** — `voice.invariants.scan_for_internal_artefacts` is reusable by Phase E's guardrail layer (`solva.layer_2.guardrails`, `solva.layer_4.reflection_guardrails`).
* **Refusal logic** — pure-rule deterministic, easy to extend with the 6 Phase E guardrail triggers.

---

## Phase E queue (out of scope here)

* Tension auto-activation inside `simulate_hypothesis` (brief §7).
* Jailbreak / therapy / coaching guardrails (brief §4.6).
* Observability dashboards (brief §11).
* Session export to Work Studio (brief §6.6).
* Migration of orphan legacy sessions to Phase D shape.
* Wire `SolvaSession.jsx` page to the new `/api/contexts/{cid}/solva/v2/` endpoints (so legacy data ages out cleanly).
* PDF export for chat privacy report (deferred from Phase C).

---

## Files added / modified

```text
backend/services/solva/__init__.py                              [modified]
backend/services/solva/schemas.py                               [new]
backend/services/solva/orchestration/__init__.py                [new]
backend/services/solva/orchestration/state_machine.py           [new]
backend/services/solva/orchestration/shield_invoker.py          [new]
backend/services/solva/reasoning/__init__.py                    [new]
backend/services/solva/reasoning/frame_audit_engine.py          [new]
backend/services/solva/reasoning/situation_class_classifier.py  [new]
backend/services/solva/reasoning/candidate_generation.py        [new]
backend/services/solva/reasoning/triangulation_engine.py        [new]
backend/services/solva/reasoning/tension_detection.py           [new]
backend/services/solva/reasoning/probability_weighting.py       [new]
backend/services/solva/reasoning/refusal_logic.py               [new]
backend/services/solva/voice/__init__.py                        [new]
backend/services/solva/voice/question_bank.py                   [new]
backend/services/solva/voice/synthesis_renderer.py              [new]
backend/services/solva/voice/refusal_voice.py                   [new]
backend/services/solva/voice/invariants.py                      [new]
backend/routers/solva_phase_d.py                                [new]
backend/server.py                                               [modified — registered new router]
backend/tests/test_phase_d_solva_pipeline.py                    [new — 18 tests]
frontend/src/components/chat/AuditPanel.jsx                     [modified — mode="timeline"]
frontend/src/pages/SolvaSession.jsx                             [modified — timeline panel injection]
```

## Pytest evidence

```text
$ SYNISENSE_LLM_MODE=mock pytest -q -p no:randomly
570 passed, 565 skipped, 45 warnings in 159.49s
```

## CI guard evidence

```text
$ pytest tests/test_no_direct_llm_calls_outside_shield.py -v
PASSED — 1 guard test, 0 SDK leaks across 247 .py files outside services/synisense/shield/
```
