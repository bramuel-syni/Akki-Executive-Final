"""Chunk 10 — 16-May Pulse-surface P1+P2 batch (-022 → -028).

Backend regression coverage. Anchor: `/app/memory/qa_reports/QA_REPORT_16MAY2026.md`
sections QA-2026-05-16-022 → -028. Frontend-only display behaviours (QA-025
filter chip removal, QA-027 drawer chip cluster, QA-028 Bookmark-merge,
QA-026 bullet formatting, QA-023/-024 saved-marker propagation) are
covered by ESLint + render-smoke step 12; this file covers the API-layer
guarantees that the frontend reads from.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk10-{suffix}@example.com"
    password = "Chunk10-2026!"
    account_id = f"acc-c10-{suffix}"
    context_id = f"ctx-c10-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk10 Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk10 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.signals.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


async def _seed_signal(db, context_id, account_id, comments=None):
    sig_id = f"sig-{uuid.uuid4().hex[:10]}"
    await db.signals.insert_one({
        "id": sig_id,
        "context_id": context_id,
        "account_id": account_id,
        "headline": "Capital adequacy buffer thinning vs Q1 baseline",
        "summary": "CET1 ratio drift suggests narrowing buffer. [doc:capital.pdf]",
        "body": "Quarterly buffer down 80bps.",
        "reasoning": (
            "Risk-weighted assets are up 4.2% this quarter.\n\n"
            "Tier-1 capital has stagnated due to deferred-tax catch-up.\n\n"
            "Combined effect is buffer erosion before Q3 close. [doc:audit.pdf]"
        ),
        "type": "risk",
        "surface_type": "risk",
        "signal_kind": "capital",
        "topic_class": "capital",
        "freshness": "new",
        "confidence": "high",
        "data_trust": "verified",
        "merge_count": 1,
        "state": "active",
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "references": [],
        "comments": comments or [],
    })
    return sig_id


# =====================================================================
# QA-022 — saved comments must be readable back via the feed
# =====================================================================
async def test_qa022_pulse_feed_returns_owners_comments_inline(client, db_conn, authed):
    """The Pulse feed (`GET /pulse/feed`) MUST return `comments[]` on
    each card, scoped to the requesting account. The QA-022 bug was
    pure frontend display; this test guards the contract the
    frontend reads from."""
    headers = await _login(client, authed["email"], authed["password"])
    headers["X-Active-Context"] = authed["context_id"]
    comment_id = f"cm-{uuid.uuid4().hex[:8]}"
    await _seed_signal(db_conn, authed["context_id"], authed["account_id"],
                       comments=[{
                           "id": comment_id,
                           "account_id": authed["account_id"],
                           "note": "Committee should ask Treasury for the contingency.",
                           "created_at": datetime.now(timezone.utc).isoformat(),
                       }])
    r = await client.get(f"/api/contexts/{authed['context_id']}/pulse/feed",
                         headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    cards = body.get("cards") or []
    assert len(cards) >= 1
    target = cards[0]
    assert "comments" in target, target
    assert len(target["comments"]) == 1
    assert target["comments"][0]["id"] == comment_id
    assert "Treasury" in target["comments"][0]["note"]


async def test_qa022_pulse_feed_hides_other_users_comments(client, db_conn, authed):
    """Comments are per-account private — a comment authored by a
    different account_id MUST NOT surface on the caller's feed."""
    headers = await _login(client, authed["email"], authed["password"])
    headers["X-Active-Context"] = authed["context_id"]
    other_account_id = f"acc-other-{uuid.uuid4().hex[:8]}"
    await _seed_signal(db_conn, authed["context_id"], authed["account_id"],
                       comments=[{
                           "id": f"cm-{uuid.uuid4().hex[:8]}",
                           "account_id": other_account_id,
                           "note": "Secret comment from another exec.",
                           "created_at": datetime.now(timezone.utc).isoformat(),
                       }])
    r = await client.get(f"/api/contexts/{authed['context_id']}/pulse/feed",
                         headers=headers)
    assert r.status_code == 200, r.text
    cards = r.json().get("cards") or []
    assert len(cards) >= 1
    assert cards[0]["comments"] == [], cards[0]["comments"]


async def test_qa022_comment_persists_then_reappears_on_refetch(client, db_conn, authed):
    """End-to-end save→reload flow: POST a comment, then GET the
    feed again and confirm the comment is in the response."""
    headers = await _login(client, authed["email"], authed["password"])
    headers["X-Active-Context"] = authed["context_id"]
    sig_id = await _seed_signal(db_conn, authed["context_id"], authed["account_id"])

    # POST a comment.
    r1 = await client.post(
        f"/api/contexts/{authed['context_id']}/pulse/signals/{sig_id}/comment",
        headers=headers, json={"note": "Refetch round-trip note."},
    )
    assert r1.status_code == 200, r1.text
    comment_doc = r1.json().get("comment") or {}
    assert comment_doc.get("note") == "Refetch round-trip note."

    # GET the feed — comment should be there.
    r2 = await client.get(
        f"/api/contexts/{authed['context_id']}/pulse/feed",
        headers=headers,
    )
    cards = r2.json().get("cards") or []
    target = next((c for c in cards if c["id"] == sig_id), None)
    assert target is not None
    assert any(c["id"] == comment_doc["id"] for c in target["comments"]), target["comments"]


