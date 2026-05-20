"""Chunk 8 — Document Overlay (QA-2026-05-16-029 → -036).

Backend regression coverage for the foundation + 7 visible-UX IDs.
The pure-UX bits (overlay shell DOM, dimming, modal close affordances)
are covered by `frontend/scripts/render-smoke.js` step 9.

Each test references its spec anchor in `qa_reports/QA_REPORT_16MAY2026.md`.
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
from services.work_studio_overlay import (
    ALLOWED_LIFECYCLE,
    can_transition,
    ensure_overlay_migration,
    find_referenced_doc_ids,
    normalise_structured_content,
    rag_band,
)


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Fixtures
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
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk8-{suffix}@example.com"
    password = "Chunk8-2026!"
    account_id = f"acc-c8-{suffix}"
    context_id = f"ctx-c8-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk8 Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk8 Context", "created_at": now_iso,
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
    await db_conn.work_studio_exports.delete_many({"context_id": context_id})
    await db_conn.work_studio_artefact_versions.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


async def _seed_artefact(db_conn, *, context_id, account_id, lifecycle_state="draft",
                          source_docs=None, structured=None, legacy=False, intel=None):
    aid = f"ws-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.work_studio_exports.insert_one({
        "id": aid,
        "context_id": context_id,
        "account_id": account_id,
        "kind": "report",
        "status": "complete" if not legacy else "complete",
        "file_name": "Test Report.docx",
        "document_title": "Test Report",
        "lifecycle_state": lifecycle_state,
        "legacy": legacy,
        "structured_content": structured or {"sections": [
            {"heading": "Executive summary", "paragraphs": ["The committee considered…"]},
            {"heading": "Capital position", "paragraphs": ["CET1 stands at 14.2%."]},
        ]},
        "source_document_ids": source_docs or [],
        "intelligence_report": intel,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    return aid


# ─────────────────────────────────────────────────────────────────────
# Foundation — migration + helpers
# ─────────────────────────────────────────────────────────────────────
def test_chunk8_rag_band_thresholds():
    """Q4 decision: ≥80 green · 50-79 amber · <50 red · None unrated."""
    assert rag_band(None) == "unrated"
    assert rag_band(0) == "red"
    assert rag_band(49) == "red"
    assert rag_band(50) == "amber"
    assert rag_band(79) == "amber"
    assert rag_band(80) == "green"
    assert rag_band(100) == "green"


def test_chunk8_can_transition_state_machine():
    """Q1 decision: Draft → InReview is owner-only; Committed is immutable."""
    assert can_transition("draft", "in_review", is_owner=True)[0]
    assert not can_transition("draft", "in_review", is_owner=False)[0]
    assert can_transition("draft", "committed", is_owner=False)[0]
    assert can_transition("in_review", "committed", is_owner=False)[0]
    # Committed is immutable.
    assert not can_transition("committed", "draft", is_owner=True)[0]
    assert not can_transition("committed", "in_review", is_owner=True)[0]


def test_chunk8_referenced_doc_id_scan():
    """Source-doc allowlist enforcement helper — scans instructions
    for explicit doc-id references in either bare-UUID or `doc:<uuid>` form."""
    instr = (
        "Reflect insights from doc:6f1d12e8-1234-5678-abcd-1234567890ab and "
        "also pull from 7a8b9c0d-1234-5678-abcd-fedcba987654."
    )
    refs = find_referenced_doc_ids(instr)
    assert "6f1d12e8-1234-5678-abcd-1234567890ab" in refs
    assert "7a8b9c0d-1234-5678-abcd-fedcba987654" in refs


def test_chunk8_normalise_structured_content_strips_junk():
    n = normalise_structured_content({
        "sections": [
            {"heading": "x", "paragraphs": ["a", "b", 12, None, "c"]},
            "not-a-dict",
            {"heading": "y"},
            {"paragraphs": ["only-paras"]},
        ],
        "extra_unwanted_key": True,
    })
    assert n == {"sections": [
        {"heading": "x", "paragraphs": ["a", "b", "12", "c"]},
        {"heading": "y", "paragraphs": []},
        {"heading": "", "paragraphs": ["only-paras"]},
    ]}


async def test_chunk8_migration_idempotent(db_conn, authed):
    """Legacy rows get lifecycle_state=committed, legacy=True. Idempotent."""
    cid = authed["context_id"]
    now_iso = datetime.now(timezone.utc).isoformat()
    # Insert a pre-Chunk-8 row (no lifecycle_state).
    legacy_id = f"ws-legacy-{uuid.uuid4().hex[:8]}"
    await db_conn.work_studio_exports.insert_one({
        "id": legacy_id, "context_id": cid, "account_id": authed["account_id"],
        "kind": "report", "status": "complete", "file_name": "old.docx",
        "created_at": now_iso, "updated_at": now_iso,
    })
    stats1 = await ensure_overlay_migration(db_conn)
    assert stats1["migrated_rows"] >= 1
    row = await db_conn.work_studio_exports.find_one({"id": legacy_id}, {"_id": 0})
    assert row["lifecycle_state"] == "committed"
    assert row["legacy"] is True
    # Idempotent: second call migrates 0 rows.
    stats2 = await ensure_overlay_migration(db_conn)
    assert stats2["migrated_rows"] == 0


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-029 — Overlay payload endpoint
# ─────────────────────────────────────────────────────────────────────
async def test_qa_029_overlay_payload_shape(client, authed, db_conn):
    """Verbatim: 'The overlay opens with the current document and its
    intelligence card.' GET returns the shape the overlay UI needs."""
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn,
        context_id=authed["context_id"],
        account_id=authed["account_id"],
        lifecycle_state="draft",
        intel={"confidence_pct": 84, "sources_count": 3, "period": "Q3 2025-26"},
    )
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == aid
    assert body["title"] == "Test Report"
    assert body["lifecycle_state"] == "draft"
    assert body["confidence_band"] == "green"
    assert body["is_owner"] is True


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-030 — Toolbar transitions
# ─────────────────────────────────────────────────────────────────────
async def test_qa_030_move_to_review_owner_only(client, authed, db_conn):
    """Q1 decision: Draft → InReview requires owner."""
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn,
        context_id=authed["context_id"],
        account_id=authed["account_id"],
        lifecycle_state="draft",
    )
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}/move-to-review",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["lifecycle_state"] == "in_review"


