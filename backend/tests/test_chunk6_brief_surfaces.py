"""Chunk 6 — Brief surfaces regression tests (WS-R01, WS-R17, WS-R18, WS-R19).

Covers four QA tickets at once:

- WS-R17: aggregate detail for `briefing`/`deck`/`report` kinds
  previously fell through to `_detail_cycle_committee_pack` and
  raised `Bad aggregate id.` 400. Now each kind has its own detail
  handler returning the artefact row + a `composer_url`.
- WS-R01: every detail response now carries `composer_url` so the
  drawer's primary CTA has a real target (no more `undefined`).
- WS-R18: chat → brief flow returns clean `{code, message}` 409s.
  The frontend (tested separately) maps these to user-readable
  toast titles.
- WS-R19: long chat titles no longer truncate at 70 chars; chat
  source bypasses the submodule prefix entirely via `title_override`.

All tests pass.
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
from work_studio.brief import build_brief_from_solva


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
    """Seed an account + context + one briefing + one deck + one report
    + one chat with assistant messages + one empty chat.

    Cleanup at teardown."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk6-probe-{suffix}@example.com"
    password = "Chunk6Probe2026!"
    aid = f"acc-c6-{suffix}"
    cid = f"ctx-c6-{suffix}"
    now = _iso()

    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid, "email": email, "password_hash": hash_password(password),
        "name": "Chunk6 Probe", "role": "executive", "created_at": now,
        "default_context_id": cid, "session_version": 0, "verified": True,
    })
    await db_conn.contexts.insert_one({
        "id": cid, "name": "Probe Ctx Chunk6", "type": "executive_personal",
        "status": "active", "owner_account_id": aid, "created_at": now,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": cid, "account_id": aid,
        "status": "active", "role": "executive", "sub_role": "admin", "joined_at": now,
    })

    # Briefing row.
    brief_id = f"brf-c6-{uuid.uuid4().hex[:8]}"
    rev_id = str(uuid.uuid4())
    await db_conn.work_studio_briefs.insert_one({
        "id": brief_id, "account_id": aid, "context_id": cid,
        "source_type": "solva_session", "source_id": "synthetic-c6",
        "title": "Chunk6 probe brief",
        "subtitle": "Brief subtitle for probe",
        "company_label": "Akki", "document_type": "Board Briefing",
        "programme": None, "active_revision_id": rev_id,
        "revision_count": 1, "created_at": now, "updated_at": now,
    })
    await db_conn.work_studio_brief_revisions.insert_one({
        "id": rev_id, "brief_id": brief_id, "account_id": aid, "context_id": cid,
        "parent_revision_id": None, "instruction": "(seed)", "scope": "whole_brief",
        "snapshot": {"title": "Chunk6 probe brief", "sections": []},
        "diff": [], "claims_changed": 0, "claims_added_without_citation": 0,
        "validation": {"verdict": "validated", "reason": "seed"},
        "llm_audit": {"mode": "seed"}, "created_at": now,
    })

    # Deck row.
    deck_id = f"dck-c6-{uuid.uuid4().hex[:8]}"
    await db_conn.decks.insert_one({
        "id": deck_id, "account_id": aid, "context_id": cid,
        "title": "Chunk6 probe deck",
        "description": "Deck description for probe",
        "body": "", "status": "draft", "slides": [],
        "created_at": now, "updated_at": now,
    })

    # Report row.
    report_id = f"rpt-c6-{uuid.uuid4().hex[:8]}"
    await db_conn.reports.insert_one({
        "id": report_id, "account_id": aid, "context_id": cid,
        "title": "Chunk6 probe report",
        "description": "Report description for probe",
        "body": "", "status": "draft", "chain": [],
        "created_at": now, "updated_at": now,
    })

    # Chat with assistant messages.
    full_chat_id = f"chat-c6-full-{uuid.uuid4().hex[:8]}"
    long_title = (
        "Q3 board meeting — strategic review of expansion plans into the "
        "East African corridor with attendant capital implications"
    )  # 119 chars
    await db_conn.chats.insert_one({
        "id": full_chat_id, "account_id": aid, "context_id": cid,
        "title": long_title, "status": "active", "model_id": "claude-test",
        "message_count": 2, "created_at": now, "updated_at": now,
    })
    await db_conn.chat_messages.insert_one({
        "id": str(uuid.uuid4()), "chat_id": full_chat_id,
        "role": "user", "content": "Tell me about Q3.", "created_at": now,
    })
    await db_conn.chat_messages.insert_one({
        "id": str(uuid.uuid4()), "chat_id": full_chat_id,
        "role": "assistant",
        "content": "The Q3 board discussion centred on the proposed expansion into Nairobi…",
        "created_at": now,
    })

    # Empty chat (no assistant messages).
    empty_chat_id = f"chat-c6-empty-{uuid.uuid4().hex[:8]}"
    await db_conn.chats.insert_one({
        "id": empty_chat_id, "account_id": aid, "context_id": cid,
        "title": "Empty chat", "status": "active", "model_id": "claude-test",
        "message_count": 0, "created_at": now, "updated_at": now,
    })

    yield {
        "email": email, "password": password,
        "account_id": aid, "context_id": cid,
        "brief_id": brief_id, "deck_id": deck_id, "report_id": report_id,
        "full_chat_id": full_chat_id, "empty_chat_id": empty_chat_id,
        "long_title": long_title,
    }

    await db_conn.chat_messages.delete_many({"chat_id": {"$in": [full_chat_id, empty_chat_id]}})
    await db_conn.chats.delete_many({"context_id": cid})
    await db_conn.work_studio_brief_revisions.delete_many({"brief_id": brief_id})
    await db_conn.work_studio_briefs.delete_many({"context_id": cid})
    await db_conn.decks.delete_many({"context_id": cid})
    await db_conn.reports.delete_many({"context_id": cid})
    await db_conn.memberships.delete_many({"account_id": aid})
    await db_conn.contexts.delete_one({"id": cid})
    await db_conn.accounts.delete_one({"id": aid})


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# WS-R17 / WS-R01 — aggregate detail for non-cycle kinds + composer_url
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_aggregate_detail_for_briefing_kind_returns_row(client, seeded):
    """Pre-Chunk-6 this returned 400 'Bad aggregate id.'"""
    token = await _login(client, seeded["email"], seeded["password"])
    aid = f"briefing::{seeded['brief_id']}"
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates/{aid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "briefing"
    assert data["name"] == "Chunk6 probe brief"
    assert data["artefact_id"] == seeded["brief_id"]
    assert data["composer_url"] == f"/app/studio/composer/briefing/{seeded['brief_id']}"


@pytest.mark.asyncio
async def test_aggregate_detail_for_deck_kind_returns_row(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    aid = f"deck::{seeded['deck_id']}"
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates/{aid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "deck"
    assert data["name"] == "Chunk6 probe deck"
    assert data["composer_url"] == f"/app/studio/composer/deck/{seeded['deck_id']}"


@pytest.mark.asyncio
async def test_aggregate_detail_for_report_kind_returns_row(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    aid = f"report::{seeded['report_id']}"
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates/{aid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "report"
    assert data["composer_url"] == f"/app/studio/composer/report/{seeded['report_id']}"


@pytest.mark.asyncio
async def test_aggregate_detail_missing_briefing_returns_404(client, seeded):
    """Defence-in-depth — a bogus uuid in the same kind should 404, not 400."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates/briefing::bogus-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_aggregate_detail_unknown_kind_still_400(client, seeded):
    """`_split_agg_id` gates on _AGG_KINDS, so an unknown kind 400s
    cleanly. This proves the new dispatch didn't regress that path."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/contexts/{seeded['context_id']}/briefings/aggregates/unknown::abc",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# WS-R18 — chat → brief surfaces clean {code, message} payloads
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_empty_returns_clean_409_payload(client, seeded):
    """The 'Seed failed' toast in SourceStep.jsx is fed by this 409.
    The payload must carry a `code` and `message` so the frontend
    apiErrorCode/apiErrorMessage helpers can branch on it."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_type": "chat_artefact",
            "source_id": seeded["empty_chat_id"],
            "kind": "briefing",
        },
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "chat_empty"
    assert "no assistant content" in detail["message"].lower()


@pytest.mark.asyncio
async def test_chat_with_messages_seeds_brief_successfully(client, seeded, db_conn):
    """The happy-path of the WS-R18 flow — a chat with assistant
    content must seed a brief without throwing."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_type": "chat_artefact",
            "source_id": seeded["full_chat_id"],
            "kind": "briefing",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "briefing"
    assert data["artefact_id"]
    assert data["brief_id"]
    # Persisted brief carries the chat's full title (no submodule prefix).
    parent = await db_conn.work_studio_briefs.find_one(
        {"id": data["brief_id"]}, {"_id": 0},
    )
    assert parent is not None
    assert parent["title"] == seeded["long_title"]


# ---------------------------------------------------------------------------
# WS-R19 — title_override + 200-char truncation
# ---------------------------------------------------------------------------
def test_build_brief_respects_title_override():
    """Chat sources pass title_override; the brief.title must match
    the override verbatim with no submodule prefix."""
    session = {
        "submodule": "seek_clarity",
        "intent": "ignored intent",
        "synthesis": {"body": "Some body text."},
    }
    brief = build_brief_from_solva(
        session, company_label="Akki", document_type="Board Briefing",
        programme=None, depth="board_summary", fidelity="low",
        title_override="My specific chat title that I named myself",
    )
    assert brief.title == "My specific chat title that I named myself"
    # No "Clarity Read:" prefix.
    assert "Clarity Read" not in brief.title


def test_build_brief_truncation_raised_to_200():
    """Pre-Chunk-6 the intent was capped at 70 chars. Now 200."""
    long_intent = "x" * 150
    session = {
        "submodule": "develop_strategy",
        "intent": long_intent,
        "synthesis": {"body": "Body."},
    }
    brief = build_brief_from_solva(
        session, company_label="Akki", document_type="Board Briefing",
        programme=None, depth="board_summary", fidelity="low",
    )
    # The 150-char intent fits under the new 200-char cap. No ellipsis.
    assert "…" not in brief.title
    assert long_intent in brief.title


def test_build_brief_caps_runaway_titles_at_200():
    """Defence-in-depth: a 500-char title still gets capped (this
    protects the DOCX cover layout from runaway titles)."""
    pathological = "y" * 500
    session = {"submodule": "seek_clarity", "intent": pathological, "synthesis": {"body": ""}}
    brief = build_brief_from_solva(
        session, company_label="Akki", document_type="Board Briefing",
        programme=None, depth="board_summary", fidelity="low",
    )
    # title is "Clarity Read: yyy…yyy…" — pull out the capped portion.
    assert brief.title.endswith("…")
    assert len(brief.title) <= 250  # 13 (prefix) + 200 + 1 ellipsis


@pytest.mark.asyncio
async def test_long_chat_title_survives_docx_render(client, seeded, db_conn):
    """End-to-end: a chat title with ≥100 chars seeds a brief whose
    rendered DOCX contains the full title (no truncation, no
    submodule prefix)."""
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/work-studio/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "source_type": "chat_artefact",
            "source_id": seeded["full_chat_id"],
            "kind": "briefing",
        },
    )
    assert r.status_code == 200
    brief_id = r.json()["brief_id"]
    # Render the DOCX.
    exp = await client.post(
        "/api/work_studio/exports",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Active-Context": seeded["context_id"],
        },
        json={
            "source_id": brief_id, "source_type": "work_studio_brief",
            "format": "docx", "depth": "board_summary", "fidelity": "low",
            "company_label": "Akki", "document_type": "Board Briefing",
            "programme": None,
        },
    )
    assert exp.status_code == 200, exp.text
    export_id = exp.json()["export_id"]
    # The DOCX bytes are served via the export download endpoint.
    download = await client.get(
        f"/api/work_studio/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200, download.text
    raw = download.content
    # DOCX is a zip; document.xml carries the text body.
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open("word/document.xml") as f:
            xml = f.read().decode("utf-8", errors="replace")
    # The full chat title must appear in the rendered DOCX.
    assert seeded["long_title"] in xml, (
        "long title was truncated in DOCX. Surrounding xml: "
        f"{xml[xml.find('Q3 board'):xml.find('Q3 board')+200] if 'Q3 board' in xml else '(not present)'}"
    )
    # No submodule prefix on this brief — title_override was set.
    assert "Clarity Read:" not in xml
