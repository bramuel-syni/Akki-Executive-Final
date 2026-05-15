SOLVA
Developer Brief
Production specification
What this document is
The complete specification for Solva — Akki's structured-reasoning module. This document defines what Solva is, how it is built, how it integrates with Synisense Service, and what acceptance criteria apply at each phase of the build.
Audience
Engineering leads · Applied-AI engineers · Product managers · Designers
Companion documents
Synisense Service Brief — specifies the platform service Solva depends on. Akki Integration Brief — specifies how Solva and Synisense coordinate to deliver Akki's promise.

CONTENTS
# Contents
    Glossary of terms
1.  What Solva is
2.  Architecture
3.  The reasoning journey
4.  Reasoning models
5.  Voice and user experience
6.  Grounding and material handling
7.  Auto-activation in Simulate Hypothesis
8.  Guardrails
9.  Synisense integration
10. Build strategy and acceptance criteria

GLOSSARY
# Glossary of terms
This glossary is the canonical reference for naming. The same terms are used identically across the Solva, Synisense, Akki Chat, and Akki Service Integration briefs. Any apparent variation in this or sibling documents resolves to one of the definitions below.



SECTION 1
# What Solva is
Solva is the structured-reasoning module within Akki. An executive opens Solva when they need to think a situation through to a position — not when they want a quick answer. Solva walks them through a sequenced reasoning process, surfaces what they may not be seeing, and produces a diagnosis that is probability-weighted, evidence-grounded, and interrogable.
Solva exists because the alternative — using an LLM directly on consequential questions — produces three predictable failures. Users formulate hypotheses without structure and get answers that confirm the framing rather than test it. Users accept plausible-sounding outputs without checking the evidence. Users mistake fluency for diagnosis. Solva is the discipline that prevents these failures at the structural level.
## 1.1 Four sub-modules
- Seek Clarity — for when the user is unsure what is happening or what the right framing is. Solva runs the diagnostic that narrows candidate causes and surfaces underlying tensions.
- Develop Strategy — for when the user needs a direction and wants to test their thinking. Solva produces probability-weighted options with sensitivity analysis.
- Simulate Hypothesis — for when the user wants to stress-test an assumption before committing. Solva produces scenarios and their implications. Solva auto-activates inside this sub-module when it detects tension in the hypothesis statement, approach, or expected outcome.
- Get Perspective — for when the user wants to see a situation from a different business mind-frame: a CFO's view of a CEO question, an investor's view of a board paper, a counterparty's view of a negotiation.
## 1.2 Solva's place in Akki's promise
Akki promises that AI is safe and honest for enterprises. Synisense Service delivers the safe — structural privacy, governance, de-identification, audit. Solva delivers the honest — refusal when evidence is thin, grounding on user material rather than LLM priors, single-voice surface without fluent rendering of internal machinery, and reasoning transparency that lets users interrogate any output.
Honest is not a tone. It is a structural property. It is what the architecture produces when the reasoning machinery is bound by refusal logic, grounding contracts, structured output schemas, and a question discipline that prevents the LLM from filling silence with fluent guessing.
## 1.3 The reference experience
Solva is built to feel like a session with a Fortune 500 executive coach. A good executive coach does not open by listing what is deficient about the executive's framing. The coach absorbs the framing, registers what is and is not there, and asks the question that opens the situation. The rigour lives in the preparation. The question is what the executive meets.
Every design and engineering decision in this brief serves that experience. The reasoning machinery runs underneath; the user meets one voice — the coach. The audit happens; the user is never the auditor's subject.
## 1.4 What Solva is not
- Not a chatbot. Solva is a sequenced reasoning architecture that requires the user to walk through five layers in order. The standard Akki chat is a separate surface for casual questions.
- Not a free-text generator. Solva's synthesis output conforms to a structured schema. The LLM renders the structured output into language; it does not produce free-form prose.
- Not a therapy tool. Solva is built for executive decision-making. The therapy-tool guardrail redirects emotional content to appropriate support.
- Not a jailbreak surface. The jailbreak guardrail prevents users from using Solva's empathetic voice as a path to extract LLM outputs without Solva's structure.
- Not a default. Solva is invoked for consequential reasoning. Casual queries should route to standard chat, not into a Solva session. Used too often, the structure becomes ritual.

SECTION 2
# Architecture
Solva is a three-tier system: presentation (the user-facing surface), orchestration (the reasoning models, layer engine, question routing, guardrails), and reasoning (the LLM provider, accessed through Synisense Service).
## 2.1 Two architectural invariants


## 2.2 The three tiers
### Presentation tier
The user-facing surface within the Akki application. Renders the sub-module landing page, the active layer view, the question prompts, the answer surfaces (text input, single-select, multi-select, file upload, document picker), the synthesis output, and the reflection prompts. Implements the coach voice. Does not render reasoning model output as user content.
### Orchestration tier
Solva's engine. Nine components:
- Sub-module router — entry-point logic per sub-module. Loads the appropriate framing prompts, question routing rules, and synthesis templates.
- Layer state machine — manages sequencing through the five layers. Enforces non-skipping and stores layer-by-layer state.
- Frame audit engine — runs at Layer 0. Audits the user's initial framing and routes Layer 1 question selection.
- Question routing engine — selects the next question based on prior answers and frame audit output. The question bank itself is data, not code.
- Material ingestion service — handles uploaded files and document references. Extracts text, chunks for retrieval.
- Triangulation engine — runs multi-source consistency checking between user narrative, attached evidence, and prior context retrieved from Synisense.
- Probability weighting engine — produces synthesis scenario probabilities with confidence intervals.
- Tension detector — identifies internal inconsistency. Auto-activates Solva inside Simulate Hypothesis when tension is detected.
- Guardrail layer — runs intent classification on every user input and synthesis output. Blocks jailbreak attempts and therapy-tool misuse.
### Reasoning tier
LLM-powered work, routed entirely through Synisense Service. Solva does not hold LLM provider credentials and does not invoke any LLM directly. Every LLM call passes through the Synisense Shield API, which handles de-identification, provider routing, audit, and re-identification. The reasoning tier from Solva's perspective is a contract with Synisense, not a direct integration with any model provider.
## 2.3 Data model
A Solva session is the unit of state. Schema:
solva_session {
  session_id: uuid
  user_id: uuid
  context_id: uuid
  sub_module: enum
  status: enum             // active | completed | abandoned | refused
  layer_state: enum        // 0 | 1 | 2 | 3 | 4 | done
  initial_framing: text

  layer_0: {
    frame_audit: frame_audit_record
    verdict: enum          // sufficient | sufficient_with_caveats |
                           //   insufficient
    routing_decision: jsonb
  }
  layer_1: {
    answers: jsonb
    candidate_set: array<candidate>
  }
  layer_2: {
    questions_asked: array<question_id>
    answers: jsonb
    triangulation_result: triangulation_output
    refined_candidates: array<weighted_candidate>
    detected_tensions: array<tension>
  }
  layer_3: {
    scenarios: array<scenario>
    sensitivity_analysis: jsonb
    surfaced_tensions: array<tension>
    primary_diagnosis: structured_text
    evidence_trace: array<evidence_link>
    refusal_flag: bool
  }
  layer_4: {
    answers: jsonb        // 3 reflection questions
  }

  attached_materials: array<material_ref>
  synisense_audit_ids: array<uuid>   // references to Shield audits
  orchestration_audit_log: array<audit_entry>
  guardrail_events: array<event>
  created_at: timestamp
  completed_at: timestamp
}

