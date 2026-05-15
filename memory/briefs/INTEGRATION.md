AKKI
Service Integration Brief
How Solva and Synisense deliver Akki's promise
What this document is
The integration specification for Akki — defining how Solva and Synisense Service work together to deliver Akki's promise to enterprises. Akki promises AI that is safe and honest. Synisense delivers the safe. Solva delivers the honest. This document specifies the boundary between them, the contract they share, and the engineering disciplines that keep both services independently sound while jointly fulfilling the promise.
Audience
Engineering leads on both services · Platform architects · Product · Compliance · Security engineering
What this document does not duplicate
The internal architecture of Solva and Synisense are specified in their own briefs. This document specifies only what is true at the boundary between them — the integration. Where the two services are independent, that independence is preserved.

CONTENTS
# Contents
    Glossary of terms
1.  Akki's promise and how the two services deliver it
2.  Boundary and contract
3.  How the services interact at runtime
4.  Audit, observability, and shared concerns
5.  Conflict prevention — the disciplines that keep both services sound
6.  Versioning and evolution
7.  Acceptance criteria for the integration

GLOSSARY
# Glossary of terms
This glossary is the canonical reference for naming. The same terms are used identically across the Solva, Synisense, Akki Chat, and Akki Service Integration briefs. Any apparent variation in this or sibling documents resolves to one of the definitions below.



SECTION 1
# Akki's promise and how the two services deliver it
Akki promises that AI is safe and honest for enterprises. The promise is the company's category claim. It is what distinguishes Akki from products that offer AI capability without addressing the trust gap that prevents enterprise deployment.
The promise is delivered by two services operating in coordination:
## 1.1 Synisense Service — the safe
Synisense Service delivers safe. Safe is a structural property of how data and LLM invocations are handled. It comprises:
- De-identification before any LLM sees enterprise content. Names, account numbers, identifiers, and case references become stable tokens. The LLM works on tokens; re-identification happens only inside the trust boundary.
- Structural encryption. Consumer data is encrypted such that even Syni engineers operating the service cannot read it without explicit authorisation. Privacy is a property of architecture, not policy.
- Audit and provenance. Every operation produces a tamper-evident audit entry. Trust receipts make the governance externally verifiable.
- Behavioural signal production. Synisense's analytics engine produces structured signals from enterprise data — anomaly flags, life-stage indicators, risk scores, operational signals — that other Akki products consume as grounded prior context.
## 1.2 Solva — the honest
Solva delivers honest. Honest is a structural property of how reasoning is produced and presented. It comprises:
- Refusal logic. Solva refuses to produce a probability-weighted diagnosis when evidence is insufficient. The system declines to guess at probabilities rather than fabricate confident-sounding analysis.
- Grounding discipline. Every factual claim in Solva's output traces to user material, prior context retrieved from Synisense, or named situation-class statistics. Ungrounded claims fail schema validation and are not surfaced.
- Single-voice surface. Reasoning machinery runs underneath the conversation. The user meets one voice — the coach. Internal artefacts (frame audits, candidate sets, triangulation results) do not render as user-facing content.
- Reasoning transparency. Every reasoning step is logged. Citations, probability intervals, sensitivity callouts, surfaced tensions — all are user-interrogable.
## 1.3 Why both are necessary
Neither service alone delivers Akki's promise.
Synisense without Solva is governed AI invocation without reasoning discipline. Enterprises get safe LLM access but no protection against fluent guessing, confirmation bias, or the failure modes of asking LLMs for analysis on consequential questions.
Solva without Synisense is structured reasoning without governance. Enterprises get rigorous diagnostic flow but their data passes to LLM providers in identifying form, with no audit, no de-identification, no structural privacy. The reasoning could be honest; the system would not be safe.
Together, the two services produce what neither alone can: rigorous reasoning over enterprise data, where the data is structurally private throughout and the reasoning is structurally honest throughout. That is Akki's category claim.

