/**
 * Website v7 — copy module.
 *
 * Single source of truth for marketing copy. Voice rules (v7 §B):
 *   - No "empower / unlock / leverage / solutions / dashboard / insights"
 *   - No "AI-powered / AI-driven / cutting-edge / disrupt"
 *   - No "consumer AI / general-purpose / unlike / better than"
 *   - Approved nouns: Solva, Synisense, Agent Cycle (proper nouns).
 *
 * One-word oxblood lift per hero (v7 §A5) — flagged via `lift: "<word>"`.
 */

// ============================================================
// HOME (v7 §4) — three-tier hierarchy
// ============================================================
export const HERO = {
  kicker: "FOR SENIOR PEOPLE",
  headline: "Safe AI for executive work.",
  lift: "Safe",
  dek: "For senior people who want to use AI fully — without governance exposure.",
  primaryCta: { label: "Join the founding cohort", href: "/cohort" },
  tertiary:   { label: "See how it works",        href: "#safety" },
};

export const EVIDENCE = [
  {
    numeral: "280 → 2",
    caption: "Pages in, pages out — a 280-page board pack reduced to a two-page briefing with cited sources.",
  },
  {
    numeral: "5",
    caption: "Layers of reasoning behind every Solva output — frame audit, candidate generation, tension detection, probability weighting, reflection.",
  },
  {
    numeral: "100%",
    caption: "Of claims traceable to their source paragraph in your underlying material.",
  },
  {
    numeral: "SHA-256",
    caption: "Audit chain on every conversation, exportable in board-ready form for committee review.",
  },
];

// Tier 1 — SAFETY (v7 §4.4)
export const TIER_1 = {
  kicker: "TIER ONE · SAFETY",
  headline: "The work you do is private work. Akki treats it that way.",
  body: "Every prompt and every document is anonymised by Synisense before any model sees it. Re-identification is reversed only on the answer that returns to you. Your underlying material never leaves your tenant. Nothing you put into Akki feeds anybody's training data.",
  band_overlay: "Reasoning runs against anonymised text. Your audit chain is hash-verifiable.",
  bullets: [
    "Anonymisation before any AI processing — names, emails, numbers, jurisdictions, financials.",
    "Companies are walled. A seat on one board cannot see a single token from another.",
    "Every reasoning step writes a SHA-256 row into an append-only chain you can export and verify offline.",
  ],
};

// Tier 2 — THE WORKSPACE (v7 §4.5) — 4 capabilities, NO product names
export const TIER_2 = {
  kicker: "TIER TWO · THE WORKSPACE",
  headline: "A working environment, not a chat box.",
  dek: "Senior decisions get made together, over weeks, across boards. The workspace mirrors that.",
  capabilities: [
    {
      title: "A reading library that knows the cycle.",
      body: "Upload board material once. The workspace threads it across pre-board reading, in-meeting referencing, and follow-ups. Every artefact is one click from any other surface.",
    },
    {
      title: "A reasoning surface for hard questions.",
      body: "When a question is too important for a chat reply, the workspace runs a structured reasoning pass — frame audit first, candidate paths, tension detection, probability-weighted synthesis, reflection — with the answer cited to the underlying paragraphs.",
    },
    {
      title: "A cycle engine for the work between meetings.",
      body: "Setup the agenda, build the team, score contributions, send follow-ups under an opaque cycle alias, compile the next pack. Replies thread back automatically.",
    },
    {
      title: "Deterministic outputs, board-ready.",
      body: "Briefs, decks and reports render byte-deterministically as DOCX, PPTX and PDF. The version you sent is provably the version you reviewed — every artefact is hash-stamped at export.",
    },
  ],
};

