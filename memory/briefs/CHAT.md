AKKI CHAT
Developer Brief
The chat surface, its protective layer, and integration with Solva and Synisense
What this document is
The complete specification for the Akki chat surface — what it is, how it protects users from LLM failure modes without breaking the chat affordance, and how it integrates with Solva and Synisense to deliver Akki's promise of safe and honest AI.
Audience
Engineering leads · Applied-AI engineers · Product managers · Designers
Companion documents
Synisense Service Brief — the platform service chat depends on for governed LLM access. Solva Developer Brief — the structured reasoning module chat hands consequential queries to. Akki Service Integration Brief — the architectural disciplines that keep all three components sound.

CONTENTS
# Contents
    Glossary of terms
1.  What Akki chat is
2.  Architecture
3.  The three LLM failure modes the chat protects against
4.  The chat protective layer — how it works
5.  Voice and behaviour
6.  Synisense integration
7.  Solva integration — the hand-off
8.  Calibration, observability, and audit
9.  Build strategy and acceptance criteria

GLOSSARY
# Glossary of terms
This glossary is the canonical reference for naming. The same terms are used identically across the Solva, Synisense, Akki Chat, and Akki Service Integration briefs. Any apparent variation in this or sibling documents resolves to one of the definitions below.



SECTION 1
# What Akki chat is
Akki chat is the highest-traffic surface in the product. Users type questions and get answers. The chat affordance is fast, conversational, and useful for the vast majority of queries — quick lookups, explanations, drafting, brainstorming, casual analysis.
Chat is also where the typical LLM failure modes occur. The user types a consequential question phrased like a casual one. The LLM produces fluent, confident output. The user reads it as analysis and acts on it. Akki chat is built to protect against this category of failure without converting chat into something else.
## 1.1 The dual nature of chat
Akki chat has two responsibilities that exist in tension:
- Preserve the chat affordance. A user typing a casual question gets a casual answer. The product is fast, direct, conversational.
- Protect against LLM failure. When a chat interaction is sliding toward a known failure mode, the system intervenes with the minimum sufficient structure to prevent it — and does so in a way that does not break the chat affordance for everything else.
Resolving this tension is the central engineering problem of chat. Most chat interactions pass through with no intervention. A minority trigger protective behaviour. The product feels like chat throughout.
## 1.2 Akki chat is not the Solva module
The Solva module is a separate surface. Users enter Solva by selecting a sub-module (Seek Clarity, Develop Strategy, Simulate Hypothesis, Get Perspective). Inside Solva, they go through a structured five-layer reasoning session — explicit opt-in to a fully structured experience.
Chat is not opt-in to structure. Users arrive at chat with a question and an expectation of a quick answer. The protective layer respects this. It does not auto-route users into Solva sessions for every consequential question; it intervenes with the minimum needed and, where deeper reasoning is warranted, offers a hand-off to Solva that the user can accept or decline.

## 1.3 Akki chat in the promise
Akki promises that AI is safe and honest for enterprises. Chat delivers both, by composition with the other Akki services:
- Safe — every LLM invocation from chat routes through Synisense Service. The Shield handles de-identification, audit, and provenance. Chat does not hold LLM provider credentials and has no path to invoke an LLM outside Synisense.
- Honest — the chat protective layer detects when an interaction is sliding toward one of three named LLM failure modes (hypothesis without structure, plausible output accepted without testing, fluency mistaken for diagnosis) and intervenes. For sufficiently consequential queries, the layer offers a hand-off to Solva.
Chat is the surface most enterprise users will encounter most often. The promise is delivered or broken here at scale.

SECTION 2
# Architecture
Akki chat is built as a four-tier system: presentation (the chat UI), the protective layer (middleware that runs on every message), reasoning (LLM invocation through Synisense), and audit (event logging and observability).
## 2.1 Architectural invariants



## 2.2 The four tiers
### Presentation tier
The chat UI within the Akki application. Renders messages, message history, attachment surfaces, citation popovers, intervention prompts, and the Solva hand-off offer. Implements the coach voice. Does not produce content directly — content comes from the reasoning tier through the protective layer.
### Protective layer (the middleware)
Sits between the user's chat input and the standard LLM response generator. Runs three failure-mode detectors in parallel with response generation. Decides whether to intervene, annotate, or pass through. Specified in Section 4.
### Reasoning tier
LLM-powered work, routed entirely through Synisense Service. Chat does not hold LLM provider credentials and does not invoke any LLM directly. Every call passes through the Synisense Shield API.
### Audit tier
Chat session audit log. Captures every message, every detector firing, every intervention, every Synisense audit ID referenced. Specified in Section 8.
## 2.3 Data model
A chat session is the unit of state:
chat_session {
  session_id: uuid
  user_id: uuid
  context_id: uuid
  messages: array<message>
  protective_layer_events: array<protective_event>
  synisense_audit_ids: array<uuid>
  created_at: timestamp
}

