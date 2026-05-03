"""Phase 12.2 closeout — regression tests for the three production bugs.

BUG 1 — governance synisense rollup must include account-scoped runs.
BUG 2 — first-accept must persist `synisense_version >= 1`.
BUG 3 — chat synisense_stats.version must be threaded from the engine.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

BACKEND = os.environ.get("AKKI_BACKEND_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.session()
    r = s.post(
        f"{BACKEND}/api/auth/login",
        json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        pytest.skip("login did not return access_token")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _run_async(coro):
    """Run an async helper inside its own loop. Each call gets a fresh
    Motor client so the loop binding is correct (Motor caches the loop
    on first use, so reusing across asyncio.run() calls fails)."""
    return asyncio.run(coro)


def _get_db():
    """Return a fresh Motor client + db. Call this inside an async
    helper that's run with asyncio.run() so the loop binding is right."""
    from motor.motor_asyncio import AsyncIOMotorClient
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ["DB_NAME"]]


# ---------------------------------------------------------------------------
# BUG 1 — governance rollup now reads account-scoped + context-scoped runs
# ---------------------------------------------------------------------------
def test_governance_rollup_picks_up_synthetic_run(admin_session, db):
    """Write a synthetic synisense_runs row with a known span shape and
    timestamp, then verify the governance synisense block reflects it.

    The user's BUG 1 was that ungrounded chat runs (with empty
    context_id) were never reflected in the rollup. The fix is an
    `$or` on context_id ∈ ctx_ids OR account_id == current.id.
    """
    # Get the admin account_id.
    me = admin_session.get(f"{BACKEND}/api/auth/me", timeout=10).json()
    account_id = me["id"]

    # Pick the account's first context for the test row.
    contexts = admin_session.get(f"{BACKEND}/api/contexts", timeout=10).json()
    ctx_id = (contexts.get("items") or contexts or [{}])[0].get("id") if isinstance(contexts, dict) else (contexts or [{}])[0].get("id")
    if not ctx_id:
        ctx_id = ""  # fall through to ungrounded test

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    synthetic_id = f"closeout-bug1-{uuid.uuid4().hex[:8]}"
    asyncio.run(db.synisense_runs.insert_one({
        "id": synthetic_id,
        "context_id": ctx_id,
        "surface": "chat",
        "mode": "redact",
        "ts": now,
        "account_id": account_id,
        "input_sha256": "test" * 16,
        "spans": [
            {"start": 0, "end": 5, "entity_type": "EMAIL_ADDRESS",
             "source": "regex", "confidence": 1.0},
            {"start": 6, "end": 12, "entity_type": "DEAL_CODENAME",
             "source": "presidio", "confidence": 0.85},
        ],
        "stats": {"elapsed_ms": 5, "regex_hits": 1, "presidio_hits": 1,
                  "llm_hits": 0, "llm_calls": 0},
        "shield_map_id": None,
        "synisense_version": "12.1.0",
    }))

    try:
        body = admin_session.get(f"{BACKEND}/api/me/governance", timeout=10).json()
        syn = body.get("synisense", {})
        # The brief's acceptance criteria.
        assert syn.get("active") is True, syn
        assert syn.get("last_run_at"), syn
        assert syn.get("spans_redacted_7d", 0) >= 2, syn
        assert "EMAIL_ADDRESS" in syn.get("entity_histogram_7d", {}), syn
        assert "DEAL_CODENAME" in syn.get("entity_histogram_7d", {}), syn
    finally:
        asyncio.run(db.synisense_runs.delete_one({"id": synthetic_id}))


