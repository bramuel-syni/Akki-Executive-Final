"""Sprint 1 additive seed for bramuel@syni.ai.

Adds on top of seed_bramuel.py:
  - 2 more NED boards (total becomes 5)
  - 7 reportee memberships on the Exec 'Tuli Financial Group (CFO)' context
  - Member-since metadata (2 years of tenure)
  - Committee metadata on each NED board

Idempotent — safe to re-run.
"""
from __future__ import annotations
import asyncio, os, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

TARGET_EMAIL = "bramuel@syni.ai"
TENURE_YEARS = 2

NED_BOARDS_ADDITIONAL = [
    {
        "name": "Chai Agri Holdings",
        "type": "ned_personal",
        "industry": "agriculture",
        "sector": "Tea, coffee, horticulture exports",
        "jurisdiction": "Kenya",
        "sub_role": "admin",
        "committees": [
            {"name": "Audit Committee",         "your_role": "member"},
            {"name": "Risk Committee",          "your_role": "chair"},
            {"name": "Remuneration Committee",  "your_role": "member"},
        ],
        "answers": {
            "q1_role": "Independent Director · Chair of Risk Committee",
            "q2_meeting_cadence": "Quarterly (full board); bi-monthly (risk)",
            "q3_focus_areas": "Climate exposure · commodity price volatility · export-market concentration · FX hedging · out-grower welfare",
            "q4_committees": "Risk (Chair), Audit (Member), Remuneration (Member)",
            "q5_prior_concerns": "Climate insurance penetration (Q1); single-buyer concentration in Netherlands (Q2); FX hedging policy refresh (Q3)",
            "q6_lens_preference": "Risk committee lens — climate scenario analysis, concentration risk",
            "q7_analytical_style": "Wants plain English on supply chain. No jargon. Values field visits over reports.",
        },
    },
    {
        "name": "Pwani Hospitality Group",
        "type": "ned_personal",
        "industry": "hospitality",
        "sector": "Hotels & resorts (coastal + Nairobi)",
        "jurisdiction": "Kenya",
        "sub_role": None,
        "committees": [
            {"name": "Audit Committee",         "your_role": "member"},
            {"name": "Nominations Committee",   "your_role": "member"},
            {"name": "ESG Committee",           "your_role": "chair"},
        ],
        "answers": {
            "q1_role": "Independent Director · Chair of ESG Committee",
            "q2_meeting_cadence": "Quarterly",
            "q3_focus_areas": "Post-pandemic recovery · occupancy · capex on property renovation · ESG reporting · local community employment",
            "q4_committees": "ESG (Chair), Audit (Member), Nominations (Member)",
            "q5_prior_concerns": "Occupancy recovery trajectory (Q1, Q2); deferred maintenance capex (Q2); TCFD-aligned reporting gap (Q3)",
            "q6_lens_preference": "ESG + capital allocation lens",
            "q7_analytical_style": "Reads both the numbers and the guest reviews. Believes reputation metrics precede financials by two quarters.",
        },
    },
]

# 7 reportees for the Exec context
REPORTEES = [
    {"name": "Agnes Mutua",     "email": "agnes.mutua@tuli-group.test",     "title": "Head of Finance"},
    {"name": "David Ochieng",   "email": "david.ochieng@tuli-group.test",   "title": "Head of Treasury"},
    {"name": "Priya Shah",      "email": "priya.shah@tuli-group.test",      "title": "Head of FP&A"},
    {"name": "Michael Kariuki", "email": "michael.kariuki@tuli-group.test", "title": "Head of Investor Relations"},
    {"name": "Fatuma Ali",      "email": "fatuma.ali@tuli-group.test",      "title": "Head of Tax"},
    {"name": "John Njuguna",    "email": "john.njuguna@tuli-group.test",    "title": "Head of Internal Audit"},
    {"name": "Liz Wanjiru",     "email": "liz.wanjiru@tuli-group.test",     "title": "Head of Procurement"},
]


def _now(): return datetime.now(timezone.utc)
def _iso(d): return d.isoformat()