// Tier 3 — THE INVENTIONS (v7 §4.6)
export const TIER_3 = {
  kicker: "TIER THREE · THE INVENTIONS",
  headline: "Three pieces of original work behind the workspace.",
  dek: "These are the parts of Akki you cannot get anywhere else. Each is open-architecture, in code, and documented in Methodology.",
  cards: [
    {
      title: "Solva",
      sub: "Structured reasoning with five layers.",
      body: "Four modes — seek clarity, develop strategy, simulate hypothesis, see perspectives. Each runs the same five-layer pipeline: frame audit, candidate generation, tension detection, probability weighting, reflection. The answer reflects what was actually weighed.",
      cta: { label: "How Solva reasons", href: "/solva" },
    },
    {
      title: "Synisense",
      sub: "Three-layer anonymisation, then reasoning.",
      body: "A deterministic ladder — regex, NER, small-model judge — runs before any frontier model sees your prompt. Re-identification reverses only on the response. The audit row records which layer caught each identifier.",
      cta: { label: "Read about Synisense", href: "/trust#synisense" },
    },
    {
      title: "Agent Cycle",
      sub: "The work between meetings, autonomously.",
      body: "Akki contacts your team under an opaque alias, threads their replies, scores contributions against agenda items, drafts the next pack, and routes follow-ups. You review and sign off; the cycle compiles.",
      cta: { label: "See Agent Cycle", href: "/cycle-manager" },
    },
  ],
};

// THREE AUDIENCES (v7 §4.7)
export const AUDIENCES = [
  {
    title: "Operating executives.",
    sub: "CEO, CFO, COO, CRO.",
    body: "You run the cycle. You produce the next board pack. You answer follow-ups in the week after. Akki holds the reading, the reasoning, and the cycle of work between meetings.",
    cta: { label: "For executives", href: "/for-executives" },
  },
  {
    title: "Non-executive directors.",
    sub: "Independent board roles.",
    body: "You sit on multiple boards. You read packs over a weekend. You walk in with three questions that move the room. Akki gives you a private reading library per seat and a reasoning surface for what you want to test.",
    cta: { label: "For NEDs", href: "/for-non-executive-directors" },
  },
  {
    title: "The senior leadership team.",
    sub: "Exco preparing for the board.",
    body: "Each member contributes a section. Akki holds the cross-document consistency — when the CFO's number doesn't match the COO's, the workspace surfaces it before the chair finds it.",
    cta: { label: "For Exco", href: "/for-exco" },
  },
];

export const COHORT_TEASER = {
  kicker: "BEFORE AKKI SHIPS",
  headline: "We are admitting a small founding cohort first.",
  body: "Akki is finished enough to use, and not finished enough to ship. We are admitting roughly twenty executives, NEDs and senior leadership-team members to use it first. In exchange for honest feedback in the first six months, the founding cohort gets early-access pricing locked for two years.",
  cta: { label: "Read about the cohort", href: "/cohort" },
};

export const INVERTED_CTA = {
  kicker: "THE FOUNDING COHORT",
  headline: "See your own board pack analysed in sixty seconds.",
  body: "The sandbox lets you paste a paragraph from your last board paper, or generate a synthetic one for your sector, and watch Solva work. Nothing is retained. No account needed.",
  cta: { label: "Begin sandbox", href: "/sandbox" },
  meta: "No account · No data retained · 60-second experience · Anonymous",
};

// ============================================================
// WHY AKKI (v7 §5)
// ============================================================
export const WHY = {
  kicker: "WHY AKKI",
  headline: "Senior work has structure.",
  lift: "structure",
  dek: "AI products are mostly built for two-thumb consumers or for engineers. Senior work is neither.",
  sections: [
    {
      title: "Senior work is private work.",
      body: "Most products in the AI category treat your prompts as training material. Akki treats them as evidence in a chain you can prove later. Nothing you write or upload trains anything. Anonymisation happens before reasoning, not after.",
    },
    {
      title: "Decisions, not transcripts.",
      body: "A chat thread answers the question you ask. The workspace helps you find the question worth asking. The reasoning surface holds the line through five layers of work — frame audit, candidates, tension, probability weighting, reflection — so you leave with a position, not a monologue.",
    },
    {
      title: "A peer, not a vendor.",
      body: "Akki is built by people whose decisions have shown up on annual reports. Restraint and clarity are the design specification. You are not the target of conversion funnels here — you are the executive holding accountability for the work.",
    },
    {
      title: "Built around how boards actually work.",
      body: "Pre-board reading, in-meeting reference, post-meeting follow-up. Briefs, minutes, committee packs. The workspace is a faithful mirror of the calendar your governance function already runs.",
    },
  ],
};

