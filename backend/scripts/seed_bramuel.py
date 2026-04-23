"""Seed test data for bramuel@syni.ai.

Loads personas and operational data from:
  - AKKI_Test_Data_01_Personas_and_Contexts.docx
  - AKKI_Test_Data_02_Operational_Data.xlsx

Sets up:
  - 3 NED personal contexts (Tuli Financial Group, Mawingu Logistics, Safiri Telecom)
  - 1 Executive personal context (reuses the existing default 'Bramuel's Context' →
    renamed to 'Tuli Financial Group (CFO)')
  - Context Objects marked completed for each, mirroring Ruth's 7-question audit
  - Documents per context with extracted_text that AKKI can ground on
  - Pre-generated signals for each NED board (no LLM call needed — seeded directly)

Idempotent-ish: skips creation if a context with the same name is already present
for this account.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

TARGET_EMAIL = "bramuel@syni.ai"

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _iso(d: datetime) -> str:
    return d.isoformat()


# ---------------------------------------------------------------------------
# CONTEXTS (from AKKI_Test_Data_01)
# ---------------------------------------------------------------------------
NED_CONTEXTS = [
    {
        "name": "Tuli Financial Group",
        "type": "ned_personal",
        "industry": "banking",
        "sector": "Multi-vehicle (banking, asset mgmt, insurance, fintech)",
        "jurisdiction": "Kenya",
        "sub_role": "admin",  # Audit Committee Chair
        "answers": {
            "q1_role": "Independent Director · Chair of Audit Committee",
            "q2_meeting_cadence": "Monthly (holding co); quarterly (audit & risk committees)",
            "q3_focus_areas": "Provisioning adequacy · capital ratios · regulatory reporting · audit findings · succession",
            "q4_committees": "Audit Committee (Chair), Risk Committee (Member), Nominations Committee (Member)",
            "q5_prior_concerns": "Loan book growth outpacing provisioning (Q2); Tuli Digital profitability (Q1, Q3); cyber exposure (Q3); Head of Treasury retention (informal)",
            "q6_lens_preference": "Audit committee lens — numerical discipline, regulatory exposure, same-page contradictions",
            "q7_analytical_style": "Reads every pack in full. Notes on paper first. Paid for pointed opinions. Numbers must be defensible.",
        },
    },
    {
        "name": "Mawingu Logistics",
        "type": "ned_personal",
        "industry": "logistics",
        "sector": "Pan-African logistics & supply chain",
        "jurisdiction": "Kenya",
        "sub_role": None,
        "answers": {
            "q1_role": "Independent Director · Member of Risk & Audit Committees",
            "q2_meeting_cadence": "Quarterly (full board, audit, risk)",
            "q3_focus_areas": "Operational risk across 5 countries · cross-border tax & compliance · cyber (ERP migration) · IPO readiness",
            "q4_committees": "Risk Committee, Audit Committee",
            "q5_prior_concerns": "ERP migration overrun (Q1, Q2); DRC operational risk framework (Q2); IPO capital adequacy (Q3); cyber exposure during ERP migration (Q3)",
            "q6_lens_preference": "Pure NED lens — operational topology, regulatory fragmentation across jurisdictions",
            "q7_analytical_style": "Cross-references past packs. Looks for risk topology shifts. Paid to notice board-management gap.",
        },
    },
    {
        "name": "Safiri Telecom",
        "type": "ned_personal",
        "industry": "telco",
        "sector": "Mobile · fixed · mobile money",
        "jurisdiction": "Kenya",
        "sub_role": "admin",  # Risk Committee Chair
        "answers": {
            "q1_role": "Independent Director · Chair of Risk Committee",
            "q2_meeting_cadence": "Quarterly (full board); monthly (risk committee)",
            "q3_focus_areas": "Cybersecurity posture · regulatory (CAK & Competition Authority) · mobile money agent risk · data privacy · customer concentration",
            "q4_committees": "Risk Committee (Chair), Audit Committee (Member)",
            "q5_prior_concerns": "Mobile money AML framework (Q1); 5G capital plan stress-test (Q2); CTO key-person risk (Q2); cyber exposure (Q3 — pattern with Mawingu & Tuli)",
            "q6_lens_preference": "Risk committee lens — cyber topology, regulatory exposure, concentration risk",
            "q7_analytical_style": "Same as other boards — evidence-grounded, paid to ask the single question that reveals oversight.",
        },
    },
]

EXEC_CONTEXT = {
    "name": "Tuli Financial Group (CFO)",
    "type": "executive_personal",
    "industry": "banking",
    "sector": "Financial services holding co",
    "jurisdiction": "Kenya",
    "answers": {
        "q1_role": "Group Chief Financial Officer",
        "q2_meeting_cadence": "Monthly board pack; weekly ExCo; Thursday standing call with each direct report",
        "q3_focus_areas": "Board pack numerical integrity · provisioning · Tuli Digital profitability · cyber/operational risk · Treasury succession · quarterly earnings quality",
        "q4_direct_reports": "11 (Heads of Finance, Treasury, IR, Risk, Credit, FP&A, Tax, Internal Audit, Procurement, 2 subsidiary finance business partners)",
        "q5_prior_board_feedback": "Ruth (NED) has flagged: provisioning (Q2), Tuli Digital path-to-profit (Q1, Q3), cyber (Q3), Treasury retention (informal to CEO)",
        "q6_lens_preference": "Pre-Board Preparation — run pack 10 days before meeting, see what NEDs flag",
        "q7_analytical_style": "A board surprise is a CFO failure. Reviews every number personally. Rewrites vague or defensive narrative.",
    },
}


# ---------------------------------------------------------------------------
# DOCUMENTS per context (plain-text seed)
# ---------------------------------------------------------------------------
DOC_TULI_CONTEXT_BRIEF = """TULI FINANCIAL GROUP — CONTEXT BRIEF FOR THE BOARD

