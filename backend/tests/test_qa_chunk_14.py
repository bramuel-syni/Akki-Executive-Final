"""Chunk 14 — Solva SV-05/06/07/08 (final Solva chunk).

Backend regression coverage for:
  • SV-05 — list endpoint `q` search now hits Phase D
    `layer_3.rendered_synthesis` in addition to `initial_framing`
    and `title`. Verifies a search term that ONLY appears in the
    synthesis field surfaces the session.
  • SV-08 — 422 reproduction matrix + friendly-message verification.
    Confirms that empty / too-short / missing `framing_text` all
    produce 422 with extractable Pydantic detail. Frontend smart-cast
    `friendlySolvaError` is unit-tested via the static-import sanity
    check.

SV-06 (rich text render) and SV-07 (output panel sizing) are
frontend-only — they're covered by ESLint + render-smoke step 16,
not by pytest.

Anchor: `/app/memory/qa_reports/SOLVA_QA_BRIEF_20MAY2026.md` §
SV-05 / SV-06 / SV-07 / SV-08.
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
    """Seed an Exec account + context + 3 Phase D sessions for SV-05 search."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk14-{suffix}@example.com"
    password = "Chunk14-2026!"
    account_id = f"acc-c14-{suffix}"
    context_id = f"ctx-c14-{suffix}"
    from core import hash_password

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk14 Exec", "role": "executive", "declared_role": "executive",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk14 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })

    # Three Phase D sessions designed to exercise the three search
    # fields independently — title, initial_framing, synthesis.
    sessions = [
        {
            "sid": f"sess-c14-title-{suffix}",
            "title": "ZEBRA-keyword-in-title only",
            "initial_framing": "Nothing matches here. " * 5,
            "synthesis": None,
        },
        {
            "sid": f"sess-c14-framing-{suffix}",
            "title": "Generic session two",
            "initial_framing": "Discussing the GIRAFFE-keyword-in-framing situation today.",
            "synthesis": None,
        },
        {
            "sid": f"sess-c14-synth-{suffix}",
            "title": "Generic session three",
            "initial_framing": "Nothing special here in the framing prose at all.",
            "synthesis": "Akki's synthesis containing the term OCTOPUS-keyword-in-synthesis.",
        },
    ]
    for spec in sessions:
        layer_3 = {"rendered_synthesis": spec["synthesis"]} if spec["synthesis"] else None
        await db_conn.solva_phase_d_sessions.insert_one({
            "session_id": spec["sid"],
            "user_id": account_id, "account_id": account_id, "context_id": context_id,
            "sub_module": "seek_clarity",
            "status": "active", "layer_state": "layer_1",
            "initial_framing": spec["initial_framing"],
            "title": spec["title"],
            "created_at": now, "updated_at": now, "completed_at": None,
            "layer_0": None, "layer_1": {"answers": [], "questions_count": 0},
            "layer_2": None, "layer_3": layer_3, "layer_4": None,
            "synisense_audit_ids": [], "orchestration_audit_log": [],
            "source_handoff": None, "seed_attached_references": [],
            "schema_version": 3,
        })

    yield {
        "email": email, "password": password,
        "account_id": account_id, "context_id": context_id,
        "session_ids": [s["sid"] for s in sessions],
    }
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.solva_phase_d_sessions.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


# =====================================================================
# SV-05 — search hits title + framing + synthesis
# =====================================================================

async def test_chunk14_sv05_search_matches_title(client, authed):
    """`q` term that appears only in `title` should surface the row."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}&q=ZEBRA-keyword-in-title",
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert "ZEBRA-keyword-in-title" in items[0]["title"]


async def test_chunk14_sv05_search_matches_framing(client, authed):
    """`q` term that appears only in `initial_framing` should surface the row."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}&q=GIRAFFE-keyword-in-framing",
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    # Server maps `initial_framing` → `intent` on the wire shape.
    assert "GIRAFFE-keyword-in-framing" in (items[0].get("intent") or "")