## 1.4 Other Akki products also depend on this integration
Solva is the most prominent consumer of Synisense, but not the only one. Other Akki products — the standard chat surface, Workspace, Highlights, Cycle Manager, Monitor, Pulse — also consume Synisense for governed LLM access and signal retrieval. The integration disciplines specified in this brief apply to those products as well. Where this brief uses Solva as the example consumer, the principle generalises.

SECTION 2
# Boundary and contract
The boundary between Solva and Synisense is the Synisense API. Solva consumes Synisense exclusively through this API. Synisense does not know which consumer is calling it beyond the consumer identity field on the request.
## 2.1 What is on each side of the boundary

## 2.2 The contract Synisense commits to Solva
Synisense's commitments to any consumer, including Solva:
- Signal schemas are stable within a version. Breaking changes require a new version with at least a 6-month deprecation window.
- Shield contracts are stable. The de-identification guarantee, the audit chain, and the trust receipt schema do not break compatibility without a major version bump.
- Authentication and tenancy semantics are stable. The four-field call envelope (consumer, user, tenant, purpose) is preserved across versions.
- Latency targets are met or breaches are reported. Shield median latency overhead below 300ms; Engine query latency below 500ms median for indexed queries.
- Audit logs are queryable within SLA. Consumers can retrieve audit records for their own calls within 5 minutes of call completion.
## 2.3 The contract Solva commits to Synisense
Solva's obligations as a consumer of Synisense:
- Every LLM call routes through the Shield. Solva does not hold LLM provider credentials and does not bypass Synisense for any reason.
- Every Shield call carries a declared purpose. The purpose is structured (e.g., "solva.layer_0.frame_audit") and validated by Synisense.
- Solva treats Shield refusals as a normal operating mode, not as exceptional errors. Architecture handles refusal gracefully.
- Solva treats Synisense unavailability as a normal operating mode. Sessions pause; data does not leak to ungoverned paths.
- Solva stores Synisense audit IDs in its own session records and references them in its audit log.
- Solva does not cache or replicate Synisense signals beyond the session lifetime. Persistent storage of prior-context signals belongs to Synisense; Solva fetches on demand.
## 2.4 What the contract does not cover
The integration contract is intentionally narrow. The following are explicitly outside it:
- Synisense's internal architecture. Solva does not depend on which databases, queues, or model providers Synisense uses internally.
- Solva's internal architecture. Synisense does not depend on which layers, models, or question banks Solva uses internally.
- Specific LLM providers. Synisense reserves the right to change providers; Solva does not depend on specific provider behaviour.
- Tenant-specific behaviour. Both services apply tenant policy at their own layers; the contract is uniform across tenants.

