"""Chunk 12 — 16-May Strategic-Goals deep rewrite (QA-2026-05-16-049).

Backend regression coverage for the Update Goal AI flow. Anchor:
`/app/memory/qa_reports/QA_REPORT_16MAY2026.md` § QA-2026-05-16-049.

Frontend-only display behaviours (drawer Performance-Score label,
no-data verbatim copy, removal of edit affordances) are covered by
ESLint + render-smoke step 14; this file covers the API-layer
guarantees that the drawer reads from.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk12-{suffix}@example.com"
    password = "Chunk12-2026!"
    account_id = f"acc-c12-{suffix}"
    context_id = f"ctx-c12-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk12 Exec", "role": "executive", "declared_role": "executive",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk12 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.strategic_goals.delete_many({"context_id": context_id})
    await db_conn.documents.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


async def _seed_goal(db, context_id, account_id, **overrides):
    gid = f"goal-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    base = {
        "id": gid,
        "context_id": context_id,
        "account_id": account_id,
        "department": "cfo",
        "title": "Lift CET1 ratio to 12.5%",
        "description": "Push regulatory capital headroom by Q3.",
        "category": "revenue",
        "current_score": 55,
        "target_score": 100,
        "probability": 50,
        "status": "at_risk",
        "score_history": [],
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    base.update(overrides)
    await db.strategic_goals.insert_one(base)
    return gid


# =====================================================================
# QA-049 success path — Update Goal applies values from LLM response
# =====================================================================
async def test_qa049_update_goal_applies_llm_values_on_success(client, db_conn, authed):
    """When Shield returns relevant=true with supporting docs/signals,
    the endpoint persists the new performance score + probability +
    status AND records a `last_akki_update` audit trail."""
    headers = await _login(client, authed["email"], authed["password"])
    # Seed a goal + a doc so the no-evidence short-circuit doesn't fire.
    gid = await _seed_goal(db_conn, authed["context_id"], authed["account_id"],
                            current_score=55, probability=50, status="at_risk")
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": authed["context_id"],
        "account_id": authed["account_id"], "name": "Q2_capital.pdf",
        "summary": "CET1 ratio improved 80bps", "extracted_text": "fake",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Mock Shield to return a structured success payload.
    fake_response = (
        '{"relevant": true, "current_score": 78, "probability": 70, '
        '"status": "on_track", "supporting_signal_ids": [], '
        f'"supporting_doc_ids": ["{doc_id}"], '
        '"rationale": "CET1 trended +80bps off Q2 capital pack."}'
    )
    with patch(
        "routers.strategic_goal_assessment.shield_invoke",
        new=AsyncMock(return_value={"response": fake_response, "audit_id": "aud-success"}),
    ):
        r = await client.post(
            f"/api/contexts/{authed['context_id']}/strategic-goals/{gid}/update",
            headers=headers, json={},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated"] is True
    assert body["no_data"] is False
    assert body["current_score"] == 78
    assert body["probability"] == 70
    assert body["status"] == "on_track"
    assert body["last_akki_update"]["audit_id"] == "aud-success"
    assert doc_id in body["last_akki_update"]["supporting_doc_ids"]

    # Confirm DB row was updated.
    row = await db_conn.strategic_goals.find_one({"id": gid}, {"_id": 0})
    assert row["current_score"] == 78
    assert row["probability"] == 70
    assert row["status"] == "on_track"
    # score_history should have a new entry.
    assert len(row["score_history"]) == 1
    assert row["score_history"][0]["score"] == 78
    assert row["score_history"][0]["source"] == "akki_update"


# =====================================================================
# QA-049 no-data short-circuit (no evidence in context)
# =====================================================================
async def test_qa049_update_goal_no_evidence_short_circuit(client, db_conn, authed):
    """When the context has zero documents AND zero engine signals,
    the endpoint short-circuits BEFORE invoking Shield. Returns the
    verbatim no-data spec message and does NOT mutate score/status."""
    headers = await _login(client, authed["email"], authed["password"])
    gid = await _seed_goal(db_conn, authed["context_id"], authed["account_id"],
                            current_score=55, probability=50, status="at_risk")

    # Spy on Shield — assert NOT called.
    spy = AsyncMock()
    with patch(
        "routers.strategic_goal_assessment.shield_invoke",
        new=spy,
    ):
        r = await client.post(
            f"/api/contexts/{authed['context_id']}/strategic-goals/{gid}/update",
            headers=headers, json={},
        )
    spy.assert_not_called()  # Short-circuit happened before Shield.

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated"] is False
    assert body["no_data"] is True
    # Verbatim spec copy — match exactly.
    assert body["message"] == (
        "No additional information found for this goal. Please upload "
        "a document with updated performance data so Akki can reassess."
    )
    # Values unchanged.
    row = await db_conn.strategic_goals.find_one({"id": gid}, {"_id": 0})
    assert row["current_score"] == 55
    assert row["probability"] == 50
    assert row["status"] == "at_risk"
    # last_akki_update timestamp WAS recorded — drawer surfaces it.
    assert row.get("last_akki_update", {}).get("no_data") is True


# =====================================================================
# QA-049 no-data short-circuit (LLM said "relevant=false")
# =====================================================================
async def test_qa049_update_goal_llm_says_irrelevant(client, db_conn, authed):
    """Even with evidence in scope, if the LLM determines none of it
    is relevant to THIS goal, the endpoint treats it as no-data."""
    headers = await _login(client, authed["email"], authed["password"])
    gid = await _seed_goal(db_conn, authed["context_id"], authed["account_id"],
                            current_score=42, probability=30, status="off_track")
    await db_conn.documents.insert_one({
        "id": f"doc-{uuid.uuid4().hex[:8]}",
        "context_id": authed["context_id"], "account_id": authed["account_id"],
        "name": "unrelated.pdf", "summary": "Marketing campaign report",
        "extracted_text": "x", "created_at": datetime.now(timezone.utc).isoformat(),
    })

    fake = '{"relevant": false, "rationale": "Doc is about marketing, not finance."}'
    with patch(
        "routers.strategic_goal_assessment.shield_invoke",
        new=AsyncMock(return_value={"response": fake, "audit_id": "aud-irrelevant"}),
    ):
        r = await client.post(
            f"/api/contexts/{authed['context_id']}/strategic-goals/{gid}/update",
            headers=headers, json={},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["no_data"] is True
    assert body["message"].startswith("No additional information found")
    # Values still unchanged.
    row = await db_conn.strategic_goals.find_one({"id": gid}, {"_id": 0})
    assert row["current_score"] == 42
    assert row["status"] == "off_track"
    assert row["last_akki_update"]["audit_id"] == "aud-irrelevant"


# =====================================================================
# QA-049 cross-context scope guard
# =====================================================================
async def test_qa049_update_goal_404_on_other_context(client, db_conn, authed):
    """A goal in a different context (or non-existent) returns 404."""
    headers = await _login(client, authed["email"], authed["password"])
    # Don't seed any goal — the call below targets a fictional id.
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/strategic-goals/goal-doesnotexist/update",
        headers=headers, json={},
    )
    assert r.status_code == 404


# =====================================================================
# QA-049 RBAC carry-over — NED users can't trigger Update Goal
# =====================================================================
async def test_qa049_ned_rejected_on_update_goal(client, db_conn):
    """NED accounts get 403 on the Update Goal endpoint (mirrors the
    Chunk-11 QA-048 RBAC pattern)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk12n-{suffix}@example.com"
    password = "Chunk12-2026!"
    account_id = f"acc-c12n-{suffix}"
    context_id = f"ctx-c12n-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk12 NED", "role": "ned", "declared_role": "ned",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk12 NED Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    try:
        gid = await _seed_goal(db_conn, context_id, account_id)
        headers = await _login(client, email, password)
        r = await client.post(
            f"/api/contexts/{context_id}/strategic-goals/{gid}/update",
            headers=headers, json={},
        )
        assert r.status_code == 403, r.text
        assert "Executive-only" in (r.json().get("detail") or "")
    finally:
        await db_conn.accounts.delete_one({"id": account_id})
        await db_conn.contexts.delete_one({"id": context_id})
        await db_conn.memberships.delete_many({"account_id": account_id})
        await db_conn.strategic_goals.delete_many({"context_id": context_id})


