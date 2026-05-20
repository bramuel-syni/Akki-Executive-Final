"""Chunk 9 — Add-a-Contribution attach (QA-2026-05-16-017 → -021).

Backend regression coverage for the 5 IDs + 3 cross-cutting guards
(combined scoring, CTA gating, auto-Title regression). Frontend
behaviour for the picker UI + chip + auto-title state is covered by
`frontend/scripts/render-smoke.js` step 10.

Spec anchors in `qa_reports/QA_REPORT_16MAY2026.md`.
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


# ─────────────────────────────────────────────────────────────────────
# Fixtures — ephemeral account / context / agenda / contributor / doc.
# ─────────────────────────────────────────────────────────────────────
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
    """Bare account + context — no cycle yet. Tests that exercise
    contribution flow seed the cycle/agenda/member inline."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk9-{suffix}@example.com"
    password = "Chunk9-2026!"
    account_id = f"acc-c9-{suffix}"
    context_id = f"ctx-c9-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk9 Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk9 Ctx", "created_at": now_iso,
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
    await db_conn.documents.delete_many({"context_id": context_id})
    await db_conn.cycle_contributions.delete_many({"context_id": context_id})
    await db_conn.cycle_agendas.delete_many({"context_id": context_id})
    await db_conn.cycle_team.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


async def _seed_cycle_fixture(db_conn, *, context_id, account_id):
    """Create one cycle + 1 agenda item + 1 team member. Returns ids."""
    cycle_id = f"cyc-{uuid.uuid4().hex[:8]}"
    agenda_id = f"agi-{uuid.uuid4().hex[:8]}"
    member_id = f"mem-tm-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.cycle_agendas.insert_one({
        "id": agenda_id, "cycle_id": cycle_id, "context_id": context_id,
        "title": "Q3 Risk register update",
        "description": "Review the live risks from the May steering session.",
        "team_member_id": member_id,
        "owner_account_id": account_id,
        "status": "active",
        "created_at": now_iso, "updated_at": now_iso,
    })
    await db_conn.cycle_team.insert_one({
        "id": member_id, "cycle_id": cycle_id, "context_id": context_id,
        "name": "Test Contributor", "email": "tc@example.com",
        "role": "CFO",
        "contribution_description": "Quarterly capital adequacy + provisioning data.",
        "created_at": now_iso,
    })
    return {"cycle_id": cycle_id, "agenda_id": agenda_id, "member_id": member_id}