Tuli Financial Group is a mid-tier listed financial services group on the NSE.
Vehicles: Tuli Bank (commercial banking), Tuli Asset Management, Tuli Insurance,
Tuli Digital (mobile money, loss-making, third year post-launch).

JURISDICTION & REGULATION
Primary regulator Central Bank of Kenya (CBK) for Tuli Bank.
Capital Markets Authority (CMA) for listing and asset management.
Insurance Regulatory Authority (IRA) for Tuli Insurance.
Communications Authority of Kenya (CAK) for Tuli Digital mobile money.

COMPETITIVE POSITION
Principal competitors: KCB Group, Equity Group, Cooperative Bank, NCBA, I&M.
Market pressures: NIM compression, digital lending competition, inflation-driven
pressure on affordability, analyst scrutiny on quarterly earnings quality.

BOARD FOCUS THIS CYCLE (as of December 2025)
1. Provisioning adequacy — loan book grew 18% YoY while provisioning stock rose
   only ~6%. Coverage ratio fell from 74% to 44%. Ruth (Audit Chair) flagged this
   in Q2 and will flag again.
2. Tuli Digital path to profitability — still loss-making, though narrowing from
   USD 0.9m monthly to USD 0.6m. Board patience thin.
3. Cyber exposure — one successful intrusion contained in September. Attempted
   intrusions rising. Systems-patching SLA dropped from 96% to 90% in Sep.
4. Deposit concentration — top 20 depositors rose from 17.8% → 24.0% of deposits.
5. Treasury succession — attrition rose from 4.5% to 16.5% annualised. Head of
   Treasury a recruitment target for competitors.
"""

DOC_TULI_GROUP_SUMMARY = """TULI FINANCIAL GROUP — GROUP SUMMARY KPIs · FY 2025

All figures in USD millions unless stated.

REVENUE & PROFITABILITY
Group revenue trended from 25.8 (Jan) to 27.5 (Dec). Total FY revenue 322.5.
Operating expenses rose from 12.1 (Jan) to 14.3 (Dec). FY opex 157.9.
Group cost-to-income ratio drifted upward from 48.0% (Jan) to 53.1% (Dec).
Net Interest Margin (Bank) compressed from 6.8% to 5.9%.
Group net margin 18.5% (Jan) → 16.5% (Dec).
ROA annualised 2.2% → 1.7%. ROE annualised 23.4% → 16.5%.

CAPITAL
Group tangible equity grew from 205 (Jan) to 247 (Dec).
Capital Adequacy Ratio stable near 17.0% all year.
Tier 1 ratio at Bank declined from 15.2% (Jan) to 14.3% (Dec).

KEY DRIVERS OF PROFIT DETERIORATION
1. NIM compression at Tuli Bank — asset yields lagging deposit costs especially
   after Q2 policy rate changes.
2. Operating expense growth — digital platform investments + wage inflation on
   Q3 compensation review.
3. Tuli Digital continues to consume group net income (~USD 9m loss FY).

