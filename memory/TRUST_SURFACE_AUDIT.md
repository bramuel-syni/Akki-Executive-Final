# Trust-Surface Inventory — Read-Only Audit
**Authored 2026-02 · dispatch 8 · no code changes, no proposals**

Scope: every UI surface in Akki that signals "this product is being governed,
audited, or trustworthy." Goal: enumerate the surfaces so the user and
orchestrator can triage keep / tune / drop together.

Conventions used below:
- **Active**: surfaces on the default reading path of a default user flow
- **Latent**: only appears on hover, drill-down, modal, drawer, second tab,
  or admin-only path
- **Source**: `live data` = derived from a real query / event;
  `static copy` = hardcoded marketing/voice copy

---

## A · Solva v2 deck (16-slide reasoning surface)

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| A1 | **CoverSlide** — slide 01 header strip ("section tag" = `cover`) | Method tag — declares the deck is a reasoning artefact, not chat output | `components/solva/artefact_v2/slides/CoverSlide.jsx` rendered by `SlideShell.jsx` header | Active | static copy + live `kind` enum |
| A2 | **CoverSlide** — slide-number badge `01 / 16` | Deck integrity — fixed 16-slide commitment, not selectable | `SlideShell.jsx` header right-align | Active | live (computed from `total`) |
| A3 | **SlideShell footer strip** — `Solva Session Output · Confidential · <contextName>` on **every** slide | Confidentiality + provenance | `SlideShell.jsx` lines 94–104 | Active | live (`contextName` injected) |
| A4 | **SlideShell footer** — slide-number repeat `01 / 16` | Pagination integrity — repeats top-right marker | Same footer | Active | live |
| A5 | **MethodologicalHonestySlide** (slide variable position) — full slide dedicated to declaring method, assumptions made, evidence gaps | Methodological transparency — the "we may be wrong because…" slide | `slides/MethodologicalHonestySlide.jsx` | Active (on completed Solva decks) | live (LLM-derived; persisted in `solva_v2_sessions.synthesis.methodological_honesty`) |
| A6 | **BiasInventorySlide** | Self-declared bias surface — "patterns Solva caught in its own reasoning" | `slides/BiasInventorySlide.jsx` | Active | live |
| A7 | **PreMortemSlide** | Adversarial nudge — "what would have to be true for this conclusion to be wrong" | `slides/PreMortemSlide.jsx` | Active | live |
| A8 | **CostAsymmetrySlide** | Decision-cost framing — symmetric loss analysis as a counter to anchoring | `slides/CostAsymmetrySlide.jsx` | Active | live |
| A9 | **DecisionLogicSlide** | Reasoning transparency — explicit logic chain | `slides/DecisionLogicSlide.jsx` | Active | live |
| A10 | **PerScenarioConfidenceTable** | Calibration — confidence per scenario, not a single point estimate | `slides/PerScenarioConfidenceTable.jsx` | Active | live |
| A11 | **SensitivitySlide** | Robustness check — what would change the conclusion | `slides/SensitivitySlide.jsx` | Active | live |
| A12 | **RiskMitigationSlide** | Risk surfacing | `slides/RiskMitigationSlide.jsx` | Active | live |
| A13 | **TensionsOverviewSlide** + **PerTensionSlide** | Contradiction-surfacing — explicitly names tensions in the evidence | `slides/TensionsOverviewSlide.jsx`, `slides/PerTensionSlide.jsx` | Active | live |
| A14 | **InClosingSlide** — "reframing paragraph" + "key findings recap" | Reframing discipline — recasts the opening framing against the evidence | `slides/InClosingSlide.jsx` | Active | live |
| A15 | **ReflectionSlide** | Methodological reflection — "what we'd ask differently next time" | `slides/ReflectionSlide.jsx` | Active | live |
| A16 | **SolvaRefusalArtefact** — alternate surface when the engine refuses | Honest refusal — "Honest refusal" header + what's missing + candidate next actions | `components/solva/artefact/SolvaRefusalArtefact.jsx` (v1 surface, still loaded for refusal sessions) | Active (only on refusal sessions) | live |
| A17 | **`data-solva-v2-slide-ready-at`** attribute on every slide root | Streaming-time provenance — auditable timestamp per slide became authoritative | `SlideShell.jsx:71` | Latent (DOM-only, not visible) | live |