# =====================================================================
# QA-023 — save endpoint returns `saved` flag for icon-state + toast
# =====================================================================
async def test_qa023_save_endpoint_returns_saved_flag(client, db_conn, authed):
    """The frontend's "Saved — find it on the Bookmarked tab." toast
    is gated on `data?.saved === true`. This test confirms the save
    endpoint returns the expected shape on first save AND on un-save."""
    headers = await _login(client, authed["email"], authed["password"])
    headers["X-Active-Context"] = authed["context_id"]
    sig_id = await _seed_signal(db_conn, authed["context_id"], authed["account_id"])

    r1 = await client.post(
        f"/api/contexts/{authed['context_id']}/pulse/signals/{sig_id}/save",
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    assert r1.json().get("saved") is True

    # Toggle off — should report saved=false.
    r2 = await client.post(
        f"/api/contexts/{authed['context_id']}/pulse/signals/{sig_id}/save",
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json().get("saved") is False


# =====================================================================
# QA-024 — saved state surfaces via actions_summary.my_saved
# =====================================================================
async def test_qa024_my_saved_surfaces_in_feed_after_save(client, db_conn, authed):
    """`actions_summary.my_saved` must be true on the feed after a
    save action. The drawer + card render their saved-state markers
    from this field; QA-024 requires the marker to appear wherever
    the signal renders."""
    headers = await _login(client, authed["email"], authed["password"])
    headers["X-Active-Context"] = authed["context_id"]
    sig_id = await _seed_signal(db_conn, authed["context_id"], authed["account_id"])

    await client.post(
        f"/api/contexts/{authed['context_id']}/pulse/signals/{sig_id}/save",
        headers=headers,
    )
    # After save, the signal moves to the Bookmarked tab (state="bookmarked").
    # The Active feed deliberately excludes it (the user just saved it FOR
    # the Bookmarked surface). QA-024 requires the saved marker to surface
    # wherever the signal renders — query the Bookmarked tab explicitly.
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/pulse/feed?state=bookmarked",
        headers=headers,
    )
    cards = r.json().get("cards") or []
    target = next((c for c in cards if c["id"] == sig_id), None)
    assert target is not None, f"signal not on Bookmarked tab after save (got {len(cards)} cards)"
    assert (target.get("actions_summary") or {}).get("my_saved") is True, target


# =====================================================================
# QA-022 / QA-024 — cross-account scope guard on save
# =====================================================================
async def test_qa024_save_state_is_per_account(client, db_conn, authed):
    """Another account saving the signal does NOT flip the caller's
    `my_saved` flag — privacy boundary intact."""
    headers = await _login(client, authed["email"], authed["password"])
    headers["X-Active-Context"] = authed["context_id"]
    sig_id = await _seed_signal(db_conn, authed["context_id"], authed["account_id"])

    # Inject a save record for a DIFFERENT account.
    other_id = f"acc-other-{uuid.uuid4().hex[:8]}"
    await db_conn.signal_actions.insert_one({
        "id": f"act-{uuid.uuid4().hex[:8]}",
        "signal_id": sig_id, "context_id": authed["context_id"],
        "account_id": other_id, "action_type": "saved",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    r = await client.get(
        f"/api/contexts/{authed['context_id']}/pulse/feed",
        headers=headers,
    )
    cards = r.json().get("cards") or []
    target = next((c for c in cards if c["id"] == sig_id), None)
    assert target is not None
    assert (target.get("actions_summary") or {}).get("my_saved") is False


# =====================================================================
# Chunk 10 architectural invariant — citation stripper is pure FE
# =====================================================================
@pytest.mark.asyncio(loop_scope="session")
async def test_chunk10_citation_stripper_is_frontend_only():
    """The Pulse.jsx `stripCitations()` helper exists at module-scope.
    Backend signal payloads are NOT pre-stripped — the spec wants
    citations to remain available in the Source section of the
    drawer (rendered from `references[]`). This static check confirms
    the backend doesn't accidentally strip the body/summary before
    returning them."""
    pulse_src = open("/app/backend/routers/pulse.py").read()
    # Backend must not contain any citation-stripping regex that
    # mutates summary/body/reasoning text in-place.
    for forbidden_pattern in (
        "stripCitations", "strip_citations", "CITATION_PATTERNS",
    ):
        assert forbidden_pattern not in pulse_src, (
            f"backend should not strip citations — frontend Pulse.jsx is the canonical location"
        )
    # Frontend has the helper.
    fe_src = open("/app/frontend/src/pages/Pulse.jsx").read()
    assert "stripCitations" in fe_src
    assert "CITATION_PATTERNS" in fe_src
    assert "splitToBullets" in fe_src