BRIGHT SPOTS
Tuli Insurance combined ratio improved from 96.3% (Jan) to 83.6% (Dec).
Tuli Asset Management AUM grew steadily from 1,820 to 2,005 (+10%).
"""

DOC_TULI_BANK = """TULI BANK — COMMERCIAL BANKING OPERATIONAL PACK · FY 2025

BALANCE SHEET
Gross loan book grew from 1,850 (Jan) to 2,183 (Dec) — ~18% YoY.
Total deposits grew from 2,420 to 2,665 — ~10% YoY.
Loan-to-deposit ratio drifted upward, closing at 81.9%.

ASSET QUALITY
Non-performing loans rose from 74 (Jan) to 131 (Dec) — almost doubled.
NPL ratio 4.0% → 6.0% over the year.
Watch-list loans 48 → 103.
Restructured loans 32 → 52.
Loan loss provisions (stock) rose only from 55 → 58.
COVERAGE RATIO FELL FROM 74.3% TO 44.3%.
Loan impairment charge (P&L) nearly tripled from 1.2 to 3.5 monthly.

THIS IS THE CENTRAL BOARD QUESTION: provisioning has NOT kept pace with book
growth or with deterioration in asset quality. The audit committee (Ruth Kamau,
Chair) is expected to raise this at the next meeting.

NET INTEREST INCOME AND MARGIN
Net Interest Income monthly 45 → 63 with volatility. FY total 662.
Net Interest Margin compressed from 6.8% to 5.9%. Asset repricing lagged
deposit cost repricing, especially from Q3 policy rate changes.

DEPOSIT CONCENTRATION
Top 20 depositors rose from 17.8% to 24.0% of total deposits.
This is a material concentration risk and merits a separate funding diversification plan.
"""

DOC_TULI_DIGITAL = """TULI DIGITAL — MOBILE MONEY SUBSIDIARY · FY 2025

USAGE
Registered customers 1.24m → 1.94m (+55%).
Monthly active users 620k → 1,060k (+71%).
Transaction volume 82 → 174 (USD m).

REVENUE
Transaction fees 1.4 → 2.2. Float income 0.3–0.4. Total revenue 2.1 → 3.0.

COSTS & RESULT
Operating expenses 3.0 → 3.6.
Net result remained loss-making ALL YEAR: -0.9 (Jan) → -0.6 (Dec).
FY net loss USD 9m.

BOARD TENSION
This is the third year post-launch. The original business case assumed
break-even by month 24; we are now at month 40 still loss-making. Ruth has
raised the path-to-profit question twice (Q1 and Q3) and we owe the board a
definitive view at the next meeting:
  (a) accelerate to profitability by end-2026 with defined milestones, or
  (b) strategic options — pause new features, regional partnership, divestment.
Narrowing losses are a weak signal; we need a milestone-based plan.
"""

DOC_TULI_RISK = """TULI FINANCIAL GROUP — RISK METRICS · FY 2025

CYBER
Attempted intrusions (detected) rose from 145/mo (Jan) to 228/mo (Dec).
FY attempted intrusions 2,321.
ONE SUCCESSFUL INTRUSION in September 2025 — contained the same day, no
customer data exfiltrated per forensic review. Discloseable event logged.
Systems patching SLA compliance: 96% → 90% in Sep, recovered to 94% by Dec.
FY average patching compliance 93.5%.

OPERATIONAL RISK
Level-3 (minor) events 1–4 per month; no Level-1 or Level-2 events.
Operational losses 28k (Jan) rising to a 215k spike in Sep (correlates with
cyber incident remediation) and settling at 55k in Dec. FY total 843k.

REGULATORY
CBK reporting compliance score 96% → 94%. CMA stable at ~100%.
Open internal audit findings: 3 → 5–6 by year-end.
Open external audit findings: 8 → 19 (note: rising steadily, merits discussion).

DEPOSIT CONCENTRATION (also in Tuli Bank pack)
Top 20 depositors 17.8% → 24.0% of total deposits.
"""

DOC_TULI_PEOPLE = """TULI FINANCIAL GROUP — PEOPLE METRICS · FY 2025

HEADCOUNT
Total group FTE grew steadily from 2,848 (Jan) to 3,035 (Dec).

ATTRITION
Group annualised attrition stable around 11–13%.

TREASURY TEAM — KEY CONCERN
Treasury team annualised attrition ROSE FROM 4.5% (Jan) TO 16.5% (Dec).
Treasury team productivity index (weekly trade execution quality + P&L
attribution accuracy) declined through Q3:
  Trade execution quality: 0.92 → 0.85 (Aug) → 0.82 (Sep) → recovered to 0.90.
  P&L attribution accuracy: 0.96 → 0.91 (Aug) → 0.88 (Sep) → 0.95 (Dec).
