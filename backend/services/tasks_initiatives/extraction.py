"""
Phase AA-slice-2 (2026-05-27) — tasks/initiatives LLM extraction.

Single public entry point:

    await extract_from_document(
        document_id, context_id, account_id,
        extract_goals=True, extract_tasks=True, force=False,
    )

Reads `documents.extracted_text`, calls Claude Sonnet 4.5 via
`llm_service.call_llm` (which goes through the Synisense Shield),
parses the JSON output, validates each row with the Phase AA-1
Pydantic schemas (`TaskInitiativeIn` for tasks, the locked goals
schema for goals), and persists valid rows to the appropriate
collection. Rows that fail validation are logged to
`extraction_failures` (auditable, never silently dropped).

Idempotency is enforced via the `extractions_log` collection —
a (document_id, kind) pair that already extracted skips the LLM
call unless `force=True`.

Two prompt templates — goals vs tasks — live as module constants
so they're trivial to lock with source-strict CI guards.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from core import db
from llm_service import call_llm
from helpers.llm_json import safe_parse_json
from routers.tasks_initiatives import TaskInitiativeIn
from services.tasks_initiatives.prompts import (
    GOALS_PROMPT_TEMPLATE,
    TASKS_PROMPT_TEMPLATE,
)


log = logging.getLogger("akki.aa.extraction")


# ─────────────────────────────────────────────────────────────────
# Tunables — module constants so source-strict CI can lock them.
# ─────────────────────────────────────────────────────────────────

# Per spec — chunk if extracted_text > 50_000 chars.
MAX_CHARS_BEFORE_CHUNK = 50_000
# Each chunk is bounded so the LLM stays under its context window.
CHUNK_SIZE_CHARS = 18_000
# Max rows we accept per chunk to protect token spend.
MAX_ROWS_PER_CHUNK = 20

# Enum sets — copied from goals + AA-1 routers so this service has
# no runtime dependency on those modules' private symbols.
_GOAL_DEPARTMENTS = {"ceo", "cfo", "coo", "commercial", "board"}
_GOAL_CATEGORIES = {"revenue", "customer", "product", "people", "operations", "compliance"}
_GOAL_STATUSES = {"on_track", "at_risk", "off_track", "achieved", "abandoned"}


# ─────────────────────────────────────────────────────────────────
# Prompts — locked verbatim in `prompts.py`. See that module for the
# template strings; this service just imports + formats them.
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# Result + helpers
# ─────────────────────────────────────────────────────────────────


@dataclass
class ExtractionResult:
    goals_extracted: int
    tasks_extracted: int
    failures: int
    idempotent_skip: bool
    model: Optional[str] = None  # informational — last LLM mode/model used

    def as_dict(self) -> Dict[str, Any]:
        return {
            "goals_extracted":  self.goals_extracted,
            "tasks_extracted":  self.tasks_extracted,
            "failures":         self.failures,
            "idempotent_skip":  self.idempotent_skip,
            "model":            self.model,
        }


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunk_text(text: str) -> List[str]:
    """Split `text` into ≤ CHUNK_SIZE_CHARS-sized chunks on paragraph
    boundaries when possible. Single-chunk when the text is small
    enough for one round-trip.
    """
    if len(text) <= MAX_CHARS_BEFORE_CHUNK:
        return [text]
    chunks: List[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= CHUNK_SIZE_CHARS:
            chunks.append(remaining)
            break
        # Prefer to break on a paragraph boundary near the cap to
        # avoid splitting mid-sentence.
        split = remaining.rfind("\n\n", 0, CHUNK_SIZE_CHARS)
        if split < CHUNK_SIZE_CHARS // 2:
            split = CHUNK_SIZE_CHARS
        chunks.append(remaining[:split])
        remaining = remaining[split:].lstrip()
    return chunks


async def _log_failure(
    *,
    document_id: str,
    context_id: str,
    kind: str,
    raw_row: Any,
    error: str,
) -> None:
    """Write a row to `extraction_failures` so the operator can audit
    what the LLM produced that we refused."""
    try:
        await db.extraction_failures.insert_one({
            "id":           uuid.uuid4().hex,
            "document_id":  document_id,
            "context_id":   context_id,
            "kind":         kind,
            "raw_row":      raw_row if isinstance(raw_row, (dict, list, str, int, float, bool)) else str(raw_row),
            "error":        (error or "")[:500],
            "created_at":   _iso_now(),
        })
    except Exception as e:  # pragma: no cover — never crash extraction over logging
        log.warning("[aa2.extract] failure-log insert failed: %s", e)


async def _log_extraction(
    *,
    document_id: str,
    context_id: str,
    kind: str,
    count: int,
    failures: int,
    model: Optional[str],
) -> None:
    """Idempotency marker — `(document_id, kind)` pair we've extracted."""
    await db.extractions_log.insert_one({
        "id":           uuid.uuid4().hex,
        "document_id":  document_id,
        "context_id":   context_id,
        "kind":         kind,
        "count":        int(count),
        "failures":     int(failures),
        "model":        model,
        "created_at":   _iso_now(),
    })


