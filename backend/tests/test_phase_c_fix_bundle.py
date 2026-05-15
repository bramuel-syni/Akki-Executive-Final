"""Phase C — fix bundle regression tests (2026-05-13).

Covers:
- `_friendly_model_name` strips API-version date suffixes from
  Anthropic / OpenAI / Gemini model ids.
- `_friendly_purpose` translates canonical purpose strings to executive
  labels (Chat + Solva pre-fold for Phase D).
- Audit panel response NO LONGER carries `raw_de_id_summary`.
- Audit panel `provider_prose` does NOT leak the model date suffix.
- Detector B fires via mocked Shield invoke — locks behavioural wiring
  even though grounding correctly refuses ungrounded natural prompts.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


# ─────────────────────────────────────────────────────────────────────
# Friendly model-name unit tests.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, expected", [
    ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5"),
    ("claude-haiku-4-5-20251001",  "claude-haiku-4-5"),
    ("gpt-4o-2024-08-06",          "gpt-4o"),
    ("gpt-4o-mini-2024-07-18",     "gpt-4o-mini"),
    ("gemini-2.5-flash-001",       "gemini-2.5-flash"),
    ("gemini-2.5-flash",           "gemini-2.5-flash"),
    ("claude-sonnet-4-5",          "claude-sonnet-4-5"),
    ("gpt-4o",                     "gpt-4o"),
    ("gemini-2.5-flash:mock",      "gemini-2.5-flash"),
    ("claude-sonnet-4-5-20250929:mock", "claude-sonnet-4-5"),
    ("",                           ""),
])
def test_friendly_model_name(raw, expected):
    from routers.chat_audit_panel import _friendly_model_name
    assert _friendly_model_name(raw) == expected


def test_friendly_purpose_chat_and_solva_labels():
    """Phase D pre-fold per PO 2026-05-13 — Solva purposes already have
    executive labels in the lookup so when Phase D wires them, the
    audit panel reads cleanly with zero further work."""
    from routers.chat_audit_panel import _friendly_purpose
    assert _friendly_purpose("chat.standard_response") == "Chat reply"
    assert _friendly_purpose("chat.fm_b.claim_extraction") == \
        "Claim-grounding check (Detector B)"
    # Solva (Phase D pre-fold).
    assert _friendly_purpose("solva.layer_0.frame_audit") == "Frame Audit"
    assert _friendly_purpose("solva.layer_2.tension_detection") == "Tension Detection"
    assert _friendly_purpose("solva.layer_3.synthesis_rendering") == "Synthesis"
    # Document journal.
    assert _friendly_purpose("document_journal.commentary.generate") == \
        "Document commentary"
    # Unknown purpose falls back to the raw string.
    assert _friendly_purpose("totally.new.purpose") == "totally.new.purpose"


# ─────────────────────────────────────────────────────────────────────
# Audit-panel API shape — no raw_de_id_summary leak.
# ─────────────────────────────────────────────────────────────────────
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
    email = f"pcfix-{suffix}@example.com"
    password = "PCFix2026!"
    account_id = f"acc-pcfix-{suffix}"
    context_id = f"ctx-pcfix-{suffix}"
    chat_id = f"cht-pcfix-{uuid.uuid4().hex[:10]}"
    from core import hash_password
    now = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email,
        "password_hash": hash_password(password),
        "name": "PCFix", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "PCFix Context", "created_at": now,
    })
    await db_conn.chats.insert_one({
        "id": chat_id, "account_id": account_id, "context_id": context_id,
        "title": "PCFix test chat", "model_id": "gemini-2.5-flash",
        "shielding_policy": "always", "status": "active",
        "synisense_audit_ids": [], "protective_layer_events": [],
        "message_count": 0,
        "created_at": now, "updated_at": now,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id,
           "chat_id": chat_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.chats.delete_many({"account_id": account_id})
    await db_conn.chat_messages.delete_many({"account_id": account_id})
    await db_conn.synisense_audit_log.delete_many({"tenant_id": account_id})


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_audit_panel_response_omits_raw_de_id_summary(client, authed):
    auth = await _login(client, authed["email"], authed["password"])
    headers = {**auth, "X-Active-Context": authed["context_id"]}
    r = await client.post(
        f"/api/chats/{authed['chat_id']}/messages",
        headers=headers,
        json={"content": "Hello.", "acknowledge_unshielded": False},
    )
    assert r.status_code == 200
    assistant_id = r.json()["assistant_message"]["id"]
    panel = await client.get(
        f"/api/chats/{authed['chat_id']}/audit-panel",
        params={"message_id": assistant_id},
        headers=auth,
    )
    assert panel.status_code == 200
    body = panel.json()
    # Hygiene fix — `raw_de_id_summary` was leaking raw enum keys.
    assert "raw_de_id_summary" not in body, (
        "Audit panel API leaks raw_de_id_summary; remove from user-visible response."
    )
    # `provider_prose` MUST NOT contain a date suffix.
    import re
    assert not re.search(r"-\d{8}\b", body["provider_prose"]), \
        f"date suffix leaked into provider_prose: {body['provider_prose']!r}"
    assert not re.search(r"-\d{4}-\d{2}-\d{2}\b", body["provider_prose"]), \
        f"dashed-ISO date leaked into provider_prose: {body['provider_prose']!r}"
    # References block now carries a friendly purpose label.
    refs = body["references"]
    assert refs.get("purpose_label"), "expected references.purpose_label to be set"
    assert refs["purpose_label"] != refs["purpose"], (
        "purpose_label should differ from raw purpose for canonical chat purposes"
    )


# ─────────────────────────────────────────────────────────────────────
# Fix 5 — Detector B fires via mocked Shield invoke.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_detector_b_fires_with_mocked_shield(client, db_conn, authed):
    """Locks Detector B's wiring behaviourally. Grounding correctly
    refuses ungrounded natural prompts, so we mock `chat.fm_b.
    claim_extraction` to return a high-confidence ungrounded-claim
    detection and verify the protective_event lands in the chat with
    the right shape."""
    # Patch the protective-layer's Shield invoke. We only need to
    # intercept calls whose `purpose` is the Detector B purpose; for
    # A and C we let them fail naturally (returning None → score 0).
    real_invoke = None
    from services.synisense.shield import client as _shield_client

    async def _mock_invoke(**kwargs):  # noqa: ANN003
        purpose = kwargs.get("purpose") or ""
        if purpose == "chat.fm_b.claim_extraction":
            return {
                "response": (
                    '{"score": 0.85, "rationale": "two general-practice '
                    'figures lack session grounding", '
                    '"claims": ["historical NPV is 12%", "industry benchmark is 8%"]}'
                ),
                "trust_receipt": {"llm_model": "gemini-2.5-flash",
                                  "llm_provider": "gemini"},
                "audit_id": "aud-mock-detector-b",
            }
        # Fall back to the real invoke for everything else (Shield
        # standard_response call, A, C).
        return await real_invoke(**kwargs)

    real_invoke = _shield_client.invoke
    with patch(
        "services.chat.protective_layer._invoke_detector",
        new=AsyncMock(side_effect=[
            None,  # Detector A → no fire
            # Detector B — mocked structured output.
            {
                "score": 0.85,
                "rationale": "two general-practice figures lack session grounding",
                "claims": ["historical NPV is 12%", "industry benchmark is 8%"],
            },
            None,  # Detector C → no fire
        ]),
    ):
        auth = await _login(client, authed["email"], authed["password"])
        headers = {**auth, "X-Active-Context": authed["context_id"]}
        r = await client.post(
            f"/api/chats/{authed['chat_id']}/messages",
            headers=headers,
            json={
                "content": "What's the typical NPV for an infrastructure investment?",
                "acknowledge_unshielded": False,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # The protective_event MUST surface on the response with B fired.
        ev = body.get("protective_event")
        assert ev is not None, "protective_event missing from response"
        assert ev["detectors_fired"] == ["B"], ev
        assert ev["intervention_type"] == "annotation", ev
        assert ev["template_id"] == "B.annotation", ev
        anchors = ev.get("annotation_anchors") or []
        assert "historical NPV is 12%" in anchors, anchors

        # And the audit panel for that message renders the
        # Detector-B prose.
        assistant_id = body["assistant_message"]["id"]
        panel = await client.get(
            f"/api/chats/{authed['chat_id']}/audit-panel",
            params={"message_id": assistant_id},
            headers=auth,
        )
        assert panel.status_code == 200
        prose = panel.json()["protective_layer_prose"]
        assert "Detector B fired" in prose, prose
        assert "general-practice references" in prose, prose
