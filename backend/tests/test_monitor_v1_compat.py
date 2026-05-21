"""Monitor v1 back-compat smoke (Phase C — replaces test_iter27_monitor.py).

Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe for `test_iter27_monitor.py`:

  > Repurpose as `test_monitor_v1_compat.py` — keep ~3 smoke tests
  > confirming the v1 endpoint still returns 200 for back-compat;
  > delete the rest. The new Monitor v2 surface is tested by
  > `test_patch_5_monitor_v2.py` (3 tests, all green).

The original Iter27 suite asserted a fixed payload shape against the
v1 `GET /api/contexts/{cid}/monitor?function=<role>` endpoint. That
endpoint is still wired in `routers/monitor.py` and the schema is
still served by the `monitor` router included from `server.py:170`,
but the v2 surface (`/api/contexts/{cid}/monitor/{kind}`) is the
modern path. This test only asserts back-compat: the v1 endpoint
returns 200 + an envelope containing `function` + `signals` for each
of the five locked role tokens, and rejects unknown role tokens with
422. We do NOT re-assert the full payload shape since that contract
has drifted across Patch 5.

In-process httpx + ASGITransport, fresh account → no rate-limit risk.
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
    """Create a fresh account → returns (token, default_ctx_id)."""
    email = f"monitor-compat-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Monitor-Compat-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Monitor Compat",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    token = body["access_token"]
    ctx_id = body["account"].get("default_context_id") or body.get("contexts", [{}])[0].get("id")
    if not ctx_id:
        # Fall back to /auth/me — register may not include contexts in some shapes.
        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        ctx_id = me.json()["contexts"][0]["id"]
    return token, ctx_id


async def test_monitor_v1_returns_200_for_each_executive_role(client):
    """The five locked role tokens (ceo/cfo/coo/commercial/other) still
    return 200 against the v1 surface."""
    token, ctx_id = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    for role in ("ceo", "cfo", "coo", "commercial", "other"):
        r = await client.get(
            f"/api/contexts/{ctx_id}/monitor",
            params={"function": role},
            headers=headers,
        )
        assert r.status_code == 200, (role, r.status_code, r.text[:200])
        body = r.json()
        # Back-compat envelope: function echoed back + signals dict present.
        assert body.get("function") == role
        assert "signals" in body and isinstance(body["signals"], dict)


async def test_monitor_v1_rejects_unknown_role(client):
    """Validation contract: unknown role token → 422 (pydantic Query regex)."""
    token, ctx_id = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.get(
        f"/api/contexts/{ctx_id}/monitor",
        params={"function": "garbage_role"},
        headers=headers,
    )
    assert r.status_code in (400, 422), (r.status_code, r.text[:200])


async def test_monitor_v1_unauthenticated_rejected(client):
    """Auth gate still bites — no token = 401/403."""
    token, ctx_id = await _register(client)  # only used to mint a valid ctx_id
    # Same ctx_id, no Authorization header.
    r = await client.get(
        f"/api/contexts/{ctx_id}/monitor",
        params={"function": "ceo"},
    )
    assert r.status_code in (401, 403), (r.status_code, r.text[:200])