SECTION 3
# How the services interact at runtime
This section walks through a representative session — a Solva session from initial framing to Layer 3 synthesis — and specifies what passes between Solva and Synisense at each step. The same patterns apply to other Akki product integrations.
## 3.1 Session start
The user opens Solva and selects a sub-module. Solva creates a session record and begins state. No Synisense calls have been made yet. Synisense is not aware the session has started.
## 3.2 User submits initial framing
The user types their initial framing and any attached material. Solva validates the upload (size, format), persists the material to its session-scoped store, and begins Layer 0.
Solva makes its first Synisense calls:
- Engine API query — retrieve any prior context signals relevant to the entities the user has named. Synisense returns matching signals (or empty result if none exist or the user has no access).
- Shield API invoke — run the situation class classifier on the framing. Solva sends the framing as encrypted payload with purpose "solva.layer_0.situation_classification." Synisense de-identifies, routes to an LLM, re-identifies the response, returns the structured classification plus a trust receipt.
- Shield API invoke — run the frame audit. Solva sends the framing, the classification result, and any signals retrieved. Purpose: "solva.layer_0.frame_audit." Synisense returns the FAR plus trust receipt.
Solva stores three trust receipts in the session record. The orchestration audit log captures the model invocations and the Synisense audit IDs.
## 3.3 Layer 1 transition
The frame audit produces a verdict and routing decision. Solva uses these to select the Layer 1 opening question from the question bank. The presentation tier renders the question to the user. No additional Synisense calls are made during the transition itself — the FAR contains everything needed to route.
## 3.4 User answers Layer 1 questions
As the user answers, Solva makes Shield-routed calls for candidate generation (purpose "solva.layer_1.candidate_generation") with the user's answers and FAR. Synisense returns candidate descriptions; Solva persists them with weights and source references.
## 3.5 Layer 2 — triangulation
Layer 2 is the most intensive Synisense interaction. For each Layer 2 answer:
- Engine API query — retrieve additional signals for any new entities or topics surfaced by the answer
- Shield API invoke — claim extraction from the user's narrative (purpose "solva.layer_2.triangulation.claim_extraction")
- Shield API invoke — entailment/contradiction classification per claim against attached evidence (purpose "solva.layer_2.triangulation.entailment_classification")
- Shield API invoke — same against prior context from Synisense signals
- Shield API invoke — tension detection (purpose "solva.layer_2.tension_detection")
Each call returns a trust receipt. Solva builds up a stack of receipts that form the audit trail for the session. Each call's de-identified inputs and outputs are logged in Synisense; Solva logs the orchestration decision the call produced.
## 3.6 Layer 3 — synthesis
Solva's probability weighting engine runs locally — no Synisense call. Probabilities are computed from candidate weights, triangulation alignment, situation class priors, and counterfactual robustness.
Solva then makes Shield-routed calls for narrative generation — the LLM renders scenario narratives, the primary diagnosis, and tension descriptions into coach voice. Purposes include "solva.layer_3.scenario_narrative_generation" and "solva.layer_3.synthesis_rendering."
The synthesis is assembled by Solva from structured outputs. Citations point to attached material and to Synisense signals retrieved during the session. Trust receipts for every Shield call are stored alongside the synthesis.
## 3.7 What the user sees
The user sees one product. They do not see Synisense at any point. The trust receipts are accessible if the user asks for an audit trail (e.g., for compliance review) but they are not foregrounded. The single-voice principle holds across the entire session — Solva renders, Synisense governs.

## 3.8 Trust receipts and external verification
Trust receipts accumulate across the session into a chain. At session completion, Solva exports a session attestation that bundles:
- The synthesis output
- All trust receipts from Synisense
- Solva's orchestration audit summary
- Any tenant compliance metadata required
The attestation is the artefact a tenant administrator (or a regulator) can use to verify that the session was governed end-to-end. It demonstrates the safe (de-identification, audit, trust receipts from Synisense) and the honest (reasoning audit log, citation trace, refusal records from Solva) jointly.

SECTION 4
# Audit, observability, and shared concerns
## 4.1 Two audit logs, one chain
Solva and Synisense maintain separate audit logs:
- Solva's orchestration audit log — reasoning model invocations, routing decisions, candidate generation steps, refusal triggers, layer transitions
- Synisense's service audit log — every API call received, de-identification operations, LLM routing, trust receipts issued, data accesses
The two logs are linked through audit IDs. Every Solva orchestration entry that involves a Synisense call carries the Synisense audit ID. Engineering debugging a session works through Solva's log; when an LLM call is implicated, they follow the audit ID into Synisense's log. The linkage is the chain; neither service owns the full picture alone.
## 4.2 What each side can answer

## 4.3 Shared observability
Both services contribute to dashboards visible to platform engineering and to tenant administrators:
- Session volume and completion rates (Solva)
- Shield invocation rates per consumer and purpose (Synisense)
- Engine query rates and latencies (Synisense)
- Refusal rates per refusal type, per service (both)
- Trust receipt issuance and verification (Synisense)
- Cross-service latency (Solva measures, Synisense reports)
Cross-service incident response uses both observability surfaces. An incident affecting Solva's session completion that traces to Shield latency requires reading both surfaces in sequence.
## 4.4 SLA composition
Akki's user-facing performance is the composition of both services' SLAs. The two services maintain independent SLAs but coordinate on what the user-facing target is.
- Synisense Shield median latency overhead: below 300ms
- Synisense Shield p99 latency overhead: below 1.5s
- Synisense Engine query latency: below 500ms median
- Solva orchestration overhead per layer transition: below 200ms
- End-to-end Solva session time to first synthesis: below 8 minutes (mostly user-time, not system-time)
When user-facing targets are missed, root-cause analysis identifies which service contributed how much. The integration discipline is that neither service blames the other in user-facing error messages; both contribute to a unified incident response.
## 4.5 Encryption and key boundaries
Synisense holds tenant-specific encryption keys. Solva does not hold tenant keys; it operates on data that is either:
- In-flight to/from Synisense (encrypted in transit)
- Within Solva's session-scoped storage (encrypted at rest with Solva's own session keys, separate from Synisense's tenant keys)
A tenant rotating their Synisense keys does not affect Solva session keys. A tenant deleting a Synisense tenant has Synisense data destruction obligations; Solva session data is cleaned up by Solva's session retention policy, triggered by the tenant deletion event.

