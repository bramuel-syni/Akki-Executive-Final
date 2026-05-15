"""Synisense Phase A — end-to-end smoke + integration tests.

These exercise the full HTTP surface against the live FastAPI app via
`httpx.AsyncClient` + `ASGITransport`. The smoke fixture follows the
brief's canonical example:

    "John Smith bought 500 shares of Apple Inc. for $50,000 on
     2026-01-15. Contact: john.smith@example.com"

End-to-end assertions:
- Endpoint returns 200 + an `audit_id`.
- Audit row exists in `synisense_audit_log` with the right tenant_id.
- `de_id_summary` covers PERSON, MONEY, EMAIL, ORG at least.
- Scores > 0 and exposure_reduction_score > 50 (the brief's threshold).
- Trust receipt exists with `version: "v1"`.
- Receipt signature verifies under HKDF-derived tenant key.
- Re-identified response contains NO `[[ENT_` tokens.

Plus contract tests for purpose validation, auth/tenant binding,
admin/reseed gating, and the signal_types catalogue.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app
from services.synisense.shield import trust_receipt


SMOKE_CONTENT = (
    "John Smith bought 500 shares of Apple Inc. for $50,000 on 2026-01-15. "
    "Contact: john.smith@example.com. Wire to IBAN GB29NWBK60161331926819 "
    "via +1-415-555-1234."
)


@pytest_asyncio.fixture
async def client():
    # Force LLM mock mode so smoke tests are hermetic.
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    # Defensive: clear any leftover FastAPI dependency overrides from
    # prior test files that registered them but did not clean up. The
    # Phase A auth path MUST run unmocked so 401/403 contract tests
    # remain honest.
    saved_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    # Restore for downstream tests that may rely on the prior override.
    app.dependency_overrides.update(saved_overrides)


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def authed_user(db_conn):
    """Fresh account + JWT for these tests."""
    suffix = uuid.uuid4().hex[:8]
    email = f"phasea-{suffix}@example.com"
    password = "PhaseA2026!"
    account_id = f"acc-{suffix}"
    from core import hash_password
    pw_hash = hash_password(password)
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": pw_hash,
        "name": "PhaseA Probe", "company_name": "Probe Co",
        "full_name": "Phase Probe", "role": "executive",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "session_version": 0, "verified": True,
    })
    yield {"account_id": account_id, "email": email, "password": password}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.synisense_audit_log.delete_many({"tenant_id": account_id})
    await db_conn.synisense_trust_receipts.delete_many({"tenant_id": account_id})
    await db_conn.synisense_signals.delete_many({"tenant_id": account_id})
    await db_conn.synisense_tenant_entities.delete_many({"tenant_id": account_id})


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# ═════════════════════════════════════════════════════════════════════
# Smoke — the canonical brief fixture.
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_e2e_shield_invoke_smoke(client, db_conn, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "test.smoke",
        "content": SMOKE_CONTENT,
        "model_preference": "balanced",
        "consumer_id": "test",
        "tenant_id": "test-tenant-smoke",
        "user_id": "test-user",
    }, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "audit_id" in body
    assert "response" in body
    assert "trust_receipt" in body
    # No tokens leaked to the consumer.
    assert "[[ENT_" not in body["response"], body["response"][:200]

    # Audit row exists with the right shape.
    audit = await db_conn.synisense_audit_log.find_one(
        {"audit_id": body["audit_id"]}, {"_id": 0},
    )
    assert audit is not None
    assert audit["tenant_id"] == "test-tenant-smoke"
    s = audit["de_id_summary"]
    assert s.get("PERSON", 0) >= 1, s
    assert s.get("MONEY", 0) >= 1, s
    assert s.get("EMAIL", 0) >= 1, s
    assert s.get("ORG", 0) >= 1, s
    assert audit["dilution_score"] > 0
    assert audit["exposure_reduction_score"] > 50

    # Trust receipt mirror.
    receipt = await db_conn.synisense_trust_receipts.find_one(
        {"audit_id": body["audit_id"]}, {"_id": 0, "payload_hash": 0},
    )
    assert receipt is not None
    assert receipt["version"] == "v1"
    # Signature verifies under HKDF-derived per-tenant key.
    assert trust_receipt.verify(receipt, tenant_id="test-tenant-smoke")


@pytest.mark.asyncio
async def test_e2e_shield_invoke_response_contains_no_tokens(client, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "test.smoke", "content": SMOKE_CONTENT,
        "consumer_id": "test", "tenant_id": "test-tenant-tokens",
        "user_id": "test-user",
    }, headers=auth)
    assert r.status_code == 200
    # Even though the mock LLM echoes the de-id'd content (which contains
    # tokens), the re-identifier MUST wipe every token before returning.
    assert "[[ENT_" not in r.json()["response"]


# ═════════════════════════════════════════════════════════════════════
# Auth + purpose contract tests.
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_invoke_unauthenticated_401(client):
    # Explicitly clear cookies to defend against ASGITransport leakage
    # under full-suite ordering (previous tests' logins leave cookies on
    # the shared cookie jar in some pytest-asyncio versions).
    client.cookies.clear()
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "test.smoke", "content": "hello",
        "consumer_id": "test", "tenant_id": "x", "user_id": "u",
    }, headers={"Authorization": ""})
    assert r.status_code == 401, f"got {r.status_code}: {r.text[:200]}"


@pytest.mark.asyncio
async def test_invoke_unknown_purpose_returns_422(client, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "phaseB.not.yet.allowed",
        "content": "hello world",
        "consumer_id": "test",
        "tenant_id": authed_user["account_id"],
        "user_id": authed_user["account_id"],
    }, headers=auth)
    assert r.status_code == 422
    body = r.json()
    assert body["error_class"] == "PURPOSE_INVALID"
    # Error format per the Chunk 3 rule.
    assert ": " in body["message"]


@pytest.mark.asyncio
async def test_invoke_internal_purpose_blocked_via_http(client, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "synisense.shield.internal.something",
        "content": "hi", "consumer_id": "test",
        "tenant_id": authed_user["account_id"],
        "user_id": authed_user["account_id"],
    }, headers=auth)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invoke_non_test_purpose_requires_tenant_eq_account_id(client, authed_user):
    """For a non-test purpose, body.tenant_id MUST match account_id."""
    auth = await _login(client, authed_user["email"], authed_user["password"])
    # Insert a temporary allow-listed purpose for this test (mimics what
    # Phase B will do).
    from services.synisense.config import ALLOWED_PURPOSES
    ALLOWED_PURPOSES.add("phaseA.binding.probe")
    try:
        # Wrong tenant_id → 401.
        r = await client.post("/api/v1/shield/llm/invoke", json={
            "purpose": "phaseA.binding.probe", "content": "hi",
            "consumer_id": "test",
            "tenant_id": "some-other-tenant",
            "user_id": authed_user["account_id"],
        }, headers=auth)
        assert r.status_code == 401
        assert r.json()["error_class"] == "AUTH_DENIED"
        # Right tenant_id (= account_id) → 200.
        r2 = await client.post("/api/v1/shield/llm/invoke", json={
            "purpose": "phaseA.binding.probe", "content": "hi",
            "consumer_id": "test",
            "tenant_id": authed_user["account_id"],
            "user_id": authed_user["account_id"],
        }, headers=auth)
        assert r2.status_code == 200
    finally:
        ALLOWED_PURPOSES.discard("phaseA.binding.probe")


# ═════════════════════════════════════════════════════════════════════
# Engine endpoints.
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_get_signal_types(client, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.get("/api/v1/engine/signal_types", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert "signal_types" in body
    cats = sorted({s["signal_category"] for s in body["signal_types"]})
    assert cats == ["anomaly", "compliance", "life_stage", "operational",
                    "profile", "risk"]


@pytest.mark.asyncio
async def test_subscription_returns_pending(client, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/engine/subscriptions", json={
        "signal_categories": ["anomaly"],
        "signal_types": [],
        "delivery": "poll",
        "tenant_id": authed_user["account_id"],
        "consumer_id": "test",
    }, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["subscription_id"].startswith("sub-")


@pytest.mark.asyncio
async def test_admin_reseed_seeds_signals_and_entities(client, db_conn, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/engine/admin/reseed", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == authed_user["account_id"]
    assert "signals_seeded" in body
    assert "tenant_entities_harvested" in body
    # Signals exist.
    n = await db_conn.synisense_signals.count_documents(
        {"tenant_id": authed_user["account_id"]},
    )
    assert n >= 1
    # Tenant entity dict has the user's company_name / full_name.
    nt = await db_conn.synisense_tenant_entities.count_documents(
        {"tenant_id": authed_user["account_id"]},
    )
    assert nt >= 2  # company_name + full_name from the authed_user fixture


@pytest.mark.asyncio
async def test_signals_query_tenant_scoped(client, db_conn, authed_user):
    """User can only query their own tenant's signals."""
    auth = await _login(client, authed_user["email"], authed_user["password"])
    # Seed signals for this tenant.
    await client.post("/api/v1/engine/admin/reseed", headers=auth)
    # Query own tenant.
    r = await client.post("/api/v1/engine/signals/query", json={
        "filter": {}, "pagination": {"limit": 100},
        "tenant_id": authed_user["account_id"], "consumer_id": "test",
    }, headers=auth)
    assert r.status_code == 200
    body = r.json()
    for s in body["signals"]:
        assert s["tenant_id"] == authed_user["account_id"]
    # Query foreign tenant → 401.
    r2 = await client.post("/api/v1/engine/signals/query", json={
        "filter": {}, "pagination": {"limit": 100},
        "tenant_id": "someone-elses-tenant", "consumer_id": "test",
    }, headers=auth)
    assert r2.status_code == 401