message {
  message_id: uuid
  role: enum                     // user | assistant
  content: text
  annotations: array<annotation> // for grounding flags
  attached_materials: array<material_ref>
  timestamp: timestamp
}

protective_event {
  message_id: uuid
  detectors_fired: array<enum>   // A | B | C
  detector_scores: jsonb
  intervention_type: enum        // none | hypothesis_test |
                                 // annotation | consequence_check |
                                 // solva_handoff_offered
  template_id: string
  user_follow_through: enum      // engaged | ignored | abandoned
  handoff_accepted: bool
  timestamp: timestamp
}

## 2.4 Component overview
The protective layer comprises five components:
- Failure-mode detectors — three parallel classifiers (A, B, C) running on each message
- Response orchestrator — collects detector outputs and decides intervention type
- Template renderer — produces intervention copy in coach voice from versioned templates
- Solva hand-off agent — when consequence threshold is met, offers Solva module entry
- Audit recorder — writes protective_event entries for every message
Each component is specified in Section 4.

SECTION 3
# The three LLM failure modes the chat protects against
LLMs fail predictably in three ways on consequential questions in chat. Each failure mode has a defined detector, a defined response, and a defined acceptance test. The failure modes are addressed at the chat surface; the protective layer is the engineering response to each.
## 3.1 Failure Mode A — Hypothesis without structure
### What it looks like
The user asks a question that contains an embedded hypothesis the LLM is being asked to confirm. The structure of the question pre-loads the answer.
- "Why is our customer concentration risk increasing?" — assumes it is increasing
- "How do we fix the engineering capacity problem?" — assumes there is a capacity problem and that it is solvable
- "What's the best way to approach the board on the restructuring?" — assumes restructuring is the right path
The LLM, given any of these, will produce fluent output that confirms the hypothesis. The user wanted an answer; the system gave one. Neither party tested the hypothesis.
### Why this is a failure
The user's actual situation is not what the question described. Confirming a misframed hypothesis produces analysis that is internally coherent and externally wrong. Acting on it costs the enterprise.
## 3.2 Failure Mode B — Plausible-sounding output accepted without testing
### What it looks like
The LLM produces a response that contains factual claims, numerical estimates, or recommendations that sound authoritative but are not grounded in evidence available to the system. The user reads the fluent output and treats it as analysis.
- "Customer concentration above 20% is generally considered a risk threshold" — sounds authoritative, may or may not be true for the user's industry
- "Most mid-market companies in this situation see a 6-month recovery cycle" — invented statistic, fluently rendered
- "The optimal headcount ratio for your stage is typically 1:12" — heuristic-as-fact
These are not hallucinations in the strict sense — they may be approximately true. They are unverified claims rendered as verified. The user has no way to tell the difference from inside the chat.
### Why this is a failure
Decisions get made on numbers that have the texture of evidence but no evidentiary backing. The user cannot inspect what the system actually knew when it produced the claim. The asymmetry between fluency and grounding is the failure.
## 3.3 Failure Mode C — Fluency mistaken for diagnosis
### What it looks like
The user asks a consequential question and the LLM produces a long, structured-sounding response — bulleted lists, sub-headings, confident framings — that reads as if a diagnosis has occurred. No actual diagnostic process has occurred. The fluency creates the impression of rigour.
- "Should I let go of my Head of Sales?" responded to with a 600-word answer, four bullet points, and a recommendation
- "What's wrong with our product strategy?" responded to with a structured critique that is pattern-matched to the question's phrasing
- "Why is morale declining on my team?" responded to with five plausible causes, none grounded in the user's actual team
These responses are the most dangerous of the three failure modes because they look most like what the user came for. The user feels they have received analysis. They have received fluent guessing.
### Why this is a failure
Consequential decisions are made on outputs that feel rigorous but are not. The cost is highest for this failure mode because the questions are the most consequential and the outputs are the most credible-feeling.
## 3.4 What about other failure modes
Other LLM failure modes exist — anchoring bias, sunk-cost rationalisation, recency bias, sycophancy. These are not addressed in v1. The chat protective layer is scoped to the three modes named above because they cover the highest-frequency, highest-consequence failures in executive use. Additional modes can be added to the layer as separate detectors without restructuring.