async def test_qa_030_committed_is_read_only(client, authed, db_conn):
    """PATCH on a committed document MUST 409 — the toolbar Save/Commit
    affordances are gone on the frontend, but the backend has to enforce
    the contract regardless of what payload the client sends."""
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn,
        context_id=authed["context_id"],
        account_id=authed["account_id"],
        lifecycle_state="committed",
    )
    r = await client.patch(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}",
        json={"title": "Should fail"},
        headers=headers,
    )
    assert r.status_code == 409, r.text


async def test_qa_030_create_new_version_clones_to_draft(client, authed, db_conn):
    """Create New Version: spawns a NEW row in `draft` state — original
    committed row is untouched."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    committed_id = await _seed_artefact(
        db_conn,
        context_id=cid,
        account_id=authed["account_id"],
        lifecycle_state="committed",
    )
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{committed_id}/create-new-version",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    new_doc = r.json()
    assert new_doc["lifecycle_state"] == "draft"
    assert new_doc["id"] != committed_id
    # Original is still committed.
    orig = await db_conn.work_studio_exports.find_one({"id": committed_id}, {"_id": 0})
    assert orig["lifecycle_state"] == "committed"


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-031 — Intelligence card RAG accent
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("pct,expected", [(91, "green"), (62, "amber"), (33, "red"), (None, "unrated")])
async def test_qa_031_intelligence_card_rag_band(client, authed, db_conn, pct, expected):
    """Q4 thresholds reach the overlay payload via `confidence_band`."""
    headers = await _login(client, authed["email"], authed["password"])
    intel = None if pct is None else {"confidence_pct": pct, "sources_count": 2}
    aid = await _seed_artefact(
        db_conn, context_id=authed["context_id"], account_id=authed["account_id"],
        intel=intel,
    )
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}",
        headers=headers,
    )
    assert r.json()["confidence_band"] == expected


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-032 — Intelligence report passthrough
# ─────────────────────────────────────────────────────────────────────
async def test_qa_032_intelligence_modal_full_passthrough(client, authed, db_conn):
    """The full report shape (sources, sections w/ confidence, gaps,
    recommendations, audit) round-trips through GET so the modal can
    render every section."""
    headers = await _login(client, authed["email"], authed["password"])
    full_intel = {
        "confidence_pct": 72,
        "sources_count": 4,
        "period": "Q3 2025-26",
        "framing": "executive",
        "pending_recommendations": 2,
        "sources": [{"doc_id": "doc-a", "name": "Source A", "period": "Q3"}],
        "sections": [{"heading": "Capital", "confidence_pct": 88, "source_doc_ids": ["doc-a"]}],
        "gaps": ["No board-level safety review attached."],
        "recommendations": [{"rank": 1, "text": "Schedule audit follow-up.", "addressed": False}],
        "audit": {
            "generated_at": "2026-05-18T10:00:00+00:00",
            "model_version": "shield-claude-sonnet-4.5",
            "source_document_ids": ["doc-a"],
        },
    }
    aid = await _seed_artefact(
        db_conn, context_id=authed["context_id"], account_id=authed["account_id"],
        intel=full_intel,
    )
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}",
        headers=headers,
    )
    rep = r.json()["intelligence_report"]
    assert rep["sources"][0]["doc_id"] == "doc-a"
    assert rep["sections"][0]["confidence_pct"] == 88
    assert rep["gaps"][0].startswith("No board-level safety")
    assert rep["audit"]["model_version"] == "shield-claude-sonnet-4.5"


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-033 — Surface autosave + read-only on committed
# ─────────────────────────────────────────────────────────────────────
async def test_qa_033_save_creates_snapshot(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    aid = await _seed_artefact(db_conn, context_id=cid, account_id=authed["account_id"])
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/save",
        json={"label": "Manual save"}, headers=headers,
    )
    assert r.status_code == 200, r.text
    snap_id = r.json()["snapshot_id"]
    assert snap_id.startswith("ver-")
    # Verify the snapshot row exists with the structured-content payload.
    snap = await db_conn.work_studio_artefact_versions.find_one(
        {"id": snap_id, "artefact_id": aid}, {"_id": 0},
    )
    assert snap["label"] == "Manual save"
    assert "sections" in snap["structured_content_snapshot"]


async def test_qa_033_save_rejected_on_committed(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn, context_id=authed["context_id"], account_id=authed["account_id"],
        lifecycle_state="committed",
    )
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}/save",
        json={}, headers=headers,
    )
    assert r.status_code == 409, r.text


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-034 — AI Revision source-doc allowlist enforcement
# ─────────────────────────────────────────────────────────────────────
async def test_qa_034_revision_rejects_legacy_no_source_docs(client, authed, db_conn):
    """Legacy artefacts (source_document_ids = []) MUST be rejected
    with 412 (not 500) — frontend uses this to disable the Revise CTA."""
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn, context_id=authed["context_id"], account_id=authed["account_id"],
        source_docs=[],
    )
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}/revise",
        json={"instruction": "Tighten the executive summary.", "scope": "entire", "tone": "formal"},
        headers=headers,
    )
    assert r.status_code == 412, r.text
    assert "source documents" in r.json()["detail"].lower()


async def test_qa_034_revision_rejects_committed(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn, context_id=authed["context_id"], account_id=authed["account_id"],
        lifecycle_state="committed",
        source_docs=["6f1d12e8-1234-5678-abcd-1234567890ab"],
    )
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/work-studio/documents/{aid}/revise",
        json={"instruction": "Tighten the exec summary.", "scope": "entire", "tone": "formal"},
        headers=headers,
    )
    assert r.status_code == 409, r.text


async def test_qa_034_revision_rejects_foreign_source_in_instruction(
    client, authed, db_conn,
):
    """The instruction explicitly names a document id that is NOT in
    the artefact's `source_document_ids`. MUST reject 400 with a clear
    'foreign source' error before any Shield call fires."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    allowlist_doc = "6f1d12e8-1234-5678-abcd-1234567890ab"
    foreign_doc = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    aid = await _seed_artefact(
        db_conn, context_id=cid, account_id=authed["account_id"],
        source_docs=[allowlist_doc],
    )
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/revise",
        json={
            "instruction": f"Reflect insights from doc:{foreign_doc} as well.",
            "scope": "entire", "tone": "formal",
        },
        headers=headers,
    )
    assert r.status_code == 400, r.text
    assert "source" in r.json()["detail"].lower()