SECTION 5
# Conflict prevention — the disciplines that keep both services sound
Two services coordinating closely have predictable failure modes. This section names them and specifies the disciplines that prevent each. The current build has no observed conflicts; this is a guard document.
## 5.1 Service contract drift
### What it looks like
Solva starts depending on Synisense behaviour that is not in the API contract — a specific response shape, a particular signal field that happens to be populated, a latency assumption. Synisense changes the implementation; Solva breaks even though the contract was held.
### Prevention
- Contract is documented in the Synisense brief. Solva engineers read the contract and depend only on what is stated.
- Synisense exposes a test environment with contract-compliant responses. Solva integration tests run against it.
- Synisense version increments follow semver. Solva pins to a major version; minor version changes do not break Solva.
- Quarterly contract review: Solva engineering and Synisense engineering meet to identify any implicit dependencies that have crept in.
## 5.2 Naming collision
### What it looks like
Both services use the same term for different things. "Refusal" means evidence-insufficient in Solva and governance-denied in Synisense. Engineers confuse the two; documentation references the wrong refusal type.
### Prevention
- Each service uses qualified names in cross-service communication: "Solva refusal" and "Shield refusal," not just "refusal."
- Shared glossary maintained jointly. Both teams contribute; both teams reference.
- Code reviews flag unqualified terms in cross-service contexts.
## 5.3 Audit ownership ambiguity
### What it looks like
An incident occurs. It is unclear which service's audit log should be authoritative for what happened. Investigation takes longer than it should because the wrong log is consulted first.
### Prevention
- Section 4.2 above specifies which questions are answerable from which log. Engineers consult that table during incident response.
- Audit IDs link the two logs. Every Solva orchestration entry that involves Synisense carries the Synisense audit ID.
- Incident response runbook references both logs by default; investigators are trained to follow the chain.
## 5.4 User experience inconsistency
### What it looks like
The user encounters Synisense behaviour without realising it. Synisense refuses a request on governance grounds; the refusal renders to the user in Synisense's voice (terse, governance-flavoured) rather than in Solva's coach voice. The user experiences two products from inside Akki.
### Prevention
- Synisense never speaks to the user directly. All user-facing copy comes from the consuming product (Solva, Workspace, etc.).
- Synisense returns structured refusals (error class plus reason); Solva translates them into coach voice before surfacing.
- Voice review is part of Solva's acceptance criteria for any new Synisense error class.
- Synisense versioning of error classes is treated as a breaking change for consumers — Solva must update its translation layer.
## 5.5 Build sequencing
### What it looks like
Solva starts building against a Synisense contract that is still in flux. Solva ships features; Synisense changes the contract; Solva has to rework.
### Prevention
- Synisense contract is frozen before Solva builds against it. Contract changes after freeze require a coordinated migration plan.
- Synisense exposes a contract-stable test environment ahead of production. Solva builds against the test environment first.
- Joint roadmap planning quarterly. Solva's needs from Synisense are surfaced before Solva commits to phase deliverables.
- Feature flags allow Solva to ship reasoning features ahead of Synisense capability, with the feature gated until Synisense is ready.
## 5.6 Latency drift
### What it looks like
Synisense Shield latency creeps up over time. Each individual increase is within SLA but the cumulative effect makes Solva sessions feel sluggish. Users abandon mid-session at a rising rate. Neither service alone sees the problem because each meets its own targets.
### Prevention
- End-to-end session latency tracked as a joint metric, not just per-service. Joint metric is reviewed monthly.
- Session abandonment correlation with Shield latency is monitored. Any correlation triggers a joint review.
- SLA targets are tightened jointly when the end-to-end target is approached. Neither service unilaterally relaxes.

