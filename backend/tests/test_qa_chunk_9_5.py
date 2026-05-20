"""Chunk 9.5 — Phase C audit regression (Sx1/Sx2) + Solva criticals (SV-01/02/03).

Backend regression coverage for the bundled chunk. Anchors:
  - Phase-C-symptom-1 — /app/memory/screenshots/audit_panel_inline_broken_20MAY2026.md
  - Phase-C-symptom-2 — /app/memory/screenshots/audit_panel_trust_view_broken_20MAY2026.md
  - SV-01/02/03       — /app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md

Frontend-only IDs (SV-01 link target, inline 404 friendly copy, save
toast) are covered by render-smoke step 11 + the per-component lint
pass; this file holds the API-layer regression tests.
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
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk95-{suffix}@example.com"
    password = "Chunk95-2026!"
    account_id = f"acc-c95-{suffix}"
    context_id = f"ctx-c95-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk9.5 Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk9.5 Context", "created_at": now_iso,
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
    await db_conn.chats.delete_many({"account_id": account_id})
    await db_conn.synisense_runs.delete_many({"account_id": account_id})
    await db_conn.solva_phase_d_sessions.delete_many({"account_id": account_id})
    await db_conn.solva_v2_sessions.delete_many({"account_id": account_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


# =====================================================================
# Phase C Symptom 2 — synisense-metrics ts type-mismatch
# =====================================================================
async def test_symptom2_ts_string_chat_created_at_still_aggregates_runs(client, db_conn, authed):
    """Reproduction of the 20-May QA report: `chats.created_at` is a
    string (historical inconsistency) while `synisense_runs.ts` is a
    BSON datetime. Pre-fix, the `$gte` filter silently returned 0
    rows. Post-fix, the chat-scoped metrics endpoint coerces the
    string to a datetime before applying the filter."""
    chat_id = f"chat-c95-{uuid.uuid4().hex[:8]}"
    created_at_str = datetime.now(timezone.utc).isoformat()  # stored as STRING
    await db_conn.chats.insert_one({
        "id": chat_id,
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "title": "PII test chat",
        "created_at": created_at_str,  # STRING — the bug shape
    })
    # Insert a synisense_runs row representing a successful Shield
    # call on that chat. `ts` is a real datetime (BSON Date).
    await db_conn.synisense_runs.insert_one({
        "id": f"sr-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "chat_id": chat_id,
        "surface": "chat",
        "ts": datetime.now(timezone.utc),  # BSON Date — mismatched type vs created_at
        "spans": [{"layer": "regex"}, {"layer": "regex"}, {"layer": "presidio"}],
        "stats": {"layer_won": "regex"},
    })

    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(f"/api/chats/{chat_id}/synisense-metrics", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # Pre-fix this came back as 0 / 0 / "on standby". Post-fix the
    # type-coerced filter sees the run and the metrics aggregate.
    assert body["identifiers_redacted"] == 3, body
    assert body["model_calls"] == 1, body
    assert body["storyline"] and "on standby" not in body["storyline"], body["storyline"]


async def test_symptom2_ts_datetime_chat_created_at_still_works(client, db_conn, authed):
    """Belt-and-braces — if `chats.created_at` is ALREADY a datetime
    (the correct schema shape), the coercion path passes it through
    unchanged."""
    chat_id = f"chat-c95-{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    await db_conn.chats.insert_one({
        "id": chat_id,
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "title": "Datetime ts chat",
        "created_at": now_dt,  # actual datetime
    })
    await db_conn.synisense_runs.insert_one({
        "id": f"sr-{uuid.uuid4().hex[:8]}",
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "chat_id": chat_id,
        "surface": "chat",
        "ts": datetime.now(timezone.utc),
        "spans": [{"layer": "regex"}],
        "stats": {"layer_won": "regex"},
    })
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(f"/api/chats/{chat_id}/synisense-metrics", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["identifiers_redacted"] == 1


# =====================================================================
# Phase C Symptom 1 — inline audit-panel endpoint 404 path
# =====================================================================
async def test_symptom1_audit_panel_404_when_message_not_in_chat(client, db_conn, authed):
    """The audit-panel endpoint correctly returns 404 when the
    `message_id` query param references a message that does not
    exist in the chat. The friendly-copy fix lives on the frontend
    (AuditPanel.jsx) but the backend contract that produces the 404
    must remain stable so the frontend's `status === 404` branch
    keeps firing."""
    chat_id = f"chat-c95-{uuid.uuid4().hex[:8]}"
    await db_conn.chats.insert_one({
        "id": chat_id,
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "title": "Empty chat",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synisense_audit_ids": [],
    })
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/chats/{chat_id}/audit-panel?message_id=msg-does-not-exist",
        headers=headers,
    )
    assert r.status_code == 404, r.text
    detail = r.json().get("detail") or ""
    assert "Message not found" in detail or "not found" in detail.lower(), detail


# =====================================================================
# SV-02 — /solva/v2/sessions requires context_id query param
# =====================================================================
async def test_sv02_sessions_endpoint_rejects_missing_context_id(client, authed):
    """Reproduction of the 20-May "Field Required" error. Without
    `context_id` query param the endpoint returns 422 listing
    `context_id` as the missing field — this is the FastAPI default
    Pydantic shape that produced the screenshot's error UI."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get("/api/solva/v2/sessions", headers=headers)
    assert r.status_code == 422, r.text
    body = r.json()
    detail = body.get("detail") or []
    missing_fields = {d.get("loc", [None, None])[1] for d in detail}
    assert "context_id" in missing_fields, body