async def seed():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    acc = await db.accounts.find_one({"email": TARGET_EMAIL}, {"_id": 0})
    if not acc:
        print(f"❌ Account {TARGET_EMAIL} not found. Run seed_bramuel.py first.")
        return
    account_id = acc["id"]
    print(f"✅ Account found: {acc['email']} (id={account_id})")

    tenure_start = _iso(_now() - timedelta(days=365 * TENURE_YEARS))

    # Update tenure on ALL contexts (existing 3 NED + new 2 + Exec)
    await db.memberships.update_many(
        {"account_id": account_id, "status": "active"},
        {"$set": {"member_since": tenure_start}},
    )
    print(f"✅ Stamped {TENURE_YEARS}-year tenure on existing memberships")

    # Create additional NED boards
    for spec in NED_BOARDS_ADDITIONAL:
        existing = await db.contexts.find_one(
            {"owner_account_id": account_id, "name": spec["name"]}, {"_id": 0}
        )
        if existing:
            print(f"  ↺ Context already exists: {spec['name']}")
            ctx_id = existing["id"]
        else:
            ctx_id = str(uuid.uuid4())
            now_iso = _iso(_now())
            await db.contexts.insert_one({
                "id": ctx_id, "name": spec["name"], "type": spec["type"],
                "industry": spec["industry"], "jurisdiction": spec["jurisdiction"],
                "sector": spec["sector"], "sponsoring_org_id": None,
                "owner_account_id": account_id, "status": "active",
                "progress_state": {"onboarding_step": 7, "onboarding_completed": True, "context_object_version": 1},
                "committees": spec["committees"],
                "created_at": now_iso,
            })
            await db.memberships.insert_one({
                "id": str(uuid.uuid4()), "account_id": account_id, "context_id": ctx_id,
                "role": "ned", "sub_role": spec.get("sub_role") or "admin",
                "provisioning": "personal", "data_ownership": "account",
                "status": "active", "created_at": now_iso, "member_since": tenure_start,
            })
            await db.context_objects.insert_one({
                "id": str(uuid.uuid4()), "context_id": ctx_id, "version": 1,
                "industry": spec["industry"], "sector": spec["sector"],
                "jurisdiction": spec["jurisdiction"], "role": "ned",
                "answers": spec["answers"], "step": 7, "completed": True,
                "created_by": account_id, "created_at": now_iso, "updated_at": now_iso,
            })
            print(f"  ✚ Created NED board: {spec['name']} (id={ctx_id})")

        # Ensure committees are attached
        await db.contexts.update_one(
            {"id": ctx_id},
            {"$set": {"committees": spec["committees"]}},
        )

    # Backfill committees on the original 3 NED boards if missing
    ORIGINAL_COMMITTEES = {
        "Tuli Financial Group": [
            {"name": "Audit Committee",      "your_role": "chair"},
            {"name": "Risk Committee",       "your_role": "member"},
            {"name": "Nominations Committee","your_role": "member"},
        ],
        "Mawingu Logistics": [
            {"name": "Risk Committee",       "your_role": "member"},
            {"name": "Audit Committee",      "your_role": "member"},
        ],
        "Safiri Telecom": [
            {"name": "Risk Committee",       "your_role": "chair"},
            {"name": "Audit Committee",      "your_role": "member"},
        ],
    }
    for name, comms in ORIGINAL_COMMITTEES.items():
        await db.contexts.update_one(
            {"owner_account_id": account_id, "name": name},
            {"$set": {"committees": comms}},
        )
    print("✅ Committees stamped on all 5 NED boards")

    # Find Exec context
    exec_ctx = await db.contexts.find_one(
        {"owner_account_id": account_id, "type": "executive_personal", "status": "active"},
        {"_id": 0},
    )
    if not exec_ctx:
        print("❌ Exec context not found; cannot seed reportees.")
        client.close()
        return

    # Create reportee accounts + memberships (idempotent)
    for r in REPORTEES:
        existing_acc = await db.accounts.find_one({"email": r["email"]}, {"_id": 0, "id": 1})
        if existing_acc:
            rep_id = existing_acc["id"]
        else:
            rep_id = str(uuid.uuid4())
            import bcrypt
            await db.accounts.insert_one({
                "id": rep_id, "email": r["email"], "name": r["name"],
                "password_hash": bcrypt.hashpw(b"TestReportee2026!", bcrypt.gensalt()).decode(),
                "declared_role": "reportee", "mfa_enabled": False,
                "mfa_secret": None, "mfa_secret_pending": None,
                "default_context_id": None,
                "title": r["title"], "preferences": {},
                "created_at": _iso(_now()),
            })
        # Membership
        existing_mem = await db.memberships.find_one(
            {"account_id": rep_id, "context_id": exec_ctx["id"]}, {"_id": 0},
        )
        if not existing_mem:
            await db.memberships.insert_one({
                "id": str(uuid.uuid4()), "account_id": rep_id, "context_id": exec_ctx["id"],
                "role": "reportee", "sub_role": r["title"],
                "provisioning": "direct", "data_ownership": "context",
                "status": "active", "created_at": _iso(_now()), "member_since": tenure_start,
                "reports_to": account_id,
            })
    print(f"✅ 7 reportees attached to {exec_ctx['name']}")

    # Summary
    n_ctx = await db.contexts.count_documents({"owner_account_id": account_id, "status": "active"})
    n_mem = await db.memberships.count_documents({"context_id": exec_ctx["id"], "status": "active"})
    print(f"\n📊 Final state: {n_ctx} contexts (5 NED + 1 Exec), {n_mem} total members on Exec context")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
