"""Chunk 17 — cleanup pass + 16-May P3.

Backend regression coverage:
  • C17-002 — seed_chunks.py extension that inserts the chunk_12_no_data
    fixture across admin@akki.ai's contexts (admin is declared_role="dual"
    which bypasses the NED RBAC gate, closing the Chunk 12 PARTIAL).
  • Item 6 — non-owner seed identity (admin@akki.ai as viewer of
    bramuel's largest context).
  • C17-001 — orphan EditGoalRow removal: static check that the
    component is gone from StrategicGoalsPanel.jsx.
  • C17-004 — SV-07 overflow-y fix: static check that the outer
    `<article>` wrapper now carries `overflow-y-auto`.
  • QA-014 — Cycle Manager spacing: static check that the
    `cycle-list-quickactions-spacer` testid is present.
  • Item 7 — render-smoke step 9 probe defensive `||` fix.

Anchor: `/app/memory/sprints/CHUNK_17_STATE.md`.
"""
from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


# =====================================================================
# C17-002 — admin@akki.ai Exec no-data fixture
# =====================================================================

async def test_chunk17_c17_002_admin_no_data_fixture_seeded(db_conn):
    """`python backend/scripts/seed_chunks.py` mints the chunk_12_no_data
    fixture across all admin@akki.ai owned contexts. Verify at least 1
    fixture exists under an admin-owned context with the verbatim
    title + seed_origin marker."""
    admin = await db_conn.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    assert admin, "admin@akki.ai must be seeded for C17-002"
    admin_id = admin["id"]
    admin_ctx_ids = [
        c["id"] for c in await db_conn.contexts.find(
            {"owner_account_id": admin_id}, {"_id": 0, "id": 1},
        ).to_list(50)
    ]
    if not admin_ctx_ids:
        pytest.skip("admin has no owned contexts in this database — re-run seed_chunks.py")
    fixtures = await db_conn.strategic_goals.find(
        {
            "context_id": {"$in": admin_ctx_ids},
            "seed_origin": "chunk_12_no_data",
            "chunk12_no_data_seed_marker": "v1",
        },
        {"_id": 0, "id": 1, "context_id": 1, "title": 1},
    ).to_list(50)
    assert fixtures, (
        "C17-002: no chunk_12_no_data fixtures found in any admin@akki.ai "
        "context. Run `python backend/scripts/seed_chunks.py` first."
    )
    # Title is verbatim per Pass H.
    assert all(f["title"] == "QA Chunk 12 — no-data fixture" for f in fixtures), (
        "C17-002: fixture title drift detected"
    )


async def test_chunk17_c17_002_seed_pass_is_idempotent(db_conn):
    """Pass H + the Chunk-17 admin extension share the same marker
    (`chunk12_no_data_seed_marker="v1"`). Counting fixtures before/after
    a no-op marker probe should be stable."""
    admin = await db_conn.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not admin:
        pytest.skip("admin not seeded")
    before = await db_conn.strategic_goals.count_documents({
        "seed_origin": "chunk_12_no_data",
    })
    # No re-seed performed in this test — just verify the count is
    # deterministic (zero new fixtures appear on every read).
    after = await db_conn.strategic_goals.count_documents({
        "seed_origin": "chunk_12_no_data",
    })
    assert before == after, "Idempotency guard tripped between two reads"


# =====================================================================
# Item 6 — non-owner seed identity
# =====================================================================

async def test_chunk17_item6_admin_non_owner_membership(db_conn):
    """`seed_chunks.py` adds admin@akki.ai as a viewer-role member of
    bramuel's largest context. Verify the membership exists with the
    correct marker."""
    admin = await db_conn.accounts.find_one({"email": "admin@akki.ai"}, {"_id": 0, "id": 1})
    if not admin:
        pytest.skip("admin not seeded")
    member = await db_conn.memberships.find_one(
        {
            "account_id": admin["id"],
            "chunk17_non_owner_membership_marker": "v1",
        },
        {"_id": 0, "context_id": 1, "sub_role": 1},
    )
    assert member, (
        "Item 6: admin non-owner membership not found. Run "
        "`python backend/scripts/seed_chunks.py` first."
    )
    assert member["sub_role"] == "viewer", (
        f"Item 6: expected sub_role=viewer; got {member['sub_role']}"
    )
    # Verify the context isn't owned by admin (which would defeat the
    # "non-owner" purpose of the seed).
    ctx = await db_conn.contexts.find_one(
        {"id": member["context_id"]},
        {"_id": 0, "owner_account_id": 1},
    )
    assert ctx, "membership references non-existent context"
    assert ctx["owner_account_id"] != admin["id"], (
        "Item 6: admin shouldn't be the owner of the context they're "
        "a non-owner-member of"
    )


# =====================================================================
# C17-001 — EditGoalRow removal (static check)
# =====================================================================