// ============================================================
// WHAT AKKI DOES (v7 §6) — product overview hub
// ============================================================
export const WHAT_AKKI_DOES = {
  kicker: "WHAT AKKI DOES",
  headline: "Seven surfaces. One workspace.",
  lift: "workspace",
  dek: "Each surface is a faithful answer to a moment that recurs in senior work. Each is built on Synisense anonymisation and the SHA-256 audit chain. Together they are the workspace.",
  surfaces: [
    { slug: "solva",            name: "Solva",            sub: "Structured reasoning.",        body: "Four modes for the questions a chat reply cannot hold. Frame audit, candidates, tension, probability weighting, reflection — cited.", href: "/solva" },
    { slug: "akki-chat",        name: "Akki Chat",        sub: "Trust-first multi-model.",     body: "Claude, Gemini, GPT. Every turn anonymised before send and hashed into a verifiable audit chain.", href: "/akki-chat" },
    { slug: "work-studio",      name: "Work Studio",      sub: "Deterministic outputs.",       body: "Briefs, decks and reports as byte-deterministic DOCX, PPTX, PDF — every render hash-stamped.", href: "/work-studio" },
    { slug: "cycle-manager",    name: "Cycle Manager",    sub: "Setup. Run. Ship.",            body: "Board cycle workflow with real outbound email under opaque cycle aliases; inbound replies thread back into the cycle.", href: "/cycle-manager" },
    { slug: "monitor",          name: "Monitor",          sub: "Goals at risk.",               body: "What is drifting, what is opening, and where the evidence sits — per role function, per company.", href: "/monitor" },
    { slug: "pulse",            name: "Pulse",            sub: "Quiet signals.",               body: "A restrained signal feed with confidence floors and lifecycle states. Cross-board patterns visible — never cross-board content.", href: "/pulse" },
    { slug: "document-journal", name: "Document Journal", sub: "Your reading assistant.",      body: "Upload, read, annotate, route. Every artefact one click from Chat, Cycle, Work Studio, or Solva. Reading momentum surfaced quietly.", href: "/document-journal" },
  ],
};

