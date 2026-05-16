"""Phase F + Phase E.5 — Engine real signal derivation + Solva seed
handoff + Monitor "Update goal" + Synisense billing.

Sub-task A:  Phase D framing — seed_payload acceptance + provenance.
Sub-task B:  signal_derivation produces `derived_from_*` signals.
Sub-task C:  Monitor update-status endpoint.
Sub-task D:  Synisense billing estimate endpoint.

Each fixture creates an ephemeral account + context so the tests
don't share state with the bramuel seed and don't trip the auth
rate-limiter under the full pytest suite.
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


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
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
    """Ephemeral non-admin account + context, cleaned up on teardown."""
    suffix = uuid.uuid4().hex[:8]
    email = f"phasef-{suffix}@example.com"
    password = "PhaseF2026!"
    account_id = f"acc-pf-{suffix}"
    context_id = f"ctx-pf-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseF Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "PhaseF Context", "created_at": now_iso,
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
    await db_conn.solva_phase_d_sessions.delete_many({"account_id": account_id})
    await db_conn.synisense_audit_log.delete_many({"tenant_id": account_id})
    await db_conn.synisense_signals.delete_many({"tenant_id": account_id})
    await db_conn.documents.delete_many({"account_id": account_id})
    await db_conn.objectives.delete_many({"context_id": context_id})
    await db_conn.projects.delete_many({"context_id": context_id})


@pytest_asyncio.fixture
async def admin(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"phasef-admin-{suffix}@example.com"
    password = "PhaseFAdmin2026!"
    account_id = f"acc-pf-admin-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseF Admin", "role": "admin", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": True,
    })
    yield {"email": email, "password": password, "account_id": account_id}
    await db_conn.accounts.delete_one({"id": account_id})


async def _login(c: AsyncClient, email: str, password: str):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ═════════════════════════════════════════════════════════════════════
# Sub-task A — Solva Phase D seed_payload support
# ═════════════════════════════════════════════════════════════════════
async def test_phase_d_session_accepts_seed_payload(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]

    doc_id = f"doc-test-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": ctx_id, "account_id": authed["account_id"],
        "title": "Q4 audit committee pack",
        "summary": "Strategic review of Q4 risk posture.",
        "created_at": datetime.now(timezone.utc),
    })

    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers,
        json={
            "sub_module": "seek_clarity",
            "seed_payload": {
                "source": "document_journal",
                "source_id": doc_id,
                "preview_text": "I want to develop a clearer view on the Q4 audit pack.",
                "attached_references": [doc_id],
                "sub_module_hint": "develop_strategy",
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sub_module"] == "develop_strategy"
    assert "Q4 audit pack" in (body.get("initial_framing") or "")
    assert body["layer_state"] == "framing"
    assert body["source_handoff"]["source"] == "document_journal"
    assert body["source_handoff"]["source_id"] == doc_id
    assert body["source_handoff"]["source_url"].startswith("/app/workspace?doc=")
    anchors = body["seed_attached_references"]
    assert len(anchors) == 1
    assert anchors[0]["ref_type"] == "document"
    assert anchors[0]["ref_id"] == doc_id
    assert body["schema_version"] == 4
    row = await db_conn.solva_phase_d_sessions.find_one(
        {"session_id": body["session_id"]}, {"_id": 0},
    )
    assert row["source_handoff"]["source_id"] == doc_id


async def test_phase_d_session_without_seed_keeps_legacy_shape(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("source_handoff") is None
    assert body.get("seed_attached_references") == []
    assert body["schema_version"] == 3
    assert body["layer_state"] == "entry"


async def test_phase_d_seed_rejects_unknown_source(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers,
        json={
            "sub_module": "seek_clarity",
            "seed_payload": {
                "source": "stripe", "source_id": "x", "preview_text": "",
                "attached_references": [],
            },
        },
    )
    assert r.status_code == 422


async def test_phase_d_seed_silently_drops_unknown_references(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers,
        json={
            "sub_module": "seek_clarity",
            "seed_payload": {
                "source": "document_journal",
                "source_id": "phantom-doc-id",
                "preview_text": "Probe with a stale reference.",
                "attached_references": ["phantom-doc-id"],
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_handoff"]["source_id"] == "phantom-doc-id"
    assert body["seed_attached_references"] == []


# ═════════════════════════════════════════════════════════════════════
# Sub-task B — Real Engine signal derivation
# ═════════════════════════════════════════════════════════════════════
async def test_signal_derivation_emits_derived_from_signals(authed, db_conn):
    """Seeds activity for the ephemeral tenant, runs derivation, and
    verifies `derived_from_*` signals are written."""
    from services.synisense.engine.signal_derivation import (
        derive_for_tenant, SIGNAL_COLLECTION,
    )

    # Seed minimal activity so behavioral_vector + life_stage emit.
    now = datetime.now(timezone.utc)
    await db_conn.chat_messages.insert_one({
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"], "role": "user",
        "content": "test", "created_at": now,
    })
    await db_conn.documents.insert_one({
        "id": f"doc-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "title": "Audit committee briefing notes",
        "summary": "Quarterly review for the audit committee.",
        "created_at": now,
    })

    counts = await derive_for_tenant(authed["account_id"])
    assert isinstance(counts, dict)
    rows = await db_conn[SIGNAL_COLLECTION].find(
        {"tenant_id": authed["account_id"],
         "derivation_source": {"$regex": "^derived_from_"}},
        {"_id": 0},
    ).to_list(length=1000)
    assert len(rows) > 0
    for r in rows:
        assert r["derivation_source"].startswith("derived_from_")
        assert not r["derivation_source"].startswith("seeded_from_")
        assert r["tenant_id"] == authed["account_id"]
        assert r["signal_id"].startswith("sig-")
        assert r["signal_type"] in {
            "anomaly_flag", "life_stage", "churn_risk",
            "behavioral_vector", "compliance_trigger", "operational_health",
        }
    # The compliance-keyword document should have triggered at least
    # one compliance signal.
    assert any(r["signal_type"] == "compliance_trigger" for r in rows)


async def test_derivation_idempotent(authed, db_conn):
    from services.synisense.engine.signal_derivation import (
        derive_for_tenant, SIGNAL_COLLECTION,
    )
    # Seed minimal activity.
    await db_conn.chat_messages.insert_one({
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"], "role": "user",
        "content": "test", "created_at": datetime.now(timezone.utc),
    })
    await derive_for_tenant(authed["account_id"])
    first = await db_conn[SIGNAL_COLLECTION].count_documents({
        "tenant_id": authed["account_id"],
        "derivation_source": {"$regex": "^derived_from_"},
    })
    await derive_for_tenant(authed["account_id"])
    second = await db_conn[SIGNAL_COLLECTION].count_documents({
        "tenant_id": authed["account_id"],
        "derivation_source": {"$regex": "^derived_from_"},
    })
    assert first == second, "derivation is not idempotent"


async def test_derive_or_seed_falls_back_on_empty_workspace(db_conn):
    from services.synisense.engine.signal_derivation import (
        derive_or_seed_for_tenant, SIGNAL_COLLECTION,
    )
    fake_tenant = f"acc-empty-{uuid.uuid4().hex[:8]}"
    try:
        result = await derive_or_seed_for_tenant(fake_tenant)
        assert result["fallback_used"] is True
        assert result["seeded"], "fallback seeder didn't emit any signals"
    finally:
        await db_conn[SIGNAL_COLLECTION].delete_many({"tenant_id": fake_tenant})


async def test_derive_endpoint_real_signals(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    # Seed some activity so derived signals exist.
    await db_conn.chat_messages.insert_one({
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"], "role": "user",
        "content": "test", "created_at": datetime.now(timezone.utc),
    })
    r = await client.post("/api/v1/engine/admin/derive", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == authed["account_id"]
    assert isinstance(body["derived"], dict)
    assert isinstance(body["fallback_used"], bool)


async def test_engine_query_returns_derived_signals(client, authed, db_conn):
    """After derivation runs, /api/v1/engine/signals/query returns
    signals carrying `derived_from_*` derivation_source."""
    headers = await _login(client, authed["email"], authed["password"])
    await db_conn.chat_messages.insert_one({
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"], "role": "user",
        "content": "test", "created_at": datetime.now(timezone.utc),
    })
    await client.post("/api/v1/engine/admin/derive", headers=headers)
    r = await client.post(
        "/api/v1/engine/signals/query",
        headers=headers,
        json={
            "tenant_id": authed["account_id"],
            "consumer_id": "test.smoke",
            "filter": {},
            "pagination": {"limit": 50},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("signals") or body.get("items") or []
    assert items, "engine query returned no signals at all"
    for it in items:
        assert "derivation_source" in it


# ═════════════════════════════════════════════════════════════════════
# Sub-task C — Monitor "Update goal" status assessment
# ═════════════════════════════════════════════════════════════════════
async def test_monitor_update_status_objective(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]

    obj_id = f"obj-test-{uuid.uuid4().hex[:8]}"
    await db_conn.objectives.insert_one({
        "id": obj_id, "context_id": ctx_id,
        "title": "Lift NPS to 60 by Q4",
        "rag_status": "amber",
        "owner_account_id": authed["account_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    r = await client.post(
        f"/api/contexts/{ctx_id}/monitor/objective/{obj_id}/update-status",
        headers=headers, json={},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "objective"
    assert body["status"] in ("on_track", "at_risk", "off_track")
    assert body["rag_status"] in ("red", "amber", "green")
    assert isinstance(body["assessment"]["rationale"], str)
    assert body["assessment"]["audit_id"].startswith("aud-")
    row = await db_conn.objectives.find_one({"id": obj_id}, {"_id": 0})
    assert row["last_akki_assessment"]["audit_id"] == body["assessment"]["audit_id"]
    assert row["last_akki_assessment"]["status"] == body["status"]


async def test_monitor_update_status_project(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    proj_id = f"prj-test-{uuid.uuid4().hex[:8]}"
    await db_conn.projects.insert_one({
        "id": proj_id, "context_id": ctx_id,
        "title": "Roll out customer-data platform",
        "rag_status": "green",
        "owner_account_id": authed["account_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    r = await client.post(
        f"/api/contexts/{ctx_id}/monitor/project/{proj_id}/update-status",
        headers=headers, json={},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "project"
    assert body["assessment"]["audit_id"].startswith("aud-")


async def test_monitor_update_status_404_on_unknown_item(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/monitor/objective/does-not-exist/update-status",
        headers=headers, json={},
    )
    assert r.status_code == 404


async def test_monitor_update_status_rejects_unknown_kind(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/monitor/widget/x/update-status",
        headers=headers, json={},
    )
    assert r.status_code == 400


async def test_monitor_assessment_parse_falls_back_safely():
    from routers.monitor_status_assessment import _parse_assessment_response
    out = _parse_assessment_response(
        "the project looks off track this quarter",
        signal_ids=["sig-1", "sig-2"], doc_ids=["doc-1"],
    )
    assert out["status"] == "off_track"


async def test_monitor_assessment_parses_valid_json():
    from routers.monitor_status_assessment import _parse_assessment_response
    out = _parse_assessment_response(
        '{"status": "at_risk", "confidence": 0.78, '
        '"rationale": "two anomaly signals last week", '
        '"supporting_signal_ids": ["sig-A", "sig-X"], '
        '"supporting_doc_ids": ["doc-Y"]}',
        signal_ids=["sig-A", "sig-B"], doc_ids=["doc-Y"],
    )
    assert out["status"] == "at_risk"
    assert out["confidence"] == pytest.approx(0.78, abs=0.001)
    assert out["supporting_signal_ids"] == ["sig-A"]
    assert out["supporting_doc_ids"] == ["doc-Y"]


# ═════════════════════════════════════════════════════════════════════
# Sub-task D — Synisense billing estimate
# ═════════════════════════════════════════════════════════════════════
async def test_billing_endpoint_requires_superadmin(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get("/api/admin/synisense/billing", headers=headers)
    assert r.status_code == 403


async def test_billing_endpoint_returns_estimate_for_superadmin(client, admin):
    headers = await _login(client, admin["email"], admin["password"])
    r = await client.get(
        "/api/admin/synisense/billing?window_days=7", headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_days"] == 7
    assert body["is_illustrative"] is True
    assert isinstance(body["estimated_total_usd"], float)
    assert isinstance(body["per_consumer"], list)
    assert isinstance(body["top_purposes_by_cost"], list)
    sig = body["pricing_table_signature"]
    assert sig["entry_count"] >= 5
    assert "anthropic" in sig["providers"]


async def test_pricing_table_flat_cost_lookup():
    from services.synisense.pricing import flat_cost_for, DEFAULT_FLAT_USD_PER_CALL
    cost = flat_cost_for("anthropic", "claude-sonnet-4-5-20250929")
    assert cost == pytest.approx(0.0030, abs=0.0001)
    cost = flat_cost_for("anthropic", "claude-future-model")
    assert cost > 0
    cost = flat_cost_for("xenoprovider", "xeno-1")
    assert cost == DEFAULT_FLAT_USD_PER_CALL


async def test_pricing_table_governance_locked():
    """Pricing table is code-controlled, NOT API-editable. Locks the
    shape so any table change forces a code review."""
    from services.synisense.pricing import PROVIDER_MODEL_PRICING
    for key, val in PROVIDER_MODEL_PRICING.items():
        assert isinstance(key, tuple) and len(key) == 2
        assert isinstance(val, tuple) and len(val) == 3
        for n in val:
            assert isinstance(n, (int, float)) and n >= 0
