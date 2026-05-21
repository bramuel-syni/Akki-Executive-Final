"""Chunk 19 — Bank-QA evidence pack polish + cron-health endpoint.

C19-005 — `GET /api/admin/synisense/cron-health` reads the
`scheduler_runs` heartbeat collection (Chunk 18) and returns the
most-recent run per `job_id`. Bank-QA reviewers use this surface to
verify scheduled work actually runs in production.

Anchor: `/app/memory/sprints/CHUNK_19_STATE.md`.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient


pytest_asyncio_mode = "auto"

# Async tests use explicit @pytest.mark.asyncio. Sync tests don't —
# avoids the "marked with @asyncio but not async" warning that
# module-level pytestmark would emit on sync helpers.


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


# =====================================================================
# C19-005 — Admin cron health endpoint
# =====================================================================

@pytest.mark.asyncio
async def test_chunk19_005_cron_health_returns_latest_per_job(db_conn):
    """Seed two heartbeat rows for the same `job_id` — the endpoint
    must return only the most recent."""
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from routers.synisense_observability import router, _require_superadmin

    app = FastAPI()
    app.include_router(router)

    async def _allow_superadmin():
        return {"id": "test-superadmin", "is_superadmin": True}

    app.dependency_overrides[_require_superadmin] = _allow_superadmin

    job_id = "test_chunk19_005_cron_health_a"
    await db_conn["scheduler_runs"].delete_many({"job_id": {"$regex": "^test_chunk19_005_"}})

    older = datetime.now(timezone.utc) - timedelta(hours=2)
    newer = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_conn["scheduler_runs"].insert_many([
        {
            "job_id": job_id, "replica_id": "rep-old",
            "started_at": older,
            "finished_at": older + timedelta(seconds=2),
            "duration_ms": 2000, "status": "ok",
            "summary": {"derived": 12}, "error": None,
        },
        {
            "job_id": job_id, "replica_id": "rep-new",
            "started_at": newer,
            "finished_at": newer + timedelta(seconds=1),
            "duration_ms": 1500, "status": "ok",
            "summary": {"derived": 34}, "error": None,
        },
        {
            "job_id": "test_chunk19_005_cron_health_b",
            "replica_id": "rep-other",
            "started_at": newer - timedelta(minutes=20),
            "finished_at": newer - timedelta(minutes=20) + timedelta(seconds=3),
            "duration_ms": 3000, "status": "failed",
            "summary": {}, "error": "RuntimeError: simulated",
        },
    ])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/synisense/cron-health")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert isinstance(rows, list)

    by_job = {r["job_id"]: r for r in rows
              if (r["job_id"] or "").startswith("test_chunk19_005_")}
    assert job_id in by_job
    assert "test_chunk19_005_cron_health_b" in by_job

    a = by_job[job_id]
    assert a["replica_id"] == "rep-new"
    assert a["status"] == "ok"
    assert a["duration_ms"] == 1500
    assert a["summary"] == {"derived": 34}
    assert a["last_run_at"].startswith(newer.isoformat()[:19])
    assert a["hour_bucket"] == newer.strftime("%Y%m%d-%H")

    b = by_job["test_chunk19_005_cron_health_b"]
    assert b["status"] == "failed"
    assert b["error"] == "RuntimeError: simulated"

    await db_conn["scheduler_runs"].delete_many({"job_id": {"$regex": "^test_chunk19_005_"}})


@pytest.mark.asyncio
async def test_chunk19_005_cron_health_empty_when_no_runs(db_conn):
    """Fresh deploy / pre-top-of-hour state — endpoint returns `[]`
    for any unseen job prefix."""
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from routers.synisense_observability import router, _require_superadmin

    app = FastAPI()
    app.include_router(router)

    async def _allow_superadmin():
        return {"id": "test-superadmin", "is_superadmin": True}

    app.dependency_overrides[_require_superadmin] = _allow_superadmin

    await db_conn["scheduler_runs"].delete_many({"job_id": "test_chunk19_005_NONE_exists"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/synisense/cron-health")
    assert resp.status_code == 200
    rows = resp.json()
    test_rows = [r for r in rows if (r.get("job_id") or "").startswith("test_chunk19_005_NONE")]
    assert test_rows == []


@pytest.mark.asyncio
async def test_chunk19_005_cron_health_requires_superadmin():
    """Non-admin caller → 403."""
    from fastapi import FastAPI, HTTPException
    from httpx import AsyncClient, ASGITransport
    from routers.synisense_observability import router, _require_superadmin

    app = FastAPI()
    app.include_router(router)

    async def _deny():
        raise HTTPException(status_code=403, detail="Superadmin only.")

    app.dependency_overrides[_require_superadmin] = _deny

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/admin/synisense/cron-health")
    assert resp.status_code == 403
    assert "Superadmin only" in resp.text


# =====================================================================
# C19-004 — Holistic product features document
# =====================================================================

def test_chunk19_004_features_doc_exists_with_required_sections():
    """The holistic AKKI features doc must exist with the dispatch's
    10 mandatory sections."""
    path = Path("/app/memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md")
    assert path.exists(), f"holistic features doc missing at {path}"
    src = path.read_text(encoding="utf-8")
    required = [
        "What AKKI is",
        "Personas served",
        "Architectural foundation",
        "Feature catalogue by surface",
        "Privacy & trust surfaces",
        "Infrastructure & performance posture",
        "QA sprint outcomes",
        "Open items requiring PO input",
        "Deferred & known-gap items",
        "Glossary",
    ]
    missing = [s for s in required if s not in src]
    assert not missing, f"Sections missing from features doc: {missing}"
    # Performance posture section must include the cold-start budget
    # numbers from Chunk 18.5.
    assert "15.7" in src and "235" in src, (
        "Cold-start budget metrics (15.7× cold, 235× warm) missing from § 6"
    )
    # Length sanity check — dispatch specified 8-12 pages of markdown
    # (roughly 2500-6000 words).
    word_count = len(src.split())
    assert word_count >= 2500, f"features doc only {word_count} words; expected 2500+"


# =====================================================================
# Final morning report
# =====================================================================

def test_chunk19_final_morning_report_present():
    """The autonomous-sprint log must carry the closing morning report
    so the human wakeup state is single-read."""
    log = Path("/app/memory/AUTONOMOUS_SPRINT_LOG.md").read_text(encoding="utf-8")
    assert "Morning Report — End of Autonomous Sprint" in log
    # The report's content must touch the chunks shipped.
    for chunk in ("9.5", "17", "18", "18.5", "19"):
        assert chunk in log, f"chunk {chunk} missing from morning report"
