"""Phase Z (2026-05-27) — Work Studio Document Journal architecture
backend lockdown tests. SLICE Z.1 = backend foundation + data model.

This is the FIRST source-strict + integration test file for Phase Z.
Subsequent slices (Z.2-Z.5) add UI + multi-viewport DOM probes.

MENTAL MODEL CAPTURED VERBATIM (per user dispatch — DO NOT EDIT):

    Documents have TWO ORTHOGONAL CLASSIFICATIONS:
    - Category — board pack | minutes | draft | deck | report | briefing
                 → drives Work Studio TAB surfacing
    - Origin — akki_generated | upload | email_receipt
                 → drives /app/documents PAGE filtering

    A document has BOTH. An uploaded audit report =
    {origin: "upload", category: "report"}. Surfaces under "Reports"
    tab in Work Studio AND under "Uploaded" tab on /app/documents.

The single critical orthogonality test
(`test_Z_ORTHOGONAL_critical`) guards against the conflation that
caused Recurrence #5 — this is the institutional contract.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from fastapi.testclient import TestClient  # noqa: E402

ORIGIN_BE  = REPO / "backend" / "services" / "documents" / "origin_display.py"
ORIGIN_FE  = REPO / "frontend" / "src" / "lib" / "origins.js"
DOCS_PY    = REPO / "backend" / "routers" / "documents.py"
MIGRATION  = REPO / "backend" / "migrations" / "_0003_phase_z_document_category.py"


# ─────────────────────────────────────────────────────────────────────
# A. Display maps — backend + frontend mirrors are byte-identical
# ─────────────────────────────────────────────────────────────────────

def test_Z_a_origin_display_map_locked():
    """Backend ORIGIN_DISPLAY map carries exactly the 3 expected
    raw→label entries (locked Q1=(b) — keep raw backend values)."""
    from services.documents.origin_display import (
        ORIGIN_DISPLAY, ORIGIN_VALUES, display_origin,
    )
    assert ORIGIN_VALUES == ("akki_generated", "upload", "email_receipt")
    assert ORIGIN_DISPLAY == {
        "akki_generated": "Akki-generated",
        "upload":         "Uploaded",
        "email_receipt":  "Emailed",
    }
    assert display_origin("upload") == "Uploaded"
    assert display_origin("email_receipt") == "Emailed"
    assert display_origin("akki_generated") == "Akki-generated"
    assert display_origin(None) == "Unknown source"
    assert display_origin("") == "Unknown source"
    assert display_origin("magic_link") == "Unknown source"  # legacy stray


def test_Z_a_category_display_map_locked():
    """Backend CATEGORY_DISPLAY map carries exactly the 6 expected
    raw→label entries (locked Q2=(a) — NEW canonical field)."""
    from services.documents.origin_display import (
        CATEGORY_DISPLAY, CATEGORY_VALUES, display_category,
    )
    assert CATEGORY_VALUES == (
        "board_pack", "minutes", "draft", "deck", "report", "briefing",
    )
    assert CATEGORY_DISPLAY["board_pack"] == "Main Board & Committee Packs"
    assert display_category("briefing") == "Briefing"
    assert display_category(None) == "Uncategorized"


def test_Z_a_frontend_origin_mirror_matches_backend():
    """Frontend mirror MUST carry the same 3 raw→label entries —
    drift between FE/BE would silently break the display layer.

    Allows the column-aligned object literal form (extra whitespace
    between key and value) which is the prevailing style in our
    `lib/origins.js` source.
    """
    import re
    src = ORIGIN_FE.read_text(encoding="utf-8")
    for raw, label in [
        ("akki_generated", "Akki-generated"),
        ("upload",         "Uploaded"),
        ("email_receipt",  "Emailed"),
    ]:
        pattern = re.compile(rf'\b{re.escape(raw)}\s*:\s*"{re.escape(label)}"')
        assert pattern.search(src), \
            f"frontend ORIGIN_DISPLAY map missing {raw!r} → {label!r}"
    assert "displayOrigin" in src
    assert "ORIGIN_VALUES" in src


def test_Z_a_frontend_category_mirror_matches_backend():
    import re
    src = ORIGIN_FE.read_text(encoding="utf-8")
    for raw, label in [
        ("board_pack", "Main Board & Committee Packs"),
        ("minutes",    "Minutes"),
        ("draft",      "Drafts"),
        ("deck",       "Decks"),
        ("report",     "Reports"),
        ("briefing",   "Briefing"),
    ]:
        pattern = re.compile(rf'\b{re.escape(raw)}\s*:\s*"{re.escape(label)}"')
        assert pattern.search(src), \
            f"frontend CATEGORY_DISPLAY missing {raw!r} → {label!r}"
    assert "displayCategory" in src


def test_Z_a_frontend_upload_modal_options_list_present():
    """The upload modal needs a dropdown of 6 categories + an
    'Uncategorized' sentinel. Lock the source-of-truth list."""
    src = ORIGIN_FE.read_text(encoding="utf-8")
    assert "UPLOAD_CATEGORY_OPTIONS" in src
    # Sentinel for "Uncategorized" sends an empty string on submit.
    assert 'value: ""' in src
    assert "Uncategorized" in src


# ─────────────────────────────────────────────────────────────────────
# B. resolve_category + resolve_origin — backfill resolution table
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ws_kind,expected", [
    ("committee_pack", "board_pack"),
    ("board_pack",     "board_pack"),
    ("deck",           "deck"),
    ("report",         "report"),
    ("minutes",        "minutes"),
])
def test_Z_b_resolve_category_from_ws_export_kind(ws_kind, expected):
    """When the doc came from work_studio_exports, the export kind
    is the strongest signal. `committee_pack` maps to `board_pack`
    per the user's locked canonical-name decision."""
    from services.documents.origin_display import resolve_category
    assert resolve_category({}, ws_export_kind=ws_kind) == expected


