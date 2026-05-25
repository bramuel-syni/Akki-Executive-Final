"""
Document Overlay foundation (Chunk 8 — QA-2026-05-16-029…-036).

Single service module that owns:
  · lifecycle state-machine transitions on `work_studio_exports`;
  · version-snapshot reads/writes on `work_studio_artefact_versions`;
  · structured-content normalisation;
  · RAG threshold helper (≥80 / 50-79 / <50);
  · source-doc allowlist enforcement for AI Revision;
  · idempotent migration (called at app startup AND by tests).

NO direct LLM calls live here — Shield-routed AI Revision lives in
`routers/work_studio_overlay.py`. This module is pure data + rules.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase


LifecycleState = Literal["draft", "in_review", "committed"]

ALLOWED_LIFECYCLE: Tuple[LifecycleState, ...] = ("draft", "in_review", "committed")

LEGACY_COMMITTED_DEFAULT: LifecycleState = "committed"


# ── RAG threshold helper (Q4 decision 2026-05-18) ──────────────────
def rag_band(pct: Optional[int]) -> Literal["green", "amber", "red", "unrated"]:
    """≥80 green · 50-79 amber · <50 red · None → unrated.

    Used identically on the overlay intelligence card accent border,
    per-section breakdown in the Intelligence modal, and any sibling
    document-card surface that re-reads the same confidence_pct.
    """
    if pct is None:
        return "unrated"
    if pct >= 80:
        return "green"
    if pct >= 50:
        return "amber"
    return "red"


# ── Migration (idempotent — call on startup or from tests) ─────────
async def ensure_overlay_migration(db: AsyncIOMotorDatabase) -> Dict[str, int]:
    """Backfill lifecycle_state + legacy flag on existing work_studio_exports.

    Returns a stats dict for the SYSTEM_STATE closeout entry. Safe
    to call multiple times — only touches rows missing the field.
    """
    matcher = {"lifecycle_state": {"$exists": False}}
    res = await db.work_studio_exports.update_many(
        matcher,
        {"$set": {
            "lifecycle_state": LEGACY_COMMITTED_DEFAULT,
            "legacy": True,
            # Leave structured_content / intelligence_report / source_document_ids
            # as None / [] on first touch so the overlay can detect and
            # render the read-only legacy state.
            "structured_content": None,
            "intelligence_report": None,
            "source_document_ids": [],
        }},
    )
    # Indexes (idempotent).
    await db.work_studio_exports.create_index([("context_id", 1), ("lifecycle_state", 1)])
    await db.work_studio_artefact_versions.create_index([("artefact_id", 1), ("saved_at", -1)])
    return {"migrated_rows": res.modified_count}


# ── Lifecycle transition rules ─────────────────────────────────────
def can_transition(current: LifecycleState, target: LifecycleState,
                   is_owner: bool) -> Tuple[bool, str]:
    """Return (allowed, reason_if_blocked)."""
    if target not in ALLOWED_LIFECYCLE:
        return False, f"unknown target state: {target}"
    if current == target:
        return True, ""
    if current == "committed":
        return False, "committed documents are immutable; use Create New Version"
    if current == "draft" and target == "in_review":
        if not is_owner:
            return False, "Move to review is owner-only"
        return True, ""
    if current == "in_review" and target == "draft":
        # Allow reverse only for owner — keeps the door open for the
        # owner to retract a doc that's prematurely in review. Not in
        # the QA spec but harmless and the "owner-only" rule mirrors
        # the forward Q1 decision.
        if not is_owner:
            return False, "only the owner can move a document back to draft"
        return True, ""
    if target == "committed":
        # draft → committed and in_review → committed both allowed,
        # no owner-only gate per spec.
        return True, ""
    return False, f"transition {current}→{target} is not defined"


# ── Structured-content normalisation ───────────────────────────────
def empty_structured_content() -> Dict[str, Any]:
    return {"sections": []}


def normalise_structured_content(payload: Any) -> Dict[str, Any]:
    """Coerce caller payload into the canonical shape — silently strip
    unknown keys so we keep storage tidy."""
    if not isinstance(payload, dict):
        return empty_structured_content()
    sections = payload.get("sections") or []
    out_sections: List[Dict[str, Any]] = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading") or "").strip()[:300]
        paragraphs_raw = s.get("paragraphs") or []
        paragraphs = [str(p)[:8000] for p in paragraphs_raw if isinstance(p, (str, int, float))]
        out_sections.append({"heading": heading, "paragraphs": paragraphs})
    return {"sections": out_sections}


# ── Version snapshot writes ────────────────────────────────────────
def _iso(d: datetime) -> str:
    return d.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_version_snapshot(
    db: AsyncIOMotorDatabase,
    *,
    artefact_id: str,
    context_id: str,
    account_id: str,
    label: Optional[str],
    pre_commit: bool = False,
) -> Dict[str, Any]:
    """Snapshot the current artefact state into work_studio_artefact_versions."""
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise ValueError(f"artefact not found: {artefact_id}")
    snap = {
        "id": f"ver-{uuid.uuid4().hex[:12]}",
        "artefact_id": artefact_id,
        "context_id": context_id,
        "account_id": account_id,
        "saved_at": _iso(_now()),
        "saved_by": account_id,
        "label": label,
        "pre_commit": pre_commit,
        "structured_content_snapshot": row.get("structured_content") or empty_structured_content(),
        "document_title_snapshot": (
            row.get("document_title") or row.get("name") or row.get("file_name") or ""
        ),
        "lifecycle_state_snapshot": row.get("lifecycle_state") or "draft",
    }
    await db.work_studio_artefact_versions.insert_one(dict(snap))
    return snap


async def list_versions(
    db: AsyncIOMotorDatabase,
    *,
    artefact_id: str,
    context_id: str,
) -> List[Dict[str, Any]]:
    rows = await db.work_studio_artefact_versions.find(
        {"artefact_id": artefact_id, "context_id": context_id},
        {"_id": 0},
    ).sort("saved_at", -1).to_list(200)
    return rows


# ── AI Revision: source-doc allowlist enforcement ──────────────────
# We scan the instruction text for any doc-id substring that
# resolves to a context document NOT in the allowlist. This is
# the v1 enforcement per the dispatch ("substring match acceptable
# for v1"). The substring scan looks for both the raw UUID and the
# `doc:<uuid>` citation form the LLM commonly emits.
_DOC_REF_PATTERN = re.compile(r"(?:doc[:_-])?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.IGNORECASE)


def find_referenced_doc_ids(instruction: str) -> List[str]:
    return list({m.group(1).lower() for m in _DOC_REF_PATTERN.finditer(instruction or "")})


async def validate_revision_inputs(
    db: AsyncIOMotorDatabase,
    *,
    artefact_id: str,
    context_id: str,
    instruction: str,
) -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, Any]]:
    """Returns (ok, error_dict, artefact_row).

    error_dict shape (when ok=False):
      {"status_code": int, "code": str, "detail": str}
    """
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        return False, {
            "status_code": 404,
            "code": "artefact_not_found",
            "detail": "Document not found in this context.",
        }, {}
    state = row.get("lifecycle_state") or "committed"
    if state == "committed":
        return False, {
            "status_code": 409,
            "code": "document_is_committed",
            "detail": "This document is committed and read-only. Create a new version to make changes.",
        }, row
    allow = row.get("source_document_ids") or []
    if not allow:
        return False, {
            "status_code": 412,
            "code": "no_source_documents",
            "detail": (
                "AI revision needs the source documents that the original document was "
                "compiled from. This artefact has no source documents recorded "
                "(legacy artefact) — please re-compile from sources to enable revision."
            ),
        }, row
    referenced = find_referenced_doc_ids(instruction)
    allowlist = {d.lower() for d in allow}
    foreign = [r for r in referenced if r not in allowlist]
    if foreign:
        return False, {
            "status_code": 400,
            "code": "foreign_source_referenced",
            "detail": (
                "Your revision instruction explicitly references document IDs that "
                "are not in this document's source set. AI revision can only draw "
                f"from the original sources. Offending ids: {', '.join(foreign[:3])}."
            ),
        }, row
    return True, None, row


# ── Read-time overlay payload assembly ─────────────────────────────
def overlay_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    """Shape returned by the overlay GET endpoint. Drops Mongo _id
    (callers should have already projected it out).

    Title fallback chain (Blocker 1, 2026-05-25): the pre-backlog-b
    implementation read `document_title → name → file_name → "Untitled
    document"` and silently swallowed the top-level `title` field. Real
    Board/Committee Packs created by the Compile flow at L1374 of
    `routers/work_studio_export.py` only populate `file_name`, but the
    Enhance flow + seeds + any direct-insert path populate the
    top-level `title`. The fallback chain now covers every documented
    spot the title can live so no row ever renders as "Untitled
    document" when a name is in fact present somewhere on the row.

    Order (first non-empty wins):
      1. `structured_content.title`  — populated by overlay PATCH and
         by the compile-pass-2 enrichment step.
      2. `intelligence_report.title` — populated by the Document
         Intelligence enrichment when it pre-names the artefact.
      3. `row.title`                  — top-level title field (the
         field seeds + direct inserts write).
      4. `row.document_title`         — legacy back-compat field.
      5. `row.name`                   — legacy back-compat alias.
      6. extension-stripped `row.file_name`.
      7. "Untitled document"          — true-empty fallback.
    """
    structured = row.get("structured_content") or {}
    intel_report = row.get("intelligence_report") or {}
    sc_title = structured.get("title") if isinstance(structured, dict) else None
    intel_title = intel_report.get("title") if isinstance(intel_report, dict) else None
    title = (
        (sc_title or "").strip()
        or (intel_title or "").strip()
        or (row.get("title") or "").strip()
        or (row.get("document_title") or "").strip()
        or (row.get("name") or "").strip()
        or _strip_extension(row.get("file_name") or "")
        or "Untitled document"
    )
    return {
        "id": row["id"],
        "context_id": row["context_id"],
        "title": title,
        "kind": row.get("kind"),
        "lifecycle_state": row.get("lifecycle_state") or "committed",
        "legacy": bool(row.get("legacy", True)),
        "structured_content": row.get("structured_content"),
        "source_document_ids": row.get("source_document_ids") or [],
        "intelligence_report": row.get("intelligence_report"),
        "owner_account_id": row.get("account_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
        "file_name": row.get("file_name"),
        "output_format": row.get("output_format"),
    }


def _strip_extension(name: str) -> str:
    for ext in (".docx", ".pdf", ".pptx", ".txt"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name
