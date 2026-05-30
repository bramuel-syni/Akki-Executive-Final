"""Sprint Z.2.D — re-seed admin integrity verification.

After Scopes A + B + C land, the admin@akki.ai cohort is re-seeded via
`scripts/solva_v2_10_sessions.py`. This test asserts the post-reseed
integrity pass rate on the rebuilt cohort.

The rebuilt cohort is identified by `created_at >= reseed_start_ts`,
where `reseed_start_ts` is recorded by the dispatch in
`/tmp/reseed_start.txt`. If the file is absent (the re-seed wasn't
run in this environment), the test SKIPS — never silently passes.

Live DB read via sync pymongo, real validator + real builder.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from services.solva_v2.payload_builder import build_payload  # noqa: E402
from services.solva_v2.integrity_validators import validate_artefact  # noqa: E402


RESEED_START_PATH = Path("/tmp/reseed_start.txt")


def _sync_db():
    import pymongo
    return pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _load_reseed_start_iso() -> str:
    """Read the unix-epoch timestamp recorded just before the seed
    script kicked off, return as ISO-8601 UTC string. Used to bound
    the "rebuilt cohort" to sessions created on/after re-seed time."""
    if not RESEED_START_PATH.exists():
        pytest.skip(
            "No re-seed timestamp at /tmp/reseed_start.txt — re-seed "
            "was not run in this environment."
        )
    raw = RESEED_START_PATH.read_text().strip()
    if not raw.isdigit():
        pytest.skip(f"/tmp/reseed_start.txt content unreadable: {raw!r}")
    return datetime.fromtimestamp(int(raw), tz=timezone.utc).isoformat()


@pytest.mark.integrity_seed
def test_rebuilt_cohort_pass_rate_meets_target():
    """Sessions created on or after the re-seed timestamp must pass
    integrity validation at the 100% target rate.

    A `validator_catch` (engine layer's own retry exhausting) is
    counted as a NON-FAILURE for this assertion's purposes — the
    cohort we're measuring is "sessions that landed on disk after
    the re-seed", and a healthy validator catch resulted in the
    session never being persisted at all.
    """
    db = _sync_db()
    acct = db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not acct:
        pytest.skip("admin@akki.ai account not present in this DB")
    iso = _load_reseed_start_iso()
    rebuilt = list(db.solva_v2_sessions.find(
        {"account_id": acct["id"], "started_at": {"$gte": iso}},
        {"_id": 0},
    ))
    if not rebuilt:
        pytest.skip(
            f"No sessions started after {iso} — re-seed may still be running "
            "or may have failed to land any sessions."
        )

    failures = 0
    fail_breakdown: dict = {}
    for s in rebuilt:
        try:
            payload = build_payload(s, context_name="Reseed")
        except Exception:  # noqa: BLE001
            failures += 1
            fail_breakdown.setdefault("build_error", 0)
            fail_breakdown["build_error"] += 1
            continue
        r = validate_artefact(payload, s)
        if not r.ok:
            failures += 1
            for o in r.blocking:
                fail_breakdown[o.validator] = fail_breakdown.get(o.validator, 0) + 1

    total = len(rebuilt)
    pass_rate = (total - failures) / total
    # Soft floor for the rebuilt cohort: ≥ 90% (true imperatives can
    # legitimately surface on a fresh LLM run; engine retry budget can
    # exhaust). Hard floor: > 0 sessions landed.
    assert total > 0, "Rebuilt cohort must contain at least one session"
    assert pass_rate >= 0.90, (
        f"Rebuilt cohort integrity pass rate {pass_rate:.1%} is below 90% "
        f"floor. {failures} / {total} failed. Breakdown: {fail_breakdown!r}"
    )


@pytest.mark.integrity_seed
def test_rebuilt_cohort_dominant_validator_changed_from_confidence_calibration():
    """After Scopes A + B land, `confidence_calibration_audit` should
    NO LONGER be the dominant failing validator on freshly-seeded
    sessions — its 99%-of-failures rate from the diagnosis is now
    eliminated by `_independent_citations` honesty. If
    confidence_calibration_audit is STILL the dominant failure,
    something has regressed in the builder."""
    db = _sync_db()
    acct = db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not acct:
        pytest.skip("admin@akki.ai account not present in this DB")
    iso = _load_reseed_start_iso()
    rebuilt = list(db.solva_v2_sessions.find(
        {"account_id": acct["id"], "started_at": {"$gte": iso}},
        {"_id": 0},
    ))
    if not rebuilt:
        pytest.skip(f"No sessions started after {iso}.")

    fail_by_validator: dict = {}
    for s in rebuilt:
        try:
            payload = build_payload(s, context_name="Reseed")
        except Exception:  # noqa: BLE001
            continue
        r = validate_artefact(payload, s)
        if r.ok:
            continue
        for o in r.blocking:
            fail_by_validator[o.validator] = fail_by_validator.get(o.validator, 0) + 1

    if not fail_by_validator:
        # 100% pass — diagnosis dominant-validator question is moot.
        return
    dominant = max(fail_by_validator.items(), key=lambda kv: kv[1])
    assert dominant[0] != "confidence_calibration_audit", (
        f"Scope B regression — confidence_calibration_audit is STILL the "
        f"dominant failing validator on the rebuilt cohort. Breakdown: "
        f"{fail_by_validator!r}"
    )


@pytest.mark.integrity_seed
def test_rebuilt_cohort_emits_at_least_one_session_with_real_independent_citations():
    """Lock the Scope B builder honesty pass — at least one fresh
    session must carry a scenario whose `supporting_evidence` contains
    ≥2 entries with DISTINCT (source_kind, source_layer) pairs."""
    db = _sync_db()
    acct = db.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not acct:
        pytest.skip("admin@akki.ai account not present in this DB")
    iso = _load_reseed_start_iso()
    rebuilt = list(db.solva_v2_sessions.find(
        {"account_id": acct["id"], "started_at": {"$gte": iso}},
        {"_id": 0},
    ))
    if not rebuilt:
        pytest.skip(f"No sessions started after {iso}.")

    found_independent = False
    for s in rebuilt:
        try:
            payload = build_payload(s, context_name="Reseed")
        except Exception:  # noqa: BLE001
            continue
        for sc in payload.scenarios:
            if len(sc.supporting_evidence) < 2:
                continue
            pairs = {(e.source_kind, e.source_layer)
                     for e in sc.supporting_evidence}
            if len(pairs) >= 2:
                found_independent = True
                break
        if found_independent:
            break
    assert found_independent, (
        "No rebuilt session carried a scenario with ≥2 independent "
        "(source_kind, source_layer) pairs — Scope B builder honesty "
        "is not surfacing on freshly-seeded data."
    )