# =====================================================================
# QA-049 — partial LLM response (only score, no probability)
# =====================================================================
async def test_qa049_update_goal_partial_llm_response_only_changes_provided_fields(client, db_conn, authed):
    """When the LLM omits probability/status, those fields stay
    unchanged. Only current_score updates."""
    headers = await _login(client, authed["email"], authed["password"])
    gid = await _seed_goal(db_conn, authed["context_id"], authed["account_id"],
                            current_score=40, probability=60, status="at_risk")
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": authed["context_id"],
        "account_id": authed["account_id"], "name": "perf.pdf",
        "summary": "Score lifted by 30pts", "extracted_text": "x",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    fake = (
        '{"relevant": true, "current_score": 70, '
        '"probability": null, "status": null, '
        '"supporting_signal_ids": [], '
        f'"supporting_doc_ids": ["{doc_id}"], '
        '"rationale": "Performance lifted but probability unclear."}'
    )
    with patch(
        "routers.strategic_goal_assessment.shield_invoke",
        new=AsyncMock(return_value={"response": fake, "audit_id": "aud-partial"}),
    ):
        r = await client.post(
            f"/api/contexts/{authed['context_id']}/strategic-goals/{gid}/update",
            headers=headers, json={},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["current_score"] == 70
    # Probability + status unchanged.
    row = await db_conn.strategic_goals.find_one({"id": gid}, {"_id": 0})
    assert row["current_score"] == 70
    assert row["probability"] == 60  # unchanged
    assert row["status"] == "at_risk"  # unchanged


# =====================================================================
# QA-049 — architectural invariant: Shield purpose + no direct LLM
# =====================================================================
async def test_chunk12_update_goal_routes_through_shield_only():
    """Static check on the assessment router source: confirms the
    Update Goal endpoint calls `shield_invoke` and does NOT import
    any LLM SDK directly. Belt-and-braces alongside the
    `test_no_direct_llm_calls_outside_shield` CI guard."""
    src = open("/app/backend/routers/strategic_goal_assessment.py").read()
    assert "shield_invoke" in src
    assert "monitor.strategic_goal.update_assessment" in src
    for forbidden in (
        "import openai", "from openai", "import anthropic", "from anthropic",
        "import litellm", "google.generativeai",
    ):
        assert forbidden not in src, forbidden
