SYNISENSE
Service Developer Brief
Version 1 — First specification
What this is
The first standalone specification of Synisense Service — a platform service consumed by Akki products including Solva. Two functions in one service: a behavioural analytics engine that produces structured signals from enterprise data, and a Shield governance layer that handles de-identification, encryption, and audit before any LLM is invoked.
Synisense's role in Akki's promise
Akki promises to make AI safe and honest for enterprises. Synisense delivers the safe — structural privacy, governed access, signal integrity, audit. Solva delivers the honest. Both services together make Akki's promise. Neither alone does.
Audience
Platform engineering · Applied-AI engineers · Security engineering · Compliance · Product managers building on Synisense

CONTENTS
# Contents
    Glossary of terms
1.  What Synisense is
2.  Service architecture
3.  The Behavioural Analytics Engine
4.  The Shield
5.  Service API and consumer contract
6.  Audit, observability, and SLAs
7.  Build strategy and acceptance criteria

GLOSSARY
# Glossary of terms
This glossary is the canonical reference for naming. The same terms are used identically across the Solva, Synisense, Akki Chat, and Akki Service Integration briefs. Any apparent variation in this or sibling documents resolves to one of the definitions below.



SECTION 1
# What Synisense is
Synisense is a platform service. It is built and operated independently of any consuming product. Akki products — Solva, the chat layer, Workspace, Highlights, the Financial Health Score, Cycle Manager, Monitor, Pulse — all consume Synisense through its API. Synisense does not know or care which product is calling it; it provides the same contract to every consumer.
Synisense has two functions, packaged as one service:
- The Behavioural Analytics Engine — continuously ingests transactional and operational data from enterprise systems, builds dynamic behavioural profiles, and produces structured signals (anomaly flags, life-stage indicators, churn risk scores, product readiness flags, compliance event triggers, behavioural vectors).
- The Shield — sits between any consumer and any LLM provider. De-identifies content before the LLM sees it, re-identifies on the way back, enforces purpose limitation, generates a complete audit trail, and ensures that even Syni engineers cannot read consumer data without authorisation.
These functions are packaged together because they share infrastructure (the data substrate, the tenancy model, the audit log) and because the safety guarantee Akki promises is the composition of both. The Engine produces signals; the Shield ensures those signals — and any downstream LLM processing — are handled with structural privacy.
## 1.1 What Synisense is not
- Not a customer-facing product. Synisense has no user interface. Its consumers are other services.
- Not an LLM. The Shield routes calls to LLM providers but Synisense is not an LLM itself. Generation happens in the LLM tier, which Synisense governs but does not implement.
- Not a reasoning engine. The Behavioural Analytics Engine produces signals; it does not produce diagnoses, recommendations, or human-readable analysis. That work belongs to consumers (Solva does it, Workspace does it, Highlights does it).
- Not a database. Synisense has internal data stores, but it is not a general-purpose data layer for Akki. Consumers do not query Synisense for arbitrary enterprise data; they request specific signals or governed LLM routes.
## 1.2 Why Synisense is built independently of Solva
Synisense and Solva are different categories of system. Synisense is a platform service — continuous, always-on, called by many consumers, optimised for throughput, reliability, and structural privacy guarantees. Solva is a reasoning module — session-based, called by users, optimised for diagnostic rigour and editorial voice.
Building them as one system would couple two different release cadences, two different scaling profiles, two different audit obligations, and two different engineering disciplines. Building them separately allows each to be optimised for what it is. Synisense becomes the platform substrate that any Akki product can build on; Solva becomes one of many products that benefit from Synisense being there.