// ============================================================
// PER-PRODUCT PAGES (v7 §7)
// ============================================================
export const PRODUCTS = {
  solva: {
    kicker: "SOLVA",
    headline: "Structured reasoning for questions a chat cannot hold.",
    lift: "Structured",
    dek: "Four modes. Five reasoning layers. Every answer carries the trace.",
    modes: [
      { name: "Seek clarity",        body: "When you don't know what's actually going on. Solva runs the diagnostic that narrows possible causes and surfaces what is underneath your framing." },
      { name: "Develop strategy",    body: "When you need a direction and want to test your thinking. Solva produces probability-weighted options with sensitivity analysis." },
      { name: "Simulate hypothesis", body: "When you want to stress-test an assumption before you commit. Solva runs the simulation and flags tensions before they become decisions." },
      { name: "See perspectives",    body: "When you want to see your situation through a different mind — a CFO's view, an investor's view, a regulator's view, a counterparty's view." },
    ],
    layers: [
      "Frame audit — what's missing before we proceed.",
      "Candidate generation — the paths worth weighing.",
      "Tension detection — where two paths collide.",
      "Probability weighting — what each path is actually worth.",
      "Reflection — what the answer tells you about the question.",
    ],
  },
  "akki-chat": {
    kicker: "AKKI CHAT",
    headline: "Multi-model chat, anonymised before the model sees you.",
    lift: "anonymised",
    dek: "Claude, Gemini, GPT. The audit chain runs underneath every turn.",
    bullets: [
      "Synisense anonymisation runs on every outbound prompt; re-identification on the response.",
      "Each turn writes a SHA-256 row into an append-only audit chain. Download and verify offline at any time.",
      "Two-pass discipline — the model thinks silently, then speaks carefully.",
      "Citations carry pill provenance back to source paragraphs in your reading library.",
    ],
  },
  "work-studio": {
    kicker: "WORK STUDIO",
    headline: "Deterministic outputs. Board-ready every time.",
    lift: "Deterministic",
    dek: "Briefs, decks and reports rendered byte-deterministically — every export hash-stamped.",
    bullets: [
      "DOCX and PPTX render with brand-grade typography, sensitivity bands and validator notes.",
      "Cross-document inconsistencies are surfaced before sign-off — the chair never finds them first.",
      "Every export is hash-stamped so the version you sent is provably the version you reviewed.",
      "Source paragraphs are cited inline; nothing is invented.",
    ],
  },
  "cycle-manager": {
    kicker: "CYCLE MANAGER",
    headline: "The work between meetings. Run by Akki, signed by you.",
    lift: "between",
    dek: "Setup the agenda. Build the team. Score contributions. Send follow-ups under opaque alias. Compile the pack.",
    steps: [
      "Agenda — paste it or extract from last month's minutes.",
      "Team — name the reportees, scope their areas of ownership.",
      "Contributions — Akki asks each reportee under an opaque cycle alias; replies thread back automatically.",
      "Scoreboard — readiness scored against agenda items.",
      "Follow-ups — chase what's thin, approve every outbound under your name.",
      "Compilation — the next pack composes itself, ready for Work Studio.",
    ],
  },
  "monitor": {
    kicker: "MONITOR",
    headline: "What is drifting. What is opening. Where the evidence sits.",
    lift: "drifting",
    dek: "Strategic goals tracked against where you actually are. Per function, per company.",
    bullets: [
      "Goals extracted from your strategic plan, scored monthly with probability of hitting.",
      "Signals filtered to what your function tracks — CEO, CFO, COO, CRO have different views.",
      "Score sparkline shows momentum across the last twelve readings; trend colour-keyed to current band.",
      "Every figure cites the document it came from.",
    ],
  },
  "pulse": {
    kicker: "PULSE",
    headline: "Quiet signals. Confidence floors. Lifecycle states.",
    lift: "Quiet",
    dek: "A restrained feed for the noise of operating life. Cross-board patterns visible, never cross-board content.",
    bullets: [
      "Confidence floors filter the feed so weak signals never reach you.",
      "Each signal carries a lifecycle state — candidate → verified → persisted — fully auditable.",
      "Cross-board view surfaces only metadata signatures; content stays in its tenant.",
      "Lens Room reframes any signal through six analytical frameworks on demand.",
    ],
  },
  "document-journal": {
    kicker: "DOCUMENT JOURNAL",
    headline: "Your reading library. With memory of how you read.",
    lift: "memory",
    dek: "Upload board material once. The workspace threads it across every surface and reads alongside you.",
    bullets: [
      "Read receipts and reading time tracked privately, per document and per reader.",
      "Anchor passages with private notes that resurface when the next pack references the same idea.",
      "Document evolution — every version chained back to its parent, with a diff view at sign-off.",
      "One-click from any other surface — Solva, Chat, Cycle, Work Studio all link back here.",
    ],
  },
};