Sessions are persisted at every layer transition. The orchestration audit log captures every Solva-internal reasoning decision. Synisense audit IDs reference Shield-side audit entries that Solva does not own but stores for traceability.

SECTION 3
# The reasoning journey
Solva sessions move through five layers. Layers run in sequence. The user cannot skip ahead. Every layer's output is persisted before the next layer begins. Every reasoning model invocation is logged.
## 3.1 Layer overview

## 3.2 Layer 0 — Frame Audit
Objective
Audit the user's initial framing and any attached material before any candidate generation begins. Produce a Frame Audit Record (FAR). Route Layer 1's opening question selection.
User-facing surface
None. After the user submits their initial framing, the system pauses briefly (1–3 seconds) while the audit runs, then transitions directly into Layer 1's first question. The user experiences this as the conversation starting; they do not experience the audit.
Reasoning models active
- Frame audit engine (specified in Section 4.1)
- Situation class classifier (specified in Section 4.2)
Output
A FAR attached to the session, a verdict (sufficient, sufficient_with_caveats, or insufficient), and a routing decision specifying the Layer 1 opening question. Carry-forward caveats are stored for use at Layer 3.
Engineering invariant
The FAR is internal. Its fields never render to the user as content. The verdict routes orchestration; it is not a user decision point.
## 3.3 Layer 1 — Surface
Objective
Establish the visible cause. Narrow the user's situation from open-ended to a working set of five to seven candidates.
Question count
Three questions preferred. Four maximum. The fourth is reserved for cases where the FAR severity profile requires it.
Reasoning models active
- Candidate generation (Section 4.5) — produces the candidate set from Layer 1 inputs and the FAR
Output
A working set of five to seven candidates — causes for Seek Clarity, strategies for Develop Strategy, hypotheses for Simulate Hypothesis, perspective frames for Get Perspective. The set is internal at this stage; it informs Layer 2 question routing.
Engineering invariant
The candidate set is reproducible. Given the same Layer 1 inputs and FAR, the same set is produced. The reasoning tier may vary the language of candidate descriptions, but the narrowing structure is deterministic.
## 3.4 Layer 2 — Depth
Objective
Probe the inherited, invisible, and compounding causes that Layer 1 did not surface. Run triangulation across user narrative, attached evidence, and prior context retrieved from Synisense. Refine candidate weights and surface tensions for Layer 3.
Question count
Three questions preferred. Four maximum, reserved for cases where the absence of a fourth would force a Layer 3 refusal.
Reasoning models active
- Triangulation engine (Section 4.3)
- Tension detection (Section 4.6)
- Candidate refinement (Section 4.5)
Question shape
Three probe types route based on Layer 1 patterns:
- Inherited-cause probe — what was true before the user inherited the situation that may still be shaping it
- Invisible-cause probe — what is true that the user has not named: patterns, omissions, things visible from a third-party perspective
- Compounding-cause probe — what is getting worse over time if the situation is not addressed
Output
A refined candidate set with weights, a triangulation result (consistency score and divergences), and detected tensions. All three feed Layer 3.
## 3.5 Layer 3 — Synthesis
Objective
Produce probability-weighted scenarios with explicit confidence intervals, evidence trace, surfaced tensions, and sensitivity analysis. Make the output decision-grade.
Question count
Zero. Layer 3 is system output, not user input.
Reasoning models active
- Probability weighting engine (Section 4.4)
- Sensitivity analysis (Section 4.4)
- Refusal logic (Section 4.7)
Output format
A structured synthesis with five components:
- Scenario set — typically three to five scenarios with explicit probability weights (summing to 1.0) and confidence intervals
- Sensitivity analysis — the two or three inputs that, if changed, would most shift scenario probabilities
- Surfaced tensions — explicit identification of where the user's framing and the evidence diverge, with citations
- Primary diagnosis — framed as a probability-weighted view, not a declarative answer, with reasoning trace visible
- Evidence trace — citations to attached materials and prior context
Carry-forward caveats from the FAR render here as conditional clauses on the diagnosis: "If [X], then [scenario A]; if [different X], then [scenario B]."
## 3.6 Layer 4 — Reflection
Objective
Force engagement with the diagnosis against the natural tendency to reject what is uncomfortable. Address denial — the tendency for executives to dismiss diagnoses that don't fit their preferred framing.
Question count
Three, fixed. No fourth — reflection does not benefit from additional questions.
Question shape
- Are you disappointed by this diagnosis, and if so, why?
- What would have to be true for you to be wrong about your prior framing?
- What would the explanation be in six months if you ignore this diagnosis and the situation continues?
Engineering invariant
The session is not marked complete until Layer 4 answers are submitted. The user can decline to answer ("prefer not to say"), but the layer cannot be skipped without an explicit decline that is recorded.

SECTION 4
# Reasoning models
Each reasoning model has a defined contract: when it activates, what it takes as input, what method it uses, what it produces, and how it logs. Engineers should treat this section as the most consequential — these contracts are what differentiate Solva from an LLM wrapper.
## 4.1 Frame audit engine
When it activates
Layer 0, before Layer 1 opens.
Inputs
- Initial framing text typed by the user
- Any materials attached at session start
- Sub-module type
- Situation class match (from 4.2)
- Relevant prior signals retrieved from Synisense Engine API
Method
Structured prompt against the framing, scoring on five audit dimensions:
- Decisional clarity — does the framing imply a decision the diagnosis would inform?
- Time horizon — is there an implicit or explicit time horizon?
- Scope boundedness — is the situation scoped, or open-ended?
- Evidence grounding — does any attached material or referenced source ground the framing?
- Lens fit — for Get Perspective sessions, does the requested lens fit the framing?
Each dimension produces a score (sufficient, thin, absent) and where thin or absent, an invalidation condition specifying when the gap would matter.
Output — the FAR
frame_audit_record {
  verdict: enum                       // sufficient |
                                      //   sufficient_with_caveats |
                                      //   insufficient
  dimensions: [
    {
      dimension: enum
      score: enum
      excluded_item: text
      invalidation_condition: text
      severity: enum                  // minor | material | critical
    }
  ]
  routing_decision: {
    layer_1_opening_question_id: string
    additional_probes: array<probe_id>
    carry_forward_caveats: array<dimension_id>
  }
}

