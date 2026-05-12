"""
test_patch_12_streaming_v3.py — Patch 12 integration acceptance.

Verifies that the Patch 9 SSE wrappers continue to emit phase events
in the locked order, AND that consecutive `phase` events arrive in the
order the client crossfade logic expects (no out-of-order arrivals).

Frontend crossfade is JS-tested in `src/lib/clauseStream.test.js`. This
backend test pins the upstream contract the client depends on.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app
from services.streaming_phases import PHASE_VOCABULARY


def _acc(prefix):
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": prefix.title(),
        "name": prefix.title(),
    }


@pytest.fixture
async def env():
    e = {
        "owner": _acc("p12-v3"),
        "ctx":   f"ctx-p12-{uuid.uuid4().hex[:10]}",
    }
    db = core_mod.db
    await db.contexts.delete_many({"id": e["ctx"]})
    await db.memberships.delete_many({"context_id": e["ctx"]})
    await db.accounts.update_one({"id": e["owner"]["id"]}, {"$set": e["owner"]}, upsert=True)
    await db.contexts.insert_one({
        "id": e["ctx"], "name": "P12 Co", "owner_account_id": e["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": e["ctx"], "account_id": e["owner"]["id"]},
        {"$set": {"context_id": e["ctx"], "account_id": e["owner"]["id"],
                   "role": "owner", "status": "active"}},
        upsert=True,
    )
    yield e


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _parse_sse(raw: str):
    out = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        ev = {"event": "message", "data": ""}
        for line in block.splitlines():
            if line.startswith("event:"):
                ev["event"] = line[6:].strip()
            elif line.startswith("data:"):
                ev["data"] = (ev["data"] + line[5:].strip()) if ev["data"] else line[5:].strip()
        out.append(ev)
    return out


@pytest.mark.asyncio
async def test_phase_events_arrive_in_locked_order_for_crossfade(env):
    """Phase events must arrive in PHASE_VOCABULARY order. The client
    crossfade logic relies on this — out-of-order arrivals would snap
    the label without a crossfade (acceptable but undesirable)."""
    _auth(env["owner"])
    async with _client() as c:
        async with c.stream(
            "POST",
            f"/api/contexts/{env['ctx']}/cycle/draft-compilation/stream",
        ) as response:
            assert response.status_code == 200
            raw = (await response.aread()).decode("utf-8", errors="replace")
    events = _parse_sse(raw)
    phase_seq = []
    for e in events:
        if e["event"] != "phase":
            continue
        try:
            phase_seq.append(json.loads(e["data"])["phase"])
        except Exception:
            pass
    assert phase_seq, "no phase events emitted"
    # Indexes must be monotonically non-decreasing.
    idxs = [PHASE_VOCABULARY.index(p) for p in phase_seq]
    assert all(b >= a for a, b in zip(idxs, idxs[1:])), (
        f"phase events arrived out of locked order: {phase_seq}"
    )
    # The first emitted phase must be reading_context.
    assert phase_seq[0] == "reading_context"
    # Honest semantics: `complete` fires ONLY on real success. The cycle
    # compile inner handler may raise (e.g. on the empty test context here),
    # which surfaces an `error` SSE event and skips the `complete` phase.
    # That's correct — the client must NOT play the completion settle on
    # a failed run. We assert the contract instead of forcing `complete`.
    error_events = [e for e in events if e["event"] == "error"]
    if "complete" not in phase_seq:
        assert error_events, (
            "phase did not reach `complete` and no `error` event was emitted — "
            "this would leave the client hanging mid-stream"
        )
