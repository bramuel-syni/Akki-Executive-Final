"""Phase P5.15 — Ideas engine Pydantic schemas.

Mongo collections:
  * `ideas_digests`           — one row per (account_id, week_iso, digest_version).
  * `user_ideas_preferences`  — one row per (account_id, user_id).
  * `ideas_audit_log`         — append-only digest generation events.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────
# Lens + confidence vocabulary
# ─────────────────────────────────────────────────────────────────

IdeaLens = Literal["strategy", "board_navigation", "capital", "governance"]
IDEA_LENSES: tuple[IdeaLens, ...] = ("strategy", "board_navigation", "capital", "governance")

ConfidenceBand = Literal["low", "medium", "high"]


# ─────────────────────────────────────────────────────────────────
# Citation
# ─────────────────────────────────────────────────────────────────


class IdeaCitation(BaseModel):
    """Pointer to a real, indexed chunk of a real document. The
    resolver verifies the document_id exists in the tenant's
    corpus AND chunk_id (when given) resolves to a chunk in
    `extractions_log`. Fabricated combos trip
    `citation_unverifiable`."""
    source_kind: Literal["document_chunk"] = "document_chunk"
    document_id: str = Field(..., min_length=1)
    chunk_id: Optional[str] = Field(
        None,
        description="extractions_log id; None means the citation points at the document as a whole",
    )
    excerpt: str = Field(..., min_length=1, max_length=400)


# ─────────────────────────────────────────────────────────────────
# Cards + digests
# ─────────────────────────────────────────────────────────────────


class IdeaCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lens: IdeaLens
    title: str = Field(..., min_length=1, max_length=80)
    body: str = Field(..., min_length=1, max_length=800)
    confidence_band: ConfidenceBand
    confidence_rationale: str = Field(..., min_length=1, max_length=200)
    citations: List[IdeaCitation] = Field(..., min_length=2)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IdeasDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    account_id: str
    week_iso: str = Field(..., description="ISO 8601 year-week: '2026-W08'")
    digest_version: str = "p5.15.0"
    cards: List[IdeaCard] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Diagnostics surfaced on the API + audit log.
    refuse_to_decide_pass_count: int = 0
    refuse_to_decide_fail_count: int = 0
    citation_count: int = 0
    model_id: Optional[str] = None
    shield_invoke_id: Optional[str] = None
    # When `cards` is fewer than 4, this list names the dropped
    # lenses for the admin-visible flag — surfaced in the API
    # response so the FE can show a polite caveat.
    dropped_lenses: List[IdeaLens] = Field(default_factory=list)
    schema_version: str = "ideas.digest.1.0"


# ─────────────────────────────────────────────────────────────────
# Preferences
# ─────────────────────────────────────────────────────────────────


class UserIdeasPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    user_id: str = Field(..., description="Account.id is the user_id in this codebase")
    custom_instructions: str = Field(default="", max_length=2000)
    lenses_enabled: List[IdeaLens] = Field(default_factory=lambda: list(IDEA_LENSES))
    cadence: Literal["weekly"] = "weekly"
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


__all__ = [
    "IDEA_LENSES",
    "IdeaLens",
    "ConfidenceBand",
    "IdeaCitation",
    "IdeaCard",
    "IdeasDigest",
    "UserIdeasPreferences",
]