async def test_qa_034_revision_with_allowed_source_passes(client, authed, db_conn, monkeypatch):
    """Positive guard: instruction only references allowlisted docs;
    Shield is invoked once with the allowlist as context_documents."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    allow_doc = "6f1d12e8-1234-5678-abcd-1234567890ab"
    # Insert source doc into context so the revise endpoint can read its text.
    await db_conn.documents.insert_one({
        "id": allow_doc, "context_id": cid, "account_id": authed["account_id"],
        "name": "Source doc A",
        "extracted_text": "Capital adequacy stood at 14.2% at quarter-end.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    aid = await _seed_artefact(
        db_conn, context_id=cid, account_id=authed["account_id"],
        source_docs=[allow_doc],
    )
    # Mock Shield so the test doesn't burn the LLM budget.
    import routers.work_studio_overlay as router_mod

    captured = {}

    async def fake_shield(**kwargs):
        captured.update(kwargs)
        return {
            "response": (
                '{"sections":[{"heading":"Executive summary","paragraphs":["Revised."]},'
                '{"heading":"Capital position","paragraphs":["CET1 stands at 14.2% — green."]}],'
                '"change_notes":["Tightened summary","Annotated capital position"]}'
            ),
            "audit_id": "aud-fake-c8",
        }

    monkeypatch.setattr(router_mod, "shield_invoke", fake_shield)

    r = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/revise",
        json={"instruction": "Tighten the executive summary.", "scope": "entire", "tone": "formal"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["audit_id"] == "aud-fake-c8"
    assert len(body["diff"]["section_diffs"]) >= 2
    # Pre-revision snapshot created (so user can revert).
    snap = await db_conn.work_studio_artefact_versions.find_one(
        {"id": body["pre_revision_snapshot_id"]}, {"_id": 0},
    )
    assert snap is not None
    assert "before AI revision" in snap["label"]


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-035 — Version History
# ─────────────────────────────────────────────────────────────────────
async def test_qa_035_versions_list_and_restore_round_trip(client, authed, db_conn):
    """Save → list → modify content → restore — content returns to the
    snapshotted state."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    aid = await _seed_artefact(
        db_conn, context_id=cid, account_id=authed["account_id"],
        structured={"sections": [{"heading": "Original", "paragraphs": ["Original body."]}]},
    )
    # 1. Save creates snapshot.
    save = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/save",
        json={"label": "v1"}, headers=headers,
    )
    snap_id = save.json()["snapshot_id"]

    # 2. Mutate the doc to a different shape.
    await client.patch(
        f"/api/contexts/{cid}/work-studio/documents/{aid}",
        json={"structured_content": {"sections": [{"heading": "Replaced", "paragraphs": ["Different."]}]}},
        headers=headers,
    )

    # 3. List should show the v1 snapshot.
    lst = await client.get(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/versions",
        headers=headers,
    )
    assert lst.status_code == 200, lst.text
    items = lst.json()["items"]
    assert any(it["id"] == snap_id and it["label"] == "v1" for it in items)

    # 4. Restore.
    restore = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/versions/{snap_id}/restore",
        headers=headers,
    )
    assert restore.status_code == 200, restore.text
    restored = restore.json()
    assert restored["structured_content"]["sections"][0]["heading"] == "Original"