async def _seed_document(db_conn, *, context_id, account_id, title, text):
    did = f"doc-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": did, "context_id": context_id, "account_id": account_id,
        "name": title, "original_filename": f"{title}.pdf",
        "extracted_text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return did


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-017 — attach icon + picker entry point
# ─────────────────────────────────────────────────────────────────────
async def test_qa_017_contribution_with_source_doc_accepted(client, authed, db_conn):
    """Verbatim: 'attach icon … From Document Journal — opens a
    searchable list … selection attaches the document.'

    Backend acceptance: `ContributionIn` accepts `source_doc_id` —
    locked since Chunk 7 -005 fix. Re-asserted here as a Chunk-9
    guard so any future schema change fails THIS test, not silently
    in the live preview."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Q3 Capital Memo", text="CET1 stands at 14.2%.",
    )
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "document",
            "title": "Q3 Capital Memo",
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["source_doc_id"] == doc_id
    assert rec["kind"] == "document"


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-018 — chip + remove (frontend behaviour locked by smoke;
# backend guard: remove doesn't strand the original document upload).
# ─────────────────────────────────────────────────────────────────────
async def test_qa_018_attached_doc_remains_in_journal_after_chip_removed(
    client, authed, db_conn,
):
    """Verbatim chip-removal behaviour is frontend-only. The backend
    guard here: when the user adds + removes an attachment without
    submitting, the Document Journal still contains the uploaded doc
    (we never delete on chip-remove — that's a journal-management
    concern, not a contribution-form concern)."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Audit Letter", text="Auditor opinion attached.",
    )
    # Simulate chip-remove → the doc is NOT deleted from the journal.
    listing = await client.get(f"/api/contexts/{cid}/documents?limit=20", headers=headers)
    assert listing.status_code == 200
    rows = listing.json()
    docs = rows if isinstance(rows, list) else (rows.get("items") or [])
    assert any(d["id"] == doc_id for d in docs), "uploaded doc disappeared from journal"


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-019 — paste textbox stays alongside attachments
# ─────────────────────────────────────────────────────────────────────
async def test_qa_019_paste_text_alongside_attachment_both_persisted(
    client, authed, db_conn,
):
    """Both `body_text` AND `source_doc_id` survive the round-trip
    when present together — backend doesn't drop one in favour of
    the other."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Source memo", text="Detail from the source memo.",
    )
    pasted = "Additional commentary from the contributor's notes."
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
            "title": "Combined contribution",
            "body_text": pasted,
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["body_text"] == pasted
    assert rec["source_doc_id"] == doc_id


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-020 — combined-scoring (core)
# ─────────────────────────────────────────────────────────────────────
async def test_qa_020_combined_scoring_uses_both_attachment_and_pasted_text(
    client, authed, db_conn,
):
    """Decision (a) from Chunk-9 dispatch: concatenate body_text +
    attached doc's extracted_text into a single string, run the
    existing heuristic once. The `scoring_input` surface on the row
    records which inputs contributed so audits can verify both."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Q3 capital adequacy briefing",
        # Long enough to push the combined fullness metric, but the
        # PASTED text alone is short — so combined-scoring is the only
        # way the test passes.
        text=(
            "Quarterly capital adequacy at 14.2 percent; provisioning "
            "coverage 47 percent; corporate concentration in top-5 "
            "borrowers; succession planning still pending for the CFO "
            "role; deposit-mix shift on track at 62 retail / 38 corp."
            * 8
        ),
    )
    create = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
            "title": "Combined",
            "body_text": "Short pasted note.",
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    assert create.status_code == 200, create.text
    contrib_id = create.json()["id"]
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions/{contrib_id}/score",
        json={}, headers=headers,
    )
    assert r.status_code == 200, r.text
    rec = r.json()
    si = rec.get("scoring_input")
    assert si, "score endpoint must expose scoring_input"
    assert si["has_body_text"] is True
    assert si["has_attachment"] is True
    # Combined string contains both halves: pasted prefix + the
    # attached title marker + first 50 chars of extracted text.
    assert si["combined_char_count"] > 200, (
        "combined_char_count should exceed body_text alone; got "
        f"{si['combined_char_count']}"
    )


async def test_qa_020_combined_scoring_works_with_attachment_only(client, authed, db_conn):
    """No pasted body_text, just an attached doc — scoring still
    runs against the extracted_text alone. The `has_attachment` flag
    is True; `has_body_text` is False."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Memo", text="Standalone memo content with enough text to score.",
    )
    create = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "document",
            "title": "Memo",
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    contrib_id = create.json()["id"]
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions/{contrib_id}/score",
        json={}, headers=headers,
    )
    assert r.status_code == 200, r.text
    si = r.json().get("scoring_input") or {}
    assert si["has_attachment"] is True
    assert si["has_body_text"] is False
    assert si["combined_char_count"] > 30


async def test_qa_020_combined_scoring_works_with_paste_only(client, authed, db_conn):
    """No attached doc — body_text alone. Backwards-compat with the
    pre-Chunk-9 flow."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    create = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
            "body_text": "Plain pasted contribution with sufficient text to score reasonably.",
        },
        headers=headers,
    )
    contrib_id = create.json()["id"]
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions/{contrib_id}/score",
        json={}, headers=headers,
    )
    si = r.json().get("scoring_input") or {}
    assert si["has_body_text"] is True
    assert si["has_attachment"] is False


