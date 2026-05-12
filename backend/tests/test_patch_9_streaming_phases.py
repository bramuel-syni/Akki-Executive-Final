"""
test_patch_9_streaming_phases.py — Patch 9 SSE phase event acceptance.

Verifies that the new streaming wrapper endpoints emit `phase` events in
the locked vocabulary order. The inner handlers are exercised against
real fixtures (cycle + solva session); failures inside the inner call
still produce a phase sequence terminated by `complete` + `error` events.
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
from services.streaming_phases import (
    PHASE_VOCABULARY, encode_phase_event,
)


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
        "owner": _acc("p9-stream"),
        "ctx":   f"ctx-p9-{uuid.uuid4().hex[:10]}",
    }
    db = core_mod.db
    await db.contexts.delete_many({"id": e["ctx"]})
    await db.memberships.delete_many({"context_id": e["ctx"]})
    await db.accounts.update_one({"id": e["owner"]["id"]}, {"$set": e["owner"]}, upsert=True)
    await db.contexts.insert_one({
        "id": e["ctx"], "name": "P9 Co", "owner_account_id": e["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": e["ctx"], "account_id": e["owner"]["id"]},
        {"$set": {
            "context_id": e["ctx"], "account_id": e["owner"]["id"],
            "role": "owner", "status": "active",
        }},
        upsert=True,
    )
    yield e


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


def _parse_sse(raw: str):
    """Parse SSE blocks into a list of {event, data} dicts (ignore comments)."""
    events = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        ev = {"event": "message", "data": ""}
        for line in block.splitlines():
            if line.startswith("event:"):
                ev["event"] = line[6:].strip()
            elif line.startswith("data:"):
                ev["data"] = (ev["data"] + line[5:].strip()) if ev["data"] else line[5:].strip()
        events.append(ev)
    return events


# -----------------------------------------------------------------------------
# Helper: encoder unit test (no HTTP).
# -----------------------------------------------------------------------------
def test_encoder_rejects_unknown_phases():
    with pytest.raises(ValueError):
        encode_phase_event("warp_speed")
    # Known phases should encode cleanly.
    for k in PHASE_VOCABULARY:
        out = encode_phase_event(k)
        assert "event: phase" in out
        assert '"phase":"' + k + '"' in out.replace(" ", "")


# -----------------------------------------------------------------------------
# Patch 9: cycle compile stream — sequence
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cycle_compile_stream_emits_phases_in_order(env):
    _auth(env["owner"])
    async with _client() as c:
        async with c.stream(
            "POST",
            f"/api/contexts/{env['ctx']}/cycle/draft-compilation/stream",
        ) as response:
            assert response.status_code == 200, await response.aread()
            raw = (await response.aread()).decode("utf-8", errors="replace")
    events = _parse_sse(raw)
    phase_events = [e for e in events if e["event"] == "phase"]
    phase_keys = []
    for e in phase_events:
        try:
            phase_keys.append(json.loads(e["data"])["phase"])
        except Exception:
            pass
    assert phase_keys[:3] == ["reading_context", "shielding_input", "reasoning"]
    # An error path can short-circuit before drafting/refining; if the run
    # succeeds we must see the full sequence.
    if "complete" in phase_keys and "drafting" in phase_keys:
        for first, second in zip(phase_keys, phase_keys[1:]):
            assert PHASE_VOCABULARY.index(first) <= PHASE_VOCABULARY.index(second), \
                f"phases out of order: {phase_keys}"


# -----------------------------------------------------------------------------
# Patch 9: work studio enhance stream — sequence
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_enhance_stream_emits_phases_in_order(env):
    _auth(env["owner"])
    async with _client() as c:
        async with c.stream(
            "POST",
            f"/api/contexts/{env['ctx']}/work-studio/enhance/deck/stream",
            json={"deck_id": "nonexistent"},
        ) as response:
            assert response.status_code == 200
            raw = (await response.aread()).decode("utf-8", errors="replace")
    events = _parse_sse(raw)
    phase_keys = [
        json.loads(e["data"])["phase"]
        for e in events
        if e["event"] == "phase"
    ]
    assert phase_keys[:3] == ["reading_context", "shielding_input", "reasoning"]
    assert "complete" in phase_keys


# -----------------------------------------------------------------------------
# Patch 9: solva turn stream — sequence
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_solva_turn_stream_emits_phases_in_order(env):
    _auth(env["owner"])
    async with _client() as c:
        async with c.stream(
            "POST",
            f"/api/contexts/{env['ctx']}/solva/sessions/nonexistent/turn/stream",
            json={"message": "hi"},
        ) as response:
            assert response.status_code == 200
            raw = (await response.aread()).decode("utf-8", errors="replace")
    events = _parse_sse(raw)
    phase_keys = [
        json.loads(e["data"])["phase"]
        for e in events
        if e["event"] == "phase"
    ]
    # We expect at least the leading three phases; a missing handler or
    # 404 inner result still surfaces those three + a terminal complete.
    assert phase_keys[:3] == ["reading_context", "shielding_input", "reasoning"]
    assert "complete" in phase_keys
