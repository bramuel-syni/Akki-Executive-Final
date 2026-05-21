"""Chunk 18 — Track 4 infra: APScheduler hourly cron + token-accurate Shield metering.

Backend regression coverage:
  • Item 2 (cron) — `scheduler_lock.run_locked()` enforces exactly-once
    execution per (job_id, hour_bucket); the heartbeat row lands in
    `scheduler_runs`; the lock auto-reaps via the TTL index.
  • Item 2 (boot wiring) — APScheduler `synisense_engine_hourly` job is
    registered at startup with `CronTrigger(minute=0)`.
  • Item 3 (metering) — exact token counts + cost surface in the audit
    row when the provider SDK returned a usage payload; estimated path
    still works for fallback; per-model rate table covers our shipping
    providers.

Anchor: `/app/memory/sprints/CHUNK_18_STATE.md`.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


# =====================================================================
# Item 2 — Mongo-locked single-instance cron
# =====================================================================

async def test_chunk18_scheduler_lock_runs_once_per_bucket(db_conn):
    """Two replicas calling `run_locked` for the SAME bucket → only one runs."""
    from services.synisense.engine import scheduler_lock as sl

    await sl.ensure_indexes()
    job_id = "test_chunk18_once_per_bucket"
    bucket = sl.current_hour_bucket()

    # Clean slate.
    await db_conn[sl.LOCK_COLLECTION].delete_many({"job_id": job_id})
    await db_conn[sl.RUNS_COLLECTION].delete_many({"job_id": job_id})

    run_counter = {"calls": 0}

    async def _fake_pass():
        run_counter["calls"] += 1
        return {"derived": run_counter["calls"]}

    # First call wins.
    await sl.run_locked(job_id=job_id, fn=_fake_pass, bucket=bucket)
    # Second call (same bucket) is short-circuited by the lock.
    await sl.run_locked(job_id=job_id, fn=_fake_pass, bucket=bucket)
    # Different bucket → runs again.
    await sl.run_locked(job_id=job_id, fn=_fake_pass, bucket=bucket + "x")

    assert run_counter["calls"] == 2, "lock should let exactly one run per (job_id, bucket)"
    runs = await db_conn[sl.RUNS_COLLECTION].find(
        {"job_id": job_id}, {"_id": 0, "status": 1, "summary": 1},
    ).to_list(10)
    assert len(runs) == 2
    assert all(r["status"] == "ok" for r in runs)


async def test_chunk18_scheduler_lock_records_failure(db_conn):
    """Failed runs land a `status="failed"` heartbeat with the error message."""
    from services.synisense.engine import scheduler_lock as sl

    job_id = "test_chunk18_records_failure"
    bucket = sl.current_hour_bucket() + "-fail"

    await db_conn[sl.LOCK_COLLECTION].delete_many({"job_id": job_id})
    await db_conn[sl.RUNS_COLLECTION].delete_many({"job_id": job_id})

    async def _boom():
        raise RuntimeError("derivation went sideways")

    await sl.run_locked(job_id=job_id, fn=_boom, bucket=bucket)

    row = await db_conn[sl.RUNS_COLLECTION].find_one(
        {"job_id": job_id}, {"_id": 0},
    )
    assert row is not None
    assert row["status"] == "failed"
    assert "derivation went sideways" in (row.get("error") or "")


async def test_chunk18_scheduler_lock_ttl_index_present(db_conn):
    """`scheduler_locks` carries the TTL index on `expires_at`."""
    from services.synisense.engine import scheduler_lock as sl

    await sl.ensure_indexes()
    indexes = await db_conn[sl.LOCK_COLLECTION].index_information()
    ttl = indexes.get("scheduler_locks_ttl")
    assert ttl is not None, f"expected scheduler_locks_ttl index, got: {list(indexes.keys())}"
    assert ttl.get("expireAfterSeconds") == 0


def test_chunk18_engine_hourly_cron_registered_in_server():
    """Boot-wiring check — server.py registers the hourly cron with
    `CronTrigger(minute=0)`. Verified statically so we don't have to
    stand the app up to confirm the job is on the scheduler."""
    server_path = "/app/backend/server.py"
    with open(server_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "synisense_engine_hourly" in src
    assert "_EngCron(minute=0)" in src or "CronTrigger(minute=0)" in src
    assert "ensure_indexes" in src  # TTL index is armed
    assert "current_hour_bucket" in src  # bucket key plumbing


# =====================================================================
# Item 3 — Token-accurate Shield metering
# =====================================================================

async def test_chunk18_compute_cost_uses_per_model_rate_table():
    """Cost calculation looks up provider+model in the rate table.
    Anthropic claude-sonnet-4-5 row is the golden case: $3 in / $15 out
    per 1M tokens → 1_000_000 in + 1_000_000 out = $18.00."""
    from services.synisense.shield.audit_log import compute_cost_usd

    cost = compute_cost_usd(
        provider="anthropic", model="claude-sonnet-4-5-20250929",
        tokens_in=1_000_000, tokens_out=1_000_000,
    )
    assert cost == pytest.approx(18.00, abs=1e-6)

    # gpt-4o: $2.50 in / $10 out per 1M → 100k+50k = $0.75
    cost_gpt = compute_cost_usd(
        provider="openai", model="gpt-4o",
        tokens_in=100_000, tokens_out=50_000,
    )
    assert cost_gpt == pytest.approx(0.75, abs=1e-6)

    # Mock suffix is stripped before lookup.
    cost_mock = compute_cost_usd(
        provider="anthropic:mock", model="claude-sonnet-4-5-20250929:mock",
        tokens_in=4, tokens_out=4,
    )
    assert cost_mock is not None and cost_mock > 0

    # No tokens → None (legacy / early-return paths).
    assert compute_cost_usd(
        provider="anthropic", model="claude-sonnet-4-5-20250929",
        tokens_in=None, tokens_out=None,
    ) is None


async def test_chunk18_audit_log_persists_chunk18_fields(db_conn):
    """`write_audit` round-trips tokens_in / tokens_out / metering_method
    / actual_cost_usd into the row."""
    from services.synisense.shield import audit_log

    audit_id = "aud-test-chunk18-fields"
    await db_conn[audit_log.AUDIT_COLLECTION].delete_many({"audit_id": audit_id})

    await audit_log.write_audit(
        audit_id=audit_id, tenant_id="tnt-test", consumer_id="solva",
        user_id="usr-test", purpose="solva.layer_0.frame_audit",
        timestamp=datetime.now(timezone.utc).isoformat(),
        de_id_summary={}, dilution_score=0.0, exposure_reduction_score=0.0,
        llm_provider="anthropic", llm_model="claude-sonnet-4-5-20250929",
        request_hash="sha256:abc", response_hash="sha256:def",
        outcome="success", latency_ms=42,
        tokens_in=1234, tokens_out=567, metering_method="exact",
        actual_cost_usd=0.012,
    )

    row = await db_conn[audit_log.AUDIT_COLLECTION].find_one(
        {"audit_id": audit_id}, {"_id": 0},
    )
    assert row is not None
    assert row["tokens_in"] == 1234
    assert row["tokens_out"] == 567
    assert row["metering_method"] == "exact"
    assert row["actual_cost_usd"] == pytest.approx(0.012)


async def test_chunk18_shield_invoke_records_exact_metering_when_sdk_returns_usage(db_conn):
    """End-to-end: when `llm_router.invoke_with_metering` returns an exact
    usage payload, `client.invoke()` persists `metering_method="exact"`
    with the SDK's token counts AND a non-None `actual_cost_usd`."""
    from services.synisense.shield import client as shield_client, audit_log

    # Force live-mode logic path (mock + estimated would short-circuit).
    saved_mode = os.environ.get("SYNISENSE_LLM_MODE", "")
    os.environ["SYNISENSE_LLM_MODE"] = ""

    async def _fake_invoke_with_metering(de_id_content, *, model_preference="balanced", timeout_seconds=20.0):
        return (
            "the LLM said: " + de_id_content,
            "anthropic", "claude-sonnet-4-5-20250929",
            {"input_tokens": 4096, "output_tokens": 1024, "method": "exact"},
        )

    with patch(
        "services.synisense.shield.client.llm_router.invoke_with_metering",
        new=AsyncMock(side_effect=_fake_invoke_with_metering),
    ):
        result = await shield_client.invoke(
            purpose="solva.layer_0.frame_audit",
            content="qualified evidence: 14.2% capital adequacy",
            tenant_id="tnt-test-chunk18", consumer_id="solva",
            user_id="tnt-test-chunk18",
        )

    # Restore env.
    if saved_mode:
        os.environ["SYNISENSE_LLM_MODE"] = saved_mode
    else:
        os.environ.pop("SYNISENSE_LLM_MODE", None)

    row = await db_conn[audit_log.AUDIT_COLLECTION].find_one(
        {"audit_id": result["audit_id"]}, {"_id": 0},
    )
    assert row is not None
    assert row["metering_method"] == "exact"
    assert row["tokens_in"] == 4096
    assert row["tokens_out"] == 1024
    # 4096 in @ $3/M + 1024 out @ $15/M = 0.012288 + 0.01536 = 0.027648
    assert row["actual_cost_usd"] == pytest.approx(0.027648, abs=1e-6)
    assert row["llm_provider"] == "anthropic"
    assert row["llm_model"] == "claude-sonnet-4-5-20250929"


