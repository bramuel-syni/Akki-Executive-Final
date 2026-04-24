"""Sandbox sector templates — Phase 2.

Each template parameterises over {company_name}, {currency}, {regulator}.
Dispatched from `sandbox_service.pick_template` via SECTOR_TO_TEMPLATE.

Each template returns:
  {id, label, industry, sector_hint, committees[], documents[], signals[], briefings[]}

Design principles:
- 2–3 documents per template (not more — prospects should skim fast)
- 4–6 seeded signals with real numbers and clear questions
- 1 pre-composed briefing so they see the "here's a draft for your next meeting" moment
- Every string in prospect voice — not vendor speak
"""
from __future__ import annotations
from typing import Any, Dict


# ---------------------------------------------------------------------------
# SaaS / technology
# ---------------------------------------------------------------------------
SAAS_TEMPLATE: Dict[str, Any] = {
    "id": "saas_growth",
    "label": "Mid-stage SaaS / technology",
    "industry": "saas",
    "sector_hint": "B2B SaaS · Enterprise + mid-market",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Revenue recognition, ARR durability, cash burn"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Security, data residency, customer concentration"},
        {"name": "Compensation Committee", "type": "comp", "cadence": "Biannual",
         "focus": "Executive pay, equity refresh, hiring envelope"},
    ],
    "documents": [
        {
            "name": "Board Pack Q4 — Operating Review",
            "description": "CEO letter, ARR build, retention, burn multiples, pipeline.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "{company_name} — Board Pack Q4 · Operating Review\n\n"
                "CEO letter. ARR closed the quarter at {currency}42.8m, up 31% year-on-year. "
                "Net revenue retention dropped from 118% to 104% — the first quarter below "
                "110% in eight. Gross retention held at 92%.\n\n"
                "Pipeline. Top-of-funnel volume is steady; the weakness is on expansion — "
                "seat growth inside existing accounts stalled. Three of the top-10 accounts "
                "are flat or shrinking at renewal.\n\n"
                "Burn. Cash burn of {currency}2.4m/month against {currency}38m on balance "
                "sheet gives 15 months of runway. Hiring paused in November pending a board "
                "decision on the Series C timing. Two senior engineering roles still open.\n\n"
                "Concentration. Top-5 customers now represent 38% of ARR (vs 31% a year ago)."
            ),
        },
        {
            "name": "CFO Memo — Rule of 40",
            "description": "Internal memo on profitability profile and peer benchmarks.",
            "mime_type": "application/pdf",
            "data_trust": "mixed",
            "extracted_text": (
                "CFO Memo — Rule of 40 benchmarking\n\n"
                "{company_name} sits at 31% + (-28%) = 3% on the Rule of 40. Peer median is "
                "22%. The margin compression is driven by (a) hiring front-loaded in H1 at a "
                "higher blended cost than plan, and (b) a pricing discount cohort (the Q3 "
                "renewals at -8% list) that flows through until Q2 next year.\n\n"
                "If we hit the Q1 plan unchanged, we re-base to 18% by year-end. If we do "
                "nothing on pricing discipline, we stay sub-10."
            ),
        },
        {
            "name": "Security & Compliance — Q4 Status",
            "description": "SOC2 Type II, pen-test summary, data-residency commitments.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "Security & Compliance Q4\n\n"
                "SOC2 Type II audit complete — 1 finding (access-review cadence), remediation "
                "due by end of Q1. ISO 27001 initiation planned for H2 next year pending "
                "board budget approval.\n\n"
                "Data residency. 3 enterprise customers have asked for EU-only storage. "
                "Engineering estimate: 1 quarter of work, {currency}380k uplift to AWS bill.\n\n"
                "Pen-test. Full external pen-test completed; 2 medium findings, both closed."
            ),
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "Net revenue retention dropped from 118% to 104% — first sub-110% quarter in eight.",
            "reasoning": "The expansion motor is flagging inside the existing base. Ask management what changed in the top-10 cohort behaviour.",
            "evidence_text": "[doc:0] Net revenue retention dropped from 118% to 104% — the first quarter below 110% in eight.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Customer concentration of 38% in top-5 warrants a real mitigation plan.",
            "reasoning": "This has moved 7pp in a year. A board-level concentration cap conversation is overdue.",
            "evidence_text": "[doc:0] Top-5 customers now represent 38% of ARR (vs 31% a year ago).",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "Cash runway of 15 months assumes current burn — no plan-B scenario tabled.",
            "reasoning": "The board should see a scenario where the Series C slips 2 quarters and what that means for hiring.",
            "evidence_text": "[doc:0] Cash burn of {currency}2.4m/month against {currency}38m on balance sheet gives 15 months of runway.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "EU data-residency would unlock 3 enterprise deals for {currency}380k of spend.",
            "reasoning": "Tight payback if the 3 enterprise deals are weighted. Comp committee should sanity-check the hire plan to deliver it.",
            "evidence_text": "[doc:2] 3 enterprise customers have asked for EU-only storage. Engineering estimate: 1 quarter of work, {currency}380k uplift to AWS bill.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Rule of 40 at 3% vs peer median of 22% — margin re-base hinges on pricing discipline.",
            "reasoning": "The CFO's own memo flags it. Audit Committee should understand the pricing-discount cohort flowing through.",
            "evidence_text": "[doc:1] {company_name} sits at 31% + (-28%) = 3% on the Rule of 40. Peer median is 22%.",
            "confidence": "high", "data_trust": "mixed",
        },
        {
            "type": "opportunity",
            "headline": "ARR growth of 31% is still top-quartile — the board can support decisive moves without panic.",
            "reasoning": "Narrate it that way before the concentration/retention points, so management hears solutions not fear.",
            "evidence_text": "[doc:0] ARR closed the quarter at {currency}42.8m, up 31% year-on-year.",
            "confidence": "medium", "data_trust": "trusted",
        },
    ],
    "briefings": [{
        "title": "For the next Audit Committee — three threads",
        "opening_paragraph": (
            "{company_name} is growing 31% but the shape of the growth has changed. Net "
            "revenue retention dipped below 110%, top-5 concentration rose 7pp, and the "
            "Rule of 40 sits well off peer. None of this is alarm territory — but the "
            "committee should expect deeper narrative on each at the next meeting."
        ),
        "closing_note": "Retention cohort, pricing discipline, and the Series C-slips-2Q scenario.",
    }],
}


