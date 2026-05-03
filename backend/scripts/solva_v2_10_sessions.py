"""Phase 15.0 acceptance — run 10 real Seek Clarity sessions end-to-end.

Uses the live Emergent Universal Key and the live Mongo instance. Walks each
session through all four layers (framing → grounding → synthesis → reflection)
and reports a pass/fail per session plus aggregate validator pass rate.

Pass criteria (per the Phase 15.0 build brief):
    - session completes to 'completed' status
    - synthesis persisted with a non-empty claims[] array
    - validator verdict in {validated, qualified} (NOT flagged)
    - ≥ 90% pass rate across 10 sessions

Usage (from /app):
    python -m backend.scripts.solva_v2_10_sessions
    — or —
    cd /app/backend && python scripts/solva_v2_10_sessions.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

# Let the script run both as a module (python -m backend.scripts.*) and
# as a standalone script (python scripts/solva_v2_10_sessions.py).
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# load_dotenv must happen BEFORE core is imported
from dotenv import load_dotenv  # noqa: E402
load_dotenv(BACKEND_DIR / ".env")

from core import db, hash_password  # noqa: E402


INTENTS: List[Dict[str, str]] = [
    {
        "cluster_id": "revenue_underperformance",
        "intent": (
            "Q3 revenue missed by 14% and the CEO's framing blames FX headwinds. "
            "Two of us on the board think it's pricing; the CFO's dashboard "
            "shows volume flat and mix shifting. We cannot agree what to ask "
            "for at next month's exec session."
        ),
    },
    {
        "cluster_id": "ceo_succession",
        "intent": (
            "The CEO is 14 months from the nominations committee's stated target "
            "handover date. Two plausible internal candidates; the stronger one "
            "has never run a P&L. The chair wants to start external search but "
            "the sponsoring PE is pushing for an internal appointment."
        ),
    },
    {
        "cluster_id": "regulatory_change",
        "intent": (
            "Our capital ratio will fall inside the regulator's intervention "
            "band by Q1 if the H2 forecast holds. Group treasurer believes a "
            "subordinated issuance closes the gap; the CFO is reluctant to pay "
            "the coupon given expected rate cuts. The audit chair wants a "
            "contingency plan before the December regulator meeting."
        ),
    },
    {
        "cluster_id": "ma_thesis",
        "intent": (
            "A sector peer half our size is privately shopped at a 12x multiple. "
            "Our own shares trade at 9x. Management wants to bid; two NEDs think "
            "we over-concentrate post-deal and that regulatory clearance risk "
            "is underpriced. Target needs a term-sheet in two weeks."
        ),
    },
    {
        "cluster_id": "revenue_underperformance",
        "intent": (
            "Revenue is on-plan but gross margin has compressed 280bps in three "
            "quarters. The commercial director insists it is temporary input "
            "costs. The audit chair has asked twice for a cohort-level margin "
            "waterfall and has not received one."
        ),
    },
    {
        "cluster_id": "ceo_succession",
        "intent": (
            "The founder-CEO has told the chair she will stand down within 18 "
            "months for personal reasons. No internal successor is ready. An "
            "interim chair-as-CEO is being floated; two NEDs think this is "
            "precisely the wrong signal to customers and employees."
        ),
    },
    {
        "cluster_id": "risk_blindspot",
        "intent": (
            "The regulator has opened an informal inquiry into our pricing "
            "disclosure practice. Management says the exposure is 'contained' "
            "but has not quantified it. Legal has advised privilege. The "
            "upcoming board meeting sets the annual report tone."
        ),
    },
    {
        "cluster_id": "ma_thesis",
        "intent": (
            "We received an unsolicited approach at 10% premium to 30-day VWAP. "
            "The CEO believes our fair value is 30% higher after the current "
            "strategic plan executes. Institutional shareholders are split. "
            "The chair wants a considered response within 10 days."
        ),
    },
    {
        "cluster_id": "revenue_underperformance",
        "intent": (
            "Our largest customer (22% of revenue) has delayed their annual "
            "renewal by 60 days. Sales insists it is procurement theatre. The "
            "customer's CFO told our CFO informally they are running an RFP. "
            "The board pack does not reflect the RFP risk."
        ),
    },
    {
        "cluster_id": "ceo_succession",
        "intent": (
            "The CEO has a clear candidate for the COO role which the board is "
            "expected to ratify next week. Two NEDs (including me) have private "
            "concerns about the candidate's judgement under pressure. Neither "
            "of us has yet raised them formally."
        ),
    },
]


async def _seed_account(email: str, password: str) -> Dict[str, Any]:
    existing = await db.accounts.find_one({"email": email}, {"_id": 0})
    if existing:
        await db.accounts.update_one(
            {"email": email},
            {"$set": {
                "solva_v2_poc": True,
                "password_hash": hash_password(password),
            }},
        )
        return existing
    aid = str(uuid.uuid4())
    account = {
        "id": aid,
        "email": email,
        "name": "Solva v2 POC Runner",
        "declared_role": "ned",
        "password_hash": hash_password(password),
        "mfa_enabled": False,
        "is_superadmin": False,
        "solva_v2_poc": True,
        "plan": "free",
        "created_at": "2026-05-04T00:00:00Z",
    }
    await db.accounts.insert_one(account)
    return account


async def _login(client, email: str, password: str) -> str:
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    r.raise_for_status()
    return r.json().get("access_token") or ""


async def _walk_session(client, headers: Dict[str, str], scenario: Dict[str, str]) -> Dict[str, Any]:
    t0 = time.monotonic()
    start_resp = await client.post(
        "/api/solva/v2/sessions",
        json={
            "cluster_id": scenario["cluster_id"],
            "intent": scenario["intent"],
            "submodule": "seek_clarity",
            "pro_tier": False,
        },
        headers=headers,
        timeout=120,
    )
    if start_resp.status_code != 200:
        return {
            "ok": False, "stage": "start",
            "status": start_resp.status_code, "body": start_resp.text[:400],
        }
    session = start_resp.json()
    sid = session["id"]

    replies = [
        "The timeframe is this quarter. No pricing change in the window.",
        "Comparables look relevant. Go deeper where they diverge.",
        "Understood. Lock the diagnosis.",
    ]
    stage = "framing"
    for txt in replies:
        r = await client.post(
            f"/api/solva/v2/sessions/{sid}/turn",
            json={"user_text": txt},
            headers=headers,
            timeout=180,
        )
        if r.status_code != 200:
            # Grounding contract violation surfaces as 422 with structured body
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:400]
            return {
                "ok": False, "stage": stage, "session_id": sid,
                "status": r.status_code, "body": detail,
            }
        session = r.json()
        stage = session.get("layer") or stage

    latency = int((time.monotonic() - t0) * 1000)
    synth = session.get("synthesis") or {}
    validation = synth.get("validation") or {}
    verdict = validation.get("verdict")
    tier_distribution = synth.get("tier_distribution") or {}
    claim_count = sum(tier_distribution.values())
    audit_len = len(session.get("reasoning_audit_log") or [])

    pass_ok = (
        session.get("status") == "completed"
        and claim_count > 0
        and verdict in {"validated", "qualified"}
    )
    return {
        "ok": pass_ok,
        "session_id": sid,
        "status": session.get("status"),
        "layer": session.get("layer"),
        "claim_count": claim_count,
        "tier_distribution": tier_distribution,
        "validator_verdict": verdict,
        "validator_confidence": validation.get("confidence"),
        "audit_entry_count": audit_len,
        "latency_ms": latency,
        "cluster_id": scenario["cluster_id"],
    }


async def main() -> int:
    import httpx
    import server  # noqa: E402 — ensures startup hook ran (indexes, cluster seed)

    # Give FastAPI startup a chance to run if this process is the one hosting.
    email = "admin@akki.ai"
    password = os.environ.get("ADMIN_PASSWORD", "AkkiAdmin2026!")
    await _seed_account(email, password)

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await _login(client, email, password)
        headers = {"Authorization": f"Bearer {token}"}
        results: List[Dict[str, Any]] = []
        for i, scenario in enumerate(INTENTS, start=1):
            print(f"[{i:02d}/10] cluster={scenario['cluster_id']}", flush=True)
            try:
                res = await _walk_session(client, headers, scenario)
            except Exception as e:  # noqa: BLE001
                res = {"ok": False, "stage": "exception", "error": f"{e.__class__.__name__}: {e}"}
            results.append(res)
            print("    " + json.dumps(
                {k: v for k, v in res.items() if k not in {"body", "tier_distribution"}},
                default=str,
            ), flush=True)

        passed = sum(1 for r in results if r.get("ok"))
        pass_rate = passed / max(len(results), 1)
        print("\n=== Summary ===")
        print(f"Passed: {passed}/{len(results)} ({pass_rate*100:.0f}%)")
        print(f"Pass threshold: 90% — {'✓ MET' if pass_rate >= 0.9 else '✗ NOT MET'}")

        # Write full report to disk for reference
        out_path = Path("/tmp/solva_v2_10_sessions_report.json")
        out_path.write_text(
            json.dumps(
                {
                    "results": results, "passed": passed, "total": len(results),
                    "pass_rate": pass_rate,
                },
                default=str, indent=2,
            )
        )
        print(f"Full report: {out_path}")
        return 0 if pass_rate >= 0.9 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