// ============================================================
// AUDIENCE PAGES (v7 §8)
// ============================================================
export const AUDIENCE_PAGES = {
  "for-executives": {
    kicker: "FOR EXECUTIVES",
    headline: "For the operating executive running the cycle.",
    lift: "running",
    dek: "CEO, CFO, COO, CRO. You produce the next pack. You answer follow-ups in the week after. Akki holds the work between meetings.",
    pricing_line: "Executive — $179 / month. Founding cohort price: $116 / month, locked for two years.",
    moments: [
      { title: "The week before the board.",         body: "Akki composes the pack from team contributions; Work Studio renders it deterministically; the validator flags any inconsistency before you sign off." },
      { title: "The hour before the board.",          body: "Solva runs frame audits on the items you expect to be challenged. You walk in with the question worth asking, not the question you wrote down." },
      { title: "The week after the board.",          body: "Cycle Manager threads the chair's follow-ups back to the right Exco member under an opaque alias. Replies arrive in your inbox already routed." },
    ],
    image: "for-executives-hero.webp",
    image_alt: "A senior executive annotating a printed report at a quiet desk.",
  },
  "for-non-executive-directors": {
    kicker: "FOR NEDS",
    headline: "For the non-executive director sitting on multiple boards.",
    lift: "multiple",
    dek: "Independent board roles. You read packs over a weekend. You walk in with three questions that move the room.",
    pricing_line: "NED — $129 / month. Founding cohort price: $84 / month, locked for two years.",
    moments: [
      { title: "Reading the pack on Sunday morning.", body: "The Document Journal threads each pack against the previous cycle's open questions; what was promised, what changed, what is missing." },
      { title: "Walking in on Tuesday.",              body: "Solva's pre-board mode produces a one-page brief and three standout questions — cited, weighted, and grounded in the underlying paragraphs." },
      { title: "Cross-board pattern, not content.",   body: "Pulse surfaces metadata signatures across your seats. You see that three boards are converging on the same regulatory risk — without seeing any board's text." },
    ],
    image: "for-neds-hero.webp",
    image_alt: "A non-executive director reading a board pack in a quiet wood-panelled lounge.",
  },
  "for-organisations": {
    kicker: "FOR ORGANISATIONS",
    headline: "For companies rolling out Akki to a leadership team.",
    lift: "team",
    dek: "SSO, tenancy, governance reporting. Anonymised reasoning across the whole Exco. One pricing band that scales by seat.",
    pricing_line: "Organisation — $150–$300 per seat per month, depending on tenancy and onboarding scope.",
    moments: [
      { title: "Onboarding the whole Exco.",         body: "Each member gets their own workspace. The Privacy Wall keeps roles isolated. The Company Secretary sees the governance reporting layer, not anyone's prompts." },
      { title: "Governance reporting that adds up.", body: "Audit chain exports, anonymisation counts, retention windows — all surfaced to your governance function in a single quarterly pack." },
      { title: "Tuning Solva to your sector.",       body: "Dedicated Solva tuning means the frame audits know your jurisdiction, regulator, and the specific judgement vocabulary your sector uses." },
    ],
  },
  "for-exco": {
    kicker: "FOR EXCO",
    headline: "For the senior leadership team preparing what the board will read.",
    lift: "leadership",
    dek: "The CFO drafting the going-concern paragraph. The COO writing the operational risk note. The CRO turning four colour-coded heatmaps into two paragraphs of judgement.",
    moments: [
      { title: "The board pack that lands together.", body: "Each Exco member contributes a section. Akki holds cross-document consistency — when the CFO's number doesn't match the COO's, the workspace surfaces it before the chair finds it." },
      { title: "Papers that survive scrutiny.",       body: "Deterministic DOCX and PPTX renders, sensitivity-banded, validator-checked, hash-stamped. The paper you sent is provably the paper that left the system." },
      { title: "The week after.",                     body: "Cycle Manager threads the board's follow-ups back to the specific Exco member who owns each item. Outbound under opaque alias, inbound automatically routed." },
    ],
  },
};

// ============================================================
// TRUST (v7 §9) — only page where Solva / Synisense / Agent Cycle
// appear as technical names in marketing copy.
// ============================================================
export const TRUST = {
  kicker: "TRUST & SOVEREIGNTY",
  headline: "Four architectural commitments. Each one in code.",
  lift: "code",
  dek: "Akki's trust posture is not a marketing claim. It is enforced in code, audited in tests, and visible to your governance function.",
  pillars: [
    {
      anchor: "synisense",
      title: "Synisense at depth.",
      sub: "Three-layer anonymisation, then reasoning.",
      body: "Synisense runs a deterministic ladder on every outbound prompt — regex first, then a Presidio NER pass, then a small-model judge if either layer's confidence falls below threshold. The original payload is encrypted at rest with a customer-isolated key. Re-identification happens only on the response that returns to you. Every audit row records which layer caught each identifier — regex, Presidio, or LLM-fallback.",
    },
    {
      anchor: "solva",
      title: "Solva at depth.",
      sub: "Five reasoning layers, each auditable.",
      body: "Every Solva output runs the same five-layer pipeline: frame audit, candidate generation, tension detection, probability weighting, reflection. Each layer's input, output, and decision criteria persist to the session record. You can replay any reasoning step against the original payload.",
    },
    {
      anchor: "agent-cycle",
      title: "Agent Cycle at depth.",
      sub: "Autonomous between meetings.",
      body: "Agent Cycle composes follow-ups against the agenda, contacts reportees under an opaque cycle alias (no executive's real email ever leaves the workspace), threads replies, scores contributions, and drafts the next pack. Every outbound and inbound message persists in the cycle's audit chain. Approval is yours; the cycle compiles on your sign-off.",
    },
    {
      anchor: "memory-provenance",
      title: "Memory and provenance.",
      sub: "Reading momentum without surveillance.",
      body: "The Document Journal records who has read what and when, scoped per company, never cross-tenant. Reading momentum surfaces as a quiet signal — never as a leaderboard. Every claim cites the source paragraph; every reasoning trace is hash-chained from first prompt to final answer.",
    },
  ],
};

