"""T3 — Cross-surface flows.

Backend coverage:
  • T3.1 — `POST /api/contexts/{cid}/work-studio/from-document` accepts
    all 5 D5 kinds, creates a Draft row in work_studio_exports, returns
    the G8 ratified redirect_url for board_pack / committee_pack vs
    the listing-with-pulse URL for the other three kinds.
  • Validation: kind outside the 5-set → 422; missing source doc → 404.

T3.3 frontend wire checks live in `tests/test_t3_frontend_wire.py`.
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


def _acc(prefix: str) -> dict:
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": prefix.title(),
        "name": prefix.title(),
    }


@pytest.fixture(scope="module")
def env() -> dict:
    return {
        "owner": _acc("t3-owner"),
        "ctx": f"ctx-t3-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env: dict) -> None:
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    for c in ("memberships", "documents", "work_studio_exports"):
        await getattr(db, c).delete_many({"context_id": cid})
    await db.accounts.update_one(
        {"id": env["owner"]["id"]},
        {"$set": env["owner"]},
        upsert=True,
    )
    await db.contexts.insert_one({
        "id": cid, "name": "T3 Co",
        "owner_account_id": env["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid,
            "account_id": env["owner"]["id"],
            "role": "executive", "sub_role": "admin", "status": "active",
        }},
        upsert=True,
    )


def _auth(account: dict) -> None:
    async def _o():
        return account
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _insert_doc(cid: str, name: str = "Q1 Memo.pdf") -> str:
    did = f"doc-{uuid.uuid4().hex[:10]}"
    await core_mod.db.documents.insert_one({
        "id": did,
        "context_id": cid,
        "name": name,
        "original_filename": name,
        "mime_type": "application/pdf",
        "size_bytes": 1024,
        "status": "extracted",
        "source_channel": "upload",
        "doc_kind": "policy",
        "created_at": "2026-05-25T00:00:00Z",
    })
    return did


# ── T3.1 — happy path for each of the 5 D5 kinds ───────────────────────
@pytest.mark.parametrize("kind,page_route", [
    ("board_pack",     True),
    ("committee_pack", True),
    ("minutes",        False),
    ("deck",           False),
    ("report",         False),
])
@pytest.mark.asyncio
async def test_t3_1_from_document_creates_draft_artefact(env, kind, page_route):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    did = await _insert_doc(cid, name="Q1 Memo.pdf")
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{cid}/work-studio/from-document",
            json={"kind": kind, "source_doc_id": did},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == kind
    assert body["title"] == "Q1 Memo.pdf"
    assert body["artefact_id"]
    # G8 ratified routing — Board Pack + Committee Pack land on the
    # dedicated page; the other three on the listing with pulse.
    if page_route:
        assert body["redirect_url"] == f"/app/work-studio/document/{body['artefact_id']}"
    else:
        assert body["redirect_url"].startswith(f"/app/work-studio?kind={kind}&pulse=")

    # Persisted row in work_studio_exports.
    row = await core_mod.db.work_studio_exports.find_one(
        {"id": body["artefact_id"]}, {"_id": 0},
    )
    assert row is not None
    assert row["context_id"] == cid
    assert row["kind"] == kind
    assert row["title"] == "Q1 Memo.pdf"
    assert row["status"] == "draft"
    assert row["source_document_ids"] == [did]
    assert row["origin"]["source"] == "document_journal_add"


@pytest.mark.asyncio
async def test_t3_1_from_document_rejects_unknown_kind(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    did = await _insert_doc(cid)
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{cid}/work-studio/from-document",
            json={"kind": "white_paper", "source_doc_id": did},
        )
    # Pydantic Literal mismatch → FastAPI returns 422 with validation
    # error referencing the input.
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_t3_1_from_document_rejects_missing_source(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{cid}/work-studio/from-document",
            json={"kind": "deck", "source_doc_id": "doc-does-not-exist"},
        )
    assert r.status_code == 404, r.text
    assert "not found" in r.text.lower()