SECTION 4
# The chat protective layer — how it works
The protective layer is middleware between user input and the standard LLM response. It runs three detectors in parallel with response generation. Detector outputs feed an orchestrator that decides one of five outcomes: pass through unchanged, insert a hypothesis test, annotate the response, change the response substantively, or offer a Solva hand-off.
## 4.1 Pipeline
Five stages run on every chat message:
- Receive — user message arrives. Session context, attached materials, and prior turns are available.
- Detect (parallel) — three detectors run concurrently with the main response generator. Detectors A and C run on the user's message; Detector B runs on the draft response as it begins streaming.
- Decide — the orchestrator collects detector outputs and selects the intervention type.
- Render — response (standard, annotated, or template) is rendered to the user.
- Log — every detector firing, every intervention, every user follow-through is logged.
## 4.2 Failure Mode A detector — hypothesis embedded in question
### Method
LLM-based classifier with structured output, routed through Synisense Shield. Purpose: "chat.fm_a.hypothesis_detection." Output: a score (0–1) indicating the degree to which the question presupposes its conclusion. Augmented by rule-based patterns for known constructions ("why is X happening," "how do we fix X," "what's the best way to do X"). Threshold tuned conservatively — false-positive rate target below 5%.
### Response
When the detector fires above threshold, the system inserts a one-sentence test of the embedded hypothesis before answering. The test is conversational. The user can ignore it and the chat continues; if the user engages, the conversation deepens before the LLM produces its main response.

If the user confirms the hypothesis ("yes, it's increasing, here's the data"), the system answers as asked. If the user reframes ("actually I'm not sure, I'm seeing churn in two accounts"), the system answers the reframed question, which is a different and more useful answer.
### Engineering invariant
The hypothesis-test sentence is templated, not LLM-generated. Templates are versioned per pattern type. The classifier identifies the pattern; the template renders the response. This prevents the LLM from softening the test into deference.
## 4.3 Failure Mode B detector — ungrounded fluent claims
### Method
Two-part detection runs on the LLM's draft response before it is shown to the user:
- Factual-claim extractor — runs on the draft response, identifies sentences containing specific numerical claims, statistical statements, or appeals to general practice. LLM-based with structured output, Shield-routed. Purpose: "chat.fm_b.claim_extraction."
- Grounding check — for each extracted claim, the system checks whether the claim is grounded in (a) attached material in the session, (b) prior context retrieved from Synisense signals, or (c) explicit citation to a known authoritative source. Claims that fail all three checks are flagged.
### Response
When ungrounded factual claims are detected, the system does not block the response. It annotates the response visually — flagged sentences are rendered with a subtle indicator (a thin amber underline or a marker icon) — and adds a single line at the end of the response acknowledging what was not grounded.