This is a material key-person risk. The Head of Treasury is a known
recruitment target. No obvious internal successor has been groomed.

DIGITAL TEAM
Annualised attrition 11.2% → 13.5%. Less acute but worth watching given
strategic investment thesis.
"""

DOC_TULI_INSURANCE = """TULI INSURANCE — UNDERWRITING & INVESTMENT · FY 2025

Gross Written Premium grew from 5.2 to 6.1 USDm monthly. FY GWP 67.5.
Net earned premium 4.4 → 5.2.
Claims incurred remarkably stable at 2.7–2.8 per month.
Loss ratio improved from 63.6% (Jan) to 51.9% (Dec).
Expense ratio stable at ~32%.
COMBINED RATIO IMPROVED FROM 96.3% TO 83.6%. This is genuinely good operational work.
Investment income 0.6 → 0.7 (modest but steady).

Segment mix stable: Motor 45%, Fire & property 24%, Liability 16%, Marine 9%, Other 6%.
"""

DOC_MAWINGU_BRIEF = """MAWINGU LOGISTICS — CONTEXT BRIEF

Pan-African private logistics & supply chain company (trucking, warehousing,
last-mile). HQ Kenya. Operations in Kenya, Uganda, Tanzania, Rwanda, DRC.

STATUS: pre-IPO, growth stage, regional expansion underway.
Principal competitors: Sendy, Lori Systems, East Africa Logistics Platform.
Market pressures: fuel costs, currency volatility across 5 operating countries,
regulatory fragmentation.

BOARD FOCUS THIS CYCLE
1. ERP system migration — overrun flagged by Ruth in Q1 and Q2. Current status:
   90% of modules live; finance reconciliation module still on legacy system.
   Target go-live now end of Q1 2026 (was end Q4 2025).
2. DRC operational risk framework — sanctions screening, counterparty KYC and
   permit compliance — gap analysis requested by Ruth in Q2 delivered to
   Risk Committee.
3. IPO readiness — capital adequacy and governance uplift for listing in 2027.
4. CYBER DURING ERP MIGRATION — the migration has opened exposure windows.
   Ruth flagged this in Q3 as part of a Cross-Board pattern with Tuli and
   Safiri.

PRIOR CONCERNS ROLLFORWARD
  Q1 — ERP migration overrun
  Q2 — ERP migration overrun (returned); DRC operational risk framework
  Q3 — IPO readiness capital adequacy; cyber exposure during ERP migration
"""

DOC_SAFIRI_BRIEF = """SAFIRI TELECOM — CONTEXT BRIEF

Listed mid-tier telecom on the NSE. Mobile · fixed · mobile money.
Principal competitors: Safaricom (dominant), Airtel Kenya, Telkom Kenya.
Market pressures: Safaricom dominance, 5G rollout costs, mobile money regulation,
fibre expansion capital intensity.

BOARD FOCUS THIS CYCLE
1. Cybersecurity posture — Risk Committee (Ruth is Chair) owns this file.
2. Regulatory exposure — Communications Authority of Kenya; Competition Authority
   ongoing mobile money interoperability inquiry.
3. Mobile money agent network risk — KYC, fraud, AML framework update completed
   Q1; monitoring ongoing.
4. Data privacy compliance — Kenya Data Protection Act, GDPR-style enforcement.
5. Customer concentration in enterprise segment — top 10 enterprise customers
   represent ~34% of enterprise revenue.
6. KEY PERSON RISK on the CTO — succession not yet formalised.

PRIOR CONCERNS ROLLFORWARD
  Q1 — Mobile money AML framework
  Q2 — 5G capital plan stress-test; CTO key-person risk
  Q3 — Cyber exposure (aligned with Mawingu and Tuli — Cross-Board Pulse flag)
"""

DOC_SAFIRI_CYBER = """SAFIRI TELECOM — CYBER THREAT BRIEFING · Q4 2025

SUMMARY
Attempted intrusions against Safiri infrastructure rose 38% QoQ. No successful
breach in Safiri infrastructure this quarter. Mobile money platform remains the
highest-value target.

AGENT NETWORK
7,400 agents active. AML framework update deployed Q1 2025.
3 agent accounts frozen Q4 on suspicious transaction patterns.

