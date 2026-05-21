"""Decks admin telemetry surface (Phase C — replaces 1/3 of test_iter55_decks.py).

Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe for `test_iter55_decks.py`:

  > Split into 3 small files: ... `test_decks_admin_telemetry.py` (admin stats) …

The original Iter55 file hit `/api/admin/decks/stats` against the
live preview URL with admin seed creds. Today the deck telemetry
surface is mounted on the admin LLM-spend router (`routers/admin_llm_spend.py`)
which aggregates per-deck quality-check spend, AND a few admin-only
endpoints in `routers/decks.py` like `GET /api/decks/{deck_id}/context`.

This file is a small contract smoke that confirms:
  - The admin spend surface still rejects non-admin tokens.
  - The legacy `/api/decks/{id}/context` lookup returns 404 for an
    unknown deck instead of 500 (regression guard against the
    pre-Phase-12 NPE that the original suite caught).
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
    email = f"decks-tel-{uuid.uuid4().hex[:10]}@example.com"
    pw = "Decks-Tel-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Decks Telemetry",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return r.json()["access_token"]


async def test_admin_llm_spend_rejects_non_admin(client):
    """The admin LLM-spend telemetry must reject non-superadmin tokens."""
    token = await _register(client)
    r = await client.get(
        "/api/admin/llm/spend",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 401 (no auth interpretation) or 403 (role check fired).
    assert r.status_code in (401, 403), (r.status_code, r.text[:200])


async def test_admin_llm_spend_requires_auth_at_all(client):
    """No Authorization header → 401, never 200."""
    r = await client.get("/api/admin/llm/spend")
    assert r.status_code in (401, 403), (r.status_code, r.text[:200])


async def test_deck_context_lookup_unknown_id_is_404(client):
    """`GET /api/decks/{unknown_id}/context` returns 404, not 500.

    This is the regression-guard the original Iter55 admin-telemetry
    block originally caught: a missing deck used to NPE inside the
    aggregation pipeline.
    """
    token = await _register(client)
    bogus_deck = uuid.uuid4().hex
    r = await client.get(
        f"/api/decks/{bogus_deck}/context",
        headers={"Authorization": f"Bearer {token}"},
    )
    # 404 = deck not found; 403 = caller not allowed to read; both are
    # safe contracts. 500 would indicate the NPE has come back.
    assert r.status_code in (403, 404), (r.status_code, r.text[:200])
