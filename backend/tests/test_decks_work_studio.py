"""Decks Work-Studio surface (Phase C — replaces 1/3 of test_iter55_decks.py).

Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe for `test_iter55_decks.py`:

  > Split into 3 small files: `test_decks_work_studio.py`
  > (create/list/get against Work Studio routes),
  > `test_decks_admin_telemetry.py` (admin stats),
  > `test_inbound_uuid_fallback.py` (the smaller piece).

This file owns the Work-Studio create/list/get smoke. Decks are now
generated through `CreateArtefactModal.jsx` against the deck routes
in `routers/decks.py` (which sits underneath the Work Studio Tab UI
surface). The legacy `/api/decks` admin surface was rewritten to
`/api/contexts/{cid}/decks` per-context — that's the contract we
assert here.

The end-to-end deck *generation* (outline → generate) requires real
LLM keys and live context data, so this smoke only validates the
LIST + GET paths against a fresh tenant. Generation itself is
covered by `tests/test_phase_a_chat_streaming_audit.py` flow tests
on the shielded LLM gateway.
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
    email = f"decks-ws-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Decks-WS-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Decks WS",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    token = body["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    ctx_id = me.json()["contexts"][0]["id"]
    return token, ctx_id


async def test_decks_list_empty_for_fresh_tenant(client):
    """A brand-new tenant has zero decks → 200 + empty list contract.

    The endpoint returns `{"items": [...], "count": N}` (wrapper form);
    older surfaces returned a bare list. We accept both.
    """
    token, ctx_id = await _register(client)
    r = await client.get(
        f"/api/contexts/{ctx_id}/decks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    if isinstance(body, dict):
        items = body.get("items", body.get("decks", []))
        assert items == [], f"fresh tenant should have no decks, got {body!r}"
        # Optional count field should also reflect emptiness.
        if "count" in body:
            assert body["count"] == 0
    else:
        assert body == [], f"fresh tenant should have no decks, got {body!r}"


async def test_decks_get_nonexistent_returns_404(client):
    """Deterministic deck-id miss → 404, not 500."""
    token, ctx_id = await _register(client)
    fake_deck_id = uuid.uuid4().hex
    r = await client.get(
        f"/api/contexts/{ctx_id}/decks/{fake_deck_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404, (r.status_code, r.text[:200])


async def test_decks_list_requires_membership(client):
    """A different account cannot list decks of someone else's
    context — 403/404 expected."""
    token_a, ctx_a = await _register(client)
    token_b, _ = await _register(client)
    r = await client.get(
        f"/api/contexts/{ctx_a}/decks",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code in (403, 404), (r.status_code, r.text[:200])


async def test_decks_unauthenticated_rejected(client):
    """No Bearer token → 401/403."""
    _token, ctx_id = await _register(client)
    r = await client.get(f"/api/contexts/{ctx_id}/decks")
    assert r.status_code in (401, 403), (r.status_code, r.text[:200])