RECOMMENDATIONS
1. Complete CTO succession plan by end Q1 2026 (RED status on Risk Committee
   tracker).
2. Pen-test the mobile money stack externally once 5G rollout crosses 60%
   coverage to catch rollout-window exposures.
3. Revisit data-classification framework against new DPA guidance expected Q2.
"""


# ---------------------------------------------------------------------------
# SIGNALS (seeded directly — realistic, grounded in the data above)
# ---------------------------------------------------------------------------
def signals_for_tuli(doc_ids: dict) -> list:
    """doc_ids: {'bank': ..., 'group': ..., 'digital': ..., 'risk': ..., 'people': ..., 'insurance': ...}"""
    return [
        {
            "type": "risk", "headline": "Provisioning is not keeping pace with loan book growth — coverage ratio now 44%",
            "summary": "Gross loan book grew 18% YoY while loan loss provisions stock rose only ~6%. NPL ratio moved from 4.0% to 6.0% and coverage ratio collapsed from 74% to 44%. This is the single most material audit-committee question for the next meeting. [doc:{bank}]",
            "confidence": "high",
            "doc_ids": [doc_ids["bank"]],
        },
        {
            "type": "risk", "headline": "Head of Treasury retention risk is now visible in productivity metrics",
            "summary": "Treasury team annualised attrition rose from 4.5% to 16.5% through 2025 and productivity metrics (trade execution quality, P&L attribution accuracy) dipped materially in Aug–Sep. No named internal successor. Key-person risk should be escalated to Nominations Committee. [doc:{people}]",
            "confidence": "high",
            "doc_ids": [doc_ids["people"]],
        },
        {
            "type": "risk", "headline": "Deposit concentration rising — top 20 depositors now 24% of total deposits",
            "summary": "Concentration in the top 20 depositors increased from 17.8% to 24.0% of total deposits, driving funding fragility even though headline deposit growth looks healthy (+10% YoY). A depositor diversification plan should accompany the next liquidity report. [doc:{bank}]",
            "confidence": "medium",
            "doc_ids": [doc_ids["bank"]],
        },
        {
            "type": "gap", "headline": "Tuli Digital needs a milestone-based profitability plan, not just narrowing losses",
            "summary": "Tuli Digital remained loss-making every month of FY2025 (USD 9m full-year). Narrowing losses (-0.9 to -0.6) are a weak signal; the board has now asked twice (Q1 and Q3) for a path-to-profit. A binary decision (accelerate with milestones vs. strategic options) is owed at the next meeting. [doc:{digital}]",
            "confidence": "high",
            "doc_ids": [doc_ids["digital"]],
        },
        {
            "type": "risk", "headline": "September cyber incident — contained, but open external audit findings have risen from 8 to 19",
            "summary": "One successful intrusion in September was contained within 24h with no customer-data exfiltration. Systems-patching SLA dipped to 90% the same month (from 96%). More broadly, open external audit findings rose from 8 to 19 across the year — a trajectory that warrants a structured remediation plan. [doc:{risk}]",
            "confidence": "medium",
            "doc_ids": [doc_ids["risk"]],
        },
        {
            "type": "opportunity", "headline": "Tuli Insurance combined ratio improved from 96% to 84% — a genuine operational win",
            "summary": "Loss ratio fell from 63.6% to 51.9% while expense ratio held at ~32%, driving combined ratio from 96.3% to 83.6%. This is a material profitability uplift and worth both recognising publicly and probing for sustainability drivers (mix, pricing, claims management). [doc:{insurance}]",
            "confidence": "high",
            "doc_ids": [doc_ids["insurance"]],
        },
    ]

def signals_for_mawingu(doc_id: str) -> list:
    return [
        {"type": "risk", "headline": "ERP migration overrun has persisted through 3 consecutive quarters",
         "summary": "The finance reconciliation module remains on the legacy system with a revised go-live of end Q1 2026 — now two quarters past the original target. Board has flagged this in Q1, Q2, and Q3. A dedicated recovery plan with budget overrun disclosure is owed at the next meeting. [doc:{d}]",
         "confidence": "high", "doc_ids": [doc_id]},
        {"type": "risk", "headline": "Cyber exposure during ERP migration windows — escalation from Q3",
         "summary": "The migration has opened intermittent exposure windows during cut-overs. No breach reported, but this is part of a Cross-Board pattern (Tuli had a contained breach in Sep; Safiri saw a 38% QoQ rise in attempted intrusions). [doc:{d}]",
         "confidence": "medium", "doc_ids": [doc_id]},
        {"type": "gap", "headline": "IPO capital adequacy assessment not yet formalised",
         "summary": "IPO readiness was raised in Q3 but no formal capital adequacy stress-test has been tabled. Listing targeted for 2027 — the capital plan and governance uplift need to be on the next audit-committee agenda. [doc:{d}]",
         "confidence": "medium", "doc_ids": [doc_id]},
    ]

def signals_for_safiri(briefs: list) -> list:
    b, c = briefs  # briefing_id, cyber_id
    return [
        {"type": "risk", "headline": "CTO succession plan is RED on the Risk Committee tracker",
         "summary": "The CTO key-person risk was flagged in Q2. No successor has been named; the tracker is still RED at end Q4. This is the single highest-probability disruptive event on the Risk Committee register. [doc:{b}]",
         "confidence": "high", "doc_ids": [b]},
        {"type": "risk", "headline": "Cyber signal is now a Cross-Board pattern — Safiri, Mawingu, Tuli all exposed",
         "summary": "Attempted intrusions rose 38% QoQ. Tuli had a contained breach in September. Mawingu has ERP-migration exposure. The pattern warrants a coordinated response playbook if Ruth's three boards are to share threat intelligence (within governance constraints). [doc:{c}]",
         "confidence": "medium", "doc_ids": [c]},
        {"type": "opportunity", "headline": "AML framework deployed Q1 has proven effective — 3 agent accounts frozen in Q4 on anomaly detection",
         "summary": "The mobile money AML framework update (Ruth raised Q1) produced 3 agent-account freezes in Q4 based on the new anomaly patterns. This validates the framework and supports a case for extending the approach to enterprise channel AML controls. [doc:{c}]",
         "confidence": "medium", "doc_ids": [c]},
    ]


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------
async def seed():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    acc = await db.accounts.find_one({"email": TARGET_EMAIL}, {"_id": 0})
    if not acc:
        print(f"Account {TARGET_EMAIL} not found. Please register first via the UI.")
        return
    account_id = acc["id"]
    print(f"✅ Account found: {acc['email']} · id={account_id} · declared_role={acc.get('declared_role')}")

    # Ensure dual role
    if acc.get("declared_role") != "dual":
        await db.accounts.update_one({"id": account_id}, {"$set": {"declared_role": "dual"}})
        print("✅ declared_role → dual")

    async def create_or_get_context(spec: dict, role: str, name: str) -> dict:
        existing = await db.contexts.find_one({"owner_account_id": account_id, "name": name}, {"_id": 0})
        if existing:
            print(f"  ↺ Context exists: {name} (id={existing['id']})")
            return existing
        ctx_id = str(uuid.uuid4())
        now = _iso(_now())
        ctx = {
            "id": ctx_id, "name": name, "type": spec["type"],
            "industry": spec.get("industry"), "jurisdiction": spec.get("jurisdiction"),
            "sector": spec.get("sector"), "sponsoring_org_id": None,
            "owner_account_id": account_id, "status": "active",
            "progress_state": {"onboarding_step": 7, "onboarding_completed": True, "context_object_version": 1},
            "created_at": now,
        }
        await db.contexts.insert_one(ctx); ctx.pop("_id", None)
        await db.memberships.insert_one({
            "id": str(uuid.uuid4()), "account_id": account_id, "context_id": ctx_id,
            "role": role, "sub_role": spec.get("sub_role") or "admin",
            "provisioning": "personal", "data_ownership": "account",
            "status": "active", "created_at": now,
        })
        # Context Object v1 completed
        await db.context_objects.insert_one({
            "id": str(uuid.uuid4()), "context_id": ctx_id, "version": 1,
            "industry": spec.get("industry"), "sector": spec.get("sector"),
            "jurisdiction": spec.get("jurisdiction"), "role": role,
            "answers": spec["answers"], "step": 7, "completed": True,
            "created_by": account_id, "created_at": now, "updated_at": now,
        })
        await db.audit_log.insert_one({
            "id": str(uuid.uuid4()), "context_id": ctx_id, "account_id": account_id,
            "action": "context.seeded", "resource_type": "context", "resource_id": ctx_id,
            "metadata": {"seed": "bramuel-test-data"}, "created_at": now,
        })
        print(f"  ✚ Created context: {name} (id={ctx_id}, role={role})")
        return ctx

    async def ensure_doc(context_id: str, name: str, text: str, trust: str = "trusted") -> str:
        existing = await db.documents.find_one(
            {"context_id": context_id, "name": name, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1},
        )
        if existing:
            return existing["id"]
        doc_id = str(uuid.uuid4())
        now = _iso(_now())
        preview = text.strip().split("\n", 1)[0][:220]
        doc = {
            "id": doc_id, "context_id": context_id,
            "name": name, "original_filename": f"{name.lower().replace(' ', '_')}.txt",
            "mime_type": "text/plain",
            "size_bytes": len(text.encode()),
            "storage_key": f"seed/{context_id}/{doc_id}.txt",
            "status": "extracted",
            "extracted_text": text, "extracted_chars": len(text),
            "preview": preview, "data_trust": trust,
            "uploaded_by": account_id, "uploaded_by_email": acc["email"],
            "error": None, "created_at": now, "updated_at": now,
        }
        await db.documents.insert_one(doc)
        return doc_id

    # --- NED contexts
    tuli = await create_or_get_context(NED_CONTEXTS[0], role="ned", name="Tuli Financial Group")
    mawingu = await create_or_get_context(NED_CONTEXTS[1], role="ned", name="Mawingu Logistics")
    safiri = await create_or_get_context(NED_CONTEXTS[2], role="ned", name="Safiri Telecom")

    # --- Executive context: reuse the existing default if present, else create new
    existing_default = await db.contexts.find_one(
        {"owner_account_id": account_id, "type": "executive_personal"},
        {"_id": 0},
    )
    if existing_default and existing_default["name"] != EXEC_CONTEXT["name"]:
        # Rename + upgrade to Tuli CFO
        await db.contexts.update_one(
            {"id": existing_default["id"]},
            {"$set": {
                "name": EXEC_CONTEXT["name"], "industry": EXEC_CONTEXT["industry"],
                "sector": EXEC_CONTEXT["sector"], "jurisdiction": EXEC_CONTEXT["jurisdiction"],
                "progress_state": {"onboarding_step": 7, "onboarding_completed": True, "context_object_version": 1},
            }},
        )
        await db.context_objects.insert_one({
            "id": str(uuid.uuid4()), "context_id": existing_default["id"], "version": 1,
            "industry": EXEC_CONTEXT["industry"], "sector": EXEC_CONTEXT["sector"],
            "jurisdiction": EXEC_CONTEXT["jurisdiction"], "role": "executive",
            "answers": EXEC_CONTEXT["answers"], "step": 7, "completed": True,
            "created_by": account_id, "created_at": _iso(_now()), "updated_at": _iso(_now()),
        })
        exec_ctx = await db.contexts.find_one({"id": existing_default["id"]}, {"_id": 0})
        print(f"  ✎ Upgraded existing exec context → {EXEC_CONTEXT['name']}")
    else:
        exec_ctx = await create_or_get_context(EXEC_CONTEXT, role="executive", name=EXEC_CONTEXT["name"])

    # --- Documents per context
    print("\n📄 Seeding documents…")
    # Tuli (NED board pack view): put all the ops data here — Ruth needs to see it
    tuli_brief = await ensure_doc(tuli["id"], "Tuli — Board Context Brief", DOC_TULI_CONTEXT_BRIEF)
    tuli_group = await ensure_doc(tuli["id"], "Tuli Group — Group Summary KPIs FY25", DOC_TULI_GROUP_SUMMARY, trust="trusted")
    tuli_bank = await ensure_doc(tuli["id"], "Tuli Bank — Commercial Banking Pack FY25", DOC_TULI_BANK, trust="trusted")
    tuli_digital = await ensure_doc(tuli["id"], "Tuli Digital — Mobile Money FY25", DOC_TULI_DIGITAL, trust="trusted")
    tuli_risk = await ensure_doc(tuli["id"], "Tuli — Risk Metrics FY25", DOC_TULI_RISK, trust="trusted")
    tuli_people = await ensure_doc(tuli["id"], "Tuli — People Metrics FY25", DOC_TULI_PEOPLE, trust="trusted")
    tuli_ins = await ensure_doc(tuli["id"], "Tuli Insurance — Underwriting FY25", DOC_TULI_INSURANCE, trust="trusted")

    # Also put the ops data into the Exec context for James/CFO workflow
    await ensure_doc(exec_ctx["id"], "Tuli Group — Group Summary KPIs FY25", DOC_TULI_GROUP_SUMMARY)
    await ensure_doc(exec_ctx["id"], "Tuli Bank — Commercial Banking Pack FY25", DOC_TULI_BANK)
    await ensure_doc(exec_ctx["id"], "Tuli Digital — Mobile Money FY25", DOC_TULI_DIGITAL)
    await ensure_doc(exec_ctx["id"], "Tuli — Risk Metrics FY25", DOC_TULI_RISK)
    await ensure_doc(exec_ctx["id"], "Tuli — People Metrics FY25", DOC_TULI_PEOPLE)

    # Mawingu
    mawingu_brief = await ensure_doc(mawingu["id"], "Mawingu — Board Context Brief", DOC_MAWINGU_BRIEF)

    # Safiri
    safiri_brief = await ensure_doc(safiri["id"], "Safiri — Board Context Brief", DOC_SAFIRI_BRIEF)
    safiri_cyber = await ensure_doc(safiri["id"], "Safiri — Cyber Threat Briefing Q4 2025", DOC_SAFIRI_CYBER, trust="mixed")

    # --- Signals
    print("\n✨ Seeding signals…")
    async def insert_signals(context_id: str, defs: list):
        now = _iso(_now())
        for i, s in enumerate(defs):
            # skip if a signal with identical headline already exists in this context
            existing = await db.signals.find_one({"context_id": context_id, "headline": s["headline"]}, {"_id": 0, "id": 1})
            if existing:
                continue
            sig_id = str(uuid.uuid4())
            doc_ids = s["doc_ids"]
            sources = []
            for d_id in doc_ids:
                d = await db.documents.find_one({"id": d_id}, {"_id": 0, "name": 1, "data_trust": 1})
                if d:
                    sources.append({"doc_id": d_id, "doc_name": d["name"], "data_trust": d.get("data_trust", "mixed")})
            # replace doc_id placeholders in summary
            summary = s["summary"]
            for placeholder_key, real_id in [("bank", tuli_bank), ("group", tuli_group), ("digital", tuli_digital),
                                             ("risk", tuli_risk), ("people", tuli_people), ("insurance", tuli_ins),
                                             ("d", doc_ids[0] if doc_ids else ""),
                                             ("b", doc_ids[0] if doc_ids else ""),
                                             ("c", doc_ids[-1] if len(doc_ids) > 1 else (doc_ids[0] if doc_ids else ""))]:
                summary = summary.replace("{" + placeholder_key + "}", real_id)
            trust = "trusted" if all((s.get("data_trust") or "trusted") == "trusted" for s in [{}]) else "trusted"
            # compute overall trust from sources
            bucket_trusts = [x["data_trust"] for x in sources]
            if not bucket_trusts:
                overall = "unrated"
            elif "weak" in bucket_trusts:
                overall = "weak"
            elif all(b == "trusted" for b in bucket_trusts):
                overall = "trusted"
            else:
                overall = "mixed"
            doc = {
                "id": sig_id, "context_id": context_id, "type": s["type"],
                "headline": s["headline"], "summary": summary,
                "confidence": s["confidence"], "sources": sources,
                "data_trust": overall, "generated_by": account_id,
                "focus": None, "shielding_masked": 0, "mode": "seeded",
                "created_at": now, "status": "active",
            }
            await db.signals.insert_one(doc)

    await insert_signals(tuli["id"], signals_for_tuli({
        "bank": tuli_bank, "group": tuli_group, "digital": tuli_digital,
        "risk": tuli_risk, "people": tuli_people, "insurance": tuli_ins,
    }))
    await insert_signals(mawingu["id"], signals_for_mawingu(mawingu_brief))
    await insert_signals(safiri["id"], signals_for_safiri([safiri_brief, safiri_cyber]))

    # Update default_context to Tuli NED (Ruth's primary)
    await db.accounts.update_one({"id": account_id}, {"$set": {"default_context_id": tuli["id"]}})
    print(f"\n✅ Default context set to Tuli Financial Group (NED)")

    # Summary
    n_ctx = await db.contexts.count_documents({"owner_account_id": account_id, "status": "active"})
    n_docs = await db.documents.count_documents({
        "context_id": {"$in": [tuli["id"], mawingu["id"], safiri["id"], exec_ctx["id"]]},
        "status": {"$ne": "archived"},
    })
    n_sigs = await db.signals.count_documents({
        "context_id": {"$in": [tuli["id"], mawingu["id"], safiri["id"]]},
        "status": "active",
    })
    print(f"\n📊 Summary: {n_ctx} contexts · {n_docs} documents · {n_sigs} signals")
    print(f"   Login: {TARGET_EMAIL} → /app")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
