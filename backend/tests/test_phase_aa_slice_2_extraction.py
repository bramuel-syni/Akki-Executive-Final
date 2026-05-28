"""
Phase AA-slice-2 (2026-05-27) — LLM extraction service CI guards.

Lock surface:

  Source-strict (module shape) —
    * `extract_from_document` is the single public entry point.
    * `ExtractionResult` dataclass with the 4 expected fields.
    * `GOALS_PROMPT_TEMPLATE` + `TASKS_PROMPT_TEMPLATE` exposed,
      each leads with the expected anchor sentence.
    * `MAX_CHARS_BEFORE_CHUNK == 50_000`, `MAX_ROWS_PER_CHUNK == 20`,
      `CHUNK_SIZE_CHARS == 18_000`.

  Runtime — `call_llm` is patched to return canned responses:
    * extract_tasks=True + good payload → tasks_initiatives rows
      persisted with `extracted_by="llm"` + `source_document_id`.
    * extract_goals=True + good payload → strategic_goals rows
      persisted with `extracted_by="llm"` + `source_doc_id`.
    * Bad row in payload → logged to `extraction_failures`, valid
      rows still inserted.
    * Empty extracted_text → no LLM call, returns zeros.
    * Idempotency: second call with same (doc, kind) returns
      `idempotent_skip=True` and writes no new rows.
    * force=True bypasses idempotency.
    * Chunking: > MAX_CHARS_BEFORE_CHUNK text triggers ≥2 chunks,
      LLM called once per chunk.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from services.tasks_initiatives import extraction as ex


# ─────────────────────────────────────────────────────────────────
# Source-strict module shape
# ─────────────────────────────────────────────────────────────────


def test_aa2_public_api_exposed() -> None:
    assert callable(ex.extract_from_document)
    assert hasattr(ex, "ExtractionResult")
    assert hasattr(ex, "ensure_indexes")
    assert hasattr(ex, "GOALS_PROMPT_TEMPLATE")
    assert hasattr(ex, "TASKS_PROMPT_TEMPLATE")


def test_aa2_extraction_result_dataclass_fields() -> None:
    r = ex.ExtractionResult(
        goals_extracted=1, tasks_extracted=2, failures=3,
        idempotent_skip=False, model="claude-sonnet-4.5",
    )
    d = r.as_dict()
    assert d["goals_extracted"] == 1
    assert d["tasks_extracted"] == 2
    assert d["failures"] == 3
    assert d["idempotent_skip"] is False
    assert d["model"] == "claude-sonnet-4.5"


def test_aa2_tunable_constants_locked() -> None:
    assert ex.MAX_CHARS_BEFORE_CHUNK == 50_000
    assert ex.CHUNK_SIZE_CHARS == 18_000
    assert ex.MAX_ROWS_PER_CHUNK == 20


def test_aa2_goals_prompt_leads_with_board_level_anchor() -> None:
    """The goals prompt's leading sentence is the anchor that makes
    Sonnet 4.5 distinguish strategic outcomes from operational
    tasks. Lock it source-strictly so it can't drift."""
    assert ex.GOALS_PROMPT_TEMPLATE.startswith(
        "You are reading a strategic / governance document"
    )
    assert "BOARD-LEVEL STRATEGIC GOALS" in ex.GOALS_PROMPT_TEMPLATE
    assert "Skip operational tasks" in ex.GOALS_PROMPT_TEMPLATE
    # JSON envelope locked.
    assert '{{"goals": [' in ex.GOALS_PROMPT_TEMPLATE


def test_aa2_tasks_prompt_leads_with_work_items_anchor() -> None:
    assert ex.TASKS_PROMPT_TEMPLATE.startswith(
        "You are reading a strategic / governance document"
    )
    assert "SPECIFIC WORK ITEMS" in ex.TASKS_PROMPT_TEMPLATE
    assert "Skip board-level strategic outcomes" in ex.TASKS_PROMPT_TEMPLATE
    assert '{{"tasks": [' in ex.TASKS_PROMPT_TEMPLATE


def test_aa2_chunk_text_single_chunk_under_threshold() -> None:
    text = "x" * 1000
    assert ex._chunk_text(text) == [text]