Verdict logic
- Sufficient — no dimension scored absent; at most one scored thin with minor severity
- Sufficient_with_caveats — one or more dimensions scored thin with material severity, or one dimension scored absent with minor severity
- Insufficient — any dimension scored absent with material or critical severity, or aggregate severity exceeds threshold
Routing
- Sufficient — standard Layer 1 opening for the sub-module and situation class
- Sufficient_with_caveats — tuned opening. The question elicits missing dimensions as part of the conversation. Caveats carry forward to Layer 3 as conditional language.
- Insufficient — conversational opening. The first question helps the user surface what is missing through conversation. If the user cannot provide it, refusal logic triggers at Layer 3.
Auditability invariant
Every FAR is logged in the orchestration audit log with the verdict, routing decision, and the question selected. Engineering must be able to answer "why did Solva open with this question" by tracing through the log.
## 4.2 Situation class classifier
When it activates
Layer 0, before the frame audit produces its verdict — the audit needs to know which dimensions apply.
Method
Structured LLM call routed through Synisense Shield, with a closed enum output. Approximately 30 known executive situation classes (customer concentration risk, capital allocation, team capacity gap, competitive positioning, board succession, regulatory shift, etc.). Each class has a versioned audit profile and candidate template. Classes are versioned data.
Output
Class match with confidence score. If no class matches above threshold, the situation is flagged as out-of-scope and Layer 0 routes to a conversational opening that probes for class identification through Layer 1.
## 4.3 Triangulation
What triangulation means
The cross-check between three sources of information available at Layer 2: the user's narrative (Layer 1 + Layer 2 answers), attached evidence (uploaded materials and Akki document references), and prior context (Synisense signals retrieved for the entities and topics in the user's narrative).
The purpose is to detect divergences — places where the user's narrative says one thing, the evidence says another, and the prior context says a third. Divergences are the most consequential reasoning artefacts in Solva.
Method
Three pairwise consistency checks:
- Narrative vs evidence — for each candidate, extract factual claims from the narrative, retrieve evidence chunks per candidate, run entailment/contradiction classification per claim. Output: per claim, an alignment score and the supporting evidence chunk.
- Narrative vs prior context — same method, with prior context retrieved from Synisense as the source. Detects narrative drift across sessions and time.
- Evidence vs prior context — checks whether attached evidence aligns with prior context. Catches the failure mode where attached documents disagree with what the system already knows about the user's situation.
Aggregation
triangulation_result {
  overall_consistency: float [0,1]
  divergences: [
    {
      type: enum         // narrative_vs_evidence |
                         //   narrative_vs_prior |
                         //   evidence_vs_prior
      claim: text
      sources: array<source_chunk>
      severity: enum     // minor | material | critical
    }
  ]
  alignments: array<alignment_record>
}

Privacy and scope
Prior context is only ever retrieved from contexts the user has access to. Synisense enforces this — a user's NED context for one board cannot pull signals from their NED context for another board. Solva does not bypass this; it requests within the user's authorisation envelope.
Auditability invariant
Every divergence carries source citations. The user can click through to inspect the source of any flagged divergence in Layer 3.
## 4.4 Probability weighting and sensitivity
When it activates
Layer 3, after Layer 2 closes.
Method
Four steps. Step 1 — scenario construction. From the refined candidate set, construct scenarios (typically three to five). Rule-based templates per situation class, with LLM-generated narrative descriptions routed through Synisense Shield. Rules ensure scenarios are mutually distinct and collectively exhaustive.
Step 2 — probability assignment. Each scenario receives a weight from aggregation of four inputs: candidate weights for the candidates composing the scenario, triangulation alignment (scenarios consistent with evidence and prior context score higher), prior probability from situation class statistics, and counterfactual robustness (scenarios that hold up across plausible perturbations score higher). Probabilities normalise to 1.0 across the scenario set.
The relative weights of these four inputs are not specified here. They are to be set during Phase 1 calibration against a curated test set of completed sessions with known outcomes. Engineering treats the specific values as TBD until calibration completes. Calibration produces the v1.0 weights; subsequent retrospectives may adjust them. The reasoning audit log captures the weights in use for every Layer 3 synthesis so engineering can trace any output to the calibration version that produced it.
Step 3 — confidence intervals. Each weight has an interval computed from evidence sufficiency, triangulation consistency, and candidate type. Intervals are not optional. The synthesis displays "Scenario A: 45% (35–55%)." Wide intervals are themselves diagnostic.
Step 4 — sensitivity analysis. Perturb each Layer 1 and Layer 2 input one at a time and recompute. The two or three inputs producing the largest shifts are surfaced as sensitivity drivers.
Output
layer_3_output {
  scenarios: array<scenario_record>
  sensitivity: array<sensitivity_driver>
  surfaced_tensions: array<tension>
  carry_forward_caveats: array<caveat>
  primary_diagnosis: text
  evidence_trace: array<evidence_link>
}

