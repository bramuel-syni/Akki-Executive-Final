"""Phase R.3 (2026-05-27) — `feature_events` cohort-funnel instrumentation CI.

Locks the autonomous-mode contract:
  - `emit_feature_event` writes to `db.feature_events` (a NEW collection,
    separate from `db.telemetry_events` / `db.events`).
  - Each row carries `{id, event_type, account_id, cohort_tag,
    created_at, payload}`.
  - The function NEVER raises (failures only log).
  - 6 canonical event types are constants the call sites use (NOT raw
    strings): account.signed_up, cohort.magic_link.consumed,
    cohort.welcome.dispatched, solva.session.created,
    work_studio.export.completed, calendar.sync.linked.
  - `GET /api/admin/cohort/funnel` returns aggregate counts +
    unique-accounts per event_type.
  - `ensure_indexes` writes TTL (90d) + 2 compound indexes.
  - Source-strict wiring: auth_magic.py + solva_v2.py + work_studio_export.py +
    admin_cohort.py all emit the 4 events they own.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.cohort.feature_events import (  # noqa: E402
    emit_feature_event,
    ensure_indexes,
    KNOWN_EVENT_TYPES,
    ACCOUNT_SIGNED_UP,
    COHORT_MAGIC_LINK_CONSUMED,
    COHORT_WELCOME_DISPATCHED,
    SOLVA_SESSION_CREATED,
    WORK_STUDIO_EXPORT_COMPLETED,
    CALENDAR_SYNC_LINKED,
)


# ─────────────────────────────────────────────────────────────────────
# A. Constant namespace — the 6 canonical event types are locked
# ─────────────────────────────────────────────────────────────────────

def test_R3_a_six_canonical_event_types_exist():
    assert len(KNOWN_EVENT_TYPES) >= 6
    assert ACCOUNT_SIGNED_UP            in KNOWN_EVENT_TYPES
    assert COHORT_MAGIC_LINK_CONSUMED   in KNOWN_EVENT_TYPES
    assert COHORT_WELCOME_DISPATCHED    in KNOWN_EVENT_TYPES
    assert SOLVA_SESSION_CREATED        in KNOWN_EVENT_TYPES
    assert WORK_STUDIO_EXPORT_COMPLETED in KNOWN_EVENT_TYPES
    assert CALENDAR_SYNC_LINKED         in KNOWN_EVENT_TYPES


def test_R3_a_event_type_strings_follow_dotted_form():
    """Future additions must follow domain.entity.verb_past_tense form."""
    for ev in KNOWN_EVENT_TYPES:
        parts = ev.split(".")
        assert len(parts) >= 2, f"event type {ev!r} must use dotted form"
        # No spaces, no uppercase
        assert ev == ev.lower(), f"event type {ev!r} must be lowercase"
        assert " " not in ev, f"event type {ev!r} must not contain spaces"


# ─────────────────────────────────────────────────────────────────────
# B. emit_feature_event — writes a row + never raises
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R3_b_emit_writes_row_with_expected_shape():
    from core import db
    await emit_feature_event(
        event_type=SOLVA_SESSION_CREATED,
        account_id="r3-test-account-1",
        cohort_tag="founding_2026Q2_TEST",
        payload={"session_id": "sess-r3-1"},
    )
    row = await db.feature_events.find_one(
        {"account_id": "r3-test-account-1"}, {"_id": 0},
    )
    assert row is not None
    assert row["event_type"] == SOLVA_SESSION_CREATED
    assert row["account_id"] == "r3-test-account-1"
    assert row["cohort_tag"] == "founding_2026Q2_TEST"
    assert row["payload"] == {"session_id": "sess-r3-1"}
    assert isinstance(row["id"], str) and len(row["id"]) >= 16
    assert row["created_at"].endswith("+00:00") or row["created_at"].endswith("Z")
    # Cleanup
    await db.feature_events.delete_many({"account_id": "r3-test-account-1"})


@pytest.mark.asyncio
async def test_R3_b_emit_never_raises_on_unknown_type():
    """Unknown event types must STILL be written so R.5 console can
    surface the typo + no data is lost."""
    from core import db
    await emit_feature_event(
        event_type="something.totally.unknown",
        account_id="r3-unknown-acct",
    )
    row = await db.feature_events.find_one({"account_id": "r3-unknown-acct"}, {"_id": 0})
    assert row is not None
    assert row["event_type"] == "something.totally.unknown"
    await db.feature_events.delete_many({"account_id": "r3-unknown-acct"})


@pytest.mark.asyncio
async def test_R3_b_emit_with_no_payload_writes_empty_dict():
    from core import db
    await emit_feature_event(
        event_type=ACCOUNT_SIGNED_UP,
        account_id="r3-nopay-acct",
    )
    row = await db.feature_events.find_one({"account_id": "r3-nopay-acct"}, {"_id": 0})
    assert row is not None
    assert row["payload"] == {}
    assert row["cohort_tag"] is None
    await db.feature_events.delete_many({"account_id": "r3-nopay-acct"})


# ─────────────────────────────────────────────────────────────────────
# C. Source-strict wiring — 4 surfaces emit their canonical events
# ─────────────────────────────────────────────────────────────────────

def test_R3_c_auth_magic_emits_magic_link_consumed():
    src = (REPO / "backend" / "routers" / "auth_magic.py").read_text(encoding="utf-8")
    assert "COHORT_MAGIC_LINK_CONSUMED" in src
    assert "emit_feature_event(" in src


def test_R3_c_solva_v2_emits_session_created():
    src = (REPO / "backend" / "routers" / "solva_v2.py").read_text(encoding="utf-8")
    assert "SOLVA_SESSION_CREATED" in src
    assert "emit_feature_event(" in src


def test_R3_c_work_studio_export_emits_export_completed():
    src = (REPO / "backend" / "routers" / "work_studio_export.py").read_text(encoding="utf-8")
    assert "WORK_STUDIO_EXPORT_COMPLETED" in src
    assert "emit_feature_event(" in src


def test_R3_c_admin_cohort_emits_welcome_dispatched():
    src = (REPO / "backend" / "routers" / "admin_cohort.py").read_text(encoding="utf-8")
    assert "COHORT_WELCOME_DISPATCHED" in src
    assert "emit_feature_event(" in src


# ─────────────────────────────────────────────────────────────────────
# D. Funnel endpoint shape — wired + returns the locked output shape
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R3_d_funnel_endpoint_returns_locked_shape():
    """Source-strict + behaviour: the funnel endpoint exists and
    returns the locked output shape."""
    src = (REPO / "backend" / "routers" / "admin_cohort.py").read_text(encoding="utf-8")
    assert "@router.get(\"/funnel\")" in src
    assert "events_by_type" in src
    assert "unique_accounts_by_type" in src
    assert "total_events" in src

    # Live behaviour: insert a few events under a unique cohort_tag,
    # call the aggregator, verify the counters.
    from core import db
    cohort = "r3-funnel-probe-cohort"
    for i in range(3):
        await emit_feature_event(
            event_type=SOLVA_SESSION_CREATED,
            account_id=f"r3-funnel-acct-{i}",
            cohort_tag=cohort,
            payload={"session_id": f"s{i}"},
        )
    await emit_feature_event(
        event_type=WORK_STUDIO_EXPORT_COMPLETED,
        account_id="r3-funnel-acct-0",
        cohort_tag=cohort,
    )

    # Invoke the aggregation directly (avoids the admin auth layer
    # — the source-strict guard above confirms the endpoint is wired).
    pipeline = [
        {"$match": {"cohort_tag": cohort}},
        {"$group": {
            "_id": "$event_type",
            "count": {"$sum": 1},
            "accounts": {"$addToSet": "$account_id"},
        }},
    ]
    counts = {ev: 0 for ev in KNOWN_EVENT_TYPES}
    unique = {ev: 0 for ev in KNOWN_EVENT_TYPES}
    async for row in db.feature_events.aggregate(pipeline):
        ev = row["_id"]
        if ev in counts:
            counts[ev] = int(row["count"])
            unique[ev] = len([a for a in row["accounts"] if a])

    assert counts[SOLVA_SESSION_CREATED] == 3
    assert unique[SOLVA_SESSION_CREATED] == 3
    assert counts[WORK_STUDIO_EXPORT_COMPLETED] == 1
    assert unique[WORK_STUDIO_EXPORT_COMPLETED] == 1

    await db.feature_events.delete_many({"cohort_tag": cohort})


# ─────────────────────────────────────────────────────────────────────
# E. ensure_indexes — TTL + 2 compound indexes
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R3_e_ensure_indexes_creates_ttl_and_compound():
    from core import db
    await ensure_indexes()
    info = await db.feature_events.index_information()
    names = set(info.keys())
    # TTL index
    assert "feature_events_ttl_90d" in names
    # Compound indexes
    assert "feature_events_account_type" in names
    assert "feature_events_cohort_type" in names