def test_aa2_chunk_text_splits_over_threshold() -> None:
    text = "x" * 60_000
    chunks = ex._chunk_text(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= ex.CHUNK_SIZE_CHARS


# ─────────────────────────────────────────────────────────────────
# Row validators
# ─────────────────────────────────────────────────────────────────


def test_aa2_validate_goal_row_rejects_non_dict() -> None:
    doc, err = ex._validate_goal_row("not a dict")  # type: ignore[arg-type]
    assert doc is None
    assert err == "row is not a dict"


def test_aa2_validate_goal_row_normalises_unknown_enums() -> None:
    doc, err = ex._validate_goal_row({
        "title": "Hit 50M ARR by 2026",
        "department": "marketing",   # not in enum → ceo
        "category": "growth",        # not in enum → operations
        "status": "blue_sky",        # not in enum → on_track
    })
    assert err is None and doc is not None
    assert doc["department"] == "ceo"
    assert doc["category"] == "operations"
    assert doc["status"] == "on_track"


def test_aa2_validate_goal_row_clamps_scores() -> None:
    doc, _ = ex._validate_goal_row({"title": "OK", "current_score": 250, "probability": -5})
    assert doc is not None
    assert doc["current_score"] == 100
    assert doc["probability"] == 0


def test_aa2_validate_task_row_returns_pydantic_model() -> None:
    validated, err = ex._validate_task_row({
        "title": "Refactor RBAC",
        "category": "operations",
        "owner_role": "cto",  # lowercase → upper
        "status": "at_risk",
        "performance_score": 33,
        "probability_score": 88,
    })
    assert err is None
    assert validated.title == "Refactor RBAC"
    assert validated.owner_role == "CTO"
    assert validated.status == "at_risk"
    assert validated.performance_score == 33
    assert validated.probability_score == 88


def test_aa2_validate_task_row_rejects_bad_title() -> None:
    _, err = ex._validate_task_row({"title": "x", "category": "operations"})
    assert err is not None


# ─────────────────────────────────────────────────────────────────
# Runtime — mocked LLM
# ─────────────────────────────────────────────────────────────────


def _llm_ok(payload: Dict[str, Any]):
    """Build a `call_llm` AsyncMock return value carrying `payload`
    as the JSON response."""
    import json as _json
    return AsyncMock(return_value={
        "response": _json.dumps(payload),
        "mode":     "claude-sonnet-4.5",
        "model":    "claude-sonnet-4.5",
    })


@pytest.fixture
async def extraction_ctx():
    """Seed a doc + the surrounding minimal collections so the
    extraction service can read + write. Tear down on exit."""
    from core import db
    cid = f"aa2-ctx-{uuid.uuid4().hex[:8]}"
    did = f"aa2-doc-{uuid.uuid4().hex[:8]}"
    uid = f"aa2-user-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.documents.insert_one({
        "id":             did,
        "context_id":     cid,
        "name":           "AA2 Test Plan",
        "extracted_text": "Strategic plan body. " * 50,
        "origin":         "upload",
        "category":       "report",
        "status":         "extracted",
        "created_at":     now_iso, "updated_at": now_iso,
    })
    yield {"cid": cid, "did": did, "uid": uid}
    await db.documents.delete_one({"id": did})
    await db.tasks_initiatives.delete_many({"context_id": cid})
    await db.strategic_goals.delete_many({"context_id": cid})
    await db.extractions_log.delete_many({"context_id": cid})
    await db.extraction_failures.delete_many({"context_id": cid})


@pytest.mark.asyncio
async def test_aa2_extract_tasks_persists_rows(extraction_ctx) -> None:
    payload = {"tasks": [
        {"title": "Hire ERP integrator", "category": "operations",
         "owner_role": "COO", "status": "on_track",
         "performance_score": 30, "probability_score": 70},
        {"title": "Launch CRM POC", "category": "customer",
         "owner_role": "CRO", "status": "at_risk",
         "performance_score": 45, "probability_score": 60},
    ]}
    from core import db
    with patch.object(ex, "call_llm", _llm_ok(payload)):
        r = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_goals=False, extract_tasks=True,
        )
    assert r.tasks_extracted == 2
    assert r.goals_extracted == 0
    assert r.failures == 0
    rows = await db.tasks_initiatives.find(
        {"context_id": extraction_ctx["cid"]},
        {"_id": 0, "title": 1, "extracted_by": 1, "source_document_id": 1},
    ).to_list(10)
    assert {r["title"] for r in rows} == {"Hire ERP integrator", "Launch CRM POC"}
    assert all(r["extracted_by"] == "llm" for r in rows)
    assert all(r["source_document_id"] == extraction_ctx["did"] for r in rows)


@pytest.mark.asyncio
async def test_aa2_extract_goals_persists_rows(extraction_ctx) -> None:
    payload = {"goals": [
        {"title": "ARR $50M by 2026", "department": "ceo",
         "category": "revenue", "status": "on_track",
         "target_value": "$50M", "target_date": "Q4 2026",
         "current_score": 35, "probability": 65},
    ]}
    from core import db
    with patch.object(ex, "call_llm", _llm_ok(payload)):
        r = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_goals=True, extract_tasks=False,
        )
    assert r.goals_extracted == 1
    assert r.tasks_extracted == 0
    rows = await db.strategic_goals.find(
        {"context_id": extraction_ctx["cid"]},
        {"_id": 0, "title": 1, "extracted_by": 1, "source_doc_id": 1},
    ).to_list(10)
    assert len(rows) == 1
    assert rows[0]["title"] == "ARR $50M by 2026"
    assert rows[0]["extracted_by"] == "llm"
    assert rows[0]["source_doc_id"] == extraction_ctx["did"]


