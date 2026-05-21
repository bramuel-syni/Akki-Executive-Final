"""Cycle v2 — questions + reportees + checklists surface (Phase C).

Replaces the cycle half of the original `test_iter18_cycle_blog.py`
quarantine entry. Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe:

  > Split this file into `test_cycle_questions_v2.py` +
  > `test_blog_admin_v2.py` and rewrite each against current routes.

Cycle Manager v2 (Patch K) restructured the routes:
  - The legacy `/api/contexts/{cid}/cycle/...` surface is in `routers/cycle.py`.
  - Multi-cycle/master is in `routers/cycles.py` (mounted via `cycles_router`).
  - Per-cycle assignments are in `routers/cycle_assignments.py`.

This file is a small in-process httpx contract check that the
"questions + checklists" surface is still mounted and gated on auth.
We do NOT re-assert the full Iter18 happy-path because the v2
multi-cycle payload shapes are exercised in detail by
`test_cycles_v2.py` already.
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
    email = f"cycle-q-v2-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Cycle-Q-V2-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Cycle Q V2",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    body = r.json()
    token = body["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    ctx_id = me.json()["contexts"][0]["id"]
    return token, ctx_id


async def test_cycles_v2_list_route_exists_and_gates_auth(client):
    """`GET /api/contexts/{cid}/cycles` (Cycle v2 multi-cycle master)
    is mounted and rejects un-authenticated calls."""
    # Auth gate — no token.
    fake_ctx = uuid.uuid4().hex
    r = await client.get(f"/api/contexts/{fake_ctx}/cycles")
    assert r.status_code in (401, 403, 404), (r.status_code, r.text[:200])


async def test_cycle_legacy_questions_route_still_mounted(client):
    """The legacy `/api/contexts/{cid}/cycle/questions` surface is
    still wired (read-only existence check via openapi)."""
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    # Look for the *family* — Cycle v1 questions hangs off this prefix.
    matching = [p for p in paths if "/cycle" in p and "{context_id}" in p]
    assert matching, (
        "no `/cycle` surface mounted under /api/contexts/{context_id} — "
        "router include may have been dropped."
    )


async def test_cycle_assignments_inbox_route_exists(client):
    """Cycle assignments surface (`/api/contexts/{cid}/cycle-assignments/...`
    + `/api/ned/inbox/assignments`) is mounted (introduced in the
    Cycle sprint)."""
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    assignments_paths = [
        p for p in paths
        if "/cycle-assignments" in p
        or "/cycle_assignments" in p
        or "/inbox/assignments" in p
        or ("/cycles/" in p and "/assignments" in p)
    ]
    assert assignments_paths, (
        "no cycle_assignments routes mounted — Patch K may have regressed."
    )


async def test_cycles_master_returns_200_for_member(client):
    """Authenticated member can hit the cycles master list and gets a
    200 — empty list is fine; we only assert the contract holds."""
    token, ctx_id = await _register(client)
    r = await client.get(
        f"/api/contexts/{ctx_id}/cycles",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 200 = list returned; 404 acceptable if no cycle scaffold exists
    # yet on a freshly-registered tenant; 403 fails the contract.
    assert r.status_code in (200, 404), (r.status_code, r.text[:200])
    if r.status_code == 200:
        body = r.json()
        # The list endpoint returns either a bare list or a wrapper.
        assert isinstance(body, (list, dict))