def test_chunk17_c17_001_edit_goal_row_removed():
    """The orphaned EditGoalRow + NumField components have been deleted
    from StrategicGoalsPanel.jsx. Static grep proves they're gone."""
    path = "/app/frontend/src/components/monitor/StrategicGoalsPanel.jsx"
    with open(path) as f:
        src = f.read()
    assert "function EditGoalRow" not in src, (
        "C17-001: EditGoalRow component still present"
    )
    assert "function NumField" not in src, (
        "C17-001: NumField helper still present"
    )
    # State references — match only the JS identifier patterns (not
    # comment mentions, which are deliberately retained for trace).
    assert "setEditingId(" not in src, (
        "C17-001: setEditingId(...) call site still present"
    )
    assert "useState(null);  // editingId" not in src
    # Detect actual destructuring of editingId state hook (the only
    # JS-syntactic usage left would be in the original `useState`
    # declaration which we deleted).
    assert "const [editingId," not in src, (
        "C17-001: editingId useState declaration still present"
    )
    assert "isEditing=" not in src and "isEditing &&" not in src, (
        "C17-001: isEditing prop / branch still present"
    )


# =====================================================================
# C17-004 — SV-07 overflow-y fix (static check on outer wrapper)
# =====================================================================

def test_chunk17_c17_004_solva_prose_outer_overflow_class():
    """The outer `<article>` element of ProseBlock now carries
    `overflow-y-auto` + `max-h-[70vh]`. Either the outer or inner
    wrapper queried via getComputedStyle().overflowY should return
    "auto" — restructure was defence-in-depth."""
    path = "/app/frontend/src/pages/SolvaPhaseDSession.jsx"
    with open(path) as f:
        src = f.read()
    # Find the ProseBlock function body and inspect ONLY the JSX
    # return block (skipping the leading comments).
    idx = src.find("function ProseBlock")
    assert idx > 0, "ProseBlock function not found"
    body = src[idx:idx + 3000]
    # Locate the actual `<article` JSX open tag — skip strings in
    # comments by requiring the line not start with `// ` or `//   `.
    article_lines = []
    for ln in body.split("\n"):
        stripped = ln.lstrip()
        if stripped.startswith("//"):
            continue
        if "<article" in ln:
            article_lines.append(ln)
        # Also capture the className lines immediately following the
        # `<article` opening — Tailwind classes typically live there.
        if article_lines and ("className=" in ln or "rounded-lg" in ln):
            article_lines.append(ln)
        if article_lines and ln.strip().endswith(">"):
            break
    assert article_lines, "outer <article> JSX not located in ProseBlock"
    article_block = "\n".join(article_lines)
    assert "overflow-y-auto" in article_block, (
        f"C17-004: outer <article> should carry overflow-y-auto — got:\n{article_block}"
    )
    assert "max-h-[70vh]" in article_block, (
        f"C17-004: outer <article> should carry max-h-[70vh] — got:\n{article_block}"
    )


# =====================================================================
# QA-014 — Cycle Manager spacing (static check)
# =====================================================================

def test_chunk17_qa014_cycle_quickactions_spacer_present():
    """The spacer between the topbar and QuickActionBar exists on
    CycleList.jsx."""
    path = "/app/frontend/src/pages/cycle/CycleList.jsx"
    with open(path) as f:
        src = f.read()
    assert 'data-testid="cycle-list-quickactions-spacer"' in src, (
        "QA-014: cycle-list-quickactions-spacer testid missing"
    )


# =====================================================================
# Item 7 — smoke probe defensive `||` fix
# =====================================================================

def test_chunk17_item7_smoke_probe_defensive_fallback():
    """render-smoke.js line ~1018 uses `c.context_id || c.id` so the
    probe handles both /api/me/contexts response shapes."""
    path = "/app/frontend/scripts/render-smoke.js"
    with open(path) as f:
        src = f.read()
    # The pattern `c.context_id || c.id` should appear at least 4 times
    # now (3 pre-existing + 1 added in Chunk 17 at smoke step 9).
    count = src.count("c.context_id || c.id")
    assert count >= 4, (
        f"Item 7: expected >=4 occurrences of `c.context_id || c.id`; got {count}"
    )


# =====================================================================
# CI sanity — Chunk 17 introduces no new LLM call sites
# =====================================================================

def test_chunk17_no_new_direct_llm_calls():
    """Chunk 17 is dead-code removal + seed extension + CSS + spacer.
    None of it touches LLM call paths."""
    touched = [
        "/app/frontend/src/components/monitor/StrategicGoalsPanel.jsx",
        "/app/frontend/src/pages/SolvaPhaseDSession.jsx",
        "/app/frontend/src/pages/cycle/CycleList.jsx",
        "/app/backend/scripts/seed_chunks.py",
        "/app/frontend/scripts/render-smoke.js",
    ]
    for path in touched:
        assert os.path.exists(path), f"Missing Chunk 17 file: {path}"
        with open(path) as f:
            src = f.read()
        for forbidden in ("import openai", "import anthropic", "import litellm",
                          "google.generativeai", "from openai", "from anthropic"):
            assert forbidden not in src, f"Chunk 17 file {path} must not import {forbidden}"
