"""Backlog-B Blocker 1 — `overlay_payload` title fallback chain.

Tests every position in the title resolution order so a future
refactor cannot silently regress any of the four populated paths.

The fallback chain (per service docstring after the 2026-05-25 fix):
    1. structured_content.title
    2. intelligence_report.title
    3. row.title                    ← the gap-exposing path (this is
                                      where the seed wrote)
    4. row.document_title           — legacy
    5. row.name                     — legacy
    6. _strip_extension(row.file_name)
    7. "Untitled document"
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")

import pytest

from services.work_studio_overlay import overlay_payload


def _base_row(**extra):
    """Minimal row that overlay_payload requires (id + context_id)."""
    row = {"id": "ar-x", "context_id": "ctx-x"}
    row.update(extra)
    return row


# ── Position 1 — structured_content.title wins ──────────────────────
def test_overlay_payload_title_from_structured_content():
    row = _base_row(
        structured_content={"title": "SC Title", "sections": []},
        intelligence_report={"title": "IR Title"},
        title="Top Title",
        document_title="Legacy Title",
        name="Legacy Name",
        file_name="legacy.docx",
    )
    assert overlay_payload(row)["title"] == "SC Title"


# ── Position 2 — intelligence_report.title wins when SC missing ─────
def test_overlay_payload_title_from_intelligence_report():
    row = _base_row(
        structured_content={"sections": []},  # no title key
        intelligence_report={"title": "IR Title"},
        title="Top Title",
        document_title="Legacy Title",
        name="Legacy Name",
        file_name="legacy.docx",
    )
    assert overlay_payload(row)["title"] == "IR Title"


# ── Position 3 — TOP-LEVEL title (the gap that broke backlog-b) ─────
def test_overlay_payload_title_from_top_level_title_field():
    """This is the regression Blocker 1 fix targets.

    The pre-fix `overlay_payload` only checked `document_title → name →
    file_name`. The seed script (and any direct-insert path) wrote a
    top-level `title` field that was silently dropped, leading to
    'Untitled document' on the Work Studio list. After the fix the
    top-level `title` is part of the fallback chain.
    """
    row = _base_row(
        # No structured_content.title, no intelligence_report.title.
        structured_content={"sections": [{"heading": "h", "paragraphs": ["p"]}]},
        intelligence_report=None,
        title="Top-level Title (the gap path)",
        # No document_title, no name. Only file_name — which would have
        # won pre-fix and produced "legacy" not the real title.
        file_name="legacy.docx",
    )
    assert overlay_payload(row)["title"] == "Top-level Title (the gap path)"


# ── Position 4 — legacy document_title wins when 1-3 missing ────────
def test_overlay_payload_title_from_document_title():
    row = _base_row(
        document_title="Legacy DT",
        name="Legacy Name",
        file_name="legacy.docx",
    )
    assert overlay_payload(row)["title"] == "Legacy DT"


# ── Position 5 — legacy name wins when 1-4 missing ──────────────────
def test_overlay_payload_title_from_name():
    row = _base_row(
        name="Legacy Name",
        file_name="legacy.docx",
    )
    assert overlay_payload(row)["title"] == "Legacy Name"


# ── Position 6 — file_name stripped of extension ────────────────────
def test_overlay_payload_title_from_stripped_file_name():
    row = _base_row(file_name="legacy_report.docx")
    assert overlay_payload(row)["title"] == "legacy_report"


# ── Position 7 — truly empty row falls back to "Untitled document" ──
def test_overlay_payload_title_falls_back_to_untitled():
    row = _base_row()
    assert overlay_payload(row)["title"] == "Untitled document"


# ── Edge — whitespace-only values are skipped, not preferred ────────
def test_overlay_payload_title_skips_whitespace_only_values():
    """A blank/whitespace title shouldn't beat a real legacy field."""
    row = _base_row(
        structured_content={"title": "   "},
        intelligence_report={"title": ""},
        title=None,
        document_title="Legacy DT",
        file_name="legacy.docx",
    )
    assert overlay_payload(row)["title"] == "Legacy DT"


# ── Regression on the gap path with the actual seed shape ───────────
def test_overlay_payload_title_resolves_seeded_board_pack_shape():
    """The backlog-b seed writes the exact shape below; this row
    is what e1_tester saw rendering as 'Untitled document'."""
    row = _base_row(
        id="demo-t5backlog-bp-001",
        context_id="ctx-fake",
        kind="board_pack",
        title="[DEMO] Q1 2026 Tuli Financial Group Board Pack",
        status="complete",
        lifecycle_state="committed",
        structured_content={"sections": [{"heading": "Executive Summary",
                                          "paragraphs": ["..."]}]},
    )
    assert overlay_payload(row)["title"] == (
        "[DEMO] Q1 2026 Tuli Financial Group Board Pack"
    )
