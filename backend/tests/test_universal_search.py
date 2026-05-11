"""Phase F0 — Universal Search regression tests.

Covers:
- A2 — federates across memberships (per_context.length >= 2)
- A6 — at least 4 surfaces return real rows end-to-end
- A7 — audit row written with q_hash; raw q NOT stored
- Negative — q < 2 chars returns 400
- Privacy — user not a member of a context never sees its rows
- Cross-context-open — audit row with from/to context_ids
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

from motor.motor_asyncio import AsyncIOMotorClient

# Pull the router's helpers directly — no HTTP needed to assert the
# dispatcher's contract.
from services.universal_search import (
    SURFACE_HANDLERS, run_federated_search, search_documents,
    search_pulse, search_monitor,
)
from routers.search import _q_hash


SENT = uuid.uuid4().hex[:10]
NEEDLE = f"PWALL-UV-{SENT}"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db_ = client[os.environ["DB_NAME"]]
    yield db_
    client.close()


@pytest.fixture(scope="module")
async def planted(db):
    """Two contexts, both owned by `account_id=acct-uv`, each carrying a
    document + a signal + a goal whose body contains NEEDLE. A third
    context exists where `account_id=acct-uv` is NOT a member — used
    to prove non-membership scoping."""
    acct_uv = f"acct-uv-{SENT}"
    acct_foreign = f"acct-foreign-{SENT}"
    cid_a = f"ctx-uvA-{SENT}"
    cid_b = f"ctx-uvB-{SENT}"
    cid_c = f"ctx-uvC-{SENT}"   # acct_uv is NOT a member here

    # Contexts
    await db.contexts.insert_many([
        {"id": cid_a, "name": "Sinasa", "owner_account_id": acct_uv},
        {"id": cid_b, "name": "Mekong Capital", "owner_account_id": acct_uv},
        {"id": cid_c, "name": "Foreign Industries", "owner_account_id": acct_foreign},
    ])
    # Memberships
    await db.memberships.insert_many([
        {"account_id": acct_uv, "context_id": cid_a, "role": "executive", "status": "active"},
        {"account_id": acct_uv, "context_id": cid_b, "role": "ned", "status": "active"},
        {"account_id": acct_foreign, "context_id": cid_c, "role": "executive", "status": "active"},
    ])
    # Documents — one per ctx, plus a foreign doc in ctx C carrying the
    # needle (to prove the dispatcher never reaches it).
    await db.documents.insert_many([
        {"id": f"doc-A-{SENT}", "context_id": cid_a, "name": f"Audit A — {NEEDLE}",
         "extracted_text": f"Background. {NEEDLE} appears in the analysis.",
         "status": "extracted", "created_at": "2026-05-10T10:00:00Z"},
        {"id": f"doc-B-{SENT}", "context_id": cid_b, "name": "Quarterly memo",
         "extracted_text": f"Mekong's quarterly view referencing {NEEDLE} risk.",
         "status": "extracted", "created_at": "2026-05-10T11:00:00Z"},
        {"id": f"doc-FOREIGN-{SENT}", "context_id": cid_c,
         "name": f"Foreign doc — {NEEDLE}", "extracted_text": NEEDLE,
         "status": "extracted", "created_at": "2026-05-10T11:30:00Z"},
    ])
    # Pulse signals
    await db.signals.insert_many([
        {"id": f"sig-A-{SENT}", "context_id": cid_a, "type": "risk", "state": "active",
         "headline": f"Liquidity flag — {NEEDLE}",
         "summary": "Runway 4 months, see audit.",
         "created_at": "2026-05-10T12:00:00Z"},
        {"id": f"sig-B-{SENT}", "context_id": cid_b, "type": "opportunity", "state": "active",
         "headline": "Capital opening", "summary": f"Window through Q3, ref {NEEDLE}.",
         "created_at": "2026-05-10T12:30:00Z"},
    ])
    # Strategic goals
    await db.strategic_goals.insert_many([
        {"id": f"goal-A-{SENT}", "context_id": cid_a, "title": f"Reduce DSO — {NEEDLE}",
         "description": "Target 45 days by Q4", "department": "Finance",
         "created_at": "2026-05-10T13:00:00Z"},
        {"id": f"goal-B-{SENT}", "context_id": cid_b, "title": "Refinance facility",
         "description": f"Roll £80m before {NEEDLE} window closes",
         "department": "Finance", "created_at": "2026-05-10T13:30:00Z"},
    ])
    # Chats — one per ctx, owned by acct_uv. We test message-body and
    # title hits.
    await db.chats.insert_many([
        {"id": f"chat-A-{SENT}", "account_id": acct_uv, "context_id": cid_a,
         "title": f"Audit discussion {NEEDLE}", "status": "active",
         "created_at": "2026-05-10T14:00:00Z",
         "last_message_at": "2026-05-10T14:15:00Z"},
        {"id": f"chat-B-{SENT}", "account_id": acct_uv, "context_id": cid_b,
         "title": "Capital meeting", "status": "active",
         "created_at": "2026-05-10T14:30:00Z",
         "last_message_at": "2026-05-10T14:45:00Z"},
    ])
    await db.chat_messages.insert_many([
        {"chat_id": f"chat-B-{SENT}", "account_id": acct_uv, "role": "user",
         "content": f"Talk through {NEEDLE} risk framing", "seq": 1,
         "created_at": "2026-05-10T14:45:00Z"},
    ])
    h = {"acct_uv": acct_uv, "cid_a": cid_a, "cid_b": cid_b, "cid_c": cid_c}
    yield h
    # Cleanup
    await db.contexts.delete_many({"id": {"$in": [cid_a, cid_b, cid_c]}})
    await db.memberships.delete_many({"context_id": {"$in": [cid_a, cid_b, cid_c]}})
    await db.documents.delete_many({"context_id": {"$in": [cid_a, cid_b, cid_c]}})
    await db.signals.delete_many({"context_id": {"$in": [cid_a, cid_b, cid_c]}})
    await db.strategic_goals.delete_many({"context_id": {"$in": [cid_a, cid_b, cid_c]}})
    await db.chats.delete_many({"context_id": {"$in": [cid_a, cid_b, cid_c]}})
    await db.chat_messages.delete_many({"chat_id": {"$regex": f"chat-.-{SENT}"}})
    await db.audit_log.delete_many(
        {"account_id": acct_uv, "action": {"$in": ["search.federated", "search.cross_context_open"]}}
    )


def test_q_hash_normalises_case_and_whitespace():
    a = _q_hash("  Hello WORLD  ")
    b = _q_hash("hello world")
    assert a == b
    assert len(a) == 64


def test_q_hash_differs_for_different_inputs():
    assert _q_hash("foo") != _q_hash("bar")


@pytest.mark.asyncio
async def test_surface_registry_complete():
    """All 7 surfaces listed in the dispatcher registry."""
    for s in ("documents", "chats", "pulse", "monitor", "cycle", "work_studio", "briefs"):
        assert s in SURFACE_HANDLERS
    # Phase 1 handlers must be callables (not stubs).
    from services.universal_search import (
        search_documents as sd, search_chats as sc,
        search_pulse as sp, search_monitor as sm, _empty as e,
    )
    assert SURFACE_HANDLERS["documents"] is sd
    assert SURFACE_HANDLERS["chats"] is sc
    assert SURFACE_HANDLERS["pulse"] is sp
    assert SURFACE_HANDLERS["monitor"] is sm
    assert SURFACE_HANDLERS["cycle"] is e
    assert SURFACE_HANDLERS["work_studio"] is e
    assert SURFACE_HANDLERS["briefs"] is e


@pytest.mark.asyncio
async def test_search_federates_across_memberships(db, planted):
    h = await planted.__anext__() if hasattr(planted, "__anext__") else planted
    mships = [
        {"context_id": h["cid_a"], "context_name": "Sinasa"},
        {"context_id": h["cid_b"], "context_name": "Mekong Capital"},
    ]
    out = await run_federated_search(
        db, account_id=h["acct_uv"], q=NEEDLE, memberships=mships,
    )
    # A6 — at least 4 surfaces returned non-zero rows.
    surface_hits = {s["surface"]: s["count"] for s in out["per_surface"]}
    for s in ("documents", "chats", "pulse", "monitor"):
        assert surface_hits.get(s, 0) >= 1, f"surface {s} returned 0 hits"
    # A2 — per_context covers both contexts and total > 0.
    ctx_ids = {p["context_id"] for p in out["per_context"]}
    assert h["cid_a"] in ctx_ids and h["cid_b"] in ctx_ids
    assert sum(p["count"] for p in out["per_context"]) >= 6  # docs+sigs+goals+1 chat at least


@pytest.mark.asyncio
async def test_search_respects_membership_scope(db, planted):
    """A user whose memberships list does NOT include cid_c must NOT
    see foreign doc rows even though the foreign doc carries the
    needle verbatim."""
    h = await planted.__anext__() if hasattr(planted, "__anext__") else planted
    mships = [
        {"context_id": h["cid_a"], "context_name": "Sinasa"},
        # NOTE: cid_b and cid_c intentionally omitted.
    ]
    out = await run_federated_search(
        db, account_id=h["acct_uv"], q=NEEDLE, memberships=mships,
    )
    for r in out["results"]:
        assert r["context_id"] == h["cid_a"], (
            f"leaked foreign context_id into result: {r['context_id']}"
        )
        assert h["cid_c"] not in r.get("deep_link", ""), "foreign deep_link leaked"
    # The foreign doc whose body literally IS the needle must not show up.
    titles = [r["title"] for r in out["results"]]
    assert "Foreign doc — " + NEEDLE not in titles


@pytest.mark.asyncio
async def test_search_audit_row_written_and_no_raw_q(db, planted):
    h = await planted.__anext__() if hasattr(planted, "__anext__") else planted
    expected_hash = _q_hash(NEEDLE)
    # Simulate one call's audit by invoking the router directly.
    from routers.search import federated_search

    class _FakeQ:
        pass

    out = await federated_search(
        q=NEEDLE, limit=25, context_id=None, surface=None, offset=0,
        current={"id": h["acct_uv"]},
    )
    assert out["total"] >= 1
    row = await db.audit_log.find_one(
        {"account_id": h["acct_uv"], "action": "search.federated"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    assert row is not None, "audit row not written for search.federated"
    md = row.get("metadata") or {}
    assert md.get("q_hash") == expected_hash
    # Raw q must NOT be stored — assert the needle is absent from the
    # whole metadata blob.
    blob = repr(row)
    assert NEEDLE not in blob, "raw query string leaked into audit row"


@pytest.mark.asyncio
async def test_search_requires_q_min_length(planted):
    from routers.search import federated_search
    from fastapi import HTTPException

    h = await planted.__anext__() if hasattr(planted, "__anext__") else planted
    with pytest.raises(HTTPException) as exc:
        await federated_search(
            q="a", limit=25, context_id=None, surface=None, offset=0,
            current={"id": h["acct_uv"]},
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_cross_context_open_audit(db, planted):
    h = await planted.__anext__() if hasattr(planted, "__anext__") else planted
    from routers.search import cross_context_open
    body = {
        "from_context_id": h["cid_a"],
        "to_context_id": h["cid_b"],
        "surface": "documents",
        "result_id": f"doc-B-{SENT}",
    }
    out = await cross_context_open(body=body, current={"id": h["acct_uv"]})
    assert out["ok"] is True
    row = await db.audit_log.find_one(
        {"account_id": h["acct_uv"], "action": "search.cross_context_open"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    assert row is not None
    md = row.get("metadata") or {}
    assert md.get("from_context_id") == h["cid_a"]
    assert md.get("to_context_id") == h["cid_b"]
    assert md.get("surface") == "documents"
    expected = hashlib.sha256(f"doc-B-{SENT}".encode()).hexdigest()
    assert md.get("result_id_hash") == expected


@pytest.mark.asyncio
async def test_cross_context_open_rejects_foreign_target(db, planted):
    """Caller is NOT a member of cid_c — must 403."""
    h = await planted.__anext__() if hasattr(planted, "__anext__") else planted
    from routers.search import cross_context_open
    from fastapi import HTTPException
    body = {
        "from_context_id": h["cid_a"],
        "to_context_id": h["cid_c"],
        "surface": "documents",
        "result_id": "x",
    }
    with pytest.raises(HTTPException) as exc:
        await cross_context_open(body=body, current={"id": h["acct_uv"]})
    assert exc.value.status_code == 403


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
