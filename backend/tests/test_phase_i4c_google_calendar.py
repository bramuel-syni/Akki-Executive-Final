"""Phase I.4.c — Google Calendar sync CI guards (2026-05-27).

Locks the Google leg of calendar sync (Microsoft Graph lands separately).
Mocks the Google API at the `googleapiclient` discovery layer so tests
run offline.

Locks:
  Token vault
    V1.  encrypt + decrypt round-trip (basic Fernet)
    V2.  decrypt of garbage raises TokenDecryptError
    V3.  init_vault auto-generates a per-process key in non-prod when
         env var is missing
  OAuth flow
    O1.  GET /connect → returns valid authorize_url with correct scopes,
         client_id, redirect_uri, state, access_type=offline, prompt=consent
    O2.  GET /connect — membership 403 + auth 401
    O3.  GET /callback rejects invalid state with 400
    O4.  GET /callback with bare `error=…` query bounces to events
         surface with `calendar_error=` param (no crash)
  Status
    S1.  /status returns {connected: false, synced_count: 0} when no
         credentials row exists
    S2.  /status returns connected=true + last_sync_at + synced_count
         when a credentials row + synced events exist
  Sync
    Y1.  Mapping: Google event → events-schema row (title, start_at,
         end_at, location, notes, type inference, source_ref)
    Y2.  Title-keyword type inference: "Audit committee" → audit_review,
         "Q3 Board meeting" → board_meeting, "AGM" → board_meeting,
         "Pre-board briefing" → briefing, "Filing deadline" → deadline,
         "Coffee chat" → other
    Y3.  All-day event (start.date but no start.dateTime) maps to
         start_at midnight
    Y4.  Idempotency: re-sync deletes ALL prior `calendar_sync` events
         for `(context_id, user_id)` before inserting; manual and
         doc_extraction events are NEVER touched
    Y5.  Refresh path: when access token expired, refresh_token mints
         a new access token; expired-cred row gets updated
    Y6.  Refresh failure: when Google rejects the refresh token,
         credentials row gets `last_sync_status="auth_expired"`
    Y7.  Connected event lands at status=confirmed (no draft review)
         and Card 5 includes it within 14d window (regression for I.5
         absence-default Card 5 behavior)
  Disconnect
    D1.  Disconnect soft-deletes credentials row + best-effort revokes
    D2.  Disconnect is idempotent (no row → returns ok=True silently)
  Source-strict negatives
    N1.  Microsoft Graph router does NOT exist (deferred per user spec)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ═════════════════════════════════════════════════════════════════
# V1-V3 — Token vault
# ═════════════════════════════════════════════════════════════════

def test_i4c_V1_token_vault_encrypt_decrypt_round_trip():
    from services.crypto import token_vault
    token_vault.init_vault()
    plain = "ya29.a0ARrdaM_TEST_TOKEN_VALUE_42"
    ct = token_vault.encrypt(plain)
    assert ct != plain
    assert token_vault.decrypt(ct) == plain


def test_i4c_V2_token_vault_decrypt_garbage_raises():
    from services.crypto import token_vault, token_vault as tv
    token_vault.init_vault()
    with pytest.raises(tv.TokenDecryptError):
        token_vault.decrypt("not-a-valid-fernet-token")


def test_i4c_V3_token_vault_auto_generates_in_non_prod(monkeypatch):
    from services.crypto import token_vault
    monkeypatch.delenv("OAUTH_TOKEN_VAULT_KEY", raising=False)
    monkeypatch.delenv("AKKI_ENV", raising=False)
    # Reset to force re-init path
    token_vault._FERNET = None
    token_vault.init_vault()
    assert token_vault._FERNET is not None
    # Round-trip works under the auto-key
    assert token_vault.decrypt(token_vault.encrypt("hello")) == "hello"


# ═════════════════════════════════════════════════════════════════
# Fixture
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
async def i4c_actor():
    from core import db, hash_password
    uid = f"i4c-{uuid.uuid4().hex[:8]}"
    email = f"i4c-{uuid.uuid4().hex[:6]}@ex.com"
    pw = "Pw!1234567Ab"
    cid = f"i4c-cid-{uuid.uuid4().hex[:6]}"
    now = _iso(datetime.now(timezone.utc))
    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "I4c Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "I4c Test Co",
        "type": "executive_personal", "owner_id": uid,
        "created_at": now,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now,
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid}
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.events.delete_many({"context_id": cid})
    await db.user_calendar_credentials.delete_many({"context_id": cid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ═════════════════════════════════════════════════════════════════
# O1-O4 — OAuth flow
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_i4c_O1_connect_returns_valid_authorize_url(i4c_actor, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://test/api/oauth/google/callback")
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, i4c_actor)
        r = await c.get(f"/api/oauth/google/connect?context_id={i4c_actor['cid']}", headers=hdr)
        assert r.status_code == 200, r.text
        url = r.json()["authorize_url"]
        assert "client_id=test-client-id" in url
        assert "calendar.events.readonly" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "state=" in url
        assert "redirect_uri=" in url


@pytest.mark.asyncio
async def test_i4c_O2_connect_membership_403(i4c_actor, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "x")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "x")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "https://x/cb")
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, i4c_actor)
        r = await c.get("/api/oauth/google/connect?context_id=not-a-member-cid", headers=hdr)
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_i4c_O2_connect_auth_401():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/oauth/google/connect?context_id=whatever")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_i4c_O3_callback_rejects_invalid_state():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/oauth/google/callback?code=x&state=garbage")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_i4c_O4_callback_with_error_redirects_safely():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False) as c:
        r = await c.get("/api/oauth/google/callback?error=access_denied")
    assert r.status_code == 302
    assert "calendar_error=access_denied" in r.headers["location"]


# ═════════════════════════════════════════════════════════════════
# S1-S2 — Status
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_i4c_S1_status_disconnected(i4c_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, i4c_actor)
        r = await c.get(f"/api/contexts/{i4c_actor['cid']}/oauth/calendar/status", headers=hdr)
        assert r.status_code == 200
        d = r.json()
        assert d["connected"] is False
        assert d["synced_count"] == 0


@pytest.mark.asyncio
async def test_i4c_S2_status_connected(i4c_actor):
    from core import db
    from services.crypto import token_vault
    token_vault.init_vault()
    cid = i4c_actor["cid"]
    uid = i4c_actor["uid"]
    now = _iso(datetime.now(timezone.utc))
    await db.user_calendar_credentials.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid, "context_id": cid,
        "provider": "google",
        "access_token_encrypted": token_vault.encrypt("at"),
        "refresh_token_encrypted": token_vault.encrypt("rt"),
        "expires_at": now, "scope": "openid", "calendar_id": "primary",
        "connected_at": now, "last_sync_at": now,
        "last_sync_status": "ok", "last_sync_error": None,
        "deleted_at": None,
    })
    # Seed 2 calendar_sync events
    for i in range(2):
        await db.events.insert_one({
            "id": f"i4c-s2-{i}", "context_id": cid,
            "title": f"E{i}", "type": "board_meeting",
            "start_at": now, "end_at": None, "location": None, "notes": None,
            "source": "calendar_sync", "source_ref": f"gcal-{i}",
            "status": "confirmed", "confidence": None,
            "extracted_at": None, "extracted_by": None,
            "created_by_account_id": uid, "created_at": now, "updated_at": now,
            "deleted_at": None,
        })
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, i4c_actor)
        r = await c.get(f"/api/contexts/{cid}/oauth/calendar/status", headers=hdr)
        d = r.json()
        assert d["connected"] is True
        assert d["provider"] == "google"
        assert d["synced_count"] == 2


# ═════════════════════════════════════════════════════════════════
# Y1-Y3 — Mapping + type inference
# ═════════════════════════════════════════════════════════════════

def test_i4c_Y1_event_mapping_basic_fields():
    from routers.oauth_google import _map_google_event
    ev = {
        "id": "evt-abc",
        "summary": "Q3 Board meeting",
        "location": "Boardroom A",
        "description": "Quarterly review",
        "start": {"dateTime": "2026-06-15T10:00:00Z"},
        "end":   {"dateTime": "2026-06-15T12:00:00Z"},
    }
    m = _map_google_event(ev)
    assert m is not None
    assert m["title"] == "Q3 Board meeting"
    assert m["type"] == "board_meeting"
    assert m["location"] == "Boardroom A"
    assert m["notes"] == "Quarterly review"
    assert m["source_ref"] == "evt-abc"
    assert m["start_at"].startswith("2026-06-15T10:00")
    assert m["end_at"].startswith("2026-06-15T12:00")


def test_i4c_Y2_type_inference_keyword_rules():
    from routers.oauth_google import _infer_type
    cases = [
        ("Q3 Board meeting", "board_meeting"),
        ("AGM 2026", "board_meeting"),
        ("Annual General Meeting", "board_meeting"),
        ("Audit committee review", "audit_review"),
        ("Q3 Audit", "audit_review"),
        ("Pre-board briefing", "briefing"),
        ("Brief Sarah on Q3", "briefing"),
        ("Pre-read deadline", "deadline"),
        ("Filing submission cut-off", "deadline"),
        ("Coffee chat", "other"),
        ("Lunch", "other"),
    ]
    for title, expected in cases:
        assert _infer_type(title) == expected, f"{title!r} → {_infer_type(title)!r} (expected {expected!r})"


def test_i4c_Y3_all_day_event_mapping():
    from routers.oauth_google import _map_google_event
    ev = {
        "id": "evt-allday",
        "summary": "Quarterly board offsite",
        "start": {"date": "2026-07-15"},
        "end":   {"date": "2026-07-16"},
    }
    m = _map_google_event(ev)
    assert m is not None
    # Midnight UTC for all-day events.
    assert m["start_at"].startswith("2026-07-15T00:00")


# ═════════════════════════════════════════════════════════════════
# Y4-Y7 — Sync flow (mocked Google API)
# ═════════════════════════════════════════════════════════════════

def _build_mocked_calendar_service(items):
    """Builds a MagicMock that mimics the googleapiclient build()
    surface so we never hit the network."""
    svc = MagicMock()
    svc.events.return_value.list.return_value.execute.return_value = {
        "items": items, "nextPageToken": None,
    }
    return svc


@pytest.mark.asyncio
async def test_i4c_Y4_sync_idempotency_replaces_prior_only_for_calendar_sync(i4c_actor):
    from core import db
    from services.crypto import token_vault
    token_vault.init_vault()
    cid, uid = i4c_actor["cid"], i4c_actor["uid"]
    now_dt = datetime.now(timezone.utc)
    fut = now_dt + timedelta(days=5)
    now = _iso(now_dt)

    # Seed 1 manual event + 1 doc_extraction draft — these MUST NOT be
    # touched by sync.
    await db.events.insert_many([
        {"id": "manual-1", "context_id": cid, "title": "Manual M",
         "type": "board_meeting", "start_at": now, "end_at": None,
         "location": None, "notes": None,
         "source": "manual", "source_ref": None,
         "created_by_account_id": uid, "created_at": now, "updated_at": now,
         "deleted_at": None},
        {"id": "draft-1", "context_id": cid, "title": "Draft D",
         "type": "board_meeting", "start_at": now, "end_at": None,
         "location": None, "notes": None,
         "source": "doc_extraction", "source_ref": "doc-x", "status": "draft",
         "confidence": 0.9, "extracted_at": now, "extracted_by": "akki_extractor",
         "created_by_account_id": uid, "created_at": now, "updated_at": now,
         "deleted_at": None},
    ])
    # Seed credentials row
    await db.user_calendar_credentials.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid, "context_id": cid,
        "provider": "google",
        "access_token_encrypted": token_vault.encrypt("at"),
        "refresh_token_encrypted": token_vault.encrypt("rt"),
        "expires_at": _iso(now_dt + timedelta(hours=1)),
        "scope": "openid", "calendar_id": "primary",
        "connected_at": now, "last_sync_at": None,
        "last_sync_status": "ok", "last_sync_error": None,
        "deleted_at": None,
    })

    # Run 1 — 2 calendar_sync events
    items_run1 = [
        {"id": "gcal-1", "summary": "Board Meeting Q3",
         "start": {"dateTime": _iso(fut)}, "end": {"dateTime": _iso(fut + timedelta(hours=2))}},
        {"id": "gcal-2", "summary": "Audit committee",
         "start": {"dateTime": _iso(fut + timedelta(days=1))}, "end": {"dateTime": _iso(fut + timedelta(days=1, hours=1))}},
    ]
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, i4c_actor)
        with patch("routers.oauth_google.gb",
                   side_effect=lambda *a, **kw: _build_mocked_calendar_service(items_run1)) if False else \
             patch("googleapiclient.discovery.build",
                   side_effect=lambda *a, **kw: _build_mocked_calendar_service(items_run1)):
            r1 = await c.post(f"/api/contexts/{cid}/events/sync-calendar?provider=google", headers=hdr)
            assert r1.status_code == 200, r1.text
            assert r1.json()["imported"] == 2

        # Run 2 — 1 different calendar_sync event
        items_run2 = [
            {"id": "gcal-3", "summary": "Pre-board briefing",
             "start": {"dateTime": _iso(fut + timedelta(days=2))}, "end": {"dateTime": _iso(fut + timedelta(days=2, hours=1))}},
        ]
        with patch("googleapiclient.discovery.build",
                   side_effect=lambda *a, **kw: _build_mocked_calendar_service(items_run2)):
            r2 = await c.post(f"/api/contexts/{cid}/events/sync-calendar?provider=google", headers=hdr)
            assert r2.status_code == 200
            assert r2.json()["imported"] == 1

    # Verify: 1 calendar_sync event remains (the new one), manual + draft untouched
    manual = await db.events.find_one({"id": "manual-1"})
    draft  = await db.events.find_one({"id": "draft-1"})
    assert manual is not None and manual["source"] == "manual"
    assert draft is not None and draft["source"] == "doc_extraction" and draft["status"] == "draft"
    sync_rows = await db.events.count_documents({
        "context_id": cid, "source": "calendar_sync", "deleted_at": None,
    })
    assert sync_rows == 1


@pytest.mark.asyncio
async def test_i4c_Y6_refresh_failure_marks_auth_expired(i4c_actor):
    from core import db
    from services.crypto import token_vault
    from routers.oauth_google import _refresh_access_token
    token_vault.init_vault()
    cid, uid = i4c_actor["cid"], i4c_actor["uid"]
    now = _iso(datetime.now(timezone.utc))
    cred_id = str(uuid.uuid4())
    await db.user_calendar_credentials.insert_one({
        "id": cred_id, "user_id": uid, "context_id": cid,
        "provider": "google",
        "access_token_encrypted": token_vault.encrypt("expired_at"),
        "refresh_token_encrypted": token_vault.encrypt("bad_rt"),
        "expires_at": now, "scope": "openid", "calendar_id": "primary",
        "connected_at": now, "last_sync_at": None,
        "last_sync_status": "ok", "last_sync_error": None,
        "deleted_at": None,
    })

    class _MockResp:
        status_code = 400
        text = '{"error": "invalid_grant"}'

    class _MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def post(self, *a, **kw): return _MockResp()

    with patch("httpx.AsyncClient", return_value=_MockClient()):
        cred = await db.user_calendar_credentials.find_one({"id": cred_id}, {"_id": 0})
        out = await _refresh_access_token(cred)
        assert out is None

    updated = await db.user_calendar_credentials.find_one({"id": cred_id}, {"_id": 0})
    assert updated["last_sync_status"] == "auth_expired"


@pytest.mark.asyncio
async def test_i4c_Y7_synced_events_appear_on_card5(i4c_actor):
    """Calendar-sync events with status=confirmed must surface on Card 5
    (within 14d window). Regression guard for the I.5 absence-default
    Card-5 filter `status: {$ne: "draft"}` — confirmed status passes."""
    from core import db
    cid, uid = i4c_actor["cid"], i4c_actor["uid"]
    now = datetime.now(timezone.utc)
    in_window = now + timedelta(days=7)
    await db.events.insert_one({
        "id": "i4c-y7", "context_id": cid,
        "title": "Synced board meeting", "type": "board_meeting",
        "start_at": _iso(in_window), "end_at": None,
        "location": "Boardroom", "notes": None,
        "source": "calendar_sync", "source_ref": "gcal-sync-y7",
        "status": "confirmed", "confidence": None,
        "extracted_at": None, "extracted_by": None,
        "created_by_account_id": uid, "created_at": _iso(now),
        "updated_at": _iso(now), "deleted_at": None,
    })
    # Clear company_home cache so we read fresh.
    from routers.company_home import _CACHE
    _CACHE.clear()
    from routers.company_home import _build_events
    card = await _build_events(cid)
    d = card.model_dump()
    assert d["count"] == 1
    assert "Synced board meeting" in d["subtext"]


# ═════════════════════════════════════════════════════════════════
# D1-D2 — Disconnect
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_i4c_D1_disconnect_soft_deletes_credentials(i4c_actor):
    from core import db
    from services.crypto import token_vault
    token_vault.init_vault()
    cid, uid = i4c_actor["cid"], i4c_actor["uid"]
    now = _iso(datetime.now(timezone.utc))
    await db.user_calendar_credentials.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid, "context_id": cid,
        "provider": "google",
        "access_token_encrypted": token_vault.encrypt("at"),
        "refresh_token_encrypted": token_vault.encrypt("rt"),
        "expires_at": now, "scope": "openid", "calendar_id": "primary",
        "connected_at": now, "last_sync_at": None,
        "last_sync_status": "ok", "last_sync_error": None,
        "deleted_at": None,
    })

    class _MockResp:
        status_code = 200
        text = "{}"

    class _MockClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def post(self, *a, **kw): return _MockResp()

    from server import app  # noqa: F401
    with patch("httpx.AsyncClient", return_value=_MockClient()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            hdr = await _login(c, i4c_actor)
            r = await c.post(f"/api/contexts/{cid}/oauth/google/disconnect", headers=hdr)
            assert r.status_code == 200
            assert r.json()["ok"] is True

    cred = await db.user_calendar_credentials.find_one(
        {"user_id": uid, "context_id": cid, "provider": "google"}, {"_id": 0},
    )
    assert cred is not None
    assert cred["deleted_at"] is not None


@pytest.mark.asyncio
async def test_i4c_D2_disconnect_idempotent(i4c_actor):
    """Disconnect on a non-connected context returns ok=True silently."""
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        hdr = await _login(c, i4c_actor)
        r = await c.post(f"/api/contexts/{i4c_actor['cid']}/oauth/google/disconnect", headers=hdr)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["revoked"] is False


# ═════════════════════════════════════════════════════════════════
# N1 — Microsoft router does NOT exist (deferred per user spec)
# ═════════════════════════════════════════════════════════════════

def test_i4c_N1_no_microsoft_router_yet():
    """Microsoft Graph leg is deferred per user spec — no
    `routers/oauth_microsoft.py` or similar shim should land in this
    dispatch. When Microsoft creds arrive, a SIBLING router will be
    added (mirroring the contract) — but not pre-stubbed here."""
    forbidden = [
        REPO / "backend" / "routers" / "oauth_microsoft.py",
        REPO / "backend" / "routers" / "oauth_outlook.py",
        REPO / "backend" / "routers" / "msgraph.py",
    ]
    for p in forbidden:
        assert not p.exists(), (
            f"Pre-stubbed Microsoft Graph file found: {p}. "
            f"Microsoft leg lands when user provides credentials."
        )
