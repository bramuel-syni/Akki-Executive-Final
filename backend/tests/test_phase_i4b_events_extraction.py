"""Phase I.4.b — Doc-extraction LLM scan CI guard (2026-05-27).

Locks:
  Backend
    T1.  Extraction endpoint round-trip: mocked LLM returns events,
         endpoint persists them as draft, returns the right shape.
    T2.  Membership 403 on the extraction endpoint.
    T3.  Auth 401 unauth.
    T4.  Low-confidence extractions (<0.6) are discarded.
    T5.  Out-of-window extractions (>7d past OR >24mo future) are discarded.
    T6.  Type taxonomy mapping: unknown LLM types collapse to "other";
         friendly aliases ("AGM" → board_meeting) map correctly.
    T7.  Idempotency: re-running extraction on the same doc deletes
         prior DRAFT rows (only), preserves confirmed events.
    T8.  Soft-deleted (rejected) drafts stay rejected on re-extract.
    T9.  Card 5 (`/api/me/company-home/attention`) does NOT count
         drafts. Promoting a draft to confirmed makes it appear.
    T10. Card 5 absence-default: manual events with no `status` field
         continue to count (regression guard).
    T11. PATCH endpoint: status can only flip to "confirmed" via PATCH;
         attempting to PATCH `status="draft"` returns 422.
    T12. Auto-extract trigger: only allowlisted doc_types fire the
         background task; non-allowlisted is a no-op.
    T13. List endpoint `?status=draft` filter returns only drafts;
         `?status=confirmed` excludes drafts; absent param returns all.

  Frontend wire
    T14. Events.jsx mounts the 4th tab `events-tab-extracted`.
    T15. Extracted tab empty state copy verbatim.
    T16. Confirm + Reject buttons present per draft row (testid pattern).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parent.parent.parent
EVENTS_ROUTER = REPO / "backend" / "routers" / "events.py"
CH_ROUTER     = REPO / "backend" / "routers" / "company_home.py"
EVENTS_JSX    = REPO / "frontend" / "src" / "pages" / "Events.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ═════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
async def i4b_actor():
    from core import db, hash_password
    uid = f"i4b-{uuid.uuid4().hex[:8]}"
    email = f"i4b-{uuid.uuid4().hex[:6]}@example.com"
    pw = "Pw!1234567Abc"
    cid = f"i4b-ctx-{uuid.uuid4().hex[:6]}"
    doc_id = f"i4b-doc-{uuid.uuid4().hex[:8]}"
    now_iso = _iso(datetime.now(timezone.utc))

    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "I4b Tester", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "I4b Test Co",
        "type": "executive_personal", "owner_id": uid,
        "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "account_id": uid, "context_id": cid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })
    # Seed a document with extracted_text (≥80 chars per
    # extract_minutes precedent).
    doc_text = (
        "Q3 BOARD AGENDA — Board pack for the executive review.\n\n"
        "The next board meeting is scheduled for 15 June 2026 at "
        "10:00 in Boardroom A. The audit committee will reconvene on "
        "22 June 2026 to review Q3 financials. AGM falls on "
        "30 September 2026. Year-end audit submission deadline: "
        "31 December 2026."
    )
    await db.documents.insert_one({
        "id": doc_id, "context_id": cid,
        "name": "Q3 Board Pack — June 2026",
        "original_filename": "q3_pack.pdf",
        "extracted_text": doc_text, "extracted_chars": len(doc_text),
        "doc_type": "Board pack", "status": "extracted",
        "uploaded_by": uid, "created_at": now_iso, "updated_at": now_iso,
    })
    yield {
        "uid": uid, "email": email, "password": pw,
        "cid": cid, "doc_id": doc_id,
    }
    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_one({"id": cid})
    await db.memberships.delete_many({"account_id": uid})
    await db.events.delete_many({"context_id": cid})
    await db.documents.delete_many({"context_id": cid})


async def _login(c, actor):
    r = await c.post("/api/auth/login",
                     json={"email": actor["email"], "password": actor["password"]})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _mock_llm_response(events: list[dict]) -> dict:
    """Mimic the shape `call_llm` returns."""
    import json as _json
    return {
        "response": _json.dumps({"events": events}),
        "mode": "mock", "model": "gemini-2.5-flash-mock",
        "tier": "fast", "sources": [], "shielding": {},
        "synisense_verified": True,
    }


# ═════════════════════════════════════════════════════════════════
# Backend
# ═════════════════════════════════════════════════════════════════

# ── T1 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_extraction_endpoint_round_trip(i4b_actor):
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)
    mock = _mock_llm_response([
        {"title": "Q3 Board meeting", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=14)),
         "location": "Boardroom A", "confidence": 0.92},
        {"title": "Audit committee review", "type": "audit_review",
         "start_at": _iso(now + timedelta(days=21)), "confidence": 0.88},
    ])
    with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            hdr = await _login(c, i4b_actor)
            r = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert len(body["extracted"]) == 2
            assert len(body["persisted_draft_ids"]) == 2
            assert body["discarded"]["low_confidence"] == 0


# ── T2 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_extraction_membership_403(i4b_actor):
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        r = await c.post(
            f"/api/contexts/not-a-member-ctx/documents/whatever/extract-events",
            headers=hdr,
        )
    assert r.status_code == 403


# ── T3 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_extraction_unauth_401():
    from server import app  # noqa: F401
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        r = await c.post(
            "/api/contexts/whatever/documents/whatever/extract-events",
        )
    assert r.status_code == 401


# ── T4 + T5 ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_low_confidence_and_out_of_window_discarded(i4b_actor):
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)
    mock = _mock_llm_response([
        # Low confidence — discarded
        {"title": "Maybe a meeting", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=10)),
         "confidence": 0.4},
        # Far future — discarded (>24 months out)
        {"title": "Way too future", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=900)),
         "confidence": 0.95},
        # Too old — discarded (>7d past)
        {"title": "Way too old", "type": "board_meeting",
         "start_at": _iso(now - timedelta(days=30)),
         "confidence": 0.95},
        # Keeper
        {"title": "Real meeting", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=10)),
         "confidence": 0.9},
    ])
    with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            hdr = await _login(c, i4b_actor)
            r = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
            assert r.status_code == 200
            body = r.json()
            assert len(body["extracted"]) == 1
            assert body["extracted"][0]["title"] == "Real meeting"
            assert body["discarded"]["low_confidence"] == 1
            assert body["discarded"]["out_of_window"] == 2


# ── T6 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_type_taxonomy_mapping(i4b_actor):
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)
    mock = _mock_llm_response([
        # Friendly alias: "AGM" → board_meeting
        {"title": "AGM", "type": "AGM",
         "start_at": _iso(now + timedelta(days=60)), "confidence": 0.9},
        # Unknown — should collapse to "other"
        {"title": "Mystery Event", "type": "xyz_unknown",
         "start_at": _iso(now + timedelta(days=30)), "confidence": 0.9},
        # Direct match
        {"title": "Briefing X", "type": "briefing",
         "start_at": _iso(now + timedelta(days=5)), "confidence": 0.9},
    ])
    with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as c:
            hdr = await _login(c, i4b_actor)
            r = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
            assert r.status_code == 200
            by_title = {e["title"]: e["type"] for e in r.json()["extracted"]}
            assert by_title["AGM"] == "board_meeting"
            assert by_title["Mystery Event"] == "other"
            assert by_title["Briefing X"] == "briefing"


# ── T7 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_idempotency_replaces_prior_drafts_preserves_confirmed(i4b_actor):
    from core import db
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)
    mock_run1 = _mock_llm_response([
        {"title": "Draft 1", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=5)), "confidence": 0.9},
        {"title": "Draft 2", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=12)), "confidence": 0.9},
    ])
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        # Run 1 — persist 2 drafts.
        with patch("llm_service.call_llm", new=AsyncMock(return_value=mock_run1)):
            r1 = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
        assert r1.status_code == 200
        ids_run1 = r1.json()["persisted_draft_ids"]
        assert len(ids_run1) == 2

        # Confirm the first draft.
        r_conf = await c.patch(
            f"/api/contexts/{cid}/events/{ids_run1[0]}",
            json={"status": "confirmed"}, headers=hdr,
        )
        assert r_conf.status_code == 200
        assert r_conf.json()["status"] == "confirmed"

        # Run 2 — different drafts.
        mock_run2 = _mock_llm_response([
            {"title": "Draft 3", "type": "audit_review",
             "start_at": _iso(now + timedelta(days=8)), "confidence": 0.9},
        ])
        with patch("llm_service.call_llm", new=AsyncMock(return_value=mock_run2)):
            r2 = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
        assert r2.status_code == 200
        assert len(r2.json()["persisted_draft_ids"]) == 1

    # Verify: confirmed event from run 1 still exists; remaining
    # draft from run 1 is gone; new draft from run 2 exists.
    confirmed_run1 = await db.events.find_one({"id": ids_run1[0]}, {"_id": 0})
    assert confirmed_run1 is not None
    assert confirmed_run1["status"] == "confirmed"
    remaining_draft_run1 = await db.events.find_one(
        {"id": ids_run1[1], "deleted_at": None}, {"_id": 0},
    )
    assert remaining_draft_run1 is None
    drafts_count = await db.events.count_documents({
        "context_id": cid, "source": "doc_extraction",
        "status": "draft", "deleted_at": None,
    })
    assert drafts_count == 1


# ── T8 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_rejected_drafts_stay_rejected_on_reextract(i4b_actor):
    from core import db
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)
    mock = _mock_llm_response([
        {"title": "Will be rejected", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=5)), "confidence": 0.9},
    ])
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
            r1 = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
        rejected_id = r1.json()["persisted_draft_ids"][0]
        # Reject = soft delete
        await c.delete(
            f"/api/contexts/{cid}/events/{rejected_id}", headers=hdr,
        )
        # Re-extract with same payload — should NOT resurrect rejected
        with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
            r2 = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
        assert r2.status_code == 200
    # The rejected row remains soft-deleted, and the new draft has a
    # different id (rejection is identity-locked).
    rejected_row = await db.events.find_one({"id": rejected_id}, {"_id": 0})
    assert rejected_row is not None
    assert rejected_row["deleted_at"] is not None


# ── T9 ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_card5_excludes_drafts_and_counts_confirmed(i4b_actor):
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)
    mock = _mock_llm_response([
        {"title": "Will be confirmed", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=7)), "confidence": 0.9},
    ])
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
            r1 = await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
        draft_id = r1.json()["persisted_draft_ids"][0]

        # Card 5 BEFORE confirm: count should be 0 (drafts excluded)
        att = await c.get(f"/api/me/company-home/attention?context_id={cid}",
                          headers=hdr)
        assert att.json()["events"]["count"] == 0

        # Confirm the draft
        await c.patch(f"/api/contexts/{cid}/events/{draft_id}",
                      json={"status": "confirmed"}, headers=hdr)

        # Need to invalidate the cache by hitting after TTL — for the
        # test we directly clear the in-process cache.
        from routers.company_home import _CACHE
        _CACHE.clear()

        att2 = await c.get(f"/api/me/company-home/attention?context_id={cid}",
                           headers=hdr)
        assert att2.json()["events"]["count"] == 1
        assert att2.json()["events"]["subtext"] == "Will be confirmed"


# ── T10 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_card5_absence_default_manual_events_still_count(i4b_actor):
    from server import app  # noqa: F401
    cid = i4b_actor["cid"]
    now = datetime.now(timezone.utc)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        # Manual event creation — POST writes NO status field.
        r = await c.post(
            f"/api/contexts/{cid}/events",
            json={"title": "Manual event no status",
                  "type": "board_meeting",
                  "start_at": _iso(now + timedelta(days=3))},
            headers=hdr,
        )
        assert r.status_code == 200
        # Card 5 must count this — status is absent, treated as
        # not-draft by the `$ne:"draft"` filter.
        from routers.company_home import _CACHE
        _CACHE.clear()
        att = await c.get(f"/api/me/company-home/attention?context_id={cid}",
                          headers=hdr)
        assert att.json()["events"]["count"] == 1
        assert att.json()["events"]["subtext"] == "Manual event no status"


# ── T11 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_patch_status_only_confirmed_allowed(i4b_actor):
    from server import app  # noqa: F401
    cid = i4b_actor["cid"]
    now = datetime.now(timezone.utc)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        r = await c.post(
            f"/api/contexts/{cid}/events",
            json={"title": "Test", "type": "board_meeting",
                  "start_at": _iso(now + timedelta(days=3))},
            headers=hdr,
        )
        eid = r.json()["id"]
        # Attempt to flip back to draft → 422
        bad = await c.patch(
            f"/api/contexts/{cid}/events/{eid}",
            json={"status": "draft"}, headers=hdr,
        )
        assert bad.status_code == 422


# ── T12 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_auto_extract_trigger_allowlist_only(i4b_actor):
    """Only docs with `doc_type` in `_AUTO_EXTRACT_DOC_TYPES` trigger
    background extraction. Non-allowlisted doc_types are no-ops."""
    from routers.events import auto_extract_after_upload, _AUTO_EXTRACT_DOC_TYPES

    cid, doc_id, uid = i4b_actor["cid"], i4b_actor["doc_id"], i4b_actor["uid"]

    # Allowlisted — should attempt extraction (mocked LLM keeps it cheap)
    assert "Board pack" in _AUTO_EXTRACT_DOC_TYPES
    assert "chat_attachment" not in _AUTO_EXTRACT_DOC_TYPES

    # No-op path: non-allowlisted doc_type returns without calling LLM.
    with patch("llm_service.call_llm", new=AsyncMock()) as mocked:
        await auto_extract_after_upload(
            cid=cid, doc_id=doc_id,
            doc_type="chat_attachment", actor_id=uid,
        )
        assert mocked.call_count == 0


# ── T13 ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_i4b_list_status_filter(i4b_actor):
    from server import app  # noqa: F401
    cid, doc_id = i4b_actor["cid"], i4b_actor["doc_id"]
    now = datetime.now(timezone.utc)

    mock = _mock_llm_response([
        {"title": "Draft A", "type": "board_meeting",
         "start_at": _iso(now + timedelta(days=5)), "confidence": 0.9},
    ])
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        hdr = await _login(c, i4b_actor)
        # 1 manual + 1 extracted draft
        await c.post(
            f"/api/contexts/{cid}/events",
            json={"title": "Manual A", "type": "board_meeting",
                  "start_at": _iso(now + timedelta(days=2))},
            headers=hdr,
        )
        with patch("llm_service.call_llm", new=AsyncMock(return_value=mock)):
            await c.post(
                f"/api/contexts/{cid}/documents/{doc_id}/extract-events",
                headers=hdr,
            )
        # No status filter → 2 total
        r_all = await c.get(
            f"/api/contexts/{cid}/events?upcoming=false", headers=hdr,
        )
        assert r_all.json()["total"] == 2
        # status=draft → 1
        r_draft = await c.get(
            f"/api/contexts/{cid}/events?upcoming=false&status=draft",
            headers=hdr,
        )
        assert r_draft.json()["total"] == 1
        assert r_draft.json()["items"][0]["title"] == "Draft A"
        # status=confirmed → 1 (manual w/o status, via $ne:"draft")
        r_conf = await c.get(
            f"/api/contexts/{cid}/events?upcoming=false&status=confirmed",
            headers=hdr,
        )
        assert r_conf.json()["total"] == 1
        assert r_conf.json()["items"][0]["title"] == "Manual A"


# ═════════════════════════════════════════════════════════════════
# Source-strict frontend guards
# ═════════════════════════════════════════════════════════════════

# ── T14 ──────────────────────────────────────────────────────────
def test_i4b_events_jsx_mounts_extracted_tab():
    src = _read(EVENTS_JSX)
    assert 'data-testid="events-tab-extracted"' in src
    # Tab label includes the dynamic count appendix.
    assert "Extracted{drafts.length > 0 ? ` (${drafts.length})` : \"\"}" in src \
        or "Extracted{drafts.length" in src


# ── T15 ──────────────────────────────────────────────────────────
def test_i4b_extracted_tab_empty_state_copy_verbatim():
    src = _read(EVENTS_JSX)
    # Exact copy from the brief, step 5.
    assert "No extracted events. Upload a board pack or briefing to surface dates automatically." in src


# ── T16 ──────────────────────────────────────────────────────────
def test_i4b_draft_row_actions_present():
    src = _read(EVENTS_JSX)
    # Both action buttons + confidence badge testid patterns.
    assert "events-draft-confirm-" in src
    assert "events-draft-reject-" in src
    assert "events-draft-confidence-" in src
    # 92% match-style suffix is in code.
    assert "% match" in src


# ── Negative invariant ──────────────────────────────────────────
def test_i4b_card5_filter_excludes_drafts_in_source():
    """Source-strict guard: the Card 5 query MUST carry the
    `$ne: "draft"` filter so drafts never bleed onto Company Home."""
    src = _read(CH_ROUTER)
    # Strip docstrings + comments
    stripped = re.sub(r'"""[\s\S]*?"""', "", src)
    stripped = re.sub(r"#[^\n]*", "", stripped)
    m = re.search(
        r"async def _build_events\([^)]*\)[\s\S]*?return CardEvents\(",
        stripped,
    )
    assert m, "_build_events function not found"
    body = m.group(0)
    assert '"$ne"' in body and '"draft"' in body, (
        "Card 5 query must filter out draft events via $ne:\"draft\". "
        "Manual events (no status field) implicitly count via the "
        "absence-default behavior."
    )
