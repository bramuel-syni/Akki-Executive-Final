/**
 * Learn library — curated AI governance & oversight content for NEDs and Executives.
 * Sources are drawn from reputable governance authorities (NACD, IoD, Deloitte,
 * Harvard CorpGov, WEF, NIST). Each entry has a plain-text summary AKKI can
 * reference in Ask, plus a link to the original source.
 */

export const LEARN_ARTICLES = [
  {
    id: "ai-governance-for-neds",
    title: "AI oversight: what a non-executive director actually needs to know",
    kicker: "Governance · 7 min read",
    topic: "governance",
    audience: ["ned", "executive"],
    source_name: "Harvard Corp Gov · Deloitte · NACD · IoD (curated)",
    source_url: "https://corpgov.law.harvard.edu/2025/04/02/ai-in-focus-in-2025-boards-and-shareholders-set-their-sights-on-ai/",
    summary: "A NED does not need to become a technologist. They need enough fluency to ask the one question that reveals whether management has thought about the risk.",
    body: `A 2025 survey found that only 20% of S&P 500 companies have at least one director with declared AI expertise — up from 11% in 2022. That gap is closing fast, but the ask on the board has changed faster. Boards are no longer being asked to approve an AI strategy once a year; they are being asked to exercise ongoing oversight of a technology that management itself does not fully understand.

The posture to aim for is the one the governance literature calls "noses in, fingers out." Keep your nose in — meaning: know which AI systems are mission-critical, what data trains them, what risks they present, and who on the executive team owns them. Keep your fingers out of the build.

Concretely, a NED should be able to answer five questions for every AI system the company depends on:

  1. Where does the training data come from, and can we defend its provenance?
  2. Who is the named accountable executive, and what is their escalation path?
  3. What is the human-in-the-loop policy for decisions this system makes?
  4. When did we last audit it for bias or drift?
  5. What is our incident-response plan when (not if) it misbehaves?

The Debevoise & Plimpton guidance is unambiguous: you do not need an AI expert on your board, but you do need an AI-literate board. The difference matters — an expert is a resource the board consults; a literate board asks the right questions of management and knows whether the answer is adequate.

A practical tactic: run a 60-minute "AI tabletop" each quarter. Management walks the board through one AI system end-to-end. What does it do? What would it take to misfire? What would we see first if it did? If management cannot answer fluently, that is itself a signal.`,
    questions_to_ask: [
      "Which three AI systems, if they misbehaved, would most damage the business — and who owns each?",
      "What is our human-in-the-loop policy and when was it last tested?",
      "When did we last commission an independent bias/drift audit, and what did it find?",
    ],
  },
  {
    id: "nist-ai-rmf-and-iso-42001",
    title: "NIST AI RMF and ISO 42001: the two frameworks worth knowing by name",
    kicker: "Frameworks · 9 min read",
    topic: "frameworks",
    audience: ["ned", "executive"],
    source_name: "NIST · ISO · Deloitte · ISPartners (curated)",
    source_url: "https://www.nist.gov/itl/ai-risk-management-framework",
    summary: "NIST AI RMF is the 'what could go wrong' map. ISO 42001 is the 'here is our management system to not let it go wrong' certificate. Most serious boards will end up knowing both.",
    body: `If your executive team is building or buying AI systems, they will eventually be asked which framework they follow. There are only two you need to know.

NIST AI Risk Management Framework (AI RMF 1.0)
  - US government, voluntary, free.
  - Four functions: Govern, Map, Measure, Manage.
  - Strength: dynamic, context-specific. You apply it per system, per use case.
  - It tells you how to think about the risk.

ISO/IEC 42001:2023
  - International standard, certifiable (third-party audit).
  - Establishes an "AI Management System" (AIMS) with documented procedures, competence management, and controls.
  - Strength: audit-ready. If a regulator, customer, or insurer asks "do you have AI governance?", ISO 42001 is the verifiable answer.
  - It tells you how to run the risk program.

Most organisations should use them together. The MAP function in NIST (understand what AI systems you have and what they do) slots directly into ISO 42001's risk-assessment planning. The MEASURE function (monitor them) maps to ISO 42001's monitoring and measurement clause.

You are not auditing management's AI code. You are auditing their governance system. A board-level question that usually lands is: "If we were to seek ISO 42001 certification this year, how far are we from passing?" If management cannot estimate, that is a material gap.`,
    questions_to_ask: [
      "Against NIST AI RMF, which of our AI systems are in Map vs. Measure vs. Manage state?",
      "How close are we to ISO 42001 readiness, and what is the cost of closing the gap?",
      "Which AI vendor contracts require ISO 42001 or equivalent — and which ones should?",
    ],
  },
  {
    id: "ai-in-financial-services",
    title: "AI in financial services: provisioning models, fraud detection, and the FCA/CBK line",
    kicker: "Sector · 6 min read",
    topic: "sector-banking",
    audience: ["ned", "executive"],
    source_name: "FCA · Bank of England · Basel · CBK (curated)",
    source_url: "https://www.bankofengland.co.uk/-/media/boe/files/fintech/ai-and-machine-learning",
    summary: "In banking the AI oversight question is concrete: can you defend the model to the regulator, and can you roll back to the human-judgement process if the model is suspended?",
    body: `Financial services boards face the sharpest version of the AI oversight question because the outputs are regulated. A provisioning model that produces the wrong impairment charge isn't a curiosity; it's a capital adequacy event.

The tangible things the audit committee should be checking, quarterly:

1. MODEL INVENTORY. Every material model — credit scoring, provisioning (IFRS 9), fraud, AML transaction monitoring, capital planning — should have an owner, a version number, a validation date, and a last-drift-check date. If this inventory is not up to date on the day the audit committee sits, escalate.

2. HUMAN-IN-THE-LOOP on high-stakes decisions. Is there a credit decline that is 100% model-driven with no human review? If so, on what volume, and what is the recourse path for the customer?

3. CHALLENGER MODELS. For every production model, is there a simpler challenger (often a logistic regression) that the validation team uses as a sanity check? When did the challenger and champion last materially diverge?

4. REGULATOR READINESS. If the CBK, FCA, or relevant local regulator were to ask for the model card for your provisioning model tomorrow, could you provide it? Model cards are becoming table stakes. Consumer Duty (UK) and similar regimes elsewhere increasingly require that you can explain a decision to the customer, not just to a regulator.

5. ROLLBACK DISCIPLINE. Is there a defined process to suspend a model and revert to a human-judgement fallback within 48 hours? Has it been tested?

A pattern worth noticing across recent FCA supervisory letters: the regulator is less interested in the model itself than in your governance OVER the model. Be ready to describe your governance before your technology.`,
    questions_to_ask: [
      "Walk the committee through the provisioning model's validation package. When did we last run it against a challenger?",
      "What is the rollback plan if the model produces outputs outside our risk appetite?",
      "Which decisions are 100% model-driven with no human review, and on what volume?",
    ],
  },
  {
    id: "ai-literacy-in-60-minutes",
    title: "AI literacy in 60 minutes: the mental model a director needs",
    kicker: "Foundations · 8 min read",
    topic: "foundations",
    audience: ["ned", "executive", "reportee"],
    source_name: "Stanford HAI · Ethan Mollick · WEF (curated)",
    source_url: "https://hai.stanford.edu/",
    summary: "You do not need to know how a transformer works. You need three mental models: what AI can do reliably, what it does unreliably, and what the cost curve looks like.",
    body: `A board member does not need a technical grounding in deep learning. They need three mental models.

1. WHAT AI CAN DO RELIABLY TODAY
  - Summarise documents and extract structured fields from them.
  - Answer questions about a bounded corpus if you ground it well (retrieval-augmented generation, RAG).
  - Classify and route (tickets, emails, transactions) at scale.
  - Draft — first drafts of code, emails, reports — that a human then finishes.
  - Detect anomalies once a baseline is established.

2. WHAT AI DOES UNRELIABLY
  - Arithmetic at scale (it guesses).
  - Temporal reasoning, dates, counting.
  - Anything requiring access to data outside its training or retrieval window, if not explicitly grounded.
  - Decisions that require weighing conflicting values with no clear signal.
  - Low-sample edge cases, where a tiny group of users suffer a model failure the aggregate metric hides.

3. THE COST CURVE
  - Model inference cost is falling fast — roughly 10x per 18 months — but the cost of the surrounding governance infrastructure (guardrails, evaluation, monitoring, incident response) is rising. Management presenting "AI will save us X" should also show you the governance cost.

The simplest heuristic for a NED evaluating any AI proposal: ask whether the proposal distinguishes between the RELIABLE CORE (classification, summarisation, structured extraction) and the UNRELIABLE EDGE (open-ended generation that affects a customer). If management cannot draw that line, they probably don't have their arms around it yet.`,
    questions_to_ask: [
      "For this AI initiative, which use cases are in the reliable core and which are in the unreliable edge?",
      "What is the governance cost alongside the forecast benefit?",
      "What would a low-sample user harm look like here, and how would we catch it?",
    ],
  },
  {
    id: "eu-ai-act-and-the-compliance-clock",
    title: "The EU AI Act: the compliance clock every multinational board is now on",
    kicker: "Regulation · 7 min read",
    topic: "regulation",
    audience: ["ned", "executive"],
    source_name: "European Commission · IAPP · Debevoise (curated)",
    source_url: "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai",
    summary: "Even if your business is not in the EU, if you sell to EU customers or use EU data, the AI Act binds you. The risk tiers are the lens through which every AI system should now be classified.",
    body: `The EU AI Act entered into force in August 2024 and is being phased in through 2026–2027. It is worth knowing four things.

1. EXTRATERRITORIAL REACH. Like GDPR, it applies to AI systems placed on the EU market or whose outputs are used in the EU — regardless of where the provider sits.

2. THE RISK TIERS. Every AI system should be classified into one of four tiers:
  - PROHIBITED (social scoring by governments, manipulative deception, real-time biometric identification in public spaces with narrow exceptions).
  - HIGH-RISK (employment decisions, credit scoring, essential services, law enforcement, critical infrastructure). Full obligations: risk management system, data governance, human oversight, logging, transparency, registration.
  - LIMITED-RISK (chatbots, emotion recognition, deepfake content). Transparency obligations.
  - MINIMAL-RISK (everything else, the majority).
  Your first board task is to ensure every AI system the company runs is classified.

3. THE GPAI ADDITIONS. General-purpose AI models (the LLM tier — GPT, Claude, Gemini) now have their own obligations, inherited by any business that substantially modifies or integrates them.

4. THE FINE CEILING. Up to €35m or 7% of global turnover for prohibited-AI violations; €15m or 3% for other violations. Materially higher than GDPR. The risk is not hypothetical.

The practical board posture: ensure management has classified every system, has a remediation plan for anything tier-2 and above, and has tested the plan. This is the governance equivalent of a fire drill.`,
    questions_to_ask: [
      "Do we have a complete, dated inventory classifying every AI system against the EU AI Act tiers?",
      "For our high-risk systems, is the conformity assessment and human-oversight documentation audit-ready?",
      "Who is our named point of contact for EU AI Act regulators, and is that role resourced?",
    ],
  },
  {
    id: "building-an-ai-incident-response-plan",
    title: "AI incident response: the plan you will need before you realise it",
    kicker: "Risk · 6 min read",
    topic: "risk",
    audience: ["ned", "executive"],
    source_name: "CISA · NCSC · MITRE ATLAS (curated)",
    source_url: "https://atlas.mitre.org/",
    summary: "Your cyber incident response plan doesn't cover half of what an AI incident requires. Build the AI-specific one before you have your first incident.",
    body: `An AI incident is not a cyber incident, though it may share some machinery. A model that produces biased decisions at scale, leaks training data in its outputs, hallucinates a legally material fact, or degrades silently are all AI-specific failure modes that your existing CSIRT is probably not trained for.

A minimum viable AI incident response plan has six elements.

1. DEFINITION. What counts as an AI incident? Be specific. "The chatbot suggested self-harm to a user," "The credit model declined 100% of applications from a postcode," "The summariser fabricated a regulator quote in a public-facing document." Without a definition, nothing gets reported.

2. DETECTION. Who is watching? Customer complaints are too late. You need (a) automated drift and bias monitors on the model itself, (b) a red-team cadence (internal or contracted), (c) a clear reporting channel for employees.

3. CONTAINMENT. Can you turn the model off in 30 minutes? Does it degrade gracefully (human fallback) or catastrophically (the process stops)? Practice this, same as you practice cyber.

4. COMMUNICATION. Pre-drafted language for customers, regulators, the board, the media. Who signs what within what hours.

5. FORENSICS. Preserve the model version, the input, the output, the intermediate artefacts. Without that, root-cause analysis is guesswork.

6. LEARNING LOOP. Every incident should feed back into the training data, the monitors, and the red-team playbook. If it doesn't, you will have the same incident twice.

The board's role is not to run the plan; it is to verify that the plan exists, is current, is tested (at least annually, ideally quarterly), and that named roles know their part.`,
    questions_to_ask: [
      "When did we last run an AI incident tabletop, and what did it reveal?",
      "What is the longest time-to-containment we have measured on any material AI system?",
      "Is our PR and regulatory-notification language for an AI incident already drafted and board-approved?",
    ],
  },
  {
    id: "vendor-ai-oversight",
    title: "Vendor AI: most of your AI risk is in your supply chain",
    kicker: "Third-party · 5 min read",
    topic: "vendor",
    audience: ["ned", "executive"],
    source_name: "ICO · Shared Assessments · Deloitte (curated)",
    source_url: "https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/",
    summary: "The AI risk you build is visible. The AI risk you buy, from every SaaS vendor quietly adding an AI feature, is the one that will surprise you.",
    body: `Between 2023 and 2025, effectively every enterprise SaaS product you use added AI features — often without a renegotiation, often without a data-processing amendment. Your vendor risk register probably doesn't reflect this.

The board-level ask is concrete:

1. VENDOR AI INVENTORY. Ask management for a one-page summary: every material vendor, whether they now offer AI features, whether you have enabled them, whether those features process your confidential data, and under what contractual terms.

2. DPA UPDATES. For any vendor processing AI-relevant data (which is almost all of them now), your Data Processing Agreement should address: training on your data (default should be NO, opt-in only), sub-processor use, data retention in the AI pipeline, bias and explainability obligations.

3. RIGHT TO AUDIT. For material vendors, you should have a right to audit their AI practices — either directly or through an independent attestation (SOC 2 Type II + ISO 42001 is the modern floor).

4. EXIT. If a vendor misbehaves, can you extract your data and switch? How long does that take? This has always been a SaaS question; it is now more urgent because AI features are trained on YOUR data and that training can be sticky.

5. INCIDENT ALIGNMENT. Your AI incident response plan must include your vendors. If a vendor's AI leaks your data, your customer sees your brand, not theirs. Contractual notification obligations should match your own disclosure clock.

The governance heuristic: if you cannot list the AI features enabled across your top ten vendors today, you do not yet have AI third-party oversight. Neither does almost anyone. Start.`,
    questions_to_ask: [
      "Which of our top ten vendors have AI features enabled on our confidential data, and under what contract?",
      "What is our opt-out posture on vendor training on our data, and can we verify it?",
      "Do our vendor incident-notification clocks match our own regulatory obligations?",
    ],
  },
];

export const TOPIC_LABEL = {
  governance: "Governance",
  frameworks: "Frameworks",
  "sector-banking": "Banking",
  foundations: "Foundations",
  regulation: "Regulation",
  risk: "Risk",
  vendor: "Third-party",
};