## B · Solva v2 deck adjuncts (panels, exports)

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| B1 | **ChairNotesStrip** — narrative companion notes per slide | Speaker-grade narrative attached to each slide; surfaced via topbar Notes toggle | `components/solva/artefact_v2/ChairNotesStrip.jsx`; toggled by `SolvaPptxToolbar.jsx` (Z2.8 facade pattern) | Latent (toggle OFF by default) | live (`GET /solva/sessions/{sid}/v2/chair_notes`) |
| B2 | **PPTX export with chair notes** | Speaker notes baked into the downloaded deck file | Backend `solva_artefact_export.py`; Z2.0 wave | Latent (only when downloaded) | live |
| B3 | **SessionLogPanel** — full SSE event timeline | Reasoning-stream auditability — every layer.start / slide.ready / session.complete with hh:mm:ss.SSS timestamps | `components/solva/artefact_v2/SessionLogPanel.jsx`; opened via topbar History icon | Latent (drawer closed by default) | live (in-memory stream meta) |
| B4 | **FrameAuditScreen** — pre-deck gate ("did we ask the right question?") | Question-quality gate — surfaces frame-audit summary + Proceed / Get more / Pause buttons before the deck is composed | `components/solva/flow/FrameAuditScreen.jsx` | Active (on first session run before deck commits) | live (SSE `frame_audit` payload) |

## C · Chat surfaces

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| C1 | **PerMessageSynisenseBadge** — "N IDENTIFIERS PROTECTED · RESTORED ON YOUR VIEW" | Redact-then-restore round-trip — names both halves of the Synisense contract | `components/chat/PerMessageSynisenseBadge.jsx` (ZZ.1) | Active (renders on every assistant message that had identifiers) | live (`useMessagesSynisense` hook → `synisense_runs` collection) |
| C2 | **Synisense badge hover tooltip** — three-layer breakdown (regex / Presidio / LLM-fallback counts) | Detection-layer transparency | Same component, hover state | Latent (hover-only) | live |
| C3 | **GovernanceSignals — bias chips** `[anchoring · Q4 number]` style | Reasoning-pattern self-flagging — Tier-2 bias detector hits | `components/chat/GovernanceSignals.jsx` (ZZ.2) | Active (renders when Tier-1 validator flags bias) | live (`zz2_governance.bias_flags`) |
| C4 | **GovernanceSignals — unsourced warning** italic line "Akki flagged N numeric claim(s) it could not source against your attached documents." | Numeric-grounding check | Same component (ZZ.2) | Active (when `numeric_claims_unsourced > 0`) | live |
| C5 | **GovernanceSignals — Solva escalation CTA** "Run this through Solva for the full 16-slide diagnostic →" | Escalation surface — recommends Solva when chat is the wrong substrate | Same component (ZZ.2); button POSTs click receipt then navigates | Active (when `escalate_to_solva && recommendation_request`) | live |
| C6 | **Chat citation chips** `[1] Document name · p.X¶Y` beneath assistant replies | Source attribution — every cited fragment resolves to a real paragraph | `pages/Chat.jsx` lines 1734–1757 (`data-testid="chat-citations"`) | Active (when reply has citations) | live (`m.citations[]`) |
| C7 | **Citation chip hover tooltip** — snippet text + doc name + page/paragraph | Quotation transparency | Same lines, `title` attr | Latent (hover-only) | live |
| C8 | **Cancelled-message marker** "Cancelled. Partial reply kept." italic line | Partial-state honesty — explicit when a stream was interrupted | `pages/Chat.jsx` lines 1721–1725 | Active (when message was cancelled) | live |
| C9 | **AuditPanel** — per-message collapsible expander rendering natural-language Synisense audit prose | Per-turn audit narrative ("what governed this answer") | `components/chat/AuditPanel.jsx` (`audit-panel-{msgId}`) | Latent (collapsed by default) | live (`GET /chats/{cid}/audit-panel?message_id={mid}`) |
| C10 | **Chat audit export ZIP** — "Export audit" topbar button | Cryptographic chain export — SHA-256 hash chain + signed payload bundle | `pages/Chat.jsx:2216` (`data-testid="chat-audit-export-btn"`); backend `/chats/{cid}/audit/export.zip` | Latent (button always shown; only triggered on demand) | live |