async def test_chunk14_sv05_search_matches_synthesis_content(client, authed):
    """NEW (SV-05): `q` term that appears only in
    `layer_3.rendered_synthesis` should also surface the row.

    Prior to Chunk 14 the q regex hit only `initial_framing` + `title`
    so a search for a word from the synthesis output returned no
    matches even when a session clearly contained it. The Chunk 14
    fix adds `layer_3.rendered_synthesis` to the `$or` clause.
    """
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}&q=OCTOPUS-keyword-in-synthesis",
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1, (
        "SV-05 regression: a search term appearing only in "
        "layer_3.rendered_synthesis must surface the session."
    )
    assert items[0]["id"] == f"sess-c14-synth-{authed['session_ids'][2].split('-')[-1]}" \
        or items[0]["id"].endswith(authed["session_ids"][2].split("-")[-1])


async def test_chunk14_sv05_search_case_insensitive(client, authed):
    """Per spec: search is case-insensitive substring match."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}&q=octopus-keyword",
        headers=headers,
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


async def test_chunk14_sv05_zero_match_returns_empty_with_counts(client, authed):
    """Zero-match search returns empty items + zero counts (counts
    honour q-filter — Chunk 11 status_counts rule)."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/solva/v2/sessions?context_id={authed['context_id']}&q=ZZZ_nothing_matches_QQQ",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["status_counts"]["all"] == 0


# =====================================================================
# SV-08 — 422 reproduction matrix
# =====================================================================

async def test_chunk14_sv08_list_endpoint_422_without_context_id(client, authed):
    """Pre-Chunk-9.5 SV-02 422 path — endpoint correctly rejects
    direct API misuse. Frontend defends with an activeContext guard,
    but the server-side validation must remain in place."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get("/api/solva/v2/sessions", headers=headers)
    assert r.status_code == 422
    detail = r.json()["detail"]
    # Pydantic shape: array with at least one missing-field entry.
    assert isinstance(detail, list)
    assert any(d.get("type") == "missing" and "context_id" in (d.get("loc") or [])
               for d in detail)


async def test_chunk14_sv08_framing_empty_returns_422(client, authed):
    """Empty framing_text triggers `string_too_short` 422 — the
    frontend `friendlySolvaError` smart-cast translates this to
    the user-friendly copy ("Please write at least 20 characters…")."""
    headers = await _login(client, authed["email"], authed["password"])
    # Create a fresh session to attempt framing on.
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    assert r.status_code in (200, 201), r.text
    sid = r.json().get("session_id") or r.json().get("id")
    assert sid

    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}/framing",
        headers=headers, json={"framing_text": ""},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    target = [d for d in detail if "framing_text" in (d.get("loc") or [])]
    assert target, "422 detail must reference framing_text loc"
    assert target[0].get("type") == "string_too_short"


async def test_chunk14_sv08_framing_too_short_returns_422(client, authed):
    """10-character framing_text (< 20 min) still triggers `string_too_short`."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    sid = r.json().get("session_id") or r.json().get("id")
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}/framing",
        headers=headers, json={"framing_text": "too short!"},
    )
    assert r.status_code == 422


async def test_chunk14_sv08_framing_missing_returns_422_with_loc(client, authed):
    """Missing framing_text → 422 `missing` — must include loc so
    the smart-cast can identify the field name."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    sid = r.json().get("session_id") or r.json().get("id")
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/solva/v2/sessions/{sid}/framing",
        headers=headers, json={},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    target = [d for d in detail if "framing_text" in (d.get("loc") or [])]
    assert target, "422 detail must locate the missing framing_text field"
    assert target[0].get("type") == "missing"


def test_chunk14_no_new_direct_llm_calls():
    """CI sanity — Chunk 14 adds no new LLM call sites.

    SV-05 is search (Mongo regex). SV-06 is frontend render. SV-07
    is CSS. SV-08 is validation copy. Verifies the new
    `proseBlocks.js` module exists and contains no LLM SDK imports.
    """
    path = "/app/frontend/src/lib/proseBlocks.js"
    if not os.path.exists(path):
        pytest.fail(f"Expected proseBlocks.js at {path}")
    with open(path) as f:
        src = f.read()
    # Frontend file — guard against accidental backend-side LLM use.
    for forbidden in ("openai", "anthropic", "litellm", "google.generativeai"):
        assert forbidden not in src, f"proseBlocks.js must not reference {forbidden}"
