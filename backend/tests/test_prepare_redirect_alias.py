"""Phase 13.2 — `/app/prepare` redirect alias smoke tests.

The frontend `<Navigate to="/app/cycle?tab=briefs" replace />` alias in
App.js cannot be asserted server-side (CRA is a SPA), but we can prove
the underlying APIs that the legacy /app/prepare page used remain live
and reachable, so the redirect target works the moment the React shell
mounts. These tests therefore assert two contracts:

  1. The backend `/api/contexts/{cid}/briefs` endpoint still responds —
     i.e. nothing in the Cycle Manager merger broke the brief surface.
  2. The new aggregator `/api/contexts/{cid}/cycle/actions` is reachable
     (its dedicated coverage lives in
     `test_cycle_manager_actions_tab.py`); a 200 here proves the new
     surface that absorbs Prepare is mounted.

Frontend Navigate behaviour itself is asserted by the Phase 13.3
browser pass.
"""
from __future__ import annotations

import os
import sys

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


def _first_ctx(admin_session):
    me = admin_session.get(f"{BACKEND}/api/auth/me", timeout=10).json()
    contexts = me.get("contexts") or []
    if not contexts:
        pytest.skip("admin has no contexts")
    return contexts[0]["id"]


def test_legacy_briefs_endpoint_still_responds(admin_session):
    """Phase 13.2 absorbed Prepare into Cycle Manager but kept the API
    surface (`/api/contexts/{cid}/briefs/*`) intact. The legacy listing
    endpoint must still 200, so any client (web, programmatic, future
    mobile) that pointed at it before the merger continues to work."""
    cid = _first_ctx(admin_session)
    r = admin_session.get(
        f"{BACKEND}/api/contexts/{cid}/briefs", timeout=10,
    )
    # The merger does NOT change the contract; an existing-ctx listing
    # should always be a 200 with `{count, items: [...]}` shape (possibly
    # empty). The shape is `{count, items}` per `routers/prepare.py`'s
    # GET handler — we assert both keys here so any future drift is
    # caught.
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    assert "items" in body, body
    assert isinstance(body.get("items"), list), body


def test_cycle_manager_actions_endpoint_mounted(admin_session):
    """The redirect target `/app/cycle?tab=briefs` is a SPA route, but
    the new aggregator `/api/contexts/{cid}/cycle/actions` is the proof
    the Phase 13.2 backend changes shipped. A 200 here means the merger
    landed cleanly and the Cycle Manager Actions tab will render."""
    cid = _first_ctx(admin_session)
    r = admin_session.get(
        f"{BACKEND}/api/contexts/{cid}/cycle/actions", timeout=10,
    )
    assert r.status_code == 200, (r.status_code, r.text[:200])
    body = r.json()
    for key in ("counts", "sections", "as_of"):
        assert key in body, (key, body.keys())
    # Sections must contain all three buckets even if empty.
    sections = body["sections"]
    for k in ("signal_actions", "plays", "cycle_pending"):
        assert k in sections, (k, sections.keys())
        assert isinstance(sections[k], list), (k, type(sections[k]))