@pytest.mark.asyncio
async def test_aa2_bad_row_logged_to_extraction_failures(extraction_ctx) -> None:
    """One good row + one row with `title=""` → only the good row
    persists; the bad row is logged in `extraction_failures`."""
    payload = {"tasks": [
        {"title": "Valid task", "category": "operations"},
        {"title": "", "category": "operations"},  # empty title → fails validation
    ]}
    from core import db
    with patch.object(ex, "call_llm", _llm_ok(payload)):
        r = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_goals=False, extract_tasks=True,
        )
    assert r.tasks_extracted == 1
    assert r.failures == 1
    inserted = await db.tasks_initiatives.count_documents(
        {"context_id": extraction_ctx["cid"]}
    )
    assert inserted == 1
    failures = await db.extraction_failures.find(
        {"context_id": extraction_ctx["cid"], "kind": "tasks"},
        {"_id": 0},
    ).to_list(10)
    assert len(failures) == 1


@pytest.mark.asyncio
async def test_aa2_empty_extracted_text_returns_zeros_no_llm_call(extraction_ctx) -> None:
    """No `extracted_text` → service short-circuits with a warning,
    no `call_llm` invocation."""
    from core import db
    await db.documents.update_one(
        {"id": extraction_ctx["did"]}, {"$set": {"extracted_text": ""}},
    )
    mock_llm = AsyncMock()
    with patch.object(ex, "call_llm", mock_llm):
        r = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_goals=True, extract_tasks=True,
        )
    assert r.tasks_extracted == 0
    assert r.goals_extracted == 0
    assert r.failures == 0
    assert mock_llm.await_count == 0


@pytest.mark.asyncio
async def test_aa2_idempotency_blocks_second_call(extraction_ctx) -> None:
    payload = {"tasks": [{"title": "First pass", "category": "operations"}]}
    with patch.object(ex, "call_llm", _llm_ok(payload)):
        r1 = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_tasks=True,
        )
        assert r1.tasks_extracted == 1
        assert r1.idempotent_skip is False
        r2 = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_tasks=True,
        )
        assert r2.idempotent_skip is True
        assert r2.tasks_extracted == 0


@pytest.mark.asyncio
async def test_aa2_force_bypasses_idempotency(extraction_ctx) -> None:
    payload = {"tasks": [{"title": "Forced row", "category": "operations"}]}
    with patch.object(ex, "call_llm", _llm_ok(payload)):
        r1 = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_tasks=True,
        )
        assert r1.tasks_extracted == 1
        r2 = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_tasks=True, force=True,
        )
        assert r2.tasks_extracted == 1
        assert r2.idempotent_skip is False


@pytest.mark.asyncio
async def test_aa2_chunking_calls_llm_per_chunk(extraction_ctx) -> None:
    """`extracted_text` > MAX_CHARS_BEFORE_CHUNK → ≥ 2 chunks → ≥ 2
    LLM calls."""
    from core import db
    long_text = "alpha beta gamma delta. " * 3500  # ~85k chars
    await db.documents.update_one(
        {"id": extraction_ctx["did"]}, {"$set": {"extracted_text": long_text}},
    )
    payload = {"tasks": [{"title": "Chunked row", "category": "operations"}]}
    mock_llm = _llm_ok(payload)
    with patch.object(ex, "call_llm", mock_llm):
        r = await ex.extract_from_document(
            extraction_ctx["did"], extraction_ctx["cid"], extraction_ctx["uid"],
            extract_tasks=True,
        )
    assert mock_llm.await_count >= 2
    assert r.tasks_extracted >= 2  # 1 row per chunk


@pytest.mark.asyncio
async def test_aa2_no_args_both_false_is_noop() -> None:
    """`extract_goals=False, extract_tasks=False` returns zeros
    without touching the DB."""
    mock_llm = AsyncMock()
    with patch.object(ex, "call_llm", mock_llm):
        r = await ex.extract_from_document(
            "any-doc", "any-ctx", "any-user",
            extract_goals=False, extract_tasks=False,
        )
    assert r.tasks_extracted == 0
    assert r.goals_extracted == 0
    assert mock_llm.await_count == 0


@pytest.mark.asyncio
async def test_aa2_ensure_indexes_runs_idempotently() -> None:
    from core import db
    await ex.ensure_indexes()
    await ex.ensure_indexes()  # second call is a no-op
    info = await db.extractions_log.index_information()
    have = [tuple(v["key"]) for v in info.values()]
    assert (("document_id", 1), ("kind", 1)) in have
