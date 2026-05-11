/**
 * Phase I1 — All website copy lives here. Edit copy without
 * touching components. Senior peer voice; no marketing hyperbole;
 * no comparisons, testimonials, or vendor logos.
 */

export const HERO = {
  eyebrow: "For senior people",
  headline: "For senior people who want to use AI fully — without governance exposure.",
  subhead: "Akki gives operating executives and non-executive directors a private, audit-defensible way to think with AI on the work that actually matters.",
  // Phase J.2 — site-wide primary CTA is now "Try the sandbox" → /sandbox.
  // The cohort intake page keeps its own contextual CTA.
  primaryCta: { label: "Try the sandbox", href: "/sandbox" },
  secondaryCta: { label: "How it works", href: "/methodology" },
};

export const HIERARCHY = [
  {
    tier: "01",
    label: "Safety",
    title: "Sovereign by construction.",
    body: "Your prompts and documents are de-identified before any model sees them. Every reasoning step is auditable. Your data does not train anything.",
  },
  {
    tier: "02",
    label: "Workspace",
    title: "A working environment, not a chat box.",
    body: "Document Journal. Cycle Manager. Work Studio. Pulse. Six surfaces that match how senior decisions actually get made — together, over weeks, across boards.",
  },
  {
    tier: "03",
    label: "Inventions",
    title: "Two original tools you cannot get elsewhere.",
    body: "Synisense Shield, our three-layer de-identification engine. Solva, our multi-mode reasoning surface. Both built for the way executives and NEDs actually think.",
  },
];

export const COHORT_TEASER = {
  label: "Founding cohort — May 2026",
  body: "We are admitting a small group of executives and NEDs to use Akki first. In exchange for feedback, the founding cohort gets early-access pricing locked for life.",
  cta: { label: "Read about the cohort", href: "/cohort" },
};

export const SURFACES = [
  { id: "solva", title: "Solva", subtitle: "Structured reasoning.",
    body: "Four modes: seek clarity, develop strategy, simulate hypothesis, get perspective. Frame audit and audit-gap surfacing before any answer." },
  { id: "chat", title: "Akki Chat", subtitle: "Trust-first multi-model.",
    body: "Claude, Gemini, GPT. Every turn hashed into a verifiable audit chain. Two-pass discipline so the model says less, but says it more carefully." },
  { id: "studio", title: "Work Studio", subtitle: "Deterministic outputs.",
    body: "Board pack, minutes, committee pack. Brand-grade DOCX, PPTX, and PDF — byte-deterministic, every render hashed for governance." },
  { id: "cycle", title: "Cycle Manager", subtitle: "Setup. Run. Ship.",
    body: "Board cycle workflow with real outbound email under opaque cycle aliases. Inbound replies thread back into the cycle." },
  { id: "monitor", title: "Monitor", subtitle: "Goals at risk.",
    body: "Surfaces what is drifting, what is opening, and where the evidence sits — per role function, per company." },
  { id: "pulse", title: "Pulse", subtitle: "Quiet signals.",
    body: "A restrained signal feed with confidence floors and lifecycle states. Cross-board patterns visible — never cross-board content." },
  { id: "journal", title: "Document Journal", subtitle: "Your working library.",
    body: "Upload, read, annotate, route. Every artefact one click from Chat, Cycle, Work Studio, or Solva." },
];

export const WHY = [
  { title: "Senior work is private work.",
    body: "Most consumer AI products treat your prompts as training material. Akki treats them as evidence in a chain you can prove later." },
  { title: "Decisions, not transcripts.",
    body: "Two-pass reasoning means the model thinks silently, then speaks carefully. You get a position, not a monologue." },
  { title: "A peer, not a vendor.",
    body: "We build for people whose decisions show up in audit committees and on annual reports. Restraint and clarity are the spec." },
  { title: "Built around how boards actually work.",
    body: "Cycle pre-board, in-meeting, post-meeting. Briefs, minutes, committee packs. Things real NEDs and CEOs hand each other every month." },
];

