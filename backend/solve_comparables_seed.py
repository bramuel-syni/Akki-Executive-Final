"""AKKI Solve · curated comparable diagnoses (Wave 3 / Triangulation v2).

Each cluster ships with 3-4 anonymised comparable diagnoses. At synthesis
time the engine picks the closest comparables (currently by cluster_id,
optional sector match) and feeds them into the prompt so the model
diagnosis isn't generic — it's grounded in what comparable boards have
done. Wave 3+ will introduce sector-aware similarity search.

Source rule: every comparable must be (a) anonymised — no company names,
(b) traceable to a real public filing or curated case, (c) include a
short 'verdict' on what worked/didn't. The verdict is what makes
triangulation useful, not the case itself.
"""
from __future__ import annotations

from typing import Any, Dict, List


COMPARABLES_V1: List[Dict[str, Any]] = [
    # ─── revenue_underperformance ──────────────────────────────────────
    {
        "id": "cmp_rev_001",
        "cluster_id": "revenue_underperformance",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Mid-cap retail bank missed Q3 by 14%. Initial CEO framing blamed macro; board found the actual cause was a friction-laden new SME onboarding flow shipped in Q2.",
        "what_worked": "Audit committee chair commissioned a 14-day post-mortem with line-of-business heads; reverted the worst friction within a quarter.",
        "what_didnt": "First three meetings post-miss were spent debating the macro story. Board lost a month not asking the activation-rate question.",
        "source_type": "curated",
    },
    {
        "id": "cmp_rev_002",
        "cluster_id": "revenue_underperformance",
        "sector_tag": "consumer_goods",
        "scale_tag": "large_cap",
        "diagnosis_summary": "Large consumer goods firm missed by 9%. Pricing held; mix shifted as customers traded down. The board had been monitoring revenue, not basket composition.",
        "what_worked": "Standing 'mix-and-margin' KPI added to monthly board pack within 60 days.",
        "what_didnt": "CFO defended the existing dashboard for two cycles before admitting it didn't surface the trade-down signal.",
        "source_type": "curated",
    },
    {
        "id": "cmp_rev_003",
        "cluster_id": "revenue_underperformance",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Growth-stage SaaS firm missed ARR by 22%. Diagnosis: net retention had been hidden by gross retention reporting. Churn in the top decile was 3x the average.",
        "what_worked": "Board mandated cohort-level retention reporting; killed the gross-retention headline number.",
        "what_didnt": "VP Sales argued for two quarters that 'pipeline is healthy' before the cohort view forced the conversation.",
        "source_type": "curated",
    },
    # ─── ceo_succession ────────────────────────────────────────────────
    {
        "id": "cmp_succ_001",
        "cluster_id": "ceo_succession",
        "sector_tag": "industrials",
        "scale_tag": "large_cap",
        "diagnosis_summary": "Founder-CEO of a 40-year-old industrial firm announced retirement; the named successor (COO) was technically capable but had never tested at scale on capital allocation or investor relations.",
        "what_worked": "Chair gave the COO 18 months running quarterly investor day prep, including hostile Q&A with non-execs. Successor stepped up without crisis.",
        "what_didnt": "First 6 months wasted on softer development items the COO already had.",
        "source_type": "curated",
    },
    {
        "id": "cmp_succ_002",
        "cluster_id": "ceo_succession",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Bank had a tidy succession plan on paper; nominated successor was a 'safe pair of hands' but had never made a strategic capital allocation call. Board chair refused to name this gap until an external NED forced it onto the agenda.",
        "what_worked": "External NED's intervention forced a real conversation; chair committed to a 12-month stretch programme with the successor running the strategy refresh.",
        "what_didnt": "Two cycles of polite deferral cost the firm six months of preparation time.",
        "source_type": "curated",
    },
    {
        "id": "cmp_succ_003",
        "cluster_id": "ceo_succession",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Founder-CEO insisted on 'no successor needed' framing for two years; board belatedly recognised the firm had no internal candidate ready for an unplanned transition.",
        "what_worked": "Hired an external search firm with a 24-month brief; chair quietly seeded the development conversation without publicly contradicting the founder.",
        "what_didnt": "External hire took 11 months; founder departure forced a 4-month interim chair scramble.",
        "source_type": "curated",
    },
    # ─── strategy_drift ────────────────────────────────────────────────
    {
        "id": "cmp_drift_001",
        "cluster_id": "strategy_drift",
        "sector_tag": "consumer_goods",
        "scale_tag": "large_cap",
        "diagnosis_summary": "18 months into a 3-year strategy, three of four divisions were running their own thing. Diagnosis: strategy was never operationally translated. Each GM had quietly substituted their own goals.",
        "what_worked": "Board demanded a one-page goal cascade per division; differences became visible and arguable for the first time.",
        "what_didnt": "CFO had been signing off on divisional plans without checking against the board strategy. That gap took two years to surface.",
        "source_type": "curated",
    },
    {
        "id": "cmp_drift_002",
        "cluster_id": "strategy_drift",
        "sector_tag": "industrials",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Strategy refresh approved 24 months ago. Execution drift not from disagreement — from the strategy never being made to face the operating constraints.",
        "what_worked": "Chair forced an operating constraints session: each function listed what the strategy actually required they stop doing. Strategy was quietly retired.",
        "what_didnt": "The original consultant-built strategy doc became board folklore; nobody wanted to be the one to admit it had quietly died.",
        "source_type": "curated",
    },
    # ─── risk_blindspot ────────────────────────────────────────────────
    {
        "id": "cmp_risk_001",
        "cluster_id": "risk_blindspot",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Top customer was shopping the firm; everyone knew. Risk register showed nothing. Audit chair refused escalation 'without evidence'.",
        "what_worked": "External NED escalated to chair informally; chair added a 'concentration risk' standing item to the next risk paper, forcing the conversation onto the record.",
        "what_didnt": "Customer left 4 months later. Fault wasn't the loss; fault was the board having no plan because they refused to name the risk.",
        "source_type": "curated",
    },
    {
        "id": "cmp_risk_002",
        "cluster_id": "risk_blindspot",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Cloud provider concentration was 94% on one vendor. Board treated it as 'standard for our sector' — nobody had asked what 'one provider walks away' looked like for the business.",
        "what_worked": "CTO asked to write a one-page DR scenario; the act of writing it made the risk visible.",
        "what_didnt": "Two AGM cycles passed with the risk noted but unowned. CFO eventually took the brief.",
        "source_type": "curated",
    },
    # ─── performance_management ────────────────────────────────────────
    {
        "id": "cmp_perf_001",
        "cluster_id": "performance_management",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "COO 14 months in; KPIs ambiguous; CEO defended; two NEDs flagged. Diagnosis: the CEO had not held the COO accountable on the two outputs that mattered (operations resilience, cost-to-income). Board had been polite.",
        "what_worked": "Chair had a structured 1:1 with the CEO that named the CEO's own gap. Action: CEO committed to monthly written assessment vs the two outputs. Three months later, gaps were undeniable; transition agreed.",
        "what_didnt": "Board had deferred for two cycles. COO wasted 14 months in a role they were unlikely to grow into.",
        "source_type": "curated",
    },
    # ─── capital_allocation ────────────────────────────────────────────
    {
        "id": "cmp_cap_001",
        "cluster_id": "capital_allocation",
        "sector_tag": "industrials",
        "scale_tag": "large_cap",
        "diagnosis_summary": "Three M&A deals approved in 11 months; each defensible in isolation; cumulatively they described a strategy nobody had voted on.",
        "what_worked": "Chair instituted a capital-allocation ratification meeting every 6 months: cumulative shape reviewed against the stated rule.",
        "what_didnt": "Board had no rule until that point. Deal #2 was the one nobody can defend in retrospect.",
        "source_type": "curated",
    },
    # ─── regulatory_change ─────────────────────────────────────────────
    {
        "id": "cmp_reg_001",
        "cluster_id": "regulatory_change",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "New regulation 9 months out. Compliance officer reported 'on track'. Two NEDs spent time with peers in the same regulatory cohort and found the firm was probably 4 months behind.",
        "what_worked": "Audit committee asked compliance officer to demo each control under load. Half didn't survive the demo. 4-month gap closed by escalating early to the regulator.",
        "what_didnt": "Compliance had been reporting paper readiness, not operational readiness. Distinction matters.",
        "source_type": "curated",
    },
    # ─── tech_debt_or_outage ───────────────────────────────────────────
    {
        "id": "cmp_tech_001",
        "cluster_id": "tech_debt_or_outage",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Three outages in 6 months, all 'unrelated'. CTO presented progress decks. Board had no language to challenge.",
        "what_worked": "External NED with engineering background demanded one reliability metric on every monthly board pack. Trend became visible. Diagnosis: under-investment in reliability budget; not talent.",
        "what_didnt": "Each prior outage post-mortem was technical and the board nodded politely. None linked to investment.",
        "source_type": "curated",
    },
    # ─── people_conduct ────────────────────────────────────────────────
    {
        "id": "cmp_cond_001",
        "cluster_id": "people_conduct",
        "sector_tag": "industrials",
        "scale_tag": "large_cap",
        "diagnosis_summary": "Anonymous letter alleging conduct by named exec. Chair held it 11 days before next meeting. Board split.",
        "what_worked": "Chair instructed external counsel to triage immediately; separated allegation, evidence, and inference before the board meeting; meeting decided process, not outcome.",
        "what_didnt": "First 4 days lost debating whether to engage external counsel at all.",
        "source_type": "curated",
    },
    {
        "id": "cmp_cond_002",
        "cluster_id": "people_conduct",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Pattern of three exits from a single team in 14 months. HR explained each separately; no one had stitched them. NED audit flagged the cluster.",
        "what_worked": "Chair commissioned a confidential listening exercise with the remaining team; surfaced a manager-conduct theme HR had under-weighted.",
        "what_didnt": "HR's quarterly people deck never showed clustered exits per manager. The dashboard hid the signal.",
        "source_type": "curated",
    },
    # ─── ma_thesis ─────────────────────────────────────────────────────
    {
        "id": "cmp_ma_001",
        "cluster_id": "ma_thesis",
        "sector_tag": "financial_services",
        "scale_tag": "large_cap",
        "diagnosis_summary": "$300m acquisition on the table. Thesis sound. Two NEDs uneasy without being able to articulate why. Diagnosis (in retrospect): the firm had no integration capacity left after two prior deals.",
        "what_worked": "Chair postponed approval and asked for an integration capacity audit. Audit found bandwidth was the binding constraint. Deal restructured to a 9-month delay.",
        "what_didnt": "If the chair had not pushed back, the deal would have closed and integration would have failed publicly.",
        "source_type": "curated",
    },
    {
        "id": "cmp_ma_002",
        "cluster_id": "ma_thesis",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Bolt-on acquisition pitched as a customer-base play; deal team argued cross-sell math. Two NEDs asked what the target's churn looked like at month 13 (post-typical contract roll-off). Nobody knew.",
        "what_worked": "Board paused 6 weeks for a churn deep-dive on the target's actual cohorts; revealed mid-30% churn at renewal — the cross-sell math collapsed.",
        "what_didnt": "Target had been on the table for 11 months and the question was never asked until it was almost too late.",
        "source_type": "curated",
    },
    # ─── board_dynamics ────────────────────────────────────────────────
    {
        "id": "cmp_dyn_001",
        "cluster_id": "board_dynamics",
        "sector_tag": "any",
        "scale_tag": "any",
        "diagnosis_summary": "Same strategic question debated across three meetings; same NED dominated; chair declined to redirect. Board was not deciding — it was performing deliberation.",
        "what_worked": "SID held a private session with the chair and the dominating NED separately; agenda discipline imposed; decision made in next meeting.",
        "what_didnt": "Pattern had been visible for 18 months. Last evaluation flagged it; no one had standing to enforce.",
        "source_type": "curated",
    },
    {
        "id": "cmp_dyn_002",
        "cluster_id": "board_dynamics",
        "sector_tag": "any",
        "scale_tag": "any",
        "diagnosis_summary": "New chair, three years in, had quietly let the audit chair drift into running risk discussions too. Risk committee chair was technically still in role but had no air time. Board was running on two committees instead of three.",
        "what_worked": "Annual evaluation was structured to ask each committee chair what they actually owned in the room; gap surfaced; chair re-assigned risk floor time within a quarter.",
        "what_didnt": "The evaluation the prior year had been process-only ('did we hold the meetings?') and missed the substance.",
        "source_type": "curated",
    },
    # ─── founder_transition ────────────────────────────────────────────
    {
        "id": "cmp_fnd_001",
        "cluster_id": "founder_transition",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Founder-chair stepped back 14 months ago. Three of last six material decisions re-litigated by them. Professional CEO patient but eroded.",
        "what_worked": "External NED + SID drafted a written 'role contract' specifying when the founder may re-engage and when not. Founder signed; CEO regained authority within 90 days.",
        "what_didnt": "Founder wasn't malicious — they hadn't realised the pattern. Earlier intervention would have spared 14 months.",
        "source_type": "curated",
    },
    {
        "id": "cmp_fnd_002",
        "cluster_id": "founder_transition",
        "sector_tag": "consumer_goods",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Family-firm founder transitioning to non-family CEO after 30 years. Family shareholders kept calling individual board members between meetings to lobby on operating questions. CEO unable to set direction.",
        "what_worked": "Chair instituted a 'one channel' rule: family questions go through the chair, not individual NEDs. Took 6 months to enforce socially but the CEO got the runway.",
        "what_didnt": "First 9 months post-transition were chaos because the rule was implicit, not written.",
        "source_type": "curated",
    },
    # ─── performance_management — second comparable ────────────────────
    {
        "id": "cmp_perf_002",
        "cluster_id": "performance_management",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Head of Engineering 18 months in; technically competent; team morale eroding. CEO kept describing them as 'finding their stride'. Two QBRs in a row missed delivery commitments by ~30%.",
        "what_worked": "Chair asked the CEO to write a one-page assessment against the role's two non-negotiables (shipping cadence + retention). Writing it forced clarity. Transition agreed within the quarter.",
        "what_didnt": "Pattern had been clear at month 9. Polite deferral cost the org 9 months of execution.",
        "source_type": "curated",
    },
    # ─── capital_allocation — second comparable ────────────────────────
    {
        "id": "cmp_cap_002",
        "cluster_id": "capital_allocation",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Board approved a buyback at the same meeting it approved a fresh capex programme. Each defensible standalone; together they over-committed the balance sheet.",
        "what_worked": "CFO required, in subsequent quarters, that any capital-deployment paper carry a one-page 'cumulative posture' summary. Forced the board to see total commitment before approving the next slice.",
        "what_didnt": "The first two quarters post-discovery, the cumulative summary was prepared but not actually read in the room. Discipline lagged the policy by 6 months.",
        "source_type": "curated",
    },
    # ─── regulatory_change — second comparable ─────────────────────────
    {
        "id": "cmp_reg_002",
        "cluster_id": "regulatory_change",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "EU AI Act compliance treated as a legal box-tick by the management team. Two NEDs (one ex-regulator) flagged that the obligations actually changed how the product worked, not just how it was documented.",
        "what_worked": "Audit chair commissioned a product-team walk-through showing each obligation mapped to a code path. Half the obligations had no owner. Mapping forced a real engineering plan.",
        "what_didnt": "Initial 'compliance dashboard' was green across the board. Green meant 'we have a policy', not 'the product behaves correctly'. Distinction is everything.",
        "source_type": "curated",
    },
    # ─── tech_debt_or_outage — second comparable ───────────────────────
    {
        "id": "cmp_tech_002",
        "cluster_id": "tech_debt_or_outage",
        "sector_tag": "financial_services",
        "scale_tag": "mid_cap",
        "diagnosis_summary": "Core banking platform 11 years old; CTO had asked for a modernisation programme three years running and been deferred. Two unrelated outages in one quarter forced the conversation.",
        "what_worked": "Audit chair re-framed the ask as a 'risk paper' rather than 'IT spend' — which moved the conversation from CFO budget gating to board risk gating. Programme approved within two cycles.",
        "what_didnt": "The CTO had been making the case in operational language to financial decision-makers. The translation was missing.",
        "source_type": "curated",
    },
    # ─── strategy_drift — third comparable ─────────────────────────────
    {
        "id": "cmp_drift_003",
        "cluster_id": "strategy_drift",
        "sector_tag": "tech_saas",
        "scale_tag": "growth",
        "diagnosis_summary": "Series-C SaaS firm pivoted strategy at every board meeting based on the loudest customer story; no through-line; team fatigue rising; sales cycle lengthening.",
        "what_worked": "Chair imposed a 'no new strategic direction without a written 4-page memo' rule. Memos surfaced the pattern; reduced pivots to one per year; sales cycle re-stabilised in 9 months.",
        "what_didnt": "The pivot pattern had been visible to mid-management for 18 months. Board only noticed when revenue lagged.",
        "source_type": "curated",
    },
]


async def seed_solve_comparables(db) -> Dict[str, Any]:
    """Idempotent — only inserts comparables not already present by id."""
    inserted = []
    for c in COMPARABLES_V1:
        existing = await db.solve_comparables.find_one({"id": c["id"]}, {"_id": 0, "id": 1})
        if existing:
            continue
        await db.solve_comparables.insert_one({**c})
        inserted.append(c["id"])
    return {"seeded_count": len(inserted), "ids": inserted}
