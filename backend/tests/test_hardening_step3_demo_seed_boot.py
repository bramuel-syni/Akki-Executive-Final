"""Hardening Step 3 — Demo seeds auto-apply on pod boot.

Spec ref: orchestrator brief 2026-05-25 (post-Step-2 dispatch).
Hooks the seed script into FastAPI's startup chain so fresh
preview / restarted prod pods don't require manual
``python -m scripts.seed_backlog_b_demo``.

Anti-source-string-assertion discipline (closeout §5.8): every
test asserts a CONTROL-FLOW CHAIN — not a literal string match.

  S3.A — After running the startup hook on a clean Mongo, the
         5 seed collections (work_studio_exports, cycles,
         cycle_agendas, objectives, projects) each carry rows
         with ``seed_marker: "DEMO_T5_BACKLOG"``.
  S3.B — Idempotency — calling the hook a SECOND time produces
         delta = 0 across all 5 collections AND post_counts are
         unchanged. The deterministic-id upserts in the seed
         script are the mechanism; the hook just exposes it
         at boot time.
  S3.C — Fail-soft — monkeypatch the seed module's `seed_async`
         to raise, assert the startup hook completes without
         re-raising AND that an operator-readable error log
         line is emitted. The pod MUST remain serving traffic.
  S3.D — Env-var guard — set ``DISABLE_DEMO_SEED=1``, assert
         the hook does NOT call `seed_async` AND emits the
         skip log line. Pin the operator opt-out.
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod  # noqa: E402
import server as server_mod  # noqa: E402

SEED_COLLECTIONS = (
    "work_studio_exports",
    "cycles",
    "cycle_agendas",
    "objectives",
    "projects",
)
SEED_MARKER = "DEMO_T5_BACKLOG"


async def _delete_seed_rows():
    """Helper — purge any existing DEMO_T5_BACKLOG rows from the 5
    seeded collections so subsequent runs exercise the first-write
    branch."""
    for coll in SEED_COLLECTIONS:
        await core_mod.db[coll].delete_many({"seed_marker": SEED_MARKER})


# ── S3.A — first-write branch lands rows in all 5 collections ──────
@pytest.mark.asyncio
async def test_s3_a_startup_hook_seeds_all_five_collections():
    """Anchor chain: clean Mongo (no DEMO_T5_BACKLOG rows) → run
    the startup hook → every one of the 5 spec'd collections has
    at least one row carrying ``seed_marker: "DEMO_T5_BACKLOG"``."""
    await _delete_seed_rows()
    # Run the hook directly — it's the same coroutine FastAPI
    # invokes during startup. The DISABLE_DEMO_SEED env var must
    # NOT be set during this run.
    prior = os.environ.pop("DISABLE_DEMO_SEED", None)
    try:
        await server_mod.on_startup_demo_seed()
    finally:
        if prior is not None:
            os.environ["DISABLE_DEMO_SEED"] = prior
    # Each collection has at least 1 row tagged with the seed marker.
    for coll in SEED_COLLECTIONS:
        n = await core_mod.db[coll].count_documents(
            {"seed_marker": SEED_MARKER},
        )
        assert n >= 1, (
            f"Seed collection `{coll}` has 0 DEMO_T5_BACKLOG rows "
            f"after the startup hook ran. The hook didn't insert "
            f"the spec'd seed pack — `{coll}` is one of the 5 "
            f"required collections."
        )


# ── S3.B — second-call branch produces delta = 0 ───────────────────
@pytest.mark.asyncio
async def test_s3_b_startup_hook_idempotent_on_second_call():
    """Anchor chain: hook has already run (rows present) → run
    again → row counts UNCHANGED across all 5 collections. The
    deterministic-id upserts in the seed script are the
    mechanism the hook leverages."""
    # Ensure prior run already landed rows.
    prior = os.environ.pop("DISABLE_DEMO_SEED", None)
    try:
        await server_mod.on_startup_demo_seed()
        before = {
            coll: await core_mod.db[coll].count_documents({})
            for coll in SEED_COLLECTIONS
        }
        # Second call — delta MUST be 0.
        await server_mod.on_startup_demo_seed()
        after = {
            coll: await core_mod.db[coll].count_documents({})
            for coll in SEED_COLLECTIONS
        }
    finally:
        if prior is not None:
            os.environ["DISABLE_DEMO_SEED"] = prior
    for coll in SEED_COLLECTIONS:
        assert before[coll] == after[coll], (
            f"Idempotency broken in `{coll}`: before={before[coll]}, "
            f"after={after[coll]}. The startup hook re-inserted "
            f"rows that should have been upsert-matched."
        )


# ── S3.C — fail-soft when seed_async raises ────────────────────────
@pytest.mark.asyncio
async def test_s3_c_startup_hook_fails_soft_on_seed_error(monkeypatch, caplog):
    """Anchor chain: monkeypatch the seed module's `seed_async` to
    raise `RuntimeError`, then call the startup hook. THE HOOK MUST
    NOT RE-RAISE. The operator-readable error log line MUST be
    emitted (format: `seed_backlog_b_demo: ERROR — <class> <msg>`)
    so the operator sees the failure without the pod dying."""
    from scripts import seed_backlog_b_demo as _seed_mod

    async def _explode(verbose=False):
        raise RuntimeError("simulated seed failure for fail-soft test")

    monkeypatch.setattr(_seed_mod, "seed_async", _explode)
    prior = os.environ.pop("DISABLE_DEMO_SEED", None)
    caplog.set_level(logging.INFO, logger="akki.startup")
    # The hook MUST NOT raise.
    try:
        await server_mod.on_startup_demo_seed()
    except Exception as e:  # noqa: BLE001
        pytest.fail(
            f"Startup hook re-raised the seed error: {type(e).__name__} "
            f"{e}. Fail-soft contract violated — pod would boot-loop."
        )
    finally:
        if prior is not None:
            os.environ["DISABLE_DEMO_SEED"] = prior
    # Error log was emitted.
    error_records = [
        r for r in caplog.records
        if r.levelno == logging.ERROR
        and "seed_backlog_b_demo: ERROR" in r.getMessage()
    ]
    assert error_records, (
        f"Fail-soft branch ran but no `seed_backlog_b_demo: ERROR` "
        f"log line was emitted. Operator can't see the failure. "
        f"Captured records: {[r.getMessage() for r in caplog.records]}"
    )
    # The exception class name appears in the log line for triage.
    msg = error_records[0].getMessage()
    assert "RuntimeError" in msg, (
        f"Error log line missing the exception class name. "
        f"Got: {msg!r}"
    )


# ── S3.D — DISABLE_DEMO_SEED env-var guard ─────────────────────────
@pytest.mark.asyncio
async def test_s3_d_disable_demo_seed_env_var_skips_hook(monkeypatch, caplog):
    """Anchor chain: set `DISABLE_DEMO_SEED=1` → run the hook →
    the hook DOES NOT call `seed_async` AND emits the
    operator-readable skip line. Pin the opt-out for prod."""
    # Force-reload the seed module so any prior monkeypatch is gone.
    from scripts import seed_backlog_b_demo as _seed_mod
    importlib.reload(_seed_mod)

    called = {"seed_async": False}

    async def _spy(verbose=False):
        called["seed_async"] = True
        return {"delta": {}, "post_counts": {}}

    monkeypatch.setattr(_seed_mod, "seed_async", _spy)
    monkeypatch.setenv("DISABLE_DEMO_SEED", "1")
    caplog.set_level(logging.INFO, logger="akki.startup")
    await server_mod.on_startup_demo_seed()
    # The seed function MUST NOT have been called.
    assert called["seed_async"] is False, (
        "DISABLE_DEMO_SEED=1 should have short-circuited the hook "
        "BEFORE calling seed_async — operator opt-out broken."
    )
    # Skip log emitted with the verbatim prefix.
    skip_msgs = [
        r.getMessage() for r in caplog.records
        if "seed_backlog_b_demo: DISABLE_DEMO_SEED" in r.getMessage()
    ]
    assert skip_msgs, (
        f"Skip log line not emitted when DISABLE_DEMO_SEED=1. "
        f"Captured: {[r.getMessage() for r in caplog.records]}"
    )


# ── S3.E — hook is registered as a FastAPI startup handler ─────────
def test_s3_e_hook_registered_with_fastapi_startup_event():
    """Anchor: the FastAPI `app` MUST have `on_startup_demo_seed`
    registered against the `startup` lifespan. Without registration,
    the hook never fires at boot time and Steps S3.A-D would test
    a code path that never runs in production."""
    handlers = server_mod.app.router.on_startup
    handler_names = [getattr(h, "__name__", "") for h in handlers]
    assert "on_startup_demo_seed" in handler_names, (
        f"`on_startup_demo_seed` not registered as a FastAPI startup "
        f"handler. Registered handlers: {handler_names}"
    )
