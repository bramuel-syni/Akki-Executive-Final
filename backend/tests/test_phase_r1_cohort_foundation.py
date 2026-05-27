"""Phase R.1 — Founding Cohort foundation CI guards (2026-05-27).

Locks the magic-link issue + consume flow + account schema additions.

Acceptance probes (5):
  (a) curl: admin POST creates an invite → signed URL returned + DB row
  (b) curl: GET /api/auth/magic/{token}?json=1 → 200 with active session
      + cohort_invites row marked consumed + accounts row stamped with
      trial fields + access_token cookie set
  (c) curl: re-fetch same magic link → 410 link_already_used
  (d) curl: tampered/unknown token → 410 link_not_found (per locked
      override to Option B; was 401 invalid_signature pre-playbook)
  (e) curl: admin GET /api/admin/cohort/invites?cohort_tag=… shows the
      consumed invite with consumed_at populated

Negative regressions (3, secret-rotation case dropped per user override):
  N1. Expired token → 410 link_expired
  N2. Non-superadmin POST /api/admin/cohort/invites → 403
  N3. Existing account: consume UPGRADES the row (first_session
      preserved, no JTI revocation, password unchanged)

Plus 1 schema-shape lockdown and 1 atomic-race lockdown:
  L1. sanitize_account() surfaces trial_* + cohort_tag + first_name +
      logo_name + grandfathered_price_locked when present, omits when null.
  L2. Atomic single-use: two concurrent consume calls only one wins;
      loser gets 410 link_already_used.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport


COHORT_TAG = "founding_2026Q2_TEST"


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────
@pytest.fixture
async def superadmin_actor():
    from core import db, hash_password
    uid = f"r1-admin-{uuid.uuid4().hex[:8]}"
    email = f"r1-admin-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "AdminPw!Phase-R1"
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "R1 Admin", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": True, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.accounts.delete_one({"id": uid})
    await db.cohort_invites.delete_many({"issued_by_account_id": uid})


@pytest.fixture
async def non_admin_actor():
    from core import db, hash_password
    uid = f"r1-user-{uuid.uuid4().hex[:8]}"
    email = f"r1-user-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "UserPw!Phase-R1"
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "R1 User", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"uid": uid, "email": email, "password": pw}
    await db.accounts.delete_one({"id": uid})


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def trial_email():
    return f"r1-trial-{uuid.uuid4().hex[:6]}@example.com"


# ─────────────────────────────────────────────────────────────────────
# (a) curl: Admin creates an invite
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_a_admin_issues_invite(superadmin_actor, trial_email):
    from core import db
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        r = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "email":             trial_email,
                "cohort_tag":        COHORT_TAG,
                "trial_length_days": 21,
                "first_name":        "TestExec",
                "logo_name":         "TestCo",
            },
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["invite_id"]
        assert j["magic_link_url"].endswith(f"/api/auth/magic/{j['magic_link_url'].rsplit('/', 1)[-1]}")
        assert "/api/auth/magic/" in j["magic_link_url"]
        assert j["expires_at"]
        # 14-day TTL
        exp = datetime.fromisoformat(j["expires_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_days = (exp - now).total_seconds() / 86400
        assert 13.9 < delta_days < 14.1
        # DB row check
        row = await db.cohort_invites.find_one(
            {"id": j["invite_id"]}, {"_id": 0},
        )
        assert row is not None
        assert row["email"] == trial_email.lower()
        assert row["cohort_tag"] == COHORT_TAG
        assert row["trial_length_days"] == 21
        assert row["first_name"] == "TestExec"
        assert row["logo_name"] == "TestCo"
        assert row["status"] == "pending"
        assert row["consumed_at"] is None
        assert row["consumed_by_account_id"] is None
        assert row["issued_by_account_id"] == superadmin_actor["uid"]


# ─────────────────────────────────────────────────────────────────────
# (b) Magic-link consume (JSON mode for curl-friendliness)
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_b_magic_link_consume_creates_active_trial(superadmin_actor, trial_email):
    from core import db
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        r1 = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": trial_email, "cohort_tag": COHORT_TAG, "first_name": "T", "logo_name": "L"},
        )
        url = r1.json()["magic_link_url"]
        # Hit the consume endpoint with json=1 to suppress the 302
        # (HTTPx test transport doesn't follow cross-origin redirects).
        path = url.split("/api/")[-1]
        consume = await c.get(f"/api/{path}?json=1")
        assert consume.status_code == 200, consume.text
        body = consume.json()
        assert body["ok"] is True
        assert body["trial_status"] == "active_trial"
        assert body["cohort_tag"] == COHORT_TAG
        assert body["access_token"]
        account_id = body["account_id"]

        # cohort_invites row stamped consumed
        inv = await db.cohort_invites.find_one(
            {"id": body["invite_id"]}, {"_id": 0},
        )
        assert inv["status"] == "consumed"
        assert inv["consumed_at"] is not None
        assert inv["consumed_by_account_id"] == account_id

        # accounts row stamped with trial fields + cohort markers
        acc = await db.accounts.find_one(
            {"id": account_id}, {"_id": 0},
        )
        assert acc["trial_status"] == "active_trial"
        assert acc["trial_start_at"]
        assert acc["trial_end_at"]
        assert acc["cohort_tag"] == COHORT_TAG
        assert acc["first_name"] == "T"
        assert acc["logo_name"] == "L"
        assert acc["declared_role"] is None        # Q2 lock
        assert acc["first_session"]["status"] == "intake"  # Q1 lock
        assert acc.get("password_hash") is None  # passwordless
        assert acc.get("grandfathered_price_locked") is False

        # access_token cookie set on the response
        cookies = consume.headers.get_list("set-cookie")
        assert any("access_token=" in ck for ck in cookies), \
            f"access_token cookie must be set on the consume response; got: {cookies}"

        # Cleanup
        await db.accounts.delete_one({"id": account_id})


# ─────────────────────────────────────────────────────────────────────
# (c) Re-use of same magic link → 410 link_already_used
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_c_magic_link_replay_returns_410(superadmin_actor, trial_email):
    from core import db
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        r1 = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": trial_email, "cohort_tag": COHORT_TAG},
        )
        url = r1.json()["magic_link_url"]
        path = url.split("/api/")[-1]

        # First consume — succeeds.
        first = await c.get(f"/api/{path}?json=1")
        assert first.status_code == 200
        account_id = first.json()["account_id"]

        # Second consume — 410 link_already_used.
        second = await c.get(f"/api/{path}?json=1")
        assert second.status_code == 410, second.text
        detail = second.json()["detail"]
        assert detail["error"] == "link_already_used"
        assert detail["invite_id"] == r1.json()["invite_id"]
        assert detail["consumed_at"]

        await db.accounts.delete_one({"id": account_id})


# ─────────────────────────────────────────────────────────────────────
# (d) Tampered / unknown token → 410 link_not_found
# (Per user's Option-B override — was "401 invalid_signature" pre-playbook)
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_d_tampered_token_returns_410_link_not_found(superadmin_actor, trial_email):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        r1 = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": trial_email, "cohort_tag": COHORT_TAG},
        )
        url = r1.json()["magic_link_url"]
        raw_token = url.rsplit("/", 1)[-1]
        # Mutate the last 4 chars — opaque random token won't match DB.
        tampered = raw_token[:-4] + "AAAA"
        bad = await c.get(f"/api/auth/magic/{tampered}?json=1")
        assert bad.status_code == 410, bad.text
        assert bad.json()["detail"]["error"] == "link_not_found"


# ─────────────────────────────────────────────────────────────────────
# (e) Admin list shows consumed invite
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_e_admin_list_shows_consumed_invite(superadmin_actor, trial_email):
    from core import db
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        # Issue + consume
        r1 = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": trial_email, "cohort_tag": COHORT_TAG},
        )
        url = r1.json()["magic_link_url"]
        path = url.split("/api/")[-1]
        consume = await c.get(f"/api/{path}?json=1")
        account_id = consume.json()["account_id"]

        # GET /api/admin/cohort/invites?cohort_tag=…
        lst = await c.get(
            f"/api/admin/cohort/invites?cohort_tag={COHORT_TAG}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert lst.status_code == 200
        items = lst.json()["items"]
        match = next((x for x in items if x["id"] == r1.json()["invite_id"]), None)
        assert match is not None, "the just-consumed invite must appear in the list"
        assert match["status"] == "consumed"
        assert match["consumed_at"] is not None
        assert match["consumed_by_account_id"] == account_id
        # Raw token must NEVER be surfaced on list responses (security).
        assert "magic_link_token" not in match

        # ?status=consumed filter narrows correctly
        filt = await c.get(
            f"/api/admin/cohort/invites?cohort_tag={COHORT_TAG}&status=consumed",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert filt.status_code == 200
        assert any(x["id"] == r1.json()["invite_id"] for x in filt.json()["items"])

        await db.accounts.delete_one({"id": account_id})


# ─────────────────────────────────────────────────────────────────────
# N1. Expired token → 410 link_expired
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_N1_expired_token_returns_410(superadmin_actor, trial_email):
    from core import db
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        r1 = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": trial_email, "cohort_tag": COHORT_TAG},
        )
        # Force-age the row to expired.
        await db.cohort_invites.update_one(
            {"id": r1.json()["invite_id"]},
            {"$set": {"expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}},
        )
        url = r1.json()["magic_link_url"]
        path = url.split("/api/")[-1]
        consume = await c.get(f"/api/{path}?json=1")
        assert consume.status_code == 410
        assert consume.json()["detail"]["error"] == "link_expired"


# ─────────────────────────────────────────────────────────────────────
# N2. Non-superadmin → 403 on POST /invites
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_N2_non_superadmin_cannot_issue_invite(non_admin_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, non_admin_actor["email"], non_admin_actor["password"])
        r = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": "ignored@x.com", "cohort_tag": COHORT_TAG},
        )
        assert r.status_code == 403, r.text
        # Also list endpoint
        r2 = await c.get(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r2.status_code == 403


# ─────────────────────────────────────────────────────────────────────
# N3. Existing-account upgrade preserves first_session + does not bump
#     sessions_revoked_after + does not touch password_hash
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_N3_existing_account_upgrade_preserves_state(superadmin_actor):
    from core import db, hash_password
    from server import app  # noqa: F401
    pre_email = f"r1-existing-{uuid.uuid4().hex[:6]}@example.com"
    pre_pw_hash = hash_password("OriginalPw!9876")
    pre_uid = uuid.uuid4().hex
    await db.accounts.insert_one({
        "id": pre_uid, "email": pre_email,
        "password_hash": pre_pw_hash,
        "name": "Pre-Existing User",
        "declared_role": "ned",
        "is_superadmin": False,
        "first_session": {"status": "done"},   # already onboarded
        "preferences": {"theme": "dark"},
        "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
            r1 = await c.post(
                "/api/admin/cohort/invites?send=0",
                headers={"Authorization": f"Bearer {tok}"},
                json={"email": pre_email, "cohort_tag": COHORT_TAG,
                      "first_name": "FromInvite", "logo_name": "FromInvite Co"},
            )
            url = r1.json()["magic_link_url"]
            path = url.split("/api/")[-1]
            consume = await c.get(f"/api/{path}?json=1")
            assert consume.status_code == 200
            assert consume.json()["account_id"] == pre_uid, \
                "Upgrade must reuse the existing account_id, not create a new one"

            # Re-read the account
            acc = await db.accounts.find_one({"id": pre_uid}, {"_id": 0})
            assert acc["password_hash"] == pre_pw_hash, "Password hash MUST be preserved"
            assert acc["declared_role"] == "ned", "Existing role MUST be preserved"
            assert acc["first_session"]["status"] == "done", \
                "Existing first_session.status MUST NOT be reset to intake"
            assert acc["preferences"] == {"theme": "dark"}, \
                "Existing preferences MUST be preserved"
            # Trial fields stamped
            assert acc["trial_status"] == "active_trial"
            assert acc["cohort_tag"] == COHORT_TAG
            assert acc["first_name"] == "FromInvite"
            assert acc["logo_name"] == "FromInvite Co"
            # No sessions_revoked_after bump (Phase J kill-switch untouched)
            assert "sessions_revoked_after" not in acc or acc.get("sessions_revoked_after") is None
    finally:
        await db.accounts.delete_one({"id": pre_uid})


# ─────────────────────────────────────────────────────────────────────
# L1. sanitize_account() schema-shape lockdown
# ─────────────────────────────────────────────────────────────────────
def test_r1_L1_sanitize_account_surfaces_cohort_fields_when_set():
    from core import sanitize_account
    a = {
        "id": "x", "email": "x@x.com", "name": "X",
        "declared_role": "executive",
        "trial_status": "active_trial",
        "trial_start_at": "2026-01-01T00:00:00+00:00",
        "trial_end_at": "2026-01-22T00:00:00+00:00",
        "cohort_tag": COHORT_TAG,
        "first_name": "X", "logo_name": "XCo",
        "grandfathered_price_locked": False,
    }
    out = sanitize_account(a)
    assert out["trial_status"] == "active_trial"
    assert out["cohort_tag"] == COHORT_TAG
    assert out["first_name"] == "X"
    assert out["logo_name"] == "XCo"
    assert out["grandfathered_price_locked"] is False
    # Password hash never surfaces
    assert "password_hash" not in out


def test_r1_L1_sanitize_account_omits_cohort_fields_when_null():
    from core import sanitize_account
    a = {"id": "x", "email": "x@x.com", "name": "X", "declared_role": "executive"}
    out = sanitize_account(a)
    # None of the cohort markers should appear for a non-cohort account
    for k in ("trial_status", "trial_start_at", "trial_end_at",
              "cohort_tag", "first_name", "logo_name"):
        assert k not in out, f"non-cohort account should not surface {k}"


# ─────────────────────────────────────────────────────────────────────
# L2. Atomic single-use: concurrent consume → only one wins
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_r1_L2_concurrent_consume_only_one_wins(superadmin_actor, trial_email):
    from core import db
    from server import app  # noqa: F401
    # Reset the in-memory rate limiter so prior tests' consume calls
    # don't push us past the per-IP threshold on the 4 concurrent fires.
    from routers.auth_magic import _recent
    _recent.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login(c, superadmin_actor["email"], superadmin_actor["password"])
        r1 = await c.post(
            "/api/admin/cohort/invites?send=0",
            headers={"Authorization": f"Bearer {tok}"},
            json={"email": trial_email, "cohort_tag": COHORT_TAG},
        )
        url = r1.json()["magic_link_url"]
        path = url.split("/api/")[-1]

        # Fire 4 concurrent consume calls. Atomic find_one_and_update
        # guarantees exactly ONE succeeds with 200; the rest return 410.
        responses = await asyncio.gather(*[
            c.get(f"/api/{path}?json=1") for _ in range(4)
        ])
        statuses = sorted(r.status_code for r in responses)
        assert statuses.count(200) == 1, (
            f"Exactly one concurrent request must succeed; got status codes {statuses}"
        )
        assert statuses.count(410) == 3, (
            f"All other concurrent requests must 410; got {statuses}"
        )
        # Verify the consumed account
        winner = next(r for r in responses if r.status_code == 200)
        await db.accounts.delete_one({"id": winner.json()["account_id"]})