async def test_chunk18_shield_invoke_falls_back_to_estimated_when_usage_missing(db_conn):
    """Empty usage dict → metering_method="estimated" with char/4 counts
    and an estimated cost. Preserves the pre-Chunk-18 behaviour on every
    code path the SDK didn't surface usage for (mock mode, legacy SDK,
    early-return errors)."""
    from services.synisense.shield import client as shield_client, audit_log

    saved_mode = os.environ.get("SYNISENSE_LLM_MODE", "")
    os.environ["SYNISENSE_LLM_MODE"] = ""

    async def _fake_no_usage(de_id_content, *, model_preference="balanced", timeout_seconds=20.0):
        return ("response without usage", "openai", "gpt-4o", {})

    with patch(
        "services.synisense.shield.client.llm_router.invoke_with_metering",
        new=AsyncMock(side_effect=_fake_no_usage),
    ):
        result = await shield_client.invoke(
            purpose="solva.layer_0.frame_audit",
            content="some content here",
            tenant_id="tnt-test-chunk18-est", consumer_id="solva",
            user_id="tnt-test-chunk18-est",
        )

    if saved_mode:
        os.environ["SYNISENSE_LLM_MODE"] = saved_mode
    else:
        os.environ.pop("SYNISENSE_LLM_MODE", None)

    row = await db_conn[audit_log.AUDIT_COLLECTION].find_one(
        {"audit_id": result["audit_id"]}, {"_id": 0},
    )
    assert row is not None
    assert row["metering_method"] == "estimated"
    assert row["tokens_in"] >= 1
    assert row["tokens_out"] >= 1
    assert row["actual_cost_usd"] is not None
    assert row["actual_cost_usd"] >= 0


# =====================================================================
# Item 7 — CI architectural invariant — no NEW direct LLM call sites
# =====================================================================

def test_chunk18_no_new_direct_llm_calls():
    """Chunk 18 must NOT introduce any direct provider SDK imports
    outside the Shield. Static check on the files touched."""
    targets = [
        "/app/backend/services/synisense/engine/scheduler_lock.py",
    ]
    banned = ("import anthropic", "import openai", "import litellm", "import google.generativeai")
    for path in targets:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        for needle in banned:
            assert needle not in src, f"{path} contains banned import: {needle}"