SECTION 6
# Versioning and evolution
## 6.1 Independent versioning
Solva and Synisense version independently. Each service ships on its own cadence. The integration is held stable through the API contract — both services can evolve internally without affecting the other.
## 6.2 Synisense contract versioning
Synisense API versions follow semver:
- Major version (vN) — breaking changes. New consumer integrations or migration of existing consumers required. Minimum 6-month deprecation window for prior version.
- Minor version (v1.N) — additive changes. Existing consumers continue to work; new features available to consumers that opt in.
- Patch version (v1.0.N) — non-functional fixes. Transparent to consumers.
Solva pins to a major version. The Solva brief specifies which Synisense major version Solva targets. Upgrading Solva to a new Synisense major requires a migration plan and coordinated build effort.
## 6.3 Joint roadmap touchpoints
Three coordination points per year:
- Annual joint roadmap. Both teams agree priorities for the year, identify dependencies, and surface contract changes needed.
- Quarterly contract review. Either team can propose a contract change. Joint review approves, defers, or rejects.
- Monthly operations review. Both teams review joint metrics — end-to-end latency, abandonment, refusal rates, audit chain integrity.
## 6.4 What changes require joint sign-off
- Any change to the Synisense API contract
- Any change to the trust receipt schema
- Any change to the audit log linkage between the two services
- Any change to the refusal error classes Synisense returns
- Any change to the purpose taxonomy Solva uses when calling Synisense
- Any change to encryption boundaries or key management practices that affect either service

SECTION 7
# Acceptance criteria for the integration
These criteria verify that the integration delivers Akki's promise. They are joint criteria — neither team can meet them alone.
## 7.1 Functional criteria
- End-to-end Solva session completes with every LLM call routed through Synisense Shield. Verified by network inspection and audit log analysis. 100% compliance required.
- Every Solva session has a complete trust receipt chain. The number of receipts matches the number of Shield calls in the orchestration log. 100% required.
- Every claim in a Solva synthesis traces to either user material, an attached document, or a Synisense signal. Ungrounded claims fail schema validation. 100% required.
- Synisense refusals render to the user in coach voice. Verified by inspection of all error-path renderings across 50 simulated refusals. 100% required.
- Solva and Synisense audit logs are linkable by audit ID. Spot-check 100 random orchestration entries; verify each Synisense audit ID resolves to a valid Synisense log entry. 100% required.
## 7.2 Performance criteria
- End-to-end Solva session time to first synthesis below 8 minutes median. Measured across 100 sessions.
- Shield median latency overhead below 300ms. Measured over 1000 Solva-initiated Shield calls.
- Engine query latency below 500ms median for indexed queries. Measured over 1000 Solva-initiated Engine queries.
- Cross-service incident response — mean time to identify which service contributed to a user-facing latency issue: below 15 minutes.
## 7.3 Privacy criteria
- Zero LLM-side exposure of identifying enterprise content. Verified by penetration test against Synisense Shield with Solva-generated traffic.
- Tenant data isolation across services. A Solva session for Tenant A cannot retrieve Synisense signals or invoke Shield calls for Tenant B. Verified by isolation test suite.
- Trust receipts verifiable by tenant administrators. Tenant admin can pull any Solva session attestation and verify the trust receipt chain against Synisense.
## 7.4 Compliance criteria
- Session attestation export functional for any completed Solva session. Tenant administrator can export a session's full audit chain (Solva orchestration + Synisense trust receipts) in a structured format.
- Regulator-readable audit trail. The session attestation is sufficient for a regulator to verify governance and reasoning rigour without privileged access to either service.
- Tenant deletion propagates correctly. Deleting a tenant in Synisense triggers Solva session retention cleanup within published SLA.
## 7.5 User experience criteria
- Five out of five user testers describe Akki as one product, not two, in open-ended first-impression interview.
- Zero testers reference Synisense by name unless prompted to discuss governance specifically.
- Zero testers describe the experience as having "two voices" or "different systems" mid-session.
## 7.6 Engineering discipline criteria
- Quarterly contract review meeting occurs on schedule. Minutes captured. Action items tracked.
- Joint glossary maintained. Both teams contribute. Updates reviewed at quarterly meeting.
- Cross-service incident runbook exists, is current, and has been exercised in the last six months.
- Shared observability dashboards live and reviewed monthly.
## 7.7 Continuous compliance — joint checks
Acceptance criteria phrased per phase are necessary but not sufficient. Between phase gates, builds can drift on either service in ways that break the integration. The following checks run on every release of either service, not only at acceptance gates:
- Joint Shield-coverage check. Every release of any consumer (Solva, chat, Workspace, etc.) verifies that every LLM call in the build routes through Synisense Shield. Any direct provider invocation blocks the release. Run as a cross-service CI check.
- Joint trust receipt chain integrity. Sampled sessions are pulled on every release; the trust receipt chain is verified against Synisense's audit log. Any break in the chain blocks the consumer release.
- Joint single-voice scan. Every release that touches user-facing strings is scanned for cross-service terminology leaks — Synisense vocabulary appearing in consumer surfaces, audit terms appearing in user copy, refusal terminology rendered without coach-voice translation. Any leak blocks the release.
- Joint contract conformance test. Every Synisense release runs the consumer-side integration test suite for all active consumers. Every consumer release runs against the Synisense test environment. Either side breaking the contract blocks the release of the breaking party.
- Joint end-to-end latency check. Median user-facing session latency is monitored continuously. Any sustained degradation triggers a joint review within 48 hours, not at the next monthly operations review.
Continuous compliance is the engineering discipline that prevents the integration documents from becoming aspirational rather than operational. Phase acceptance verifies the foundation; continuous compliance prevents the drift on either side.