# ---------------------------------------------------------------------------
# Logistics / supply chain
# ---------------------------------------------------------------------------
LOGISTICS_TEMPLATE: Dict[str, Any] = {
    "id": "logistics_panafrican",
    "label": "Pan-regional logistics & supply chain",
    "industry": "logistics",
    "sector_hint": "Freight · Distribution · Last-mile",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Consolidation, cross-border tax, revenue recognition"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Operational, cyber (ERP migration), regulatory fragmentation"},
    ],
    "documents": [
        {
            "name": "Board Pack Q4 — Operational Review",
            "description": "5-country operational summary, ERP migration, fleet utilisation.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "{company_name} — Operational Review Q4\n\n"
                "Revenue of {currency}214m across five operating countries, up 18% year-on-year. "
                "EBITDA margin held at 11.4% against a planned 12.8% — the gap driven by fuel "
                "price volatility and a delayed freight-rate pass-through.\n\n"
                "ERP migration. Planned go-live Q2; now slipping to Q3 with an incremental "
                "{currency}3.1m spend. Dual-systems will run for ~4 months. Cyber exposure "
                "during dual-systems period is the single biggest open risk on the register.\n\n"
                "DRC operation. Regulatory filings for H1 complete; H2 filing blocked by a "
                "registration dispute with the customs authority. External counsel engaged."
            ),
        },
        {
            "name": "Risk Register — Top 10",
            "description": "Rated operational risks with owner and next-action.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "Top-10 Risk Register (extract)\n\n"
                "1. Cyber exposure during ERP dual-systems period — HIGH. Owner: CIO. "
                "Quarterly pen-test overdue by 4 months.\n"
                "2. DRC customs registration dispute — MEDIUM-HIGH. Owner: GC. External "
                "counsel engaged; worst case, H2 revenue of {currency}8.4m at risk.\n"
                "3. Fleet maintenance backlog (Kenya + Uganda) — MEDIUM. Owner: COO. 62 "
                "vehicles past service interval. 11 off-road for >30 days.\n"
                "4. Cross-border VAT reconciliation — MEDIUM. Owner: CFO. {regulator} "
                "enquiry pending from last year's filings."
            ),
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "ERP migration dual-systems window introduces 4 months of elevated cyber risk.",
            "reasoning": "Risk Committee should demand the pen-test before dual-systems begin, not after.",
            "evidence_text": "[doc:0] Dual-systems will run for ~4 months. Cyber exposure during dual-systems period is the single biggest open risk on the register.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "DRC customs dispute puts {currency}8.4m of H2 revenue at risk.",
            "reasoning": "Material enough to be a Q4 board agenda item in its own right.",
            "evidence_text": "[doc:1] DRC customs registration dispute — MEDIUM-HIGH. Worst case, H2 revenue of {currency}8.4m at risk.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "Fleet maintenance backlog — 62 vehicles past service interval, 11 off-road over 30 days.",
            "reasoning": "Operating theatre is quietly eroding. Ask for a utilisation delta since Q1.",
            "evidence_text": "[doc:1] 62 vehicles past service interval. 11 off-road for >30 days.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "EBITDA margin 140bps below plan with no pass-through explanation by country.",
            "reasoning": "Fuel volatility is the narrative — ask for the country-level pass-through breakdown.",
            "evidence_text": "[doc:0] EBITDA margin held at 11.4% against a planned 12.8% — the gap driven by fuel price volatility and a delayed freight-rate pass-through.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "18% revenue growth across 5 countries — strongest diversification the group has had.",
            "reasoning": "Narrate the top-line strength before the risk items to keep management constructive.",
            "evidence_text": "[doc:0] Revenue of {currency}214m across five operating countries, up 18% year-on-year.",
            "confidence": "medium", "data_trust": "trusted",
        },
    ],
    "briefings": [{
        "title": "For the next Risk Committee — what to raise",
        "opening_paragraph": (
            "{company_name} is delivering growth but the risk topology is shifting. The "
            "ERP dual-systems window, the DRC customs dispute, and the fleet backlog are "
            "each individually manageable; the board's role is to make sure they aren't "
            "managed in isolation."
        ),
        "closing_note": "ERP pen-test before go-live, DRC counsel engagement, and a consolidated fleet utilisation view.",
    }],
}


