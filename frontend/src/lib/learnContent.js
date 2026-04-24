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
    content_type: "tl_article",
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
    content_type: "tl_article",
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
    content_type: "case_study",
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
    content_type: "tl_article",
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
    content_type: "tl_article",
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
    content_type: "case_study",
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
    content_type: "case_study",
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
  leadership: "Leadership",
  strategy: "Strategy",
  news: "News",
};

export const CONTENT_TYPE_LABEL = {
  news: "News",
  tl_article: "TL Articles",
  video: "Videos",
  case_study: "Case Studies",
};

/**
 * "View more" reading list — per active tab. Opens in a modal below the grid
 * as supplementary reference reading vetted by AKKI editors. Grouped by topic
 * so a NED researching, say, 'regulation' gets the 4 primary-source URLs we'd
 * hand them if asked in person.
 *
 * Shape: { [tab_key]: { [topic_slug]: [{title, source, url, note}] } }
 * Topic 'general' = always shown regardless of topic filter.
 */
export const LEARN_MORE = {
  tl_article: {
    general: [
      { title: "Principles for the Responsible Use of AI in Financial Services",
        source: "Bank of England · Prudential Regulation Authority",
        url: "https://www.bankofengland.co.uk/prudential-regulation/publication/2024/november/artificial-intelligence-and-machine-learning",
        note: "PRA's evolving supervisory expectations — the clearest public signal of what UK regulators will look for." },
      { title: "The AI Risk Repository",
        source: "MIT Center for Collective Intelligence",
        url: "https://airisk.mit.edu/",
        note: "1,600+ categorised AI risks — useful as a risk-register starter pack, reviewed by MIT." },
      { title: "AI Governance Scorecard",
        source: "Stanford HAI",
        url: "https://hai.stanford.edu/policy",
        note: "Self-assessment tool published quarterly; lets boards benchmark their AI governance maturity." },
    ],
    governance: [
      { title: "Director's Handbook — AI Oversight",
        source: "NACD",
        url: "https://www.nacdonline.org/all-governance-resources/ai/",
        note: "The US director-community reference work. Updated annually. Members-only full text." },
      { title: "AI and Corporate Governance",
        source: "Institute of Directors (UK)",
        url: "https://www.iod.com/resources/factsheets/technology/artificial-intelligence-ai-and-corporate-governance/",
        note: "UK counterpart to NACD. Pragmatic, short, usable inside a board meeting." },
    ],
    frameworks: [
      { title: "AI RMF Playbook",
        source: "NIST",
        url: "https://airc.nist.gov/AI_RMF_Knowledge_Base/Playbook",
        note: "Stage-by-stage actionable playbook mapped to the NIST AI RMF functions." },
      { title: "ISO/IEC 42001 explainer",
        source: "BSI",
        url: "https://www.bsigroup.com/en-GB/iso-42001-ai-management-system/",
        note: "Readable certification-body summary — cheaper than buying the standard upfront." },
    ],
    "sector-banking": [
      { title: "Artificial Intelligence in banking supervision",
        source: "Central Bank of Kenya",
        url: "https://www.centralbank.go.ke/",
        note: "CBK's emerging stance on AI model risk management — directors of Kenyan banks should watch this." },
      { title: "AI in financial services — discussion paper",
        source: "Financial Conduct Authority (UK)",
        url: "https://www.fca.org.uk/publications/discussion-papers/dp5-24-artificial-intelligence-machine-learning",
        note: "Reference document quoted in current supervisory letters." },
    ],
    regulation: [
      { title: "EU AI Act — consolidated text",
        source: "European Parliament",
        url: "https://artificialintelligenceact.eu/",
        note: "Searchable annotated version. More usable than the Official Journal PDF." },
      { title: "AI governance in Africa — state-of-play",
        source: "Access Partnership",
        url: "https://accesspartnership.com/africa-ai-policy-tracker/",
        note: "Country-by-country tracker. Important for multi-jurisdictional boards." },
    ],
    vendor: [
      { title: "Shared Assessments — AI in Third Party Risk",
        source: "Shared Assessments",
        url: "https://sharedassessments.org/ai/",
        note: "Vendor-AI specific TPRM tooling, including an AI addendum for SIG questionnaires." },
    ],
  },
  news: {
    general: [
      { title: "FT Artificial Intelligence coverage",
        source: "Financial Times",
        url: "https://www.ft.com/artificial-intelligence",
        note: "Paywalled but the serious business of record for executive AI news." },
      { title: "Reuters AI",
        source: "Reuters",
        url: "https://www.reuters.com/technology/artificial-intelligence/",
        note: "Breaking, fact-first — pairs well with FT for perspective." },
      { title: "Stanford AI Index — annual report",
        source: "Stanford HAI",
        url: "https://aiindex.stanford.edu/report/",
        note: "The closest thing AI has to an annual almanac. Cite with confidence in board papers." },
      { title: "The Economist — technology",
        source: "The Economist",
        url: "https://www.economist.com/technology",
        note: "Weekly, sober, context-rich. Good antidote to daily tech-press breathlessness." },
      { title: "MIT Technology Review — AI",
        source: "MIT Technology Review",
        url: "https://www.technologyreview.com/topic/artificial-intelligence/",
        note: "Deeper than daily news, faster than academic — good for a NED who reads once a week." },
    ],
    regulation: [
      { title: "EU AI Act — implementing acts tracker",
        source: "Future of Life Institute",
        url: "https://artificialintelligenceact.eu/implementation/",
        note: "Tracks secondary legislation in real time — more useful than the Official Journal for practitioners." },
      { title: "White House AI Executive Orders — live tracker",
        source: "Center for AI Safety",
        url: "https://www.safe.ai/",
        note: "Independent tracker of US federal AI policy actions." },
      { title: "OECD AI Policy Observatory",
        source: "OECD",
        url: "https://oecd.ai/en/",
        note: "Country-by-country AI policy dashboard updated quarterly. Use for multi-jurisdictional board agendas." },
    ],
    "sector-banking": [
      { title: "Basel Committee — AI supervisory implications",
        source: "BIS",
        url: "https://www.bis.org/bcbs/publications.htm",
        note: "BCBS consultative documents on AI model risk — source material for all central-bank supervisory letters." },
      { title: "AFI — AI in financial regulation (Africa)",
        source: "Alliance for Financial Inclusion",
        url: "https://www.afi-global.org/",
        note: "Pan-African regulatory network. Useful for boards across CBK, SARB, BCEAO, CBN jurisdictions." },
    ],
  },
  video: {
    general: [
      { title: "Stanford HAI — AI+X Executive Courses",
        source: "Stanford Online",
        url: "https://online.stanford.edu/programs/artificial-intelligence",
        note: "Executive-grade short courses from HAI faculty. Paid, but a recognised credential." },
      { title: "MIT Sloan — AI for Senior Executives",
        source: "MIT Sloan",
        url: "https://executive.mit.edu/course/artificial-intelligence/",
        note: "The US counterpart. Strong alumni track record in financial services." },
      { title: "Oxford Saïd — AI Programme for Directors",
        source: "Oxford Saïd Business School",
        url: "https://www.sbs.ox.ac.uk/programmes",
        note: "UK/EU-angled director programme; shorter format than Stanford/MIT." },
      { title: "INSEAD — AI Strategy for Business",
        source: "INSEAD",
        url: "https://www.insead.edu/executive-education",
        note: "Continental-Europe view. Strong on management science rather than the engineering stack." },
      { title: "TED — Artificial Intelligence playlist",
        source: "TED",
        url: "https://www.ted.com/playlists/310/talks_on_artificial_intelligen",
        note: "Free, short, broad. Good warmup for a board offsite." },
    ],
    leadership: [
      { title: "Andrew Ng — AI Transformation Playbook",
        source: "Landing.AI",
        url: "https://landing.ai/case-studies/",
        note: "Case-by-case implementation write-ups. Not academic; practical." },
      { title: "a16z — AI podcast",
        source: "Andreessen Horowitz",
        url: "https://a16z.com/podcast/",
        note: "Venture-side perspective on where AI capital and business models are going. Useful counterweight to regulator-heavy reading." },
      { title: "Hard Fork (NYT / Platformer)",
        source: "The New York Times",
        url: "https://www.nytimes.com/column/hard-fork",
        note: "Weekly podcast that keeps you current without a doctorate. Casey Newton and Kevin Roose." },
    ],
  },
  case_study: {
    general: [
      { title: "Harvard CorpGov — AI in the Boardroom series",
        source: "Harvard Law",
        url: "https://corpgov.law.harvard.edu/category/artificial-intelligence/",
        note: "Free, rigorous, frequently updated. The anchor reading list for any director serious about AI oversight." },
      { title: "Deloitte — State of Generative AI in the Enterprise",
        source: "Deloitte",
        url: "https://www.deloitte.com/global/en/issues/trends/state-of-generative-ai-in-the-enterprise.html",
        note: "Quarterly survey — useful for benchmarking 'are we behind our peers?'." },
      { title: "McKinsey — State of AI",
        source: "McKinsey & Company",
        url: "https://www.mckinsey.com/capabilities/quantumblack/our-insights",
        note: "Consulting-angle counterpart to Deloitte. Board-ready charts, source-referenced." },
      { title: "BCG — AI Radar",
        source: "BCG",
        url: "https://www.bcg.com/capabilities/artificial-intelligence",
        note: "Executive-survey based. Strong on the 'value capture vs. value created' gap." },
      { title: "EY — AI Pulse",
        source: "Ernst & Young",
        url: "https://www.ey.com/en_gl/insights/ai",
        note: "Audit-firm perspective. Pairs usefully with Deloitte for a two-source triangulation." },
    ],
    vendor: [
      { title: "ICO — AI and data protection",
        source: "Information Commissioner's Office (UK)",
        url: "https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/",
        note: "Regulator guidance on vendor AI data flows. Apply as a floor, not a ceiling." },
      { title: "NIST — AI TEVV resources",
        source: "NIST",
        url: "https://www.nist.gov/aisi",
        note: "Test, Evaluation, Verification, Validation — the gold-standard methodology US regulators will reference." },
      { title: "OWASP Top 10 for LLM Applications",
        source: "OWASP",
        url: "https://owasp.org/www-project-top-10-for-large-language-model-applications/",
        note: "Security-engineering perspective on LLM-specific risks in the product pipeline." },
    ],
  },
};


