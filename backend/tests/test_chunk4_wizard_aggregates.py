"""Chunk 4 — Compilation Wizard kind dispatch regression tests
(WS-R02, WS-R04, WS-R05, WS-R07, WS-R08).

The Compile-XXX buttons in `pages/WorkStudio.jsx` historically all
passed the string `"report"` to `onCompile(...)`, regardless of which
Compile button was clicked. That made the wizard:

  * land on Step 2 instead of Step 1     (WS-R02 / R07 / R08)
  * show Report pre-selected on Step 1   (WS-R04)
  * query Step 2 sources by `kind=report` (WS-R05 — Minutes empty;
    WS-R08 sources empty for Committee Pack)

The frontend fix lives in WorkStudio.jsx (correct type per button) +
CompilationWizard.jsx (always start at Step 1, format default keyed
off type). This file locks the backend side: the aggregates endpoint
must accept every kind the wizard's `ARTEFACT_TYPES` table maps to,
and the per-kind item routing must be honoured strictly so a Compile
Minutes wizard sees ONLY minutes (never any cycle_board_packs / decks
/ etc.).

The frontend unit-test layer is intentionally light in this codebase
— `render-smoke.js` carries the click-the-button assertions instead
(see `scripts/render-smoke.js` Step 5, added in this chunk).
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


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_conn():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest_asyncio.fixture
async def seeded(db_conn):
    """Seed an account + 1 context. We seed a `cycle_board_pack` row
    in `db.boardpacks` so we can prove the kind=cycle_board_pack
    aggregate returns it (and nothing else). The other 5 kinds in
    this codebase pull from different source-of-truth collections
    (cycle_minutes / cycle_committee_pack from `db.documents`
    filtered by doc_kind; deck / report / briefing from their own
    derived listings) — we don't seed those; instead we assert that
    the endpoint accepts each kind cleanly and returns a 200 + items
    list, which is the only contract this chunk needs to lock.
    """
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk4-wiz-{suffix}@example.com"
    password = "Chunk4Wiz2026!"
    aid = f"acc-c4-{suffix}"
    cid = f"ctx-c4-{suffix}"
    now = _iso()

    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid, "email": email, "password_hash": hash_password(password),
        "name": "Chunk4 Wizard Probe", "role": "executive", "created_at": now,
        "default_context_id": cid, "session_version": 0, "verified": True,
    })
    await db_conn.contexts.insert_one({
        "id": cid, "name": "Probe Ctx Chunk4", "type": "executive_personal",
        "status": "active", "owner_account_id": aid, "created_at": now,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": cid, "account_id": aid,
        "status": "active", "role": "executive", "sub_role": "admin", "joined_at": now,
    })

    # Seed exactly one boardpack row for cycle_board_pack dispatch.
    bp_id = f"agg-bp-{uuid.uuid4().hex[:8]}"
    await db_conn.boardpacks.insert_one({
        "id": bp_id,
        "context_id": cid,
        "kind": "cycle_board_pack",
        "name": "Probe-cycle_board_pack-name",
        "title": "Probe-cycle_board_pack-title",
        "items": [],
        "executive_summary": "Summary.",
        "version": 1,
        "meeting_date": now,
        "created_by": aid,
        "created_at": now,
        "status": "active",
    })

    yield {
        "email": email, "password": password, "account_id": aid, "context_id": cid,
        "board_pack_id": bp_id,
    }
    await db_conn.boardpacks.delete_many({"context_id": cid})
    await db_conn.memberships.delete_many({"account_id": aid})
    await db_conn.contexts.delete_one({"id": cid})
    await db_conn.accounts.delete_one({"id": aid})


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.mark.parametrize("kind", [
    "cycle_board_pack",
    "cycle_minutes",
    "cycle_committee_pack",
    "deck",
    "report",
    "briefing",
])
@pytest.mark.asyncio
async def test_aggregates_accepts_every_wizard_kind(client, seeded, kind):
    """The aggregate endpoint must respond cleanly (200 + items list)
    for every kind the wizard's `ARTEFACT_TYPES` table maps to.
    Pre-Chunk 4 only `cycle_board_pack` was actually reachable from
    the UI; the others returned empty because the buttons passed
    `report` regardless. This test proves the backend was always
    capable of differentiating — the bug was upstream wiring.
    """
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates",
        params={"kind": kind, "page_size": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"{kind}: {r.status_code} {r.text}"
    data = r.json()
    assert "items" in data, f"{kind}: response missing `items`"
    assert isinstance(data["items"], list), f"{kind}: `items` is not a list"


@pytest.mark.asyncio
async def test_board_pack_kind_surfaces_seeded_row(client, seeded):
    """When a cycle_board_pack row is seeded, the kind=cycle_board_pack
    response surfaces it and the response does NOT include rows of
    foreign kinds. The most-likely regression class going forward."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates",
        params={"kind": "cycle_board_pack", "page_size": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    items = r.json().get("items") or []
    ids = [it["id"] for it in items]
    # IDs are prefixed by the aggregate-kind namespace (e.g.
    # `cycle_board_pack::<rowid>`) so we match by suffix.
    seeded_id = seeded["board_pack_id"]
    assert any(rid == seeded_id or rid.endswith(f"::{seeded_id}") for rid in ids), (
        f"seeded board_pack {seeded_id} not surfaced; got {ids}"
    )


@pytest.mark.asyncio
async def test_board_pack_response_does_not_leak_into_other_kinds(client, seeded):
    """The seeded `cycle_board_pack` row must NOT surface under any
    other kind. (Belt-and-braces — if a future dispatch wires a kind
    to the wrong source-of-truth, this fails.)"""
    token = await _login(client, seeded["email"], seeded["password"])
    seeded_id = seeded["board_pack_id"]
    for kind in ("cycle_minutes", "cycle_committee_pack", "deck", "report", "briefing"):
        r = await client.get(
            f"/api/contexts/{seeded['context_id']}/briefings/aggregates",
            params={"kind": kind, "page_size": 50},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        ids = [it["id"] for it in (r.json().get("items") or [])]
        leaked = [rid for rid in ids if rid == seeded_id or rid.endswith(f"::{seeded_id}")]
        assert not leaked, (
            f"cycle_board_pack row leaked into kind={kind} response: {ids}"
        )


@pytest.mark.asyncio
async def test_aggregates_rejects_unknown_kind(client, seeded):
    """Defence-in-depth: an unknown kind must 400 rather than fall
    through to a default. Pre-fix the wizard could pass anything;
    post-fix it passes one of the six valid keys."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates",
        params={"kind": "definitely_not_a_kind"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    body = r.text.lower()
    # Error message must list the valid kinds so a developer
    # mis-configuring the frontend sees the right names.
    for expected in ("cycle_board_pack", "cycle_minutes", "cycle_committee_pack", "deck"):
        assert expected in body, f"expected kind {expected} in error: {body[:300]}"