async def test_sv02_sessions_endpoint_accepts_context_id_query(client, db_conn, authed):
    """With context_id supplied the endpoint returns 200. Empty
    context (no sessions yet) returns items=[]."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and isinstance(body["items"], list)
    assert body["count"] == 0, "fresh context should have no sessions"


# =====================================================================
# SV-03 — Phase D sessions merge into /solva/v2/sessions response
# =====================================================================
async def test_sv03_phase_d_sessions_surface_in_view_all_sessions_list(client, db_conn, authed):
    """The View-All-Sessions page reads from `/solva/v2/sessions`.
    Pre-fix, Phase D sessions (stored in `solva_phase_d_sessions`)
    were invisible there because the endpoint only queried the v2
    collection. Post-fix, Phase D sessions are merged into the
    response with their fields mapped to the v2 wire shape."""
    sid = f"sol-{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    await db_conn.solva_phase_d_sessions.insert_one({
        "session_id": sid,
        "user_id": authed["account_id"],
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "sub_module": "seek_clarity",
        "status": "active",
        "layer_state": "layer_1",
        "initial_framing": "Should we raise additional capital before Q3?",
        "title": "Capital raise timing — Q3 vs Q4",
        "schema_version": 3,
        "created_at": now_dt,
        "updated_at": now_dt,
        "completed_at": None,
    })

    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [it["id"] for it in body["items"]]
    assert sid in ids, body
    row = next(it for it in body["items"] if it["id"] == sid)
    assert row["engine"] == "phase_d", row
    assert row["title"] == "Capital raise timing — Q3 vs Q4", row
    assert row["intent"] == "Should we raise additional capital before Q3?", row
    assert row["submodule"] == "seek_clarity", row


# =====================================================================
# SV-03 — PATCH session title endpoint
# =====================================================================
async def test_sv03_patch_title_updates_session(client, db_conn, authed):
    """User-edited titles round-trip via the Phase D PATCH endpoint
    and are tagged `title_source=user` so a future re-run of
    submit_framing doesn't clobber them."""
    sid = f"sol-{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    await db_conn.solva_phase_d_sessions.insert_one({
        "session_id": sid,
        "user_id": authed["account_id"],
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "sub_module": "seek_clarity",
        "status": "active",
        "layer_state": "layer_1",
        "initial_framing": "Initial framing",
        "title": "Auto-generated working title",
        "title_source": "auto",
        "schema_version": 3,
        "created_at": now_dt,
        "updated_at": now_dt,
        "completed_at": None,
    })

    headers = await _login(client, authed["email"], authed["password"])
    r = await client.patch(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}/title",
        headers=headers,
        json={"title": "User-edited title for board review"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "User-edited title for board review"
    assert body["title_source"] == "user"

    # Verify persistence + source-flag flip.
    row = await db_conn.solva_phase_d_sessions.find_one(
        {"session_id": sid}, {"_id": 0, "title": 1, "title_source": 1},
    )
    assert row["title"] == "User-edited title for board review"
    assert row["title_source"] == "user"


async def test_sv03_patch_title_rejects_empty_string(client, db_conn, authed):
    """Pydantic's `min_length=1` plus the strip-after guard reject
    empty / whitespace-only titles — defence in depth."""
    sid = f"sol-{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    await db_conn.solva_phase_d_sessions.insert_one({
        "session_id": sid,
        "user_id": authed["account_id"],
        "account_id": authed["account_id"],
        "context_id": authed["context_id"],
        "sub_module": "seek_clarity",
        "status": "active",
        "layer_state": "framing",
        "initial_framing": "",
        "title": "",
        "schema_version": 3,
        "created_at": now_dt,
        "updated_at": now_dt,
        "completed_at": None,
    })
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.patch(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}/title",
        headers=headers,
        json={"title": ""},
    )
    # Pydantic 422 (min_length violation).
    assert r.status_code == 422, r.text