/**
 * News briefs — short board-relevant AI governance news items.
 * Curated from reputable outlets (FT, Reuters, Bloomberg, Deloitte, NACD, FCA, ICO).
 * Each brief is a 3–5 sentence summary with a primary-source link.
 */
export const LEARN_NEWS = [
  {
    id: "news-eu-ai-act-gpai-code",
    title: "EU publishes the GPAI Code of Practice — material for any board using GPT/Claude/Gemini",
    kicker: "News · EU · 3 min read",
    content_type: "news",
    topic: "regulation",
    audience: ["ned", "executive"],
    source_name: "European Commission · IAPP",
    source_url: "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai",
    summary: "The voluntary Code of Practice for General-Purpose AI (GPAI) providers went live in 2025 and becomes the reference point for AI Act enforcement in 2026. If your business substantially integrates a frontier model, the code now sets the documentation, transparency, and copyright-compliance bar your regulator will assume you meet.",
    body: `The European Commission finalised the General-Purpose AI Code of Practice in 2025. Signing it is voluntary, but non-signatories will have to demonstrate equivalent compliance when the AI Act's GPAI obligations apply.

What this means for a board:
  - Any business substantially modifying or deploying a GPAI (LLM) inherits provider-side obligations downstream. Your AI vendor contracts should now reference the Code.
  - Documentation expectations (model cards, evaluation summaries, systemic risk assessments) are public and specific.
  - Expect your insurers and auditors to start asking whether your providers are signatories.

A practical board ask: "Is our LLM vendor a signatory of the EU GPAI Code of Practice, and if not, what equivalent attestation do we hold?"`,
    questions_to_ask: [
      "Are our frontier model vendors (OpenAI, Anthropic, Google) signatories of the GPAI Code of Practice?",
      "What documentation have we received from them to satisfy AI Act downstream obligations?",
      "Has our legal counsel reviewed the code against our existing DPA / AI addenda?",
    ],
  },
  {
    id: "news-fca-ai-discussion-paper",
    title: "FCA sharpens its AI supervisory posture — model governance under the microscope",
    kicker: "News · UK · 2 min read",
    content_type: "news",
    topic: "sector-banking",
    audience: ["ned", "executive"],
    source_name: "FCA · Bank of England",
    source_url: "https://www.fca.org.uk/firms/artificial-intelligence-ai",
    summary: "Recent FCA supervisory letters have shifted emphasis from 'do you use AI?' to 'how do you govern the AI you use?' The ask is for a live inventory, challenger models on high-stakes decisions, and a 48-hour rollback plan.",
    body: `Pattern across recent FCA supervisory correspondence and Dear CEO letters in 2025:

  - Less interest in individual model mechanics, more interest in the management system around them.
  - Explicit expectation of a live, dated model inventory including owner, validation date, and last drift check.
  - Questions about challenger models (often logistic regression baselines) for any material production model.
  - Explicit ask: can you suspend the model and revert to human judgement within 48 hours? Have you rehearsed this?

Audit committees in UK regulated firms should expect a version of this conversation at their next PRA / FCA engagement.`,
    questions_to_ask: [
      "When was our model inventory last refreshed and reviewed by the audit committee?",
      "For our three most material production models, when did the challenger and champion last diverge?",
      "Have we rehearsed a 48-hour model suspension and human-fallback this year?",
    ],
  },
  {
    id: "news-nacd-ai-oversight-bench",
    title: "NACD 2026 benchmark: AI oversight is now a named standing-committee charge at 41% of S&P 500 boards",
    kicker: "News · US · 2 min read",
    content_type: "news",
    topic: "governance",
    audience: ["ned", "executive"],
    source_name: "NACD · Harvard Corp Gov",
    source_url: "https://corpgov.law.harvard.edu/",
    summary: "The 2026 NACD governance benchmark shows AI oversight has moved from a full-board topic to a named charter line — usually on the audit committee, increasingly on a new technology committee. Committee charters are catching up in real time.",
    body: `Key 2026 NACD data points:
  - 41% of S&P 500 companies now name AI oversight in a standing committee charter, up from 19% in 2024.
  - The audit committee is the most common home, followed by a distinct technology / risk committee.
  - Dedicated "AI" committees remain rare — preferred pattern is integrating AI oversight into an existing committee with updated remit.

For NEDs, the tactical question is whether YOUR committee charter reflects this. If not, request the redline at your next governance review.`,
    questions_to_ask: [
      "Does our committee charter name AI oversight explicitly, and if not, who proposes the redline?",
      "What is the reporting cadence from management on the AI risk register to this committee?",
      "Do we have the right expertise in the room to execute the charge?",
    ],
  },
];

