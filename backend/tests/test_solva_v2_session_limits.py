"""Phase 15.3 — session-limit integration tests (decision #11).

Requires the live backend (uses existing pytest pattern: requests against
http://localhost:8001). Asserts:
  * 3-concurrent-active limit at session create time → 422
  * 20-turn-per-session ceiling → 422
  * Stale-session cron sweep marks idle sessions abandoned

We do NOT exercise the LLM here — for the 20-turn path we patch the
sessions collection directly to stuff in synthetic turns until we hit
the ceiling. For the concurrent path we just create N sessions back-to-
back without posting turns; the start endpoint checks the count.
"""
import os
import time
import asyncio

import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "http://localhost:8001"
).rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"
CRON_SECRET = os.environ.get("AKKI_CRON_SECRET")


def _login():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ensure_clusters_seeded(headers):
    r = requests.get(f"{BASE_URL}/api/solva/clusters", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    items = r.json().get("clusters") or []
    assert items, "Solve clusters not seeded"
    return items[0]["id"]


def _abandon_all_active(headers):
    """Reset state for the test: abandon every active session this account
    currently has, so we can deterministically check the limit."""
    r = requests.get(
        f"{BASE_URL}/api/solva/v2/sessions",
        params={"status": "active"},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    for s in r.json().get("items") or []:
        requests.post(
            f"{BASE_URL}/api/solva/v2/sessions/{s['id']}/abandon",
            headers=headers, timeout=30,
        )


# -----------------------------------------------------------------------------
# Concurrent active session limit (3)
# -----------------------------------------------------------------------------
@pytest.mark.timeout(180)
def test_concurrent_active_session_limit():
    headers = _login()
    cid = _ensure_clusters_seeded(headers)
    _abandon_all_active(headers)

    intent_text = (
        "Should we restructure the regional commercial team in Q4 given the "
        "softness in EMEA bookings? I want to walk this through diagnosis."
    )
    created_ids = []
    for i in range(3):
        r = requests.post(
            f"{BASE_URL}/api/solva/v2/sessions",
            headers=headers,
            json={"cluster_id": cid, "intent": intent_text, "submodule": "seek_clarity"},
            timeout=180,
        )
        assert r.status_code == 200, f"slot {i} failed: {r.text}"
        created_ids.append(r.json()["id"])

    # 4th must be 422
    r4 = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions",
        headers=headers,
        json={"cluster_id": cid, "intent": intent_text, "submodule": "seek_clarity"},
        timeout=60,
    )
    assert r4.status_code == 422, f"expected 422 on 4th, got {r4.status_code}: {r4.text}"
    detail = r4.json().get("detail")
    assert detail and isinstance(detail, dict)
    assert detail.get("error") == "too_many_active_sessions"
    assert detail.get("limit") == 3

    # Cleanup
    for sid in created_ids:
        requests.post(
            f"{BASE_URL}/api/solva/v2/sessions/{sid}/abandon",
            headers=headers, timeout=30,
        )


# -----------------------------------------------------------------------------
# 20-turn ceiling — direct DB stuffing of synthetic user turns
# -----------------------------------------------------------------------------
@pytest.mark.timeout(180)
@pytest.mark.asyncio
async def test_max_turns_per_session_returns_422():
    headers = _login()
    cid = _ensure_clusters_seeded(headers)
    _abandon_all_active(headers)

    intent_text = (
        "We have a regulatory letter on our AI vendor governance. Let's "
        "diagnose the gap and identify the first three actions."
    )
    r = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions",
        headers=headers,
        json={"cluster_id": cid, "intent": intent_text, "submodule": "seek_clarity"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # Use the same Mongo handle the backend uses, via core.db.
    from core import db
    synthetic_turns = [
        {
            "id": f"synthetic-{i}",
            "role": "user",
            "layer": "framing",
            "text": "synthetic ceiling test",
            "model": None,
            "tier": None,
            "created_at": "2026-01-01T00:00:00Z",
        }
        for i in range(20)
    ]
    res = await db.solva_v2_sessions.update_one(
        {"id": sid},
        {"$set": {"turns": synthetic_turns}},
    )
    assert res.modified_count == 1

    # Now POST /turn must 422 with the limit error.
    r2 = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions/{sid}/turn",
        headers=headers,
        json={"user_text": "any text"},
        timeout=60,
    )
    assert r2.status_code == 422, f"expected 422, got {r2.status_code}: {r2.text}"
    detail = r2.json().get("detail")
    assert isinstance(detail, dict) and detail.get("error") == "session_turn_limit"
    assert detail.get("limit") == 20

    requests.post(
        f"{BASE_URL}/api/solva/v2/sessions/{sid}/abandon",
        headers=headers, timeout=30,
    )


# -----------------------------------------------------------------------------
# Stale-session cron sweep
# -----------------------------------------------------------------------------
@pytest.mark.timeout(60)
@pytest.mark.skipif(not CRON_SECRET, reason="AKKI_CRON_SECRET not set")
@pytest.mark.asyncio
async def test_stale_session_cron_marks_old_active_abandoned():
    headers = _login()
    cid = _ensure_clusters_seeded(headers)
    _abandon_all_active(headers)

    intent_text = (
        "Quick one — should we change the audit-committee chair given the "
        "succession plan? Diagnose the trade-offs."
    )
    r = requests.post(
        f"{BASE_URL}/api/solva/v2/sessions",
        headers=headers,
        json={"cluster_id": cid, "intent": intent_text, "submodule": "seek_clarity"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # Stuff the updated_at way into the past so the cron marks it abandoned.
    from core import db
    long_ago = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
    await db.solva_v2_sessions.update_one(
        {"id": sid},
        {"$set": {"updated_at": long_ago, "status": "active"}},
    )

    # Fire the cron with the secret.
    r2 = requests.post(
        f"{BASE_URL}/api/solva/v2/cron/stale-session-sweep",
        headers={"X-Cron-Secret": CRON_SECRET},
        timeout=60,
    )
    assert r2.status_code == 200, f"cron failed: {r2.status_code}: {r2.text}"
    body = r2.json()
    assert body["modified"] >= 1, f"cron didn't sweep: {body}"

    # The session is now abandoned.
    rec = await db.solva_v2_sessions.find_one({"id": sid}, {"_id": 0, "status": 1, "abandoned_reason": 1})
    assert rec["status"] == "abandoned"
    assert rec["abandoned_reason"] == "stale_30d"


# -----------------------------------------------------------------------------
# Cron rejects without the secret
# -----------------------------------------------------------------------------
def test_stale_session_cron_requires_secret():
    r = requests.post(
        f"{BASE_URL}/api/solva/v2/cron/stale-session-sweep",
        headers={"X-Cron-Secret": "wrong-value"},
        timeout=30,
    )
    assert r.status_code == 403


def test_stale_session_cron_rejects_when_no_secret_set_or_wrong():
    """Defence in depth: secret missing entirely also returns 403."""
    r = requests.post(
        f"{BASE_URL}/api/solva/v2/cron/stale-session-sweep",
        timeout=30,
    )
    assert r.status_code == 403
