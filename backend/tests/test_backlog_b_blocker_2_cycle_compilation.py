"""Backlog-B Blocker 2 — Cycle Page wire payload exposes the G6 chip
linkage regardless of which collection holds the compilation reference.

The `GET /api/contexts/{cid}/cycles/{cycle_id}` endpoint (in
`backend/routers/cycles.py`) computes a `compilation` block via a
defensive multi-path lookup:

    1. cycles.compilation_export_id
    2. cycles.compiled_brief_id
    3. work_studio_exports query (kind=cycle_board_pack +
       source_cycle_id = cycle_id)

This integration test asserts that ALL THREE linkage paths surface
the `compilation` block correctly so the Cycle Page's CompilationStep
can pre-populate `out` and render the DOCX/PDF/PPTX chips.

Anti-false-green: each path is tested in isolation — the others are
deliberately cleared on the cycle row so the test fails if the path
in question is broken.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


@pytest.fixture
def env() -> dict:
    return {
        "owner": _acc("blocker2-owner"),
        "ctx": f"ctx-blocker2-{uuid.uuid4().hex[:10]}",
    }


async def _seed_env(env: dict) -> None:
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    for c in ("memberships", "cycles", "cycle_agendas",
              "work_studio_exports"):
        await getattr(db, c).delete_many({"context_id": cid})
    await db.accounts.update_one(
        {"id": env["owner"]["id"]},
        {"$set": env["owner"]},
        upsert=True,
    )
    await db.contexts.insert_one({
        "id": cid, "name": "Blocker2 Co",
        "owner_account_id": env["owner"]["id"],
        "type": "executive_personal",
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


async def _make_cycle_and_compilation(
    cid: str, owner_id: str,
    *,
    compilation_export_id_on_cycle: str | None = None,
    compiled_brief_id_on_cycle: str | None = None,
    source_cycle_id_on_export: str | None = None,
) -> tuple[str, str]:
    """Build one cycle + one cycle_board_pack export with the linkage
    path(s) chosen by the caller.

    Each caller picks exactly one or two linkage paths so the test
    asserts the correct path resolved end-to-end.
    """
    cycle_id = f"cyc-{uuid.uuid4().hex[:10]}"
    export_id = f"exp-{uuid.uuid4().hex[:10]}"
    cycle_row = {
        "id": cycle_id, "context_id": cid, "account_id": owner_id,
        "title": "Blocker2 cycle", "status": "active",
        "created_at": "2026-05-25T00:00:00Z",
    }
    if compilation_export_id_on_cycle:
        cycle_row["compilation_export_id"] = compilation_export_id_on_cycle
    if compiled_brief_id_on_cycle:
        cycle_row["compiled_brief_id"] = compiled_brief_id_on_cycle
    await core_mod.db.cycles.insert_one(cycle_row)
    # Shell agenda — required for the legacy single-cycle endpoints.
    await core_mod.db.cycle_agendas.insert_one({
        "id": cycle_id, "cycle_id": cycle_id, "context_id": cid,
        "account_id": owner_id, "title": cycle_row["title"],
        "items": [], "status": "active",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    export_row = {
        "id": export_id, "context_id": cid, "account_id": owner_id,
        "kind": "cycle_board_pack",
        "title": "Blocker2 compilation",
        "file_name": "blocker2_compilation.docx",
        "output_format": "docx",
        "status": "complete", "lifecycle_state": "in_review",
        "structured_content": {
            "sections": [
                {"heading": "S1", "paragraphs": ["p1", "p2"]},
                {"heading": "S2", "paragraphs": ["p3"]},
            ],
        },
        "sensitivity_band": "CONFIDENTIAL",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    }
    if source_cycle_id_on_export:
        export_row["source_cycle_id"] = source_cycle_id_on_export
    await core_mod.db.work_studio_exports.insert_one(export_row)
    return cycle_id, export_id


# ── Path 1 — cycles.compilation_export_id ───────────────────────────
@pytest.mark.asyncio
async def test_blocker_2_path_1_compilation_export_id_resolves(env):
    await _seed_env(env)
    _auth(env["owner"])
    cid = env["ctx"]
    # Build export FIRST so we know its id.
    cycle_id, export_id = await _make_cycle_and_compilation(
        cid, env["owner"]["id"],
        compilation_export_id_on_cycle=None,
        compiled_brief_id_on_cycle=None,
        source_cycle_id_on_export=None,
    )
    # Now patch the cycle row to point at the export via path 1 only.
    await core_mod.db.cycles.update_one(
        {"id": cycle_id},
        {"$set": {"compilation_export_id": export_id}},
    )
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/cycles/{cycle_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    compilation = body.get("compilation")
    assert compilation is not None, "Path 1 did not resolve"
    assert compilation["export_id"] == export_id
    assert compilation["linkage_path"] == "cycles.compilation_export_id"
    assert compilation["output_format"] == "docx"


# ── Path 2 — cycles.compiled_brief_id ───────────────────────────────
@pytest.mark.asyncio
async def test_blocker_2_path_2_compiled_brief_id_resolves(env):
    await _seed_env(env)
    _auth(env["owner"])
    cid = env["ctx"]
    cycle_id, export_id = await _make_cycle_and_compilation(
        cid, env["owner"]["id"],
        compilation_export_id_on_cycle=None,
        compiled_brief_id_on_cycle=None,
        source_cycle_id_on_export=None,
    )
    await core_mod.db.cycles.update_one(
        {"id": cycle_id},
        {"$set": {"compiled_brief_id": export_id}},
    )
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/cycles/{cycle_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    compilation = body.get("compilation")
    assert compilation is not None, "Path 2 did not resolve"
    assert compilation["export_id"] == export_id
    assert compilation["linkage_path"] == "cycles.compiled_brief_id"


# ── Path 3 — work_studio_exports.source_cycle_id ────────────────────
@pytest.mark.asyncio
async def test_blocker_2_path_3_source_cycle_id_resolves(env):
    """Cycle row carries NO linkage; only the work_studio_exports row
    carries `source_cycle_id`. The defensive lookup must still find it."""
    await _seed_env(env)
    _auth(env["owner"])
    cid = env["ctx"]
    cycle_id, export_id = await _make_cycle_and_compilation(
        cid, env["owner"]["id"],
        compilation_export_id_on_cycle=None,
        compiled_brief_id_on_cycle=None,
        source_cycle_id_on_export=None,
    )
    # Patch the export, leave the cycle row clean.
    await core_mod.db.work_studio_exports.update_one(
        {"id": export_id},
        {"$set": {"source_cycle_id": cycle_id}},
    )
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/cycles/{cycle_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    compilation = body.get("compilation")
    assert compilation is not None, "Path 3 did not resolve"
    assert compilation["export_id"] == export_id
    assert compilation["linkage_path"] == "work_studio_exports.source_cycle_id"


# ── Negative — no linkage, no compilation block ─────────────────────
@pytest.mark.asyncio
async def test_blocker_2_no_linkage_no_compilation_block(env):
    """A cycle with no linkage at all and an unrelated work_studio
    export row in the same context must NOT surface a compilation."""
    await _seed_env(env)
    _auth(env["owner"])
    cid = env["ctx"]
    cycle_id = f"cyc-{uuid.uuid4().hex[:10]}"
    await core_mod.db.cycles.insert_one({
        "id": cycle_id, "context_id": cid,
        "account_id": env["owner"]["id"],
        "title": "Unlinked cycle", "status": "active",
        "created_at": "2026-05-25T00:00:00Z",
    })
    await core_mod.db.cycle_agendas.insert_one({
        "id": cycle_id, "cycle_id": cycle_id, "context_id": cid,
        "account_id": env["owner"]["id"], "title": "x",
        "items": [], "status": "active",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    # Insert an unrelated cycle_board_pack referencing a DIFFERENT cycle.
    await core_mod.db.work_studio_exports.insert_one({
        "id": f"exp-{uuid.uuid4().hex[:10]}",
        "context_id": cid,
        "account_id": env["owner"]["id"],
        "kind": "cycle_board_pack",
        "source_cycle_id": "some-other-cycle",
        "structured_content": {"sections": [{"heading": "h", "paragraphs": ["p"]}]},
        "status": "complete",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/cycles/{cycle_id}")
    assert r.status_code == 200, r.text
    assert r.json().get("compilation") is None


# ── Negative — linkage but export has empty sections ────────────────
@pytest.mark.asyncio
async def test_blocker_2_linkage_without_structured_content_no_compilation(env):
    """A cycle with a linkage to an export that has NO
    `structured_content.sections` must NOT surface a compilation
    block — the G6 chips would render but the download would 409."""
    await _seed_env(env)
    _auth(env["owner"])
    cid = env["ctx"]
    cycle_id = f"cyc-{uuid.uuid4().hex[:10]}"
    export_id = f"exp-{uuid.uuid4().hex[:10]}"
    await core_mod.db.cycles.insert_one({
        "id": cycle_id, "context_id": cid,
        "account_id": env["owner"]["id"],
        "title": "Empty-sections cycle", "status": "active",
        "compilation_export_id": export_id,
        "created_at": "2026-05-25T00:00:00Z",
    })
    await core_mod.db.cycle_agendas.insert_one({
        "id": cycle_id, "cycle_id": cycle_id, "context_id": cid,
        "account_id": env["owner"]["id"], "title": "x",
        "items": [], "status": "active",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    await core_mod.db.work_studio_exports.insert_one({
        "id": export_id, "context_id": cid,
        "account_id": env["owner"]["id"],
        "kind": "cycle_board_pack",
        "structured_content": None,   # explicit empty
        "status": "complete",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/cycles/{cycle_id}")
    assert r.status_code == 200, r.text
    assert r.json().get("compilation") is None


# ── End-to-end against the seeded demo cycle ────────────────────────
@pytest.mark.asyncio
async def test_blocker_2_seeded_demo_cycle_surfaces_compilation():
    """The backlog-b seed writes `demo-t5backlog-cycle-001` with the
    Path 1 linkage. The GET endpoint must surface the compilation
    block so the Cycle Page chips render in the browser.

    This is the live-data assertion the e1_tester verdict needs.
    """
    # Re-run the seed to guarantee the rows exist (idempotent).
    from scripts.seed_backlog_b_demo import (
        seed_async, CYCLE_ID, CYCLE_COMPILATION_ID,
        BRAMUEL_NED_TULI_CTX, BRAMUEL_ACCOUNT_ID,
    )
    await seed_async(verbose=False)
    _auth({
        "id": BRAMUEL_ACCOUNT_ID,
        "email": "bramuel@syni.ai",
        "display_name": "Bramuel",
        "name": "Bramuel",
    })
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{BRAMUEL_NED_TULI_CTX}/cycles/{CYCLE_ID}"
        )
    assert r.status_code == 200, r.text
    body = r.json()
    compilation = body.get("compilation")
    assert compilation is not None, "Seed cycle did not surface compilation"
    assert compilation["export_id"] == CYCLE_COMPILATION_ID
    assert compilation["kind"] == "cycle_board_pack"
    assert compilation["output_format"] == "docx"
    assert compilation["linkage_path"] in {
        "cycles.compilation_export_id",
        "cycles.compiled_brief_id",
        "work_studio_exports.source_cycle_id",
    }
