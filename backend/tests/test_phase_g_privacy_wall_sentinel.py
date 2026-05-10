"""Phase G — Privacy Wall regression sentinel.

Asserts the new G fields (state, content_hash, merge_count, comments,
bookmarked_at, resolved_at, resolution_note, reasoning, last_merged_at)
NEVER appear in the cross-board aggregator response.

Run:
  pytest backend/tests/test_phase_g_privacy_wall_sentinel.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

from motor.motor_asyncio import AsyncIOMotorClient
from services.metadata_signatures import derive_and_persist
from services.privacy_wall import (
    _ALLOW_SIGNALS, _DENY_SIGNALS, cross_context_query,
)
from services.signal_dedup import dedup_or_insert, signal_content_hash


# Phase G fields — new in this phase. Per spec, every one of these
# MUST be in _DENY_SIGNALS (so cross_context_query strips them) and
# MUST NOT appear in /pulse/across-boards response payloads.
PHASE_G_FIELDS = (
    "state", "content_hash", "merge_count", "comments",
    "bookmarked_at", "bookmarked_by",
    "resolved_at", "resolved_by", "resolution_note",
    "last_merged_at", "reasoning",
)

# Across-boards response shape — locked. Anything else is a leak.
EXPECTED_TOP_KEYS = {"patterns", "window_days", "active_board_signature_count", "leakage_check"}
EXPECTED_PATTERN_KEYS = {
    "signature_kind", "signature_value",
    "other_boards_count", "active_board_count",
    "first_seen_other", "last_seen_other",
}


def test_phase_g_fields_in_denylist():
    """Static check: every Phase G field is denied + none are in allow."""
    for f in PHASE_G_FIELDS:
        assert f in _DENY_SIGNALS, f"Phase G field {f!r} missing from _DENY_SIGNALS"
        assert f not in _ALLOW_SIGNALS, (
            f"Phase G field {f!r} accidentally allowlisted"
        )


def test_phase_g_content_hash_helper_is_deterministic():
    h1 = signal_content_hash("Audit risk", "Receivables ageing", "risk")
    h2 = signal_content_hash("AUDIT RISK", "  receivables ageing ", "risk")
    h3 = signal_content_hash("Audit risk", "Receivables ageing", "opportunity")
    assert h1 == h2, "hash should normalise whitespace + case"
    assert h1 != h3, "hash should incorporate signal_type"
    assert len(h1) == 64, "sha256 hex digest"


@pytest.fixture(scope="module")
def db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


SENT_G_A = f"PWALL-G-A-{uuid.uuid4().hex[:12]}"
SENT_G_B = f"PWALL-G-B-{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
async def planted_g(db):
    """Plant Phase G-shaped signals (with state, content_hash, comments,
    bookmarked_at, resolved_at, resolution_note populated) in two
    contexts so the cross-board aggregator has cross-board hits."""
    cid_a = f"test-pgwall-A-{uuid.uuid4().hex[:8]}"
    cid_b = f"test-pgwall-B-{uuid.uuid4().hex[:8]}"
    common = "MiFID II suitability — review next audit committee."
    for cid, sentinel in ((cid_a, SENT_G_A), (cid_b, SENT_G_B)):
        sid = f"test-pgsig-{uuid.uuid4().hex}"
        sig = {
            "id": sid, "context_id": cid, "type": "risk",
            "headline": f"MiFID II exposure flagged — {sentinel}",
            "summary": f"{common} Sentinel-payload: {sentinel}",
            "confidence": "high",
            "created_at": "2026-05-10T13:00:00Z",
            # Phase G fields
            "state": "bookmarked",
            "merge_count": 3,
            "comments": [{"id": "c1", "account_id": "u",
                          "note": f"Private note carrying {sentinel}",
                          "created_at": "2026-05-10T13:30:00Z"}],
            "bookmarked_at": "2026-05-10T14:00:00Z",
            "bookmarked_by": "user-x",
            "resolved_at": None,
            "resolution_note": f"Hidden resolution note {sentinel}",
            "reasoning": f"Reasoning carries {sentinel}",
        }
        sig["content_hash"] = signal_content_hash(
            sig["headline"], sig["summary"], sig["type"],
        )
        await db.signals.insert_one(sig)
        await derive_and_persist(
            db,
            text=f"{sig['headline']} {sig['summary']}",
            context_id=cid, account_id="u",
            source_artefact_kind="signal", source_artefact_id=sid,
        )
    h = {"ctx_a": cid_a, "ctx_b": cid_b}
    yield h
    await db.signals.delete_many({"context_id": {"$in": [cid_a, cid_b]}})
    await db.context_metadata_signatures.delete_many(
        {"context_id": {"$in": [cid_a, cid_b]}},
    )


@pytest.mark.asyncio
async def test_phase_g_cross_context_query_strips_g_fields(db, planted_g):
    h = await planted_g.__anext__() if hasattr(planted_g, "__anext__") else planted_g
    rows = await cross_context_query(
        db.signals, collection_name="signals",
        query={"context_id": {"$in": [h["ctx_a"], h["ctx_b"]]}},
        limit=10,
    )
    assert len(rows) >= 2
    for r in rows:
        for f in PHASE_G_FIELDS:
            assert f not in r or r[f] in (None, "", [], {}), (
                f"Phase G field {f!r} leaked: {r.get(f)!r}"
            )
        # Sanity — sentinel must not be present anywhere in the row.
        blob = repr(r)
        assert SENT_G_A not in blob and SENT_G_B not in blob, (
            f"sentinel leaked into projected row: {r}"
        )


@pytest.mark.asyncio
async def test_phase_g_aggregator_response_shape_locked(db, planted_g):
    """Across-boards response shape must be the fixed key set —
    NO new Phase G fields, NO sentinel content."""
    from routers.pulse import pulse_across_boards

    h = await planted_g.__anext__() if hasattr(planted_g, "__anext__") else planted_g
    # Build a minimal ctx that satisfies the function signature.
    fake_ctx = {"context": {"id": h["ctx_a"]},
                "account": {"id": "u"}}
    resp = await pulse_across_boards(
        context_id=h["ctx_a"], window_days=30,
        min_other_boards=1, limit=50, ctx=fake_ctx,
    )
    # Top-level shape must match exactly.
    assert set(resp.keys()) == EXPECTED_TOP_KEYS, (
        f"unexpected top keys in across-boards response: "
        f"got={set(resp.keys())}, expected={EXPECTED_TOP_KEYS}"
    )
    # Every pattern row must match the locked key set.
    for p in resp["patterns"]:
        assert set(p.keys()) == EXPECTED_PATTERN_KEYS, (
            f"unexpected pattern keys: got={set(p.keys())}, "
            f"expected={EXPECTED_PATTERN_KEYS}"
        )
        # No Phase G field has snuck in.
        for f in PHASE_G_FIELDS:
            assert f not in p, f"Phase G field {f!r} leaked into pattern: {p}"
    # No sentinel anywhere in response body.
    body = repr(resp)
    assert SENT_G_A not in body and SENT_G_B not in body, (
        "sentinel content leaked into aggregator response"
    )
    assert resp["leakage_check"] == "metadata_only"


@pytest.mark.asyncio
async def test_phase_g_dedup_increments_merge_count(db):
    """Same headline+summary+type → merge_count++, no new row."""
    cid = f"test-pgdedup-{uuid.uuid4().hex[:8]}"
    base = {
        "id": str(uuid.uuid4()), "context_id": cid, "type": "risk",
        "headline": "Liquidity tight",
        "summary": "Cash runway 4 months",
        "created_at": "2026-05-10T15:00:00Z", "state": "active",
    }
    row1, inserted1 = await dedup_or_insert(db, dict(base))
    assert inserted1 is True
    base2 = {**base, "id": str(uuid.uuid4()),
             "created_at": "2026-05-10T15:05:00Z"}
    row2, inserted2 = await dedup_or_insert(db, base2)
    assert inserted2 is False, "second insert should merge"
    assert row2["merge_count"] >= 2
    assert row2["id"] == row1["id"], "merge keeps original id"

    rows = await db.signals.find({"context_id": cid}, {"_id": 0}).to_list(10)
    assert len(rows) == 1, f"expected 1 row, got {len(rows)}"

    # Cleanup.
    await db.signals.delete_many({"context_id": cid})


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
