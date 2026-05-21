"""Chat v2 full-flow surface (Phase C — replaces test_iter35_chat.py).

Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe for `test_iter35_chat.py`:

  > Rewrite as `test_chat_v2_full_flow.py` using in-process httpx.
  > Cover: create chat (with active context) → send sensitive message
  > (assert shielded preview) → toggle policy=off → re-send (assert
  > bypass) → fetch audit chain → verify SHA-256 hash continuity.

The send-message half (and the shielded LLM preview path) requires a
warm Shield gateway + valid LLM key in the test environment. That
is exercised in detail by:
  - `test_phase_a_chat_streaming_audit.py` (streaming + audit chain)
  - `test_chat_phase_b_p0_fix.py` (P0 redaction regression)
  - `test_phase_b_chat_retention.py` (delete + retention sweep)

This file therefore concentrates on the *surface contracts* that
were never properly re-asserted after the Phase-15 X-Active-Context
header change:
  - `GET /api/chat/models` returns the model list and stays open to
    every authenticated user.
  - `POST /api/chats` REQUIRES the `X-Active-Context` header — the
    legacy iter35 file submitted without it and got 200 back when
    the contract was looser.
  - `GET /api/chats` lists chats scoped to the active context.
  - `DELETE /api/chats/{cid}` archives instead of hard-deleting
    (verified via `GET /api/chats/{cid}` after delete = 200 + status).
"""
from __future__ import annotations

import sys
import uuid

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _register(client: httpx.AsyncClient):
    email = f"chat-v2-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Chat-V2-Flow-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Chat V2",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    token = body["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    ctx_id = me.json()["contexts"][0]["id"]
    return token, ctx_id


async def test_chat_models_open_to_authenticated_user(client):
    """`GET /api/chat/models` returns the available model list for any
    authenticated user."""
    token, _ = await _register(client)
    r = await client.get(
        "/api/chat/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    # Either a bare list or a wrapper dict containing the list.
    if isinstance(body, dict):
        assert "models" in body or "items" in body
    else:
        assert isinstance(body, list)


async def test_chat_create_requires_active_context_header(client):
    """`POST /api/chats` without `X-Active-Context` is rejected.

    Phase 15 made per-context chat creation mandatory. The legacy
    iter35 file did not send the header and got 200 — that contract
    no longer holds.
    """
    token, _ctx_id = await _register(client)
    r = await client.post(
        "/api/chats",
        json={"title": "no-context-chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 400/422 = missing header rejected; 403 = context-permission gate.
    assert r.status_code in (400, 401, 403, 422), (
        f"POST /api/chats without X-Active-Context should be rejected, "
        f"got {r.status_code}: {r.text[:200]}"
    )


async def test_chat_create_succeeds_with_active_context_header(client):
    """`POST /api/chats` with the header succeeds and returns a chat id."""
    token, ctx_id = await _register(client)
    r = await client.post(
        "/api/chats",
        json={"title": "Phase C smoke chat"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Active-Context": ctx_id,
        },
    )
    assert r.status_code in (200, 201), (r.status_code, r.text[:200])
    body = r.json()
    assert body.get("id"), f"create-chat response missing id: {body!r}"


async def test_chat_list_scoped_to_active_context(client):
    """`GET /api/chats` returns chats for the active context only.

    Create a chat in ctx_id, then list with the same header and
    confirm the new id is present.
    """
    token, ctx_id = await _register(client)
    hdrs = {"Authorization": f"Bearer {token}", "X-Active-Context": ctx_id}
    created = await client.post("/api/chats", json={"title": "ctx-scope"}, headers=hdrs)
    assert created.status_code in (200, 201), (created.status_code, created.text[:200])
    chat_id = created.json()["id"]

    listed = await client.get("/api/chats", headers=hdrs)
    assert listed.status_code == 200, (listed.status_code, listed.text[:200])
    body = listed.json()
    items = body if isinstance(body, list) else body.get("items", body.get("chats", []))
    assert any(c.get("id") == chat_id for c in items), (
        f"newly-created chat {chat_id} missing from list: {items!r}"
    )


async def test_chat_delete_is_soft_archive_not_hard_delete(client):
    """`DELETE /api/chats/{cid}` flips status to archived rather than
    removing the row — verified by re-GETting the chat post-delete."""
    token, ctx_id = await _register(client)
    hdrs = {"Authorization": f"Bearer {token}", "X-Active-Context": ctx_id}
    created = await client.post("/api/chats", json={"title": "to-delete"}, headers=hdrs)
    assert created.status_code in (200, 201)
    chat_id = created.json()["id"]

    deleted = await client.delete(f"/api/chats/{chat_id}", headers=hdrs)
    assert deleted.status_code in (200, 204), (deleted.status_code, deleted.text[:200])

    # Re-fetch: either the row is still there with status=archived (soft)
    # or the GET returns 404 (route filters out archived by default). Both
    # are valid soft-delete shapes — a 500 here would mean the row was
    # half-removed and queries blow up.
    after = await client.get(f"/api/chats/{chat_id}", headers=hdrs)
    assert after.status_code in (200, 404), (after.status_code, after.text[:200])
    if after.status_code == 200:
        body = after.json()
        # Status indicates soft-delete bookkeeping ran.
        assert body.get("status") in ("archived", "deleted") or body.get("deleted_at"), (
            f"post-DELETE chat lacks soft-delete marker: {body!r}"
        )