## 1.3 The Akki promise — what Synisense delivers
Akki promises that AI is safe and honest for enterprises. Synisense delivers the safe — three structural commitments:
- De-identification before the LLM. No LLM provider ever sees identifying information about a Synisense consumer's data. Names, account numbers, identifiers, case references become stable tokens before any model call. Re-identification happens only inside the trust boundary, on the way back to the consumer.
- Structural encryption. Consumer data is encrypted such that even Syni engineers operating Synisense cannot read it without explicit authorisation. The privacy is a property of the architecture, not of policy.
- Audit and provenance. Every signal Synisense produces, every LLM call it routes, and every access to consumer data is logged with a tamper-evident audit trail. Consumers and regulators can reconstruct what happened and why.
Solva delivers the honest — refusal, grounding, single-voice discipline, transparency. Together, the two services make AI safe and honest. The integration brief specifies how they coordinate without either compromising its own discipline.

SECTION 2
# Service architecture
Synisense is a multi-tenant service with two functional surfaces (Engine and Shield) sharing common infrastructure (data substrate, tenancy, audit log, key management). This section describes the architecture at the level engineering needs to build against.
## 2.1 Tier model
Five tiers internal to Synisense:
### Ingestion tier
Receives enterprise data from configured sources — core banking systems, insurance platforms, CRM, transaction processors, HR systems, operational databases. Supports streaming (Kafka, Kinesis, change-data-capture) and batch (scheduled extracts). Ingestion is per-tenant; one tenant's data never touches another tenant's pipeline.
### Substrate tier
Stores ingested data in encrypted form. Each tenant has a dedicated encryption key managed by a key management service the operating team cannot bypass. Data at rest is encrypted; data in motion between tiers is encrypted. The substrate is not queried by consumers — it is queried only by the Engine and the Shield.
### Analytics tier (the Engine)
Runs continuously over the substrate. Produces signals as specified in Section 3. Signals are written to a tenant-scoped signal store with retention policies per signal type. Consumers retrieve signals through the API, never by querying the substrate directly.
### Governance tier (the Shield)
Sits in the call path between any consumer and any LLM provider. Detokenises consumer requests, de-identifies content, routes to the LLM, re-identifies responses, and audits the entire flow. Specified in Section 4.
### Interface tier
The Synisense API. Specified in Section 5. The only surface consumers interact with. Enforces authentication, authorisation, rate limiting, and request/response schema validation.
## 2.2 Tenancy model
Synisense is multi-tenant by design but isolated by guarantee. The tenancy unit is the enterprise customer (a bank, an insurer, a corporate). Within a tenant, sub-tenancies exist for organisational units (a board, a department, an executive's NED contexts).
- Cross-tenant data access is structurally impossible — different encryption keys, different storage partitions, different query paths
- Cross-sub-tenancy access within a tenant is permission-gated and audited — an executive's NED context for Board A cannot pull signals from their NED context for Board B without explicit cross-context permission, which is rare
- Operating engineers can access tenant infrastructure for support but not tenant data — the encryption keys are not in their reach
- Tenant administrators have access to their own audit logs; they can see what Synisense has done with their data
## 2.3 Two functions, one service — why
The Engine and the Shield could in principle be built as two services. They are built as one for three reasons:
- Shared substrate. Both functions operate on the same encrypted data store, with the same encryption keys, the same tenancy model, the same audit log. Splitting the service would duplicate or fragment all of these.
- Shared tokenisation. The de-identification tokens the Shield uses are derived from entities the Engine identifies during ingestion (this customer, this account, this case). Stable tokens require both functions to share the entity-resolution layer.
- Shared audit obligation. Regulators want one audit trail per tenant, not two. The audit log captures every signal produced, every LLM call routed, and every access to data — as a single tamper-evident chain.
The two functions are exposed to consumers as separate API surfaces (signals endpoint vs governed-LLM endpoint) so consumers can use one without using the other. Internally they are one service.
## 2.4 Synisense as a dependency
Synisense is a hard dependency for any Akki product that processes enterprise data through LLMs. Akki products do not have an option to bypass Synisense and call an LLM provider directly. The architecture enforces this — LLM provider credentials are held only by the Shield, not by consumer products.

SECTION 3
# The Behavioural Analytics Engine
The Engine continuously ingests enterprise data, builds dynamic behavioural profiles, and produces structured signals consumers can subscribe to or query.
## 3.1 What the Engine produces — signal categories
Signals fall into six categories. Each has a defined schema, a refresh cadence, and a retention policy.

## 3.2 What the Engine does not produce
- Customer-facing content. The Engine does not write copy, generate summaries, or produce human-readable outputs. Those belong to LLM-powered consumers (the Akki AI Platform, Solva, Workspace).
- Diagnoses or recommendations. The Engine produces signals about what is happening; it does not produce conclusions about what should happen. Diagnostic work happens in Solva, recommendation work happens in consumer products.
- Predictions outside the signal schema. The Engine produces forward-looking signals (churn risk, product readiness) within its defined schema; it does not generate novel predictions outside that schema on demand.
## 3.3 Signal schema
signal {
  signal_id: uuid
  tenant_id: uuid
  sub_tenant_id: uuid (nullable)
  entity_ref: encrypted_token        // de-identified entity reference
  category: enum                     // profile | anomaly | life_stage |
                                     // risk | operational | compliance
  type: string                       // specific signal type within category
  value: jsonb                       // structured payload per type
  confidence: float [0,1]
  computed_at: timestamp
  valid_until: timestamp (nullable)
  source_refs: array<source_ref>     // for audit
  version: string                    // signal-type schema version
}

## 3.4 Entity resolution
Synisense maintains an entity resolution layer that identifies real-world entities (customers, accounts, employees, business units) across ingestion sources. Entity resolution produces stable internal identifiers, which the Shield uses as the basis for tokenisation.
Entity resolution is per-tenant. Synisense never resolves entities across tenant boundaries — a person who is a customer of two different tenants is two different entities inside Synisense, with no link between them. This is structural, not policy.
## 3.5 Engine consumer pattern
Two consumption patterns:
- Subscription — consumers subscribe to signal categories (or specific signal types) for entities they have access to. Synisense pushes signals as they are produced. Used by Akki Pulse, Highlights, real-time monitoring.
- Query — consumers request signals at a point in time, by entity, category, or time window. Synisense returns matching signals from the signal store. Used by Solva for prior-context grounding, Workspace for analysis, Cycle Manager for retrospectives.
## 3.6 Engine versioning
Signal types are versioned. When a signal type's schema changes, Synisense publishes a new version while continuing to produce the old version during a deprecation window. Consumers explicitly opt into the new version. Synisense maintains a compatibility matrix that consumers can query.

SECTION 4
# The Shield
The Shield is the governance function of Synisense. It sits between any consumer and any LLM provider. No consumer of Akki has direct LLM access; every LLM call passes through the Shield.
## 4.1 The four operations the Shield performs
### De-identification (pre-LLM)
The Shield receives a request from a consumer containing potentially sensitive content — a board pack, a strategy memo, transaction data, personnel material. Before the request reaches the LLM provider, the Shield:
- Identifies named entities (people, organisations, accounts, places, case references, financial figures over thresholds)
- Replaces each with a stable token derived from the entity resolution layer — Director_47, Institution_3, Account_X, Figure_12
- Maintains a tokenisation map for the duration of the request, in memory, scoped to the request and not persisted
- Strips metadata that could re-identify (timestamps at fine granularity, system identifiers, unique formatting patterns) where possible without breaking the content's meaning
The LLM provider receives the de-identified content. It produces a response against the tokens. The Shield re-identifies the response on the way back to the consumer.
### Re-identification (post-LLM)
On the response path, the Shield uses the tokenisation map to replace tokens with their original entities. The consumer receives content that reads as if the LLM had access to the real data — but no LLM provider, no LLM logs, no LLM training data ever contained the real entities.
The tokenisation map is destroyed after the response is delivered. Subsequent requests produce the same tokens (entity resolution is stable) but the in-memory map is per-request.
### Purpose limitation and scoping
Every Shield request carries a declared purpose — what the consumer is using the LLM for. The Shield validates the purpose against the consumer's authorisation (specific Akki product, specific user, specific tenant scope). Requests outside declared purpose are rejected.
### Audit
The Shield logs every request: which consumer, which purpose, which entities were tokenised (by entity ID, not by identifying content), which LLM provider was invoked, what model version, what the response shape was. The audit log is tamper-evident.
## 4.2 Encryption
Consumer data ingested into Synisense, consumer requests routed through the Shield, and Synisense's own audit logs are encrypted with tenant-specific keys managed in a key management service the operating engineering team cannot access directly.
- Tenant administrators can rotate their keys; rotation invalidates the prior key's ability to decrypt
- Operating engineers can keep Synisense running but cannot read tenant data — debugging tenant-specific issues requires explicit, time-bounded, audited authorisation from the tenant
- The encryption model is structural: privacy is a property of the architecture, not of operational policy
## 4.3 LLM provider abstraction
The Shield abstracts LLM providers. Consumers do not know which provider their request is routed to. The Shield's routing logic selects providers based on:
- Tenant configuration (some tenants restrict to specific providers for sovereignty reasons)
- Request type (some providers are better-suited for analytical work, others for generation)
- Cost and performance constraints
- Provider availability
Provider changes are transparent to consumers. If a provider's terms change, becomes unavailable, or is replaced, consumer products do not need to change.
## 4.4 Refusal at the Shield
The Shield refuses requests that violate its contracts:
- Requests without a valid declared purpose
- Requests that exceed the consumer's authorisation scope
- Requests containing content that cannot be de-identified safely (e.g., content where de-identification would destroy meaning) — these are returned to the consumer with a structured refusal
- Requests with detected jailbreak patterns aimed at the LLM provider
Shield refusals are different from Solva refusals. Solva refuses to weight scenarios when evidence is insufficient — a reasoning discipline. The Shield refuses when a request would violate governance — an infrastructure discipline. Both are protections; they operate at different layers.
## 4.5 Synisense Shield Trust Receipts
On every Shield-routed request, Synisense produces a trust receipt — a structured artefact the consumer stores alongside its own work. The receipt contains:
- Request and response audit IDs
- Tokenisation summary (count of entities tokenised, by category)
- LLM provider and model version invoked
- Purpose declared
- Timestamp and signing chain
Trust receipts are how consumers prove to their users — and their users' regulators — that work done in Akki was governed by Synisense. The receipt is the externalisable evidence of the safe in Akki's promise.

SECTION 5
# Service API and consumer contract
Synisense exposes two API surfaces: the Engine API (for signals) and the Shield API (for governed LLM access). All consumer interaction with Synisense happens through one of these two.
## 5.1 Authentication and tenancy
Every API call carries:
- Consumer identity — which Akki product is calling (Solva, Workspace, etc.)
- User identity — which end user the call is on behalf of
- Tenant context — which tenant and sub-tenancy the call operates in
- Declared purpose — what the call is for
Synisense validates all four against the consumer's authorisation. Mismatches are refused at the interface tier.
## 5.2 Engine API — signal endpoints
### Subscribe
POST /v1/engine/subscriptions
body: {
  signal_categories: array<enum>,
  signal_types: array<string> (optional, narrows within categories),
  entity_filter: entity_query (optional)
  delivery: enum  // webhook | stream | poll
}
returns: subscription_id, delivery_config

### Query
POST /v1/engine/signals/query
body: {
  filter: { category, type, entity_ref, time_range, confidence_min },
  pagination: { cursor, limit }
}
returns: signals[], next_cursor

### Schema discovery
GET /v1/engine/signal_types
returns: array<signal_type_definition>

## 5.3 Shield API — governed LLM access
### Request
POST /v1/shield/llm/invoke
body: {
  purpose: string,             // declared use
  content: encrypted_payload,  // pre-encrypted by consumer
  model_preference: enum,      // analytical | generative | balanced
  schema: response_schema      // expected response shape
}
returns: {
  response: encrypted_payload,
  trust_receipt: trust_receipt,
  audit_id: uuid
}

## 5.4 Error responses
Synisense returns structured errors. Consumers must handle four error classes:

## 5.5 The contract Synisense commits to consumers
Synisense's commitments to any consumer:
- Signal schemas are stable within a version. Breaking changes require a new version with deprecation window of at least 6 months.
- Shield contracts are stable. The de-identification guarantee, the audit chain, and the trust receipt schema do not break compatibility without a major version bump.
- Authentication and tenancy semantics are stable. The four-field call envelope (consumer, user, tenant, purpose) is preserved across versions.
- Latency targets are met or breaches are reported. The Shield's median latency overhead is below 300ms; the Engine's query latency is below 500ms for indexed queries.
- Audit logs are queryable within SLA. Consumers can retrieve audit records for their own calls within 5 minutes of the call completing.
## 5.6 What Synisense does not commit to
- Specific LLM providers. Synisense reserves the right to change providers; consumers must not depend on specific provider behaviour.
- Signal semantics beyond schema. The values inside a signal are produced by the Engine's current models, which can be retrained. Consumers must treat signal values as the Engine's best current estimate, not as ground truth.
- Cross-tenant aggregation. Synisense does not produce signals that aggregate across tenants — this would violate the structural privacy boundary.

SECTION 6
# Audit, observability, and SLAs
## 6.1 The Synisense audit log
Synisense maintains a tamper-evident audit log per tenant. Every operation is recorded:
- Engine: every signal produced (signal ID, type, entity, confidence, source refs, computed-at)
- Shield: every LLM call routed (audit ID, purpose, consumer, user, model, latency, trust receipt ID)
- Substrate: every data access (who, when, why, what scope)
- Tenancy: every authorisation decision (granted, denied, escalated)
Audit entries are written to an append-only store with cryptographic chaining — each entry includes a hash of the previous entry. Tampering with any past entry invalidates the chain from that point forward.
## 6.2 What consumers see
Consumer products (Akki products) can query the audit log for entries related to their own calls. They cannot query other consumers' entries. Tenant administrators can query all entries within their tenant; the operating engineering team can query infrastructure-level entries but not the encrypted content.
## 6.3 Observability
Synisense exposes operational telemetry:
- Signal production rate per category, per tenant
- Shield invocation rate per consumer, per purpose
- Latency distributions for both APIs
- Error rates by class
- De-identification statistics (entities tokenised per request, by category)
- Audit log integrity verification (chain checks)
Telemetry is exposed to operations engineering and to tenant administrators with appropriate scoping.
## 6.4 SLAs

## 6.5 Failure modes and degradation
Synisense can fail in three categories. Each has a specified degradation behaviour:
- Engine degradation — if signal production is delayed or unavailable, consumers receive stale signals with a freshness indicator. Consumers must check the indicator and decide whether stale signals are acceptable for their use case.
- Shield degradation — if the LLM provider is unavailable or the Shield itself is degraded, the Shield refuses with SERVICE_UNAVAILABLE. Consumers do not get a fallback path that bypasses the Shield. No degradation reduces the governance guarantee.
- Substrate degradation — if data ingestion is delayed, both functions degrade. Consumers see this as Engine signals being stale and Shield calls succeeding with the most recent available context. The trust receipt records the data freshness state.


SECTION 7
# Build strategy and acceptance criteria
## 7.1 Build phases
### Phase 1 — Substrate, tenancy, and Shield core (weeks 1–10)
- Ingestion tier for at least two streaming and two batch sources
- Substrate with tenant-specific encryption and key management
- Entity resolution layer
- Shield de-identification and re-identification pipeline
- Shield API (invoke endpoint) with one LLM provider integration
- Audit log with cryptographic chaining
- Authentication and tenancy enforcement at the interface tier
### Phase 1 acceptance criteria
- End-to-end Shield call: consumer → de-identification → LLM → re-identification → trust receipt
- Zero LLM-side exposure of real entity content verified by penetration test
- Tenant isolation verified — one tenant's data cannot be accessed via another tenant's calls
- Audit chain integrity verified across 10,000 simulated calls
- Shield median latency overhead below 300ms
### Phase 2 — Engine and signal production (weeks 11–18)
- Analytics tier with first three signal categories (profile, anomaly, life-stage)
- Engine API (subscribe and query endpoints)
- Signal store with retention policies
- Schema versioning infrastructure
- First consumer integration (Akki Pulse or Highlights)
### Phase 2 acceptance criteria
- All three signal categories producing signals on a labelled test tenant
- Signal schema reproducibility — same input data produces same signal IDs and values
- Subscription delivery within 5s for 99% of signals
- Query latency below 500ms median for indexed queries
- Consumer integration verified end-to-end
### Phase 3 — Additional signals, multi-provider, hardening (weeks 19–24)
- Remaining signal categories (risk, operational, compliance)
- Second and third LLM provider integrations
- Provider routing logic
- Cross-region replication for tenant data with sovereignty requirements
- Tenant administrator dashboard for audit log access
### Phase 3 acceptance criteria
- All six signal categories live
- Provider routing transparent to consumers verified across 100 test calls
- Sovereignty configuration verified — tenant-configured provider restrictions enforced
- Audit log access by tenant administrators verified end-to-end
### Phase 4 — SLAs, observability, scale (weeks 25–28)
- Production SLA monitoring
- Capacity testing at 10x expected initial load
- Failure injection testing across all degradation modes
- Operational runbooks for incident response
### Phase 4 acceptance criteria
- All SLAs met under simulated production load
- Degradation behaviour verified — Shield refuses correctly when governance cannot be maintained
- Operational team can respond to a simulated tenant incident within published response targets
## 7.2 Build principles
### Structural privacy, not policy privacy
Every privacy guarantee in this spec must be enforced by architecture, not by operational policy. Engineering reviews reject any implementation that depends on operator behaviour to uphold privacy. The encryption model, the tenancy boundary, the audit chain — all must hold even if every operator behaves adversarially.
### Refusal preserves the guarantee
Synisense never degrades by relaxing governance. If a request cannot be served safely, the Shield refuses. Consumers are built around refusal as a normal mode. Engineering investment in graceful refusal handling is as significant as investment in the success path.
### The contract is the product
Consumers depend on Synisense's API contract. Changes to internal implementation are invisible if the contract holds; changes to the contract require version management, deprecation windows, and migration support. Engineering treats the contract as the public surface of Synisense; everything else is implementation detail.
## 7.3 Continuous compliance checks
Acceptance criteria phrased per phase are necessary but not sufficient. Between phase gates, builds can drift back into the failure modes the architecture is built to prevent. The following checks run on every release, not only at phase acceptance:
- Tenant isolation scan. Every release runs an automated penetration test against tenant isolation — attempts to access Tenant A data using Tenant B credentials, attempts to cross sub-tenancy boundaries, attempts to read encrypted data without authorisation. Any breach blocks the release.
- Audit chain integrity check. The cryptographic chaining of audit log entries is verified continuously, not at release boundaries. Any tampering or chain break triggers an incident.
- Shield governance compliance. Every Shield API call path is verified to apply de-identification before LLM invocation and re-identification after. Any path that returns un-de-identified content to a consumer triggers a build block.
- Trust receipt issuance. Every Shield call in staging is verified to produce a valid trust receipt. Missing or malformed receipts block the release.
- Refusal-when-cannot-govern verification. Failure injection runs on every release — Shield is presented with un-de-identifiable content, invalid purposes, and policy violations; refusal behaviour is verified.
Continuous compliance is the engineering discipline that prevents the documents from becoming aspirational rather than operational. Phase acceptance verifies the foundation; continuous compliance prevents the drift.
## 7.4 Out of scope for v1
- Consumer-facing UI — Synisense has no UI in v1; tenant administrators interact through the API or through Akki product surfaces that consume Synisense
- Self-service tenant provisioning — tenants are onboarded by the Syni team in v1; self-service is a v2 concern
- Custom signal types per tenant — the v1 signal catalogue is fixed; per-tenant custom signals are deferred
- Federated learning across tenants — Synisense does not learn from one tenant's data to improve signals for another; this is a structural commitment, not a v1 limitation
- Direct LLM provider negotiation by tenants — tenants accept Synisense's provider portfolio; per-tenant provider contracts are deferred
## 7.5 Success metrics for v1

— End of Synisense Service brief, v1 —

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
| INDEPENDENCE INVARIANT / Synisense is built so that if Solva were never built, Synisense would still be useful — other Akki products consume it identically. Conversely, if Synisense's API contract is held stable, the underlying implementation can change without Solva noticing. The boundary between the two services is the contract specified in Section 5, not a shared codebase. |

### Table 3
| ARCHITECTURAL ENFORCEMENT / No Akki product holds LLM provider credentials. The Shield is the only path to LLM invocation. A consumer that needs LLM generation requests it through the Shield API; a consumer that needs signals requests them through the Engine API. There is no fourth path. This is enforced at the infrastructure level — IAM, network policy, credential vaulting — not at the product level. |

### Table 4
| Category | Examples | Cadence |
| Behavioural profile vectors | Dynamic profile of an entity (customer, employee, account, business unit) — spending pattern, engagement pattern, risk posture | Continuous, with hourly snapshot |
| Anomaly signals | Deviations from established patterns — unusual transactions, sudden engagement changes, off-pattern access | Real-time on detection |
| Life-stage indicators | Recognised transitions — new customer phase, growth phase, dormancy, churn-risk phase | Daily evaluation |
| Risk and readiness signals | Churn risk score, credit risk indicator, product readiness flag, compliance event trigger | Recomputed on relevant data change |
| Operational signals | Aggregate operational state — capacity utilisation, throughput, error rates, queue depths | Real-time |
| Compliance signals | Events with compliance significance — large transactions, regulated activity, threshold breaches | Real-time on detection |

### Table 5
| Class | When | Consumer response |
| AUTH_DENIED | Authentication or authorisation failure | Fail the user-facing operation; do not retry |
| PURPOSE_INVALID | Declared purpose does not match authorisation | Fail the operation; surface the contract violation to engineering |
| GOVERNANCE_REFUSED | Shield refused on policy grounds (e.g., un-de-identifiable content) | Fail gracefully; surface a structured refusal to the end user |
| SERVICE_UNAVAILABLE | Synisense temporarily unavailable | Retry with backoff; degrade gracefully per consumer policy |

### Table 6
| Metric | Target |
| Shield median latency overhead | Below 300ms |
| Shield p99 latency overhead | Below 1.5s |
| Engine query latency (indexed) | Below 500ms median |
| Engine subscription delivery | Below 5s from signal production |
| API availability | Above 99.9% |
| Audit log query availability | Above 99.95% |
| Audit log integrity | 100% — verified continuously |

### Table 7
| DEGRADATION INVARIANT / Synisense never degrades by reducing its governance guarantees. If the Shield cannot run with full de-identification and audit, the Shield refuses. The promise of structural privacy holds even under partial failure. Consumers must be built to handle Shield refusal as a normal operating mode, not as an exceptional error. |

### Table 8
| Metric | Target | How measured |
| Tenant data isolation | 100% | Continuous penetration testing |
| Shield latency overhead (median) | Below 300ms | Production telemetry |
| Shield latency overhead (p99) | Below 1.5s | Production telemetry |
| Engine query latency (median) | Below 500ms | Production telemetry |
| API availability | Above 99.9% | Production telemetry |
| Audit log integrity | 100% | Continuous chain verification |
| Refusal-when-cannot-govern compliance | 100% | Failure injection testing |
| Consumer integrations active | At least 4 (Solva, Pulse, Highlights, Workspace) | Integration test coverage |
| Trust receipts issued per consumer | 1 per Shield call | Audit log analysis |