The user can hover or click any flagged sentence to see why it was flagged. The visual treatment is calm — informational, not alarming. The point is to make the difference between grounded and ungrounded content visible, not to interrupt the conversation.
### Engineering invariant
The annotation is rendered by the presentation tier from a structured field on the response object. The LLM does not write its own caveats inline — the caveats are added by the protective layer based on the grounding check output. This prevents the LLM from learning to pre-emptively hedge in order to suppress the annotation.
## 4.4 Failure Mode C detector — fluency mistaken for diagnosis
### Method
Consequence-versus-evidence ratio detector. Two-part check:
- Consequence classifier — identifies whether the user's question is consequential (decisions about people, capital, strategic direction, irreversible actions). LLM-based with structured output, Shield-routed. Purpose: "chat.fm_c.consequence_classification." Tuned against a labelled set of consequential vs casual queries.
- Evidence audit — checks whether the session contains sufficient evidence to support a substantive response (attached material relevant to the question, prior session context, or specific facts in the user's framing). Output: sufficient, thin, or insufficient.
When the question is consequential AND the evidence is thin or insufficient, the detector fires. The intervention is the strongest of the three — it changes the response itself, not just annotates it.
### Response
The system does not produce the fluent response the user expected. It produces a different response — shorter, more honest, structured around what the system can and cannot answer. It also offers a Solva hand-off.

The user has three paths: provide the missing context (which produces a grounded chat response), accept the generic answer (rendered with explicit caveats), or open a Solva session (specified in Section 7). Either way, the user has been made aware that the original question, as asked, was not answerable with rigour.
### Engineering invariant
The consequence classifier and the evidence audit are independent. Both must fire for Failure Mode C to activate. A consequential question with sufficient evidence proceeds normally. A casual question with thin evidence proceeds normally. Only the intersection triggers the response template.
## 4.5 Intervention strength is proportionate

Proportionate intervention is the architectural principle that preserves the chat affordance. Mode A inserts; Mode B annotates; only Mode C replaces. A user typing casual questions never encounters Mode C. A user typing a question that genuinely warrants Solva is offered Solva.

SECTION 5
# Voice and behaviour
Akki chat shares the single-voice principle with Solva. The user meets one voice — the coach — across the entire product. When the protective layer intervenes, the intervention sounds like the same voice the user has been talking to, not a different system.
## 5.1 Three voice rules
- Conversational, not clinical. Interventions are written as the next thing a thoughtful person would say in the conversation, not as system notices. "Quick check before I answer" not "FAILURE MODE A DETECTED."
- Proportionate to the risk. Mode A inserts a sentence. Mode B annotates without changing the response. Mode C changes the response substantively. The intervention strength matches the failure severity.
- Always offers a path forward. No intervention leaves the user with a refusal alone. Every template gives the user a way to proceed — answer the test question, provide more context, accept the generic response with caveats, or open a Solva session. Refusal without a forward path is bad chat affordance.
## 5.2 What never happens
- Chat never blocks a response without offering an alternative. "I can't answer that" is not a chat response. "I can answer that two different ways — which would help more" is.
- Chat never lectures the user about LLM limitations. The user did not come to chat to be educated about epistemology. The intervention does its work conversationally and moves on.
- Chat never references its own detection mechanism. The user does not learn that "Failure Mode A" exists. The intervention is voiced as the coach's own observation, not as a system flag.
- Chat never auto-routes to Solva without consent. Solva hand-offs are offered; never imposed. The user clicks through to Solva only by explicit choice.
- Chat never produces user-facing content from Synisense directly. Synisense governance behaviour (refusal, de-identification failures) is translated into coach voice before surfacing.
## 5.3 Sample sequences — start to end
### Sequence 1 — Mode A fires, user engages, response is better
User: "Why is our customer concentration risk increasing?"
Chat: "Before I answer — you're asking why customer concentration risk is increasing. Quick check: do you know it's increasing, or are you noticing signals and wondering if that's the explanation? I can answer either question, but the answer's different."
User: "Honestly, I'm not sure. Two of our top accounts have been slower to renew this quarter."
Chat: "That's a different question and a more useful one. Slower renewal on two top accounts is a renewal-velocity signal — concentration risk is one possible explanation but it's not the only one. Want me to walk through what could be behind slower renewals, or look specifically at whether concentration risk fits the pattern?"
### Sequence 2 — Mode B fires, user gets annotated response
User: "What's a healthy customer concentration ratio for a SaaS company at our stage?"
Chat (response with annotated claims): "For SaaS companies at Series B–C stage, the general benchmark is that no single customer should account for more than 10–15% of ARR, and the top 10 customers combined should ideally be below 40–50%. These ranges come from venture capital diligence frameworks and are sometimes treated as risk thresholds in board reporting..."
Chat (note appended): "Two figures here — the 10–15% single-customer threshold and the 40–50% top-10 figure — are general-practice references, not facts about your specific stage or sector. If they're going into a board discussion, worth verifying against your peer-set benchmarks."
### Sequence 3 — Mode C fires, user accepts the Solva hand-off
User: "Should I let go of my Head of Sales?"
Chat: "That's a real question and I don't want to answer it with a generic framework. To be useful here I'd need a bit more — what's been happening with the Head of Sales over the last quarter, and what would have to be true for letting them go to be the right call. If you want a quick answer to the general question, I can give that too — but I'd rather give you something specific. This is also the kind of question Solva is built for if you want depth. Which would help most?"
User: "Open Solva."
Chat: "Opening Develop Strategy. I'll carry your initial framing across — you can refine it as we go."
The session continues inside the Solva module. Specified in Section 7.

SECTION 6
# Synisense integration
Akki chat depends on Synisense Service for two functions: governed LLM invocation (Shield API) and prior-context signal retrieval (Engine API). Chat does not hold LLM provider credentials. Every LLM call passes through the Shield. Every signal retrieval passes through the Engine.
## 6.1 Shield API — every LLM call
Every LLM invocation from chat is a Shield call. This includes:
- The standard chat response generator — purpose "chat.standard_response"
- Failure Mode A detector (hypothesis classification) — purpose "chat.fm_a.hypothesis_detection"
- Failure Mode B factual-claim extractor — purpose "chat.fm_b.claim_extraction"
- Failure Mode C consequence classifier — purpose "chat.fm_c.consequence_classification"
- Any tool-use or sub-task LLM invocations chat may perform
Each call carries the four-field envelope (consumer = chat, user, tenant, purpose) and returns a structured response plus a trust receipt. Chat stores the trust receipt in the session record.
## 6.2 Engine API — prior-context signals
Chat retrieves signals from the Engine API to ground responses when relevant. Examples:
- User asks about a specific entity (customer, account, team) — chat queries Engine for recent signals about that entity
- Failure Mode B grounding check — Engine signals are one of the three grounding sources checked
- Failure Mode C evidence audit — Engine signals contribute to the evidence-sufficiency assessment
Signals retrieved during a chat session are scoped to the user's accessible contexts. Synisense enforces tenancy at the Engine API; chat respects the enforcement and does not attempt to query across context boundaries.
## 6.3 Trust receipts and chat audit
Each Shield call produces a trust receipt. Chat stores receipts in the session record. At any point, the user (or a tenant administrator) can pull the full receipt chain for any chat session as proof that every LLM call was governed.
This is the externalisation of the safe property of Akki's promise. Even in casual chat, every LLM invocation is auditable. The user does not have to think about it — but it is there when they need it.
## 6.4 Handling Synisense degradation
Synisense can degrade in three ways. Chat must handle each:
- Engine signal staleness — chat proceeds with stale signals if within tolerance; the Failure Mode B grounding check accounts for signal freshness when assessing claims
- Shield SERVICE_UNAVAILABLE — chat cannot proceed. New messages are paused with a clear message; users can resume when Synisense is available. Chat does not fall back to an ungoverned LLM path; there is no such path.
- Shield GOVERNANCE_REFUSED — chat surfaces the refusal to the user in coach voice. Synisense refused on policy grounds, and chat does not work around governance.

## 6.5 What chat owns vs what Synisense owns


SECTION 7
# Solva integration — the hand-off
When Failure Mode C fires, chat offers a Solva hand-off. The hand-off is the path from casual chat to structured reasoning, taken only with the user's explicit consent. This section specifies how the hand-off works at the boundary between chat and Solva.
## 7.1 When the hand-off is offered
The hand-off is offered specifically when Failure Mode C fires — consequential question, thin evidence. It is not offered for Mode A or Mode B; those interventions stay inside chat.
The hand-off offer is contextual: chat suggests the specific Solva sub-module most likely to be useful. "This sounds like a Develop Strategy session" or "This might be worth a Seek Clarity diagnostic." The user accepts, declines, or asks for the generic answer first.
## 7.2 What carries across
When the user accepts the hand-off, chat transitions into the Solva module. The following carries across:
- The user's original question becomes the Solva session's initial framing
- Any materials attached in chat become Solva attachments
- Recent chat history relevant to the question is summarised and added to Solva session context (in coach voice, not as raw chat log)
- Trust receipts from chat are linked to the new Solva session
What does not carry across: the chat protective layer's detector outputs and the Mode C intervention. Those stay in the chat session audit; Solva starts fresh with its own reasoning models. The user experiences continuity of conversation; the system maintains separation of orchestration.
## 7.3 What happens inside Solva
Inside Solva, the user goes through the standard five-layer reasoning journey. Layer 0 runs the frame audit on the carried-across framing. Layer 1 opens with the question that addresses whatever the frame audit identified. The chat hand-off is invisible at this point — the user is in Solva, talking to the coach.
The Solva session produces its standard output: probability-weighted scenarios, sensitivity analysis, evidence trace, surfaced tensions, reflection questions. At session completion, the user can return to chat or continue in Solva. If they return, the synthesis is summarised back into the chat conversation.
## 7.4 What does not happen
- Chat never auto-routes to Solva. The hand-off requires explicit user consent.
- Chat never opens Solva for Mode A or Mode B interventions. Those are chat-internal.
- Chat never opens Solva on casual queries that don't meet the consequence-and-evidence threshold.
- Solva never runs in the background while the user is in chat. Solva is opt-in, fully-foregrounded.
- Chat never tries to be Solva. The protective layer is the chat surface's protection — it is not a lite version of the reasoning module.
## 7.5 The reverse direction
After a Solva session completes, the user can return to chat and continue conversation about the session's findings. The synthesis is available as context for follow-up chat queries. The relationship is one-way at the hand-off point (chat → Solva) and bidirectional thereafter (Solva session is accessible from chat context).
## 7.6 The composition
Together, chat and Solva form a graduated reasoning surface. Casual questions stay in chat. Consequential questions with sufficient evidence get fluent answers with appropriate annotation. Consequential questions with thin evidence either get re-scoped through chat protection or escalated to Solva. The user is met where they are; the system applies the appropriate intensity of structure.


SECTION 8
# Calibration, observability, and audit
The protective layer is a behavioural intervention. Its calibration matters more than most product systems because the failure mode of over-intervention (interrupting casual chat) is as bad as under-intervention (letting failure modes pass).
## 8.1 Initial calibration thresholds
Each detector has a threshold that determines firing. Initial thresholds are conservative — the system errs on the side of letting chat be chat.

## 8.2 Chat session audit log
Every chat session has an audit log capturing:
- Every message (user and assistant)
- Every detector firing per message, with scores
- Every intervention triggered, with template ID used
- Every user follow-through outcome (engaged, ignored, abandoned)
- Every Synisense audit ID for every LLM call made on the session's behalf
- Every hand-off offer and outcome (accepted, declined)
The chat audit log is separate from but linked to the Synisense service audit log. Engineers debugging a chat session work through the chat audit log; when an LLM call is implicated, they follow the Synisense audit ID into the Synisense log.
## 8.3 Observability
Operational metrics, reviewed daily during build and weekly post-launch:
- Per-detector firing rate, by user segment
- Per-intervention user follow-through rate
- Solva hand-off offer rate, acceptance rate, and post-handoff session completion rate
- False-positive feedback — explicit user signals ("this wasn't helpful") and implicit signals (user rephrases or abandons within 60s of intervention)
- End-to-end chat latency, with Synisense Shield latency as a sub-component
- Distribution of detector scores — to identify whether thresholds need adjustment
## 8.4 Calibration loop
Weekly during build, monthly post-launch. Three calibration questions:
- Are the detectors firing on the right queries? Sample of fired and not-fired queries reviewed by the product team.
- Are users engaging with interventions or ignoring them? Low engagement on a specific intervention type suggests the voice or the offered path forward needs revision.
- Are users who engage with interventions ending up with better outcomes than users who don't? Measured by user-reported usefulness on completed chat threads and by Solva session completion rates for hand-offs.
## 8.5 What is learned, what is not
The protective layer learns thresholds, template effectiveness, and detector calibration from aggregated session data. It does not learn user-specific patterns in v1 — every user sees the same detection logic. Per-user adaptation is deferred to v2 and gated on demonstrated value of the v1 system.
## 8.6 Privacy of audit data
Chat audit logs are stored with tenant-specific encryption. Like Solva and other Akki products, chat does not duplicate Synisense audit data — it stores references. The chat audit captures chat-orchestration decisions; the Synisense audit captures LLM-call details. The chain is the linkage.

SECTION 9
# Build strategy and acceptance criteria
## 9.1 Build phases
### Phase 1 — Chat foundation and Synisense integration (weeks 1–5)
- Chat surface and session storage
- Message ingestion and rendering
- Material attachment for chat sessions
- Synisense Shield integration for every LLM call
- Synisense Engine integration for signal retrieval
- Trust receipt storage and audit log linkage
- Chat session audit log
Phase 1 acceptance criteria
- Standard chat experience works end-to-end with every LLM call routing through Synisense Shield
- Trust receipts captured for every Shield call and linkable to chat session entries
- Engine API integration verified — signal retrieval scoped to user's accessible contexts
- No path to invoke an LLM outside Synisense, verified by network inspection and credential audit
- Chat latency overhead from Shield routing below 300ms median
### Phase 2 — Protective layer middleware and detectors (weeks 6–10)
- Protective layer middleware between chat input and LLM response generator
- Response orchestrator with five outcome paths (pass, A intervention, B annotation, C intervention, Solva hand-off offer)
- Failure Mode A detector — classifier and pattern rules
- Failure Mode B detector — factual-claim extraction and grounding check pipeline
- Failure Mode C detector — consequence classifier and evidence audit
- Template renderer with versioned response templates per failure mode
- Protective event logging extension to chat audit
Phase 2 acceptance criteria
- Standard chat experience is unchanged when no detector fires — verified on 100 sample casual queries
- Failure Mode A detector — sensitivity above 80%, specificity above 90% on a curated test set of 100 queries
- Failure Mode B detector — flags ungrounded claims with above 85% precision against a labelled gold set
- Failure Mode C detector — fires on at least 90% of a curated set of 30 consequential-but-evidence-thin queries, and on below 5% of casual queries
- Latency overhead from protective layer below 200ms median
### Phase 3 — Voice, hand-off, and Solva integration (weeks 11–14)
- Voice rule enforcement in all templates
- Annotation rendering in chat presentation tier (visual indicators for Mode B)
- Solva hand-off offer — sub-module selection logic
- Hand-off transition — initial framing, material, and chat context carry-across into Solva
- Return-to-chat from Solva, with synthesis summary integration
- Observability dashboards
- Calibration loop process
Phase 3 acceptance criteria
- Each intervention template renders in coach voice — verified by inspection across all template variants
- Single-voice compliance — no system-flag language, no LLM-epistemology lectures, no detector mechanism references in user-facing text
- Hand-off carry-across verified — Solva sessions opened from chat have correct initial framing, attached materials, and chat-context summary
- Return-from-Solva integration verified — synthesis available as context for follow-up chat queries
- Hand-off offer acceptance rate above 20% when offered
- Solva session completion rate from hand-offs at or above standalone Solva session completion rate
### Phase 4 — Calibration, polish, scale (weeks 15–17)
- Threshold tuning based on Phase 3 calibration data
- Template refinement based on follow-through rates
- Failure-mode coverage review — confirm no consequential failure modes are passing through
- Capacity testing at expected production load
- Operational runbooks for chat incidents (with Synisense and Solva cross-reference)
Phase 4 acceptance criteria
- False-positive rate below 5% on a sample of 200 chat sessions
- User follow-through rate above 40% on Mode A interventions, above 30% on Mode B annotations, above 50% on Mode C interventions
- End-to-end chat latency targets met under simulated production load
- Incident response runbook exercised at least once, covering all three failure paths (chat-only, Synisense-implicated, Solva-implicated)
## 9.2 Build principles
### Preserve the chat affordance
The default chat experience must remain fast, conversational, and direct. Every intervention is a tax on that experience and must earn its place. Conservative thresholds, proportionate responses, and forward paths are non-negotiable.
### Voice continuity with Solva
The user must not experience chat as a separate product from Solva. The voice is the same coach, the values are the same, and the hand-off is a deepening, not a switch. Two surfaces, one product.
### Governance is structural
Every LLM call routes through Synisense Shield. Architecture enforces this; no operational policy is required to uphold it. The build review rejects any path that would allow LLM invocation outside the Shield.
### Make protection compounding, not redundant
Chat's protective layer and Solva's reasoning discipline protect against the same family of failure modes at different intensities. Components are shared where possible (claim extractor, grounding check), the audit chain is shared, voice is shared. Investment in one strengthens the other.
## 9.3 Continuous compliance checks
Acceptance criteria phrased per phase are necessary but not sufficient. Between phase gates, builds can drift back into the failure modes the architecture is built to prevent. The following checks run on every release, not only at phase acceptance:
- Single-voice compliance scan. Automated inspection of all user-facing strings introduced or modified in the release. Any string containing internal failure-mode labels ("Failure Mode A," "FM-A," "hypothesis_detection," etc.), audit terminology, detector mechanism references, or Synisense vocabulary triggers a build block. Internal labels are confined to the orchestration layer and the audit log; they must never appear in template copy or in any user-facing surface.
- Synisense Shield coverage check. Every LLM call path in the build — including detector calls, response generation, and any sub-task invocations — is verified to route through the Shield. Any path introducing direct LLM provider invocation triggers a build block.
- Intervention proportionality check. Audit logs from staging are sampled on every release; if intervention rate exceeds the threshold (5% of all queries for Mode C, 35% for Mode B, 15% for Mode A), the release is held for calibration review. Over-firing breaks the chat affordance even with perfect voice.
- Trust receipt completeness. Every Shield call in staging is verified to produce a stored trust receipt. Missing receipts block the release.
- Hand-off carry-across check. Test scenarios that exercise the Solva hand-off are run on every release; initial framing, attached materials, and context summary must transfer correctly. Any data loss in transition blocks the release.
Continuous compliance is the engineering discipline that prevents the documents from becoming aspirational rather than operational. Phase acceptance verifies the foundation; continuous compliance prevents the drift.
## 9.4 Out of scope for v1
- Per-user adaptive thresholds — same detection logic for every user in v1
- Detection of additional failure modes (anchoring bias, sunk-cost rationalisation) — flagged for v2
- Cross-session pattern detection — "you asked a similar consequential question last week" is a v2 concern
- Voice and audio chat interfaces — text-only in v1
- Multi-user chat sessions — single-user in v1
- Chat-to-chat hand-offs (escalating to a human) — Solva is the only hand-off target in v1
## 9.5 Success metrics for v1

— End of Akki Chat developer brief —

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
| Failure Mode A, B, C | Internal labels for the three LLM failure modes the chat protective layer detects: hypothesis without structure (A), plausible output accepted without testing (B), fluency mistaken for diagnosis (C). These labels are internal to the engineering team and must never appear in user-facing copy. |

### Table 2
| THE FUNDAMENTAL DISCIPLINE / The chat affordance is preserved by default. Protection activates conditionally — invisible until a specific failure mode is detected, and proportionate to the risk. No casual question is treated as a consequential question. No consequential question is given a fluent guess in place of structured reasoning. |

### Table 3
| INVARIANT 1 — CHAT AFFORDANCE PRESERVED / The default behaviour is unmodified chat. The protective layer's interventions are scoped, proportionate, and conservative. A user typing 95% of casual queries experiences chat unchanged. Engineering reviews reject any design that adds friction or latency to the default path. |

### Table 4
| INVARIANT 2 — NO UNGOVERNED LLM PATH / Every LLM invocation from chat — for the user-facing response, for the protective detectors, for any internal processing — routes through Synisense Shield. Chat does not hold LLM provider credentials. The architecture enforces this at the infrastructure level. |

### Table 5
| INVARIANT 3 — SINGLE AKKI VOICE / Chat speaks in the same voice as Solva — the coach. When the protective layer intervenes, the user does not experience a different system speaking; they experience the coach noticing something. The product is one product. Two surfaces, one voice. |

### Table 6
| Failure Mode A — intervention voice / "Before I answer — you're asking why customer concentration risk is increasing. Quick check: do you know it's increasing, or are you noticing signals and wondering if that's the explanation? I can answer either question, but the answer's different." |

### Table 7
| Failure Mode B — annotation voice / "Note: two claims in this response — the 20% concentration threshold and the 6-month recovery cycle — are general-practice references rather than facts about your specific situation. If they matter to your decision, worth verifying against your data." |

### Table 8
| Failure Mode C — intervention voice / "That's a real question and I don't want to answer it with a generic framework. To be useful here I'd need a bit more — what's been happening with the Head of Sales over the last quarter, and what would have to be true for letting them go to be the right call. If you want a quick answer to the general 'when to let go of a sales lead' question, I can give that too — but I'd rather give you something specific to your situation. This is also the kind of question Solva is built for if you want depth — I can open a Develop Strategy session, your call. Which would help most?" |

### Table 9
| Failure mode | Intervention strength | What changes |
| A — hypothesis embedded | Lightest | One sentence inserted before the response |
| B — ungrounded claims | Light-moderate | Visual annotation on flagged sentences; response content unchanged |
| C — fluency mistaken for diagnosis | Strongest | Response substantively different; Solva hand-off offered |

### Table 10
| THE ARCHITECTURAL ENFORCEMENT / Chat is built so that Synisense unavailability is a normal operating state, not an error. No path bypasses the Shield. If Synisense is unavailable, chat is unavailable. This is by design — it is what makes the safe property of Akki's promise structural rather than operational. |

### Table 11
| Concern | Chat owns | Synisense owns |
| LLM provider credentials | Nothing | Everything |
| De-identification of content | Nothing | Everything |
| Signal production | Nothing | Everything |
| Protective layer detection logic | Everything | Routes the LLM calls |
| Response orchestration | Everything | Nothing |
| Trust receipt storage in session | Chat stores references | Synisense owns the trust chain |
| User-facing surface | Everything | Nothing — Synisense has no UI |
| Conversation history | Chat owns session storage | Nothing |

### Table 12
| THE PRODUCT IS THE COMPOSITION / Akki is not chat. Akki is not Solva. Akki is chat-plus-Solva, with Synisense governing both, all behind a single coach voice. The user does not have to choose between conversation and rigour — the product chooses, conservatively, on their behalf, and offers them the escalation when it matters. |

### Table 13
| Detector | Initial threshold | Target firing rate | Target false-positive rate |
| Failure Mode A | 0.75 score | 8–15% of consequential queries | Below 5% |
| Failure Mode B | Any ungrounded factual claim | 20–35% of substantive responses | Below 8% |
| Failure Mode C | Consequential AND evidence-thin | 3–6% of all queries | Below 3% |

### Table 14
| Metric | Target | How measured |
| Chat experience preservation | ≥95% of sessions with zero intervention | Audit log analysis |
| Detector precision (avg across three) | Above 80% | Labelled gold set evaluation |
| User follow-through on interventions | Above 45% average | Audit log: engaged / ignored / abandoned |
| False-positive complaint rate | Below 2% of intervened sessions | Explicit user feedback |
| Solva hand-off acceptance rate | Above 20% when offered | Audit log: offers vs accepts |
| Voice compliance | 100% | Sampled inspection of intervention text |
| Synisense Shield coverage | 100% | Audit log shows every LLM call routed through Shield |
| Latency overhead (protective layer) | Below 200ms median | Performance telemetry |
| End-to-end chat latency | Below 1.5s median for standard responses | Performance telemetry |
| Single-voice compliance | 100% | Sampled inspection — no system-flag language anywhere |
| Repeat-question rate after intervention | Below baseline | Sessions where user rephrases within 60s — proxy for intervention helping |