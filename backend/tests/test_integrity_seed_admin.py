"""Issue 2 — Deterministic reproducer for the admin@akki.ai
Solva v2 `integrity_failed` cohort.

Marked `integrity_seed` so CI can opt-in / opt-out:
    pytest -m integrity_seed                # run only this reproducer
    pytest -m "not integrity_seed"          # exclude

The test walks every Solva v2 session belonging to `admin@akki.ai`,
runs `validate_artefact` (the real, live validator), and asserts NO
session trips. Currently the assertion fails with a detailed offender
breakdown — that's the deterministic reproducer for the bug.

The test reads from the live MongoDB at backend/.env::MONGO_URL. No
fixture / synthetic data. If `admin@akki.ai` doesn't exist or has no
Solva v2 sessions, the test SKIPS — never silently passes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from services.solva_v2.payload_builder import build_payload  # noqa: E402
from services.solva_v2.integrity_validators import validate_artefact  # noqa: E402


def _sync_db():
    """Sync pymongo handle — avoids async-loop binding so the test
    can run inside any test runner shape."""
    import pymongo
    url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    return pymongo.MongoClient(url)[db_name]


@pytest.mark.integrity_seed
def test_admin_solva_v2_sessions_pass_integrity():
    """The admin@akki.ai cohort must validate cleanly under
    `validate_artefact`. Currently fails — see
    /app/memory/sprints/issue2_integrity_failed_diagnosis.md for the
    root cause."""
    db = _sync_db()
    acct = db.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1, "email": 1},
    )
    if not acct:
        pytest.skip("admin@akki.ai account not seeded in this DB")

    sessions: List[Dict[str, Any]] = list(
        db.solva_v2_sessions.find({"account_id": acct["id"]}, {"_id": 0})
    )
    if not sessions:
        pytest.skip("admin@akki.ai has no Solva v2 sessions seeded")

    fail_total = 0
    fail_by_validator: Dict[str, int] = {}
    fail_examples: List[Dict[str, Any]] = []
    build_errors = 0

    for s in sessions:
        try:
            payload = build_payload(s, context_name="IntegritySeed")
        except Exception as e:  # noqa: BLE001
            build_errors += 1
            fail_examples.append({
                "session_id": s.get("id"),
                "build_error": f"{type(e).__name__}: {str(e)[:200]}",
            })
            continue
        result = validate_artefact(payload, s)
        if result.ok:
            continue
        fail_total += 1
        for o in result.blocking:
            fail_by_validator[o.validator] = (
                fail_by_validator.get(o.validator, 0) + 1
            )
        if len(fail_examples) < 3:
            fail_examples.append({
                "session_id": s.get("id"),
                "submodule": s.get("submodule"),
                "cluster_id": s.get("cluster_id") or s.get("seed_cluster"),
                "blocking": [
                    {
                        "validator": o.validator,
                        "location": o.location,
                        "message": o.message,
                    }
                    for o in result.blocking[:6]
                ],
            })

    if fail_total or build_errors:
        import json
        msg_lines = [
            f"{fail_total} / {len(sessions)} admin Solva v2 sessions fail integrity validation.",
        ]
        if build_errors:
            msg_lines.append(f"Plus {build_errors} build errors.")
        msg_lines.append(f"Failure by validator: {fail_by_validator!r}")
        msg_lines.append("Example offenders:")
        msg_lines.append(json.dumps(fail_examples, indent=2))
        pytest.fail("\n".join(msg_lines))


@pytest.mark.integrity_seed
def test_admin_failure_dominant_validator_is_confidence_calibration():
    """Lock the diagnosis — the dominant validator currently firing
    on the admin cohort MUST be `confidence_calibration_audit`. If
    this assertion changes, the diagnosis in
    `issue2_integrity_failed_diagnosis.md` needs revisiting.

    Will go GREEN once `_build_scenarios` is patched to emit ≥2
    independent supporting_evidence entries per high-confidence scenario.
    Until then, the assertion holds the regression record.
    """
    db = _sync_db()
    acct = db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not acct:
        pytest.skip("admin@akki.ai account not seeded in this DB")
    sessions = list(db.solva_v2_sessions.find({"account_id": acct["id"]}, {"_id": 0}))
    if not sessions:
        pytest.skip("admin@akki.ai has no Solva v2 sessions seeded")

    fail_by_validator: Dict[str, int] = {}
    for s in sessions:
        try:
            payload = build_payload(s, context_name="IntegritySeed")
        except Exception:  # noqa: BLE001
            continue
        result = validate_artefact(payload, s)
        if result.ok:
            continue
        for o in result.blocking:
            fail_by_validator[o.validator] = fail_by_validator.get(o.validator, 0) + 1

    if not fail_by_validator:
        pytest.skip(
            "No integrity failures observed in this DB — fix may already be applied, "
            "or admin sessions are clean. Diagnosis (and this lock) supersede when "
            "fail_by_validator is empty."
        )
    dominant = max(fail_by_validator.items(), key=lambda kv: kv[1])
    assert dominant[0] == "confidence_calibration_audit", (
        f"Diagnosis lock: dominant failing validator should be "
        f"`confidence_calibration_audit`. Got: {fail_by_validator!r}"
    )