## D · Document drawer

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| D1 | **Document Drawer · Sources section** — "Sources" header + list of source documents (or "Sources: not applicable for this artefact type." for non-artefact docs) | Provenance — every drafted artefact declares its source documents | `components/documents/DocumentDrawer.jsx` lines 274–291 (Z2.7) | Active (Intelligence tab) | live (`source_doc_ids`) |
| D2 | **Document Drawer · Intelligence tab** — completeness gaps, objective-adherence score, clarity signals | Draft-quality scrutiny — gaps + score + readability | Same component, `drawer-intelligence-tab` | Latent (second tab) | live |
| D3 | **Document tombstone** — soft-delete UI state | Auditable deletion (not destructive) | Document Journal listings (Z2.5) | Active (when doc is archived) | live |

## E · Trust Center (`/app/trust-center`)

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| E1 | **Trust Center · "This session" tab** | Per-session audit narrative | `pages/TrustCenter.jsx::SessionView` | Active (when chatId present) | live |
| E2 | **Trust Center · "All activity" tab** | Cross-session activity log | `pages/TrustCenter.jsx::ActivityView` | Active | live (`GET /trust-center/activity`) |
| E3 | **Trust Center · "Reasoning" tab — 6 tile row** (Identifiers protected · Restored on your view · Evidence-grounding checks · Unsourced claims refused · Bias flags surfaced · Solva escalations offered/accepted) | Cumulative governance counts | `pages/TrustCenter.jsx::ReasoningView` (ZZ.3); `data-testid="tc-reasoning-tiles"` | Active (after tab click) | live (`GET /trust-center/reasoning?window=7d|30d`) |
| E4 | **Trust Center · Reasoning · 7d/30d window toggle** | Time-window selectability | Same component (ZZ.3) | Active | n/a (control) |
| E5 | **Trust Center · Reasoning · bias-by-kind breakdown** | Bias-pattern decomposition | Same component (ZZ.3) | Active (when bias counts > 0) | live |
| E6 | **Trust Center · Reasoning · aggregated feed** `(day · event_kind · count)` rows | Day-level event volume | Same component (ZZ.3); `data-testid="tc-reasoning-feed-row"` | Active | live |
| E7 | **Trust Center · Reasoning · ReasoningVelocityTile** "Solva delivers a fully-cited 16-slide diagnosis in <avg>s on average. p95 <p95>s." + optional slowest-layer hint + empty-state copy | Latency aggregate — literal speed of Solva production | Same component (ZZ.4); `data-testid="tc-velocity-tile"` | Active | live (`GET /observability/reasoning_velocity?window=7d|30d`) |
| E8 | **TrustCenterTour** modal | One-shot onboarding for the Trust Center surfaces | `components/trust/TrustCenterTour.jsx` | Latent (dismissed after first view) | live (cookie / flag) |

## F · TrustPanel drawer (right-side, from user menu)

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| F1 | **TrustPanel · Audit log** — filterable rows + ZIP export | Cross-system audit | `components/governance/TrustPanel.jsx` (Phase 7) | Latent (drawer closed by default) | live |
| F2 | **TrustPanel · De-identification status** | Live Synisense status indicator | Same component | Latent | live |
| F3 | **TrustPanel · Inbound email** | Email-ingest provenance | Same component | Latent | live |
| F4 | **TrustPanel · Connected models** | Model transparency | Same component | Latent | live |
| F5 | **TrustPanel · Sensitivity at a glance** | Bucket-level sensitivity counts (public / internal / confidential / restricted) | Same component | Latent | live |

## G · Website / marketing trust surfaces

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| G1 | **Website TIER_2 dek** — "Every prompt and every document is anonymised by Synisense before any model sees it…" | Synisense narrative | `website/copy/index.js` HERO + TIER_2 + WHY block | Active (homepage above fold) | static copy |
| G2 | **Website TRUST page** (`/trust`) — long-form Synisense / Audit Chain / Sensitivity sections | Full trust narrative | `website/pages/Trust.jsx` + `website/copy/index.js:350-…` (v7 §9) | Active (separate page) | static copy |
| G3 | **Website Methodology page** — "prove the chain from genesis to current row" claim | Audit-chain explanation | `website/pages/Methodology.jsx:85` | Active | static copy |
| G4 | **Website Methodology page · Solva H2** "We invented Solva because chat is not how executives reason." | Product-rationale framing | `website/pages/Methodology.jsx:62` | Active | static copy |
| G5 | **Website What-Akki-Does dek** — "Each surface is a faithful answer to a moment that recurs in executive work. Each is built on Synisense anonymisation and the SHA-256 audit chain." | Cross-surface trust framing | `website/copy/index.js:181` | Active | static copy |
| G6 | **citation-pill** primitive on the website — small chip showing source attribution | Evidence-citation visual on marketing pages | `website/components/PagePrimitives.jsx:61` | Active (where used in copy data) | static copy |
| G7 | **Legal — Privacy** "Synisense rehydrates the response so you see your data fully restored." | Legal-grade Synisense claim | `website/copy/legal.js:19` | Active | static copy |