// ============================================================
// COHORT (v7 §10.1) — light surface, no form this sprint
// ============================================================
export const COHORT = {
  kicker: "FOUNDING COHORT",
  headline: "Used first by roughly twenty senior people.",
  lift: "first",
  dek: "Akki is finished enough to use, and not finished enough to ship. We are admitting a small founding cohort to use it first.",
  body: "In exchange for honest feedback in the first six months, the cohort gets early-access pricing locked for two years. We read every application and reply personally. We are not running a waitlist; we are running an admission.",
  cta: { label: "See the full proposition and apply", href: "https://syni.ai/akki-cohort" },
};

// ============================================================
// PRICING (v7 §10.2)
// ============================================================
export const PRICING = {
  kicker: "PRICING",
  headline: "Three tiers. Plus organisation.",
  lift: "tiers",
  dek: "Founding cohort pricing is locked for two years. Standard pricing applies thereafter.",
  table: [
    { tier: "Executive",                  standard: "$179 / month", founding: "$116 / month" },
    { tier: "NED",                        standard: "$129 / month", founding: "$84 / month" },
    { tier: "Dual",                       standard: "$249 / month", founding: "$162 / month" },
    { tier: "Reportee seat (Org plans)",  standard: "+$49 / month", founding: "—" },
    { tier: "Organisation",               standard: "$150–$300 / seat", founding: "—" },
  ],
  footnote: "Founding cohort pricing is admission-only. We are not running a discount code or a waitlist.",
};

// ============================================================
// ABOUT (v7 §10.3) — text-only, no platitudes
// ============================================================
export const ABOUT = {
  kicker: "ABOUT",
  headline: "Akki is built by operators who have sat where you sit.",
  lift: "operators",
  dek: "A small team in Nairobi. We have spent decades inside the kinds of organisations Akki serves.",
  body: [
    "Akki is a product of Syni.ai, a research studio in Nairobi. The team is small on purpose. We build for the people we have been — operating executives running cycles, non-executive directors reading packs, senior leadership teams preparing what the board will read.",
    "We started Akki because every product in the AI category has been built for two-thumb consumers or for engineers. Senior work is neither. The work that matters carries audit consequences and requires a counterpart who understands restraint.",
    "Akki is not a chat product. It is a workspace for the work that actually matters. We expect to be used by people who already know what they are doing and want a counterpart, not a tutor.",
  ],
  named_roles: [
    { role: "Founder",          contact: "bram@syni.ai" },
    { role: "Engineering lead", contact: "info@syni.ai" },
    { role: "Studio operations", contact: "info@syni.ai" },
  ],
};

// ============================================================
// CONTACT (v7 §10.4) — three paths
// ============================================================
export const CONTACT = {
  kicker: "CONTACT",
  headline: "Three ways to reach us.",
  lift: "Three",
  dek: "Pick the one that matches what you are doing. We reply personally.",
  paths: [
    {
      label: "For the founding cohort",
      body: "Direct to the founder. Use this if you are applying as an executive, an NED, or a senior leadership-team member.",
      cta_label: "bram@syni.ai",
      cta_href: "mailto:bram@syni.ai",
    },
    {
      label: "For organisations",
      body: "Use the organisation form if you are rolling Akki out to a leadership team or a portfolio.",
      cta_label: "Organisation form",
      cta_href: "/contact?form=organisation",
    },
    {
      label: "For everything else",
      body: "General questions, press, partnerships. info@syni.ai or the general form.",
      cta_label: "info@syni.ai",
      cta_href: "mailto:info@syni.ai",
    },
  ],
};