export const LEARN_VIDEOS = [
  {
    id: "vid-hai-2025-index",
    title: "HAI Seminar — Presenting the 2025 AI Index Report",
    kicker: "Video · 1h 14m · Stanford HAI",
    topic: "governance",
    audience: ["ned", "executive"],
    youtube_id: "D03EJhztsHQ",
    speaker: "Nestor Maslej, Research Manager, Stanford HAI",
    source_name: "Stanford Human-Centered AI",
    source_url: "https://www.youtube.com/watch?v=D03EJhztsHQ",
    summary: "The definitive annual survey on where AI regulation, governance, and ethics actually stand — not where tech headlines say they stand. The single most useful hour a board member can spend on state-of-the-world.",
    duration: "1:13:46",
  },
  {
    id: "vid-hai-human-centered",
    title: "How Stanford HAI Defines Human-Centered AI",
    kicker: "Video · 46m · Stanford HAI",
    topic: "foundations",
    audience: ["ned", "executive"],
    youtube_id: "JokJprdSo94",
    speaker: "Russell Wald, Executive Director, Stanford HAI",
    source_name: "Stanford Human-Centered AI",
    source_url: "https://www.youtube.com/watch?v=JokJprdSo94",
    summary: "The guardrails framing most boards use today originate from the human-centred AI school of thought. Wald walks through what it actually requires of an executive team.",
    duration: "0:45:46",
  },
  {
    id: "vid-hai-2024-index",
    title: "2024 Stanford HAI Index Report — key takeaways",
    kicker: "Video · 25m · Stanford HAI",
    topic: "governance",
    audience: ["ned", "executive", "reportee"],
    youtube_id: "mxwyGigwmMI",
    speaker: "Nestor Maslej, Research Manager, Stanford HAI",
    source_name: "Stanford Human-Centered AI",
    source_url: "https://www.youtube.com/watch?v=mxwyGigwmMI",
    summary: "The short version. Twenty-five minutes covering the previous year's meaningful moves in AI regulation, enterprise adoption, and the gap between both.",
    duration: "0:24:38",
  },
  {
    id: "vid-mollick-leadership",
    title: "Ethan Mollick on embracing AI and transforming leadership",
    kicker: "Video · 10m · Knowledge at Wharton",
    topic: "leadership",
    audience: ["executive", "ned"],
    youtube_id: "QhR_3x148iA",
    speaker: "Ethan Mollick, Associate Professor, Wharton",
    source_name: "Knowledge at Wharton",
    source_url: "https://www.youtube.com/watch?v=QhR_3x148iA",
    summary: "Mollick is the sharpest voice writing about what AI means for managers today. This short interview lands the core: AI is a management challenge, not an IT project.",
    duration: "0:10:00",
  },
  {
    id: "vid-mollick-strategy",
    title: "Every leader needs this AI strategy",
    kicker: "Video · 60m · Strange Loop with Sana",
    topic: "strategy",
    audience: ["executive", "ned"],
    youtube_id: "KEQjwE7hDjk",
    speaker: "Ethan Mollick, Wharton",
    source_name: "Strange Loop",
    source_url: "https://www.youtube.com/watch?v=KEQjwE7hDjk",
    summary: "The long version of the above. Why companies are thinking too small, how org charts bend under AI, and what differentiates the executives who actually get value from AI from those who don't.",
    duration: "1:00:00",
  },
  {
    id: "vid-mollick-rules",
    title: "The five rules of great AI leadership",
    kicker: "Video · 6m · Ethan Mollick",
    topic: "leadership",
    audience: ["executive", "ned", "reportee"],
    youtube_id: "21IaJ_kU4Cg",
    speaker: "Ethan Mollick",
    source_name: "Ethan Mollick",
    source_url: "https://www.youtube.com/watch?v=21IaJ_kU4Cg",
    summary: "Six minutes. Five rules. Worth listening to twice before the next board offsite.",
    duration: "0:06:00",
  },
  {
    id: "vid-ng-empower",
    title: "How AI could empower any business",
    kicker: "Video · 11m · TED",
    topic: "foundations",
    audience: ["executive", "ned", "reportee"],
    youtube_id: "reUZRyXxUs4",
    speaker: "Andrew Ng",
    source_name: "TED",
    source_url: "https://www.youtube.com/watch?v=reUZRyXxUs4",
    summary: "The accessible, TED-shaped primer on what AI can and can't do, from one of its most credible builders and educators.",
    duration: "0:10:55",
  },
  {
    id: "vid-ng-faster",
    title: "Andrew Ng — Building faster with AI",
    kicker: "Video · 44m · Y Combinator",
    topic: "strategy",
    audience: ["executive", "reportee"],
    youtube_id: "RNJCfif1dPY",
    speaker: "Andrew Ng",
    source_name: "Y Combinator AI Startup School",
    source_url: "https://www.youtube.com/watch?v=RNJCfif1dPY",
    summary: "Practical. How to think about execution speed when AI is in the toolchain — relevant for executives whose teams are standing up AI-enabled workflows.",
    duration: "0:44:00",
  },
];
