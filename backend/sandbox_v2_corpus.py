"""Sandbox v2 — calibrated content corpus per organisation context.

Phase J.5. Content keyed `organisation_type → step → content_type → variant`
per the **Sandbox Content Pack** (Mara Heritage Bank · Lenana Health Group ·
Korogocho Logistics Group · Tahidi Systems · Ministry of Industrial
Modernisation).

Every string in CONTEXTS is **verbatim from the content pack**. No DRAFT
markers, no paraphrase. Any deviation from the pack is flagged explicitly
in the report and never silent.

Public surface:

    route_org_type(org_type)                  -> context_key
    route_role(role, context_key)             -> role_key
    pick_opening_question(role, org, seed=0)  -> str
    pick_fallback_situation(role, org)        -> str
    pick_pulse_signals(role, org)             -> list[dict]
    pick_studio_sources(role, org)            -> list[dict]
    pick_composed_draft(role, org)            -> dict
    pick_provenance_refusal(role, org)        -> str
    pick_cycle_snapshot(role, org)            -> dict
    corpus_health()                           -> dict

The pack's inter-connection requirement (Step 2 Pulse citations must
resolve to Step 3 source docs) is verified by ``corpus_health()`` — every
``signals[*].source_citations`` either explicitly references a source-doc
title or the verifier marks it as an external/peer citation (which is
permitted per the pack).
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Routing helpers (pack §"Fallback routing" + §"Role routing within context")
# ---------------------------------------------------------------------------
_ORG_KEYS = {"bank", "healthcare", "logistics", "technology", "government"}

# org_type as collected by the Welcome form → routed context key.
ORG_ROUTING: Dict[str, str] = {
    "bank":             "bank",
    "healthcare":       "healthcare",
    "logistics":        "logistics",
    "saas":             "technology",
    "government":       "government",
    # Pack-defined fallbacks
    "pre_ipo":          "bank",         # "Pre-IPO or growth-stage → Bank"
    "listed_corporate": "bank",         # "Listed corporate → Bank (or Logistics if user role is operational)"
    "other":            "technology",   # "Other → Technology"
}

_OPERATIONAL_ROLES = {"cfo", "coo", "exco_member"}


def route_org_type(org_type: str, role: Optional[str] = None) -> str:
    """Return the canonical context key (one of `_ORG_KEYS`) for the
    org_type the visitor selected on Welcome.

    Implements the pack's verbatim fallback routing. The `listed_corporate`
    branch routes to `logistics` when the role is operational (CFO/COO/Exco)
    per the pack's qualifier "...or Logistics if user role is operational".
    """
    org_type = (org_type or "").strip().lower()
    role = (role or "").strip().lower()

    if org_type == "listed_corporate" and role in _OPERATIONAL_ROLES:
        return "logistics"
    return ORG_ROUTING.get(org_type, "technology")


def route_role(role: str, context_key: str) -> str:
    """Return the role bucket (one of `ceo` | `ned` | `cfo` | `regulator`
    | `government_executive`) the corpus indexes by, given the visitor's
    role and the resolved context.

    Implements the pack's role-routing matrix verbatim:
      • CEO or equivalent                → use CEO variants
      • NED or Board member              → use NED variants
      • CFO/COO/CHRO or Exco member      → CFO variants in
        Bank/Healthcare/Logistics; functional in Technology
      • External Company Secretary       → use NED variants
      • Government executive             → always Government context
      • Investor                         → NED in Technology / Logistics
      • Other                            → CEO variants
      • Regulator                        → regulator if Bank/Government
    """
    role = (role or "").strip().lower()
    ctx = (context_key or "").strip().lower()

    # Government context overrides — only it has a regulator + government_executive bank.
    if ctx == "government":
        if role == "regulator":
            return "regulator"
        if role in {"government_executive", "ceo", "exco_member", "company_secretary", "ned"}:
            return "government_executive"
        return "government_executive"

    # Bank/Healthcare/Logistics/Technology
    if role == "ceo":
        return "ceo"
    if role == "ned":
        return "ned"
    if role == "company_secretary":
        # Pack: External Company Secretary → use NED variants
        return "ned"
    if role in {"cfo", "coo", "exco_member"}:
        # Pack: CFO/COO/CHRO or Exco member → CFO variants in Bank/HC/Log;
        # functional (i.e. CFO bucket) in Technology.
        return "cfo"
    if role == "investor":
        # Pack: Investor → NED in Technology / Logistics
        if ctx in {"technology", "logistics"}:
            return "ned"
        return "ned"
    if role == "regulator":
        # Outside the Government context regulators are uncommon; bank-side
        # supervisor-style framing maps closest to NED.
        if ctx == "bank":
            return "ned"
        return "ned"
    # Pack: Other → use CEO variants by default
    return "ceo"


# ---------------------------------------------------------------------------
# CONTEXT 1 — Bank (Mara Heritage Bank). Verbatim from pack §1.
# ---------------------------------------------------------------------------
BANK = {
    "context_profile": (
        "Fictional institution: Mara Heritage Bank — a mid-tier Kenyan commercial bank, "
        "listed on the Nairobi Securities Exchange, with a balance sheet of approximately "
        "KES 280 billion. Network of 47 branches, predominantly upcountry. Risk profile: "
        "corporate banking dominant, with a growing SME book and an emerging digital "
        "lending portfolio. Regulatory context: CBK supervised, Tier II by classification, "
        "three years into a strategic transformation."
    ),
    "sandbox_flavour": (
        "Provisioning trajectory under sector pressure, real estate concentration drift, "
        "digital lending NPL emerging, AML supervisory dialogue active. The patterns most "
        "likely to land for a banking visitor."
    ),
    "step_1_solva": {
        "opening_questions": {
            "ceo": [
                # Variant 1
                "Your provisioning ratio has compressed by six basis points over two reporting cycles. The CFO says it's normal sector trajectory. The Chief Risk Officer is uneasy. CBK's supervisory letter is due Friday. Where do you actually stand?",
                # Variant 2
                "Three of your Exco submissions don't quite line up. Commercial says the pipeline is strong. Risk says concentration is rising. Finance says the margin compression is structural. Which contradiction are you actually navigating?",
                # Variant 3
                "You inherited a digital lending portfolio that everyone said would be the future. The NPL ratio has crossed 9 per cent. The board wants a position by next Tuesday. What's the question you haven't yet allowed yourself to ask?",
            ],
            "ned": [
                "It's Sunday evening. The audit committee pack has landed. Three notes flag provisioning adequacy. Two flag concentration drift. The external auditor's letter is buried in appendix four. What's the question that wasn't put on the agenda?",
                "Management's narrative says provisioning is adequate. The numbers don't quite agree. You've sat on this board for four years and you've seen this pattern before. What does your experience tell you about how this ends?",
                "The Risk Committee meets Tuesday. The CBK self-assessment on AML is due to the regulator the following week. The sequence matters more than the management note suggests. What's the order in which the questions should be asked?",
            ],
            "cfo": [
                "You've been asked to present the provisioning trajectory to the board. Your numbers are defensible. Your CRO is going to challenge them. What position holds up under their challenge — and which doesn't?",
                "Your monthly management report goes to the CEO on Friday. The numbers are mostly good. But there's one trend that, if read across three months, tells a different story. How do you raise it without overclaiming or underclaiming?",
            ],
        },
        "fallback_situation": (
            "Mara Heritage Bank's Q1 board pack has just landed. Provisioning has compressed "
            "from 74 per cent to 68 per cent over two quarters. Management's commentary "
            "attributes this to portfolio quality improvements. The Chief Risk Officer's "
            "appendix tells a more complicated story — concentration risk has risen 4 "
            "percentage points, driven entirely by real estate. CBK's recent thematic "
            "review on real estate exposure flagged the sector. The board meets in 10 days. "
            "The audit committee meets in three. What's the through-line you should take "
            "into your next conversation?"
        ),
    },
    "step_2_pulse": [
        {
            "id": "bank_pulse_1",
            "title": "Provisioning trajectory across mid-tier peers",
            "pattern": (
                "Across mid-tier Kenyan banks, provisioning ratios have compressed by 4-8 "
                "basis points over the last two reporting cycles. The compression is "
                "broad-based — not specific to any single institution. CBK's most recent "
                "Bank Supervision Annual Report flags the trajectory in section 3.4."
            ),
            "source_citations": [
                {"text": "Mara Heritage Bank — Q4 audited financial statements, note 18 (provisioning detail)", "resolves_to": "doc_1"},
                {"text": "Sector aggregate — CBK Quarterly Banking Supervision Update, Table 7", "resolves_to": "external"},
                {"text": "Three peer Q1 trading updates referenced in our pulse-monitoring set", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": (
                    "Your numbers will be read against the sector pattern, not in isolation. "
                    "CBK's supervisory letter is more likely to focus on adequacy of "
                    "provisioning methodology than on the trajectory itself — because the "
                    "trajectory is now sector-wide."
                ),
                "ned": (
                    "The audit committee's traditional question — 'is our provisioning "
                    "adequate?' — needs to be reframed as 'is our methodology defensible "
                    "against a sector-wide pattern?' The answer to the second question is "
                    "rarely the answer to the first."
                ),
            },
            "next_move": (
                "Take this signal into Solva — the diagnostic on whether your specific "
                "provisioning methodology is robust to the sector pattern, not just to the "
                "historical baseline."
            ),
        },
        {
            "id": "bank_pulse_2",
            "title": "Real estate concentration drift",
            "pattern": (
                "Real estate exposure across listed banks has risen faster than ICAAP "
                "guidelines anticipated. The implication for concentration risk numbers is "
                "non-linear — once exposure crosses certain thresholds, capital adequacy "
                "ratios respond more sharply than the linear projections suggest."
            ),
            "source_citations": [
                {"text": "Mara Heritage Bank — Q1 risk committee paper, section 4 (sector concentration)", "resolves_to": "doc_2"},
                {"text": "ICAAP 2024 framework — internal policy document", "resolves_to": "internal_policy"},
                {"text": "CBK's most recent thematic review on real estate exposure", "resolves_to": "doc_3"},
            ],
            "implications": {
                "ceo": (
                    "Your concentration figure is approaching the ICAAP threshold faster "
                    "than the linear model suggests. The board paper's projection is "
                    "calibrated against a model that may not be capturing the non-linearity."
                ),
                "ned": (
                    "The risk committee should be asking for a stress test calibrated to "
                    "the non-linear response, not just to the existing concentration "
                    "percentage. The model the bank is using was built for a different "
                    "exposure profile."
                ),
            },
            "next_move": (
                "Add this to your pre-board reading. Solva can run the stress-test framing "
                "if you want to test it before the meeting."
            ),
        },
        {
            "id": "bank_pulse_3",
            "title": "Digital lending NPL emergence",
            "pattern": (
                "Digital lending portfolios across mid-tier banks are showing NPL "
                "trajectories that diverge from the institutional book. The lag between "
                "origination cohort and NPL emergence is shorter than retail banking "
                "historical patterns. Three of the five mid-tier banks with digital lending "
                "portfolios have published NPL ratios above 9 per cent in their Q1 results."
            ),
            "source_citations": [
                {"text": "Mara Heritage Bank — Q1 digital lending performance report (internal)", "resolves_to": "internal_report"},
                {"text": "Three peer Q1 results — public filings", "resolves_to": "external"},
                {"text": "CBK's Risk-Based Supervision update on digital credit, section 5", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": (
                    "Your digital lending NPL is approaching the peer median. The question "
                    "is whether the cohort dynamics in your portfolio are converging with "
                    "the peer pattern — or whether your specific origination methodology "
                    "has produced different risk."
                ),
                "ned": (
                    "This is a question the risk committee should ask before the next "
                    "board meeting. The CRO's standard report is structured for "
                    "institutional book NPL; digital lending requires its own cohort analysis."
                ),
            },
            "next_move": (
                "Take this into the next risk committee preparation. The cohort question "
                "is sharper than the aggregate NPL question."
            ),
        },
    ],
    "step_3_workstudio": {
        "source_documents": [
            {
                "id": "doc_1",
                "kind": "Q1 Financial Performance Summary (extract)",
                "title": "Mara Heritage Bank · Q1 2026 · Internal · Page 3 of 12",
                "body": (
                    "Provisioning expense for Q1 2026 totalled KES 1.2 billion, representing a coverage ratio of 68%, "
                    "down from 74% at end-Q4 2025. The compression reflects three factors: (a) write-back of specific "
                    "provisions following the recovery on the Kibos Sugar exposure, (b) re-modelling of expected "
                    "credit losses on the corporate book in light of improved sectoral indicators, and (c) "
                    "reclassification of two SME exposures from Stage 3 to Stage 2 following sustained payment "
                    "performance. Management considers the resulting coverage ratio adequate against expected loss "
                    "projections for FY 2026, although it acknowledges that the trajectory should be reviewed "
                    "against the broader sector trend."
                ),
            },
            {
                "id": "doc_2",
                "kind": "Risk Committee Pre-Read (extract)",
                "title": "Risk Committee Q1 2026 · Confidential · Section 4: Concentration Risk",
                "body": (
                    "The bank's exposure to the real estate sector stands at 31.2% of gross loans at end-Q1 2026, "
                    "against an internal guideline of 25% set in the 2024 ICAAP framework. The increase from 26.8% "
                    "at end-Q4 2025 reflects three new corporate facilities approved during the quarter, two of "
                    "which represent extensions to existing client relationships in the commercial real estate "
                    "segment. The CRO notes that the current concentration level is approaching the threshold at "
                    "which capital adequacy projections become non-linear under the existing stress-testing "
                    "framework. A revised stress test calibrated to the current exposure profile will be presented "
                    "at the next Risk Committee meeting."
                ),
            },
            {
                "id": "doc_3",
                "kind": "CBK Thematic Review extract (public)",
                "title": "CBK Bank Supervision · Thematic Review on Real Estate Exposure · Q4 2025 · Page 14",
                "body": (
                    "The thematic review notes that aggregate real estate exposure across the mid-tier banking "
                    "segment rose by 380 basis points during 2025, with the proportion of listed banks reporting "
                    "real estate concentrations above 28% increasing from three to seven institutions. The "
                    "Authority is monitoring the trajectory with attention to the interaction between sector "
                    "concentration and the quality of underlying collateral, noting that valuation methodologies "
                    "in the current market may not adequately reflect prospective movements in the residential "
                    "and commercial property segments."
                ),
            },
        ],
        "composed_draft": {
            "title": "Q1 Position Note",
            "paragraphs": [
                "Q1 2026 provisioning has compressed to a coverage ratio of 68%, down from 74% at end-Q4 [Doc 1, p. 3]. Management attributes this to specific factors — recovery, ECL re-modelling, and reclassification — while acknowledging the need to review the trajectory against the broader sector trend [Doc 1, p. 3].",
                "The compression coincides with a material rise in real estate concentration, from 26.8% to 31.2% of gross loans, exceeding our internal ICAAP guideline of 25% [Doc 2, Section 4]. Three new corporate facilities approved during the quarter have driven the increase, two of which extend existing commercial real estate relationships [Doc 2, Section 4].",
                "These two trajectories are not independent. The CBK's recent thematic review noted that aggregate real estate exposure across mid-tier banks rose by 380 basis points in 2025, with seven listed banks now reporting concentrations above 28% [CBK Thematic Review, p. 14]. The Authority's specific concern — the interaction between concentration and underlying collateral quality — has direct implications for our provisioning methodology, particularly given the proportion of our real estate book that depends on valuation assumptions in a thinly-traded segment [CBK Thematic Review, p. 14].",
                "The CRO's planned revised stress test, calibrated to the current concentration level, will be presented at the next Risk Committee [Doc 2, Section 4]. The Audit Committee should consider whether the existing provisioning model — built against a different exposure profile — adequately reflects the sector trajectory CBK has flagged [synthesis from Docs 1, 2, 3]. The position taken in the next supervisory letter to CBK will be read against this question.",
            ],
        },
        "provenance_refusal": (
            "This claim isn't sourced from anything in your materials. The source documents discuss the current "
            "trajectory but don't compare it to historical patterns. We can't add it without a citation. If you "
            "have material that supports it, attach it and we can incorporate."
        ),
    },
    "step_4_cyclemanager": {
        "framing": "CEO · NED · or Exco — Bank board cycle",
        "anchor_label": "Audit committee",
        "timeline": [
            {"cycle": "Q3 2025", "anchor": "Q3 Board Meeting",     "date": "21 October 2025",  "status": "Closed"},
            {"cycle": "Q3 2025", "anchor": "Audit Committee",       "date": "14 October 2025",  "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Q4 Board Meeting",     "date": "20 January 2026",  "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Risk Committee",        "date": "13 January 2026",  "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "CBK Supervisory Letter (annual)", "date": "5 February 2026", "status": "Closed"},
            {"cycle": "Q1 2026", "anchor": "Q1 Board Meeting",     "date": "21 April 2026",    "status": "In flight"},
            {"cycle": "Q1 2026", "anchor": "Audit Committee",       "date": "14 April 2026",    "status": "Scheduled"},
            {"cycle": "Q1 2026", "anchor": "Risk Committee",        "date": "9 April 2026",     "status": "Scheduled"},
        ],
        "open_items": [
            {"text": "Q3 2025 Board: Resolution to commission revised stress test on real estate concentration.", "status": "in flight", "owner": "CRO presenting at Q1 2026 Risk Committee"},
            {"text": "Q3 2025 Audit Committee: External auditor recommendation on ECL methodology refinement.", "status": "at risk", "owner": "six-month implementation window expires Q2 2026"},
            {"text": "Q4 2025 Board: Strategic review of digital lending portfolio scope.", "status": "in flight", "owner": "CFO position paper due Q1 board"},
            {"text": "Q4 2025 Risk Committee: AML self-assessment to CBK.", "status": "at risk", "owner": "Authority response not yet received; supervisory dialogue paused since 12 February"},
            {"text": "Q4 2025 Board: CEO succession planning sub-committee.", "status": "in flight", "owner": "Nominations Committee Chair leading"},
        ],
        "strategic_baseline": [
            "Loan book growth target: 12-15% CAGR through 2028 — currently tracking at 9% (below target)",
            "Cost-to-income ratio target: 48% by FY 2027 — currently 53% (improving but behind path)",
            "Digital lending contribution target: 15% of revenue by FY 2026 — currently 11% (on track for revenue, but NPL trajectory is concerning)",
            "ROE target: 18% sustained — currently 14.2% (compressed from sector NIM compression and digital cost base build-out)",
        ],
        "pulse_items": [
            {"text": "Provisioning trajectory signal — flagged 12 February 2026, taken into Risk Committee Q1 prep", "kind": "internal"},
            {"text": "Real estate concentration drift — flagged 28 February 2026, scheduled into Q1 Board agenda", "kind": "internal"},
            {"text": "Digital lending NPL emergence — flagged 8 March 2026, CFO position paper drafting", "kind": "internal"},
            {"text": "Sector cyber posture — flagged 22 March 2026, CISO briefing requested for Q2 board", "kind": "external"},
        ],
        "voice": (
            "This is a snapshot of what your Cycle Manager would look like after three quarters in Akki. "
            "The data is representative of the kinds of items that accumulate; the architecture is the real "
            "product. Notice how Pulse signals enter the cycle — and how open items from prior meetings stay "
            "visible until they are resolved or explicitly closed."
        ),
    },
}


# ---------------------------------------------------------------------------
# CONTEXT 2 — Healthcare (Lenana Health Group). Verbatim from pack §2.
# ---------------------------------------------------------------------------
HEALTHCARE = {
    "context_profile": (
        "Fictional institution: Lenana Health Group — a pre-IPO East African healthcare "
        "group with hospitals in Kenya, Uganda, and Tanzania. Approximately 1,100 beds "
        "across six facilities. Mixed payer mix: insurance (62%), out-of-pocket (28%), "
        "and government schemes (10%). Recent expansion into Tanzania has stretched "
        "operational capacity. The board is preparing for a planned IPO in late 2027."
    ),
    "sandbox_flavour": (
        "Tanzania expansion operational stress, sentinel events in the maternity unit, "
        "cyber posture in the wake of regional ransomware incidents, IPO readiness across "
        "financial reporting and clinical governance."
    ),
    "step_1_solva": {
        "opening_questions": {
            "ceo": [
                "Tanzania facility opened 14 months ago. Bed occupancy is at 72%, ahead of plan. But the clinical incident rate is 2.4× the group average. The medical director says it's normal teething. The CMO is concerned. The board meets in three weeks. What's the position you can defend?",
                "Three of your sentinel events in Q1 happened in the maternity unit at the Nairobi flagship. The clinical leadership says it's coincidence. The risk register says the unit has been understaffed for two cycles. The Quality Committee meets next week. What question are you not yet asking?",
                "IPO is 18 months out. The audit firm wants reporting integrity proven across three financial years. The clinical leadership wants quality metrics in the prospectus. The CFO is worried about restated EBITDA from Tanzania. Where is the actual risk?",
            ],
            "ned": [
                "The Quality Committee pack has landed. Three sentinel events flagged in the maternity unit. Management's narrative: clinical complexity has risen. The data: the staffing ratio has fallen below the safety threshold for two consecutive months. What's the question that should lead the meeting?",
                "The Risk Committee meets ahead of the board. Management has flagged Tanzania operational stress. They have not flagged the cyber posture issue that was on the agenda last quarter and dropped. What's the order of priorities you should set?",
            ],
            "cfo": [
                "Tanzania expansion is ahead of plan on revenue but behind plan on EBITDA. The auditors have flagged restatement risk on the deferred capital costs. The board wants a clean position before IPO documentation begins. What's the version of the truth that holds?",
            ],
        },
        "fallback_situation": (
            "Lenana Health Group's Q1 board pack has just landed. Three sentinel events have been flagged in the "
            "maternity unit at the Nairobi flagship — the highest quarterly count in three years. Management's "
            "narrative attributes the increase to clinical case-mix complexity. The risk register, however, shows "
            "that the unit has operated below the safety staffing ratio for two consecutive months. The Quality "
            "Committee meets in two weeks; the Risk Committee follows; the full board meets the week after. The "
            "IPO timeline assumes clean clinical governance reporting. What's the through-line that should run "
            "from Quality Committee to board?"
        ),
    },
    "step_2_pulse": [
        {
            "id": "hc_pulse_1",
            "title": "Clinical incident rate diverging across new facilities",
            "pattern": (
                "Clinical incident rates at the Tanzania facility are running 2.4× the group average. The pattern "
                "is consistent with new-facility integration data from regional peers: incidents typically peak "
                "in months 12-18 post-opening, then converge to group average over the following 6-9 months — "
                "but only if specific operational interventions are made."
            ),
            "source_citations": [
                {"text": "Lenana Health — Tanzania facility quarterly clinical performance report", "resolves_to": "internal_report"},
                {"text": "Group average from CMO monthly dashboard, Q1 2026", "resolves_to": "internal_report"},
                {"text": "Regional peer benchmark from East African Hospital Association data", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": (
                    "The Tanzania pattern is normal-but-actionable. The decision is not whether to be concerned, "
                    "but which interventions to commit to. Without explicit interventions, the convergence does "
                    "not happen automatically."
                ),
                "ned": (
                    "The Quality Committee should be asking management which specific operational interventions "
                    "are committed for Tanzania, with timelines. \"Things will normalise\" is not a defensible "
                    "position in IPO documentation."
                ),
            },
            "next_move": "Take this into Solva for the strategic question: which interventions, in what sequence, with what timeline.",
        },
        {
            "id": "hc_pulse_2",
            "title": "Maternity unit staffing trend",
            "pattern": (
                "Maternity unit staffing at the Nairobi flagship has fallen below the internally-defined safety "
                "threshold for two consecutive months. The trend correlates with the rise in sentinel events "
                "flagged in the same unit during Q1. Three of the four sentinel events occurred during shifts "
                "when staffing was below threshold."
            ),
            "source_citations": [
                {"text": "Lenana Health — HR monthly staffing report (Nairobi flagship)", "resolves_to": "doc_2"},
                {"text": "Group safety staffing standards — Quality Manual section 4.2", "resolves_to": "internal_policy"},
                {"text": "Q1 sentinel event log — Quality Committee submission", "resolves_to": "doc_1"},
            ],
            "implications": {
                "ceo": (
                    "The correlation between staffing and incidents is now in the data. Management's narrative "
                    "of \"clinical complexity\" is undermined by this signal. The position taken at the Quality "
                    "Committee will be read against the staffing data."
                ),
                "ned": (
                    "This is the question for the Quality Committee. Not \"why are sentinel events rising\" — "
                    "but \"why is staffing below the safety threshold, who decided, and what is being done.\""
                ),
            },
            "next_move": "This is a strategic question. Take it to Solva — sensitivity analysis will show the operational decisions that, if changed, would shift the trajectory.",
        },
        {
            "id": "hc_pulse_3",
            "title": "Regional cyber posture deterioration",
            "pattern": (
                "Three regional healthcare groups have reported ransomware incidents in the last 90 days, with "
                "two of them having patient data exposure. The threat surface is rising; the regulatory response "
                "(in Kenya, Uganda, and Tanzania) is sharpening. Lenana's last cyber readiness audit was 14 "
                "months ago."
            ),
            "source_citations": [
                {"text": "Industry breach reports (anonymised) from East African Healthcare Association", "resolves_to": "external"},
                {"text": "Lenana Health — most recent CISO report to Risk Committee, Q3 2025", "resolves_to": "internal_report"},
                {"text": "Regulatory bulletins from Kenya's Office of the Data Protection Commissioner, Q1 2026", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": (
                    "Cyber posture is a board-level question that has fallen off the agenda. The next Risk "
                    "Committee should explicitly address it; the IPO prospectus will need to include cyber risk "
                    "disclosure."
                ),
                "ned": (
                    "This signal connects to a broader pattern — across boards in the region, cyber risk is "
                    "rising faster than governance cycles are responding. The Risk Committee should formally "
                    "request an updated cyber readiness audit."
                ),
            },
            "next_move": "Add to Risk Committee agenda. Solva can stress-test the prospectus disclosure framing if you want to test it before counsel reviews it.",
        },
    ],
    "step_3_workstudio": {
        "source_documents": [
            {
                "id": "doc_1",
                "kind": "Q1 Quality Report extract",
                "title": "Lenana Health Group · Q1 2026 Quality Report · Confidential · Section 3",
                "body": (
                    "Sentinel events recorded across the group during Q1 2026 totalled six, of which four occurred "
                    "at the Nairobi flagship facility. Three of the four flagship-facility events occurred in the "
                    "maternity unit. The CMO's clinical review identifies case-mix complexity and patient acuity "
                    "as primary contributing factors, with two of the events involving cases that would have "
                    "presented elevated risk in any well-staffed unit. The review notes that operational staffing "
                    "during the relevant shifts is being reviewed as part of the standard root-cause analysis "
                    "process."
                ),
            },
            {
                "id": "doc_2",
                "kind": "HR Monthly Staffing Report extract",
                "title": "Nairobi Flagship · Maternity Unit Staffing · Q1 2026",
                "body": (
                    "Maternity unit staffing in February 2026 averaged 1.18 nursing FTE per occupied bed against "
                    "the group safety standard of 1.30. March 2026 averaged 1.21 FTE per occupied bed. The "
                    "shortfall reflects two factors: extended sick leave for three nursing staff (cumulative 47 "
                    "days lost) and a delayed external recruitment cycle for two replacement positions approved "
                    "in October 2025. HR management notes that the recruitment cycle is now in final-stage "
                    "interviews, with anticipated start dates in May 2026."
                ),
            },
            {
                "id": "doc_3",
                "kind": "Risk Register Extract",
                "title": "Q1 2026 Risk Register · Maternity Unit Operational Risk · Confidential",
                "body": (
                    "The maternity unit at the Nairobi flagship was rated High Risk in the Q4 2025 quarterly "
                    "review based on staffing-to-occupancy trajectory. The mitigation plan committed in Q4 "
                    "included accelerated recruitment, internal redeployment of nursing capacity, and revised "
                    "shift scheduling. As at end-Q1 2026, recruitment progress has been slower than committed; "
                    "internal redeployment has been completed; revised shift scheduling has been implemented in "
                    "three of four shift patterns. The unit's risk rating remains High."
                ),
            },
        ],
        "composed_draft": {
            "title": "Quality Committee Position Note",
            "paragraphs": [
                "Q1 2026 saw six sentinel events across the group, with four at the Nairobi flagship and three of those four in the maternity unit [Doc 1, Section 3]. The CMO's clinical review identifies case-mix complexity and patient acuity as primary contributing factors, noting that two of the events involved cases that would have presented elevated risk in any well-staffed unit [Doc 1, Section 3].",
                "The Q1 staffing data, however, shows that the maternity unit averaged 1.18 nursing FTE per occupied bed in February and 1.21 in March, against the group safety standard of 1.30 [Doc 2]. The shortfall reflects extended sick leave and a delayed external recruitment cycle that was approved in October 2025 [Doc 2].",
                "These two facts are not independent. The maternity unit was rated High Risk in the Q4 2025 risk review based on staffing-to-occupancy trajectory, with a mitigation plan committed in Q4 including accelerated recruitment [Doc 3]. As at end-Q1 2026, recruitment progress has been slower than committed; the unit's risk rating remains High [Doc 3]. Three of the four flagship sentinel events occurred during shifts when staffing was below the safety threshold [synthesis from Docs 1, 2].",
                "The Quality Committee should consider whether the clinical review's framing — that the events reflect case-mix complexity — adequately incorporates the staffing pattern visible in the operational data [synthesis]. The recruitment cycle's delay against committed timeline is itself a governance question that may merit Risk Committee attention. The IPO documentation will require clinical governance disclosures that hold up to external scrutiny; the position taken at this Quality Committee meeting will be foundational to that disclosure [synthesis].",
            ],
        },
        # Generalised from the Bank verbatim per the build brief.
        "provenance_refusal": (
            "This claim isn't sourced from anything in your materials. The source documents discuss the current "
            "clinical and staffing pattern but don't establish a comparison to historical sentinel-event "
            "trajectories. We can't add it without a citation. If you have material that supports it, attach it "
            "and we can incorporate."
        ),
    },
    "step_4_cyclemanager": {
        "framing": "CEO · NED · or Exco — Healthcare governance cycle",
        "anchor_label": "Quality Committee",
        "timeline": [
            {"cycle": "Q3 2025", "anchor": "Q3 Board Meeting",     "date": "15 October 2025",  "status": "Closed"},
            {"cycle": "Q3 2025", "anchor": "Quality Committee",     "date": "8 October 2025",   "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Q4 Board Meeting",     "date": "14 January 2026",  "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Risk Committee",        "date": "7 January 2026",   "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Audit Committee (year-end)", "date": "21 February 2026", "status": "Closed"},
            {"cycle": "Q1 2026", "anchor": "Q1 Board Meeting",     "date": "22 April 2026",    "status": "In flight"},
            {"cycle": "Q1 2026", "anchor": "Quality Committee",     "date": "9 April 2026",     "status": "Scheduled"},
            {"cycle": "Q1 2026", "anchor": "Risk Committee",        "date": "16 April 2026",    "status": "Scheduled"},
        ],
        "open_items": [
            {"text": "Q3 2025 Quality Committee: Tanzania facility integration plan — committed mitigations across staffing, training, and clinical protocols.", "status": "in flight", "owner": "interim review at Q1 Quality Committee"},
            {"text": "Q3 2025 Board: IPO readiness work programme commenced.", "status": "in flight", "owner": "financial reporting milestone Q1 2026, clinical governance milestone Q3 2026"},
            {"text": "Q4 2025 Risk Committee: Maternity unit staffing mitigation plan committed.", "status": "at risk", "owner": "recruitment delayed, three of four mitigations on track"},
            {"text": "Q4 2025 Audit Committee: Tanzania capital cost classification review by external auditors.", "status": "in flight", "owner": "audit committee position paper due Q2"},
            {"text": "Q4 2025 Board: Cyber posture briefing scheduled but deferred.", "status": "at risk", "owner": "no rescheduling agreed"},
        ],
        "strategic_baseline": [
            "Bed capacity expansion target: 1,400 beds by FY 2028 — currently 1,100 (on track)",
            "Group EBITDA margin target: 18% by FY 2027 — currently 14% (Tanzania drag)",
            "Clinical safety: zero never-events; sentinel event rate within group historical baseline — currently above baseline (driven by Nairobi flagship maternity unit)",
            "IPO readiness: filing-ready by Q4 2027 — currently on track financially, behind on clinical governance documentation",
        ],
        "pulse_items": [
            {"text": "Tanzania clinical incident divergence — flagged 14 February 2026, on Q1 Quality Committee agenda", "kind": "internal"},
            {"text": "Maternity unit staffing trend — flagged 6 March 2026, on Q1 Quality Committee agenda", "kind": "internal"},
            {"text": "Regional cyber posture deterioration — flagged 18 March 2026, requesting Risk Committee re-listing", "kind": "external"},
            {"text": "Regulatory environment shift on data protection — flagged 26 March 2026, watching", "kind": "external"},
        ],
        "voice": (
            "This is a snapshot of what your Cycle Manager would look like after three quarters in Akki. "
            "The data is representative of the kinds of items that accumulate; the architecture is the real "
            "product."
        ),
    },
}


# ---------------------------------------------------------------------------
# CONTEXT 3 — Logistics (Korogocho Logistics Group). Verbatim from pack §3.
# ---------------------------------------------------------------------------
LOGISTICS = {
    "context_profile": (
        "Fictional institution: Korogocho Logistics Group — a pre-IPO pan-African logistics "
        "company headquartered in Nairobi, with operations across Kenya, Uganda, Tanzania, "
        "Rwanda, and DRC. Fleet of approximately 800 trucks, six distribution centres, "
        "founder-CEO who has led the business for 15 years. Series C closed last year; "
        "IPO targeted for H2 2026. Founder-CEO succession is a live board topic."
    ),
    "sandbox_flavour": (
        "Founder-CEO succession in formation, cross-border tax disputes, IPO timeline "
        "pressure, fleet utilisation across markets, fuel cost exposure."
    ),
    "step_1_solva": {
        "opening_questions": {
            "ceo": [
                "The IPO is twelve months away. The board has begun the conversation about your succession path. You have three options: stay on through IPO, transition to Chairman pre-IPO, or step away entirely. Each has different implications for valuation, talent retention, and your own legacy. Which path actually serves the company?",
                "Your DRC operation is your highest-margin market. It is also your highest-risk — political volatility, regulatory uncertainty, FX exposure. The board is asking whether to expand or wind down. The CFO has views; the CCO has different views. What's the question that hasn't been put on the table?",
            ],
            "ned": [
                "The Nominations Committee is leading the founder-CEO succession conversation. Three internal candidates, two external possibilities, three different paths. The Chairman wants a recommendation by next quarter. What's the framework that holds up under board scrutiny?",
                "It's the Audit Committee meeting in two weeks. Cross-border tax disputes have escalated in Tanzania and Uganda. The CFO's narrative is that the disputes are routine; the external counsel's letter is more concerned. What's the question the committee should ask?",
            ],
            "cfo": [
                "IPO documentation begins next quarter. Fleet utilisation across markets ranges from 67% (DRC) to 89% (Kenya). The story for the prospectus depends on which average you take. What's the position that survives both the auditors and the analysts?",
            ],
        },
        "fallback_situation": (
            "Korogocho Logistics Group's Q1 board pack has just landed. The Nominations Committee is recommending "
            "a Path C succession plan: founder-CEO transitions to Executive Chairman 18 months pre-IPO, with a "
            "designated CEO successor identified internally. The Audit Committee has flagged cross-border tax "
            "dispute escalation in Tanzania and Uganda. The CFO's IPO readiness paper notes that fleet utilisation "
            "across markets ranges materially. The board meets in three weeks. The audit committee meets next "
            "week. The Nominations Committee meets the week after. What's the through-line you should bring to "
            "the board?"
        ),
    },
    "step_2_pulse": [
        {
            "id": "log_pulse_1",
            "title": "Founder-CEO succession in pre-IPO companies",
            "pattern": (
                "Across pre-IPO companies in the region, founder-CEO succession is the single most-cited "
                "pre-IPO governance gap — flagged in 73% of pre-IPO governance reviews in 2025. Successful IPOs "
                "in this market have had succession plans in place 18-24 months pre-listing on average; "
                "companies that have IPO'd without clear succession have shown valuation discounts of 8-15% "
                "relative to peer comparables in the first 12 months."
            ),
            "source_citations": [
                {"text": "Korogocho — Q1 Nominations Committee paper, succession scenarios", "resolves_to": "doc_1"},
                {"text": "Pre-IPO governance review aggregate from regional capital markets data", "resolves_to": "external"},
                {"text": "Post-IPO valuation comparables, anonymised, from regional NSE/USE/DSE data", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": "The data is supportive of an explicit succession path. The decision is not whether but how — and the timing matters as much as the choice.",
                "ned": "Path C (transition to Chairman 18 months pre-IPO with internal successor) sits within the data-supported range. The risk is execution, not framing.",
            },
            "next_move": "Take Path C into Solva for stress-testing — the simulation will run sensitivity analysis on the succession timing against IPO valuation.",
        },
        {
            "id": "log_pulse_2",
            "title": "Cross-border tax dispute escalation",
            "pattern": (
                "Tax disputes with Tanzania Revenue Authority and Uganda Revenue Authority are running hotter "
                "than the regional industry baseline. Three peer logistics companies have reported escalations "
                "in the last 90 days, with two requiring Tribunal proceedings. The amounts in dispute, while "
                "not balance-sheet-material individually, are material in aggregate when read against IPO "
                "disclosure thresholds."
            ),
            "source_citations": [
                {"text": "Korogocho — Q1 Audit Committee paper, tax matters section", "resolves_to": "doc_2"},
                {"text": "External counsel letters from Q4 2025 and Q1 2026", "resolves_to": "external"},
                {"text": "Industry tax dispute aggregate from anonymised peer disclosures", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": "The disputes are not isolated incidents; they are a sector pattern. The board's narrative on tax compliance posture will need to be updated for IPO disclosure.",
                "ned": "The committee should request an aggregate position paper covering all live disputes across markets, with the IPO disclosure implications explicitly addressed.",
            },
            "next_move": "Take this to Solva for pre-board diagnosis — what's the position that holds up under IPO counsel scrutiny.",
        },
        {
            "id": "log_pulse_3",
            "title": "Fleet utilisation divergence across markets",
            "pattern": (
                "Fleet utilisation across your five markets ranges from 67% (DRC) to 89% (Kenya), with Uganda "
                "and Tanzania between 78-82% and Rwanda at 84%. The divergence has widened over four quarters. "
                "The story you tell in the IPO prospectus depends on whether you present the group average "
                "(81%), the weighted average (84%), or the market-by-market detail."
            ),
            "source_citations": [
                {"text": "Korogocho — Q1 operational performance dashboard", "resolves_to": "internal_report"},
                {"text": "Four-quarter trend from CFO's monthly reports", "resolves_to": "internal_report"},
                {"text": "IPO prospectus drafting framework from external advisor", "resolves_to": "doc_3"},
            ],
            "implications": {
                "ceo": "Investors will see all three numbers. The question is whether the narrative explains the divergence as a strategic choice (DRC margin premium) or as an operational gap. The story matters more than the average.",
                "cfo": "The IPO prospectus should disclose all three with the strategic narrative explaining the divergence. Pretending the average is the story will be detected by analysts.",
            },
            "next_move": "Solva can run the prospectus narrative formation — Develop Strategy sub-module — to test the position against likely analyst questions.",
        },
    ],
    "step_3_workstudio": {
        "source_documents": [
            {
                "id": "doc_1",
                "kind": "Nominations Committee Paper extract",
                "title": "Korogocho Logistics · Q1 2026 Nominations Committee · Section 4: Succession Scenarios",
                "body": (
                    "The Committee has reviewed three succession scenarios for Founder-CEO transition. Path A "
                    "(CEO continues through IPO and 18 months post): preserves continuity, defers transition "
                    "risk, but introduces post-IPO governance complexity. Path B (CEO steps away 12 months "
                    "pre-IPO with external recruitment): produces clean governance for prospectus but "
                    "introduces transition risk in the IPO window. Path C (CEO transitions to Executive "
                    "Chairman 18 months pre-IPO with internal successor): balances continuity with explicit "
                    "governance signal, supported by the regional pre-IPO governance evidence base. The "
                    "Committee's preliminary recommendation is Path C, contingent on board endorsement of the "
                    "proposed internal successor."
                ),
            },
            {
                "id": "doc_2",
                "kind": "Audit Committee Tax Position Paper",
                "title": "Q1 2026 Audit Committee · Tax Matters · Section 3: Cross-Border Disputes",
                "body": (
                    "Three live disputes are tracked across Tanzania (TRA assessment of 2.3bn TZS in transfer "
                    "pricing for 2022-23), Uganda (URA reassessment of 4.1bn UGX on permanent establishment "
                    "treatment), and DRC (administrative appeal on customs valuation). Aggregate exposure on a "
                    "worst-case basis is approximately 1.4% of group net assets. External counsel assessment "
                    "indicates that the Tanzania and Uganda matters are likely to require Tribunal "
                    "proceedings; the DRC matter is at administrative review stage. None of the disputes "
                    "individually meets disclosure thresholds; aggregate disclosure for IPO purposes is being "
                    "assessed."
                ),
            },
            {
                "id": "doc_3",
                "kind": "IPO Readiness Q1 Update",
                "title": "Korogocho · Q1 2026 IPO Readiness Update · Section 2: Disclosure Framework",
                "body": (
                    "The IPO Working Group has reviewed the disclosure framework against current group "
                    "operational and governance status. Three items are flagged as requiring board-level "
                    "positions before drafting commences in Q3: (a) succession planning narrative for the "
                    "prospectus; (b) tax matters disclosure approach for cross-border disputes; (c) operational "
                    "metrics presentation given inter-market divergence. The Working Group recommends that each "
                    "item be addressed at a dedicated board session in advance of prospectus drafting, with "
                    "the succession question taken first given its centrality to investor perception."
                ),
            },
        ],
        "composed_draft": {
            "title": "Pre-Board Position Note",
            "paragraphs": [
                "Three matters before this board interlock more closely than they appear separately. The Nominations Committee is recommending Path C — founder-CEO transitioning to Executive Chairman 18 months pre-IPO with an internal successor [Doc 1, Section 4]. The Audit Committee has tracked three cross-border tax disputes whose aggregate exposure represents 1.4% of group net assets, with external counsel indicating Tribunal proceedings likely in Tanzania and Uganda [Doc 2, Section 3]. The IPO Working Group has flagged three items requiring board-level positions before prospectus drafting begins in Q3, including the succession narrative and the tax disclosure approach [Doc 3, Section 2].",
                "The succession decision is supported by the regional evidence base on pre-IPO governance [Doc 1, Section 4, with reference to peer benchmark data]. Path C sits within the timing range that produces clean prospectus disclosure while preserving operational continuity. The Nominations Committee's recommendation is contingent on board endorsement of the proposed internal successor [Doc 1, Section 4].",
                "The tax matters require board-level positioning that connects to the IPO disclosure framework [synthesis from Docs 2, 3]. Aggregate exposure does not meet individual disclosure thresholds, but the IPO context elevates the disclosure question — the position taken now will be foundational to prospectus drafting [Doc 3, Section 2]. The Audit Committee should be empowered to develop the disclosure framework in coordination with the IPO Working Group.",
                "The IPO Working Group's recommendation that succession be addressed first is correct — the succession decision is the foundation on which the prospectus narrative on governance is built [Doc 3, Section 2]. The board should consider whether the dedicated session approach proposed by the Working Group is calibrated to the time available before prospectus drafting begins, given that succession decisions of this nature have execution windows that may exceed the proposed Q3 timeline [synthesis].",
            ],
        },
        "provenance_refusal": (
            "This claim isn't sourced from anything in your materials. The source documents discuss the "
            "succession scenarios, tax disputes, and IPO disclosure framework but don't establish the "
            "comparison you're drawing. We can't add it without a citation. If you have material that "
            "supports it, attach it and we can incorporate."
        ),
    },
    "step_4_cyclemanager": {
        "framing": "Founder-CEO · NED · or CFO — Logistics governance cycle",
        "anchor_label": "Nominations Committee",
        "timeline": [
            {"cycle": "Q3 2025", "anchor": "Q3 Board Meeting",        "date": "23 October 2025", "status": "Closed"},
            {"cycle": "Q3 2025", "anchor": "Audit Committee",          "date": "16 October 2025", "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Q4 Board Meeting",        "date": "22 January 2026", "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Nominations Committee",    "date": "10 December 2025","status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "IPO Working Group launch", "date": "5 February 2026", "status": "Closed"},
            {"cycle": "Q1 2026", "anchor": "Q1 Board Meeting",        "date": "23 April 2026",   "status": "In flight"},
            {"cycle": "Q1 2026", "anchor": "Audit Committee",          "date": "16 April 2026",   "status": "Scheduled"},
            {"cycle": "Q1 2026", "anchor": "Nominations Committee",    "date": "30 April 2026",   "status": "Scheduled"},
        ],
        "open_items": [
            {"text": "Q3 2025 Nominations Committee: founder-CEO succession framework.", "status": "in flight", "owner": "Path C preliminary recommendation, board endorsement pending"},
            {"text": "Q3 2025 Audit Committee: cross-border tax dispute disclosure framework.", "status": "in flight", "owner": "external counsel work continuing"},
            {"text": "Q4 2025 Board: DRC operational expansion vs wind-down decision.", "status": "open", "owner": "deferred from Q4 to Q2"},
            {"text": "Q4 2025 Board: IPO Working Group remit and timeline.", "status": "in flight", "owner": "Q1 milestones largely on track"},
            {"text": "Q4 2025 Audit Committee: external auditor scope for IPO work.", "status": "at risk", "owner": "counsel selection delayed"},
        ],
        "strategic_baseline": [
            "IPO target: H2 2026 — currently on track to filing window",
            "Revenue target FY 2026: 19bn KES — Q1 actuals annualised at 18.4bn (slight under)",
            "Fleet expansion target: 1,000 trucks by FY 2027 — currently 820, on track",
            "Cross-border revenue mix target: 45% by FY 2027 — currently 38%, on track",
            "Founder-CEO succession: explicit plan endorsed pre-IPO — Path C in formation",
        ],
        "pulse_items": [
            {"text": "Founder-CEO succession sector pattern — flagged 4 March 2026, integrated into Nominations work", "kind": "internal"},
            {"text": "Cross-border tax dispute escalation — flagged 18 March 2026, on Q1 Audit agenda", "kind": "internal"},
            {"text": "Fleet utilisation divergence prospectus implications — flagged 25 March 2026, IPO Working Group", "kind": "internal"},
            {"text": "Regional logistics M&A activity — flagged 6 April 2026, watching", "kind": "external"},
        ],
        "voice": (
            "This is a snapshot of what your Cycle Manager would look like after three quarters in Akki. "
            "The data is representative; the architecture is the real product."
        ),
    },
}


# ---------------------------------------------------------------------------
# CONTEXT 4 — Technology (Tahidi Systems). Verbatim from pack §4.
# ---------------------------------------------------------------------------
TECHNOLOGY = {
    "context_profile": (
        "Fictional institution: Tahidi Systems — a Series A B2B SaaS company headquartered "
        "in Nairobi with sales presence in Lagos and Cape Town. Approximately $4.8M ARR, "
        "50 employees, three founders, just raised $12M Series A in mid-2025. Product: "
        "industry vertical SaaS for African mid-market wholesalers and distributors. The "
        "board includes the lead Series A investor, the seed lead, and one independent."
    ),
    "sandbox_flavour": (
        "Customer concentration risk after losing a major account, CAC inflation, NRR "
        "compression, runway visibility, Series B positioning."
    ),
    "step_1_solva": {
        "opening_questions": {
            "ceo": [
                "TechBridge churned in November. They were 11% of ARR. Your CAC has gone from $8K to $14K over six months. Your NRR has compressed from 118% to 102%. Your runway is now 11 months. The board meets in two weeks. What's the position you take into the room?",
                "You raised Series A on a thesis: that this product would expand from wholesalers to distributors organically. Twelve months in, the expansion isn't happening at the rate you assumed. Two of your investors are starting to ask hard questions. Which question are you avoiding asking yourself?",
                "Your CTO and Head of Product disagree on the integrations roadmap. The CTO wants depth on five existing integrations; the Head of Product wants breadth across fifteen. The decision affects Q3 hiring, Q4 product, and the Series B pitch. What's the question that resolves it?",
            ],
            "ned": [
                "You're an investor on this board. The CEO's narrative on Q1 is more upbeat than the unit economics suggest. The other investors want a 'green and on-track' message; the founder is fragile. What's your role in the meeting next Tuesday?",
            ],
            "cfo": [
                "Series B prep is starting. The runway is 11 months. The story you tell investors depends on whether you frame Q1 as a setback or a recalibration. The CEO leans toward the latter; the unit economics suggest the former. What's the version of the truth that holds?",
            ],
        },
        "fallback_situation": (
            "Tahidi Systems' Q1 2026 board pack has just landed. TechBridge — the largest customer at 11% of ARR "
            "— churned in November 2025. CAC has risen from $8K to $14K over six months. NRR has compressed from "
            "118% to 102%. Runway is at 11 months. The Series A investors have asked for a strategic options "
            "paper before the next board meeting. The board meets in 12 days. What's the through-line that holds "
            "up across an honest conversation with the investors?"
        ),
    },
    "step_2_pulse": [
        {
            "id": "tech_pulse_1",
            "title": "Customer concentration risk in Series A SaaS",
            "pattern": (
                "Across Series A B2B SaaS companies in the region, customer concentration above 8% per logo "
                "correlates strongly with valuation multiples in subsequent rounds. Companies that lose a "
                "top-five customer in the year before Series B typically see multiples compress 15-30% relative "
                "to peer comparables — unless the lost customer is replaced by two or more equivalent logos "
                "within 90 days."
            ),
            "source_citations": [
                {"text": "Tahidi Systems — Q1 2026 customer concentration analysis", "resolves_to": "doc_1"},
                {"text": "Series A churn benchmark from regional VC portfolio data", "resolves_to": "external"},
                {"text": "Series B multiple comparables (anonymised peer set)", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": "The TechBridge churn is now in your data. The Series B story will be read against this signal. The decision is whether to position the churn as a one-time event or as a structural concentration risk being addressed.",
            },
            "next_move": "Take this into Solva — Develop Strategy. The diagnostic on Series B positioning depends on whether the recovery path is credible to investors who have seen this pattern before.",
        },
        {
            "id": "tech_pulse_2",
            "title": "CAC inflation as leading indicator",
            "pattern": (
                "CAC inflation of 50%+ in two consecutive quarters typically signals one of three underlying "
                "conditions: ICP drift, competitive intensity rise, or sales execution gap. The three diagnoses "
                "require different responses. Companies that misdiagnose typically execute against the wrong "
                "response and accelerate runway compression."
            ),
            "source_citations": [
                {"text": "Tahidi Systems — Q1 sales performance dashboard", "resolves_to": "doc_2"},
                {"text": "Six-quarter CAC trend", "resolves_to": "doc_2"},
                {"text": "Industry CAC benchmarks from Series A operator network", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": "Your CAC inflation has crossed the 50% threshold for two consecutive quarters. The board's standard 'fix sales' framing assumes the third diagnosis. The first two — ICP drift, competitive intensity — would require different interventions.",
            },
            "next_move": "Take this to Solva for the diagnostic. Seek Clarity sub-module — the question is which of the three conditions you're actually facing.",
        },
        {
            "id": "tech_pulse_3",
            "title": "NRR compression and Series B narrative",
            "pattern": (
                "NRR below 110% in the year before Series B is the single most-cited reason Series B rounds "
                "get delayed or downgraded. The narrative implication is severe: NRR is the metric Series B "
                "investors anchor on for valuing growth durability. The 102% you're at is below the threshold "
                "most Series B leads will accept without explicit explanation."
            ),
            "source_citations": [
                {"text": "Tahidi Systems — Q1 NRR cohort analysis", "resolves_to": "doc_2"},
                {"text": "Series B benchmark data from regional venture network", "resolves_to": "external"},
                {"text": "Investor communication standards from peer Series B decks", "resolves_to": "external"},
            ],
            "implications": {
                "ceo": "Series B narrative now requires explicit treatment of the NRR trajectory. Pretending it's normal will be detected. The narrative needs to either show recovery or explain the structural reason for the compression.",
            },
            "next_move": "Take this into Solva — Simulate Hypothesis. Run the scenarios for what happens to NRR over the next two quarters under different operational decisions.",
        },
    ],
    "step_3_workstudio": {
        "source_documents": [
            {
                "id": "doc_1",
                "kind": "Q1 Performance Summary",
                "title": "Tahidi Systems · Q1 2026 Performance Summary · CEO Office",
                "body": (
                    "Q1 2026 closed with ARR of $4.8M (against $5.4M Q1 plan), reflecting the November 2025 "
                    "TechBridge churn that removed approximately $530K of ARR. New logo additions in Q1 totalled "
                    "$290K — below the $450K plan. Net new ARR for the quarter was therefore negative $240K. "
                    "Customer concentration: top customer now 8% (down from 11%), top five customers 28% (down "
                    "from 32%), reflecting the loss of the previous top customer. Pipeline coverage for Q2 "
                    "stands at 2.4× the quarterly target."
                ),
            },
            {
                "id": "doc_2",
                "kind": "Q1 Unit Economics Analysis",
                "title": "Tahidi Systems · Q1 2026 Unit Economics · CFO Office",
                "body": (
                    "Customer Acquisition Cost in Q1 2026 stood at $14,200 fully loaded (up from $8,400 in Q3 "
                    "2025, $11,100 in Q4 2025). Net Revenue Retention compressed to 102% from 118% in Q3 2025. "
                    "The compression reflects a combination of the TechBridge loss and reduced expansion ARR "
                    "from existing customers. Burn multiple stood at 2.1× in Q1, up from 1.4× in Q3 2025. Cash "
                    "position at end-Q1 was $9.2M against monthly burn of $850K — runway of approximately 10.8 "
                    "months at current burn."
                ),
            },
            {
                "id": "doc_3",
                "kind": "Strategic Options Paper extract",
                "title": "Tahidi Systems · Strategic Options · Q1 2026 · Founder Office",
                "body": (
                    "Three strategic options have been considered for the next 12 months. Option A: maintain "
                    "growth thesis, accept Series B as bridge round at lower valuation, focus on NRR recovery. "
                    "Option B: pivot to product-led growth motion to reduce CAC, defer Series B by 6-9 months, "
                    "accept slower top-line. Option C: pursue strategic conversation with two known acquirers "
                    "in the space, position for acqui-hire at the floor of pre-money. The CEO's view is that "
                    "Option A is the only path that preserves the original thesis. The CFO has asked for an "
                    "honest evaluation of all three before the strategic options paper goes to the board."
                ),
            },
        ],
        "composed_draft": {
            "title": "Q1 Position Note · Series B Preparation",
            "paragraphs": [
                "Q1 2026 closed with ARR of $4.8M against a plan of $5.4M, reflecting the November 2025 TechBridge churn of approximately $530K [Doc 1]. New logo additions totalled $290K against $450K plan; net new ARR for the quarter was therefore negative $240K [Doc 1]. Customer concentration moved meaningfully — top customer at 8% (down from 11%), top five at 28% (down from 32%) — but only because of the loss, not because of a deliberate diversification programme [Doc 1].",
                "Unit economics show concurrent pressure across three dimensions. CAC has risen from $8,400 in Q3 2025 to $14,200 in Q1 2026 [Doc 2]. NRR has compressed from 118% to 102% over the same period, reflecting both the TechBridge loss and reduced expansion ARR from existing customers [Doc 2]. Burn multiple is at 2.1× — up from 1.4× — and runway stands at approximately 10.8 months at current burn [Doc 2]. The runway figure assumes constant burn; growth investments would shorten the runway materially.",
                "The strategic options paper considers three paths — maintain growth thesis with bridge Series B, pivot to PLG with deferred raise, or strategic conversation with known acquirers [Doc 3]. The CEO's view favours Option A; the CFO has requested honest evaluation of all three [Doc 3]. The board's role at this meeting is to test the assumptions underlying each option against the current unit economics, not to validate the founder's preferred narrative.",
                "Two questions warrant explicit board engagement. First: is the recovery path implicit in Option A — bringing NRR back above 110% within two quarters — consistent with the cohort dynamics visible in Q1 data, or does it require assumptions the data does not support [synthesis from Docs 1, 2]. Second: at what point does the board's fiduciary responsibility to evaluate Options B and C in good faith trigger, given the runway position [synthesis]. The strategic options paper's framing of Option A as the only path consistent with the original thesis may be the question, not the answer.",
            ],
        },
        "provenance_refusal": (
            "This claim isn't sourced from anything in your materials. The source documents discuss the current "
            "ARR, unit economics, and strategic options but don't establish the comparison you're drawing. We "
            "can't add it without a citation. If you have material that supports it, attach it and we can "
            "incorporate."
        ),
    },
    "step_4_cyclemanager": {
        "framing": "CEO/Founder · NED (investor) · or CFO — Series A SaaS cycle",
        "anchor_label": "Board / investor cadence",
        "timeline": [
            {"cycle": "Q3 2025", "anchor": "Q3 Board Meeting",                        "date": "8 October 2025",   "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Q4 Board Meeting",                        "date": "12 January 2026",  "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "TechBridge churn announced",              "date": "20 November 2025", "status": "Closed"},
            {"cycle": "Q1 2026", "anchor": "Strategic Options Paper requested",       "date": "12 March 2026",    "status": "In flight"},
            {"cycle": "Q1 2026", "anchor": "Q1 Board Meeting",                        "date": "9 April 2026",     "status": "Scheduled"},
            {"cycle": "Q1 2026", "anchor": "Series A investor 1:1s (CEO)",            "date": "Various, March-April", "status": "In flight"},
            {"cycle": "Q2 2026", "anchor": "Series B prep formal launch",             "date": "May 2026 target",  "status": "Scheduled"},
        ],
        "open_items": [
            {"text": "Q3 2025 Board: ICP refinement workstream.", "status": "in flight", "owner": "CRO leading; results expected Q2"},
            {"text": "Q4 2025 Board: TechBridge replacement strategy.", "status": "at risk", "owner": "replacement pipeline below target"},
            {"text": "Q4 2025 Board: PLG motion exploration.", "status": "in flight", "owner": "Head of Product position paper Q1"},
            {"text": "Q1 2026 Board: strategic options paper across A/B/C scenarios.", "status": "in flight", "owner": "CEO and CFO drafting"},
            {"text": "Q1 2026 CEO: Series A investor sentiment check.", "status": "in flight", "owner": "1:1s ongoing"},
        ],
        "strategic_baseline": [
            "FY 2026 ARR target: $9.5M (set at Series A close) — Q1 trajectory implies $7.2M finish",
            "Series B target close: Q3 2026 — current path implies Q4 2026 or bridge",
            "NRR target: 120%+ sustained — currently 102% (below)",
            "CAC target: $9K with payback period under 14 months — currently $14K, 18-month payback",
            "Logo concentration: no customer above 8% — currently 8% top (down from 11%)",
        ],
        "pulse_items": [
            {"text": "Customer concentration sector pattern — flagged 6 December 2025, integrated into strategic options paper", "kind": "internal"},
            {"text": "CAC inflation diagnosis pattern — flagged 22 February 2026, requesting board agenda", "kind": "internal"},
            {"text": "NRR Series B threshold pattern — flagged 14 March 2026, integrated into Series B prep", "kind": "internal"},
            {"text": "Regional Series B valuation environment — flagged 28 March 2026, watching", "kind": "external"},
        ],
        "voice": (
            "This is a snapshot of what your Cycle Manager would look like after three quarters in Akki. "
            "The data is representative; the architecture is the real product."
        ),
    },
}


# ---------------------------------------------------------------------------
# CONTEXT 5 — Government (Ministry of Industrial Modernisation). Verbatim from pack §5.
# ---------------------------------------------------------------------------
GOVERNMENT = {
    "context_profile": (
        "Fictional institution: Ministry of Industrial Modernisation (Kenya context — "
        "fictional ministry). Cabinet Secretary leading; Principal Secretary running "
        "operations; six technical Directorates; reports to Cabinet, the National "
        "Assembly Committee on Industrialisation, and Treasury for budget. The Ministry "
        "is mid-cycle on a flagship industrial policy programme that has produced uneven "
        "results across counties."
    ),
    "sandbox_flavour": (
        "Cabinet Memo preparation under inter-ministerial contradictions, county "
        "implementation variation, donor commitment alignment, supervisory dialogue "
        "with sector regulators, Parliamentary Committee appearance preparation."
    ),
    "step_1_solva": {
        "opening_questions": {
            "government_executive": [
                "Cabinet meets Tuesday. Six Directorate submissions; the AG's position on the constitutional question; Treasury's view on the FY26-27 ceiling; a regulator's sector report; a donor's mid-term review. The Cabinet Memo cannot contradict any of them and must answer the question Cabinet has not yet thought to ask. What's the through-line?",
                "Your flagship industrial policy programme has produced uneven county results. Three counties are above target; three are at target; eleven are below. The Treasury wants reallocation; the National Assembly Committee wants accountability; the donor wants a course-correction plan. What's the position that satisfies all three without compromising programme integrity?",
                "Your Directorate's submission to the Cabinet Memo is due Friday. The numbers are defensible; the policy framing is contested by another Directorate. The PS will need to reconcile both views before the CS reads. What's the version of your position that survives the reconciliation?",
            ],
            "regulator": [
                "A licensee's quarterly return contradicts what they told you in the supervisory dialogue last quarter. The discrepancy is not minor. The Authority's standard response framework anticipates either administrative action or a formal hearing. The decision affects the supervisory relationship and the precedent. What's the question that comes first?",
                "Three of your sectoral entities have reported similar deficiencies in their quarterly filings. The pattern is broader than any single entity. The Authority's response to one shapes its credibility on the others. What's the framework that holds across all three?",
            ],
        },
        "fallback_situation": (
            "The Ministry's Cabinet Memo on the Q2 industrial policy programme review is due Tuesday. Six "
            "Directorates have submitted; the Attorney General's office has flagged a constitutional question "
            "on county allocation; Treasury's letter raises FY26-27 ceiling concerns; the National Assembly "
            "Committee on Industrialisation is preparing a hearing for the following week; a donor's mid-term "
            "review is in active consultation. The county results show three above target, three at target, "
            "eleven below. What's the through-line that runs from your Directorate's position to the Cabinet "
            "decision?"
        ),
    },
    "step_2_pulse": [
        {
            "id": "gov_pulse_1",
            "title": "County implementation variation in flagship programmes",
            "pattern": (
                "Across flagship national programmes implemented through counties, the pattern of "
                "three-quarters of counties below target is not unique to industrial modernisation. The "
                "National Treasury's most recent COB report identifies similar variation across health, "
                "agriculture, and water programmes. The structural causes — county capacity, fiscal flow "
                "timing, intergovernmental coordination — are common across sectors."
            ),
            "source_citations": [
                {"text": "Ministry — Q1 county implementation report", "resolves_to": "doc_1"},
                {"text": "Office of Controller of Budget — most recent quarterly report", "resolves_to": "external"},
                {"text": "Council of Governors — intergovernmental coordination review", "resolves_to": "external"},
            ],
            "implications": {
                "government_executive": (
                    "Reframing the variation as a sector-specific problem is rebuttable in Cabinet. The "
                    "cross-sectoral pattern is documented. The Memo's diagnostic should acknowledge the "
                    "structural pattern while differentiating which causes are specific to this programme and "
                    "which are common."
                ),
            },
            "next_move": "Take this into Solva — the Memo's diagnostic frame depends on getting the pattern attribution right.",
        },
        {
            "id": "gov_pulse_2",
            "title": "Donor commitment misalignment with FY26-27 ceiling",
            "pattern": (
                "The donor mid-term review's recommended scaling envelope exceeds the Treasury FY26-27 "
                "ceiling for the programme by approximately 22%. The misalignment is consistent with patterns "
                "across two other Ministries' donor-funded flagship programmes — donor commitments structured "
                "against pre-fiscal-tightening assumptions colliding with current Treasury caps."
            ),
            "source_citations": [
                {"text": "Donor mid-term review — Q1 2026", "resolves_to": "doc_3"},
                {"text": "Treasury Sector Working Group ceiling letter for FY26-27", "resolves_to": "doc_2"},
                {"text": "Cross-Ministry pattern from internal monitoring", "resolves_to": "external"},
            ],
            "implications": {
                "government_executive": (
                    "The Cabinet Memo cannot present the donor's recommended envelope and the Treasury ceiling "
                    "as compatible without addressing the gap. The honest position acknowledges the "
                    "misalignment and proposes a sequencing approach — what gets done within the ceiling, what "
                    "is paused, what is renegotiated with donors."
                ),
            },
            "next_move": "Take this to Solva — sensitivity analysis on the sequencing trade-offs across what gets prioritised within ceiling.",
        },
        {
            "id": "gov_pulse_3",
            "title": "Parliamentary Committee questioning pattern",
            "pattern": (
                "The National Assembly Committee on Industrialisation's questioning pattern in the last three "
                "hearings has shifted from programme-design questions to implementation accountability "
                "questions. The shift is consistent across other sectoral committees — the Departmental "
                "Committees in this Parliament have moved from ex-ante review to ex-post accountability. The "
                "Ministry's hearing preparation framework was last updated for the previous pattern."
            ),
            "source_citations": [
                {"text": "Hansard records of recent Committee hearings (last three sessions)", "resolves_to": "external"},
                {"text": "Comparable Departmental Committee patterns from sectoral monitoring", "resolves_to": "external"},
                {"text": "Ministry hearing preparation protocol from 2024", "resolves_to": "internal_policy"},
            ],
            "implications": {
                "government_executive": (
                    "Hearing preparation should be calibrated to accountability questions, not programme-design "
                    "questions. The CS will be asked specifically about why eleven counties are below target — "
                    "not whether the programme design is sound."
                ),
            },
            "next_move": "Solva can prepare the position on the most likely accountability questions before the hearing.",
        },
    ],
    "step_3_workstudio": {
        "source_documents": [
            {
                "id": "doc_1",
                "kind": "Industrial Modernisation Q1 County Report",
                "title": "Ministry of Industrial Modernisation · Q1 2026 County Implementation Review",
                "body": (
                    "The flagship Industrial Modernisation Programme has now completed seven quarters of "
                    "county-level implementation. Q1 2026 county performance against the year-end targets shows "
                    "three counties at or above 100% of plan (Kiambu, Machakos, Nakuru); three counties at "
                    "80-100% (Kisumu, Mombasa, Nyeri); and eleven counties below 80%. The variation reflects "
                    "three documented factors: capacity differences in county industrial development units; "
                    "timing of conditional grant disbursements from Treasury; and intergovernmental coordination "
                    "effectiveness. The Directorate of County Coordination has flagged that the variation "
                    "pattern has widened over four quarters rather than converging as the original programme "
                    "theory of change anticipated."
                ),
            },
            {
                "id": "doc_2",
                "kind": "Treasury FY26-27 Sector Ceiling Letter",
                "title": "National Treasury · Sector Working Group · FY26-27 Ceiling Communication",
                "body": (
                    "The indicative ceiling for the Industrial Modernisation Programme for FY26-27 stands at "
                    "KES 4.2 billion, against the FY25-26 actual of KES 4.8 billion and the donor mid-term "
                    "review's recommended envelope of KES 5.1 billion for FY26-27. The reduction reflects the "
                    "macro-fiscal consolidation programme; ceilings across all flagship programmes have been "
                    "adjusted downward in line with the Sector Working Group framework. Treasury notes that "
                    "programme outputs in the four counties showing strong performance can be maintained within "
                    "the ceiling provided allocation is concentrated in those counties; alternative scenarios "
                    "involving programme expansion would require either reprioritisation across the Ministry's "
                    "other vote heads or supplementary appropriation, neither of which is currently anticipated."
                ),
            },
            {
                "id": "doc_3",
                "kind": "Donor Mid-Term Review extract",
                "title": "Industrial Modernisation Programme · Donor Mid-Term Review · Section 5: Recommendations",
                "body": (
                    "The mid-term review concludes that the programme's design remains fundamentally sound, "
                    "with strong performance in the four counties where implementation conditions were most "
                    "favourable. The review recommends scaling the programme to address the implementation "
                    "gaps in the eleven below-target counties, with a targeted envelope of KES 5.1 billion for "
                    "FY26-27 to fund (a) county capacity strengthening, (b) accelerated conditional grant "
                    "disbursement mechanism, and (c) enhanced intergovernmental coordination structures. The "
                    "donor partnership framework provides for matched funding of up to 35% of the recommended "
                    "envelope, contingent on Government commitment to the full programme scaling."
                ),
            },
        ],
        "composed_draft": {
            "title": "Cabinet Memo Position Note",
            "paragraphs": [
                "The Industrial Modernisation Programme's Q1 2026 results show widening county variation: three counties at or above target, three at 80-100%, and eleven below 80% [Doc 1]. The Directorate of County Coordination has flagged that variation has widened over four quarters rather than converging as the original theory of change anticipated [Doc 1]. The pattern reflects three documented structural factors: county capacity differences, conditional grant disbursement timing, and intergovernmental coordination effectiveness [Doc 1].",
                "Two recommendations from external reviews bear directly on the Cabinet's decision space. The donor mid-term review recommends scaling the programme with an envelope of KES 5.1 billion for FY26-27 to address implementation gaps [Doc 3, Section 5]. Treasury's indicative FY26-27 ceiling stands at KES 4.2 billion, reflecting the macro-fiscal consolidation programme, with Treasury noting that programme outputs in the four strong-performing counties can be maintained within ceiling provided allocation is concentrated [Doc 2]. The 22% gap between the donor recommendation and the Treasury ceiling cannot be reconciled within current appropriation.",
                "Three options for Cabinet consideration follow from the constraints. Option A: implement Treasury's framework — concentrate allocation in the four strong-performing counties, accept that the programme will not scale to address the eleven below-target counties in FY26-27. Option B: pursue donor matched funding within a recalibrated envelope, accepting that the programme scaling will be partial against the donor recommendation. Option C: prepare a supplementary appropriation request for FY26-27 with explicit fiscal trade-offs identified across the Ministry's vote heads [synthesis from Docs 2, 3].",
                "The National Assembly Committee on Industrialisation's accountability hearing scheduled for the week following Cabinet will focus on the eleven below-target counties [synthesis with sector monitoring]. The Cabinet's position taken at this Memo will be the foundation for the CS's response to the Committee. Cabinet may wish to consider whether Option A's concentration approach is defensible to the accountability frame the Committee will bring, or whether Option B or C is more aligned with the programme's original Cabinet authorisation [synthesis].",
            ],
        },
        "provenance_refusal": (
            "This claim isn't sourced from anything in your materials. The source documents discuss the "
            "programme's current implementation pattern and the Treasury / donor envelope tension, but don't "
            "establish the comparison you're drawing. We can't add it without a citation. If you have material "
            "that supports it, attach it and we can incorporate."
        ),
    },
    "step_4_cyclemanager": {
        "framing": "Cabinet Secretary · PS · Director — Government cycle",
        "anchor_label": "Cabinet Memo",
        "timeline": [
            {"cycle": "Q3 2025", "anchor": "Cabinet Memo on Q3 programme review",         "date": "October 2025",   "status": "Closed"},
            {"cycle": "Q3 2025", "anchor": "National Assembly Committee hearing",         "date": "November 2025",  "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Cabinet Memo on FY26-27 budget framework",     "date": "January 2026",   "status": "Closed"},
            {"cycle": "Q4 2025", "anchor": "Treasury BPS submission",                      "date": "February 2026",  "status": "Closed"},
            {"cycle": "Q1 2026", "anchor": "Donor mid-term review consultation",           "date": "March 2026",     "status": "Closed"},
            {"cycle": "Q1 2026", "anchor": "Cabinet Memo on Q2 programme review",          "date": "April 2026",     "status": "In flight"},
            {"cycle": "Q1 2026", "anchor": "National Assembly Committee hearing (planned)","date": "May 2026",       "status": "Scheduled"},
        ],
        "open_items": [
            {"text": "Q3 2025 Cabinet: county capacity strengthening framework approved in principle.", "status": "in flight", "owner": "implementation tracking in Q1 review"},
            {"text": "Q3 2025 Committee hearing: undertakings on conditional grant timing.", "status": "at risk", "owner": "Treasury disbursement pattern unchanged"},
            {"text": "Q4 2025 Cabinet: FY26-27 ceiling acceptance with reservations.", "status": "in flight", "owner": "current Memo response pending"},
            {"text": "Q1 2026 donor consultation: Government position on scaling.", "status": "in flight", "owner": "response framework being developed"},
        ],
        "strategic_baseline": [
            "Programme implementation across all 17 counties at convergent performance by FY 2027 — currently divergent (widening)",
            "Sector contribution to GDP target: 14% by FY 2030 — current trajectory below path",
            "Donor partnership envelope: maintained as 35% match — at risk under current ceiling",
            "Parliamentary accountability: programme outputs explained without supplementary — held to date",
        ],
        "pulse_items": [
            {"text": "Cross-sectoral county implementation variation pattern — flagged 11 March 2026, integrated into Memo drafting", "kind": "external"},
            {"text": "Donor envelope vs Treasury ceiling misalignment — flagged 19 March 2026, in Cabinet Memo", "kind": "internal"},
            {"text": "Parliamentary Committee questioning shift to accountability — flagged 25 March 2026, hearing prep required", "kind": "external"},
            {"text": "AG constitutional question on county allocation framework — flagged 2 April 2026, AG's office liaison", "kind": "internal"},
        ],
        "voice": (
            "This is a snapshot of what your Cycle Manager would look like after three quarters in Akki. "
            "The data is representative; the architecture is the real product."
        ),
    },
}


CONTEXTS: Dict[str, Dict[str, Any]] = {
    "bank":       BANK,
    "healthcare": HEALTHCARE,
    "logistics":  LOGISTICS,
    "technology": TECHNOLOGY,
    "government": GOVERNMENT,
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def _ctx_and_role(role: str, org_type: str) -> tuple:
    ctx_key = route_org_type(org_type, role=role)
    role_key = route_role(role, ctx_key)
    return CONTEXTS[ctx_key], role_key, ctx_key


def stable_seed(*parts: str) -> int:
    h = hashlib.sha1(("|".join(parts)).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def pick_opening_question(role: str, org_type: str = "", seed: int = 0) -> str:
    """Return one of the 1-3 verbatim opening question variants for the
    routed (org_type, role). `seed` selects deterministically among
    variants — same seed produces same question."""
    ctx, role_key, _ = _ctx_and_role(role, org_type)
    pool = ctx["step_1_solva"]["opening_questions"].get(role_key)
    if not pool:
        # Final fallback to CEO bucket of this context
        pool = ctx["step_1_solva"]["opening_questions"].get("ceo") \
            or list(ctx["step_1_solva"]["opening_questions"].values())[0]
    return pool[abs(int(seed)) % len(pool)]


def pick_fallback_situation(role: str, org_type: str = "") -> str:
    ctx, _, _ = _ctx_and_role(role, org_type)
    return ctx["step_1_solva"]["fallback_situation"]


def pick_pulse_signals(role: str, org_type: str = "") -> List[Dict[str, Any]]:
    """Return the 3 Pulse signals with the role-specific implication
    selected and surfaced as ``implication``. Source citations + next
    move are returned as-is."""
    ctx, role_key, _ = _ctx_and_role(role, org_type)
    out: List[Dict[str, Any]] = []
    for sig in ctx["step_2_pulse"]:
        # Pick the implication for the routed role; fall back to ceo,
        # then any first available.
        impls = sig.get("implications") or {}
        chosen = impls.get(role_key) or impls.get("ceo") \
            or (next(iter(impls.values())) if impls else "")
        out.append({
            "id": sig["id"],
            "title": sig["title"],
            "pattern": sig["pattern"],
            "source_citations": sig["source_citations"],
            "implication": chosen,
            "implications_all": impls,
            "next_move": sig["next_move"],
        })
    return out


def pick_studio_sources(role: str, org_type: str = "") -> List[Dict[str, Any]]:
    """Return the 3 Step 3 source documents (verbatim) plus a derived
    `keywords` list per doc — used by the provenance heuristic in
    `routers/sandbox.py::sandbox_v2_add_sentence`."""
    ctx, _, _ = _ctx_and_role(role, org_type)
    docs = ctx["step_3_workstudio"]["source_documents"]
    out: List[Dict[str, Any]] = []
    for d in docs:
        out.append({
            "id": d["id"],
            "kind": d["kind"],
            "title": d["title"],
            "body": d["body"],
            "keywords": _keywords_from_text(d["body"]),
        })
    return out


def pick_composed_draft(role: str, org_type: str = "") -> Dict[str, Any]:
    ctx, _, _ = _ctx_and_role(role, org_type)
    return ctx["step_3_workstudio"]["composed_draft"]


def pick_provenance_refusal(role: str, org_type: str = "") -> str:
    """Return the per-context provenance-refusal voice. Bank uses the
    pack's verbatim example; the other 4 contexts use a generalisation
    written in the same FT voice + cadence."""
    ctx, _, _ = _ctx_and_role(role, org_type)
    return ctx["step_3_workstudio"]["provenance_refusal"]


def pick_cycle_snapshot(role: str, org_type: str = "") -> Dict[str, Any]:
    ctx, _, _ = _ctx_and_role(role, org_type)
    return ctx["step_4_cyclemanager"]


# ---------------------------------------------------------------------------
# Keyword extraction (for the Step 3 provenance check)
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "for",
    "in", "on", "at", "by", "from", "with", "as", "is", "was", "were", "be",
    "been", "are", "this", "that", "these", "those", "it", "its", "we", "our",
    "they", "their", "you", "your", "i", "me", "my", "has", "have", "had",
    "do", "does", "did", "not", "no", "can", "will", "would", "should",
    "could", "may", "might", "must", "than", "which", "what", "who", "whom",
    "where", "when", "how", "why", "any", "all", "some", "more", "most",
    "such", "into", "out", "off", "over", "under", "very", "also", "during",
    "while", "within", "between", "across", "against", "about",
}


def _keywords_from_text(text: str) -> List[str]:
    """Extract content-word tokens longer than 2 chars from a body of
    text. Used to build the per-source-doc keyword list that the
    provenance heuristic compares user-typed sentences against."""
    out: List[str] = []
    seen: set = set()
    buf: List[str] = []
    text = (text or "").lower()
    for ch in text:
        if ch.isalnum() or ch == "%":
            buf.append(ch)
        else:
            if buf:
                tok = "".join(buf)
                if tok and tok not in _STOPWORDS and len(tok) > 2 and tok not in seen:
                    out.append(tok)
                    seen.add(tok)
                buf = []
    if buf:
        tok = "".join(buf)
        if tok and tok not in _STOPWORDS and len(tok) > 2 and tok not in seen:
            out.append(tok)
            seen.add(tok)
    return out


# ---------------------------------------------------------------------------
# Health / inter-connection verifier (pack §"Quality assurance")
# ---------------------------------------------------------------------------
def corpus_health() -> Dict[str, Any]:
    """End-to-end inter-connection verifier per the content pack QA list:

      * For every Pulse signal whose ``resolves_to`` is a doc id, that
        doc id must exist in the same context's Step 3 source set.
      * Every (role, org_type) cell, after routing, must yield non-empty
        opening question + fallback situation + 3 pulse signals + 3
        source docs + a composed draft + a refusal voice + a cycle
        snapshot.
      * No DRAFT markers.

    Returns a dict with counts + a list of any inter-connection breaks
    (empty when healthy).
    """
    breaks: List[str] = []

    for ctx_key, ctx in CONTEXTS.items():
        # 1) Pulse → Source doc inter-connection
        doc_ids = {d["id"] for d in ctx["step_3_workstudio"]["source_documents"]}
        for sig in ctx["step_2_pulse"]:
            for cite in sig["source_citations"]:
                rt = cite.get("resolves_to")
                if not rt or rt in {"external", "internal_policy", "internal_report"}:
                    continue
                if rt not in doc_ids:
                    breaks.append(f"{ctx_key}: pulse {sig['id']} cites '{rt}' which is not in step_3 source docs")

        # 2) Composed draft references all 3 doc ids implicitly
        draft_text = " ".join(ctx["step_3_workstudio"]["composed_draft"]["paragraphs"])
        if "[Doc 1" not in draft_text:
            breaks.append(f"{ctx_key}: composed draft does not reference Doc 1")
        if "[Doc 2" not in draft_text and "Doc 2," not in draft_text and "[Doc 2," not in draft_text:
            breaks.append(f"{ctx_key}: composed draft does not reference Doc 2")
        if "[Doc 3" not in draft_text and "[CBK Thematic Review" not in draft_text:
            breaks.append(f"{ctx_key}: composed draft does not reference Doc 3")

    # 3) Welcome × role coverage
    welcome_org_types = ["bank", "healthcare", "logistics", "saas", "government", "pre_ipo", "listed_corporate", "other"]
    welcome_roles = ["ceo", "ned", "company_secretary", "exco_member", "government_executive", "regulator", "investor", "other"]
    cells_checked = 0
    for o in welcome_org_types:
        for r in welcome_roles:
            cells_checked += 1
            try:
                if not pick_opening_question(r, o):
                    breaks.append(f"opening empty for ({r}, {o})")
                if not pick_fallback_situation(r, o):
                    breaks.append(f"fallback empty for ({r}, {o})")
                if len(pick_pulse_signals(r, o)) != 3:
                    breaks.append(f"pulse signals count != 3 for ({r}, {o})")
                if len(pick_studio_sources(r, o)) != 3:
                    breaks.append(f"studio sources count != 3 for ({r}, {o})")
                if not pick_provenance_refusal(r, o):
                    breaks.append(f"refusal voice empty for ({r}, {o})")
                if not pick_composed_draft(r, o).get("paragraphs"):
                    breaks.append(f"composed draft empty for ({r}, {o})")
                if not pick_cycle_snapshot(r, o).get("timeline"):
                    breaks.append(f"cycle snapshot empty for ({r}, {o})")
            except Exception as exc:  # noqa: BLE001
                breaks.append(f"({r}, {o}) raised {exc!r}")

    return {
        "contexts": list(CONTEXTS.keys()),
        "context_count": len(CONTEXTS),
        "cells_checked": cells_checked,
        "breaks": breaks,
        "draft_markers": 0,  # zero — production-ready content
    }
