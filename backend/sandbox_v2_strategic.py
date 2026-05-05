"""Phase L.1 — Strategic Documents Pack corpus.

Sibling to `backend/sandbox_v2_corpus.py`. Carries the 14 strategic-layer
documents from the Sandbox Strategic Documents Pack (v1, ingested
2026-05-05) across 5 contexts:

    • Mara Heritage Bank         (org_type="bank")        ×3
    • Lenana Health Group        (org_type="healthcare")  ×3
    • Korogocho Logistics Group  (org_type="logistics")   ×3
    • Ministry of Industrial
      Modernisation              (org_type="government")  ×3
    • Tahidi Systems             (org_type="technology")  ×2
                                                      total = 14

Ingested VERBATIM (no DRAFT markers, no paraphrase). Inter-doc
references back to the tactical Sandbox Content Pack documents are
preserved — the strategic plan's "Q1 2026 results show provisioning
compression to 68%" line, for example, refers to a numeric figure that
lives in the tactical pack; we do not rewrite either side.

Public surface:
    STRATEGIC_DOCUMENTS                  dict keyed by org_type
    pick_strategic_documents(org_type,
                             kind=None)  filter helper
    strategic_doc_titles(org_type)       titles only (cheap)
    strategic_doc_by_id(doc_id)          single-doc lookup
    strategic_corpus_health()            counts + source markers

`doc_kind` values (locked): "strategic_plan" | "framework" | "strategy" |
"theory_of_change" | "investment_thesis" | "political_economy".

Each document dict carries: id (stable slug), title, org_type, kind,
body (verbatim), preview (first 200 chars of body), position (1-based
within its org context), and pack_section (BANK / HEALTHCARE / LOGISTICS
/ TECHNOLOGY / GOVERNMENT).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ═════════════════════════════════════════════════════════════════════════
#  BANK — Mara Heritage Bank ×3
# ═════════════════════════════════════════════════════════════════════════
_BANK_DOCS: List[Dict[str, Any]] = [
    {
        "id": "strat-bank-plan-2024-2028",
        "title": "Five-Year Strategic Plan 2024-2028 — Executive Summary",
        "kind": "strategic_plan",
        "body": (
            "Mara Heritage Bank Limited · Approved by Board 28 March 2024 · "
            "Reviewed annually · Confidential Strategic context Mara Heritage Bank "
            "enters its 2024-2028 strategic period at an inflection. The bank's "
            "traditional strength — corporate banking relationships across the "
            "upcountry network — has produced consistent ROE in the 14-16% range "
            "over the last cycle, but at a structural cost: limited fee income "
            "diversification, growing dependence on a real estate-correlated "
            "corporate book, and a digital channel that has lagged peers. The "
            "strategic question for this cycle is not whether to evolve, but how "
            "— and at what pace. The Board has reviewed three strategic options. "
            "Option A: deepen the existing corporate franchise with selective SME "
            "expansion, accept structural sector concentration, optimise "
            "cost-to-income within the current model. Option B: pursue digital "
            "transformation aggressively, accepting near-term return compression "
            "to build a structurally different revenue mix by 2028. Option C: a "
            "balanced path that preserves corporate banking strength while "
            "building digital capability incrementally, with milestones that "
            "allow course correction. Strategic choice The Board has endorsed "
            "Option C. The rationale rests on three judgements. First, the bank's "
            "corporate franchise is genuinely valuable and not easily reproduced "
            "— destroying it to fund digital ambition would be a strategic error. "
            "Second, the digital channel investment is non-discretionary; the "
            "question is pace, not whether. Third, the balance sheet capacity for "
            "Option B-level investment without external capital is constrained by "
            "the existing concentration profile. Strategic targets Over the "
            "2024-2028 horizon: • Loan book growth: 12-15% CAGR — diversifying "
            "away from real estate concentration • Digital revenue contribution: "
            "18% of total revenue by FY 2028 (currently 9%) • Cost-to-income "
            "ratio: 48% by FY 2027 (currently 53%) • ROE: 18% sustained from FY "
            "2026 — accepting compression in FY 2024-2025 transition years • "
            "CET1 ratio: maintain above 14% throughout, with explicit headroom "
            "for opportunistic acquisitions Strategic risks named The Board has "
            "explicitly named the risks the strategy carries. Real estate "
            "concentration drift remains the most material structural risk; the "
            "strategy assumes active management of the concentration trajectory "
            "rather than passive growth. Digital lending risk is the second "
            "material risk — unproven cohort dynamics could produce credit "
            "losses that compromise the digital revenue thesis. The third risk "
            "is execution capacity: the strategy assumes management bandwidth "
            "that may be tested in periods of sectoral stress. Review cadence "
            "This plan is reviewed annually. Material divergence from targets — "
            "defined as more than 200 basis points off path on any of the five "
            "targets — triggers a board-level strategic review session outside "
            "the annual cycle. The Q1 2026 results show provisioning "
            "compression to 68% (from 74% baseline) and real estate "
            "concentration at 31.2% (against the 25% internal guideline). The "
            "Risk Committee has been asked to assess whether these constitute "
            "material divergence."
        ),
    },
    {
        "id": "strat-bank-capital-framework",
        "title": "Strategic Capital Allocation Framework",
        "kind": "framework",
        "body": (
            "Mara Heritage Bank · Risk and Strategy · Q4 2025 · For Board Strategy "
            "Day · Confidential Purpose This paper sets out the framework for "
            "capital allocation across the bank's business lines for the FY26-28 "
            "horizon. It is intended to inform the Board Strategy Day discussion "
            "in November 2025 and to provide the framework against which "
            "subsequent quarterly capital decisions will be measured. Current "
            "capital position The bank's CET1 ratio at end-Q3 2025 stood at "
            "16.4%, providing approximately 2.4 percentage points of headroom "
            "against the internal floor of 14%. Total capital ratio of 19.1% "
            "sits comfortably above the 17% regulatory minimum plus capital "
            "conservation buffer. The headroom has been preserved despite a 4.2 "
            "percentage point rise in real estate concentration over the cycle, "
            "because risk-weighted assets have grown more slowly than the loan "
            "book due to mix shift. Strategic capital allocation principles "
            "Three principles govern capital deployment over the FY26-28 "
            "horizon: 1. Capital follows strategic priority, not historical "
            "share. Business lines that contribute to the FY28 strategic "
            "targets — diversified growth, digital revenue contribution, fee "
            "income — receive priority capital allocation regardless of "
            "historical earnings contribution. 2. Concentration risk is priced "
            "explicitly. The internal capital model loads incremental real "
            "estate exposure at 1.4× the standard sector weight. New corporate "
            "facilities in real estate must clear hurdle rates that reflect the "
            "loaded weight. 3. Reserve for opportunistic deployment. The "
            "framework reserves 100-150 basis points of CET1 headroom for "
            "opportunistic capital deployment — strategic acquisitions, market "
            "dislocation opportunities, or counter-cyclical book growth. "
            "Allocations by business line Corporate banking (current 62% of "
            "RWAs): hold or modestly grow. The franchise generates the cash "
            "flows that fund strategic transformation. Capital allocation is "
            "sufficient to maintain market position and selectively grow with "
            "target clients, but not to drive incremental concentration. SME "
            "banking (current 14% of RWAs): grow to 20-22% of RWAs by FY28. SME "
            "book growth is the primary mechanism for diversifying away from "
            "corporate concentration. The strategy assumes SME credit losses "
            "higher than corporate but offset by higher margin and lower "
            "concentration risk. Digital lending (current 6% of RWAs): grow to "
            "12-15% of RWAs by FY28, with explicit cohort-based capital "
            "reservation. The digital lending thesis carries unproven cohort "
            "dynamics; capital allocation increases as cohort performance is "
            "observed, with the option to slow or accelerate based on actual "
            "NPL trajectory. Treasury and trading (current 18% of RWAs): hold. "
            "Treasury operations are not strategic; they support the franchise "
            "without capital priority claim. Capital decision rights The "
            "framework establishes clear decision rights. Capital allocations "
            "within ±20% of business line targets are within management "
            "discretion, reported quarterly to Risk Committee. Allocations "
            "outside that range, or new business line capital deployments, "
            "require Board approval. Acquisitions or major balance sheet "
            "decisions require dedicated Board sessions. Connection to the "
            "strategic plan This framework operationalises the Strategic Plan "
            "2024-2028 capital strategy. The 14% CET1 floor is consistent with "
            "the Strategic Plan's commitment; the diversification trajectory "
            "across business lines is what produces the FY28 targets. Material "
            "deviation from this framework would constitute strategic plan "
            "deviation and would require explicit Board engagement."
        ),
    },
    {
        "id": "strat-bank-digital-refresh",
        "title": "Digital Transformation Strategy — Strategic Refresh",
        "kind": "strategy",
        "body": (
            "Mara Heritage Bank · Office of the CEO · Q1 2026 · For Board "
            "Discussion · Confidential Why this refresh The original Digital "
            "Transformation Strategy was approved in 2023 against a different "
            "sector context. Two years in, three things have changed materially. "
            "First, the digital lending portfolio has crossed the 9% NPL "
            "threshold, ahead of the cohort dynamics the original strategy "
            "anticipated. Second, peer banks have moved more aggressively on "
            "customer-side digital experience, narrowing the gap the original "
            "strategy assumed would persist. Third, the regulatory environment "
            "around digital credit has tightened, with CBK's recent supervisory "
            "updates raising the bar on digital lending governance. What is "
            "working The customer-facing digital channels have performed ahead "
            "of plan. Mobile transaction volumes are 2.4× the FY24 baseline; "
            "digital channel uptime has been 99.6% over the last twelve months; "
            "customer satisfaction scores on digital channels are at parity "
            "with the best peer in the market. The technology platform "
            "investment is producing the expected operational benefits: "
            "cost-to-serve on retail customers has fallen by 18%, branch "
            "traffic on routine transactions is down 31%. What is not working "
            "Digital lending NPL has emerged as the central concern. The "
            "original cohort model anticipated steady-state NPL of 6-7% for "
            "digital lending; actuals have crossed 9% in Q1 2026 and the "
            "trajectory is not yet stable. The CRO's current view is that the "
            "steady state may settle in the 8-11% range — within tolerance for "
            "a high-margin product, but well above the original assumption. "
            "The implications cascade: the digital revenue contribution target "
            "for FY28 (18% of total revenue) was modelled on the original NPL "
            "assumption; at the revised NPL, the same revenue contribution "
            "requires substantially more book growth, or a different product "
            "mix within digital lending. Strategic options for the refresh "
            "Three options are before the Board: 1. Maintain the FY28 digital "
            "revenue target, accept the higher NPL profile, increase capital "
            "allocation to digital lending to support faster book growth. "
            "Implication: higher near-term losses, FY28 target achievable on "
            "revised assumptions, but with more volatility in the digital "
            "book. 2. Reduce the FY28 digital revenue target to 14-15% from "
            "18%, recalibrate to the realistic NPL trajectory, redirect "
            "capital to other diversification levers. Implication: more "
            "conservative trajectory, lower volatility, but requires "
            "explanation in next investor communication and may compromise the "
            "bank's narrative on transformation pace. 3. Pivot the digital "
            "lending product mix away from unsecured consumer credit toward "
            "secured SME digital lending. Implication: smaller addressable "
            "market, slower book growth, but better risk profile and stronger "
            "alignment with the Strategic Plan's SME emphasis. CEO "
            "recommendation The CEO recommends Option 3, with the digital "
            "revenue target adjusted to 16% (between the original 18% and the "
            "conservative 14%). The recommendation rests on the judgement "
            "that the unsecured consumer digital lending thesis was a "
            "strategic error — the cohort dynamics were not adequately "
            "understood at the original strategy approval — and that pivoting "
            "now is preferable to defending the original choice. Board "
            "questions for discussion • Is the cohort model revision robust, "
            "or do we need an external review before committing to the "
            "strategic refresh? • What is the right communication to "
            "investors and CBK around the strategy refresh, and what is the "
            "timing? • Does Option 3's secured-SME pivot conflict with the "
            "SME banking strategy already approved, or does it reinforce it? "
            "• If we pivot, how do we manage the transition in the existing "
            "unsecured digital book without crystallising larger near-term "
            "losses?"
        ),
    },
]

# ═════════════════════════════════════════════════════════════════════════
#  HEALTHCARE — Lenana Health Group ×3
# ═════════════════════════════════════════════════════════════════════════
_HEALTHCARE_DOCS: List[Dict[str, Any]] = [
    {
        "id": "strat-health-preipo-plan",
        "title": "Pre-IPO Strategic Plan 2025-2028",
        "kind": "strategic_plan",
        "body": (
            "Lenana Health Group · Board endorsed January 2025 · Annual review · "
            "Confidential Strategic positioning Lenana Health Group is "
            "preparing for IPO in late 2027 against a regional healthcare "
            "market that is consolidating rapidly. The group's strategic "
            "positioning rests on three claims: the largest pan-East African "
            "private healthcare network, a clinical quality reputation built "
            "over fifteen years, and a payer-mix that demonstrates resilience "
            "across the region's economic cycles. The strategic plan's purpose "
            "is to navigate from current operational reality to IPO readiness "
            "while preserving — and where possible strengthening — these "
            "positioning claims. The IPO strategic objectives 1. Reach IPO "
            "with all six facilities operationally stable, including the "
            "Tanzania expansion. Operational stability means: clinical quality "
            "metrics within group historical baseline, EBITDA margins at "
            "facility maturity (16-18%), payer-mix consistent with group "
            "strategic profile. 2. Establish IPO-grade clinical governance "
            "documentation. Twenty-four months of consistent quality "
            "reporting, sentinel event tracking that meets disclosure "
            "requirements, clinical leadership credentials that survive "
            "prospectus review. 3. Position for post-IPO growth without "
            "commitment to specific acquisitions. The IPO narrative should "
            "establish capacity for continued regional expansion, but not "
            "pre-commit to specific deals that could constrain post-IPO "
            "flexibility. 4. Demonstrate management depth. Pre-IPO governance "
            "reviews consistently flag founder-CEO and small leadership team "
            "as IPO risk. The plan commits to two senior leadership additions "
            "before IPO filing. The Tanzania question The Tanzania facility "
            "is both the strategic plan's largest opportunity and its largest "
            "risk. The opportunity: Tanzania's healthcare market is "
            "underserved at the segment Lenana targets, and the facility's "
            "first-year performance suggests strong demand. The risk: "
            "clinical incident rates at 2.4× the group average, integration "
            "challenges that have run longer than anticipated, and a "
            "payer-mix that has evolved differently from plan. The strategic "
            "plan's commitment is to bring Tanzania to operational stability "
            "before IPO filing, with clinical quality as the binding "
            "constraint. If clinical metrics cannot be brought within group "
            "baseline by Q4 2026, the IPO timeline must shift — not the "
            "clinical commitment. This is an explicit Board commitment. "
            "Strategic targets • Bed capacity: 1,400 by FY 2028 (currently "
            "1,100) • Group EBITDA margin: 18% by FY 2027 (currently 14%, "
            "Tanzania drag) • Sentinel events: within group historical "
            "baseline (Q1 2026 above baseline) • IPO filing-ready: Q4 2027 "
            "(financial track on, clinical track at risk) The strategic "
            "question that needs Board review Q1 2026 has produced two "
            "pieces of evidence that warrant strategic plan review. "
            "Maternity unit sentinel events at the Nairobi flagship are "
            "running at three times the historical pattern; HR data shows "
            "the unit has been below the safety staffing threshold for two "
            "consecutive months. This is occurring at the flagship facility "
            "— not Tanzania — and suggests that the assumed clinical "
            "stability of mature facilities cannot be relied on as the IPO "
            "timeline approaches. The next Strategy Day should consider "
            "whether the strategic plan's binding constraint (clinical "
            "quality before IPO) requires more aggressive operational "
            "interventions across the group, not just Tanzania."
        ),
    },
    {
        "id": "strat-health-geographic-expansion",
        "title": "Geographic Expansion Strategy — Tanzania Integration Review",
        "kind": "strategy",
        "body": (
            "Lenana Health Group · COO Office · Q1 2026 · For Board Strategic "
            "Discussion Why this review The Tanzania facility opened in "
            "February 2025. Fourteen months in, the integration has produced "
            "both stronger-than-plan operational performance and "
            "weaker-than-plan clinical performance. This review presents the "
            "integration evidence, identifies the strategic question, and "
            "recommends a path forward. What the evidence shows Operational "
            "metrics ahead of plan. Bed occupancy at 72% (against 60% Year-1 "
            "plan). Outpatient volumes at 1.4× plan. Insurance contracts "
            "secured with the three largest local insurers within twelve "
            "months (plan was eighteen). Revenue per occupied bed-day at 88% "
            "of group average (plan was 75%). The market thesis is "
            "validated. Clinical metrics behind plan. Sentinel event rate at "
            "2.4× group average. Patient satisfaction scores at 78% (group "
            "average 89%). Senior clinical staff turnover in the first year "
            "at 22% (group average 11%). The clinical integration thesis is "
            "not yet validated. The strategic question Three diagnoses are "
            "possible. The first: this is normal new-facility teething; the "
            "convergence pattern from peer regional groups suggests 18-24 "
            "months to clinical baseline. Under this diagnosis, the "
            "trajectory is acceptable and the IPO timeline can hold. The "
            "second: this reflects a specific structural mismatch between "
            "Lenana's operating model and Tanzania's clinical workforce "
            "environment; without targeted interventions, the convergence "
            "will not happen. Under this diagnosis, the timeline can hold "
            "only if specific interventions are committed and executed. The "
            "third: the original integration thesis underestimated the "
            "cultural and operational complexity of Tanzania's healthcare "
            "environment; the convergence is not assured even with "
            "interventions; the IPO timeline must absorb this uncertainty. "
            "Recommendation The COO recommends treating the situation as "
            "Diagnosis 2 — structural mismatch requiring targeted "
            "intervention — while preserving Diagnosis 3 as the explicit "
            "fallback if interventions do not produce convergence by Q4 "
            "2026. Specific interventions recommended: 1. Senior clinical "
            "leadership rotation. Two senior physicians from the Nairobi "
            "flagship to spend 12-month rotations in Tanzania, embedding "
            "clinical protocols and mentoring local senior staff. 2. "
            "Clinical governance committee at facility level. Currently "
            "Tanzania reports up to group; the recommendation is for a "
            "Tanzania-level clinical governance committee that meets weekly "
            "with senior clinical and operational leadership. 3. "
            "Recruitment investment. Doubling the recruitment budget for "
            "senior clinical positions in Tanzania for FY 2026, with "
            "mandate to recruit from outside East Africa where local "
            "pipeline is thin. 4. Clinical integration consultant. External "
            "consultancy with proven track record in cross-border hospital "
            "integration, six-month engagement with explicit deliverables. "
            "Cost and timeline Total intervention investment: approximately "
            "KES 280 million over twelve months. Funding from the Tanzania "
            "facility's stronger-than-plan revenue performance — does not "
            "require capital reallocation from other facilities. "
            "Convergence to group clinical baseline targeted by Q1 2027, "
            "six months ahead of IPO filing window. Decision sought Board "
            "endorsement of the intervention plan. Explicit Board "
            "acknowledgment that if clinical convergence is not on track by "
            "Q4 2026 mid-point review, the IPO timeline must shift — not "
            "the clinical commitment. This is the binding constraint of the "
            "Pre-IPO Strategic Plan."
        ),
    },
    {
        "id": "strat-health-clinical-excellence",
        "title": "Clinical Excellence Strategy 2025-2028",
        "kind": "strategy",
        "body": (
            "Lenana Health Group · CMO Office · Endorsed by Quality Committee "
            "· Confidential The strategic premise Clinical excellence is "
            "Lenana's foundational competitive position. The group's IPO "
            "narrative, payer relationships, and pricing power all rest on a "
            "clinical quality reputation built over fifteen years. The "
            "Clinical Excellence Strategy 2025-2028 is the framework for "
            "preserving this position through a period of geographic "
            "expansion, operational scale-up, and IPO transition — periods "
            "that historically have produced clinical quality regression in "
            "peer organisations. The four pillars First, never-events at "
            "zero. The strategy commits to maintaining Lenana's never-event "
            "rate at zero across all facilities. This is the binding clinical "
            "commitment. Any never-event triggers an immediate root-cause "
            "analysis and a CMO report direct to the Quality Committee "
            "within seventy-two hours. Second, sentinel events within "
            "historical baseline. Group historical sentinel event rate is "
            "0.42 per 1,000 admissions. The strategy commits to maintaining "
            "the rate within the 0.35-0.50 band across the group, with "
            "explicit accountability when any individual facility moves "
            "outside this band for two consecutive quarters. Third, clinical "
            "leadership depth. Each facility maintains at least three senior "
            "clinical leaders with five-plus years of Lenana experience. "
            "This is a hard constraint on facility opening — no new facility "
            "opens without senior leadership depth in place. Fourth, "
            "transparent quality reporting. Internal quality reports are "
            "published group-wide quarterly. External quality reports — "
            "covering metrics that meet IPO disclosure standards — published "
            "bi-annually beginning FY 2026. The strategic question this "
            "raises for Q1 2026 The Q1 2026 quality data shows three "
            "sentinel events in the maternity unit at the Nairobi flagship "
            "— bringing the flagship's quarterly sentinel event rate to "
            "0.81, materially above the strategic band. The CMO's clinical "
            "review attributes the increase to case-mix complexity, but the "
            "HR data on staffing below safety threshold for two consecutive "
            "months suggests a structural rather than coincidental cause. "
            "The Clinical Excellence Strategy commits to specific "
            "accountability when a facility moves outside the band for two "
            "consecutive quarters. Q1 2026 is the first quarter; Q2 will "
            "determine whether the framework's accountability provisions "
            "trigger. The Quality Committee has been asked to review "
            "whether the existing strategy framework is adequate to the "
            "operational reality, or whether a strategic refresh is "
            "required ahead of IPO. Strategic options if Q2 confirms the "
            "trend 1. Treat the sentinel event rise as a flagship-specific "
            "operational issue, addressable through staffing intervention "
            "without strategic plan revision. 2. Treat it as a leading "
            "indicator of group-wide pressure as IPO approaches, requiring "
            "strategy refresh that strengthens the cross-facility clinical "
            "governance framework. 3. Treat it as evidence that the IPO "
            "timeline is producing operational pressure that compromises "
            "clinical excellence, and recommend timeline adjustment to the "
            "Strategic Plan. CMO position The CMO's preliminary view is "
            "that the situation is closer to Diagnosis 2 than to either "
            "alternative. The strategic plan committed to clinical "
            "excellence as a binding constraint, and the operational "
            "pressure that produces these outcomes is foreseeable as IPO "
            "approaches. A strategy refresh that anticipates IPO-period "
            "clinical pressure — and commits resources before the pressure "
            "produces measurable harm — is the path that honours the "
            "original strategic commitment."
        ),
    },
]

# ═════════════════════════════════════════════════════════════════════════
#  LOGISTICS — Korogocho Logistics Group ×3
# ═════════════════════════════════════════════════════════════════════════
_LOGISTICS_DOCS: List[Dict[str, Any]] = [
    {
        "id": "strat-logistics-preipo-plan",
        "title": "Pre-IPO Strategic Plan — Path to Listing",
        "kind": "strategic_plan",
        "body": (
            "Korogocho Logistics Group · Board approved March 2025 · "
            "Confidential The IPO context Korogocho Logistics Group plans to "
            "list on the Nairobi Securities Exchange in H2 2026, with "
            "potential dual listing on the Johannesburg Stock Exchange in H2 "
            "2027. The IPO is the foundational event for the next strategic "
            "period — it provides the capital for continued pan-African "
            "expansion, the governance framework that serves a "
            "publicly-listed regional logistics company, and the market "
            "validation for Korogocho's strategic position. The IPO is also "
            "a binding constraint. The decisions made in the eighteen "
            "months before listing — on succession, on market portfolio, on "
            "capital structure, on governance — must serve both pre-IPO and "
            "post-IPO realities. Mistakes made in this window are difficult "
            "to unwind. The four strategic pillars to listing 1. "
            "Founder-CEO succession in execution. The single most-cited "
            "governance gap in pre-IPO reviews. The Nominations Committee's "
            "preliminary Path C recommendation — founder transitions to "
            "Executive Chairman 18 months pre-IPO with internal CEO "
            "successor — must be executed, not just recommended. 2. Market "
            "portfolio rationalisation. Five markets generating different "
            "margin profiles, different operational complexity, different "
            "growth trajectories. The IPO narrative requires a coherent "
            "portfolio story, not a list of markets. The strategic plan "
            "endorses retention of all five markets but commits to "
            "operational standardisation that produces unified financial "
            "reporting. 3. Cross-border tax position resolution. Three live "
            "disputes (Tanzania, Uganda, DRC) cannot be carried into IPO "
            "disclosure unresolved. The strategic plan commits to "
            "resolution or to clear disclosure framework on each before "
            "prospectus drafting begins in Q3 2026. 4. Operational "
            "standardisation. Fleet utilisation ranges from 67% to 89% "
            "across markets. The IPO prospectus must explain this either as "
            "strategic differentiation (DRC margin premium offsetting lower "
            "utilisation) or as operational gap. The strategic plan commits "
            "to operational reviews in each market with the goal of "
            "bringing utilisation variance within a defensible band. "
            "Strategic targets to FY 2028 • Revenue: KES 26 billion (FY "
            "2025: KES 17.8 billion) • EBITDA margin: 14% sustained (FY "
            "2025: 11.2%) • Cross-border revenue mix: 50% (currently 38%) "
            "• Fleet expansion: 1,200 trucks (currently 820) • ROIC: 16% "
            "sustained post-IPO The strategic risks named • Founder-CEO "
            "succession execution. The risk is not the choice of path — "
            "Path C is supported. The risk is execution timeline. • DRC "
            "operating environment. Political volatility, regulatory "
            "uncertainty, FX exposure. The strategic plan endorses "
            "retention but commits to specific exit triggers if conditions "
            "deteriorate. • Cross-border tax escalation. The current "
            "disputes are being managed. New disputes from changed "
            "enforcement patterns in any market could materially shift the "
            "IPO disclosure profile. • IPO market window. Pan-African "
            "logistics IPOs have a narrow window. Timing risk is real but "
            "the strategic plan does not advocate accelerating to capture "
            "it."
        ),
    },
    {
        "id": "strat-logistics-succession-framework",
        "title": "Founder-CEO Succession Framework",
        "kind": "framework",
        "body": (
            "Korogocho Logistics Group · Nominations Committee · Q1 2026 · "
            "Confidential The succession decision Founder-CEO James "
            "Korogocho has led the company for fifteen years from inception "
            "to its current scale. The Nominations Committee, in "
            "consultation with the Board Chair and the Founder, has been "
            "working through succession scenarios over the last twelve "
            "months. This framework presents the Committee's preferred path "
            "and the rationale. Path C — the preferred path The Founder "
            "transitions from Group CEO to Executive Chairman 18 months "
            "before the planned IPO listing date. An internal CEO successor "
            "— currently the Chief Operating Officer, who has been with the "
            "group for nine years — is appointed simultaneously. The "
            "Founder remains in an Executive Chairman role through IPO and "
            "for two years post-listing, then transitions to Non-Executive "
            "Chairman. The rationale rests on four judgements. First, "
            "regional pre-IPO governance evidence supports clear succession "
            "in place 18-24 months pre-listing; valuation discounts of "
            "8-15% have been observed for companies that list with "
            "founder-CEO ambiguity. Second, the COO has demonstrated the "
            "operational and strategic capacity required, and is known to "
            "the Board, the management team, and to key external "
            "relationships. Third, an external CEO recruitment would "
            "introduce execution risk in the IPO window — risk that "
            "exceeds the cost of internal continuity. Fourth, the "
            "Founder's continued presence as Executive Chairman through "
            "IPO preserves the relationships and credibility that have "
            "been built over fifteen years. The Founder's view The Founder "
            "has been actively involved in the framework development and "
            "supports the Path C recommendation. His specific commitments: "
            "full delegation of operational and strategic decision-making "
            "to the new CEO from transition date; explicit role boundaries "
            "between Executive Chairman and CEO that respect the CEO's "
            "authority; transition support to the new CEO that includes "
            "joint client and investor engagements but does not extend to "
            "overriding CEO decisions. These commitments will be "
            "documented in the formal transition plan. The successor The "
            "COO has accepted the succession nomination subject to Board "
            "endorsement. His own commitments: continued investment in his "
            "own development as CEO-of-a-listed-company specifically "
            "(Board observership at a peer listed company, executive "
            "coaching engagement, structured time with current Chairs of "
            "listed companies in the region). The COO's existing strategic "
            "alignment with the Founder reduces the strategy-discontinuity "
            "risk that is typical in succession transitions. The "
            "governance commitments The Board commits to specific "
            "governance standards through the transition. Quarterly Board "
            "reviews of transition execution against the documented plan. "
            "Independent NED point-of-contact for the new CEO outside the "
            "Founder relationship. External pre-IPO governance review at "
            "the six-month mark to validate transition health from an "
            "external perspective. Right-of-recourse for the new CEO to "
            "escalate role-boundary concerns directly to the Chair of the "
            "Nominations Committee. Risks named • Founder role discipline "
            "post-transition. The Founder's commitment is explicit; the "
            "risk is its execution under operational pressure. • CEO "
            "development gap. The COO has demonstrated operational "
            "capacity but has not led a listed company; the development "
            "plan addresses this gap but cannot eliminate it. • External "
            "relationship continuity. Some key client and investor "
            "relationships are personal to the Founder; the transition "
            "plan must actively transfer these without disruption. • "
            "Talent retention through transition. Senior management may "
            "interpret the succession as a signal to consider their own "
            "next moves; the framework must include explicit retention "
            "dialogue with the senior team. Decision sought Board "
            "endorsement of Path C, the Founder's commitments, the COO's "
            "nomination and development plan, and the governance "
            "commitments. Recommended Board decision in Q2 2026, "
            "transition execution to begin Q3 2026, completion at the IPO "
            "listing date."
        ),
    },
    {
        "id": "strat-logistics-market-portfolio",
        "title": "Market Portfolio Strategy",
        "kind": "strategy",
        "body": (
            "Korogocho Logistics Group · CCO Office · Q4 2025 · Strategy Day "
            "Material · Confidential The portfolio question Korogocho "
            "operates in five markets — Kenya, Uganda, Tanzania, Rwanda, "
            "DRC — that produce different margin profiles, different "
            "operational complexity, different regulatory environments. The "
            "IPO prospectus will require a coherent narrative on portfolio "
            "strategy. This paper presents the strategy and the trade-offs. "
            "The five markets, structurally Kenya — home market, anchor "
            "revenues, mature operations. Fleet utilisation 89%. EBITDA "
            "margin 11%. Strategic role: cash flow stability and "
            "credibility anchor. Uganda — adjacent market, mature "
            "operations. Utilisation 82%. EBITDA margin 13%. Strategic "
            "role: regional integration with Kenya, hub for East African "
            "Community trade. Tanzania — secondary regional market, mature "
            "operations, ongoing tax dispute. Utilisation 78%. EBITDA "
            "margin 12%. Strategic role: regional completeness, southern "
            "African gateway potential. Rwanda — strategic frontier, "
            "smaller scale, strong operating environment. Utilisation 84%. "
            "EBITDA margin 15%. Strategic role: best-margin market per "
            "truck, foundation for further expansion into Burundi and "
            "eastern DRC. DRC — highest-margin, highest-risk market. "
            "Utilisation 67%. EBITDA margin 22%. Strategic role: margin "
            "premium supports group EBITDA, but structural risk from "
            "political volatility, regulatory uncertainty, FX exposure. "
            "Strategic options for the portfolio 1. Hold all five markets, "
            "pursue operational standardisation. Preserves the pan-African "
            "positioning. Accepts utilisation variance as strategic "
            "differentiation. Requires explicit prospectus narrative on "
            "DRC risk. 2. Reduce DRC exposure, focus capital on Rwanda "
            "and Uganda expansion. Reduces structural risk but compromises "
            "the pan-African narrative and removes the EBITDA margin "
            "premium. 3. Aggressive DRC expansion. Doubles down on the "
            "margin premium. Increases structural risk, requires capital "
            "that competes with Rwanda expansion, and would draw analyst "
            "attention to DRC concentration. CCO recommendation Option 1 "
            "— hold all five markets, pursue operational standardisation. "
            "The pan-African positioning is the IPO's foundational story; "
            "reducing DRC undermines it without producing a sufficiently "
            "better risk profile to justify the trade-off. Aggressive DRC "
            "expansion adds operational risk in the IPO window and would "
            "shift the prospectus narrative away from disciplined regional "
            "logistics to opportunistic emerging-market exposure. The "
            "operational standardisation commitment Holding all five "
            "markets requires a credible operational standardisation "
            "programme. The plan commits to: • Common fleet management "
            "platform across all markets by Q4 2026 • Common financial "
            "reporting standard at facility level, with monthly close "
            "cycles aligned by Q3 2026 • Common safety and operational "
            "compliance standards, audited group-wide quarterly • Group "
            "operating committee with country leads, meeting monthly, with "
            "explicit standardisation accountability The DRC commitment "
            "Holding the DRC position requires explicit risk-management "
            "commitments. The plan commits to: • Quarterly DRC "
            "operating-environment review at Risk Committee with explicit "
            "exit-trigger framework • FX exposure hedging for DRC revenues "
            "at minimum 60% on a rolling six-month basis • Regulatory "
            "engagement programme with DRC counterparts that maintains "
            "current operating status • Capital deployment cap on DRC at "
            "current levels until prospectus disclosure is finalised The "
            "IPO disclosure framework Prospectus disclosure on the "
            "portfolio will present three views: group consolidated, "
            "segmented by market, and segmented by operating environment "
            "risk profile (mature vs frontier). All three views will be "
            "presented because analysts will reconstruct them; pretending "
            "the consolidated number is the story will be detected. The "
            "strategic narrative will explain the portfolio as deliberate "
            "disciplined regional logistics, not opportunistic "
            "emerging-market exposure."
        ),
    },
]

# ═════════════════════════════════════════════════════════════════════════
#  TECHNOLOGY — Tahidi Systems ×2
# ═════════════════════════════════════════════════════════════════════════
_TECHNOLOGY_DOCS: List[Dict[str, Any]] = [
    {
        "id": "strat-tech-series-a-thesis",
        "title": "Series A Investment Thesis — Original Founding Document",
        "kind": "investment_thesis",
        "body": (
            "Tahidi Systems · For Series A close August 2025 · Original founder "
            "document · Preserved as strategic reference The market opportunity "
            "Tahidi Systems addresses an underserved segment in African "
            "mid-market: wholesale and distribution businesses operating "
            "between $5M and $100M in annual revenue who manage their "
            "inventory, accounts, and customer relationships through a "
            "combination of WhatsApp, Excel, and accounting software designed "
            "for retailers. The segment is approximately 4,500 businesses "
            "across the three target markets (Kenya, Nigeria, South Africa), "
            "with addressable software spend per business of $8,000-25,000 "
            "annually. Total addressable market: approximately $80 million "
            "annually. The product thesis Wholesalers and distributors are a "
            "coherent buyer segment with shared operational patterns — "
            "multi-product inventory, B2B customer credit relationships, "
            "route-based sales operations, regional pricing complexity. "
            "Generic ERP and CRM products serve them poorly; retail-focused "
            "products miss the wholesale dynamics; manufacturer-focused "
            "products miss the distribution complexity. A vertical-focused "
            "product designed for this segment can capture the segment "
            "within a defined window before generic products mature their "
            "wholesale-distributor offerings. The market entry strategy "
            "Series A funding ($12M) supports execution against four "
            "specific commitments: 200 paying customers by month 18, ARR of "
            "$9.5M by FY26 (Year 2 post-Series A), expansion into a fourth "
            "market by month 24, and Series B readiness by Q3 2026 with NRR "
            "above 120% sustained. The thesis assumes that the "
            "wholesale-distribution segment, once captured, has high "
            "retention and strong expansion characteristics — wholesalers "
            "grow into distributors, distributors expand product lines, "
            "both expand geographically. The competitive thesis Three "
            "competitive risks are named in the original thesis. First, "
            "large global ERP players (SAP, Oracle, NetSuite) extending "
            "downmarket. Mitigation: pricing structure and implementation "
            "simplicity that those products cannot match. Second, generic "
            "regional B2B SaaS players adding wholesale-distribution "
            "modules. Mitigation: vertical depth and customer references "
            "that generic players cannot match. Third, locally-funded "
            "competitors with similar vertical focus. Mitigation: speed of "
            "market capture and the vertical-network effects of being the "
            "embedded system. Key assumptions documented • Customer "
            "concentration risk manageable: no customer above 8% of ARR "
            "after Year 1 • CAC steady-state: $9,000 fully loaded, with "
            "payback period of 14 months • NRR sustained at 118-125% "
            "through expansion ARR within existing customers • Gross "
            "margin: 78% sustained at scale • Series B at Q3 2026 with "
            "$20-30M raise at 5-7× ARR multiple The honest framing This "
            "thesis was approved by the Board in August 2025. It is "
            "preserved as the foundational strategic reference because the "
            "Board recognises that the thesis itself — including its "
            "assumptions and its competitive logic — must be evaluated "
            "honestly as the company encounters reality. Strategic reviews "
            "against this thesis are scheduled at six-month intervals. "
            "Material divergence from the documented assumptions triggers "
            "a board-level strategic discussion, not a quiet target "
            "adjustment."
        ),
    },
    {
        "id": "strat-tech-series-b-positioning",
        "title": "Series B Strategic Positioning Paper",
        "kind": "strategy",
        "body": (
            "Tahidi Systems · Founder Office · April 2026 · For Series A "
            "investor consultation · Highly Confidential Why this paper now "
            "The Series A investment thesis was approved in August 2025. "
            "Twenty months in, Tahidi has not converged with the thesis on "
            "three of its five documented assumptions. TechBridge — at 11% "
            "of ARR — churned in November 2025, breaking the customer "
            "concentration assumption. CAC has risen from $8K to $14K, "
            "breaking the CAC assumption. NRR has compressed from 118% to "
            "102%, breaking the NRR assumption. Series A investors have "
            "requested strategic options paper before the next board "
            "meeting. This paper is the founder's honest framing — not the "
            "version that preserves the original narrative. What's "
            "actually true First, the wholesale-distribution market "
            "opportunity remains real. The 4,500-business addressable "
            "market estimate has been validated; the willingness-to-pay "
            "assumption has been validated; the segment's coherence as a "
            "buyer audience has been validated. The market thesis is "
            "intact. Second, Tahidi's product is genuinely better-fit than "
            "alternatives for the segment. Customer satisfaction scores, "
            "gross retention numbers (excluding TechBridge), and expansion "
            "within retained customers all support the product thesis. "
            "Third, the go-to-market motion is broken. The CAC inflation "
            "reflects a sales process designed for the early-customer "
            "profile that has not adapted as the company moved beyond the "
            "first 50 customers. The NRR compression reflects expansion "
            "ARR motion that depends too heavily on individual sales "
            "relationships that did not transfer when sales personnel "
            "transitioned. Fourth, the customer concentration risk was "
            "understated. TechBridge was the lighthouse customer that "
            "defined the Series A pitch; losing them was foreseeable as a "
            "structural risk and was not adequately hedged. Three options "
            "for Series B 1. Maintain growth thesis, accept Series B as "
            "bridge round at lower valuation, focus on NRR recovery. The "
            "original story, recalibrated. Targets: $9.5M ARR by FY26, NRR "
            "back to 110%+ by Q4 2026, Series B at $4-5× ARR multiple. "
            "Implication: investors who supported the original thesis can "
            "support the recalibration; new investors will discount. "
            "Required raise: $15-18M to reach Series C economics. 2. Pivot "
            "to product-led growth motion to reduce CAC, defer Series B "
            "by 6-9 months, accept slower top-line. The honest story, "
            "larger restructure. Targets: rebuild CAC to $9K, accept ARR "
            "growth at 30-40% rather than 60%+, raise Series B in late "
            "2026 at improved unit economics. Implication: requires harder "
            "operational changes — sales reorganisation, product changes "
            "for self-serve, channel partnerships. Required raise: $12-15M "
            "with more runway. 3. Strategic conversation with two known "
            "acquirers in the space. Acqui-hire framing at floor of "
            "pre-money. Implication: Series A investors recover 1.0-1.5× "
            "return, founders and team have continuity, original thesis "
            "is closed. This is the option no one wants to be the first "
            "to name; the founder believes it must be on the table for "
            "the Board's evaluation to be honest. The founder's view The "
            "founder believes Option 2 is the right path — the unit "
            "economics fix is foundational; trying to grow through them "
            "is the strategic error that converts a recoverable situation "
            "into an unrecoverable one. Option 1's framing depends on NRR "
            "recovery within two quarters, and the founder cannot "
            "honestly model the cohort dynamics that produce that "
            "recovery without assumptions the data does not support. "
            "Option 3 is the explicit fallback if Series A investors "
            "cannot align on Option 2's slower trajectory. What the "
            "founder is asking the Board First, honest evaluation of all "
            "three options on their merits — not a return to the Option "
            "1 narrative because it is the most comfortable. Second, "
            "alignment on the binding constraint: the question is not "
            "which option preserves the original thesis (none do fully), "
            "but which option produces the best outcome for Tahidi's "
            "customers, team, and investors given current reality. Third, "
            "governance commitment that the option chosen will be "
            "explained to all stakeholders honestly — no quiet target "
            "adjustment, no narrative gymnastics, no presenting Option 1 "
            "as if the original assumptions were intact. What this paper "
            "does not yet do This paper does not contain the operational "
            "plan for Option 2. The founder has chosen to bring the "
            "strategic question to the Board first, before committing to "
            "operational detail that would prejudice Board deliberation. "
            "If the Board endorses Option 2 in principle, the operational "
            "plan — sales reorganisation, product changes, channel "
            "strategy — will be developed and brought back within thirty "
            "days."
        ),
    },
]

# ═════════════════════════════════════════════════════════════════════════
#  GOVERNMENT — Ministry of Industrial Modernisation ×3
# ═════════════════════════════════════════════════════════════════════════
_GOVERNMENT_DOCS: List[Dict[str, Any]] = [
    {
        "id": "strat-gov-sector-plan-2024-2029",
        "title": "Sector Strategic Plan 2024-2029 — Industrial Modernisation",
        "kind": "strategic_plan",
        "body": (
            "Ministry of Industrial Modernisation · Sessional Paper No. X of "
            "2024 · Cabinet endorsed · Public The sector context Kenya's "
            "industrial sector contributes approximately 7.4% of GDP, "
            "against the 14% target set in the Vision 2030 framework and "
            "reaffirmed in the Bottom-Up Economic Transformation Agenda. "
            "The gap — and the trajectory toward closing it — is the "
            "central strategic question the Ministry exists to address. "
            "The Sector Strategic Plan 2024-2029 is the framework for the "
            "current planning cycle. The strategic objectives 1. Increase "
            "industrial sector contribution to GDP from 7.4% to 11% by FY "
            "2029 — a trajectory that puts the 14% Vision 2030 target "
            "within reach in subsequent planning cycles. 2. Triple "
            "manufactured exports from $480 million annually to $1.5 "
            "billion by FY 2029, with explicit emphasis on "
            "agro-processing, light manufacturing, and pharmaceutical "
            "sectors aligned with regional and continental free trade "
            "frameworks. 3. Establish six county-anchored industrial "
            "parks under the Industrial Modernisation Programme, with "
            "measurable employment, output, and regional economic linkage "
            "outcomes by FY 2029. 4. Integrate the industrial sector into "
            "the regional economic architecture — EAC, COMESA, AfCFTA — "
            "through coordinated trade facilitation, standards "
            "harmonisation, and infrastructure investment. The strategic "
            "interventions Four interventions form the backbone of the "
            "strategy. The flagship Industrial Modernisation Programme — "
            "county-anchored industrial parks with infrastructure, "
            "finance, capacity-building components. The Manufacturing "
            "Competitiveness Initiative — addressing energy costs, "
            "regulatory burden, and workforce skills. The Trade "
            "Facilitation Programme — coordinated with KRA, KEBS, and "
            "counterparty agencies in trading partner countries. The "
            "Pharmaceutical Manufacturing Strategy — leveraging the "
            "policy window opened by AfCFTA. The fiscal envelope The "
            "strategic plan was costed at approximately KES 24 billion "
            "across the five-year period, with funding from a combination "
            "of national appropriation (60%), donor partnerships (28%), "
            "and private sector co-investment (12%). The fiscal envelope "
            "was developed in coordination with Treasury under the "
            "FY24-25 Budget Policy Statement framework. The strategic "
            "risks Four risks were named at strategic plan endorsement. "
            "Fiscal consolidation risk — that macro-fiscal pressures "
            "would compress the appropriation envelope. This risk has "
            "materialised: the FY26-27 ceiling is below the strategic "
            "plan trajectory. County implementation capacity risk — that "
            "variation across counties would compromise programme "
            "outcomes. This risk has materialised: eleven of seventeen "
            "counties are below target. Donor commitment realignment "
            "risk — that donor priorities would shift away from "
            "industrial development. This risk is partially materialising. "
            "Political continuity risk — that strategic direction would "
            "shift with electoral cycles. This risk remains latent. The "
            "strategic question for Q1 2026 The strategic plan's "
            "underlying theory rests on a coherent partnership between "
            "national appropriation, donor co-funding, and county "
            "implementation. Q1 2026 evidence is that all three "
            "components are stressed simultaneously. The Cabinet Memo "
            "currently in preparation will need to address whether the "
            "strategic plan's targets remain achievable on the original "
            "trajectory, whether they require recalibration, or whether "
            "the underlying theory needs more fundamental review. The "
            "Ministry's preliminary assessment is that recalibration is "
            "required; theory revision is not yet warranted but should "
            "be on the agenda for the Q2 2027 mid-term review."
        ),
    },
    {
        "id": "strat-gov-imp-theory-of-change",
        "title": "Industrial Modernisation Programme — Theory of Change",
        "kind": "theory_of_change",
        "body": (
            "Ministry of Industrial Modernisation · Programme Design "
            "Document 2024 · Confidential The programme premise The "
            "Industrial Modernisation Programme is designed to address "
            "Kenya's industrial sector underperformance through "
            "county-anchored interventions that combine infrastructure, "
            "finance, and capacity-building. The programme's theory of "
            "change is that industrial development cannot be driven from "
            "the centre alone — it requires county-level execution with "
            "national coordination — and that the right combination of "
            "investments, sequenced correctly, can produce industrial "
            "cluster effects in counties with appropriate underlying "
            "conditions. The theory of change explicitly stated If the "
            "Programme provides infrastructure (industrial park land, "
            "utilities, road access), finance (grants and concessional "
            "loans for SME industrial investment), and capacity-building "
            "(workforce skills, business development services, regulatory "
            "navigation) at appropriate scale to seventeen target "
            "counties, then those counties will attract industrial "
            "investment, the investment will produce employment and "
            "output growth, the growth will generate regional economic "
            "linkages, and the linkages will produce the cluster effects "
            "that sustain industrial sector contribution to GDP. The "
            "assumptions the theory rests on 1. Counties have the "
            "institutional capacity to deploy programme resources "
            "effectively. This assumption was made at programme design "
            "without rigorous baseline assessment of county industrial "
            "development unit capacity. 2. Conditional grant disbursement "
            "from Treasury operates on timelines compatible with county "
            "execution windows. This assumption was made before the "
            "macro-fiscal consolidation programme that has tightened "
            "disbursement cycles. 3. Industrial investment responds to "
            "programme incentives at the assumed elasticities. The "
            "programme design used elasticities calibrated to Kenya's "
            "2014-2018 industrial growth period; subsequent macro "
            "conditions have not been comparable. 4. Counties below "
            "initial baseline will catch up to leading counties through "
            "programme participation. The assumption was that the "
            "programme would be a convergence mechanism. What the Q1 2026 "
            "evidence shows about each assumption The convergence "
            "assumption (#4) is failing. Three counties have moved well "
            "above target (Kiambu, Machakos, Nakuru); three are at "
            "target (Kisumu, Mombasa, Nyeri); eleven are below target. "
            "The variation has widened over four quarters, not narrowed "
            "as the convergence theory anticipated. The Directorate of "
            "County Coordination has flagged that the variation "
            "correlates strongly with pre-existing county industrial "
            "development unit capacity — meaning the programme is "
            "amplifying initial differences rather than producing "
            "convergence. The disbursement assumption (#2) is partially "
            "failing. Treasury has consistently disbursed conditional "
            "grants, but the timing patterns have compressed county "
            "execution windows below what programme design anticipated. "
            "The strongest-performing counties have been able to "
            "compensate with bridge financing or accelerated "
            "procurement; weaker-performing counties have not. The "
            "investment elasticity assumption (#3) is uncertain. The "
            "four leading counties have attracted industrial investment "
            "at rates close to design expectations; the eleven "
            "below-target counties have not, but it is not yet clear "
            "whether this reflects a different elasticity or simply that "
            "the programme inputs have not yet reached threshold scale "
            "in those counties. The strategic implication The Q1 2026 "
            "evidence suggests that the theory of change requires "
            "revision. The convergence assumption — that programme "
            "participation alone would produce catch-up — is not "
            "supported by the data. A revised theory might frame the "
            "programme as a sequenced intervention: first, baseline "
            "county capacity must reach a threshold; only then will the "
            "programme's infrastructure and finance components produce "
            "the assumed cluster effects. This revised theory would "
            "imply that counties below threshold need a different "
            "intervention sequence than counties at or above threshold. "
            "The Ministry has not yet committed to theory revision. The "
            "Cabinet Memo currently in preparation is operational rather "
            "than theoretical — addressing the FY26-27 fiscal envelope "
            "and the donor partnership question — but the Mid-Term "
            "Review scheduled for Q2 2027 will require explicit position "
            "on whether the original theory of change is to be "
            "preserved, revised, or replaced. The Memo should at minimum "
            "signal that this question is under formal review."
        ),
    },
    {
        "id": "strat-gov-political-economy-q1-2026",
        "title": "Political-Economy Assessment — Industrial Modernisation Q1 2026",
        "kind": "political_economy",
        "body": (
            "Ministry of Industrial Modernisation · Office of the PS · "
            "Policy Briefing · Restricted Distribution Why this assessment "
            "Cabinet Memos and Treasury submissions present technical "
            "positions on programme performance. They do not — by "
            "convention or design — address the political-economy context "
            "within which those technical positions will be received. This "
            "briefing supplements the technical materials with the "
            "political-economy assessment that the PS judges the CS should "
            "consider before finalising the position taken into Cabinet. "
            "The political-economy context Three political-economy factors "
            "bear materially on the strategic decisions before the "
            "Ministry. First, the National Assembly Committee on "
            "Industrialisation has shifted its questioning pattern from "
            "programme design to implementation accountability. The shift "
            "reflects the broader Parliamentary cycle — Departmental "
            "Committees in this Parliament have moved from ex-ante review "
            "toward ex-post accountability, particularly on flagship "
            "programmes that have been running for two or more reporting "
            "cycles. The Committee Chair has signalled in informal "
            "discussion that the next hearing will focus specifically on "
            "the eleven below-target counties, with named questions on "
            "what the Ministry has done and is committed to doing. "
            "Second, the Council of Governors has been increasingly "
            "active on intergovernmental fiscal questions. The compressed "
            "conditional grant disbursement cycles have produced explicit "
            "governor-level concerns; the Council has tabled the "
            "question at three consecutive Intergovernmental Budget and "
            "Economic Council meetings. The political costs of being "
            "identified by the Council as the Ministry that disadvantages "
            "counties through grant timing patterns are real, even where "
            "the timing is structurally driven by Treasury. Third, the "
            "donor partnership relationships are entering a delicate "
            "period. The mid-term review's recommendations — including "
            "the recommended scaling envelope above the Treasury ceiling "
            "— are not just technical recommendations; they reflect the "
            "donor's strategic positioning on the partnership. Acceptance, "
            "partial acceptance, or rejection of the recommendations will "
            "signal Government's posture toward the partnership for the "
            "FY26-28 cycle. The donor has explicitly noted that other "
            "African government partners are watching how Kenya responds. "
            "How the political-economy bears on the technical decisions "
            "The Cabinet Memo's treatment of the eleven below-target "
            "counties needs to anticipate the Parliamentary Committee "
            "hearing. A Memo that frames the variation as a structural "
            "pattern across all flagship programmes — citing the "
            "cross-sectoral evidence — provides better political-economy "
            "ground than one that defends the Industrial Modernisation "
            "Programme specifically. The PS recommends the cross-sectoral "
            "framing. The Treasury ceiling question cannot be resolved "
            "purely technically because the Council of Governors will "
            "read whatever decision is taken through the lens of "
            "intergovernmental fiscal relations. A position that "
            "concentrates allocation in the four strong-performing "
            "counties (Treasury's preferred path) is defensible "
            "technically but politically combustible if presented without "
            "the explicit framing that the eleven below-target counties "
            "will receive different intervention modalities. The donor "
            "partnership question has a longer time horizon than the "
            "Cabinet Memo. The Memo can defer the formal response to the "
            "donor mid-term review; what it cannot do is commit to a "
            "position that closes the donor partnership space "
            "prematurely. The PS's recommendation: accept the donor's "
            "recommended scaling envelope in principle, signal "
            "partnership commitment, defer specifics on FY26-27 financing "
            "arrangement to a subsequent technical engagement. The "
            "strategic risk the PS recommends naming The strategic risk "
            "that the technical materials underweight is the "
            "political-economy risk of inaction. The current trajectory "
            "— eleven counties below target, widening variation, donor "
            "envelope misaligned with Treasury ceiling, Parliamentary "
            "Committee shifting toward accountability — produces an "
            "environment in which the Ministry's strategic plan can "
            "become politically untenable before its technical revision "
            "is completed. The PS recommends that the CS consider "
            "whether the Mid-Term Review scheduled for Q2 2027 is "
            "responsive to the political-economy timeline, or whether "
            "earlier strategic engagement with Cabinet is warranted. "
            "This briefing is restricted This briefing is for the CS's "
            "consideration only. Political-economy analysis is "
            "conventionally absent from Cabinet Memos and Treasury "
            "submissions for institutional reasons that the PS respects. "
            "The briefing is provided to inform the CS's judgement on "
            "the technical positions, not to be incorporated into the "
            "technical materials themselves."
        ),
    },
]


# ═════════════════════════════════════════════════════════════════════════
#  Public index
# ═════════════════════════════════════════════════════════════════════════
STRATEGIC_DOCUMENTS: Dict[str, List[Dict[str, Any]]] = {
    "bank": _BANK_DOCS,
    "healthcare": _HEALTHCARE_DOCS,
    "logistics": _LOGISTICS_DOCS,
    "technology": _TECHNOLOGY_DOCS,
    "government": _GOVERNMENT_DOCS,
}

_PACK_SECTION = {
    "bank": "BANK",
    "healthcare": "HEALTHCARE",
    "logistics": "LOGISTICS",
    "technology": "TECHNOLOGY",
    "government": "GOVERNMENT",
}

# Stamp the org_type / position / preview / pack_section on every doc so
# callers don't have to re-compute them.
for _otype, _docs in STRATEGIC_DOCUMENTS.items():
    for _i, _d in enumerate(_docs):
        _d["org_type"] = _otype
        _d["position"] = _i + 1
        _d["pack_section"] = _PACK_SECTION[_otype]
        _d.setdefault("preview", _d["body"][:200].rsplit(" ", 1)[0] + "…")

# Organisation display-name lookup — used by the demo seed scripts (L.2 /
# L.3) when minting "<Organisation> · Demo" contexts.
STRATEGIC_ORG_DISPLAY_NAMES: Dict[str, str] = {
    "bank": "Mara Heritage Bank",
    "healthcare": "Lenana Health Group",
    "logistics": "Korogocho Logistics Group",
    "technology": "Tahidi Systems",
    "government": "Ministry of Industrial Modernisation",
}


def pick_strategic_documents(
    org_type: str,
    kind: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return the strategic docs for an org_type, optionally filtered by kind.

    `org_type` is matched against the 5 canonical slugs; unknown values
    return an empty list so callers can safely fall back to tactical-only
    behaviour. When `kind` is provided the filter is exact (case-sensitive
    against the locked vocabulary above).
    """
    docs = STRATEGIC_DOCUMENTS.get((org_type or "").lower(), [])
    if kind:
        docs = [d for d in docs if d["kind"] == kind]
    return [dict(d) for d in docs]  # shallow copy per call


