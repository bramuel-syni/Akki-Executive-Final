"""
test_patch_2b2_compilations.py — Patch 2B.2 backend acceptance.

Covers the three new endpoints under
`/api/contexts/{cid}/work-studio/compilations`:
  • POST   — happy path + validation errors
  • GET    — list, scoped to the calling context
  • GET /{id} — detail
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


def _acc(prefix):
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": prefix.title(),
        "name": prefix.title(),
    }


@pytest.fixture(scope="module")
def env():
    return {
        "owner_a": _acc("comp-a"),
        "owner_b": _acc("comp-b"),
        "ctx_a": f"ctx-comp-a-{uuid.uuid4().hex[:10]}",
        "ctx_b": f"ctx-comp-b-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env):
    db = core_mod.db
    for ctx_key, owner_key in (("ctx_a", "owner_a"), ("ctx_b", "owner_b")):
        cid = env[ctx_key]
        owner = env[owner_key]
        await db.contexts.delete_many({"id": cid})
        await db.memberships.delete_many({"context_id": cid})
        await db.compilations.delete_many({"context_id": cid})
        await db.accounts.update_one(
            {"id": owner["id"]}, {"$set": owner}, upsert=True
        )
        await db.contexts.insert_one({
            "id": cid,
            "name": f"P2B2 {ctx_key}",
            "owner_account_id": owner["id"],
            "type": "executive_enterprise",
        })
        await db.memberships.update_one(
            {"context_id": cid, "account_id": owner["id"]},
            {"$set": {
                "context_id": cid,
                "account_id": owner["id"],
                "role": "owner",
                "status": "active",
            }},
            upsert=True,
        )


def _auth(a):
    async def _o(): return a
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


def _valid_body(title="Q1 Report"):
    return {
        "title": title,
        "artefact_type": "report",
        "template_key": "standard",
        "source_ids": ["src-1", "src-2"],
        "contributor_ids": ["acc-x", "acc-y"],
        "cadence_kind": "one_off",
        "cadence_payload": {},
        "formats": ["docx", "pdf"],
    }


@pytest.mark.asyncio
async def test_post_compilation_happy_path(env):
    await _seed(env)
    _auth(env["owner_a"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=_valid_body("Q1 2026 Audit Committee — Report"),
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["title"] == "Q1 2026 Audit Committee — Report"
    assert body["artefact_type"] == "report"
    assert body["formats"] == ["docx", "pdf"]
    assert len(body["agent_cycle_log"]) == 1
    assert body["agent_cycle_log"][0]["kind"] == "created"
    assert body["context_id"] == env["ctx_a"]
    assert "id" in body


@pytest.mark.asyncio
async def test_post_validation_rejects_missing_formats(env):
    _auth(env["owner_a"])
    bad = _valid_body()
    bad["formats"] = []
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=bad,
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_validation_rejects_unknown_artefact_type(env):
    _auth(env["owner_a"])
    bad = _valid_body()
    bad["artefact_type"] = "not_a_real_type"
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=bad,
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_post_validation_rejects_unknown_cadence(env):
    _auth(env["owner_a"])
    bad = _valid_body()
    bad["cadence_kind"] = "intermittently"
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=bad,
        )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_get_list_scopes_to_context(env):
    """A compilation created in ctx_a must not appear when listing ctx_b."""
    await _seed(env)
    # Create one row in each context.
    _auth(env["owner_a"])
    async with _client() as c:
        ra = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=_valid_body("CtxA isolation row"),
        )
        assert ra.status_code == 200, ra.text
        ctx_a_id = ra.json()["id"]
    _auth(env["owner_b"])
    async with _client() as c:
        rb = await c.post(
            f"/api/contexts/{env['ctx_b']}/work-studio/compilations",
            json=_valid_body("CtxB only — Deck"),
        )
        assert rb.status_code == 200, rb.text
        ctx_b_id = rb.json()["id"]

    body_a = await _list(env["ctx_a"], env["owner_a"])
    body_b = await _list(env["ctx_b"], env["owner_b"])

    ids_a = {it["id"] for it in body_a["items"]}
    ids_b = {it["id"] for it in body_b["items"]}
    assert ctx_a_id in ids_a
    assert ctx_b_id in ids_b
    assert ctx_a_id not in ids_b
    assert ctx_b_id not in ids_a


async def _list(cid, owner):
    _auth(owner)
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/work-studio/compilations")
        assert r.status_code == 200
        return r.json()


@pytest.mark.asyncio
async def test_get_detail_round_trips(env):
    _auth(env["owner_a"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=_valid_body("Detail round-trip"),
        )
        cid_a = env["ctx_a"]
        new_id = r.json()["id"]
        d = await c.get(f"/api/contexts/{cid_a}/work-studio/compilations/{new_id}")
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["id"] == new_id
    assert body["title"] == "Detail round-trip"


@pytest.mark.asyncio
async def test_get_detail_404_when_cross_context(env):
    """A compilation id from ctx_a should 404 when fetched under ctx_b."""
    _auth(env["owner_a"])
    async with _client() as c:
        r = await c.post(
            f"/api/contexts/{env['ctx_a']}/work-studio/compilations",
            json=_valid_body("Cross-context guard"),
        )
        new_id = r.json()["id"]
    _auth(env["owner_b"])
    async with _client() as c:
        d = await c.get(f"/api/contexts/{env['ctx_b']}/work-studio/compilations/{new_id}")
    assert d.status_code == 404, d.text