Auditability invariant
Every probability weight is reproducible from inputs. Engineering must be able to answer "why was Scenario B weighted at 32% instead of 28%" by tracing through the orchestration audit log.
## 4.5 Candidate generation and refinement
Method
Layer 1 generation is two-step. First, domain decomposition via the situation class match. Second, candidate enumeration: for the matched class, retrieve the structured candidate template and personalise candidates against the user's specific input.
The candidate set is not free-form. Each candidate has a type, a description, an evidence requirement (what would confirm or refute it), and an estimated prior probability from situation class statistics.
Layer 2 refinement processes each Layer 2 answer for: which candidates does it support, which does it weaken, and does it surface a candidate that wasn't in the Layer 1 set. Weights adjust; new candidates are added up to a cap of eight, with lowest-weighted candidates removed if exceeded.
## 4.6 Tension detection
What tension means
Internal inconsistency — between framing and evidence, between expected outcomes and hypotheses, between narrative and prior context.
Categories — Layer 2
- Narrative-evidence tension — narrative claims X, evidence shows not-X
- Internal narrative tension — contradictions across Layer 1 and Layer 2 answers
- Prior-context tension — narrative diverges from a prior session, signal, or recorded data
Categories — Simulate Hypothesis pre-flight
- Statement tension — hypothesis contains internal contradictions or pre-loaded framing
- Approach tension — proposed test has structural weakness
- Outcome tension — expected outcome is internally inconsistent or overconfident relative to evidence
Method
Hybrid: rule-based pattern matching for known tension types, augmented with LLM-based contradiction classification routed through Synisense Shield. Each tension carries a severity score (minor, material, critical) from evidence weight, centrality to the user's framing, and alignment with prior context.
Threshold and surfacing
Material and critical tensions are always surfaced in Layer 3. Minor tensions aggregate and surface if cumulative count exceeds threshold. Surfacing is editorial — the synthesis names the tension in coach voice, cites the source, frames the implication.
## 4.7 Refusal logic
Why refusal matters
The willingness to refuse is the property of Solva that the LLM cannot replicate. An LLM given a situation with insufficient evidence will produce confident-sounding analysis anyway. Solva refuses — explicitly tells the user that evidence is insufficient to weight scenarios honestly, and declines to produce a probability-weighted synthesis on that basis.
Triggers
- Insufficient evidence — candidate set has fewer than three candidates supported by evidence; triangulation has no aligned chunks; scenarios cannot be constructed with intervals narrower than [0,1]
- Contradictory evidence at scale — triangulation has critical divergences across multiple candidates such that no scenario can be constructed without overriding direct evidence
- FAR insufficient verdict not resolved — Layer 0 verdict was insufficient and Layer 1/2 conversation did not surface the missing dimensions
- Out-of-scope situation — situation class match below threshold with no template-driven fallback
Refusal output
A refusal is not a failure. It is a structured output that:
- Names what is missing — in coach voice. "I don't have enough to weight scenarios honestly here. The candidates worth examining are clear — there are four of them — but without evidence on [X] and [Y], I'd be guessing at probabilities."
- Produces what Solva can produce — typically the candidate set without probability weighting, framed as "here are the framings worth examining"
- Recommends next action — what the user should do to enable a future synthesis
Engineering invariant
Refusal logic runs as a guard before the probability weighting engine. If refusal triggers, the weighting engine does not run and no fabricated probabilities are produced. The orchestration audit log captures the refusal decision and its rationale.
## 4.8 The orchestration audit log
What it captures
- Timestamp and session ID
- Model invoked (frame audit, classifier, candidate generation, triangulation, weighting, tension, refusal)
- Inputs
- Method version
- Output (structured)
- Orchestration decision (what the orchestration tier did with the output)
- Synisense audit IDs for any Shield-routed LLM calls invoked within the reasoning step
Relationship to Synisense audit
The orchestration log captures Solva's reasoning decisions. The Synisense audit log captures the LLM calls Solva makes. Solva stores Synisense audit IDs as cross-references; it does not duplicate the Synisense entries. Engineers debugging an issue trace through the orchestration log; when an LLM call is implicated, they follow the audit ID into the Synisense log.
Privacy
Orchestration log entries are stored with tenant-specific encryption. Inputs to LLM calls are de-identified through Synisense before being logged (the orchestration log stores references to the de-identified content, not the content itself for sensitive cases).

SECTION 5
# Voice and user experience
The user journey is Solva's primary differentiator. The structure must feel empathetic, not bureaucratic; clean, not clinical; deliberate, not slow.
## 5.1 Journey state machine
Every Solva session moves through six states:
- Entry. The user lands on the Solva menu item or is auto-activated into Simulate Hypothesis. Sub-module is selected.
- Framing. The system explains what the sub-module does in two sentences. The user enters initial framing.
- Layer 0 (silent). The frame audit runs. 1–3 second pause. No user-facing screen. Transitions directly to Layer 1 with the tuned opening question.
- Layers 1 and 2. Up to four questions per layer. One question at a time with progress indication. Material attachment available at any question.
- Layer 3. Synthesis prepared ("Let me put this together") and rendered. User reviews; can request clarification of any element via citation; can return to earlier layers if framing was off.
- Layer 4. Three reflection questions, one at a time. Session marked complete on submission and saved to history.
## 5.2 The coach voice
Solva has one user-facing voice — the coach. Empathetic, restrained, conversational. Informed by every reasoning model but surfaces none of them as content. Four rules govern it:
- Explain before asking. Each layer opens with a one-sentence explanation of what is about to happen and why.
- Acknowledge before pushing. If the user has provided a framing, the system reflects what it has heard before asking the next question. One sentence.
- Restrain in synthesis. Layer 3 output uses editorial cadence — short sentences, one idea per line, white space.
- Speak in one voice — the coach's. The audit is preparation, not content. No reasoning model output renders to the user as audit language.
## 5.3 Voice examples
Below: the opening prompt of Layer 1 for each sub-module. Each absorbs a frame audit finding invisibly. Illustrative; the question bank carries the canonical set.
### Seek Clarity

### Develop Strategy

### Simulate Hypothesis

### Get Perspective

### Refusal voice

## 5.4 Question discipline
Three preferred per layer. Four maximum. Enforced at orchestration; the LLM cannot generate a fifth. Three principles:
- Per-question yield matters more than question count. A question that elicits two FAR caveats counts as one slot. The bank invests in compound-yield questions, not compound questions — "What does badly look like, and by when would you know" is two short questions in one breath; the user reads it as one ask and answers both.
- The fourth-question budget is reserved. Used only when its absence would force a Layer 3 refusal. Hard rule; routing logs reviewed weekly for budget discipline.
- The question bank is data, not code. Every situation class has its own question set per layer. New classes are data updates; orchestration code does not change.
## 5.5 Rendering Layer 3
- Probability weights with intervals. "Scenario A: 45% (35–55%)." Wide intervals are visually distinct from narrow ones.
- Citation rendering. Every claim drawing on attached material or prior context is citation-linked. Hover or click reveals the source chunk in a popover.
- Sensitivity callouts. The 2–3 sensitivity drivers surface as a distinct block — "What would change this read."
- Tension callouts. Material and critical tensions surface as distinct blocks — "Where your framing and the evidence diverge." Editorial in tone, citing both sources.
- Carry-forward caveats. Frame audit caveats not resolved during Layer 1/2 render here as conditional clauses on the diagnosis.
- Refusal rendering. Refusal surfaces in coach voice. Visual treatment is calm and confident, not apologetic.
## 5.6 Answer surfaces
- Open text — generous textarea, no character limit, file attachment and Akki document reference inline
- Single-select with text fallback — when the question benefits from a constrained answer, 4–6 options plus an "Other — describe" text field
- Multi-select with weighting — when asking the user to weight several factors, 4–6 options with simple weighting. Used sparingly.
One question at a time. One answer surface at a time. Clear progression indication.
## 5.7 Resume and revisit
If the user closes Solva mid-session, the session resumes at the next layer entry on return. From Akki Pulse, the user sees "In progress: Solva session — Develop Strategy" with one-click resume.
From the Solva landing page, the user sees their five most recent completed sessions with one-line summaries. Clicking opens the synthesis output and reflection answers.
## 5.8 Frequency-of-invocation discipline
Solva is for consequential reasoning. Used on every interaction, the structure becomes ritual — fluent five-layer journeys for casual questions, which produces the same fluency-mistaken-for-diagnosis failure the discipline exists to prevent.
Engineering implication: do not auto-route casual chat into Solva sessions. Solva is invoked explicitly by the user (selecting a sub-module) or by tension auto-activation in Simulate Hypothesis. The standard Akki chat surface handles the rest.