— End of Akki Service Integration Brief —

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
| THE COMPOSITION IS THE PROMISE / Akki's value proposition is not the sum of Solva and Synisense. It is the composition. Engineering both services to integrate cleanly is what produces the safe-and-honest property. Engineering them as separate concerns that happen to coexist would not. |

### Table 3
| Concern | Synisense side | Solva side |
| LLM provider relationships | Owned — credentials, contracts, provider routing | Not visible — Solva does not know which provider runs which call |
| De-identification logic | Owned — tokenisation, re-identification, entity resolution | Not implemented — Solva sends content; Synisense handles tokens |
| Behavioural signal production | Owned — ingestion, analytics, signal schemas | Not implemented — Solva queries the signal API |
| Reasoning orchestration | Not implemented — Synisense has no reasoning machinery | Owned — layer state, question routing, candidate sets, triangulation |
| User-facing surface | Not present — Synisense has no UI | Owned — coach voice, conversation flow, synthesis rendering |
| Refusal logic | Owned at governance layer (Shield refuses on policy) | Owned at reasoning layer (Solva refuses on evidence) |
| Audit ownership | Synisense audit log for service operations | Solva orchestration log for reasoning operations |
| Trust receipts | Issued by Synisense per call | Stored by Solva in session record |

### Table 4
| FROM THE USER'S PERSPECTIVE / The user experiences Akki. They do not experience two services coordinating. The integration is invisible. This is intentional — the safe-and-honest property emerges from the composition, but the user does not need to understand the composition to benefit from it. |

### Table 5
| Question | Answerable from |
| Why did Solva ask this question? | Solva orchestration log |
| Why did Solva refuse? | Solva orchestration log |
| What LLM produced this response? | Synisense service log |
| Was this content de-identified? | Synisense service log (trust receipt) |
| Did anyone access this tenant's data? | Synisense service log |
| Did Solva ground this claim? | Solva orchestration log + cited source |
| Which Synisense calls were made in this session? | Solva orchestration log (audit IDs) → Synisense service log (entries) |