## H · Cross-app shell surfaces

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| H1 | **Topbar Synisense status pill** ("On / Off / Bypass") if present | Live status indicator on every signed-in surface | `components/layout/AppShell.jsx` | Latent (peripheral) | live |
| H2 | **TrustPanel trigger** in user menu | Global access point to F1–F5 | `AppShell.jsx:38` + topbar | Latent (menu item) | live |
| H3 | **Trust Center link** (sidebar / nav) | Global access point to E1–E8 | App nav | Latent (nav item) | n/a |

## I · Auxiliary surfaces (lower-traffic)

| # | Surface | Trust signal | Where | A/L | Source |
|---|---|---|---|---|---|
| I1 | **Voice-violation tag** (two-pass enforcement) | When an assistant reply violated the voice contract and was retried | Persisted in `chat_audit_log.payload.voice_violation`; surfaced via AuditPanel narrative (C9), not as its own UI chip | Latent (audit-only) | live |
| I2 | **Refusal-reason audit row** (chat.refused / unsourced_claim) | Why a turn was refused | Audit log → AuditPanel + Trust Center → Reasoning E3 ("Unsourced claims refused" tile) | Latent (deep audit) | live |
| I3 | **`solva_v2_session_complete` audit row** | Substrate for ZZ.4 velocity + E7 tile | `db.audit_log`, not directly user-visible | Latent (DOM-invisible) | live |
| I4 | **`data-bias-kind` DOM attribute** on bias chips | Programmatic introspection of bias kinds | `GovernanceSignals.jsx:33` | Latent (DOM-only) | live |
| I5 | **`data-identifiers-restored` DOM attribute** on Synisense badge | Programmatic introspection of restoration count | `PerMessageSynisenseBadge.jsx` (ZZ.1) | Latent (DOM-only) | live |

---

## REDUNDANCY MATRIX

> Surfaces grouped by **what they're saying**, regardless of where they say
> it. A row with three or more entries is a candidate for triage —
> repetition crosses from "reinforcement" into "defensive clutter" past
> roughly three independent surfaces.