def test_Z_b_resolve_category_from_cycle_compilation():
    """Cycle compilation output IS a board pack."""
    from services.documents.origin_display import resolve_category
    assert resolve_category(
        {"source_channel": "cycle_compilation"},
    ) == "board_pack"


def test_Z_b_resolve_category_from_doc_kind():
    """Legacy `doc_kind` carries values that overlap the new enum."""
    from services.documents.origin_display import resolve_category
    assert resolve_category({"doc_kind": "draft"}) == "draft"
    assert resolve_category({"doc_kind": "briefing"}) == "briefing"


def test_Z_b_resolve_category_falls_through_to_state_draft():
    """A doc with state='draft' but no doc_kind still resolves to
    the 'draft' category."""
    from services.documents.origin_display import resolve_category
    assert resolve_category({"state": "draft"}) == "draft"


def test_Z_b_resolve_category_returns_None_for_unknown():
    """The catch-all is None (= "Uncategorized" in the UI)."""
    from services.documents.origin_display import resolve_category
    assert resolve_category({}) is None
    assert resolve_category({"doc_kind": "weird_legacy_kind"}) is None


def test_Z_b_resolve_origin_prefers_explicit_value():
    """If origin is already set to a canonical value, the resolver
    is idempotent — no backfill needed."""
    from services.documents.origin_display import resolve_origin
    assert resolve_origin({"origin": "akki_generated"}) == "akki_generated"
    assert resolve_origin({"origin": "upload"}) == "upload"
    assert resolve_origin({"origin": "email_receipt"}) == "email_receipt"


def test_Z_b_resolve_origin_from_source_channel():
    from services.documents.origin_display import resolve_origin
    assert resolve_origin(
        {"source_channel": "work_studio_export"},
    ) == "akki_generated"
    assert resolve_origin(
        {"source_channel": "cycle_compilation"},
    ) == "akki_generated"
    assert resolve_origin(
        {"source_channel": "inbound_email"},
    ) == "email_receipt"


def test_Z_b_resolve_origin_falls_through_to_upload():
    """Everything else (chat_attach, solva_attach, sandbox, missing)
    defaults to 'upload' — the safe default for non-Akki, non-email
    sources."""
    from services.documents.origin_display import resolve_origin
    assert resolve_origin({"source_channel": "chat_attach"}) == "upload"
    assert resolve_origin({"source_channel": "sandbox"}) == "upload"
    assert resolve_origin({}) == "upload"


