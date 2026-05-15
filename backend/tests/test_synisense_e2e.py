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
# Phase A P0 fix (2026-05-13): tenant_id MUST equal the authenticated
# account_id for every purpose, including test.*. Smoke now uses the
# authed_user's account_id rather than a sentinel "test-tenant-smoke".
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_e2e_shield_invoke_smoke(client, db_conn, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "test.smoke",
        "content": SMOKE_CONTENT,
        "model_preference": "balanced",
        "consumer_id": "test",
        "tenant_id": authed_user["account_id"],
        "user_id": authed_user["account_id"],
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
    assert audit["tenant_id"] == authed_user["account_id"]
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
    assert trust_receipt.verify(receipt, tenant_id=authed_user["account_id"])


@pytest.mark.asyncio
async def test_e2e_shield_invoke_response_contains_no_tokens(client, authed_user):
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "test.smoke", "content": SMOKE_CONTENT,
        "consumer_id": "test", "tenant_id": authed_user["account_id"],
        "user_id": authed_user["account_id"],
    }, headers=auth)
    assert r.status_code == 200
    # Even though the mock LLM echoes the de-id'd content (which contains
    # tokens), the re-identifier MUST wipe every token before returning.
    assert "[[ENT_" not in r.json()["response"]


# ═════════════════════════════════════════════════════════════════════
# P0 REGRESSION (e1_tester Test 2): cross-tenant isolation must hold
# for EVERY purpose, including test.*. User A authenticated with their
# own JWT must NOT be able to forge a receipt for user B by passing
# `tenant_id = B's account_id`.
# ═════════════════════════════════════════════════════════════════════
@pytest_asyncio.fixture
async def second_authed_user(db_conn):
    """A second isolated account so we can prove cross-tenant rejection."""
    suffix = uuid.uuid4().hex[:8]
    email = f"phasea-b-{suffix}@example.com"
    password = "PhaseA-B2026!"
    account_id = f"acc-b-{suffix}"
    from core import hash_password
    pw_hash = hash_password(password)
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": pw_hash,
        "name": "PhaseA B Probe", "role": "executive",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "session_version": 0, "verified": True,
    })
    yield {"account_id": account_id, "email": email, "password": password}
    await db_conn.accounts.delete_one({"id": account_id})


@pytest.mark.asyncio
async def test_shield_rejects_foreign_tenant_id(client, db_conn, authed_user, second_authed_user):
    """User A's JWT cannot forge a receipt under user B's tenant_id."""
    auth_a = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/shield/llm/invoke", json={
        "purpose": "test.smoke",
        "content": "Just hello.",
        "model_preference": "balanced",
        "consumer_id": "test",
        # The forgery — user A passing user B's account_id.
        "tenant_id": second_authed_user["account_id"],
        "user_id": authed_user["account_id"],
    }, headers=auth_a)
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body["error_class"] == "AUTH_DENIED"
    # Error message format per the Chunk 3 authenticity rule.
    assert authed_user["account_id"] in body["message"]
    assert second_authed_user["account_id"] in body["message"]
    # No audit row or receipt should have been written under either tenant.
    n_a = await db_conn.synisense_audit_log.count_documents(
        {"tenant_id": authed_user["account_id"]},
    )
    n_b = await db_conn.synisense_audit_log.count_documents(
        {"tenant_id": second_authed_user["account_id"]},
    )
    assert n_a == 0 and n_b == 0, "no audit row may be written for a rejected forgery"


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
    """For ANY purpose (test or otherwise), body.tenant_id MUST match
    account_id. The test/non-test distinction was retired in the
    2026-05-13 P0 fix — see `test_shield_rejects_foreign_tenant_id`."""
    auth = await _login(client, authed_user["email"], authed_user["password"])
    # Insert a temporary allow-listed purpose for this test (mimics what
    # Phase B will do for production consumer purposes).
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
    """Subscriptions now filter by suffixed type names only (P0 fix:
    `signal_categories` field removed; `signal_types` accepts the 6
    canonical catalogue type names)."""
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/engine/subscriptions", json={
        "signal_types": ["anomaly_flag", "churn_risk"],
        "delivery": "poll",
        "tenant_id": authed_user["account_id"],
        "consumer_id": "test",
    }, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["subscription_id"].startswith("sub-")


@pytest.mark.asyncio
async def test_subscription_rejects_unsuffixed_category(client, authed_user):
    """Sending `"anomaly"` (an umbrella category) MUST be rejected —
    the canonical naming is the suffixed type name (`anomaly_flag`)."""
    auth = await _login(client, authed_user["email"], authed_user["password"])
    r = await client.post("/api/v1/engine/subscriptions", json={
        "signal_types": ["anomaly"],
        "delivery": "poll",
        "tenant_id": authed_user["account_id"],
        "consumer_id": "test",
    }, headers=auth)
    # Pydantic Literal validation → 422.
    assert r.status_code == 422


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


@pytest.mark.asyncio
async def test_signals_query_http_pagination_with_cursor(client, db_conn, authed_user):
    """HTTP-level pagination round-trip on a tenant with ≥10 signals
    (addresses tester item (c): 2-signal tenant can't exercise the cursor)."""
    auth = await _login(client, authed_user["email"], authed_user["password"])
    # Seed 12 synthetic signals so the cursor can do a real round-trip.
    tid = authed_user["account_id"]
    base = datetime.now(timezone.utc)
    rows = []
    for i in range(12):
        rows.append({
            "signal_id": f"sig-pagi-{i:03d}",
            "tenant_id": tid,
            "signal_category": "profile",
            "signal_type": "behavioral_vector",
            "entity_ref": tid,
            "payload": {"vector": [0.0] * 8, "window_days": 7},
            "confidence": 0.5,
            "derivation_source": "seeded_from_action_log",
            "created_at": base.replace(microsecond=i * 1000).isoformat(),
        })
    await db_conn.synisense_signals.insert_many(rows)

    # Page 1.
    r1 = await client.post("/api/v1/engine/signals/query", json={
        "filter": {"signal_type": "behavioral_vector"},
        "pagination": {"limit": 5},
        "tenant_id": tid, "consumer_id": "test",
    }, headers=auth)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert len(b1["signals"]) == 5
    assert b1["next_cursor"] is not None

    # Page 2 — pass the cursor.
    r2 = await client.post("/api/v1/engine/signals/query", json={
        "filter": {"signal_type": "behavioral_vector"},
        "pagination": {"limit": 5, "cursor": b1["next_cursor"]},
        "tenant_id": tid, "consumer_id": "test",
    }, headers=auth)
    assert r2.status_code == 200
    b2 = r2.json()
    assert len(b2["signals"]) == 5
    # Page 3 — should drain the rest (2 remaining of the 12).
    r3 = await client.post("/api/v1/engine/signals/query", json={
        "filter": {"signal_type": "behavioral_vector"},
        "pagination": {"limit": 5, "cursor": b2["next_cursor"]},
        "tenant_id": tid, "consumer_id": "test",
    }, headers=auth)
    assert r3.status_code == 200
    b3 = r3.json()
    assert len(b3["signals"]) == 2
    assert b3["next_cursor"] is None

    # No overlap across pages.
    ids = [s["signal_id"] for page in (b1, b2, b3) for s in page["signals"]]
    assert len(ids) == len(set(ids)), "pagination produced duplicate signals"
