"""P5.15 — Scheduler lockdown.

Coverage:
  * Scheduler idempotency: same `(account_id, week_iso, digest_version)`
    swept twice → exactly one Mongo row.
  * Boundary correctness: scheduler honours an explicit `week_iso`
    override and writes that exact value.
  * Dormant-tenant skip: an account with no recent corpus is
    silently skipped (status="skipped_no_corpus"), NOT written.
  * Disabled-by-env: `IDEAS_SCHEDULER_DISABLED=true` short-circuits
    the cron entry point.
  * Voice-lint clean: scheduler source carries no banned vocabulary.
  * Source-strict: server.py wires the Monday-07:00 UTC job under
    the canonical id `ideas_weekly_sweep`.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

import server  # noqa: F401
from services.ideas_engine import (
    DEFAULT_ACTIVE_WINDOW_DAYS,
    is_scheduler_disabled,
    run_weekly_ideas_sweep,
    sweep_account,
    week_iso_for,
)


# ─── Helpers ─────────────────────────────────────────────────────


async def _seed_corpus(db, *, account_id: str, n_docs: int = 5) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    seeded: List[Dict[str, Any]] = []
    for i in range(n_docs):
        doc_id = "doc-sched-" + uuid.uuid4().hex[:10]
        await db.documents.insert_one({
            "id": doc_id,
            "account_id": account_id,
            "title": f"Scheduler test document {i}",
            "filename": f"sched_{i}.pdf",
            "status": "indexed",
            "created_at": now,
            "updated_at": now,
        })
        chunk_ids = []
        for ci in range(4):
            cid = "chunk-sched-" + uuid.uuid4().hex[:10]
            await db.extractions_log.insert_one({
                "id": cid,
                "document_id": doc_id,
                "page": ci + 1,
                "kind": "paragraph",
                "text": (
                    f"Sched doc {i} chunk {ci}: observed that the metric "
                    f"moved meaningfully across the period under review; "
                    f"reviewers may want to triangulate against context "
                    f"this single chunk does not capture. "
                ) * 2,
                "created_at": now,
            })
            chunk_ids.append(cid)
        seeded.append({"document_id": doc_id, "chunk_ids": chunk_ids})
    return seeded


async def _ensure_account(db, *, account_id: str) -> None:
    """Insert a minimal account row so `run_weekly_ideas_sweep`'s
    accounts-cursor includes it."""
    await db.accounts.update_one(
        {"id": account_id},
        {"$setOnInsert": {
            "id": account_id,
            "email": f"{account_id}@p5-15-sched.example.com",
            "name": "Scheduler test account",
            "declared_role": "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


# ─── sweep_account ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sweep_account_generates_when_corpus_present():
    from core import db
    acct = "acct-p515-sched-" + uuid.uuid4().hex[:8]
    await _ensure_account(db, account_id=acct)
    await _seed_corpus(db, account_id=acct, n_docs=5)

    out = await sweep_account(db, account_id=acct, user_id=acct)
    assert out["status"] == "generated", out
    assert out["card_count"] == 4, out
    # The synthesizer-produced row must be persisted.
    row = await db.ideas_digests.find_one(
        {"account_id": acct, "week_iso": out["week_iso"]},
        {"_id": 0, "id": 1, "cards": 1},
    )
    assert row is not None and len(row["cards"]) == 4


@pytest.mark.asyncio
async def test_sweep_account_is_idempotent_on_double_run():
    """Same tenant × same week × same digest_version → second sweep
    is a no-op (`status="exists"`); exactly ONE Mongo row remains."""
    from core import db
    acct = "acct-p515-sched-idem-" + uuid.uuid4().hex[:8]
    await _ensure_account(db, account_id=acct)
    await _seed_corpus(db, account_id=acct, n_docs=5)
    first = await sweep_account(db, account_id=acct, user_id=acct)
    assert first["status"] == "generated"
    second = await sweep_account(db, account_id=acct, user_id=acct)
    assert second["status"] == "exists", second
    assert second["digest_id"] == first["digest_id"]
    count = await db.ideas_digests.count_documents(
        {"account_id": acct, "week_iso": first["week_iso"]},
    )
    assert count == 1, f"expected 1 row, got {count}"


@pytest.mark.asyncio
async def test_sweep_account_skips_dormant_tenant():
    """Account with no recent corpus → silently skipped, no row written."""
    from core import db
    acct = "acct-p515-sched-dormant-" + uuid.uuid4().hex[:8]
    await _ensure_account(db, account_id=acct)
    # NO seed — corpus is empty.

    out = await sweep_account(db, account_id=acct, user_id=acct)
    assert out["status"] == "skipped_no_corpus", out
    count = await db.ideas_digests.count_documents({"account_id": acct})
    assert count == 0


@pytest.mark.asyncio
async def test_sweep_account_skips_stale_corpus_outside_window():
    """Documents older than `DEFAULT_ACTIVE_WINDOW_DAYS` → silently skipped."""
    from core import db
    acct = "acct-p515-sched-stale-" + uuid.uuid4().hex[:8]
    await _ensure_account(db, account_id=acct)
    # Insert a doc whose updated_at is more than `DEFAULT_ACTIVE_WINDOW_DAYS`
    # ago — the sweep should skip the tenant.
    stale_ts = (
        datetime.now(timezone.utc) - timedelta(days=DEFAULT_ACTIVE_WINDOW_DAYS + 5)
    ).isoformat()
    await db.documents.insert_one({
        "id": "doc-stale-" + uuid.uuid4().hex[:8],
        "account_id": acct,
        "title": "Stale doc",
        "filename": "stale.pdf",
        "status": "indexed",
        "created_at": stale_ts,
        "updated_at": stale_ts,
    })
    out = await sweep_account(db, account_id=acct, user_id=acct)
    assert out["status"] == "skipped_no_corpus", out


@pytest.mark.asyncio
async def test_sweep_account_honours_explicit_week_iso():
    """Caller-supplied `week_iso` (e.g. for a backfill / regenerate
    job) is the value the persisted row carries."""
    from core import db
    acct = "acct-p515-sched-weekiso-" + uuid.uuid4().hex[:8]
    await _ensure_account(db, account_id=acct)
    await _seed_corpus(db, account_id=acct, n_docs=5)
    target = "2026-W01"
    out = await sweep_account(
        db, account_id=acct, user_id=acct, week_iso=target,
    )
    assert out["week_iso"] == target, out
    row = await db.ideas_digests.find_one(
        {"account_id": acct, "week_iso": target}, {"_id": 0, "week_iso": 1},
    )
    assert row is not None and row["week_iso"] == target


# ─── run_weekly_ideas_sweep aggregate ────────────────────────────


@pytest.mark.asyncio
async def test_run_weekly_ideas_sweep_aggregate_counts():
    """End-to-end sweep across multiple accounts — counter shape
    matches what the cron logs. We seed 2 accounts (one with
    corpus, one without) and assert each lands in the right
    persisted state. We DO NOT lean on `summary["sample"]` here
    because the sweep caps it at 50 entries and the live dev Mongo
    has many more accounts than that; we go straight to Mongo
    for ground truth."""
    from core import db
    acct_active = "acct-p515-sched-active-" + uuid.uuid4().hex[:6]
    acct_dormant = "acct-p515-sched-dormant-" + uuid.uuid4().hex[:6]
    await _ensure_account(db, account_id=acct_active)
    await _ensure_account(db, account_id=acct_dormant)
    await _seed_corpus(db, account_id=acct_active, n_docs=5)

    summary = await run_weekly_ideas_sweep(db)
    counters = summary["counters"]
    assert counters["scanned"] >= 2, counters
    # Counter shape sanity — at minimum, the active tenant generated
    # (or already existed from a prior test run) and the dormant
    # tenant skipped.
    assert (counters.get("generated", 0) + counters.get("exists", 0)) >= 1, counters
    assert counters.get("skipped_no_corpus", 0) >= 1, counters

    # Persisted-row ground truth.
    week = summary["week_iso"]
    active_row = await db.ideas_digests.find_one(
        {"account_id": acct_active, "week_iso": week},
        {"_id": 0, "cards": 1, "account_id": 1},
    )
    assert active_row is not None and len(active_row["cards"]) == 4
    dormant_count = await db.ideas_digests.count_documents(
        {"account_id": acct_dormant, "week_iso": week},
    )
    assert dormant_count == 0, "dormant tenant must not write a digest"


# ─── Env disable + scheduler boundary ────────────────────────────


def test_is_scheduler_disabled_default_false(monkeypatch):
    monkeypatch.delenv("IDEAS_SCHEDULER_DISABLED", raising=False)
    assert is_scheduler_disabled() is False


def test_is_scheduler_disabled_true_when_env_set(monkeypatch):
    monkeypatch.setenv("IDEAS_SCHEDULER_DISABLED", "true")
    assert is_scheduler_disabled() is True


def test_week_iso_for_isocalendar_round_trip():
    """A date in week 8 of 2026 must round-trip to `2026-W08`. Lock
    the leading-zero padding (the spec ISO 8601 form)."""
    assert week_iso_for(datetime(2026, 2, 17, tzinfo=timezone.utc)) == "2026-W08"


# ─── Source-strict server-wiring + voice-lint ────────────────────


def test_scheduler_job_id_registered_in_server():
    """server.py must carry the canonical job id + Monday-07:00 trigger."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert 'id="ideas_weekly_sweep"' in src
    assert 'day_of_week="mon", hour=7, minute=0' in src
    assert "_fire_ideas_weekly_sweep" in src
    assert "run_weekly_ideas_sweep" in src


def test_scheduler_source_voice_lint_clean():
    """Scheduler module must not carry banned customer-copy vocabulary.
    These are the same banned terms as the synthesizer template lock."""
    src = Path("/app/backend/services/ideas_engine/scheduler.py").read_text(encoding="utf-8")
    banned = ["seamless", "AI-powered", "transform", "harness", "leverage"]
    for bad in banned:
        # Case-insensitive substring scan
        assert re.search(re.escape(bad), src, re.IGNORECASE) is None, (
            f"banned vocab {bad!r} in scheduler source"
        )


def test_scheduler_idempotency_marker_in_audit_log():
    """The sweep tags audit-log rows with `trigger="scheduler_weekly"`
    so admin diagnostics can tell scheduler-warmed rows apart from
    lazy-on-GET ones."""
    src = Path("/app/backend/services/ideas_engine/scheduler.py").read_text(encoding="utf-8")
    assert '"trigger": "scheduler_weekly"' in src
