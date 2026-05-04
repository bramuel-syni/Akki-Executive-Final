"""Phase 15.0 hardening — shield_required / shield_bypassed_reason invariant.

The reasoning_audit_log carries an explicit shield posture on every entry.
The contract is:
    shield_required=True   -> synisense_run_id NON-null,
                              shield_bypassed_reason MUST be None
    shield_required=False  -> synisense_run_id MUST be None,
                              shield_bypassed_reason in SHIELD_BYPASS_REASONS

This test asserts the invariant by sweeping a freshly-completed Seek Clarity
session's full audit log.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest
from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
load_dotenv("/app/backend/.env")

import httpx  # noqa: E402
import server  # noqa: E402
from core import db, hash_password  # noqa: E402
from services.solva_v2.llm_adapter import (  # noqa: E402
    SHIELD_BYPASS_REASONS,
    synthetic_audit_entry,
)


def _check_invariant(entry: dict) -> None:
    assert "shield_required" in entry, f"missing shield_required: {entry.get('engine')}"
    assert "shield_bypassed_reason" in entry, (
        f"missing shield_bypassed_reason: {entry.get('engine')}"
    )
    if entry["shield_required"]:
        assert entry.get("synisense_run_id"), (
            f"shield_required=True but synisense_run_id is null on engine={entry.get('engine')}"
        )
        assert entry["shield_bypassed_reason"] is None, (
            f"shield_required=True but shield_bypassed_reason set on engine={entry.get('engine')}"
        )
    else:
        assert entry.get("synisense_run_id") is None, (
            f"shield_required=False but synisense_run_id present on engine={entry.get('engine')}"
        )
        assert entry["shield_bypassed_reason"] in SHIELD_BYPASS_REASONS, (
            f"invalid shield_bypassed_reason {entry['shield_bypassed_reason']!r} "
            f"on engine={entry.get('engine')}"
        )


# ---------------------------------------------------------------------------
# Unit-level invariant checks on synthetic_audit_entry
# ---------------------------------------------------------------------------
async def test_synthetic_audit_rejects_missing_reason():
    with pytest.raises(ValueError, match="shield_bypassed_reason"):
        await synthetic_audit_entry(
            engine="triangulation",
            layer="grounding",
            turn_id="t1",
            output={"x": 1},
            shield_required=False,
            shield_bypassed_reason=None,  # invalid: must be one of the 3
        )


async def test_synthetic_audit_rejects_bad_reason():
    with pytest.raises(ValueError, match="shield_bypassed_reason"):
        await synthetic_audit_entry(
            engine="triangulation",
            layer="grounding",
            turn_id="t1",
            output={"x": 1},
            shield_required=False,
            shield_bypassed_reason="just_because",  # not in vocabulary
        )


async def test_synthetic_audit_rejects_required_without_run_id():
    with pytest.raises(ValueError, match="must carry synisense_run_id"):
        await synthetic_audit_entry(
            engine="validator",
            layer="synthesis",
            turn_id="t1",
            output={"x": 1},
            shield_required=True,
            synisense_run_id=None,  # invalid: required must have run_id
        )


async def test_synthetic_audit_rejects_run_id_when_not_required():
    with pytest.raises(ValueError, match="must NOT carry synisense_run_id"):
        await synthetic_audit_entry(
            engine="triangulation",
            layer="grounding",
            turn_id="t1",
            output={"x": 1},
            shield_required=False,
            shield_bypassed_reason="deterministic_only",
            synisense_run_id="leaked-id",  # invalid: bypassed must not have run_id
        )


async def test_synthetic_audit_accepts_validator_with_upstream_run_id():
    """The validator pattern: shield_required=True + run_id reused from upstream."""
    entry = await synthetic_audit_entry(
        engine="validator",
        layer="synthesis",
        turn_id="t1",
        output={"verdict": "validated"},
        shield_required=True,
        synisense_run_id="upstream-run-abc",
    )
    _check_invariant(entry)
    assert entry["engine"] == "validator"
    assert entry["synisense_run_id"] == "upstream-run-abc"


# ---------------------------------------------------------------------------
# End-to-end invariant sweep against a real session's audit log
# ---------------------------------------------------------------------------
async def test_invariant_holds_across_full_session(monkeypatch):
    """Drive a complete Seek Clarity session with mocked LLM and prove every
    audit entry obeys the shield invariant."""
    call_counter = {"n": 0}

    valid_synth = (
        "Revenue slipped 14% last quarter [T:corpus]. A comparable mid-cap bank "
        "found onboarding friction [T:comparable]. Boards misdiagnose this often "
        "[T:domain_prior]. The CEO asserted macro [T:user_assertion]. "
        "Pricing may be the real cause [T:speculation]. What does the dashboard show?"
    )
    framing_reply = "What is the timeframe? Was pricing changed in the window?"

    async def fake_call(**kwargs):
        call_counter["n"] += 1
        body = framing_reply if call_counter["n"] == 1 else valid_synth
        return (
            {"response": body, "model": "claude-sonnet-4-5-20250929",
             "tier": "standard", "mode": "live"},
            {"downgraded": False, "served_tier": "standard"},
        )

    async def fake_validate(**kwargs):
        return {
            "verdict": "validated", "confidence": 80,
            "notes": ["mock"],
            "validator_provider": "gemini", "validator_model": "gemini-2.5-flash",
        }

    monkeypatch.setattr("llm_tier_quota.call_llm_with_tier", fake_call)
    monkeypatch.setattr("llm_service.validate_independent", fake_validate)

    email = f"solva-v2-inv-{uuid.uuid4().hex[:8]}@solva-v2-test.ai"
    aid = str(uuid.uuid4())
    password = "InvTest2026!"
    await db.accounts.insert_one({
        "id": aid, "email": email, "name": "Inv Sweep",
        "declared_role": "ned",
        "password_hash": hash_password(password),
        "mfa_enabled": False, "is_superadmin": False,
        "solva_v2_poc": True, "plan": "free",
        "created_at": "2026-05-04T00:00:00Z",
    })
    try:
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            login = await client.post(
                "/api/auth/login",
                json={"email": email, "password": password},
            )
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            clusters = (await client.get("/api/solva/clusters", headers=headers)).json()["clusters"]

            start = await client.post(
                "/api/solva/v2/sessions",
                json={
                    "cluster_id": clusters[0]["id"],
                    "intent": "Test invariant sweep across a complete Seek Clarity session.",
                    "submodule": "seek_clarity",
                },
                headers=headers,
            )
            sid = start.json()["id"]

            for txt in [
                "Timeframe is this quarter. Pricing flat.",
                "Comparables relevant.",
                "Move on.",
            ]:
                r = await client.post(
                    f"/api/solva/v2/sessions/{sid}/turn",
                    json={"user_text": txt},
                    headers=headers,
                )
                assert r.status_code == 200, r.text

            log = (await client.get(
                f"/api/solva/v2/sessions/{sid}/reasoning-log", headers=headers
            )).json()
            entries = log["entries"]
            assert len(entries) > 0

            engines_seen = set()
            for e in entries:
                _check_invariant(e)
                engines_seen.add(e["engine"])

            # Phase 15.0 hardening: ensure the placeholder rename for reflection
            # took effect and that the validator entry now declares
            # shield_required=True with a real run_id.
            assert "placeholder" in engines_seen, (
                f"reflection placeholder not renamed; engines seen: {engines_seen}"
            )
            assert "validator" in engines_seen
            validator_entry = next(e for e in entries if e["engine"] == "validator")
            assert validator_entry["shield_required"] is True
            assert validator_entry["synisense_run_id"]
            assert validator_entry["shield_bypassed_reason"] is None
    finally:
        await db.accounts.delete_one({"id": aid})
        await db.solva_v2_sessions.delete_many({"account_id": aid})