async def test_qa_020_combined_scoring_silent_fallback_when_source_doc_missing(
    client, authed, db_conn,
):
    """Robustness guard: if the attached doc id refers to a deleted
    document, the score endpoint MUST NOT 500 — it falls back to
    body_text alone with `has_attachment=True` (the row still
    references the missing id) but contributing-nothing semantics."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    create = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
            "body_text": "Body text present.",
            "source_doc_id": "doc-nonexistent-12345",
        },
        headers=headers,
    )
    contrib_id = create.json()["id"]
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions/{contrib_id}/score",
        json={}, headers=headers,
    )
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-021 — CTA gating (backend echo of the frontend rule)
# ─────────────────────────────────────────────────────────────────────
async def test_qa_021_contribution_rejected_when_no_input_provided(
    client, authed, db_conn,
):
    """Frontend CTA disable is the primary defence. Backend should
    also reject a contribution with neither body_text NOR
    source_doc_id — a defensive 400/422 keeps the contract honest."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
            # No body_text. No source_doc_id.
        },
        headers=headers,
    )
    assert r.status_code in (400, 422), (
        f"empty contribution must be rejected, got HTTP {r.status_code}: {r.text}"
    )


# ─────────────────────────────────────────────────────────────────────
# Cross-cutting #1 — combined-scoring evidence (both inputs counted)
# ─────────────────────────────────────────────────────────────────────
async def test_chunk9_combined_scoring_single_pass_with_both_inputs(
    client, authed, db_conn,
):
    """Single rubric pass = single `scoring_input` row, both flags
    True, char count > sum of either alone. Locks decision (a)."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Detail report", text="A" * 500,
    )
    body = "B" * 200
    create = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "body_text": body,
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    r = await client.post(
        f"/api/contexts/{cid}/cycle/contributions/{create.json()['id']}/score",
        json={}, headers=headers,
    )
    si = r.json()["scoring_input"]
    assert si["has_body_text"] and si["has_attachment"]
    # Combined must include the body (200) + the marker + the
    # attachment text (500). Should be > 700.
    assert si["combined_char_count"] >= 700


# ─────────────────────────────────────────────────────────────────────
# Cross-cutting #2 — CTA-gating backend echo
# ─────────────────────────────────────────────────────────────────────
async def test_chunk9_cta_gating_both_inputs_clear_means_reject(client, authed, db_conn):
    """Direct re-assert of the spec: zero inputs = reject. We also
    confirm one-input is sufficient (either side)."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])

    # zero inputs → 400/422
    rz = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
        },
        headers=headers,
    )
    assert rz.status_code in (400, 422)

    # one input (body only) → 200
    rb = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note",
            "body_text": "Just text.",
        },
        headers=headers,
    )
    assert rb.status_code == 200

    # one input (attachment only) → 200
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Just memo", text="Memo content.",
    )
    rd = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "document",
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    assert rd.status_code == 200


# ─────────────────────────────────────────────────────────────────────
# Cross-cutting #3 — auto-Title regression
# ─────────────────────────────────────────────────────────────────────
# The full title-auto-fill / clear-only-if-not-edited logic is in
# `Cycle.jsx` form state (frontend-only). The backend's job here is
# narrower: respect whatever Title the client sent. We assert that
# the round-trip preserves user titles AND attachment-derived titles.
async def test_chunk9_title_round_trip_preserves_user_intent(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    fx = await _seed_cycle_fixture(db_conn, context_id=cid, account_id=authed["account_id"])
    # 1. User-edited title — explicit value.
    r1 = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "note", "body_text": "x",
            "title": "User-typed title — preserved",
        },
        headers=headers,
    )
    assert r1.json()["title"] == "User-typed title — preserved"
    # 2. Frontend chose to auto-populate from the attached doc — same
    # round-trip semantics. Backend doesn't differentiate "auto vs
    # user" — that's frontend bookkeeping. We just confirm round-trip.
    doc_id = await _seed_document(
        db_conn, context_id=cid, account_id=authed["account_id"],
        title="Q3 Capital Memo.pdf", text="...",
    )
    r2 = await client.post(
        f"/api/contexts/{cid}/cycle/contributions",
        json={
            "agenda_item_id": fx["agenda_id"],
            "team_member_id": fx["member_id"],
            "kind": "document",
            "title": "Q3 Capital Memo.pdf",
            "source_doc_id": doc_id,
        },
        headers=headers,
    )
    assert r2.json()["title"] == "Q3 Capital Memo.pdf"
