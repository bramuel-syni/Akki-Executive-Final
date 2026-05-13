"""Chunk 5 — Create-Summary-Deck / Create-Report regression tests
(WS-R09, WS-R10, WS-R11, WS-R13, WS-R14).

The Decks and Reports tabs each expose three create paths through
`CreateArtefactModal.jsx`:

  - blank                — empty body, user composes from scratch
  - brief                — references db.work_studio_briefs by uuid
  - external_document    — references db.documents by uuid

Pre-Chunk-5 the frontend posted to non-existent backend routes
(`POST /decks`, `POST /cycle/reports/compose`) and the brief picker
forwarded compound aggregate ids (`briefing::<uuid>`) the backend
couldn't read. The fix adds a unified endpoint
`POST /api/contexts/{cid}/work-studio/artefacts` that inserts a
draft row into `db.decks` / `db.reports` and returns a composer
redirect URL.

Six "happy path" tests prove each path works end-to-end.
Cross-tests cover: brief reference is persisted, document reference
is persisted, compound aggregate id is gracefully unwrapped, listing
endpoint shows the new row, and the new listing description field
is emitted (Patch 28D parity).
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


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_conn():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest_asyncio.fixture
async def seeded(db_conn):
    """Seed an account + 1 context + 1 work_studio_brief + 1 document
    so we can exercise all three create-from sources without
    hand-crafting them in every test.
    """
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk5-create-{suffix}@example.com"
    password = "Chunk5Create2026!"
    aid = f"acc-c5-{suffix}"
    cid = f"ctx-c5-{suffix}"
    now = _iso()

    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid, "email": email, "password_hash": hash_password(password),
        "name": "Chunk5 Create Probe", "role": "executive", "created_at": now,
        "default_context_id": cid, "session_version": 0, "verified": True,
    })
    await db_conn.contexts.insert_one({
        "id": cid, "name": "Probe Ctx Chunk5", "type": "executive_personal",
        "status": "active", "owner_account_id": aid, "created_at": now,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": cid, "account_id": aid,
        "status": "active", "role": "executive", "sub_role": "admin", "joined_at": now,
    })

    # Seed a brief (parent + revision_0). Title is distinctive so we
    # can assert on it.
    brief_id = f"brf-c5-{uuid.uuid4().hex[:8]}"
    rev_id = str(uuid.uuid4())
    await db_conn.work_studio_briefs.insert_one({
        "id": brief_id, "account_id": aid, "context_id": cid,
        "source_type": "solva_session", "source_id": "synthetic-c5",
        "title": "Probe Brief Chunk5", "subtitle": "for the chunk-5 test",
        "company_label": "Akki", "document_type": "Board Briefing",
        "programme": None, "active_revision_id": rev_id,
        "revision_count": 1, "created_at": now, "updated_at": now,
    })
    await db_conn.work_studio_brief_revisions.insert_one({
        "id": rev_id, "brief_id": brief_id, "account_id": aid, "context_id": cid,
        "parent_revision_id": None,
        "instruction": "(original)", "scope": "whole_brief",
        "snapshot": {
            "title": "Probe Brief Chunk5",
            "subtitle": "for the chunk-5 test",
            "cover_lead_paragraph": "Opening paragraph for the seed.",
            "sections": [
                {"title": "Section A", "kicker": None,
                 "body_paragraphs": ["Body para one.", "Body para two."],
                 "bullets": [], "tables": []},
            ],
            "closing_recap": "Closing recap line.",
        },
        "diff": [], "claims_changed": 0, "claims_added_without_citation": 0,
        "validation": {"verdict": "validated", "reason": "seed"},
        "llm_audit": {"mode": "seed"}, "created_at": now,
    })

    # Seed a document.
    doc_id = f"doc-c5-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": cid, "account_id": aid,
        "name": "Probe Doc Chunk5.pdf",
        "doc_type": "uploaded", "status": "ready",
        "size": 1024, "mime": "application/pdf",
        "preview": "First 240 chars of the doc preview, used to seed the artefact body.",
        "extracted_text": "Full extracted body.",
        "created_at": now, "updated_at": now,
    })

    yield {
        "email": email, "password": password,
        "account_id": aid, "context_id": cid,
        "brief_id": brief_id, "document_id": doc_id,
    }

    await db_conn.documents.delete_many({"context_id": cid})
    await db_conn.work_studio_brief_revisions.delete_many({"brief_id": brief_id})
    await db_conn.work_studio_briefs.delete_many({"context_id": cid})
    await db_conn.decks.delete_many({"context_id": cid})
    await db_conn.reports.delete_many({"context_id": cid})
    await db_conn.memberships.delete_many({"account_id": aid})
    await db_conn.contexts.delete_one({"id": cid})
    await db_conn.accounts.delete_one({"id": aid})


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


async def _create(client, token, cid, **body):
    return await client.post(
        f"/api/contexts/{cid}/work-studio/artefacts",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


async def _list_kind(client, token, cid, kind):
    r = await client.get(
        f"/api/contexts/{cid}/briefings/aggregates",
        params={"kind": kind, "page_size": 50},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json().get("items") or []


# ---------------------------------------------------------------------------
# 6 happy paths — Deck × {blank, brief, external_document} +
#                 Report × {blank, brief, external_document}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_deck_blank_creates_draft_row(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="Chunk5 blank deck", source="blank",
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["kind"] == "deck"
    assert data["artefact_id"]
    assert data["brief_id"] is None
    assert data["document_id"] is None
    assert data["redirect_url"] == f"/app/studio/composer/deck/{data['artefact_id']}"

    rows = await _list_kind(client, token, seeded["context_id"], "deck")
    assert any(r["name"] == "Chunk5 blank deck" for r in rows), (
        f"new deck did not surface in listing: {rows}"
    )


@pytest.mark.asyncio
async def test_create_deck_from_brief_links_source(client, seeded, db_conn):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="Chunk5 brief-sourced deck",
        source="brief", source_brief_id=seeded["brief_id"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["brief_id"] == seeded["brief_id"]
    deck = await db_conn.decks.find_one({"id": data["artefact_id"]}, {"_id": 0})
    assert deck is not None
    assert deck["brief_id"] == seeded["brief_id"]
    # Body was seeded from the brief snapshot — opening paragraph
    # must appear.
    assert "Opening paragraph for the seed." in (deck.get("body") or "")


@pytest.mark.asyncio
async def test_create_deck_from_external_document_links_doc(client, seeded, db_conn):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="Chunk5 doc-sourced deck",
        source="external_document", source_document_id=seeded["document_id"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["document_id"] == seeded["document_id"]
    deck = await db_conn.decks.find_one({"id": data["artefact_id"]}, {"_id": 0})
    assert deck is not None
    assert deck["source_document_id"] == seeded["document_id"]
    # Body was seeded with the doc preview text.
    assert "preview" in (deck.get("body") or "").lower()


@pytest.mark.asyncio
async def test_create_report_blank_creates_draft_row(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="report", title="Chunk5 blank report", source="blank",
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["kind"] == "report"
    assert data["redirect_url"] == f"/app/studio/composer/report/{data['artefact_id']}"
    rows = await _list_kind(client, token, seeded["context_id"], "report")
    assert any(r["name"] == "Chunk5 blank report" for r in rows)


@pytest.mark.asyncio
async def test_create_report_from_brief_links_source(client, seeded, db_conn):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="report", title="Chunk5 brief-sourced report",
        source="brief", source_brief_id=seeded["brief_id"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    report = await db_conn.reports.find_one({"id": data["artefact_id"]}, {"_id": 0})
    assert report is not None
    assert report["brief_id"] == seeded["brief_id"]
    assert "Opening paragraph for the seed." in (report.get("body") or "")


@pytest.mark.asyncio
async def test_create_report_from_external_document_links_doc(client, seeded, db_conn):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="report", title="Chunk5 doc-sourced report",
        source="external_document", source_document_id=seeded["document_id"],
    )
    assert r.status_code == 201, r.text
    data = r.json()
    report = await db_conn.reports.find_one({"id": data["artefact_id"]}, {"_id": 0})
    assert report is not None
    assert report["source_document_id"] == seeded["document_id"]


# ---------------------------------------------------------------------------
# Contract + safety tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_artefact_rejects_briefing_kind(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    # FastAPI's Literal validation 422s before our explicit check runs;
    # this proves briefing creation cannot accidentally double-write.
    r = await _create(
        client, token, seeded["context_id"],
        kind="briefing", title="Should refuse", source="blank",
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_create_artefact_rejects_missing_brief(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="brief miss", source="brief",
        source_brief_id="brf-does-not-exist",
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_create_artefact_rejects_missing_document(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="report", title="doc miss", source="external_document",
        source_document_id="doc-does-not-exist",
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_create_artefact_rejects_brief_source_without_id(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="no id", source="brief",
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_create_artefact_accepts_compound_brief_id(client, seeded, db_conn):
    """The Work Studio aggregates listing emits compound ids
    (`briefing::<uuid>`). The backend must gracefully unwrap them
    for forward-compatibility with future UI calls that forget to
    strip the prefix."""
    token = await _login(client, seeded["email"], seeded["password"])
    compound = f"briefing::{seeded['brief_id']}"
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="compound id deck",
        source="brief", source_brief_id=compound,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    deck = await db_conn.decks.find_one({"id": data["artefact_id"]}, {"_id": 0})
    # The persisted brief_id must be the raw uuid, not the compound form.
    assert deck["brief_id"] == seeded["brief_id"]


@pytest.mark.asyncio
async def test_list_decks_surfaces_description(client, seeded):
    """Patch 28D parity — `_list_decks` must emit a `description`
    field on each row so the Work Studio listing can render a
    description line under the title."""
    token = await _login(client, seeded["email"], seeded["password"])
    # Create one deck so the listing has a row to inspect.
    r = await _create(
        client, token, seeded["context_id"],
        kind="deck", title="desc probe deck", source="blank",
    )
    assert r.status_code == 201, r.text
    rows = await _list_kind(client, token, seeded["context_id"], "deck")
    probe = next((rr for rr in rows if rr["name"] == "desc probe deck"), None)
    assert probe is not None
    # Description key must always be present (None is fine — the UI
    # decides whether to render the line).
    assert "description" in probe
    assert probe["description"] == "Draft started from blank."


@pytest.mark.asyncio
async def test_list_reports_surfaces_description(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await _create(
        client, token, seeded["context_id"],
        kind="report", title="desc probe report", source="blank",
    )
    assert r.status_code == 201, r.text
    rows = await _list_kind(client, token, seeded["context_id"], "report")
    probe = next((rr for rr in rows if rr["name"] == "desc probe report"), None)
    assert probe is not None
    assert "description" in probe
    assert probe["description"] == "Draft started from blank."


@pytest.mark.asyncio
async def test_create_artefact_unauthorised_context(client, seeded, db_conn):
    """Defence-in-depth — a logged-in user must NOT be able to create
    an artefact under a context they're not a member of."""
    token = await _login(client, seeded["email"], seeded["password"])
    # Seed a second, foreign context the user has no membership of.
    suffix = uuid.uuid4().hex[:8]
    foreign_cid = f"ctx-foreign-{suffix}"
    now = _iso()
    await db_conn.contexts.insert_one({
        "id": foreign_cid, "name": "Foreign", "type": "executive_personal",
        "status": "active", "owner_account_id": "someone-else", "created_at": now,
    })
    try:
        r = await _create(
            client, token, foreign_cid,
            kind="deck", title="should refuse", source="blank",
        )
        # require_context_membership() returns 403 (not a member).
        assert r.status_code == 403, r.text
    finally:
        await db_conn.contexts.delete_one({"id": foreign_cid})
