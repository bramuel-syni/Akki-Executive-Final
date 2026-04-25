"""
Iter19 E2E seed — adds the minimal data needed to verify the new UI polish:

1. Two committees on Tuli Financial Group (NED ctx) → so the Checklists
   committee scope strip renders.
2. One scoped reportee on the Audit Committee → so a scoped checklist
   generate POST has at least one target.
3. One richer draft report (≥ 600 words of business prose) on Mawingu
   Logistics → so 'Polish with AKKI' produces a non-trivial diff and the
   PolishDiffModal can be exercised.

Idempotent: re-runs upsert by deterministic IDs.

Run:
    cd /app/backend && python -m scripts.seed_iter19_e2e
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Make sure backend's .env is loaded so MONGO_URL/DB_NAME resolve when run as a module
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TULI_NED_CTX = "fb4df969-3f17-4279-bf78-f07bb9e29650"
MAWINGU_NED_CTX = "06cc1fc6-4308-4d19-a679-6f8f6bd692dc"

AUDIT_CTTE_ID = "iter19-tuli-audit-cmte"
RISK_CTTE_ID = "iter19-tuli-risk-cmte"
RICH_REPORT_ID = "iter19-mawingu-rich-draft"
SCOPED_REPORTEE_ID = "iter19-tuli-audit-reportee"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # --- 1. Committees on Tuli ---------------------------------------------
    audit = {
        "id": AUDIT_CTTE_ID,
        "context_id": TULI_NED_CTX,
        "name": "Audit Committee",
        "kind": "audit",
        "chair_email": "bramuel@syni.ai",
        "status": "active",
        "created_at": _now_iso(),
    }
    risk = {
        "id": RISK_CTTE_ID,
        "context_id": TULI_NED_CTX,
        "name": "Risk Committee",
        "kind": "risk",
        "chair_email": "bramuel@syni.ai",
        "status": "active",
        "created_at": _now_iso(),
    }
    for c in (audit, risk):
        await db.committees.update_one({"id": c["id"]}, {"$set": c}, upsert=True)
    print(f"[committees] upserted {AUDIT_CTTE_ID}, {RISK_CTTE_ID} on Tuli ctx")

    # --- 2. One audit-scoped reportee on Tuli ------------------------------
    reportee = {
        "id": SCOPED_REPORTEE_ID,
        "context_id": TULI_NED_CTX,
        "name": "Ruth Kamau",
        "title": "Chief Audit Executive",
        "email": "delivered@resend.dev",  # Resend sandbox always-deliver
        "areas": ["audit", "financial", "regulatory"],
        "committee_id": AUDIT_CTTE_ID,
        "status": "active",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.reportees.update_one({"id": reportee["id"]}, {"$set": reportee}, upsert=True)
    print(f"[reportees] upserted {SCOPED_REPORTEE_ID} on Tuli ctx (scoped to Audit)")

    # --- 3. Rich draft report on Mawingu (so Polish makes real diffs) ------
    rich_body = """\
# Mawingu Logistics — Q2 2026 Submission to the Board

## Executive Summary

The second quarter delivered solid topline growth across the East African
corridor, but the underlying operational picture is mixed. Revenue grew
14.2% year-on-year to $48.3M, driven primarily by the new Mombasa–Kampala
intermodal lane and stronger pricing on the regional fast-moving consumer
goods (FMCG) segment. However, fuel-adjusted gross margin compressed by
180 basis points to 23.1%, reflecting the front-loaded cost of the ERP
migration and a temporary doubling of overland insurance premiums in the
Democratic Republic of Congo (DRC) following the April convoy incident.

## Operational topology

We exited the quarter with active operations in Kenya, Uganda, Tanzania,
Rwanda, and the DRC. The DRC corridor remains our highest-risk lane: two
convoys experienced delays exceeding seventy-two hours due to the renewed
militia activity around Beni, and our local operating partner has flagged
that the M23 escalation is now affecting goods movement on the Goma–Bukavu
route. We have temporarily rerouted high-value cargo through the Kigali
overland gateway at a gross-margin cost of approximately 290 bps on
affected loads.

## ERP migration

The migration to the new ERP platform is now seventy-three percent
complete on the operations module and forty-one percent complete on the
finance module. We are tracking a four-week slip against the original Q4
2025 board-approved schedule. The slip is driven primarily by the
custom-clearance integration with the Kenya Revenue Authority's
electronic cargo tracking note system, which has required substantially
more bespoke development than the vendor scoped. The CFO's office is
proposing a revised go-live window of late October 2026, which would push
the project's incremental opex into the next budget cycle but would not
threaten the IPO readiness work.

## Cyber exposure during transition

The CISO has flagged that during the cut-over window we are running
parallel systems with limited segmentation between the legacy stack and
the new ERP. This is a known elevated-risk window and we have engaged a
specialist firm to run a focused tabletop exercise in August. The risk
committee has visibility on this and the chair has asked for a written
update at every monthly meeting until cut-over is complete.

## IPO readiness

We are continuing to execute against the IPO readiness work programme as
ratified by the board in Q4 2025. The four key open items are: (1)
finalisation of the consolidated DRC accounting policy under IFRS, (2)
the long-form auditor opinion on the FY25 statutory accounts, (3) the
remaining director independence reviews, and (4) the legal opinion on the
cross-border holdings structure. We expect items (2) and (3) to clear by
end of August. Item (1) remains the binding constraint and is being
escalated this week to the audit committee chair.

## Capital adequacy

The proposed bond raise to fund the Tanzania expansion is fully
underwritten subject to final pricing. The treasurer is comfortable with
the proposed term sheet and has stress-tested the resulting capital
structure against three downside scenarios, including a return to 2022-style
fuel volatility. All three scenarios remain within the bounds set by the
risk committee in the Q1 2026 capital plan.

## Asks of the board

We are seeking the board's view on three items at the upcoming meeting:
(a) confirmation of the revised ERP go-live window, (b) endorsement of
the proposed bond raise terms, and (c) guidance on whether the DRC
operational risk framework should be re-tabled now or held until the
post-monsoon stability window opens in October.

We will table this submission on Tuesday morning and welcome any
follow-up questions from members in advance.
"""

    rich_report = {
        "id": RICH_REPORT_ID,
        "context_id": MAWINGU_NED_CTX,
        "cycle_name": "Q2 2026 board pack",
        "title": "CFO submission to CEO — Q2 2026 (iter19 fixture)",
        "body": rich_body,
        "status": "draft",
        "author_id": None,  # not strictly required for the seed
        "author_name": "Bramuel Mwalo",
        "author_email": "bramuel@syni.ai",
        "chain": [
            {"tier": 1, "name": "Bramuel Mwalo", "title": "Author / CFO",
             "email": "bramuel@syni.ai", "status": "pending",
             "acted_at": None},
        ],
        "events": [{"at": _now_iso(), "actor_name": "seed",
                    "action": "drafted", "note": "iter19 e2e fixture"}],
        "current_reviewer_email": "bramuel@syni.ai",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.reports.update_one({"id": rich_report["id"]}, {"$set": rich_report}, upsert=True)
    print(f"[reports] upserted {RICH_REPORT_ID} on Mawingu ctx (~{len(rich_body.split())} words)")

    # --- Verification echo --------------------------------------------------
    cmtes = await db.committees.count_documents({"context_id": TULI_NED_CTX, "status": {"$ne": "archived"}})
    reps = await db.reportees.count_documents({"context_id": TULI_NED_CTX, "status": "active"})
    print(f"[verify] Tuli committees: {cmtes}, active reportees: {reps}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
