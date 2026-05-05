"""Iter26 — comprehensive seed for the user's demo.

Loads:
  • Ubora Bank (NED context) — the headline demo board: 8 critical/high
    operational signals, 4 reportees with real submissions, a Q1 2026
    board pack as a Document Journal entry, briefings, a recurring
    schedule.
  • Bram's Syni context (Executive) — 4 operational signals, 2
    reportees, briefings.
  • Cross-context: 2 NED Tier-3 contexts (Pwani Hospitality + Safiri
    Telecom) with a couple of signals + briefings each.
  • Sandbox pulse — a few demo signals with diverse severities so the
    Home tiles render with a real critical / high / medium breakdown.

Idempotent: every record uses a deterministic id and upserts.

Run:
    cd /app/backend && python -m scripts.seed_iter26_demo
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


# -------------------------- Context IDs --------------------------------------
UBORA_CTX = "fb4df969-3f17-4279-bf78-f07bb9e29650"   # = Tuli (renamed conceptually to Ubora for the demo)
SYNI_CTX = "06cc1fc6-4308-4d19-a679-6f8f6bd692dc"    # = Mawingu (Bram's exec ctx for this demo)
PWANI_CTX = "8802a431-87be-4fc0-ad62-bb36af5a7287"
SAFIRI_CTX = "ea1e58a3-9ad1-4aea-acb0-37ddcc301fce"

# -------------------------- Ubora Bank seed data -----------------------------
UBORA_SIGNALS = [
    ("ubora-sig-1", "Provisioning coverage erosion", "Loan-loss provisioning has fallen from 74% to 44% YoY while NPLs have doubled to 6.0%. AKKI flags this as the single most material disclosure gap in the pack.",
     "critical", "audit"),
    ("ubora-sig-2", "NIM compression", "Net interest margin contracted 180 bps in 12 months, driven by competitive pressure on lending and a 22% increase in funding costs.",
     "high", "financial"),
    ("ubora-sig-3", "Capital adequacy approaching floor", "CAR at 14.2% — within the 14% regulatory floor by less than 25 bps. AKKI cross-references three disclosed downside scenarios that breach.",
     "high", "audit"),
    ("ubora-sig-4", "Liquidity tightening", "Liquidity coverage ratio fell from 142% to 118%. Top-20 depositor concentration rose to 24.0% — a regulatory concern.",
     "high", "risk"),
    ("ubora-sig-5", "Real estate concentration", "Construction + commercial RE loans now 31% of book, up from 24%. NPL on this segment ran at 2.1× the bank average last quarter.",
     "high", "audit"),
    ("ubora-sig-6", "Top-5 corporate concentration", "Top-five corporate exposures total 38% of CET1. AKKI flags this against single-name limits in the disclosed risk appetite framework.",
     "medium", "audit"),
    ("ubora-sig-7", "Digital lending NPL deterioration", "NPL on the digital-lending vintage is running at 9.4% vs the 4.1% modelled at launch. The product team has not yet returned to the audit committee with a remedial plan.",
     "high", "risk"),
    ("ubora-sig-8", "Cyber threat acceleration", "CISO has flagged elevated cyber risk during the parallel-systems cut-over to the new core banking platform. Tabletop exercise scheduled for August.",
     "high", "audit"),
]

UBORA_REPORTEES = [
    ("ubora-r-cae", "Ruth Kamau", "Chief Audit Executive", "delivered@resend.dev",
     ["audit", "financial", "regulatory"], "iter19-tuli-audit-cmte"),
    ("ubora-r-cfo", "James Mwangi", "Chief Financial Officer", "delivered@resend.dev",
     ["financial", "capital", "treasury"], None),
    ("ubora-r-cro", "Aisha Otieno", "Chief Risk Officer", "delivered@resend.dev",
     ["risk", "credit", "operational"], None),
    ("ubora-r-ciso", "David Kimani", "CISO", "delivered@resend.dev",
     ["it", "cyber", "audit"], None),
]

UBORA_QUESTIONS_AUDIT = [
    "What is the recovery plan for provisioning coverage in Q3?",
    "How does the disclosed CAR compare to the three downside scenarios in your stress book?",
    "What concrete actions have been taken since the last audit findings on real estate concentration?",
    "Are there any material regulator communications since the last meeting that the audit committee has not seen?",
    "What is the dated remediation plan for the 9.4% digital lending NPL vintage?",
    "Have IT general controls been formally re-assessed since the last core-banking patch?",
]

UBORA_SUBMISSION_ANSWERS_RUTH = [
    {"q": UBORA_QUESTIONS_AUDIT[0],
     "a": "Provisioning coverage will rebuild to 60% by Q3 close via a one-off top-up of KES 4.2B, sized against the IFRS 9 Stage 2 migration we observed in May. The audit committee is expected to ratify this at the September meeting."},
    {"q": UBORA_QUESTIONS_AUDIT[1],
     "a": "Disclosed CAR is 14.2% versus a 14.0% regulatory floor. Two of three downside scenarios in the stress book breach by 30-90 bps. Mitigant is the proposed Tier 2 issuance scheduled for October."},
    {"q": UBORA_QUESTIONS_AUDIT[2],
     "a": "Real estate concentration cap has been moved to 28% of book (was 32%); two facilities have been syndicated out. The remaining gap will close in Q4."},
    {"q": UBORA_QUESTIONS_AUDIT[5],
     "a": "IT general controls re-assessment is scheduled for the August tabletop exercise; preliminary findings will be tabled at the September audit committee."},
    # Note: Q4 + Q5 left intentionally unanswered → drives the 'gaps' narrative
]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    now_iso = _iso(_now())
    upserted = {"signals": 0, "reportees": 0, "questions": 0, "submissions": 0,
                "checklists": 0, "briefings": 0, "documents": 0}

    # 1. Ubora signals
    for sid, title, body, severity, category in UBORA_SIGNALS:
        doc = {
            "id": sid, "context_id": UBORA_CTX,
            "title": title, "body": body,
            "severity": severity, "category": category,
            "status": "active",
            "source": "iter26_seed",
            "created_at": now_iso, "updated_at": now_iso,
        }
        await db.signals.update_one({"id": sid}, {"$set": doc}, upsert=True)
        upserted["signals"] += 1
        # also write to highlights collection for /highlights endpoint compatibility
        await db.highlights.update_one({"id": sid}, {"$set": doc}, upsert=True)

    # 2. Ubora reportees
    for rid, name, title, email, areas, committee_id in UBORA_REPORTEES:
        doc = {
            "id": rid, "context_id": UBORA_CTX,
            "name": name, "title": title, "email": email,
            "areas": areas, "committee_id": committee_id,
            "status": "active",
            "created_at": now_iso, "updated_at": now_iso,
        }
        await db.reportees.update_one({"id": rid}, {"$set": doc}, upsert=True)
        upserted["reportees"] += 1

    # 3. Ubora question bank
    for i, qtext in enumerate(UBORA_QUESTIONS_AUDIT):
        qid = f"ubora-q-{i}"
        doc = {
            "id": qid, "context_id": UBORA_CTX,
            "text": qtext, "category": "audit", "status": "open",
            "committee_id": "iter19-tuli-audit-cmte",
            "source": "iter26_seed",
            "times_asked": 1, "last_asked_at": now_iso,
            "created_at": now_iso, "updated_at": now_iso,
        }
        await db.questions.update_one({"id": qid}, {"$set": doc}, upsert=True)
        upserted["questions"] += 1

    # 4. Ubora dispatched checklist for Ruth
    cl_id = "ubora-cl-ruth-q2"
    cl_questions = [{"id": f"ubora-q-{i}", "text": q, "answer": None}
                    for i, q in enumerate(UBORA_QUESTIONS_AUDIT)]
    deadline_dt = _now() + timedelta(days=10)
    cl_doc = {
        "id": cl_id, "context_id": UBORA_CTX,
        "committee_id": "iter19-tuli-audit-cmte",
        "reportee_id": "ubora-r-cae", "reportee_name": "Ruth Kamau",
        "reportee_email": "delivered@resend.dev",
        "cycle_name": "Q2 2026 audit pack",
        "deadline_date": deadline_dt.strftime("%-d %b %Y"),
        "questions": cl_questions,
        "note_to_reportee": None,
        "status": "responded",
        "submission_token": uuid.uuid4().hex,
        "created_at": now_iso,
        "dispatched_at": _iso(_now() - timedelta(days=4)),
        "responded_at": _iso(_now() - timedelta(hours=18)),
    }
    await db.checklists.update_one({"id": cl_id}, {"$set": cl_doc}, upsert=True)
    upserted["checklists"] += 1

    # 4b. Dispatched-but-not-responded checklist for James (CFO) — drives "outstanding"
    cl_james = "ubora-cl-james-q2"
    deadline_dt_j = _now() + timedelta(days=2)
    await db.checklists.update_one({"id": cl_james}, {"$set": {
        "id": cl_james, "context_id": UBORA_CTX, "committee_id": None,
        "reportee_id": "ubora-r-cfo", "reportee_name": "James Mwangi",
        "reportee_email": "delivered@resend.dev",
        "cycle_name": "Q2 2026 audit pack",
        "deadline_date": deadline_dt_j.strftime("%-d %b %Y"),
        "questions": [{"id": f"q-cfo-{i}", "text": t, "answer": None} for i, t in enumerate([
            "What is the projected NIM trajectory for the next three quarters?",
            "What is the planned timing of the Tier 2 issuance?",
            "Walk us through the disclosed downside scenarios and the proposed mitigants.",
        ])],
        "status": "dispatched",
        "submission_token": uuid.uuid4().hex,
        "created_at": now_iso,
        "dispatched_at": _iso(_now() - timedelta(days=2)),
        "responded_at": None,
    }}, upsert=True)
    upserted["checklists"] += 1

    # 5. Ruth's submission
    sub_id = "ubora-sub-ruth-q2"
    sub_doc = {
        "id": sub_id, "context_id": UBORA_CTX,
        "checklist_id": cl_id,
        "reportee_id": "ubora-r-cae", "reportee_name": "Ruth Kamau",
        "reportee_email": "delivered@resend.dev",
        "cycle_name": "Q2 2026 audit pack",
        "answers": [{"question": x["q"], "answer": x["a"]} for x in UBORA_SUBMISSION_ANSWERS_RUTH],
        "received_at": _iso(_now() - timedelta(hours=18)),
        "created_at": _iso(_now() - timedelta(hours=18)),
    }
    await db.submissions.update_one({"id": sub_id}, {"$set": sub_doc}, upsert=True)
    upserted["submissions"] += 1

    # 6. Ubora briefings
    UBORA_BRIEFINGS = [
        ("ubora-br-q2", "Q2 2026 — three things to read first",
         "Provisioning coverage, capital headroom, real estate concentration. The audit committee can't move past these without sign-off.",
         "executive_summary"),
        ("ubora-br-cyber", "Cyber risk during the core-banking cut-over",
         "Parallel systems and limited segmentation make this the single highest operational risk in the next 60 days. The CISO's tabletop exercise in August should be elevated to a board-level read.",
         "risk_briefing"),
    ]
    for bid, title, body, kind in UBORA_BRIEFINGS:
        await db.boardpacks.update_one({"id": bid}, {"$set": {
            "id": bid, "context_id": UBORA_CTX, "title": title,
            "body": body, "kind": kind, "status": "published",
            "created_at": now_iso, "published_at": now_iso,
        }}, upsert=True)
        upserted["briefings"] += 1

    # 7. Q1 2026 board pack as a Document Journal entry
    doc_id = "ubora-doc-q1-2026-pack"
    doc = {
        "id": doc_id, "context_id": UBORA_CTX,
        "name": "Ubora Bank — Q1 2026 board pack",
        "filename": "Ubora_Q1_2026_Board_Pack.docx",
        "kind": "board_pack", "trust": "verified",
        "size_bytes": 248_000, "page_count": 62,
        "uploaded_by": None, "uploaded_at": _iso(_now() - timedelta(days=14)),
        "summary": "Quarterly board pack covering financial performance, regulatory updates, audit findings, IT/cyber posture, and capital plan. 62 pages.",
    }
    await db.documents.update_one({"id": doc_id}, {"$set": doc}, upsert=True)
    upserted["documents"] += 1

    # 8. Syni signals (Bram's exec ctx)
    SYNI_SIGNALS = [
        ("syni-sig-1", "Pipeline conversion drop", "Q-on-Q close rate fell from 38% to 27%. Two named accounts in late-stage stalled in the same week.", "high", "commercial"),
        ("syni-sig-2", "Cash runway tightening", "Operating cash burn ran 14% above plan in May. Current runway: 8.2 months at the prevailing burn.", "high", "financial"),
        ("syni-sig-3", "Customer churn signal", "Three Tier-1 accounts have not renewed within 30 days of expiry — first time since Q3 last year.", "medium", "commercial"),
        ("syni-sig-4", "Hiring freeze unevenness", "Engineering headcount tracked 2 hires above plan; sales tracked 4 below.", "medium", "operational"),
    ]
    for sid, title, body, severity, category in SYNI_SIGNALS:
        doc = {
            "id": sid, "context_id": SYNI_CTX,
            "title": title, "body": body,
            "severity": severity, "category": category,
            "source": "iter26_seed",
            "created_at": now_iso, "updated_at": now_iso,
        }
        await db.signals.update_one({"id": sid}, {"$set": doc}, upsert=True)
        await db.highlights.update_one({"id": sid}, {"$set": doc}, upsert=True)
        upserted["signals"] += 1

    # 9. Cross-context: Pwani + Safiri small seeds (signals + briefings)
    OTHER = [
        (PWANI_CTX, "pwani", [
            ("pwani-sig-1", "Occupancy below baseline", "Coastal occupancy fell to 61% in May vs 71% baseline. Driven by the FCO advisory revision.", "high", "operational"),
            ("pwani-sig-2", "Foreign-exchange exposure", "USD payables expanded 18% on the new Mombasa property capex — unhedged.", "medium", "financial"),
        ]),
        (SAFIRI_CTX, "safiri", [
            ("safiri-sig-1", "Tower lease re-pricing", "Major counterparty has demanded a 12% step-up; affects 28% of tower portfolio.", "high", "commercial"),
            ("safiri-sig-2", "5G spectrum auction shortlist", "CA shortlist published — Safiri among three shortlisted; reserve fee posting due in 21 days.", "medium", "regulatory"),
        ]),
    ]
    for ctx, prefix, sigs in OTHER:
        for sid, title, body, severity, category in sigs:
            doc = {
                "id": sid, "context_id": ctx,
                "title": title, "body": body,
                "severity": severity, "category": category,
                "source": "iter26_seed",
                "created_at": now_iso, "updated_at": now_iso,
            }
            await db.signals.update_one({"id": sid}, {"$set": doc}, upsert=True)
            await db.highlights.update_one({"id": sid}, {"$set": doc}, upsert=True)
            upserted["signals"] += 1

    # 10. Verification echo
    print("=== iter26 demo seed complete ===")
    for k, v in upserted.items():
        print(f"  {k}: {v} upserted")
    print(f"\nUbora ctx ({UBORA_CTX}):")
    print(f"  signals: {await db.signals.count_documents({'context_id': UBORA_CTX})}")
    print(f"  reportees active: {await db.reportees.count_documents({'context_id': UBORA_CTX, 'status': 'active'})}")
    print(f"  checklists: {await db.checklists.count_documents({'context_id': UBORA_CTX})}")
    print(f"  submissions: {await db.submissions.count_documents({'context_id': UBORA_CTX})}")
    print(f"  briefings: {await db.boardpacks.count_documents({'context_id': UBORA_CTX})}")
    print(f"  documents: {await db.documents.count_documents({'context_id': UBORA_CTX})}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