# ---------------------------------------------------------------------------
# Healthcare
# ---------------------------------------------------------------------------
HEALTHCARE_TEMPLATE: Dict[str, Any] = {
    "id": "healthcare_provider",
    "label": "Healthcare provider group",
    "industry": "healthcare",
    "sector_hint": "Hospitals · Clinics · Outpatient services",
    "committees": [
        {"name": "Clinical Governance Committee", "type": "clinical", "cadence": "Monthly",
         "focus": "Patient outcomes, incident reporting, clinical audits"},
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Payer mix, provisioning, regulatory reporting"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Clinical, operational, cyber, regulatory"},
    ],
    "documents": [
        {
            "name": "Clinical Outcomes Dashboard — Q4",
            "description": "30-day readmission, mortality, infection rates across facilities.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "{company_name} — Clinical Outcomes Q4\n\n"
                "30-day all-cause readmission rate: 11.2% (target 9.5%). Outlier facility: "
                "North Hospital at 14.1%. Root-cause review ordered by the Clinical Governance "
                "Committee; interim findings pending.\n\n"
                "Hospital-acquired infection rate: 1.8 per 1,000 patient-days (target 1.5). "
                "Driven by two ICU outbreaks in Q3 both now closed.\n\n"
                "Mortality ratio (SHMI): 0.97 — within expected range. No outlier facility."
            ),
        },
        {
            "name": "Board Pack Q4 — Operating Summary",
            "description": "Payer mix, occupancy, receivables, regulatory items.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "Operating Summary Q4\n\n"
                "Revenue of {currency}118m, up 9% YoY. Bed occupancy at 74% (target 78%). "
                "Payer mix: 42% public insurance, 36% private, 18% out-of-pocket, 4% other.\n\n"
                "Receivables. Days sales outstanding rose from 68 to 84 days — driven by a "
                "delay in public-insurance reimbursements. Management has raised with "
                "{regulator} as an industry-wide issue. Cash tight if it persists through Q1.\n\n"
                "Regulatory. One clinical-license renewal in progress for the Coastal Clinic; "
                "expected to close Q1."
            ),
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "North Hospital readmission rate at 14.1% vs group target of 9.5% — outlier requires board visibility.",
            "reasoning": "Clinical Governance has ordered a review; the board should ask to see the interim findings in person.",
            "evidence_text": "[doc:0] Outlier facility: North Hospital at 14.1%. Root-cause review ordered by the Clinical Governance Committee.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "DSO jumped 16 days to 84 — cash could tighten meaningfully if public reimbursement delay persists.",
            "reasoning": "Audit Committee should ask management to model a one-quarter-worse scenario.",
            "evidence_text": "[doc:1] Days sales outstanding rose from 68 to 84 days — driven by a delay in public-insurance reimbursements.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "Bed occupancy at 74% vs target 78% — no root-cause narrative in the pack.",
            "reasoning": "4pp off target with no explanation. Ask for a case-mix breakdown.",
            "evidence_text": "[doc:1] Bed occupancy at 74% (target 78%).",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Hospital-acquired infection rate 20% above target — driven by two Q3 ICU outbreaks.",
            "reasoning": "Clinical Governance should confirm the closure root-cause to prevent recurrence.",
            "evidence_text": "[doc:0] Hospital-acquired infection rate: 1.8 per 1,000 patient-days (target 1.5).",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "Mortality ratio 0.97 is within expected range across every facility — strong clinical quality signal.",
            "reasoning": "Counterweight to the readmission story. Clinical Governance can open with this.",
            "evidence_text": "[doc:0] Mortality ratio (SHMI): 0.97 — within expected range. No outlier facility.",
            "confidence": "medium", "data_trust": "trusted",
        },
    ],
    "briefings": [{
        "title": "For the next Clinical Governance Committee",
        "opening_paragraph": (
            "{company_name}'s clinical outcomes are broadly steady, but two patterns warrant "
            "a structured conversation: the North Hospital readmission outlier, and the "
            "infection-rate tail from Q3. Alongside, the board should track the cash-flow "
            "consequence of the public-insurance reimbursement slowdown."
        ),
        "closing_note": "North Hospital review, infection-outbreak closure confirmation, DSO scenario planning.",
    }],
}


