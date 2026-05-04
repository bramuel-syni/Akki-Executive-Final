"""Phase 15.1 — Work Studio Briefings tab visibility regression.

Guard against the briefings-list shape mismatch found during the demo
window: backend GET /api/contexts/{cid}/briefings returns a BARE LIST,
the WorkStudio frontend was reading data?.items / data?.briefings only,
so freshly-created briefings never appeared on /app/work-studio.

This test pins the contract from the API side: a freshly-created
briefing (status='active') MUST be returned by the list endpoint in the
same session. If we ever switch to an {items: [...]} envelope, the test
will still pass against either shape.

Run:
    pytest /app/backend/tests/test_work_studio_briefings_visible.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


@pytest.fixture(scope="module")
def client_ctx():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    cid = (me.get("account") or {}).get("default_context_id")
    if not cid and me.get("contexts"):
        cid = me["contexts"][0]["id"]
    assert cid, "admin has no context"
    return s, cid


def _seed_briefing_direct(cid: str) -> str:
    """Insert a briefing row directly into Mongo so the test doesn't need
    to round-trip the (slow) LLM-driven /briefings POST. The visibility
    contract is independent of the create-path."""
    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "akki_dev")
    db = MongoClient(mongo_url)[db_name]
    bid = str(uuid.uuid4())
    db.briefings.insert_one({
        "id": bid,
        "context_id": cid,
        "title": f"Phase 15.1 visibility test {bid[:6]}",
        "status": "active",   # the contested state
        "version": 1,
        "role": "executive",
        "opening_paragraph": "Smoke test briefing — should be visible.",
        "items": [],
        "closing_note": "",
        "source_doc_ids": [],
        "signal_ids": [],
        "data_trust": "high",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "block_status": "draft",  # also test that this doesn't filter it out
    })
    return bid


def _cleanup_briefing(bid: str) -> None:
    from pymongo import MongoClient

    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "akki_dev")]
    db.briefings.delete_one({"id": bid})


def _normalise_list(data):
    """Mirror the WorkStudio frontend normalisation. Accept bare list,
    {items: [...]}, or {briefings: [...]}."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or data.get("briefings") or []
    return []


def test_freshly_created_briefing_appears_in_list(client_ctx):
    """Insert one briefing with status='active' and confirm it surfaces in
    GET /api/contexts/{cid}/briefings within the same session, regardless
    of envelope shape."""
    s, cid = client_ctx
    bid = _seed_briefing_direct(cid)
    try:
        r = s.get(f"{BASE_URL}/api/contexts/{cid}/briefings", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        items = _normalise_list(data)
        ids = [b.get("id") for b in items]
        assert bid in ids, (
            f"newly-created briefing {bid} not visible in /briefings list. "
            f"Got {len(items)} items, ids={ids[:5]}…"
        )
        ours = next(b for b in items if b.get("id") == bid)
        assert ours.get("status") == "active"
        # The non-sent filter on the WorkStudio side must not strip 'active'.
        assert (ours.get("status") or "draft") != "sent"
    finally:
        _cleanup_briefing(bid)


def test_briefings_endpoint_shape_is_documented_and_stable(client_ctx):
    """Pin the wire contract: list OR {items:[]} OR {briefings:[]}. If the
    backend ever changes shape, _normalise_list still has to work — this
    is the safety net for the WorkStudio fix."""
    s, cid = client_ctx
    r = s.get(f"{BASE_URL}/api/contexts/{cid}/briefings", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    # Either a list directly, or a dict whose first list-valued key holds
    # briefings — must not be a plain dict with no list anywhere.
    if isinstance(data, dict):
        has_list = any(isinstance(v, list) for v in data.values())
        assert has_list, f"unexpected dict-shaped briefings response: {list(data.keys())}"
    else:
        assert isinstance(data, list), f"unexpected response type: {type(data).__name__}"
    items = _normalise_list(data)
    # All items must have id + status + context_id minimum.
    for b in items:
        assert b.get("id"), b
        assert b.get("context_id") == cid, b
        assert "status" in b, b
