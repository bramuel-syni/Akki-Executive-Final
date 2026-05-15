"""Synisense Engine — Phase A unit + contract tests."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from services.synisense.engine import signal_query, signal_seeder, signal_types
from services.synisense.engine.signal_seeder import SIGNAL_COLLECTION
from services.synisense.models import SignalQueryFilter, SignalQueryPagination


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def isolated_engine_tenant(db_conn):
    """Tenant + clean signal collection."""
    tid = "engine-tenant-" + uuid.uuid4().hex[:10]
    yield tid
    await db_conn[SIGNAL_COLLECTION].delete_many({"tenant_id": tid})


# ─────────────────────────────────────────────────────────────────────
# Catalogue.
# ─────────────────────────────────────────────────────────────────────
def test_signal_catalogue_six_canonical_categories():
    cat = signal_types.catalogue()
    cats = sorted({d.signal_category for d in cat})
    # Every signal type must fit one of the six brief categories.
    allowed = {"profile", "anomaly", "life_stage", "risk", "operational", "compliance"}
    assert set(cats).issubset(allowed)
    # And every category should be represented at least once in Phase A.
    assert allowed == set(cats)


def test_signal_catalogue_versioned_v1():
    cat = signal_types.catalogue()
    for d in cat:
        assert d.version == "v1"


# ─────────────────────────────────────────────────────────────────────
# Seeder.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_seeder_writes_signals_with_derivation_source(
    db_conn, isolated_engine_tenant,
):
    await signal_seeder.seed_for_tenant(isolated_engine_tenant)
    cursor = db_conn[SIGNAL_COLLECTION].find(
        {"tenant_id": isolated_engine_tenant}, {"_id": 0},
    )
    rows = [r async for r in cursor]
    assert len(rows) >= 2, "expected at least churn_risk + behavioral_vector"
    for r in rows:
        ds = r.get("derivation_source")
        assert isinstance(ds, str) and ds.startswith("seeded_from_"), \
            f"every seeded signal must carry seeded_from_* derivation_source: {r}"
        assert r.get("confidence") == 0.5


@pytest.mark.asyncio
async def test_seeder_idempotent(db_conn, isolated_engine_tenant):
    await signal_seeder.seed_for_tenant(isolated_engine_tenant)
    n1 = await db_conn[SIGNAL_COLLECTION].count_documents(
        {"tenant_id": isolated_engine_tenant},
    )
    await signal_seeder.seed_for_tenant(isolated_engine_tenant)
    n2 = await db_conn[SIGNAL_COLLECTION].count_documents(
        {"tenant_id": isolated_engine_tenant},
    )
    assert n1 == n2, "re-seeding the same tenant should not duplicate rows"


@pytest.mark.asyncio
async def test_seeder_keeps_real_ingestion_rows(db_conn, isolated_engine_tenant):
    # Insert a fake real-ingestion row.
    await db_conn[SIGNAL_COLLECTION].insert_one({
        "signal_id": "real-" + uuid.uuid4().hex,
        "tenant_id": isolated_engine_tenant,
        "signal_category": "operational",
        "signal_type": "operational_health",
        "entity_ref": "ent-1",
        "payload": {"queue_depth": 12},
        "confidence": 0.9,
        "derivation_source": "real_ingestion",
        "created_at": _iso(),
    })
    await signal_seeder.seed_for_tenant(isolated_engine_tenant)
    real = await db_conn[SIGNAL_COLLECTION].find_one(
        {"tenant_id": isolated_engine_tenant, "derivation_source": "real_ingestion"},
        {"_id": 0},
    )
    assert real is not None, "seeder must not wipe real-ingestion rows"


# ─────────────────────────────────────────────────────────────────────
# Query.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_query_strict_tenant_scoping(db_conn):
    tid_a = "engine-a-" + uuid.uuid4().hex[:8]
    tid_b = "engine-b-" + uuid.uuid4().hex[:8]
    try:
        await signal_seeder.seed_for_tenant(tid_a)
        await signal_seeder.seed_for_tenant(tid_b)
        res = await signal_query.query(
            tenant_id=tid_a, filter_=SignalQueryFilter(),
            pagination=SignalQueryPagination(limit=100),
        )
        for s in res.signals:
            assert s.tenant_id == tid_a, "cross-tenant leak"
    finally:
        await db_conn[SIGNAL_COLLECTION].delete_many({"tenant_id": {"$in": [tid_a, tid_b]}})


@pytest.mark.asyncio
async def test_query_filter_by_category(db_conn, isolated_engine_tenant):
    await signal_seeder.seed_for_tenant(isolated_engine_tenant)
    res = await signal_query.query(
        tenant_id=isolated_engine_tenant,
        filter_=SignalQueryFilter(signal_category="risk"),
        pagination=SignalQueryPagination(limit=100),
    )
    for s in res.signals:
        assert s.signal_category == "risk"


@pytest.mark.asyncio
async def test_query_pagination(db_conn, isolated_engine_tenant):
    # Insert 10 signals manually with monotonic timestamps.
    base = datetime.now(timezone.utc)
    rows = []
    for i in range(10):
        rows.append({
            "signal_id": f"sig-{i:03d}",
            "tenant_id": isolated_engine_tenant,
            "signal_category": "profile", "signal_type": "behavioral_vector",
            "entity_ref": isolated_engine_tenant,
            "payload": {"vector": [0.0] * 8, "window_days": 7},
            "confidence": 0.5, "derivation_source": "seeded_from_action_log",
            "created_at": base.replace(microsecond=i * 1000).isoformat(),
        })
    await db_conn[SIGNAL_COLLECTION].insert_many(rows)
    # Page 1.
    page1 = await signal_query.query(
        tenant_id=isolated_engine_tenant,
        filter_=SignalQueryFilter(),
        pagination=SignalQueryPagination(limit=4),
    )
    assert len(page1.signals) == 4
    assert page1.next_cursor is not None
    # Page 2 — pass the cursor.
    page2 = await signal_query.query(
        tenant_id=isolated_engine_tenant,
        filter_=SignalQueryFilter(),
        pagination=SignalQueryPagination(limit=4, cursor=page1.next_cursor),
    )
    assert len(page2.signals) == 4
    # No overlap.
    ids1 = {s.signal_id for s in page1.signals}
    ids2 = {s.signal_id for s in page2.signals}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_query_excludes_mongo_objectid(db_conn, isolated_engine_tenant):
    await signal_seeder.seed_for_tenant(isolated_engine_tenant)
    res = await signal_query.query(
        tenant_id=isolated_engine_tenant,
        filter_=SignalQueryFilter(),
        pagination=SignalQueryPagination(limit=100),
    )
    for s in res.signals:
        d = s.model_dump()
        assert "_id" not in d