SECTION 6
# Grounding and material handling
Solva produces better diagnoses when grounded in the user's actual material. The user can attach material at any question in Layers 1 and 2. This section specifies what Solva does with material and how the grounding contract works.
## 6.1 Supported sources
### Direct upload
- DOCX — Word documents up to 50MB
- XLSX — Excel spreadsheets up to 50MB; multiple sheets supported
- PDF — including scanned PDFs (OCR applied)
- TXT — plain text up to 10MB
- CSV — tabular data up to 25MB
### Akki document references
The user can reference any document already in the Akki system — board packs, committee papers, reportee submissions, prior Solva session outputs.
## 6.2 Ingestion pipeline
- Receive — file upload or document reference. Validate format, size, and Akki access permissions.
- Extract — text extraction per format with structure preservation.
- Sanitise — Synisense Shield de-identification applied to extracted content before any LLM call.
- Chunk — semantic chunking optimised for retrieval. Typical chunk size: 500–1500 tokens, with overlap.
- Index — embedded into a session-scoped vector store.
- Acknowledge — UI confirmation that the material is available.
## 6.3 The grounding contract
Specifies when reasoning models use attached material vs LLM general knowledge. This is what prevents "the LLM analysed your situation" from collapsing into "the LLM made up plausible analysis using fluency."
### Grounding hierarchy
When any reasoning model needs information, sources are consulted in this order:
- User narrative (initial framing + Layer 1 + Layer 2 answers) — always available, always primary
- Attached material — retrieved per candidate, per claim, per scenario at the point of need
- Synisense signals — prior context retrieved through the Engine API for the user's accessible contexts
- Situation class statistics — versioned priors associated with the matched class
- LLM general knowledge — used only for natural language generation and analytical sub-tasks (entailment classification, contradiction detection); never for factual claims about the user's situation
### Grounding rules
- Factual claims about the user's situation must come from sources 1–3. If the synthesis says "your customer concentration has risen 8 percentage points," that claim must trace to attached material or a Synisense signal. The LLM may render the claim in language; it did not produce the claim.
- Probability weights come from the weighting engine. The LLM does not assign probabilities.
- Triangulation results come from the triangulation engine. The LLM does not produce divergence claims.
- Situation class priors come from versioned data. The LLM does not generate these from session to session.
- LLM general knowledge can support reasoning but cannot ground it. Priors on "customer concentration risk in mid-cap banks" can inform candidate-template language; they are not the source of facts about this user's bank.
### Engineering enforcement
Grounding rules are enforced through structured output schemas. Every claim in the synthesis schema must include a source attribution field. Claims without attribution to sources 1–3 fail validation and are not surfaced. The orchestration audit log records every grounding decision.
## 6.4 Retrieval at synthesis
At Layer 3, the synthesis prompt is augmented with retrieval over session-attached material:
- Material retrieved per candidate in the candidate set
- Material retrieved per Layer 2 input — chunks relevant to inherited, invisible, and compounding patterns
- Retrieved chunks presented to the synthesis with explicit attribution
- Synthesis output references material citations the user can click through to source
## 6.5 Material privacy
All ingested material is encrypted at rest. Synisense Shield ensures any LLM provider receives only de-identified content. Materials attached to a session are deleted at session completion unless the user opts to retain. Materials referenced from the Akki system are not duplicated — the reference is a pointer, and access permissions are checked at retrieval time.

SECTION 7
# Auto-activation in Simulate Hypothesis
Inside Simulate Hypothesis, Solva's diagnostic flow auto-activates when the system detects tension in the user's hypothesis. This is the differentiator from generic LLM-driven hypothesis testing.
## 7.1 What constitutes tension
### Statement tension
- Hypothesis presupposes a causal direction the data does not support
- Hypothesis frames a strategic choice as binary when material suggests a third option
- Hypothesis uses absolute language on a topic where evidence is mixed
### Approach tension
- The approach would not actually distinguish the hypothesis from a plausible alternative
- The approach relies on a metric downstream of the variable being tested
- The approach has a sample size or scope that cannot produce decision-grade evidence
### Outcome tension
- Expected outcome includes a directional claim with a confidence interval narrower than evidence supports
- Expected outcome assumes a magnitude not present in any prior cohort
- Expected outcome contradicts a finding in attached material the user has not engaged with
## 7.2 Detection methodology
Tension detection runs as a parallel process when the user enters hypothesis statement, approach, and outcome. Detection produces a tension score per category. When any exceeds threshold, auto-activation triggers.
- Statement tension — LLM-based contradiction detection (Shield-routed) with structured rules; cross-referenced with attached material
- Approach tension — rule-based detection with retrieval; prior Akki sessions or attached material suggesting the approach has known weaknesses
- Outcome tension — statistical and retrieval-based; expected magnitude and direction compared against attached material or analogous prior evidence
## 7.3 Threshold and auto-activation
Threshold is set conservatively — the system errs on the side of activating when uncertain. The user can opt out per session by toggling "skip tension check." Opt-outs are logged.
## 7.4 Auto-activation surface — coach voice
Auto-activation does not announce "statement tension detected." It opens with a coach-voice question that surfaces the tension as the user's own observation.

The user accepts (default) or declines (logged). On accept, the standard five-layer flow runs. The Layer 3 synthesis specifically addresses the detected tension and produces a refined hypothesis, approach, or outcome the user can take into the simulation phase. On decline, the simulation proceeds without the diagnostic, the tension flag is recorded, and the user is shown a brief reminder at the simulation output that tension was detected and not addressed.
## 7.5 Engineering invariant
The tension detector must be auditable. Given a hypothesis input, the system must be able to explain why tension was or was not detected — which categories triggered, which patterns matched, which retrieval returned what. Required for product trust and guardrail compliance.

