"""Track A Phase 1 (2026-06-03) — Analysis entity.

The successor to `services.workbook_analyzer.WorkbookAnalysis`.
Sibling entity, NOT a replacement: the P5.14 surface keeps running
unchanged. Phase 2 of Track A wires the UI to this entity; Phase 1
just establishes the persistence shape + endpoints.

Differences from `WorkbookAnalysis`:
  • `sources[]` instead of a single (filename, file_format, size).
    Multi-file uploads land here.
  • `observations[]` — the unified-layer observation list (analogous
    to `signals[]` in P5.14 but workbook-agnostic).
  • `notes[]` — per-run notes captured by the user.
  • `refresh_history[]` — every (re)run appends an entry.
  • `context_id` is REQUIRED (tenant-scoping rides on
    `(account_id, context_id)` rather than account-only).

Mongo collection: `analyses`. Indexed on `(account_id, context_id)`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisSource(BaseModel):
    """A single source file referenced by an Analysis. The raw bytes
    live in `analysis_blobs` (separate collection, mirroring the
    P5.14 `workbook_blobs` split). After session-close the blob is
    deleted; the source ref + metadata stays on the Analysis row."""
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., description="Stable id; foreign key to analysis_blobs.source_id")
    filename: str = Field(..., min_length=1, max_length=400)
    file_format: Literal["xlsx", "csv"]
    file_size_bytes: int = Field(..., ge=0)
    uploaded_at: str = Field(default_factory=_iso_now)
    # Set to True after the blob has been removed from
    # `analysis_blobs`. Reads after this still work; re-parsing
    # the matrices is not possible without re-upload.
    blob_purged: bool = Field(default=False)


class AnalysisObservation(BaseModel):
    """Unified observation surface across all sources of an
    Analysis. Phase 1 ships the persistence shape only — Phase 3
    populates this from the synthesis layer (Solva v2 narration)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["trend", "outlier", "metric", "ratio", "missing_data", "synthesis"]
    title: str = Field(..., min_length=1, max_length=200)
    detail: str = Field(..., min_length=1, max_length=2000)
    # Per source-file (when applicable).
    source_id: Optional[str] = None
    # Free-form citation envelope; Phase 1 doesn't constrain shape.
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=_iso_now)


class AnalysisNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    body: str = Field(..., min_length=1, max_length=4000)
    created_at: str = Field(default_factory=_iso_now)
    author_account_id: str


class AnalysisRefreshEntry(BaseModel):
    """One run / re-run record. Phase 4 enforces the
    "refresh-creates-new-version" pattern; Phase 1 just makes the
    field exist so the contract is locked."""
    model_config = ConfigDict(extra="forbid")
    refresh_id: str
    ran_at: str = Field(default_factory=_iso_now)
    triggered_by: Literal["upload", "re-run", "session-close"]
    note: Optional[str] = None


class Analysis(BaseModel):
    """Root persisted document for the Track A entity.

    Mongo collection: `analyses`.
    Tenant scope: `(account_id, context_id)` — cross-tenant access
    returns 404 (no existence leak), mirroring the P5.14 pattern.
    """
    model_config = ConfigDict(extra="forbid")

    id: str
    account_id: str
    context_id: str  # REQUIRED per spec (vs. optional on WorkbookAnalysis)
    title: str = Field(..., min_length=1, max_length=200)

    # Track A Phase 2 (2026-06-04) — objective text captured at the
    # top of the drawer. NOT a chat thread (D4 — chats live in chats).
    # Used as narration context by Solva v2 in Phase 3.
    objective: str = Field(default="", max_length=4000)

    # Track A Phase 3 (2026-06-04) — Solva narration output. Populated
    # by POST /v2/analyses/{aid}/synthesize. `cache_key` enables
    # idempotency on re-call.
    headline: str = Field(default="", max_length=400)
    narration: Optional[Dict[str, Any]] = Field(default=None)

    sources: List[AnalysisSource] = Field(default_factory=list)
    observations: List[AnalysisObservation] = Field(default_factory=list)
    notes: List[AnalysisNote] = Field(default_factory=list)
    refresh_history: List[AnalysisRefreshEntry] = Field(default_factory=list)

    status: Literal["draft", "ready", "purged"] = "draft"

    schema_version: str = "analysis.1.0"
    created_at: str = Field(default_factory=_iso_now)
    updated_at: str = Field(default_factory=_iso_now)


__all__ = [
    "Analysis",
    "AnalysisSource",
    "AnalysisObservation",
    "AnalysisNote",
    "AnalysisRefreshEntry",
]