export const TRUST = {
  intro: "Akki is built on three architectural commitments. Each is enforced in code, audited in tests, and visible to your governance function.",
  pillars: [
    {
      title: "Synisense Shield",
      sub: "Three-layer de-identification.",
      body: "Every prompt is processed by a deterministic ladder — regex, NER, and a small-model judge — before any frontier model sees it. The original payload is encrypted at rest with a customer-isolated key. Re-identification happens only on the response.",
    },
    {
      title: "Privacy Wall",
      sub: "Companies are architecturally isolated.",
      body: "You can hold seats on twelve boards in Akki. None of them sees a single token of any other. Cross-board features run on metadata signatures, never content. Foreign tenants are field-projection-locked, denylisted at the query layer.",
    },
    {
      title: "Hash-chained audit",
      sub: "Every reasoning step verifiable.",
      body: "Every chat turn writes a SHA-256 row into a hash chain whose genesis literal is locked in source. Your governance team can download the chain and verify it offline at any time.",
    },
    {
      title: "Sovereignty",
      sub: "Your data does not train anything.",
      body: "No prompts, no documents, no outputs feed any model's training data. Model providers see only Synisense-shielded payloads. Your data lives in your tenant. You can export it.",
    },
  ],
};

export const PRICING = {
  intro: "Three tiers, plus organisation pricing. The founding cohort is admitted at a price that locks for life.",
  tiers: [
    {
      id: "executive", name: "Executive",
      price: "£1,200", period: "per month",
      audience: "For a single operating executive (CEO, CFO, COO).",
      includes: [
        "All six product surfaces",
        "Up to 3 active companies",
        "Synisense Shield + hash-chained audit",
        "All four Solva modes",
        "Brand-grade DOCX / PPTX / PDF export",
      ],
    },
    {
      id: "ned", name: "NED",
      price: "£600", period: "per month",
      audience: "For a single non-executive director sitting on multiple boards.",
      includes: [
        "Pulse, Cycle Manager (NED), Solva, Akki Chat",
        "Up to 6 active board seats",
        "Cross-board metadata view (no content)",
        "Confidential committee through-line",
      ],
    },
    {
      id: "dual", name: "Dual",
      price: "£1,500", period: "per month",
      audience: "For senior people who are both — executive role and one or more NED seats.",
      includes: [
        "Everything in Executive",
        "Everything in NED",
        "Strict Privacy Wall between roles",
        "Single sign-in, separate audit trails",
      ],
    },
    {
      id: "organisation", name: "Organisation",
      price: "On request", period: "",
      audience: "For companies and funds rolling out Akki to a leadership team or portfolio.",
      includes: [
        "SSO + tenancy controls",
        "Company Secretary sharing model",
        "Dedicated Solva tuning",
        "Governance reporting on use",
      ],
    },
  ],
  footnote: "Founding cohort: 30% off — locked for life. Limited to the first cohort.",
};

export const COHORT = {
  headline: "Founding cohort",
  body: "We are admitting a small group of executives and NEDs to use Akki first. In exchange for honest feedback during the first six months, the cohort gets 30% off — locked for life. We are not running a waitlist. We read every application and reply personally.",
  formIntro: "Tell us a little about you and we'll be in touch within a few business days.",
};

export const ABOUT = {
  body: [
    "Akki is built by a small team of operators, builders, and former board members who have spent decades inside the kinds of organisations Akki serves.",
    "We started Akki because every product in the AI category has been built for two-thumb consumers or for engineers — never for the senior peer holding accountability for hard decisions.",
    "Akki is not a chat product. It is a working environment for the work that actually matters. We expect to be used by people who already know what they are doing and want a counterpart, not a tutor.",
  ],
};

export const FOOTER = {
  signoff: "Made with restraint.",
};
