// Role-specific board-focused audit questions.
// 7 questions total. First 2 are shared (industry + jurisdiction), last 5 branch.

export const SHARED_QUESTIONS = [
  {
    id: "industry",
    type: "industry",
    question: "Which industry best represents this context?",
    hint: "Drives benchmarks, comparator set, and sector-specific frameworks.",
  },
  {
    id: "jurisdiction",
    type: "jurisdiction",
    question: "Primary jurisdiction?",
    hint: "Regulatory context, currency, peer set.",
  },
];

export const NED_QUESTIONS = [
  {
    id: "board_cadence",
    type: "single",
    question: "How often does this board meet?",
    options: [
      { value: "monthly", label: "Monthly" },
      { value: "bimonthly", label: "Bi-monthly" },
      { value: "quarterly", label: "Quarterly" },
      { value: "adhoc", label: "Ad-hoc / project-based" },
    ],
  },
  {
    id: "oversight_areas",
    type: "multi",
    question: "Which oversight areas do you actively shape?",
    hint: "Select all that apply.",
    options: [
      { value: "audit", label: "Audit & financial reporting" },
      { value: "risk", label: "Risk & compliance" },
      { value: "remco", label: "Remuneration" },
      { value: "nomco", label: "Nominations & succession" },
      { value: "strategy", label: "Strategy & performance" },
      { value: "tech", label: "Technology & data" },
      { value: "esg", label: "ESG & sustainability" },
    ],
  },
  {
    id: "briefing_style",
    type: "single",
    question: "How do you prefer briefings?",
    options: [
      { value: "summary", label: "Executive summary with drill-downs" },
      { value: "detailed", label: "Detailed, with tables and appendices" },
      { value: "raw_data", label: "Raw data plus a short interpretation" },
    ],
  },
  {
    id: "risk_appetite",
    type: "single",
    question: "What's the board's stated risk appetite?",
    options: [
      { value: "conservative", label: "Conservative — capital preservation first" },
      { value: "balanced", label: "Balanced — growth with managed downside" },
      { value: "aggressive", label: "Aggressive — prioritise growth / share gain" },
      { value: "unclear", label: "Not clearly stated" },
    ],
  },
  {
    id: "pack_trust",
    type: "single",
    question: "How much do you trust the board packs you receive?",
    hint: "This calibrates AKKI's verification posture.",
    options: [
      { value: "trusted", label: "Trusted — mostly accurate and timely" },
      { value: "mixed", label: "Mixed — quality varies by topic" },
      { value: "weak", label: "Weak — frequent gaps or stale data" },
    ],
  },
];

export const EXEC_QUESTIONS = [
  {
    id: "reporting_cadence",
    type: "single",
    question: "How often do you report to the board?",
    options: [
      { value: "monthly", label: "Monthly" },
      { value: "quarterly", label: "Quarterly" },
      { value: "halfyearly", label: "Half-yearly" },
      { value: "adhoc", label: "Ad-hoc" },
    ],
  },
  {
    id: "top_kpis",
    type: "multi",
    question: "Which KPIs do you track most closely?",
    hint: "Select all that apply. Custom KPIs can be added later in Monitor.",
    options: [
      { value: "revenue", label: "Revenue / top line" },
      { value: "margin", label: "Margin / profitability" },
      { value: "cac_ltv", label: "CAC / LTV / retention" },
      { value: "cashflow", label: "Cashflow / runway" },
      { value: "nps", label: "NPS / customer satisfaction" },
      { value: "ops_efficiency", label: "Operational efficiency" },
      { value: "headcount", label: "Headcount / productivity" },
      { value: "market_share", label: "Market share" },
    ],
  },
  {
    id: "team_scope",
    type: "single",
    question: "How many direct reports do you lead?",
    options: [
      { value: "0-3", label: "0–3 (senior IC or small team)" },
      { value: "4-8", label: "4–8 (mid-sized org)" },
      { value: "9-20", label: "9–20 (large org)" },
      { value: "20+", label: "20+ (enterprise scale)" },
    ],
  },
  {
    id: "decision_horizon",
    type: "single",
    question: "What's your dominant decision horizon?",
    options: [
      { value: "weekly", label: "Weekly operating rhythm" },
      { value: "monthly", label: "Monthly / quarterly planning" },
      { value: "annual", label: "Annual strategic cycle" },
      { value: "multi_year", label: "Multi-year transformation" },
    ],
  },
  {
    id: "pain_points",
    type: "multi",
    question: "Which of these are currently hardest for you?",
    hint: "Select up to 3.",
    options: [
      { value: "signal_noise", label: "Cutting through signal vs noise" },
      { value: "data_trust", label: "Trusting the underlying data" },
      { value: "board_prep", label: "Preparing board-ready narratives" },
      { value: "stakeholder_align", label: "Aligning stakeholders on decisions" },
      { value: "talent", label: "Talent and team capability" },
      { value: "tech_debt", label: "Tech debt / systems constraints" },
      { value: "pace", label: "Pace of change" },
    ],
  },
];