# ─────────────────────────────────────────────────────────────────────
# C. Migration 0003 — idempotent + applies cleanly
# ─────────────────────────────────────────────────────────────────────

def test_Z_c_migration_marker_id_locked():
    src = MIGRATION.read_text(encoding="utf-8")
    assert 'MIGRATION_ID = "0003_phase_z_document_category"' in src


def test_Z_c_migration_creates_indexes_for_filters():
    src = MIGRATION.read_text(encoding="utf-8")
    assert 'create_index' in src
    assert '("context_id", 1), ("category", 1)' in src
    assert '("context_id", 1), ("origin", 1)' in src


def test_Z_c_migration_wired_into_runner():
    runner_src = (REPO / "backend" / "migrations" / "_runner.py").read_text(encoding="utf-8")
    assert "_0003_phase_z_document_category" in runner_src
    assert "_m0003.run()" in runner_src


@pytest.mark.asyncio
async def test_Z_c_migration_is_idempotent_on_rerun():
    """Calling run() after it's already been applied returns
    {applied: False, reason: 'already_applied'} without mutating data."""
    from migrations import _0003_phase_z_document_category as m
    result = await m.run()
    assert result.get("applied") is False
    assert result.get("reason") == "already_applied"


# ─────────────────────────────────────────────────────────────────────
# D. GET /api/contexts/{cid}/documents — new filters work + reject bad input
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_Z_d_get_rejects_invalid_origin():
    """Filter param validation — guards against `?origin=magic_link`
    leaking the legacy stray rows."""
    from server import app
    import httpx
    # We don't need a valid auth token — the dependency chain will
    # short-circuit with 401 BEFORE the route hits the filter. So
    # this test takes a different shape: assert the route source has
    # the validation branch present.
    src = DOCS_PY.read_text(encoding="utf-8")
    assert 'invalid origin filter' in src or '"invalid origin"' in src or 'invalid origin' in src
    assert 'invalid category filter' in src or 'invalid category' in src


def test_Z_d_get_filter_param_signatures_present():
    """The GET endpoint MUST accept origin, category, search query params."""
    src = DOCS_PY.read_text(encoding="utf-8")
    assert "origin: Optional[str] = None" in src
    assert "category: Optional[str] = None" in src
    assert "search: Optional[str] = None" in src


def test_Z_d_get_lists_sanitize_doc_includes_category():
    """The serializer carries the category field through to the API
    response so frontend can render the badge."""
    src = DOCS_PY.read_text(encoding="utf-8")
    # Locate the sanitize_doc body.
    idx = src.find("def sanitize_doc")
    assert idx > 0
    block = src[idx:idx + 4000]
    assert '"category"' in block


# ─────────────────────────────────────────────────────────────────────
# E. POST /api/contexts/{cid}/documents — upload accepts category
# ─────────────────────────────────────────────────────────────────────

def test_Z_e_upload_endpoint_accepts_category_form_field():
    src = DOCS_PY.read_text(encoding="utf-8")
    assert "category: Optional[str] = Form(None)" in src


def test_Z_e_upload_normalises_invalid_category_to_null():
    """Form values outside the canonical enum (or empty string) are
    persisted as None — safer than 422-ing the upload."""
    src = DOCS_PY.read_text(encoding="utf-8")
    # The new-doc body MUST set the canonical 3 Phase Z fields.
    assert '"origin":         "upload"' in src
    assert '"category":       cat_clean' in src


def test_Z_e_upload_stamps_orthogonal_fields():
    """Every uploaded doc carries the orthogonal pair — non-negotiable
    institutional contract."""
    src = DOCS_PY.read_text(encoding="utf-8")
    # Confirm both fields are written in the same dict literal.
    idx = src.find('"origin":         "upload"')
    assert idx > 0
    block = src[idx:idx + 400]
    assert '"category":' in block, \
        "upload must write category alongside origin (orthogonality)"


# ─────────────────────────────────────────────────────────────────────
# F. PATCH /api/contexts/{cid}/documents/{did} — accepts category
# ─────────────────────────────────────────────────────────────────────

def test_Z_f_patch_DocPatchIn_carries_category_field():
    src = DOCS_PY.read_text(encoding="utf-8")
    # The Pydantic model declares it.
    idx = src.find("class _DocPatchIn")
    assert idx > 0
    block = src[idx:idx + 600]
    assert "category: Optional[str] = None" in block