# ---------------------------------------------------------------------------
# Manufacturing
# ---------------------------------------------------------------------------
MANUFACTURING_TEMPLATE: Dict[str, Any] = {
    "id": "manufacturing_industrial",
    "label": "Industrial manufacturer",
    "industry": "manufacturing",
    "sector_hint": "Industrial · Export-exposed",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Inventory, cost recovery, FX exposure"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Safety, supply chain, regulatory"},
    ],
    "documents": [
        {
            "name": "Board Pack Q4 — Operating & Safety Review",
            "description": "Throughput, safety TRIR, inventory, FX exposure.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "{company_name} — Operating & Safety Review Q4\n\n"
                "Throughput at 91% of nameplate, up 3pp on Q3. Inventory days rose from 52 to "
                "68 — driven by a build-up of WIP ahead of the annual maintenance shutdown.\n\n"
                "Safety. TRIR (total recordable incident rate) at 0.42 — best quarter on "
                "record. One serious near-miss at the Eastern plant documented and closed.\n\n"
                "FX. 38% of revenue is hard-currency exports; only 22% is hard-currency "
                "hedged at next-12-month horizon. {regulator} has flagged the exposure "
                "informally during the last compliance visit.\n\n"
                "Regulatory. Environmental discharge permit up for renewal in Q2."
            ),
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "Hard-currency exposure: 38% of revenue, only 22% hedged — {regulator} has flagged informally.",
            "reasoning": "Gap is wide and comes with a regulator signal. Audit Committee should review the hedging mandate.",
            "evidence_text": "[doc:0] 38% of revenue is hard-currency exports; only 22% is hard-currency hedged.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Inventory days rose 16 to 68 — most is WIP ahead of shutdown, but confirm with the floor.",
            "reasoning": "The management narrative is defensible; ask for the Q1 reversal plan.",
            "evidence_text": "[doc:0] Inventory days rose from 52 to 68 — driven by a build-up of WIP ahead of the annual maintenance shutdown.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "Environmental discharge permit renewal in Q2 — no board visibility on preparedness yet.",
            "reasoning": "Single-point-of-failure risk. Risk Committee should see a readiness paper.",
            "evidence_text": "[doc:0] Environmental discharge permit up for renewal in Q2.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "TRIR at 0.42 is the best quarter on record — reinforce with the Eastern plant near-miss closure.",
            "reasoning": "Safety culture signal. Board can publicly acknowledge the progress.",
            "evidence_text": "[doc:0] TRIR at 0.42 — best quarter on record.",
            "confidence": "medium", "data_trust": "trusted",
        },
    ],
    "briefings": [{
        "title": "For the next Audit Committee",
        "opening_paragraph": (
            "{company_name} is operating well: throughput at 91% of nameplate and TRIR at "
            "an all-time low. The board's attention belongs on the hedging gap, the inventory "
            "reversal plan, and the environmental permit renewal — none of which management has "
            "framed adequately in this pack."
        ),
        "closing_note": "Hedging mandate review, Q1 inventory reversal plan, Q2 permit preparedness.",
    }],
}


