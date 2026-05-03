"""Phase 13.2 — `/api/contexts/{cid}/cycle/actions` aggregator tests.

Asserts the three-source aggregation:
  1. signal_actions  — `action_type == "acted"` rows feed the
                       Signal Actions section.
  2. plays           — instances with `status ∈ {active, paused}` feed
                       the In-Flight Plays section.
  3. checklists      — `status ∈ {pending_approval, dispatched}` feed
                       the Pending Submissions section.

The endpoint is read-only and is the data backbone of the new
`ActionsTab.jsx` Cycle Manager surface.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

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


def _run_db(coro_factory):
    """Run a one-shot DB coroutine with a fresh Motor client.

    Same pattern as `test_phase12_2_closeout._run_db` — Motor pins its
    loop on first use, so we open + close a client per call.
    """
    async def _runner():
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = cli[os.environ["DB_NAME"]]
            return await coro_factory(db)
        finally:
            cli.close()
    return asyncio.run(_runner())


def _admin_ctx(admin_session):
    me = admin_session.get(f"{BACKEND}/api/auth/me", timeout=10).json()
    # `/auth/me` returns `{account: {...}, contexts: [...]}` — the
    # canonical place to discover the user's contexts. There is NO
    # `GET /api/contexts` endpoint (contexts are listed inline on /me).
    contexts = me.get("contexts") or []
    if not contexts:
        pytest.skip("admin has no contexts")
    cid = contexts[0].get("id")
    account_id = (me.get("account") or {}).get("id") or me.get("id")
    return cid, account_id


# ---------------------------------------------------------------------------
# Source 1 — signal_actions
# ---------------------------------------------------------------------------
def test_actions_endpoint_surfaces_signal_actions(admin_session):
    cid, aid = _admin_ctx(admin_session)
    sig_id = f"actions-test-sig-{uuid.uuid4().hex[:8]}"
    sa_id = f"actions-test-sa-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    _run_db(lambda db: db.signals.insert_one({
        "id": sig_id, "context_id": cid, "type": "risk",
        "headline": "Test signal — supplier concentration",
        "created_at": now_iso,
    }))
    _run_db(lambda db: db.signal_actions.insert_one({
        "id": sa_id, "signal_id": sig_id, "context_id": cid,
        "account_id": aid, "actor_email": "admin@akki.ai",
        "action_type": "acted",
        "recommendation_label": "Brief the audit chair",
        "created_at": now_iso,
    }))

    try:
        body = admin_session.get(
            f"{BACKEND}/api/contexts/{cid}/cycle/actions", timeout=10,
        ).json()
        sa_items = (body.get("sections") or {}).get("signal_actions") or []
        ours = [it for it in sa_items if it.get("id") == sa_id]
        assert ours, sa_items[:5]
        item = ours[0]
        assert item["status"] == "acted"
        assert item["title"] == "Brief the audit chair"
        assert item["signal_id"] == sig_id
        assert item["href"].startswith("/app/cycle?tab=signals")
        assert sig_id in item["href"]
    finally:
        _run_db(lambda db: db.signals.delete_one({"id": sig_id}))
        _run_db(lambda db: db.signal_actions.delete_one({"id": sa_id}))


# ---------------------------------------------------------------------------
# Source 2 — plays in-flight
# ---------------------------------------------------------------------------
def test_actions_endpoint_surfaces_in_flight_plays(admin_session):
    cid, aid = _admin_ctx(admin_session)
    play_id = f"actions-test-play-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    _run_db(lambda db: db.plays.insert_one({
        "id": play_id, "context_id": cid, "account_id": aid,
        "play_type": "board_pack",
        "title": "Test in-flight play",
        "status": "active",
        "current_stage": 1, "stages": [{}, {}, {}, {}],
        "created_at": now_iso, "last_activity_at": now_iso,
    }))

    try:
        body = admin_session.get(
            f"{BACKEND}/api/contexts/{cid}/cycle/actions", timeout=10,
        ).json()
        plays_items = (body.get("sections") or {}).get("plays") or []
        ours = [it for it in plays_items if it.get("id") == play_id]
        assert ours, plays_items[:5]
        item = ours[0]
        assert item["status"] in {"active", "paused"}
        assert item["title"] == "Test in-flight play"
        assert item["href"] == f"/app/plays/{play_id}"

        # Counts must reflect this row.
        counts = body.get("counts") or {}
        assert counts.get("plays", 0) >= 1, counts
    finally:
        _run_db(lambda db: db.plays.delete_one({"id": play_id}))


# ---------------------------------------------------------------------------
# Source 3 — pending checklists
# ---------------------------------------------------------------------------
def test_actions_endpoint_surfaces_pending_cycle_submissions(admin_session):
    cid, _aid = _admin_ctx(admin_session)
    cl_id = f"actions-test-cl-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    _run_db(lambda db: db.checklists.insert_one({
        "id": cl_id, "context_id": cid,
        "cycle_name": "Test cycle",
        "reportee_email": "test-reportee@example.com",
        "reportee_name": "Test Reportee",
        "status": "dispatched",
        "created_at": now_iso,
    }))

    try:
        body = admin_session.get(
            f"{BACKEND}/api/contexts/{cid}/cycle/actions", timeout=10,
        ).json()
        cyc_items = (body.get("sections") or {}).get("cycle_pending") or []
        ours = [it for it in cyc_items if it.get("id") == cl_id]
        assert ours, cyc_items[:5]
        item = ours[0]
        assert item["status"] == "dispatched"
        assert item["owner_email"] == "test-reportee@example.com"
        assert "Test cycle" in item["title"]
        assert "Test Reportee" in item["title"]

        # Once we mark it as responded, it must drop OFF the list.
        _run_db(lambda db: db.checklists.update_one(
            {"id": cl_id},
            {"$set": {"status": "responded"}},
        ))
        body2 = admin_session.get(
            f"{BACKEND}/api/contexts/{cid}/cycle/actions", timeout=10,
        ).json()
        cyc_items2 = (body2.get("sections") or {}).get("cycle_pending") or []
        ours2 = [it for it in cyc_items2 if it.get("id") == cl_id]
        assert not ours2, "responded checklist should no longer surface"
    finally:
        _run_db(lambda db: db.checklists.delete_one({"id": cl_id}))