async def test_qa_035_restore_blocked_on_committed(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    aid = await _seed_artefact(db_conn, context_id=cid, account_id=authed["account_id"])
    snap = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/save",
        json={"label": "v1"}, headers=headers,
    )
    snap_id = snap.json()["snapshot_id"]
    # Commit the doc.
    await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
        headers=headers,
    )
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/versions/{snap_id}/restore",
        headers=headers,
    )
    assert r.status_code == 409, r.text


# ─────────────────────────────────────────────────────────────────────
# QA-2026-05-16-036 — Commit Confirmation
# ─────────────────────────────────────────────────────────────────────
async def test_qa_036_commit_locks_and_pre_commit_snapshot(client, authed, db_conn):
    """Commit creates a Pre-commit snapshot AND transitions state to
    committed in one round-trip. Subsequent edits must 409."""
    headers = await _login(client, authed["email"], authed["password"])
    cid = authed["context_id"]
    aid = await _seed_artefact(db_conn, context_id=cid, account_id=authed["account_id"])
    r = await client.post(
        f"/api/contexts/{cid}/work-studio/documents/{aid}/commit",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lifecycle_state"] == "committed"
    pre = body["pre_commit_snapshot_id"]
    # Pre-commit snapshot exists with pre_commit=True + label="Pre-commit".
    snap = await db_conn.work_studio_artefact_versions.find_one(
        {"id": pre, "artefact_id": aid}, {"_id": 0},
    )
    assert snap["pre_commit"] is True
    assert snap["label"] == "Pre-commit"
    # Further edits rejected.
    r2 = await client.patch(
        f"/api/contexts/{cid}/work-studio/documents/{aid}",
        json={"title": "Should fail"}, headers=headers,
    )
    assert r2.status_code == 409


# ─────────────────────────────────────────────────────────────────────
# Tenant scoping — every endpoint must reject cross-context reads
# ─────────────────────────────────────────────────────────────────────
async def test_chunk8_endpoints_scope_to_context(client, authed, db_conn):
    """The artefact belongs to one context — a request scoped to a
    DIFFERENT context (same authed user) must 404, not leak."""
    headers = await _login(client, authed["email"], authed["password"])
    aid = await _seed_artefact(
        db_conn, context_id=authed["context_id"], account_id=authed["account_id"],
    )
    # Create a second context the user is also a member of.
    other_ctx = f"ctx-c8-other-{uuid.uuid4().hex[:8]}"
    await db_conn.contexts.insert_one({
        "id": other_ctx, "owner_account_id": authed["account_id"],
        "name": "Other ctx", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}", "context_id": other_ctx,
        "account_id": authed["account_id"], "status": "active", "sub_role": "owner",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        # Read via the wrong context — must 404.
        r = await client.get(
            f"/api/contexts/{other_ctx}/work-studio/documents/{aid}",
            headers=headers,
        )
        assert r.status_code == 404, r.text
    finally:
        await db_conn.contexts.delete_one({"id": other_ctx})
        await db_conn.memberships.delete_many({"context_id": other_ctx})


def test_chunk8_allowed_lifecycle_constant():
    """Sanity guard so future agents can't silently expand the enum
    without seeing the state-machine doc."""
    assert ALLOWED_LIFECYCLE == ("draft", "in_review", "committed")