# ---------------------------------------------------------------------------
# Retail & consumer
# ---------------------------------------------------------------------------
RETAIL_TEMPLATE: Dict[str, Any] = {
    "id": "retail_multicategory",
    "label": "Multi-category retailer",
    "industry": "retail",
    "sector_hint": "Physical + digital retail",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Same-store sales, shrinkage, credit"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Supply chain, cyber, regulatory"},
    ],
    "documents": [
        {
            "name": "Board Pack Q4 — Trading & Operations",
            "description": "Like-for-like sales, margin, digital mix, shrinkage.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "{company_name} — Trading & Operations Q4\n\n"
                "Group LfL sales +4.8%. Grocery +7.2%, general merchandise +1.1%, digital "
                "+22%. Gross margin 28.6%, down 90bps driven by category-mix shift and "
                "promotional intensity in non-food.\n\n"
                "Digital. Digital revenue now 18% of mix (target 20% by year-end). Click-and-"
                "collect penetration 9%, home delivery 11% — home delivery loss-making at "
                "the basket level.\n\n"
                "Shrinkage. Shrinkage rose to 1.8% of sales vs 1.3% last year. Self-checkout "
                "channels over-represented. Loss Prevention has a recovery plan tabled.\n\n"
                "Cyber. Ransomware attempt in October; contained. Root cause: third-party "
                "loyalty-program vendor. Audit Committee briefed."
            ),
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "Shrinkage jumped from 1.3% to 1.8% of sales — Loss Prevention plan needs board test.",
            "reasoning": "Material margin leak. Audit Committee should sanity-check the recovery assumptions.",
            "evidence_text": "[doc:0] Shrinkage rose to 1.8% of sales vs 1.3% last year. Self-checkout channels over-represented.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Home delivery loss-making at basket level — 11% of mix on an unproven unit economic.",
            "reasoning": "The growth cohort runs at a negative margin. Ask for the minimum basket / price-up plan.",
            "evidence_text": "[doc:0] home delivery loss-making at the basket level.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Gross margin down 90bps — promotional intensity in non-food is the narrative.",
            "reasoning": "If it persists two more quarters, it re-bases the plan. Audit Committee to ask for cadence commitment.",
            "evidence_text": "[doc:0] Gross margin 28.6%, down 90bps driven by category-mix shift and promotional intensity in non-food.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Cyber incident root-caused to a loyalty-program vendor — audit third-party access across the estate.",
            "reasoning": "Risk Committee should see a vendor-risk register refresh this quarter.",
            "evidence_text": "[doc:0] Ransomware attempt in October; contained. Root cause: third-party loyalty-program vendor.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "Digital at 18% of mix, growing 22% — on track to hit the year-end 20% target.",
            "reasoning": "Narrate this first — reinforces that the margin pressure is a deliberate investment, not a miss.",
            "evidence_text": "[doc:0] Digital revenue now 18% of mix (target 20% by year-end).",
            "confidence": "medium", "data_trust": "trusted",
        },
    ],
    "briefings": [{
        "title": "For the next Audit Committee — three threads",
        "opening_paragraph": (
            "{company_name}'s trading is strong — +4.8% LfL, digital +22% — but the margin "
            "shape is drifting. Shrinkage, promotional intensity, and the home-delivery basket "
            "are the three items that, together, determine whether next year's guidance holds."
        ),
        "closing_note": "Loss Prevention stress-test, promotional cadence, home-delivery basket economics.",
    }],
}


