"""Integration test - full Seek Clarity session end-to-end with mocked LLM.

Phase 15.0 hardening pass: migrated to pytest-asyncio (auto mode set in
pytest.ini). The whole flow runs inside one event loop so Motor's client
binds cleanly and the test cleans up without the cross-test loop fragility
that asyncio.run() introduced.
"""
from __future__ import annotations

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


VALID_SYNTH_BODY = (
    "Revenue slipped 14% last quarter [T:corpus]. A comparable mid-cap bank "
    "found the cause was onboarding friction [T:comparable]. The board may "
    "be avoiding the pricing question [T:speculation]. The CEO asserted macro "
    "headwinds were decisive [T:user_assertion]. Boards often misdiagnose "
    "macro as root cause [T:domain_prior]. What does the activation-rate "
    "dashboard show?"
)

FRAMING_REPLY = (
    "You have named a revenue miss and a disagreement over cause. "
    "What is the timeframe of the miss, and was pricing changed in the window?"
)


async def test_full_seek_clarity_session_end_to_end(monkeypatch):
    """Full v2 flow under pytest-asyncio. One event loop for the whole test."""
    call_counter = {"n": 0}

    # Phase 15.1 — surface-aware mock. New engines (refusal / candidate
    # generation / probability weighting) parse strict JSON; the old
    # call-counter pattern returned plain text and crashed those parsers.
    REFUSAL_JSON = (
        '{"category": "clean", "confidence": 0.9, "reason": "ordinary question"}'
    )
    CANDIDATES_JSON = (
        '{"candidates": ['
        '{"hypothesis": "Pricing change drove the revenue miss this quarter", '
        '"tentative_tier_hint": "comparable"},'
        '{"hypothesis": "Macro headwinds account for the quarterly revenue gap", '
        '"tentative_tier_hint": "domain_prior"},'
        '{"hypothesis": "Customer onboarding friction reduced revenue conversion", '
        '"tentative_tier_hint": "speculation"}'
        ']}'
    )
    RATINGS_JSON_6 = (
        '{"ratings": ['
        '{"confidence_pct": 80, "rationale": "corpus"},'
        '{"confidence_pct": 65, "rationale": "comparable"},'
        '{"confidence_pct": 55, "rationale": "speculation bounded"},'
        '{"confidence_pct": 60, "rationale": "user assertion"},'
        '{"confidence_pct": 55, "rationale": "domain prior"},'
        '{"confidence_pct": 50, "rationale": "open question"}'
        ']}'
    )

    async def fake_call_llm_with_tier(**kwargs):
        call_counter["n"] += 1
        surface = kwargs.get("surface") or ""
        if surface == "solve_v2.refusal":
            body = REFUSAL_JSON
        elif surface == "solve_v2.candidate_generation":
            body = CANDIDATES_JSON
        elif surface == "solve_v2.probability_weighting":
            body = RATINGS_JSON_6
        elif surface == "solve_v2.synthesis":
            body = VALID_SYNTH_BODY
        else:
            body = FRAMING_REPLY
        return (
            {
                "response": body,
                "model": "claude-sonnet-4-5-20250929",
                "tier": "standard",
                "mode": "live",
            },
            {"downgraded": False, "served_tier": "standard"},
        )

    async def fake_validate(**kwargs):
        return {
            "verdict": "validated",
            "confidence": 82,
            "notes": ["integration-test mock"],
            "validator_provider": "gemini",
            "validator_model": "gemini-2.5-flash",
        }

    monkeypatch.setattr("llm_tier_quota.call_llm_with_tier", fake_call_llm_with_tier)
    monkeypatch.setattr("llm_service.validate_independent", fake_validate)

    email = f"solva-v2-int-{uuid.uuid4().hex[:8]}@solva-v2-test.ai"
    aid = str(uuid.uuid4())
    password = "IntTest2026!"

    await db.accounts.insert_one({
        "id": aid,
        "email": email,
        "name": "Solva v2 Int",
        "declared_role": "ned",
        "password_hash": hash_password(password),
        "mfa_enabled": False,
        "is_superadmin": False,
        "solva_v2_poc": True,
        "plan": "free",
        "created_at": "2026-05-04T00:00:00Z",
    })
    try:
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            login = await client.post(
                "/api/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            clusters_resp = await client.get("/api/solva/clusters", headers=headers)
            assert clusters_resp.status_code == 200
            clusters = clusters_resp.json().get("clusters") or []
            assert clusters, "Clusters not seeded; cannot run integration."
            cluster_id = clusters[0]["id"]

            # 1. Start session
            start = await client.post(
                "/api/solva/v2/sessions",
                json={
                    "cluster_id": cluster_id,
                    "intent": (
                        "Q3 revenue missed by 14%. CEO says macro; two of us think "
                        "pricing. Not sure what to ask next month."
                    ),
                    "submodule": "seek_clarity",
                    "pro_tier": False,
                },
                headers=headers,
            )
            assert start.status_code == 200, start.text
            session = start.json()
            sid = session["id"]
            assert session["version"] == 2
            assert session["submodule"] == "seek_clarity"
            assert session["layer"] == "framing"
            assert len(session["turns"]) == 1
            assert session["turns"][0]["role"] == "solva"
            audit = session["reasoning_audit_log"]
            assert len(audit) >= 2
            for e in audit:
                assert "synisense_run_id" in e
                # Phase 15.0 hardening: every entry must declare its shield posture.
                assert "shield_required" in e
                assert "shield_bypassed_reason" in e

            # 2. framing -> grounding
            t2 = await client.post(
                f"/api/solva/v2/sessions/{sid}/turn",
                json={"user_text": "The timeframe is this quarter. Pricing was flat."},
                headers=headers,
            )
            assert t2.status_code == 200, t2.text
            session = t2.json()
            assert session["layer"] == "grounding", f"expected grounding, got {session['layer']}"

            # 3. grounding -> synthesis
            t3 = await client.post(
                f"/api/solva/v2/sessions/{sid}/turn",
                json={"user_text": "Comparables look relevant. Go deeper."},
                headers=headers,
            )
            assert t3.status_code == 200, t3.text
            session = t3.json()
            assert session["layer"] == "synthesis"
            synth = session.get("synthesis")
            assert synth is not None
            assert synth["claims"], "synthesis must carry parsed claims"
            total = sum(synth["tier_distribution"].values())
            assert total == len(synth["claims"])
            assert synth["validation"]["verdict"] == "validated"

            # 4. synthesis -> reflection (completed)
            t4 = await client.post(
                f"/api/solva/v2/sessions/{sid}/turn",
                json={"user_text": "Understood. Move on."},
                headers=headers,
            )
            assert t4.status_code == 200, t4.text
            session = t4.json()
            assert session["status"] == "completed"
            assert session["layer"] == "reflection"

            # 5. reasoning-log endpoint
            log_resp = await client.get(
                f"/api/solva/v2/sessions/{sid}/reasoning-log", headers=headers
            )
            assert log_resp.status_code == 200
            log_body = log_resp.json()
            assert log_body["entry_count"] > 0
            for e in log_body["entries"]:
                assert "id" in e
                assert "layer" in e
                assert "engine" in e
                assert "engine_version" in e
                assert "input_hash" in e
                assert "created_at" in e
                assert "shield_required" in e
                assert "shield_bypassed_reason" in e
    finally:
        await db.accounts.delete_one({"id": aid})
        await db.solva_v2_sessions.delete_many({"account_id": aid})