async def _idempotency_skip(document_id: str, kind: str) -> bool:
    """`True` if we've already extracted this (doc, kind) pair."""
    return await db.extractions_log.find_one(
        {"document_id": document_id, "kind": kind},
        {"_id": 0, "id": 1},
    ) is not None


# ─────────────────────────────────────────────────────────────────
# Per-kind LLM passes
# ─────────────────────────────────────────────────────────────────


def _coerce_int_0_100(v: Any, default: int = 0) -> int:
    try:
        n = int(v)
        return max(0, min(100, n))
    except (TypeError, ValueError):
        return default


def _validate_goal_row(raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Coerce + validate a single goal row. Returns
    `(insertable_doc, None)` on success, `(None, error_str)` on
    failure."""
    if not isinstance(raw, dict):
        return None, "row is not a dict"
    title = str(raw.get("title") or "").strip()
    if not (2 <= len(title) <= 180):
        return None, f"title length {len(title)} not in [2,180]"
    dept = (raw.get("department") or "ceo").lower()
    if dept not in _GOAL_DEPARTMENTS:
        dept = "ceo"
    cat = (raw.get("category") or "operations").lower()
    if cat not in _GOAL_CATEGORIES:
        cat = "operations"
    status = (raw.get("status") or "on_track").lower()
    if status not in _GOAL_STATUSES:
        status = "on_track"
    return {
        "title":         title,
        "description":   (str(raw.get("description") or "")[:600]) or None,
        "department":    dept,
        "category":      cat,
        "status":        status,
        "target_value":  (str(raw.get("target_value") or "")[:120]) or None,
        "target_date":   (str(raw.get("target_date") or "")[:40]) or None,
        "current_score": _coerce_int_0_100(raw.get("current_score"), 0),
        "probability":   _coerce_int_0_100(raw.get("probability"), 0),
    }, None


def _validate_task_row(raw: Dict[str, Any]) -> Tuple[Optional[TaskInitiativeIn], Optional[str]]:
    """Coerce + Pydantic-validate a single task row."""
    if not isinstance(raw, dict):
        return None, "row is not a dict"
    payload: Dict[str, Any] = {
        "title":              str(raw.get("title") or "").strip(),
        "body":               (str(raw.get("body") or "").strip() or None),
        "category":           (str(raw.get("category") or "operations").lower()),
        "owner_role":         (raw.get("owner_role") if raw.get("owner_role") else None),
        "status":             (str(raw.get("status") or "not_started").lower()),
        "performance_score":  _coerce_int_0_100(raw.get("performance_score"), 0),
        "probability_score":  _coerce_int_0_100(raw.get("probability_score"), 0),
    }
    # `owner_role` may arrive lowercase from the LLM — normalize.
    if isinstance(payload["owner_role"], str):
        payload["owner_role"] = payload["owner_role"].upper()
    try:
        return TaskInitiativeIn(**payload), None
    except ValidationError as ve:
        return None, str(ve)[:480]


async def _run_extraction_pass(
    *,
    kind: str,
    prompt_template: str,
    response_key: str,
    validate: Any,
    persist: Any,
    doc_id: str,
    doc_name: str,
    context_id: str,
    chunks: List[str],
) -> Tuple[int, int, Optional[str]]:
    """Generic per-chunk LLM extraction loop. `kind` is "goals" or
    "tasks" (drives the LLM module name + failure-log tag).
    `validate(raw_row) -> (insertable, err)` and
    `persist(insertable) -> None` are kind-specific.
    """
    inserted = 0
    failures = 0
    last_model: Optional[str] = None
    for idx, chunk in enumerate(chunks, start=1):
        prompt = prompt_template.format(
            doc_name=doc_name, chunk_idx=idx, chunk_total=len(chunks),
            doc_text=chunk,
        )
        try:
            out = await call_llm(
                module=f"tasks_initiatives.extract_{kind}",
                user_query=prompt,
                response_format="json",
                tier="standard",
                purpose=f"tasks_initiatives.extract_{kind}",
                session_context={"context_id": context_id},
            )
        except Exception as e:
            log.warning("[aa2.extract] %s chunk %d LLM call failed: %s", kind, idx, e)
            failures += 1
            continue
        last_model = out.get("mode") or out.get("model") or last_model
        parsed, _ = safe_parse_json(out.get("response") or "{}")
        if not isinstance(parsed, dict):
            failures += 1
            continue
        raw_rows = parsed.get(response_key) or []
        if not isinstance(raw_rows, list):
            raw_rows = []
        for raw in raw_rows[:MAX_ROWS_PER_CHUNK]:
            doc, err = validate(raw)
            if err or doc is None:
                failures += 1
                await _log_failure(
                    document_id=doc_id, context_id=context_id,
                    kind=kind, raw_row=raw, error=err or "unknown",
                )
                continue
            await persist(doc)
            inserted += 1
    return inserted, failures, last_model


async def _persist_goal(
    insertable: Dict[str, Any], *, doc_id: str, doc_name: str,
    context_id: str, account_id: str,
) -> None:
    now_iso = _iso_now()
    full = {
        "id":              str(uuid.uuid4()),
        "context_id":      context_id,
        **insertable,
        "initiatives_count": 0,
        "owner_name":      None,
        "target_metric":   None,
        "current_value":   None,
        "source_doc_id":   doc_id,
        "source_doc_name": doc_name,
        "extracted_by":    "llm",
        "score_history":   (
            [{"score": insertable["current_score"], "recorded_at": now_iso}]
            if insertable["current_score"] else []
        ),
        "created_at":      now_iso,
        "updated_at":      now_iso,
        "created_by":      account_id,
    }
    await db.strategic_goals.insert_one(full)


async def _persist_task(
    validated: TaskInitiativeIn, *, doc_id: str, context_id: str,
) -> None:
    now_iso = _iso_now()
    full = {
        "id":                  uuid.uuid4().hex,
        "context_id":          context_id,
        "title":               validated.title.strip(),
        "body":                (validated.body or "").strip() or None,
        "category":            validated.category,
        "owner_role":          validated.owner_role,
        "parent_objective_id": None,
        "status":              validated.status,
        "performance_score":   int(validated.performance_score),
        "probability_score":   int(validated.probability_score),
        "last_reassessed_at":  now_iso,
        "source_document_id":  doc_id,
        "extracted_by":        "llm",
        "status_active":       True,
        "created_at":          now_iso,
        "updated_at":          now_iso,
    }
    await db.tasks_initiatives.insert_one(full)


# ─────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────


async def extract_from_document(
    document_id: str,
    context_id: str,
    account_id: str,
    *,
    extract_goals: bool = False,
    extract_tasks: bool = True,
    force: bool = False,
) -> ExtractionResult:
    """Extract goals / tasks from a document's `extracted_text` and
    persist valid rows to the appropriate collections.

    The two switches are independent; passing `extract_goals=True,
    extract_tasks=True` runs both passes; passing both False is a
    no-op that returns zeroes.

    Idempotency: a `(document_id, kind)` pair already in
    `extractions_log` is skipped unless `force=True`.
    """
    if not extract_goals and not extract_tasks:
        return ExtractionResult(0, 0, 0, False)

    doc = await db.documents.find_one(
        {"id": document_id, "context_id": context_id},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
         "extracted_text": 1},
    )
    if not doc:
        return ExtractionResult(0, 0, 0, False)
    text = (doc.get("extracted_text") or "").strip()
    if not text:
        log.warning(
            "[aa2.extract] doc=%s in context=%s has empty extracted_text; "
            "returning zero result.", document_id, context_id,
        )
        return ExtractionResult(0, 0, 0, False)

    doc_name = doc.get("name") or doc.get("original_filename") or "Document"

    skip_goals = extract_goals and (not force) and await _idempotency_skip(document_id, "goals")
    skip_tasks = extract_tasks and (not force) and await _idempotency_skip(document_id, "tasks")

    if extract_goals and skip_goals and (not extract_tasks or skip_tasks):
        return ExtractionResult(0, 0, 0, True)
    if extract_tasks and skip_tasks and not extract_goals:
        return ExtractionResult(0, 0, 0, True)

    chunks = _chunk_text(text)

    goals_inserted = 0
    tasks_inserted = 0
    failures = 0
    last_model: Optional[str] = None

    if extract_goals and not skip_goals:
        async def _g_persist(d): await _persist_goal(
            d, doc_id=document_id, doc_name=doc_name,
            context_id=context_id, account_id=account_id,
        )
        g_ins, g_fail, g_model = await _run_extraction_pass(
            kind="goals", prompt_template=GOALS_PROMPT_TEMPLATE,
            response_key="goals", validate=_validate_goal_row,
            persist=_g_persist,
            doc_id=document_id, doc_name=doc_name,
            context_id=context_id, chunks=chunks,
        )
        goals_inserted += g_ins
        failures += g_fail
        last_model = g_model or last_model
        await _log_extraction(
            document_id=document_id, context_id=context_id,
            kind="goals", count=g_ins, failures=g_fail, model=g_model,
        )

    if extract_tasks and not skip_tasks:
        async def _t_persist(d): await _persist_task(
            d, doc_id=document_id, context_id=context_id,
        )
        t_ins, t_fail, t_model = await _run_extraction_pass(
            kind="tasks", prompt_template=TASKS_PROMPT_TEMPLATE,
            response_key="tasks", validate=_validate_task_row,
            persist=_t_persist,
            doc_id=document_id, doc_name=doc_name,
            context_id=context_id, chunks=chunks,
        )
        tasks_inserted += t_ins
        failures += t_fail
        last_model = t_model or last_model
        await _log_extraction(
            document_id=document_id, context_id=context_id,
            kind="tasks", count=t_ins, failures=t_fail, model=t_model,
        )

    return ExtractionResult(
        goals_extracted=goals_inserted,
        tasks_extracted=tasks_inserted,
        failures=failures,
        idempotent_skip=False,
        model=last_model,
    )


# ─────────────────────────────────────────────────────────────────
# Startup index helper
# ─────────────────────────────────────────────────────────────────


async def ensure_indexes() -> None:
    """Idempotent. Called from `server.py` startup."""
    await db.extractions_log.create_index([("document_id", 1), ("kind", 1)])
    await db.extractions_log.create_index([("context_id", 1), ("created_at", -1)])
    await db.extraction_failures.create_index([("document_id", 1), ("kind", 1)])
    await db.extraction_failures.create_index([("context_id", 1), ("created_at", -1)])