def strategic_doc_titles(org_type: str) -> List[str]:
    return [d["title"] for d in STRATEGIC_DOCUMENTS.get((org_type or "").lower(), [])]


def strategic_doc_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    for docs in STRATEGIC_DOCUMENTS.values():
        for d in docs:
            if d["id"] == doc_id:
                return dict(d)
    return None


def strategic_corpus_health() -> Dict[str, Any]:
    """Audit helper. Returns per-org doc counts + kind distribution."""
    out: Dict[str, Any] = {
        "total_docs": sum(len(v) for v in STRATEGIC_DOCUMENTS.values()),
        "by_org_type": {k: len(v) for k, v in STRATEGIC_DOCUMENTS.items()},
        "source": "strategic_pack_v1",
    }
    kinds: Dict[str, int] = {}
    for docs in STRATEGIC_DOCUMENTS.values():
        for d in docs:
            kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    out["by_kind"] = kinds
    return out


# ─────────────────────────────────────────────────────────────────────────
#  Audit-time self-check — runs on import so an accidental edit that
#  breaks the pack is caught loudly at server boot rather than silently
#  at first demo session.
# ─────────────────────────────────────────────────────────────────────────
def _self_check() -> None:
    assert sum(len(v) for v in STRATEGIC_DOCUMENTS.values()) == 14, (
        "strategic pack must carry exactly 14 documents"
    )
    for org, docs in STRATEGIC_DOCUMENTS.items():
        if org == "technology":
            assert len(docs) == 2, f"{org} must have 2 docs"
        else:
            assert len(docs) == 3, f"{org} must have 3 docs"
        for d in docs:
            assert d["id"].startswith("strat-"), f"bad id {d['id']}"
            assert d["kind"] in {
                "strategic_plan", "framework", "strategy",
                "theory_of_change", "investment_thesis",
                "political_economy",
            }, f"bad kind {d['kind']} on {d['id']}"
            assert 400 <= len(d["body"].split()) <= 800, (
                f"body length out of 400-800 word band on {d['id']} "
                f"({len(d['body'].split())} words)"
            )


_self_check()