def test_governance_rollup_picks_up_ungrounded_chat_run(admin_session, db):
    """Variant of BUG 1: explicitly insert a row with empty context_id
    (the ungrounded-chat case the original filter missed) and assert
    it's still reflected via the account_id $or branch."""
    me = admin_session.get(f"{BACKEND}/api/auth/me", timeout=10).json()
    account_id = me["id"]
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    synthetic_id = f"closeout-bug1-ungrounded-{uuid.uuid4().hex[:8]}"
    asyncio.run(db.synisense_runs.insert_one({
        "id": synthetic_id,
        "context_id": "",  # the precise shape that triggered the bug
        "surface": "chat",
        "mode": "redact",
        "ts": now,
        "account_id": account_id,
        "input_sha256": "x" * 64,
        "spans": [{"start": 0, "end": 5, "entity_type": "PHONE_NUMBER",
                   "source": "regex", "confidence": 1.0}],
        "stats": {"elapsed_ms": 3, "regex_hits": 1, "presidio_hits": 0,
                  "llm_hits": 0, "llm_calls": 0},
        "shield_map_id": None,
    }))
    try:
        syn = admin_session.get(f"{BACKEND}/api/me/governance", timeout=10).json().get("synisense", {})
        assert "PHONE_NUMBER" in syn.get("entity_histogram_7d", {}), syn
    finally:
        asyncio.run(db.synisense_runs.delete_one({"id": synthetic_id}))


# ---------------------------------------------------------------------------
# BUG 2 — first-accept persists synisense_version
# ---------------------------------------------------------------------------
def test_synisense_accept_persists_version(admin_session, db):
    """Pick any briefing the admin owns (post-backfill they all have
    body_redacted), call /synisense-accept, then re-fetch and assert
    `synisense_version >= 1` is present."""
    cur = db.briefings.find({}, {"_id": 0, "id": 1, "context_id": 1}).limit(1)
    rows = asyncio.run(cur.to_list(1))
    if not rows:
        pytest.skip("no briefings seeded — backfill should have populated some")
    target = rows[0]
    aid = target["id"]
    # context_id not needed for this test — the studio routes resolve
    # the artefact directly by id under the user's accessible contexts.

    # Touch an existing block so the save path runs and Synisense fires.
    blocks_now = admin_session.get(
        f"{BACKEND}/api/studio/briefing/{aid}/blocks", timeout=10,
    ).json()
    block_list = blocks_now.get("blocks") or []
    if block_list:
        bid = block_list[0]["id"]
        admin_session.patch(
            f"{BACKEND}/api/studio/briefing/{aid}/blocks/{bid}",
            json={"content": block_list[0].get("content") or {"text": "Refreshed"}},
            timeout=30,
        )

    # Now hit /synisense-accept.
    r = admin_session.post(
        f"{BACKEND}/api/studio/briefing/{aid}/synisense-accept", timeout=10,
    )
    assert r.status_code == 200, r.text[:300]
    accept_body = r.json()
    assert accept_body["ok"] is True
    assert accept_body.get("synisense_first_accept_at")

    # Re-fetch the artefact and assert version is set.
    art = asyncio.run(db.briefings.find_one({"id": aid}, {"_id": 0, "synisense_version": 1, "synisense_first_accept_at": 1}))
    assert art.get("synisense_version") and int(art["synisense_version"]) >= 1, art
    assert art.get("synisense_first_accept_at"), art


# ---------------------------------------------------------------------------
# BUG 3 — chat synisense_stats.version threaded from the engine
# ---------------------------------------------------------------------------
def test_chat_synisense_stats_version_populated(admin_session):
    chat = admin_session.post(
        f"{BACKEND}/api/chats",
        json={"title": "closeout bug3", "model_id": "claude-sonnet-4-5"},
        timeout=10,
    ).json()
    cid = chat["id"]
    msg = admin_session.post(
        f"{BACKEND}/api/chats/{cid}/messages",
        json={"content": "Phone +44 20 7123 4567 about Project Wolf."},
        timeout=60,
    ).json()
    asst_stats = msg.get("assistant_message", {}).get("synisense_stats", {})
    assert asst_stats.get("version"), asst_stats
    # Engine version is the package's `12.1.0`-style string today.
    assert isinstance(asst_stats["version"], str)
    assert "." in asst_stats["version"]
