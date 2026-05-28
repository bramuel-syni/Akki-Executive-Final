"""Phase Z (2026-05-27) — Document origin + category display helpers.

The `documents` collection uses these RAW backend values:

    origin:    "akki_generated" | "upload" | "email_receipt" | None
    category:  "board_pack" | "minutes" | "draft" | "deck" | "report"
               | "briefing" | None  (None == uncategorized)

User spec Q1 = (b) — keep raw backend values; map to friendly labels
for display only. This module is the single source of truth for those
maps.

Frontend mirror lives at `frontend/src/lib/origins.js` with byte-for-
byte the same label strings (locked by `test_phase_z_*.py`).

Why two enums?
  - `origin` answers "where did this doc come from?" → drives the
    `/app/documents` page's 3 capsule tabs (Akki-generated / Uploaded
    / Emailed).
  - `category` answers "what kind of artefact is it?" → drives the
    Work Studio 6-tab row.
  A document has BOTH classifications independently. An uploaded
  audit report = `{origin: "upload", category: "report"}` and surfaces
  in BOTH the `/app/documents` "Uploaded" tab AND the Work Studio
  "Reports" tab. This orthogonality is the institutional contract
  Phase Z exists to enforce — Recurrence #5 was caused by conflation
  of these axes.
"""
from __future__ import annotations

from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# Origin — `where did this doc come from?`
# ─────────────────────────────────────────────────────────────────────
ORIGIN_VALUES = ("akki_generated", "upload", "email_receipt")

ORIGIN_DISPLAY = {
    "akki_generated": "Akki-generated",
    "upload":         "Uploaded",
    "email_receipt":  "Emailed",
}


def display_origin(origin: Optional[str]) -> str:
    """Return the friendly label for an origin value. Unknown / None
    fall back to a neutral "Unknown source" string so nothing else in
    the system has to special-case nulls."""
    if not origin:
        return "Unknown source"
    return ORIGIN_DISPLAY.get(origin, "Unknown source")


# ─────────────────────────────────────────────────────────────────────
# Category — `what kind of artefact is it?`
# ─────────────────────────────────────────────────────────────────────
CATEGORY_VALUES = (
    "board_pack", "minutes", "draft", "deck", "report", "briefing",
)

CATEGORY_DISPLAY = {
    "board_pack": "Main Board & Committee Packs",
    "minutes":    "Minutes",
    "draft":      "Drafts",
    "deck":       "Decks",
    "report":     "Reports",
    "briefing":   "Briefing",
}


def display_category(category: Optional[str]) -> str:
    """Return the Work Studio tab label for a category. Unknown / None
    fall back to "Uncategorized"."""
    if not category:
        return "Uncategorized"
    return CATEGORY_DISPLAY.get(category, "Uncategorized")


# ─────────────────────────────────────────────────────────────────────
# Backfill resolution — used by the migration script + new-write
#                       defaulting path.
# ─────────────────────────────────────────────────────────────────────
#
# Source signals (in priority order):
#   1. `work_studio_exports.kind` (when source_channel="work_studio_export")
#       committee_pack → "board_pack"  (per user clarification — both
#                                       Main Board AND Committee packs
#                                       surface under the one Work Studio
#                                       "Main Board & Committee Packs" tab)
#       board_pack     → "board_pack"
#       deck           → "deck"
#       report         → "report"
#       minutes        → "minutes"
#   2. `source_channel == "cycle_compilation"` → "board_pack"
#       (cycle compile output IS a board pack)
#   3. `doc_kind`:
#       draft / briefing → match directly
#       anything else    → fall through to step 4
#   4. `state == "draft"` → "draft"
#   5. Otherwise → None (uncategorized)
#
# Origin resolution (used for backfill — existing docs without
# `origin` set):
#   1. If `source_channel in ("work_studio_export","cycle_compilation")`
#       → "akki_generated"
#   2. If `source_channel == "inbound_email"` → "email_receipt"
#   3. Otherwise → "upload"
WS_EXPORT_KIND_TO_CATEGORY = {
    "committee_pack": "board_pack",
    "board_pack":     "board_pack",
    "deck":           "deck",
    "report":         "report",
    "minutes":        "minutes",
}

AKKI_GENERATED_CHANNELS = ("work_studio_export", "cycle_compilation")


def resolve_category(doc: dict, ws_export_kind: Optional[str] = None) -> Optional[str]:
    """Derive the canonical category for a document.

    `ws_export_kind` is the corresponding `work_studio_exports.kind`
    if the doc was synthesized from an export (the caller does the
    join — kept stateless here)."""
    if ws_export_kind and ws_export_kind in WS_EXPORT_KIND_TO_CATEGORY:
        return WS_EXPORT_KIND_TO_CATEGORY[ws_export_kind]
    source_channel = (doc.get("source_channel") or "").lower()
    if source_channel == "cycle_compilation":
        return "board_pack"
    doc_kind = (doc.get("doc_kind") or "").lower()
    if doc_kind in CATEGORY_VALUES:
        return doc_kind
    if (doc.get("state") or "").lower() == "draft":
        return "draft"
    return None


def resolve_origin(doc: dict) -> str:
    """Derive the canonical origin for a document. Always returns a
    non-null value so the GET /api/documents filter can run cleanly."""
    if doc.get("origin") in ORIGIN_VALUES:
        return doc["origin"]
    source_channel = (doc.get("source_channel") or "").lower()
    if source_channel in AKKI_GENERATED_CHANNELS:
        return "akki_generated"
    if source_channel == "inbound_email":
        return "email_receipt"
    return "upload"
