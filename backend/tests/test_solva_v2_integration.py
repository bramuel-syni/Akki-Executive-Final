"""Integration test - full Seek Clarity session end-to-end with mocked LLM.

Structure: a single test function with a single asyncio.run invocation so
Motor's client binds to one event loop for the whole test. Mocks placed on
`llm_tier_quota.call_llm_with_tier` and `llm_service.validate_independent`
so no real LLM is hit. Exercises: start session -> framing primed ->
advance layers -> synthesis parses cleanly -> reflection -> completed.
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


def test_full_seek_clarity_session_end_to_end(monkeypatch):
    """Single asyncio.run - one Motor loop - full v2 flow in one pass."""
    call_counter = {"n": 0}

    async def fake_call_llm_with_tier(**kwargs):
        call_counter["n"] += 1
        body = FRAMING_REPLY if call_counter["n"] == 1 else VALID_SYNTH_BODY
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

    async def _runner():
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
        finally:
            await db.accounts.delete_one({"id": aid})
            await db.solva_v2_sessions.delete_many({"account_id": aid})

    asyncio.run(_runner())
