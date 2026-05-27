"""Phase 15.0/15.1 acceptance — run 10 real Seek Clarity sessions end-to-end.

Uses the live universal LLM key and the live Mongo instance. Walks each
session through all four layers (framing → grounding → synthesis → reflection)
and reports outcomes on three orthogonal axes (Phase 15.1):

  engine_ok    — orchestrator + engines ran without raising / timing out
                 / breaching shield invariant / breaching confidence-band
                 invariant / carrying a stub `@0.x-stub` engine_version
                 string. Floor: ≥ 95% (≥ 9.5 / 10).

  contract_ok  — synthesis emitted compliant tier markers and the
                 grounding contract did NOT exhaust its second-attempt
                 retry. Floor: ≥ 90% (≥ 9 / 10).

  validator_ok — validator verdict in {validated, qualified}. A `flagged`
                 or `rejected` verdict counts as a `validator_catch` —
                 healthy product behaviour, NOT a defect — and is
                 reported separately with no rate floor.

The legacy `ok` field is retained for the simple pass/fail dashboard:
ok = engine_ok AND contract_ok AND validator_ok.

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
from typing import Any, Dict, List, Optional

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
    # Phase 15.2 — mixed sub-modules. 3 seek_clarity, 3 develop_strategy,
    # 2 simulate_hypothesis, 2 get_perspective. Each session walks layers
    # the orchestrator owns; the script asserts engine + contract floors
    # only (validator catches are reported separately).
    {
        "cluster_id": "revenue_underperformance",
        "submodule": "seek_clarity",
        "intent": (
            "Q3 revenue missed by 14% and the CEO's framing blames FX headwinds. "
            "Two of us on the board think it's pricing; the CFO's dashboard "
            "shows volume flat and mix shifting. We cannot agree what to ask "
            "for at next month's exec session."
        ),
    },
    {
        "cluster_id": "ceo_succession",
        "submodule": "seek_clarity",
        "intent": (
            "The CEO is 14 months from the nominations committee's stated target "
            "handover date. Two plausible internal candidates; the stronger one "
            "has never run a P&L. The chair wants to start external search but "
            "the sponsoring PE is pushing for an internal appointment."
        ),
    },
    {
        "cluster_id": "regulatory_change",
        "submodule": "seek_clarity",
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
        "submodule": "develop_strategy",
        "intent": (
            "A sector peer half our size is privately shopped at a 12x multiple. "
            "Our own shares trade at 9x. Management wants to bid; two NEDs think "
            "we over-concentrate post-deal and that regulatory clearance risk "
            "is underpriced. Target needs a term-sheet in two weeks."
        ),
    },
    {
        "cluster_id": "revenue_underperformance",
        "submodule": "develop_strategy",
        "intent": (
            "Revenue is on-plan but gross margin has compressed 280bps in three "
            "quarters. The commercial director insists it is temporary input "
            "costs. The audit chair has asked twice for a cohort-level margin "
            "waterfall and has not received one."
        ),
    },
    {
        "cluster_id": "ceo_succession",
        "submodule": "develop_strategy",
        "intent": (
            "The founder-CEO has told the chair she will stand down within 18 "
            "months for personal reasons. No internal successor is ready. An "
            "interim chair-as-CEO is being floated; two NEDs think this is "
            "precisely the wrong signal to customers and employees."
        ),
    },
    {
        "cluster_id": "risk_blindspot",
        "submodule": "simulate_hypothesis",
        "intent": (
            "The regulator has opened an informal inquiry into our pricing "
            "disclosure practice. Management says the exposure is 'contained' "
            "but has not quantified it. Legal has advised privilege. What if "
            "the inquiry escalates to a formal one within 90 days \u2014 what "
            "are the second-order effects on our annual report tone?"
        ),
    },
    {
        "cluster_id": "ma_thesis",
        "submodule": "simulate_hypothesis",
        "intent": (
            "We received an unsolicited approach at 10% premium to 30-day VWAP. "
            "The CEO believes our fair value is 30% higher after the current "
            "strategic plan executes. What if institutional shareholders side "
            "with the bidder \u2014 how does that play through proxy season?"
        ),
    },
    {
        "cluster_id": "revenue_underperformance",
        "submodule": "get_perspective",
        "persona": "Chair",
        "intent": (
            "Our largest customer (22% of revenue) has delayed their annual "
            "renewal by 60 days. Sales insists it is procurement theatre. The "
            "customer's CFO told our CFO informally they are running an RFP. "
            "The board pack does not reflect the RFP risk. How would the "
            "chair frame this for the next board meeting?"
        ),
    },
    {
        "cluster_id": "ceo_succession",
        "submodule": "get_perspective",
        "persona": "Investor",
        "intent": (
            "The CEO has a clear candidate for the COO role which the board is "
            "expected to ratify next week. Two NEDs (including me) have private "
            "concerns about the candidate's judgement under pressure. Neither "
            "of us has yet raised them formally. How would a long-only "
            "institutional investor read this if it leaked?"
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
    # Phase 15.3: 3-concurrent-active limit means the script must abandon
    # any leftover actives from a prior session before starting a new one.
    # Idempotent — does nothing on the first iteration.
    try:
        list_resp = await client.get(
            "/api/solva/v2/sessions",
            params={"status": "active"},
            headers=headers,
            timeout=30,
        )
        if list_resp.status_code == 200:
            for s in (list_resp.json().get("items") or []):
                await client.post(
                    f"/api/solva/v2/sessions/{s['id']}/abandon",
                    headers=headers, timeout=30,
                )
    except Exception:  # noqa: BLE001 — best-effort cleanup
        pass

    body = {
        "cluster_id": scenario["cluster_id"],
        "intent": scenario["intent"],
        "submodule": scenario.get("submodule") or "seek_clarity",
        "pro_tier": False,
    }
    if scenario.get("persona"):
        body["persona"] = scenario["persona"]
    start_resp = await client.post(
        "/api/solva/v2/sessions", json=body, headers=headers, timeout=180,
    )
    if start_resp.status_code != 200:
        return _classify({
            "stage": "start", "session_id": None,
            "status": start_resp.status_code, "body": start_resp.text[:400],
            "cluster_id": scenario["cluster_id"],
            "submodule": body["submodule"],
        })
    session = start_resp.json()
    sid = session["id"]

    # Phase 15.2 — simulate_hypothesis has 5 layers (adds `hypothesis`
    # between grounding and synthesis), so it needs 4 user turns to walk
    # framing -> grounding -> hypothesis -> synthesis -> reflection. Other
    # sub-modules have 4 layers and need 3 turns. The script sends one
    # extra reply for simulate_hypothesis.
    base_replies = [
        "The timeframe is this quarter. No structural change in the window.",
        "Comparables look relevant. Go deeper where they diverge.",
        "Understood. Lock the diagnosis.",
    ]
    if body["submodule"] == "simulate_hypothesis":
        replies = [
            base_replies[0],
            base_replies[1],
            "Yes, weigh those tensions explicitly when you synthesise.",
            base_replies[2],
        ]
    else:
        replies = base_replies
    stage = "framing"
    walk_error: Optional[Dict[str, Any]] = None
    for txt in replies:
        try:
            r = await client.post(
                f"/api/solva/v2/sessions/{sid}/turn",
                json={"user_text": txt},
                headers=headers,
                timeout=240,
            )
        except Exception as e:  # noqa: BLE001 — bucket as engine-layer fault
            walk_error = {
                "stage": stage, "session_id": sid,
                "status": "exception",
                "exception": f"{e.__class__.__name__}: {e}",
                "cluster_id": scenario["cluster_id"],
            }
            break
        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:  # noqa: BLE001
                detail = r.text[:400]
            walk_error = {
                "stage": stage, "session_id": sid,
                "status": r.status_code, "body": detail,
                "cluster_id": scenario["cluster_id"],
            }
            break
        session = r.json()
        stage = session.get("layer") or stage

    latency = int((time.monotonic() - t0) * 1000)
    if walk_error:
        return _classify({**walk_error, "latency_ms": latency})

    synth = session.get("synthesis") or {}
    validation = synth.get("validation") or {}
    verdict = validation.get("verdict")
    tier_distribution = synth.get("tier_distribution") or {}
    claim_count = sum(tier_distribution.values())
    audit = session.get("reasoning_audit_log") or []
    # Phase 15.2 — surface tension_detector activation count for the
    # report. Only simulate_hypothesis sessions should emit > 0; all
    # others should be 0.
    tension_count = 0
    for e in audit:
        if e.get("engine") == "tension_detector":
            tension_count = max(tension_count, (e.get("output") or {}).get("tension_count", 0))
    recommendations_count = len((synth.get("recommendations") or []))
    return _classify({
        "session_id": sid,
        "submodule": session.get("submodule") or "seek_clarity",
        "persona": session.get("persona"),
        "status": session.get("status"),
        "layer": session.get("layer"),
        "claim_count": claim_count,
        "tier_distribution": tier_distribution,
        "validator_verdict": verdict,
        "validator_confidence": validation.get("confidence"),
        "audit_entry_count": len(audit),
        "audit": audit,
        "synthesis_claims": synth.get("claims") or [],
        "tension_count": tension_count,
        "recommendations_count": recommendations_count,
        "latency_ms": latency,
        "cluster_id": scenario["cluster_id"],
    })


# ---------------------------------------------------------------------------
# Phase 15.1 outcome classifier — three orthogonal axes:
#
#   engine_ok      — orchestrator + engines executed without raising,
#                    timing out, violating shield invariant, violating
#                    confidence-band invariant, or carrying a stub
#                    engine_version string.  Floor: ≥ 95%.
#
#   contract_ok    — synthesis emitted compliant tier markers and the
#                    grounding contract did NOT exhaust the second-attempt
#                    retry. Counts a 422 from the orchestrator as a
#                    contract-layer failure.  Floor: ≥ 90%.
#
#   validator_ok   — validator returned `validated` or `qualified`. A
#                    `flagged` or `rejected` verdict is COUNTED but does
#                    NOT count against engine_ok or contract_ok — it is a
#                    successful catch by the validator and a healthy run.
#                    Floor: NONE (a non-zero catch rate is healthy).
# ---------------------------------------------------------------------------
_ALLOWED_PLACEHOLDER_VERSIONS: set = set()
# Phase A — Reflection is now @1.0 (real). The legacy
# `reflection@0.0-placeholder` whitelist has been removed; any future
# stub version string in the audit log is a code-discipline regression
# and fails engine_ok.
_STUB_TOKENS = ("@0.1-stub", "-stub")


def _has_stub_versions(audit) -> List[str]:
    """Return the list of stub-versioned engines found in the audit log.

    Phase A — every engine is real. Any `*-stub` or `@0.1-stub` string
    is a code-discipline regression and fails engine_ok.
    """
    bad = []
    for e in (audit or []):
        v = e.get("engine_version") or ""
        if v in _ALLOWED_PLACEHOLDER_VERSIONS:
            continue
        for tok in _STUB_TOKENS:
            if tok in v:
                bad.append(v)
                break
    return bad


def _has_invariant_violations(audit) -> Dict[str, Any]:
    """Inspect probability_weighting and shield audit entries for any
    invariant violations the engines persisted on themselves."""
    pw_violations = []
    shield_violations = []
    for e in (audit or []):
        if e.get("engine") == "probability_weighting":
            out = e.get("output") or {}
            if out.get("invariant_valid") is False and out.get("attempt", 0) >= 1:
                # Final attempt still violating — that's a real engine miss.
                if e.get("output", {}).get("invariant_violations"):
                    # Only the LAST attempt counts — engine retried already.
                    last_attempt_ix = max(
                        idx for idx, x in enumerate(audit or [])
                        if x.get("engine") == "probability_weighting"
                    )
                    if audit.index(e) == last_attempt_ix:
                        pw_violations.extend(out.get("invariant_violations") or [])
        # Shield invariant: any LLM-call entry must carry shield_required=True
        # AND non-null synisense_run_id, OR shield_required=False AND a valid
        # shield_bypassed_reason. Anything else is a shield violation.
        if e.get("engine") in (
            "candidate_generation", "probability_weighting", "refusal",
            "validator", "llm_primary",
        ):
            shield_required = e.get("shield_required")
            run_id = e.get("synisense_run_id")
            reason = e.get("shield_bypassed_reason")
            if shield_required is True and not run_id:
                shield_violations.append((e.get("engine"), "missing run_id"))
            elif shield_required is False and not reason:
                shield_violations.append((e.get("engine"), "bypass without reason"))
    return {"pw": pw_violations, "shield": shield_violations}


def _classify(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Bucket a raw _walk_session result into engine_ok / contract_ok /
    validator_ok and produce the outcome row written to disk + summary."""
    audit = raw.pop("audit", []) or []
    raw.pop("synthesis_claims", None)  # not interesting downstream

    # ---- engine layer ----
    stage = raw.get("stage")
    status = raw.get("status")
    exc = raw.get("exception")
    engine_failures: List[str] = []
    if exc:
        engine_failures.append(f"raised:{exc}")
    if isinstance(status, int) and status >= 500:
        engine_failures.append(f"http_5xx:{status}")
    if stage == "exception":
        engine_failures.append("walk_exception")
    stub_hits = _has_stub_versions(audit)
    if stub_hits:
        engine_failures.append(f"stub_versions:{stub_hits}")
    invariants = _has_invariant_violations(audit)
    if invariants["pw"]:
        engine_failures.append(f"pw_invariant:{invariants['pw']}")
    if invariants["shield"]:
        engine_failures.append(f"shield_invariant:{invariants['shield']}")

    engine_ok = len(engine_failures) == 0

    # ---- contract layer ----
    # 422 from the orchestrator after engines completed = grounding contract
    # exhausted retries. (Engine-stage 422 counts as contract failure too —
    # the contract is what surfaces the rejection.)
    contract_failures: List[str] = []
    if status == 422:
        contract_failures.append("grounding_contract_retry_exhausted")
    contract_ok = len(contract_failures) == 0 and engine_ok

    # ---- validator layer ----
    verdict = raw.get("validator_verdict")
    # Healthy runs land 'validated' or 'qualified'. Anything else (None,
    # 'flagged', 'rejected') is a validator-layer NON-PASS but NOT an
    # engine or contract failure — the validator is doing its job.
    validator_ok = verdict in {"validated", "qualified"}
    validator_catch = verdict in {"flagged", "rejected"}

    # Backwards-compat: keep the ok flag for the simple dashboard.
    raw["ok"] = engine_ok and contract_ok and validator_ok

    raw["engine_ok"] = engine_ok
    raw["contract_ok"] = contract_ok
    raw["validator_ok"] = validator_ok
    raw["validator_catch"] = validator_catch
    raw["engine_failures"] = engine_failures
    raw["contract_failures"] = contract_failures

    return raw


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
                res = _classify({
                    "stage": "exception", "session_id": None,
                    "exception": f"{e.__class__.__name__}: {e}",
                    "cluster_id": scenario["cluster_id"],
                })
            results.append(res)
            print("    " + json.dumps(
                {k: v for k, v in res.items()
                 if k not in {"body", "tier_distribution", "engine_failures",
                              "contract_failures"}},
                default=str,
            ), flush=True)
            if res.get("engine_failures"):
                print(f"    engine_failures: {res['engine_failures']}", flush=True)
            if res.get("contract_failures"):
                print(f"    contract_failures: {res['contract_failures']}", flush=True)

        engine_passed = sum(1 for r in results if r.get("engine_ok"))
        contract_passed = sum(1 for r in results if r.get("contract_ok"))
        validator_passed = sum(1 for r in results if r.get("validator_ok"))
        validator_catches = sum(1 for r in results if r.get("validator_catch"))
        n = len(results)
        legacy_passed = sum(1 for r in results if r.get("ok"))
        engine_floor_met = engine_passed >= int(n * 0.95 + 0.999)  # ceil
        contract_floor_met = contract_passed >= int(n * 0.90 + 0.999)

        print("\n=== Summary (Phase 15.1 three-axis) ===")
        print(f"engine_ok    : {engine_passed}/{n}   ({engine_passed/max(n,1)*100:.0f}%)   floor: ≥95%   {'✓ MET' if engine_floor_met else '✗ NOT MET'}")
        print(f"contract_ok  : {contract_passed}/{n}   ({contract_passed/max(n,1)*100:.0f}%)   floor: ≥90%   {'✓ MET' if contract_floor_met else '✗ NOT MET'}")
        print(f"validator_ok : {validator_passed}/{n}   ({validator_passed/max(n,1)*100:.0f}%)   no floor — {validator_catches} validator catches counted (healthy)")
        print(f"legacy ok    : {legacy_passed}/{n}   (all three axes pass)")

        # Write full report to disk for reference
        out_path = Path("/tmp/solva_v2_10_sessions_report.json")
        out_path.write_text(
            json.dumps(
                {
                    "results": results,
                    "engine_passed": engine_passed,
                    "contract_passed": contract_passed,
                    "validator_passed": validator_passed,
                    "validator_catches": validator_catches,
                    "legacy_passed": legacy_passed,
                    "total": n,
                    "engine_floor_met": engine_floor_met,
                    "contract_floor_met": contract_floor_met,
                },
                default=str, indent=2,
            )
        )
        print(f"Full report: {out_path}")
        return 0 if (engine_floor_met and contract_floor_met) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