# ---------------------------------------------------------------------------
# Real estate / construction
# ---------------------------------------------------------------------------
REAL_ESTATE_TEMPLATE: Dict[str, Any] = {
    "id": "real_estate_developer",
    "label": "Real-estate developer / REIT",
    "industry": "real_estate",
    "sector_hint": "Commercial + residential developer",
    "committees": [
        {"name": "Audit Committee", "type": "audit", "cadence": "Quarterly",
         "focus": "Valuation, development cost, debt covenants"},
        {"name": "Risk Committee", "type": "risk", "cadence": "Quarterly",
         "focus": "Construction, contractual, regulatory"},
    ],
    "documents": [
        {
            "name": "Board Pack Q4 — Portfolio & Development",
            "description": "Portfolio NAV, occupancy, pipeline, debt covenants.",
            "mime_type": "application/pdf",
            "data_trust": "trusted",
            "extracted_text": (
                "{company_name} — Portfolio & Development Q4\n\n"
                "Portfolio NAV {currency}612m, +3.4% versus prior-year revaluation. Weighted "
                "average lease expiry 4.8 years. Commercial occupancy 89%, residential 94%.\n\n"
                "Development pipeline. Two projects in flight: Downtown Tower (on time, "
                "within 2% of budget) and Coast Gardens ({currency}7m over budget, 5 months "
                "behind schedule — contractor dispute in arbitration).\n\n"
                "Debt. LTV ratio 42% (covenant 50%). ICR 2.1x (covenant 1.8x). Headroom "
                "tight if Coast Gardens slips further or commercial occupancy drops below 85%.\n\n"
                "Regulatory. Building-code amendment effective Q3 next year; estimated "
                "{currency}11m retrofit cost across the portfolio to comply."
            ),
        },
    ],
    "signals": [
        {
            "type": "risk",
            "headline": "Coast Gardens project 5 months late, {currency}7m over budget — arbitration now material.",
            "reasoning": "Single-project risk is bleeding into group covenants. Risk Committee should see the arbitration timeline.",
            "evidence_text": "[doc:0] Coast Gardens ({currency}7m over budget, 5 months behind schedule — contractor dispute in arbitration).",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Debt covenants have limited headroom — LTV 42% vs 50%, ICR 2.1x vs 1.8x.",
            "reasoning": "Two adverse moves — Coast slipping + commercial dropping below 85% — breach ICR. Stress-test this.",
            "evidence_text": "[doc:0] LTV ratio 42% (covenant 50%). ICR 2.1x (covenant 1.8x). Headroom tight if Coast Gardens slips further or commercial occupancy drops below 85%.",
            "confidence": "high", "data_trust": "trusted",
        },
        {
            "type": "gap",
            "headline": "Building-code retrofit estimated at {currency}11m — not yet in the capex plan.",
            "reasoning": "Known liability becoming a covenant variable. Audit Committee should see the phasing.",
            "evidence_text": "[doc:0] Building-code amendment effective Q3 next year; estimated {currency}11m retrofit cost across the portfolio to comply.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "risk",
            "headline": "Commercial occupancy 89% — a 4pp drop puts ICR under pressure.",
            "reasoning": "Not alarming today but worth stress-modelling against the two weakest assets.",
            "evidence_text": "[doc:0] Commercial occupancy 89%, residential 94%.",
            "confidence": "medium", "data_trust": "trusted",
        },
        {
            "type": "opportunity",
            "headline": "Portfolio NAV +3.4% year-on-year — valuation holding through a flatter market.",
            "reasoning": "Narrate the underlying resilience alongside the Coast Gardens concern.",
            "evidence_text": "[doc:0] Portfolio NAV {currency}612m, +3.4% versus prior-year revaluation.",
            "confidence": "medium", "data_trust": "trusted",
        },
    ],
    "briefings": [{
        "title": "For the next Risk Committee",
        "opening_paragraph": (
            "{company_name}'s portfolio remains resilient but covenant headroom is tightening. "
            "Coast Gardens is now the single-largest discretionary risk the board is carrying, "
            "and the incoming building-code retrofit sits outside the current capex plan. Both "
            "warrant a structured discussion at this quarter's committee."
        ),
        "closing_note": "Coast Gardens arbitration timeline, covenant stress-test, retrofit phasing.",
    }],
}


# ---------------------------------------------------------------------------
# Registry — used by sandbox_service.pick_template
# ---------------------------------------------------------------------------
ALL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "saas_growth":            SAAS_TEMPLATE,
    "logistics_panafrican":   LOGISTICS_TEMPLATE,
    "healthcare_provider":    HEALTHCARE_TEMPLATE,
    "manufacturing_industrial": MANUFACTURING_TEMPLATE,
    "retail_multicategory":   RETAIL_TEMPLATE,
    "real_estate_developer":  REAL_ESTATE_TEMPLATE,
}