| Trust pillar | Surfaces saying it | Count | Notes |
|---|---|---|---|
| **Synisense protects identifiers (Pillar 1: Redact-then-restore)** | C1 (chat badge), C2 (chat badge tooltip), E3-tile-1 (Trust Center "Identifiers protected"), E3-tile-2 (Trust Center "Restored on your view"), F2 (TrustPanel de-id status), G1 (homepage TIER_2 dek), G2 (Trust page), G7 (Legal privacy), H1 (topbar status pill) | **9** | Heaviest cluster. Five live-data surfaces (C1, C2, E3.1, E3.2, F2, H1) say substantially the same thing. **Triage candidate.** |
| **Every signal cites its source (Pillar 2: Citations / grounding)** | A12 (RiskMitigation slide cites), A14 (InClosing recap), B2 (PPTX chair notes), C4 (unsourced warning), C6 (chat citation chips), C7 (citation hover), D1 (drawer Sources section), E3-tile-3 (Evidence-grounding checks tile), E3-tile-4 (Unsourced claims refused tile), G6 (marketing citation-pill) | **10** | Second heaviest. The deck-internal surfaces (A12, A14) are inside Solva itself and arguably internal narrative; the user-facing redundancy is C4 + C6 + D1 + E3.3 + E3.4 = **5**. **Triage candidate.** |
| **Audit chain / cryptographic integrity (Pillar 3)** | A3 (slide footer "Confidential"), A17 (DOM ready-at timestamps), B3 (SessionLogPanel), C9 (chat AuditPanel), C10 (chat audit ZIP export), E2 ("All activity"), F1 (TrustPanel audit log + ZIP), G3 (Methodology "prove the chain"), I3 (DOM-invisible audit_log substrate) | **9** | Most are latent. User-facing concentration: A3 (every slide) + B3 (drawer) + C9 (per-msg) + F1 (global drawer) = **4 actives**. **Triage candidate.** |
| **Reasoning is shown, not hidden (Pillar 4: Solva method visibility)** | A1 (method tag on cover), A5 (MethodologicalHonestySlide), A6 (BiasInventorySlide), A7 (PreMortemSlide), A8 (CostAsymmetrySlide), A9 (DecisionLogicSlide), A10 (PerScenarioConfidenceTable), A11 (SensitivitySlide), A13 (TensionsOverview + PerTension), A14 (InClosing reframing), A15 (ReflectionSlide), B1 (ChairNotesStrip), C3 (chat bias chips), C5 (Solva escalation CTA), E3-tile-5 (Bias flags tile), E5 (bias-by-kind breakdown), E3-tile-6 (Solva escalations tile), G4 (Methodology page Solva H2), G5 (What-Akki-Does dek) | **18** | Largest cluster by far. Mostly intra-Solva (10 of 18 are slides within one session); cross-surface redundancy outside Solva = C3 + C5 + E3.5 + E5 + E3.6 = **5 chat/Trust Center surfaces saying "we surface bias / can escalate."** |
| **Self-flagging confidence / hedging** | A5 (MethodologicalHonesty), A7 (PreMortem), A8 (CostAsymmetry), A10 (PerScenarioConfidence), A11 (Sensitivity), A14 (InClosing reframing), A15 (Reflection), C4 (unsourced warning), C8 (cancelled marker) | **9** | Intra-deck pile (A5/A7/A8/A10/A11/A14/A15 = 7 separate slides). Anyone reading a full deck encounters 7 "we may be wrong / here's our uncertainty" moments. **Triage candidate inside the deck specifically.** |
| **Latency / speed proof** | E7 (ReasoningVelocityTile in Trust Center) | **1** | Unique surface (ZZ.4) — no redundancy. Safe. |
| **Refusal honesty (we say no when we can't help)** | A16 (SolvaRefusalArtefact), C8 (chat cancelled marker), E3-tile-4 (Unsourced refused tile), I2 (refusal reason audit row) | **4** | Distributed but distinct kinds of refusal (Solva session, chat cancel, unsourced refusal, deep audit). Reasonable. |
| **Sensitivity / data-classification posture** | F5 (TrustPanel sensitivity), legal copy (G7) | **2** | Thin coverage; possibly under-surfaced relative to other pillars. |
| **Provenance — "this came from your documents"** | C6 (citation chips), D1 (drawer Sources section), C4 (unsourced warning is the negative form) | **3** | Tight cluster; reasonable. |
| **Process / methodology meta** | A5, A15, B1 (ChairNotesStrip narrative), G4 (Methodology page) | **4** | Three of these are Solva-deck-internal; G4 is marketing. No real redundancy on the working surfaces. |

### Surface-level overload alarm

> Highlighted because repetition past roughly three independent surfaces
> crosses from "reinforcement" into "defensive clutter":

1. **Synisense / identifier protection** — repeated on 9 surfaces (5 live, 4 static). The same fact is on every chat assistant message (C1), in the global TrustPanel (F2), in two separate Trust Center tiles (E3.1 + E3.2), in the topbar status pill (H1) if present, and in three marketing locations (G1 + G2 + G7).
2. **Citation / source attribution** — 10 surfaces, 5 user-active. C4 + C6 + D1 + E3.3 + E3.4 all say "we cite / we don't fake citations."
3. **"Reasoning is shown"** — 18 surfaces, **10 of them are inside one Solva session deck.** A user reading a single 16-slide deck encounters 7 different "we hedge / we surface uncertainty" moments.

### Surfaces with NO redundancy (safe / unique)

- E7 (ReasoningVelocityTile, latency)
- E4 (window toggle, control)
- B4 (FrameAuditScreen pre-deck gate — the only surface that gates *before* the deck commits)
- I4, I5 (DOM-only programmatic attributes)

### Gap (under-surfaced pillars)

- **Sensitivity / data-classification posture** is only visible in F5 (TrustPanel, latent) and legal copy (G7). For an executive product, "we know which documents are public / internal / confidential / restricted" is a stronger signal than its current placement implies.
- **Cryptographic integrity** has 9 surfaces but **most are latent**. Only A3 (slide footer "Confidential") is unambiguously active and user-visible.

---

## End of audit

No changes proposed. Triage decisions are the user's call.