async def test_sv03_patch_title_rejects_cross_account_session(client, db_conn, authed):
    """A second account can't PATCH another user's session title —
    `_get_session` raises 404 before the update fires."""
    # Seed a session that belongs to ANOTHER account but lives in the
    # SAME context (membership for the attacker context is fine; we
    # block via session.account_id != ctx.account.id).
    other_account_id = f"acc-other-{uuid.uuid4().hex[:8]}"
    sid = f"sol-{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)
    await db_conn.solva_phase_d_sessions.insert_one({
        "session_id": sid,
        "user_id": other_account_id,
        "account_id": other_account_id,   # owned by attacker target
        "context_id": authed["context_id"],
        "sub_module": "seek_clarity",
        "status": "active",
        "layer_state": "framing",
        "initial_framing": "Confidential framing",
        "title": "Other user's title",
        "schema_version": 3,
        "created_at": now_dt,
        "updated_at": now_dt,
        "completed_at": None,
    })
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.patch(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}/title",
        headers=headers,
        json={"title": "Hijack attempt"},
    )
    assert r.status_code == 404, r.text


# =====================================================================
# Architectural invariant — auto-title routes through Shield only
# =====================================================================
def test_chunk95_auto_title_routes_through_shield_not_direct_llm():
    """Reads the helper source to confirm `_generate_session_auto_title`
    calls `shield_invoke` (NOT any direct LLM SDK). This is a static
    guard that complements the CI guard
    `test_no_direct_llm_calls_outside_shield`."""
    src = open("/app/backend/routers/solva_phase_d.py").read()
    assert "_generate_session_auto_title" in src
    # The helper body must contain a shield_invoke call.
    helper_start = src.index("async def _generate_session_auto_title")
    helper_end = src.index("async def ", helper_start + 1)
    helper_body = src[helper_start:helper_end]
    assert "shield_invoke" in helper_body, helper_body[:1500]
    # Never call openai / anthropic / litellm / genai SDKs directly.
    for forbidden in ("import openai", "import anthropic", "from openai",
                      "from anthropic", "import litellm", "google.generativeai"):
        assert forbidden not in helper_body, (forbidden, helper_body[:1500])