SECTION 8
# Guardrails
Solva must prevent two specific misuse patterns: jailbreak (using Solva as a path to extract LLM outputs without Solva's structure) and therapy (using Solva for personal emotional matters that fall outside executive decision-making).
## 8.1 Guardrail architecture
Guardrails run in three positions: session entry (intent classification, before Layer 0), per layer transition (continuity check), and pre-output (sanitisation and refusal generation). All three feed the session's guardrail event log.

## 8.2 Jailbreak guardrail
### Patterns flagged
- Initial framing contains explicit prompt-injection patterns ("ignore previous instructions," "act as if you are not bounded by Solva," embedded role-play directives)
- Initial framing requests output that bypasses Solva's structure ("just give me the answer without the layers," "skip to the synthesis")
- Layer answers attempt to redirect the LLM into producing arbitrary content unrelated to the framing
- Material upload contains content designed to override Solva's prompts (poisoned documents, instruction-laden text framed as user material)
### Response
Soft block on first detection — the system explains that Solva runs through its layered structure for every session. Hard block on persistent or escalating attempts — the session is terminated, the user is informed why, and a guardrail event is logged for review.
## 8.3 Therapy-tool guardrail
### Patterns flagged
- Initial framing centres on personal emotional content without an executive decision-making frame
- Layer answers shift from organisational situation to personal feelings about self-worth, identity, or interpersonal dynamics outside professional context
- User explicitly requests therapeutic guidance, emotional support, or mental health advice
### Response — redirect, not refusal
On detection, Solva responds with a redirect. The voice acknowledges the importance of what the user has shared and is explicit about Solva's scope:

## 8.4 Edge cases — executive content with personal dimensions
Some legitimate executive situations have personal dimensions — a CEO navigating board succession that affects their own role, a founder considering whether to step back, a leader making a decision with family implications. The therapy guardrail must not over-reach.
Pattern recognition focuses on what dominates the framing. "How do I make this decision?" with personal context — Solva engages. "How do I feel about this?" without a decision context — Solva redirects. The distinction is decision-orientation, not absence of personal content.
## 8.5 Audit and review
Every guardrail event is logged with timestamp, session ID, user ID, position, pattern detected, severity, action taken, and user response. Logs are reviewed weekly during build phase, monthly post-launch. False positives are tracked; the product team monitors the rate and adjusts thresholds when it exceeds 2% of sessions.

SECTION 9
# Synisense integration
Solva depends on Synisense Service for two functions: signal retrieval (Engine API) and governed LLM invocation (Shield API). Solva does not hold LLM provider credentials and has no path to invoke an LLM outside Synisense. This section specifies the integration contract Solva must implement against.
## 9.1 Engine API — signal retrieval
Solva calls the Engine API to retrieve signals that inform reasoning:
- Layer 0 (frame audit) — retrieves operational signals, anomaly flags, or life-stage indicators relevant to the user's framing
- Layer 2 (triangulation) — retrieves prior-context signals for the entities named in the user's narrative
- Layer 3 (synthesis) — retrieves any additional signals needed to ground claims
Solva does not subscribe to Synisense signals continuously — Solva is session-based and queries on demand. Continuous subscription is for other Akki products (Pulse, Highlights, Monitor).
## 9.2 Shield API — governed LLM invocation
Solva calls the Shield API for every LLM invocation. Every call includes a declared purpose. Examples of Solva purposes:
- solva.layer_0.frame_audit
- solva.layer_0.situation_classification
- solva.layer_1.candidate_generation
- solva.layer_2.triangulation.claim_extraction
- solva.layer_2.triangulation.entailment_classification
- solva.layer_2.tension_detection
- solva.layer_3.scenario_narrative_generation
- solva.layer_3.synthesis_rendering
Synisense validates each purpose against Solva's authorisation and refuses if the declared purpose is invalid.
## 9.3 Trust receipts
Every Shield call returns a trust receipt — a structured artefact Solva stores in the session record. The receipt is what makes Solva's outputs externally verifiable. Solva carries the receipt forward into the session's audit chain so an end user — or a regulator — can prove that every LLM call was governed.
## 9.4 Audit ownership boundary

## 9.5 Handling Synisense degradation
Synisense can degrade in three ways. Solva must handle each:
- Engine signal staleness — Solva proceeds with stale signals if the staleness indicator is within acceptable bounds; otherwise Layer 2 triangulation runs without prior-context signals and the FAR carries a "limited prior context" caveat forward to Layer 3
- Shield SERVICE_UNAVAILABLE — Solva cannot proceed. The session pauses with a clear message; users can resume when Synisense is available. Solva does not fall back to an ungoverned LLM path; there is no such path.
- GOVERNANCE_REFUSED — Solva surfaces the refusal to the user in coach voice and terminates the session. Synisense refused on policy grounds, and Solva does not work around governance.


SECTION 10
# Build strategy and acceptance criteria
Solva is one of the most architecturally distinctive modules in Akki. The build prioritises depth before breadth, reasoning rigour before feature count, observability throughout.
## 10.1 Build phases
### Phase 1 — Foundation and reasoning architecture (weeks 1–8)
- Layer state machine with persistence (Layer 0 through Layer 4)
- Frame audit engine and FAR schema
- Situation class classifier
- Question routing engine — Layer 1 question banks per situation class, Layer 2 conditional routing rules, FAR-driven question selection
- Material ingestion pipeline with grounding contract enforcement
- Candidate generation and refinement
- Triangulation engine (consuming Synisense Engine API for prior context)
- Probability weighting engine
- Refusal logic
- Orchestration audit log
- Synthesis output schema with citation and provenance fields
- Layer 4 reflection question banks
- Synisense Shield integration for all LLM calls
- Solva landing page and session resume
Phase 1 acceptance criteria
- End-to-end Solva session can be completed in any sub-module
- All reasoning models specified in Section 4 are implemented and producing structured output
- Orchestration audit log captures every model invocation with traceable inputs and outputs, including Synisense audit IDs
- Refusal logic triggers correctly on a curated test set of 30 low-evidence situations
- Probability weights are reproducible — same inputs produce same weights
- Triangulation produces divergence outputs that match human-annotated test cases at ≥85% agreement
- Sessions persist correctly across browser refresh and re-login
- Single-voice invariant verified — no reasoning model output renders directly to the user. Inspected across the Layer 0 → Layer 1 transition for all four sub-modules
- Question count per layer never exceeds 4 in any session log. Median converges to 3
- Every LLM call routes through Synisense Shield with valid purpose. Verified by inspection of network traffic and Synisense audit logs
### Phase 2 — Tension detection and auto-activation (weeks 9–12)
- Tension detector for Simulate Hypothesis — three categories
- Auto-activation flow integrated into Simulate Hypothesis
- Coach-voice auto-activation copy
- Opt-out mechanism ("skip tension check") with logging
- Audit trail for tension detection decisions
- Tension surfacing in Layer 3 synthesis
Phase 2 acceptance criteria
- Tension detection triggers correctly on a curated test set of 50 hypotheses (25 with tension, 25 without)
- Detection sensitivity above 85%, specificity above 90%
- Auto-activation copy reviewed against coach voice — no audit vocabulary leak
- User opt-out is functional and logged
- Material and critical tensions are surfaced in Layer 3 with citations in coach voice
### Phase 3 — Guardrails (weeks 13–15)
- Jailbreak guardrail at session entry, layer transition, and pre-output
- Therapy-tool guardrail with redirect voice
- Edge case handling for executive content with personal dimensions
- Guardrail event logging and weekly review process
Phase 3 acceptance criteria
- Jailbreak attack vectors from a curated red-team set of 30 attempts are blocked appropriately
- Therapy-pattern framings from a curated test set of 20 examples trigger the redirect
- Edge cases from a curated set of 15 examples are correctly engaged with
- False-positive rate below 2% on a sample of 100 legitimate sessions
### Phase 4 — Polish, observability, and calibration (weeks 16–18)
- Resume/revisit experience with reasoning trace views
- Citation rendering for material-grounded synthesis with click-through
- Session export to Work Studio as a structured artefact
- Cross-module integration — Solva invocable from any Akki surface (but not auto-invoked from chat)
- Observability dashboards — session completion, per-layer drop-off, tension trigger rate, guardrail events, refusal rate, question-budget discipline
- Reasoning calibration — aggregated audit log analysis
Phase 4 acceptance criteria
- Resume from any session state works without state loss
- Solva invocable from at least three other Akki modules with one click — never auto-invoked
- Observability dashboards live with weekly review cadence
- End-to-end user testing with five executive testers shows 4 of 5 completing sessions without intervention
- Five of five testers describe the experience as conversational rather than diagnostic on open-ended first impression
- Reasoning calibration runs against 50 completed real-user sessions with no systematic miscalibration identified
- Median question count per layer is 3; fourth-question usage below 25% of layer instances
## 10.2 Build principles
### Structure is the differentiator, not the LLM
The reasoning tier (Synisense Shield + LLM provider) is interchangeable. The orchestration tier and the question bank are what give Solva its category claim. Engineering investment is weighted toward orchestration — better question banks beat better prompts; structured output schemas beat free-form synthesis; observable orchestration beats opaque generation.
### Earn the empathetic voice through restraint
Solva does not use breathless language, exclamation marks, or vendor cadence. The voice is restrained throughout — including at moments where it would be tempting to celebrate user progress. Voice is built into system prompts and structured output schemas; product cadence enforced by template, not LLM-generated style.
### Reasoning transparency is the trust bar
Executives will not trust Solva on fluency alone. Citations, probability intervals, sensitivity callouts, refusal-when-evidence-is-thin — these are what turn Solva from impressive demo to deployed system. Engineering investment in transparency components is as significant as investment in synthesis voice.
### Hold the single-voice line
The hardest part of the build is not the reasoning models. It is keeping the reasoning models off the user-facing surface. Every time a build decision exposes audit vocabulary, FAR fields, candidate types, or any other internal artefact to the user, the product becomes "chat with rigour-flavoured prompts" rather than "a thinking partner."
## 10.3 Continuous compliance checks
Acceptance criteria phrased per phase are necessary but not sufficient. Between phase gates, builds can drift back into the failure modes the architecture is built to prevent. The following checks run on every release, not only at phase acceptance:
- Single-voice compliance scan. Automated inspection of all user-facing strings introduced or modified in the release. Any string containing FAR vocabulary, audit terminology, reasoning model artefact names, or internal failure-mode labels triggers a build block. Enforced at the CI pipeline level.
- Synisense Shield coverage check. Every LLM call path in the build is verified to route through the Shield. Any path introducing direct LLM provider invocation triggers a build block.
- Question budget check. Audit logs from staging are sampled on every release; if any session exceeded four questions at any layer, the release is held for review.
- Grounding contract check. Synthesis schema validation is run against a corpus of test cases; any claim that passes validation without source attribution triggers a build block.
Continuous compliance is the engineering discipline that prevents the documents from becoming aspirational rather than operational. Phase acceptance verifies the foundation; continuous compliance prevents the drift.
## 10.4 Out of scope for v1
- Multi-user Solva sessions (collaborative diagnosis between executive and reportee)
- Solva session learning (the system improving question routing based on completed session patterns) — observability now, learning later
- Voice and audio interfaces — text-only
- Mobile-native experience — responsive web
- Custom sub-modules — Enterprise feature, deferred
- Cross-context triangulation — Solva does not pull from the user's other Akki contexts; only the active context
## 10.5 Success metrics

— End of Solva developer brief —

### Table 1
| Term | Definition |
| Akki | The product. Comprises the chat surface, the Solva reasoning module, and any other Akki product surfaces (Workspace, Highlights, Cycle Manager, Monitor, Pulse, etc.), all built on Synisense Service. |
| Akki chat | The conversational surface of Akki. The highest-traffic surface. Separate from the Solva module. |
| Solva | The structured-reasoning module within Akki. Five-layer sequenced reasoning architecture. Accessed by selecting a sub-module: Seek Clarity, Develop Strategy, Simulate Hypothesis, or Get Perspective. |
| Synisense Service | The platform service Akki products consume. Comprises two functions packaged in one service: the Behavioural Analytics Engine and the Shield. Often abbreviated to "Synisense." |
| Synisense Engine (or Engine API) | The behavioural analytics function of Synisense Service. Produces structured signals from enterprise data. Consumers retrieve signals through the Engine API. |
| Synisense Shield (or Shield API) | The governance function of Synisense Service. De-identification, encryption, audit, and LLM routing. Consumers invoke LLMs through the Shield API. |
| Coach voice | The single user-facing voice across all Akki surfaces. Empathetic, restrained, conversational. The reference experience is a Fortune 500 executive coach. |
| Single-voice principle | No reasoning model artefact or internal machinery renders to the user as content. All user-facing content is produced by templates and rendered in coach voice. |
| FAR (Frame Audit Record) | The structured output of Solva's Layer 0 frame audit. Internal to Solva. Never rendered to the user as content; consumed by the question routing engine and synthesis renderer. |
| Trust receipt | A structured artefact issued by Synisense Shield for every LLM call. Stored by the consumer (Solva, chat, etc.) as proof that the call was governed. Forms the audit chain consumers expose to tenant administrators and regulators. |
| Refusal — Solva | Solva's discipline of declining to produce a probability-weighted diagnosis when evidence is insufficient. A reasoning-tier discipline. |
| Refusal — Shield | Synisense's discipline of declining a request that would violate governance (invalid purpose, un-de-identifiable content, jailbreak pattern). An infrastructure-tier discipline. Different from Solva refusal. |
| Tenant | An enterprise customer of Akki — a bank, an insurer, a corporate. Tenancy is the primary isolation unit in Synisense. |
| Sub-tenancy | Organisational units within a tenant — boards, departments, executive contexts. Permission-gated and audited. |
| Consumer (in Synisense context) | An Akki product that consumes Synisense — Solva, chat, Workspace, etc. Identified by consumer ID on every API call. |
| Purpose (in Shield context) | A declared use for an LLM call (e.g., "solva.layer_0.frame_audit"). Validated by Synisense against the consumer's authorisation. |

### Table 2
| INVARIANT 1 — SINGLE VOICE / No reasoning model artefact renders directly to the user. All user-facing content is produced by the question bank and the synthesis renderer, both of which consume reasoning model output as inputs. The user experiences one voice — the coach — across the entire session. Audit records, candidate sets, triangulation results, and frame audits are all internal. |

### Table 3
| INVARIANT 2 — QUESTION DISCIPLINE / Each user-facing layer asks three questions by default. A fourth is permitted only when it is required to keep the session honest — its absence would force a refusal at synthesis. The orchestration tier enforces the cap; the LLM cannot generate a fifth. Compound questions are discouraged: clarity per question matters more than question count. |

### Table 4
| Layer | Name | User-facing | Questions |
| 0 | Frame Audit | No — silent | 0 |
| 1 | Surface | Yes | 3 preferred, 4 max |
| 2 | Depth | Yes | 3 preferred, 4 max |
| 3 | Synthesis | Yes (output) | 0 |
| 4 | Reflection | Yes | 3 fixed |

### Table 5
| Frame audit finding (internal): no decisional framing, no time horizon / "Sounds like something's sitting uneasily here. Before I ask anything else — when you picture this going badly, what does badly look like? And by when would you know it had gone that way?" |

### Table 6
| Frame audit finding (internal): narrow candidate set, user has named two options when class typically presents 4–5 / "You've named A and B as the directions you're weighing. Walk me through how you arrived at those two — and what else was on the table before you set it aside." |

### Table 7
| Frame audit finding (internal): statement tension — hypothesis presupposes its own conclusion / "Before we test this, I want to make sure we're testing the right thing. When you say [X] will happen if [Y] — are you treating [Y] as a given here, or is [Y] part of what we're testing?" |

### Table 8
| Frame audit finding (internal): lens-framing mismatch — CFO requested, framing is operational / "You've asked for a CFO's view. The situation as you've described it is mostly operational — should the CFO weigh in on the operational picture as it stands, or would it help to reframe in financial terms first so the lens fits cleanly?" |

### Table 9
| Refusal triggered at Layer 3 / "I don't have enough to weight scenarios honestly here. The candidates worth examining are clear — there are four of them — but without evidence on [the customer churn pattern across Q1] and [the engineering capacity decisions made in October], I'd be guessing at probabilities. Here's what I can give you. And here's what would change the picture." |

### Table 10
| Auto-activation opening / "Before we run the simulation, I want to make sure we're testing the right thing. The way you've framed this — when you say [X] will happen if [Y] — are you treating [Y] as a given here, or is [Y] part of what we're testing? A few quick questions will help me sharpen the hypothesis before we go further." |

### Table 11
| Position | Job | Output |
| Session entry | Classify initial framing for jailbreak/therapy intent before Layer 0 begins | Pass | soft block | hard block |
| Layer transition | Check subsequent answers remain consistent with executive decision-making domain | Pass | soft block | hard block |
| Pre-output (Layer 3) | Sanitise synthesis output to remove LLM content drift outside Solva's structure | Cleaned synthesis or refusal |

### Table 12
| Therapy redirect / "What you've shared sounds like it matters, and it deserves more than what Solva can give you. Solva is built for executive decision-making — strategic choices, hypothesis testing, situations you're navigating in your professional context. For what you've described, a different kind of support would serve you better. If there's an executive dimension to this — a decision about how you're showing up at work, a strategic choice connected to what you're navigating personally — I can help with that. Want to reframe?" |

### Table 13
| Concern | Solva owns | Synisense owns |
| LLM provider credentials | Nothing | Everything |
| De-identification of content | Nothing | Everything |
| Signal production | Nothing | Everything |
| Reasoning orchestration | Everything | Nothing |
| Frame audit logic | Everything (uses Shield-routed LLM) | Routes the LLM call |
| Question routing | Everything | Nothing |
| Synthesis output schema | Everything | Validates Shield responses against it |
| Orchestration audit log | Everything (Solva-internal) | Nothing |
| Shield audit log | Audit IDs only (as references) | Everything |
| User-facing surface | Everything | Nothing — Synisense has no UI |

### Table 14
| ARCHITECTURAL ENFORCEMENT / Solva is built so that Synisense unavailability is a normal operating state, not an error. The architecture does not provide a fallback path that bypasses Synisense. If Synisense is unavailable, Solva is unavailable. This is by design — it is what makes Akki's safety guarantee structural rather than operational. |

### Table 15
| Metric | Target | How measured |
| Session completion rate | Above 75% | Sessions reaching Layer 4 / sessions started |
| Per-layer drop-off | Below 10% per layer | Layer abandonment / layer entry |
| Median question count per layer | 3 | Audit log analysis |
| Fourth-question usage | Below 25% of layer instances | Audit log analysis |
| Tension trigger rate (Sim) | 20–40% | Auto-activations / hypothesis sessions |
| Refusal rate | 5–15% | Refusal sessions / total sessions |
| Probability weight reproducibility | 100% | Same-input runs producing same weights |
| Citation click-through rate | Above 30% | Citation clicks / sessions reaching Layer 3 |
| Guardrail false-positive rate | Below 2% | Legitimate sessions blocked / sessions |
| User satisfaction (post-session) | Above 4.0 / 5.0 | Optional post-session pulse |
| Conversational descriptor | 5 of 5 testers | Open-ended first-impression interview |
| Time to first synthesis | Under 8 minutes | Median Layer 1 entry to Layer 3 render |
| Material attachment rate | Above 40% | Sessions with material / sessions |
| Solva invocations from other modules | Above 25% | Cross-module entries / total entries |
| Single-voice compliance | 100% | Sampled session inspection; zero audit-vocabulary leak |
| Synisense Shield coverage | 100% | Audit log shows every LLM call routed through Shield |