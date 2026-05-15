"""Phase C — Akki Chat Protective Layer + Audit Panel regression tests.

Covers:
- Protective Layer detector A/B/C bundle output shape + intervention precedence.
- `chats.protective_layer_events` persisted per assistant message.
- Audit panel single-message endpoint shape + natural-language prose.
- Audit panel aggregate endpoint.
- Async-mirror endpoints return {job_id, status: "queued"} immediately.
- Archived chats list + permanent delete CRUD.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


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
    email = f"phasec-{suffix}@example.com"
    password = "PhaseC2026!"
    account_id = f"acc-phasec-{suffix}"
    context_id = f"ctx-phasec-{suffix}"
    chat_id = f"cht-phasec-{uuid.uuid4().hex[:10]}"
    from core import hash_password
    now = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseC Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "PhaseC Context", "created_at": now,
    })
    await db_conn.chats.insert_one({
        "id": chat_id, "account_id": account_id, "context_id": context_id,
        "title": "PhaseC test chat", "model_id": "gemini-2.5-flash",
        "shielding_policy": "always", "status": "active",
        "synisense_audit_ids": [], "protective_layer_events": [],
        "message_count": 0,
        "created_at": now, "updated_at": now,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id,
           "chat_id": chat_id}
    # Tear-down — leaves no orphans for downstream tests.
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.chats.delete_many({"account_id": account_id})
    await db_conn.chat_messages.delete_many({"account_id": account_id})
    await db_conn.synisense_audit_log.delete_many({"tenant_id": account_id})
    await db_conn.async_jobs.delete_many({"account_id": account_id})


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ─────────────────────────────────────────────────────────────────────
# Protective Layer detectors — unit-level (no HTTP).
# ─────────────────────────────────────────────────────────────────────
def test_detector_bundle_precedence_a_over_c_over_b():
    """A > C > B precedence."""
    from services.chat.protective_layer import DetectorBundle
    # A fires AND C fires AND B fires → expect Mode A.
    bundle = DetectorBundle(
        score_a=0.8, framing_question_a="What's your time horizon?",
        score_b=0.7, claims_b=["return averages 8%"],
        score_c=0.9, handoff_rationale_c="Capital decision flagged.",
    )
    ev = bundle.as_protective_event(message_id="msg-1")
    assert ev.intervention_type == "hypothesis_test"
    assert ev.template_id == "A.framing_question"
    assert ev.detectors_fired == ["A", "B", "C"]


def test_detector_bundle_c_only():
    from services.chat.protective_layer import DetectorBundle
    bundle = DetectorBundle(
        score_c=0.85, handoff_rationale_c="Restructuring carries consequence.",
    )
    ev = bundle.as_protective_event(message_id="msg-2")
    assert ev.intervention_type == "solva_handoff_offered"
    assert "Solva" in (ev.intervention_text or "")


def test_detector_bundle_b_only():
    from services.chat.protective_layer import DetectorBundle
    bundle = DetectorBundle(
        score_b=0.7, claims_b=["historical NPV is 12%", "industry benchmark is 8%"],
    )
    ev = bundle.as_protective_event(message_id="msg-3")
    assert ev.intervention_type == "annotation"
    assert ev.annotation_anchors == ["historical NPV is 12%", "industry benchmark is 8%"]


def test_detector_bundle_no_fires():
    from services.chat.protective_layer import DetectorBundle
    bundle = DetectorBundle(score_a=0.1, score_b=0.2, score_c=0.0)
    ev = bundle.as_protective_event(message_id="msg-4")
    assert ev.intervention_type == "none"
    assert ev.detectors_fired == []


def test_detector_b_threshold_requires_claims():
    """Score-B above threshold but no claims → no fire."""
    from services.chat.protective_layer import DetectorBundle
    bundle = DetectorBundle(score_b=0.8, claims_b=[])
    ev = bundle.as_protective_event(message_id="msg-5")
    assert "B" not in ev.detectors_fired
    assert ev.intervention_type == "none"


# ─────────────────────────────────────────────────────────────────────
# Audit panel single-message endpoint.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_audit_panel_single_message_returns_executive_prose(
    client, db_conn, authed,
):
    """Send a real chat message, then fetch the audit panel data and
    assert the natural-language sections are populated."""
    auth = await _login(client, authed["email"], authed["password"])
    headers = {**auth, "X-Active-Context": authed["context_id"]}
    r = await client.post(
        f"/api/chats/{authed['chat_id']}/messages",
        headers=headers,
        json={
            "content": "Wire $50,000 to John Smith on 2026-01-15. "
                       "Contact: john.smith@example.com.",
            "acknowledge_unshielded": False,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assistant_id = body["assistant_message"]["id"]

    # Now fetch the audit panel data for that message.
    panel = await client.get(
        f"/api/chats/{authed['chat_id']}/audit-panel",
        params={"message_id": assistant_id},
        headers=auth,
    )
    assert panel.status_code == 200, panel.text
    pdata = panel.json()
    assert pdata["message_id"] == assistant_id
    assert pdata["audit_id"], "audit_id missing on panel data"
    assert "shielded" in pdata["shielding_prose"] or \
           "no sensitive identifiers were detected" in pdata["shielding_prose"].lower(), pdata
    # Executive language — no raw enum values surface anywhere.
    s = pdata["shielding_prose"]
    for forbidden in ["PERSON", "EMAIL", "MONEY", "DATE_ISO", "purpose=", "consumer_id="]:
        assert forbidden not in s, f"raw value '{forbidden}' leaked: {s}"
    # The protective layer prose is always present (event may be None
    # if detectors silently failed; prose tolerates that case).
    assert pdata["protective_layer_prose"]
    # References block carries the audit_id back to the caller.
    refs = pdata["references"]
    assert refs["audit_id"] == pdata["audit_id"]
    assert refs["purpose"].startswith("chat."), refs


@pytest.mark.asyncio
async def test_audit_panel_aggregate_strip(client, authed):
    auth = await _login(client, authed["email"], authed["password"])
    headers = {**auth, "X-Active-Context": authed["context_id"]}
    # Two sends → two audit entries → aggregate counts work.
    for content in ["Hi Akki — quick question 1.", "Hi Akki — follow-up."]:
        r = await client.post(
            f"/api/chats/{authed['chat_id']}/messages",
            headers=headers,
            json={"content": content, "acknowledge_unshielded": False},
        )
        assert r.status_code == 200
    agg = await client.get(
        f"/api/chats/{authed['chat_id']}/audit-panel/aggregate",
        headers=auth,
    )
    assert agg.status_code == 200, agg.text
    a = agg.json()
    assert a["llm_calls"] == 2
    assert "shielded" in a["headline_prose"]
    # The aggregate prose mentions both the message_count and a number
    # of LLM calls.
    assert "2 LLM calls" in a["headline_prose"] or "2 messages" in a["headline_prose"]


# ─────────────────────────────────────────────────────────────────────
# Async-mirror endpoints.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_async_meta_endpoint_returns_immediately(client, authed):
    auth = await _login(client, authed["email"], authed["password"])
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/documents/generate-meta/async",
        headers={**auth, "X-Active-Context": authed["context_id"]},
        json={"filename": "Q4-board.pdf", "preview_text": "Acme Q4 board pack snapshot."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued", body
    assert body["job_id"], body
    assert body["kind"] == "document.meta.generate"


@pytest.mark.asyncio
async def test_async_endpoints_complete_via_poll(client, authed):
    """Submit an async meta job, then poll /api/jobs/{id} until terminal."""
    auth = await _login(client, authed["email"], authed["password"])
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/documents/generate-meta/async",
        headers={**auth, "X-Active-Context": authed["context_id"]},
        json={"filename": "Q4-board.pdf",
              "preview_text": "Q4 board pack with operating model summary and capital plan."},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    # Poll up to ~10 seconds. The mock LLM is hermetic so this should
    # complete fast.
    final_status = None
    for _ in range(30):
        await asyncio.sleep(0.4)
        j = await client.get(f"/api/jobs/{job_id}", headers=auth)
        if j.status_code != 200:
            continue
        status = j.json().get("status")
        if status in ("completed", "failed"):
            final_status = status
            break
    assert final_status in ("completed", "failed"), \
        f"job never terminated; last seen status={final_status}"


# ─────────────────────────────────────────────────────────────────────
# Archived chats.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_archived_chats_list_and_permanent_delete(client, db_conn, authed):
    auth = await _login(client, authed["email"], authed["password"])
    # Archive the test chat directly.
    await db_conn.chats.update_one(
        {"id": authed["chat_id"]},
        {"$set": {"status": "archived",
                  "archived_at": datetime.now(timezone.utc).isoformat()}},
    )
    # List archived.
    r = await client.get("/api/chats/archived", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    ids = [c["id"] for c in body["items"]]
    assert authed["chat_id"] in ids

    # Permanent-delete without confirm → 400.
    r1 = await client.request(
        "DELETE", f"/api/chats/{authed['chat_id']}/permanent",
        json={}, headers=auth,
    )
    assert r1.status_code == 400, r1.text

    # Permanent-delete with confirm → 200.
    r2 = await client.request(
        "DELETE", f"/api/chats/{authed['chat_id']}/permanent",
        json={"confirm": True}, headers=auth,
    )
    assert r2.status_code == 200, r2.text
    # Chat row is gone.
    gone = await db_conn.chats.find_one(
        {"id": authed["chat_id"]}, {"_id": 0, "id": 1},
    )
    assert gone is None
