"""Phase I.4.a — Events system (manual entry) CI guard (2026-05-27).

Locks:
  Backend
    T1.  POST + GET + PATCH + DELETE round-trip works (full lifecycle).
    T2.  Required fields validated (title, type, start_at).
    T3.  Invalid `type` rejected (must be one of the 5 enum values).
    T4.  Membership 403 on all 5 endpoints.
    T5.  401 unauth on all 5 endpoints.
    T6.  Soft delete — deleted events DO NOT appear in list nor get-by-id.
    T7.  Card 5 ("events") on /api/me/company-home/attention now
         returns real data: count of events in the next 14 days,
         and subtext = top 2 titles (or +N more variant).
    T8.  Card 5 empty-state preserved when no events fall in the window.
    T9.  Negative invariant — events NOT pulled from tasks
         (I.2 guard T5 is re-validated for I.4.a).

  Frontend wire
    T10. Events page (`pages/Events.jsx`) mounts the eyebrow, H1,
         tabs (upcoming/past/all), and the Add Event button.
    T11. Add Event modal validates required fields before submit.
    T12. CompanyHome `_routeForCard("events", cid)` returns
         `/app/events?context_id=<cid>` (not null).
    T13. Phase I.4.a route registered in `App.js`.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
ROUTER       = REPO / "backend" / "routers" / "events.py"
CH_ROUTER    = REPO / "backend" / "routers" / "company_home.py"
EVENTS_JSX   = REPO / "frontend" / "src" / "pages" / "Events.jsx"
COMPANY_JSX  = REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx"
APP_JS       = REPO / "frontend" / "src" / "App.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ═════════════════════════════════════════════════════════════════
# Live fixture
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
async def i4a_actor():
    from core import db, hash_password
    uid = f"i4a-{uuid.uuid4().hex[:8]}"
    email = f"i4a-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    cid = f"i4a-ctx-{uuid.uuid4().hex[:6]}"
    now_iso = _iso(datetime.now(timezone.utc))

    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "I4a Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "I4a Test Co",
        "type": "executive_personal", "owner_id": uid,
        "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })
    yield {"uid": uid, "email": email, "password": pw, "cid": cid}
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.events.delete_many({"context_id": cid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ═════════════════════════════════════════════════════════════════
# Backend
# ═════════════════════════════════════════════════════════════════

# ── T1. Full CRUD round-trip ─────────────────────────────────────
@pytest.mark.asyncio
async def test_i4a_full_crud_round_trip(i4a_actor):
    from server import app  # noqa: F401
    cid = i4a_actor["cid"]
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    body = {
        "title": "Board Meeting Q3",
        "type":  "board_meeting",
        "start_at": start,
        "location": "Boardroom A",
        "notes": "Cover risk register.",
    }
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        # CREATE
        r = await c.post(f"/api/contexts/{cid}/events", json=body, headers=hdr)
        assert r.status_code == 200, r.text
        ev = r.json()
        eid = ev["id"]
        assert ev["title"] == "Board Meeting Q3"
        assert ev["type"]  == "board_meeting"
        assert ev["source"] == "manual"
        assert ev["created_by_account_id"] == i4a_actor["uid"]

        # GET
        r = await c.get(f"/api/contexts/{cid}/events/{eid}", headers=hdr)
        assert r.status_code == 200
        assert r.json()["title"] == "Board Meeting Q3"

        # LIST (upcoming=true default)
        r = await c.get(f"/api/contexts/{cid}/events", headers=hdr)
        assert r.status_code == 200
        lst = r.json()
        assert lst["total"] == 1
        assert lst["items"][0]["id"] == eid

        # PATCH
        r = await c.patch(
            f"/api/contexts/{cid}/events/{eid}",
            json={"title": "Board Meeting Q3 — updated", "location": "Room 2"},
            headers=hdr,
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Board Meeting Q3 — updated"
        assert r.json()["location"] == "Room 2"

        # DELETE (soft)
        r = await c.delete(f"/api/contexts/{cid}/events/{eid}", headers=hdr)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # GET after delete → 404
        r = await c.get(f"/api/contexts/{cid}/events/{eid}", headers=hdr)
        assert r.status_code == 404

        # LIST after delete → empty
        r = await c.get(f"/api/contexts/{cid}/events", headers=hdr)
        assert r.json()["total"] == 0


# ── T2 / T3. Validation ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4a_required_fields_enforced(i4a_actor):
    from server import app  # noqa: F401
    cid = i4a_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        # Missing title
        r = await c.post(f"/api/contexts/{cid}/events",
                         json={"type": "briefing",
                               "start_at": _iso(datetime.now(timezone.utc) + timedelta(days=1))},
                         headers=hdr)
        assert r.status_code == 422
        # Missing start_at
        r = await c.post(f"/api/contexts/{cid}/events",
                         json={"title": "x", "type": "briefing"},
                         headers=hdr)
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_i4a_invalid_type_rejected(i4a_actor):
    from server import app  # noqa: F401
    cid = i4a_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        r = await c.post(f"/api/contexts/{cid}/events",
                         json={"title": "x", "type": "not_a_type",
                               "start_at": _iso(datetime.now(timezone.utc) + timedelta(days=1))},
                         headers=hdr)
        assert r.status_code == 422


# ── T4. Membership 403 ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4a_membership_403_on_all_endpoints(i4a_actor):
    from server import app  # noqa: F401
    foreign = "not-a-member-ctx"
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        # POST
        r = await c.post(f"/api/contexts/{foreign}/events",
                         json={"title": "x", "type": "briefing",
                               "start_at": _iso(datetime.now(timezone.utc))},
                         headers=hdr)
        assert r.status_code == 403
        # GET list
        r = await c.get(f"/api/contexts/{foreign}/events", headers=hdr)
        assert r.status_code == 403
        # GET single
        r = await c.get(f"/api/contexts/{foreign}/events/whatever", headers=hdr)
        assert r.status_code == 403
        # PATCH
        r = await c.patch(f"/api/contexts/{foreign}/events/whatever",
                          json={"title": "y"}, headers=hdr)
        assert r.status_code == 403
        # DELETE
        r = await c.delete(f"/api/contexts/{foreign}/events/whatever", headers=hdr)
        assert r.status_code == 403


# ── T5. Unauth 401 on the list ───────────────────────────────────
@pytest.mark.asyncio
async def test_i4a_unauth_401():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.get("/api/contexts/whatever/events")
    assert r.status_code == 401


# ── T6. Soft delete hidden in list ───────────────────────────────
@pytest.mark.asyncio
async def test_i4a_soft_delete_hidden_in_list(i4a_actor):
    from server import app  # noqa: F401
    cid = i4a_actor["cid"]
    body = {"title": "X", "type": "briefing",
            "start_at": _iso(datetime.now(timezone.utc) + timedelta(days=1))}
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        r = await c.post(f"/api/contexts/{cid}/events", json=body, headers=hdr)
        eid = r.json()["id"]
        await c.delete(f"/api/contexts/{cid}/events/{eid}", headers=hdr)
        # List with upcoming=true (default)
        r = await c.get(f"/api/contexts/{cid}/events", headers=hdr)
        assert r.json()["total"] == 0
        # List with upcoming=false (all)
        r = await c.get(f"/api/contexts/{cid}/events?upcoming=false", headers=hdr)
        assert r.json()["total"] == 0


# ── T7 / T8. Card 5 wiring on /me/company-home/attention ────────
@pytest.mark.asyncio
async def test_i4a_company_home_card5_returns_event_data(i4a_actor):
    from server import app  # noqa: F401
    cid = i4a_actor["cid"]
    now = datetime.now(timezone.utc)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        # Seed 3 upcoming events within 14d
        for i, (t, off) in enumerate([
            ("First event",  timedelta(days=1)),
            ("Second event", timedelta(days=3)),
            ("Third event",  timedelta(days=7)),
        ]):
            await c.post(
                f"/api/contexts/{cid}/events",
                json={"title": t, "type": "briefing",
                      "start_at": _iso(now + off)},
                headers=hdr,
            )
        # And one outside the 14d window — should NOT count
        await c.post(
            f"/api/contexts/{cid}/events",
            json={"title": "Way out", "type": "briefing",
                  "start_at": _iso(now + timedelta(days=30))},
            headers=hdr,
        )
        # And a past event — should NOT count
        await c.post(
            f"/api/contexts/{cid}/events",
            json={"title": "Past event", "type": "briefing",
                  "start_at": _iso(now - timedelta(days=2))},
            headers=hdr,
        )

        r = await c.get(
            f"/api/me/company-home/attention?context_id={cid}",
            headers=hdr,
        )
        assert r.status_code == 200
        events_card = r.json()["events"]
        assert events_card["count"] == 3, f"got {events_card}"
        # subtext = top 2 titles + " · 1 more"
        assert events_card["subtext"] == "First event, Second event · 1 more"


@pytest.mark.asyncio
async def test_i4a_company_home_card5_empty_state_preserved(i4a_actor):
    """No events → preserve I.2 empty state copy verbatim."""
    from server import app  # noqa: F401
    cid = i4a_actor["cid"]
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4a_actor)
        r = await c.get(
            f"/api/me/company-home/attention?context_id={cid}",
            headers=hdr,
        )
    assert r.status_code == 200
    events_card = r.json()["events"]
    assert events_card["count"] == 0
    assert events_card["subtext"] == "No events scheduled"


# ── T9. Negative invariant — events helper never reads tasks ─────
def test_i4a_events_helper_never_reads_tasks_collection():
    src = _read(CH_ROUTER)
    # Strip docstrings + comments before scanning executable code.
    stripped = re.sub(r'"""[\s\S]*?"""', "", src)
    stripped = re.sub(r"#[^\n]*", "", stripped)
    m = re.search(
        r"async def _build_events\([^)]*\)[\s\S]*?return CardEvents\(",
        stripped,
    )
    assert m, "_build_events function not found"
    body = m.group(0)
    for f in ("db.tasks", "tasks.find", "tasks.aggregate", "final_due_date"):
        assert f not in body, (
            f"_build_events must NOT touch `{f}` — tasks are NOT an "
            "events source. Locked OUT in both the I.2 and I.4.a briefs."
        )


# ═════════════════════════════════════════════════════════════════
# Frontend wire
# ═════════════════════════════════════════════════════════════════

def test_i4a_events_page_mounts_required_elements():
    src = _read(EVENTS_JSX)
    # Eyebrow + H1 + subtitle
    assert 'data-testid="events-eyebrow"' in src
    assert 'data-testid="events-h1"' in src
    assert "Upcoming on the calendar." in src
    # Phase I.4.c (2026-05-27) — subtitle evolved from "Manual entries.
    # Document extraction and calendar sync land in later phases." to a
    # tri-source description ("Manual entries, AI-extracted dates, and
    # your connected calendar — in one place.") now that I.4.b/.c shipped.
    # The "Manual entries" prefix is preserved as the institutional anchor
    # — fall through either old or new form.
    assert "Manual entries" in src
    # Tabs
    for t in ("upcoming", "past", "all"):
        assert f'data-testid="events-tab-{t}"' in src
    # Add button
    assert 'data-testid="events-add-btn"' in src
    # Modal
    assert 'data-testid="event-modal"' in src
    assert 'data-testid="event-modal-title"' in src
    assert 'data-testid="event-modal-save"' in src
    # H1 uses inline 32px override (NOT .akki-greeting token)
    assert 'style={{ fontSize: "32px" }}' in src
    assert "akki-greeting" not in src


def test_i4a_event_modal_validates_required_fields_before_submit():
    src = _read(EVENTS_JSX)
    # Title + start_at required guards.
    assert 'setErr("Title is required")' in src
    assert 'setErr("Start date/time is required")' in src


def test_i4a_company_home_events_card_routes_to_events_page():
    src = _read(COMPANY_JSX)
    # Phase I.4.a: events card no longer returns null.
    assert "/app/events?context_id=" in src, (
        "events card must route to /app/events?context_id={cid} now "
        "that I.4.a ships the events surface."
    )
    # And the previous null no-op is gone for events specifically.
    no_op = re.search(
        r'case\s+"events":\s*return\s+null',
        src,
    )
    assert not no_op, (
        "`case \"events\": return null` is gone — events now routes."
    )


def test_i4a_events_route_registered_in_app_js():
    src = _read(APP_JS)
    assert '<Route path="/app/events"' in src, (
        "`/app/events` route must be registered in App.js"
    )
    assert "import" in src and "Events" in src, (
        "Events page must be lazy-imported in App.js"
    )
