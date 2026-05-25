"""Backlog-B seed-script regression — exercises `seed_backlog_b_demo`.

Asserts the three POST_T5_BACKLOG seed-data gaps are closed end-to-end:

  T4 gap — at least one Board Pack + one Committee Pack in
           `work_studio_exports` with non-null `structured_content`.
  T5 gap — at least one Cycle with a linked cycle_board_pack
           `work_studio_exports` row carrying `structured_content`.
  T2.3 gap — at least one Objective AND one Project where
             `last_akki_assessment.supporting_docs` resolves to ≥ 2
             docs (the field the Monitor drawer Citations Card reads).

Also asserts idempotency: running the seed twice produces a zero
count delta for every demo-tagged collection.

These tests use the **live Mongo configured in `backend/.env`** because
the seed script is opinionated about deterministic IDs and explicit
context bindings (Bramuel's Tuli contexts). The seed is upsert-only;
re-running here is safe and is in fact the idempotency proof.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")

from scripts.seed_backlog_b_demo import (  # noqa: E402
    seed_async,
    SEED_MARKER,
    BOARD_PACK_ID,
    COMMITTEE_PACK_ID,
    CYCLE_ID,
    CYCLE_COMPILATION_ID,
    OBJECTIVE_ID,
    PROJECT_ID,
    BRAMUEL_NED_TULI_CTX,
    BRAMUEL_EXEC_TULI_CTX,
)
from core import db  # noqa: E402


@pytest.mark.asyncio
async def test_seed_runs_and_inserts_all_required_rows():
    """First-pass: the seed script writes one row of every required
    shape. Re-running is part of the next test."""
    result = await seed_async(verbose=False)

    assert result["board_pack_id"] == BOARD_PACK_ID
    assert result["committee_pack_id"] == COMMITTEE_PACK_ID
    assert result["cycle_id"] == CYCLE_ID
    assert result["cycle_compilation_id"] == CYCLE_COMPILATION_ID
    assert result["objective_id"] == OBJECTIVE_ID
    assert result["project_id"] == PROJECT_ID

    # Post-counts MUST be non-zero for every demo-tagged collection.
    pc = result["post_counts"]
    assert pc["work_studio_exports.demo"] >= 3, pc
    assert pc["cycles.demo"] >= 1, pc
    assert pc["objectives.demo"] >= 1, pc
    assert pc["projects.demo"] >= 1, pc


@pytest.mark.asyncio
async def test_seed_is_idempotent_on_second_run():
    """Re-running the seed against an already-seeded DB must produce a
    zero delta in every demo-tagged collection."""
    # First run (ensures baseline).
    first = await seed_async(verbose=False)
    # Second run — same call, same deterministic IDs.
    second = await seed_async(verbose=False)
    for k, delta in second["delta"].items():
        assert delta == 0, (
            f"Idempotency violation in {k}: delta={delta} on second run. "
            f"Pre={second['pre_counts'][k]} post={second['post_counts'][k]}."
        )
    # Counts must also be equal between the two runs.
    assert first["post_counts"] == second["post_counts"]


@pytest.mark.asyncio
async def test_t4_gap_board_pack_has_non_null_structured_content():
    """T4 gap: at least 1 Board Pack with non-null structured_content."""
    rows = await db.work_studio_exports.find(
        {"kind": "board_pack", "structured_content": {"$ne": None}},
        {"_id": 0, "id": 1, "structured_content": 1, "lifecycle_state": 1},
    ).to_list(50)
    assert len(rows) >= 1, "No Board Pack with non-null structured_content found."
    bp = next((r for r in rows if r["id"] == BOARD_PACK_ID), None)
    assert bp is not None, "Demo Board Pack missing."
    sections = (bp.get("structured_content") or {}).get("sections") or []
    assert len(sections) >= 2, (
        f"Board Pack must have ≥ 2 sections per backlog-b scope; got {len(sections)}."
    )
    for s in sections:
        assert s.get("heading"), "Section missing heading."
        paragraphs = s.get("paragraphs") or []
        assert len(paragraphs) >= 1, "Section missing paragraphs."


@pytest.mark.asyncio
async def test_t4_gap_committee_pack_has_non_null_structured_content():
    """T4 gap: at least 1 Committee Pack with non-null structured_content."""
    rows = await db.work_studio_exports.find(
        {"kind": "committee_pack", "structured_content": {"$ne": None}},
        {"_id": 0, "id": 1, "structured_content": 1},
    ).to_list(50)
    assert len(rows) >= 1, "No Committee Pack with non-null structured_content found."
    cp = next((r for r in rows if r["id"] == COMMITTEE_PACK_ID), None)
    assert cp is not None, "Demo Committee Pack missing."
    sections = (cp.get("structured_content") or {}).get("sections") or []
    assert len(sections) >= 2, (
        f"Committee Pack must have ≥ 2 sections; got {len(sections)}."
    )


@pytest.mark.asyncio
async def test_t5_gap_cycle_has_linked_compilation_with_structured_content():
    """T5 gap: at least 1 cycle linked to a cycle_board_pack
    `work_studio_exports` row carrying `structured_content`."""
    cycle = await db.cycles.find_one(
        {"id": CYCLE_ID}, {"_id": 0}
    )
    assert cycle is not None, "Demo cycle missing."
    assert cycle.get("compilation_export_id") == CYCLE_COMPILATION_ID
    assert cycle.get("status") == "active"

    compile_row = await db.work_studio_exports.find_one(
        {"id": CYCLE_COMPILATION_ID, "kind": "cycle_board_pack"},
        {"_id": 0},
    )
    assert compile_row is not None, "Demo cycle compilation row missing."
    sc = compile_row.get("structured_content") or {}
    sections = sc.get("sections") or []
    assert len(sections) >= 2, (
        f"Cycle compilation must have ≥ 2 sections; got {len(sections)}."
    )


@pytest.mark.asyncio
async def test_t2_3_gap_objective_supporting_docs_resolves_at_least_two():
    """T2.3 gap: at least 1 objective with supporting_docs ≥ 2."""
    obj = await db.objectives.find_one({"id": OBJECTIVE_ID}, {"_id": 0})
    assert obj is not None, "Demo objective missing."
    docs = (
        ((obj.get("last_akki_assessment") or {}).get("supporting_docs")) or []
    )
    assert len(docs) >= 2, (
        f"Objective supporting_docs must resolve to ≥ 2 docs; got {len(docs)}."
    )
    # Each ref must carry both id + name (this is the shape the Citations
    # Card reads in the drawer).
    for d in docs:
        assert d.get("id"), "supporting_docs entry missing id"
        assert d.get("name"), "supporting_docs entry missing name"


@pytest.mark.asyncio
async def test_t2_3_gap_project_supporting_docs_resolves_at_least_two():
    """T2.3 gap: at least 1 project with supporting_docs ≥ 2."""
    prj = await db.projects.find_one({"id": PROJECT_ID}, {"_id": 0})
    assert prj is not None, "Demo project missing."
    docs = (
        ((prj.get("last_akki_assessment") or {}).get("supporting_docs")) or []
    )
    assert len(docs) >= 2, (
        f"Project supporting_docs must resolve to ≥ 2 docs; got {len(docs)}."
    )
    for d in docs:
        assert d.get("id"), "supporting_docs entry missing id"
        assert d.get("name"), "supporting_docs entry missing name"


@pytest.mark.asyncio
async def test_all_seeded_rows_carry_marker():
    """Every seeded row carries `seed_marker = DEMO_T5_BACKLOG` so the
    backlog-b cleanup can be reversed deterministically later."""
    bp = await db.work_studio_exports.find_one({"id": BOARD_PACK_ID})
    cp = await db.work_studio_exports.find_one({"id": COMMITTEE_PACK_ID})
    cyc = await db.cycles.find_one({"id": CYCLE_ID})
    comp = await db.work_studio_exports.find_one({"id": CYCLE_COMPILATION_ID})
    obj = await db.objectives.find_one({"id": OBJECTIVE_ID})
    prj = await db.projects.find_one({"id": PROJECT_ID})
    for row, label in [
        (bp, "board_pack"), (cp, "committee_pack"),
        (cyc, "cycle"), (comp, "cycle_compilation"),
        (obj, "objective"), (prj, "project"),
    ]:
        assert row is not None, f"{label} missing"
        assert row.get("seed_marker") == SEED_MARKER, (
            f"{label} missing seed_marker"
        )


@pytest.mark.asyncio
async def test_seed_does_not_create_orphan_doc_references():
    """The objective/project supporting_docs must reference REAL
    documents already present in the same context — no orphans."""
    obj = await db.objectives.find_one({"id": OBJECTIVE_ID}, {"_id": 0})
    docs = ((obj.get("last_akki_assessment") or {}).get("supporting_docs")) or []
    for d in docs:
        # Synthetic fallback IDs are allowed only if the live env has
        # < 2 documents in the Tuli NED context — which is not the case
        # here (the strategic pack mirror ships 14 docs). Assert
        # against the real-data path.
        if d["id"].startswith("demo-doc-synth-"):
            pytest.skip(
                "Live environment did not have ≥ 2 docs in Bramuel's "
                "Tuli NED context; synthetic fallback used."
            )
        real = await db.documents.find_one(
            {"id": d["id"], "context_id": BRAMUEL_NED_TULI_CTX},
            {"_id": 0, "id": 1, "name": 1},
        )
        assert real is not None, (
            f"supporting_docs references doc id={d['id']} that does not "
            f"live in the Tuli NED ctx — orphan!"
        )