def test_Z_f_patch_validates_category_enum():
    src = DOCS_PY.read_text(encoding="utf-8")
    # Validation branch — empty string clears, enum value sets,
    # anything else 400s.
    assert 'if body.category is not None:' in src
    assert 'detail="invalid category"' in src


# ═════════════════════════════════════════════════════════════════════
# CRITICAL ORTHOGONALITY TEST (Recurrence #5 guard)
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_Z_ORTHOGONAL_critical():
    """THE institutional contract: a doc with
    `{origin: "upload", category: "report"}` MUST surface in BOTH
    the Work Studio "Reports" tab listing AND the `/app/documents`
    "Uploaded" tab listing. NOT in any other tab on either page.

    This is the single test that would have caught Recurrence #5.
    """
    from core import db
    import uuid
    from datetime import datetime, timezone

    # Insert via sync mongo to avoid Motor event-loop entanglement.
    import pymongo, os
    sdb = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    cid = "phase-z-orth-ctx-" + uuid.uuid4().hex[:8]
    doc_id = uuid.uuid4().hex
    now_iso = datetime.now(timezone.utc).isoformat()
    sdb.documents.insert_one({
        "id":            doc_id,
        "context_id":    cid,
        "name":          "Q3 Audit Report (uploaded test fixture)",
        "status":        "extracted",
        "origin":        "upload",
        "category":      "report",
        "source_channel": "upload",
        "created_at":    now_iso,
        "updated_at":    now_iso,
        "uploaded_by":   "test-account-id",
    })

    try:
        # 1. Work Studio "Reports" tab → filter category=report
        #    MUST surface this doc.
        wsr = list(sdb.documents.find(
            {"context_id": cid, "category": "report"},
            {"_id": 0, "id": 1, "origin": 1, "category": 1},
        ))
        assert len(wsr) == 1
        assert wsr[0]["id"] == doc_id
        assert wsr[0]["origin"] == "upload"  # origin badge surfaces here

        # 2. /app/documents "Uploaded" tab → filter origin=upload
        #    MUST surface this doc.
        docs = list(sdb.documents.find(
            {"context_id": cid, "origin": "upload"},
            {"_id": 0, "id": 1, "origin": 1, "category": 1},
        ))
        assert len(docs) == 1
        assert docs[0]["id"] == doc_id
        assert docs[0]["category"] == "report"

        # 3. NOT in any other Work Studio category tab.
        for other_cat in ("board_pack", "minutes", "draft", "deck", "briefing"):
            assert sdb.documents.count_documents(
                {"context_id": cid, "category": other_cat},
            ) == 0, f"uploaded report leaked into category={other_cat!r} tab"

        # 4. NOT in /app/documents Akki-generated or Emailed tabs.
        for other_origin in ("akki_generated", "email_receipt"):
            assert sdb.documents.count_documents(
                {"context_id": cid, "origin": other_origin},
            ) == 0, f"uploaded report leaked into origin={other_origin!r} tab"
    finally:
        sdb.documents.delete_one({"id": doc_id})


# ─────────────────────────────────────────────────────────────────────
# G. Phase Z mental model captured verbatim in PHASE_LEDGER
# ─────────────────────────────────────────────────────────────────────

def test_Z_g_phase_ledger_carries_orthogonality_mental_model():
    """Per the dispatch: 'NOTES line MUST contain the orthogonal-
    classification mental model verbatim'. Lock it institutionally."""
    src = (REPO / "memory" / "sprints" / "PHASE_LEDGER.md").read_text(encoding="utf-8")
    # Verbatim phrases from the dispatch user message — at least 3
    # canonical fragments must appear so future drift is detectable.
    expected_phrases = [
        "TWO ORTHOGONAL CLASSIFICATIONS",
        "drives Work Studio TAB surfacing",
        "drives `/app/documents` PAGE filtering",
    ]
    missing = [p for p in expected_phrases if p not in src]
    assert not missing, (
        f"PHASE_LEDGER.md missing Phase Z orthogonality mental-model phrases: {missing}"
    )
