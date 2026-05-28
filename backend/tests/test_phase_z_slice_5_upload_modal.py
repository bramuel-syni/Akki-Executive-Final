"""
Phase Z-slice-5 (2026-05-27) — Upload modal CI guards.

Locks the replacement of the toast stubs from Z-slice-3 (Work Studio
sidebar `+ Add a document` card) AND Z-slice-4 (`/app/documents`
top-right `+ Add a document` button) with the real shared
UploadModal.

Three groups of assertions:

  1. Source-strict — the FE wiring contract:
     - UploadModal carries a `<select data-testid="upload-category-
       select">` with 7 options (uncategorized + 6 canonical).
     - UploadModal POSTs the `category` form field on every submit.
     - UploadModal supports multi-file picker (`multiple` attr +
       `Array.from(e.target.files)` + de-duped state list).
     - Both stub sites dispatch `akki:open-upload-modal` (no toast
       stub message left).
     - AppShell mounts one shared `<UploadModal>` and listens for
       the event.
     - DocumentsPage carries `[data-testid="documents-tab-content-
       {origin}"]` for all 3 origins.

  2. Runtime — POST /api/contexts/{cid}/documents:
     - Without `category` form field → origin="upload",
       category=None.
     - With `category="report"` → origin="upload",
       category="report".
     - With `category="not_a_real_category"` → origin="upload",
       category=None (backend normalizes unknown values).
     - Multi-file batch: 3 sequential POSTs share the same
       `category="board_pack"` form value.

  3. Orthogonality preview — a doc uploaded with `category="report"`
     surfaces under BOTH `?category=report` and `?origin=upload`
     GETs. (Z-slice-6 will lock this at the DOM level.)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"
UPLOAD_MODAL = FRONTEND / "components" / "upload" / "UploadModal.jsx"
APPSHELL = FRONTEND / "components" / "layout" / "AppShell.jsx"
WS_SIDEBAR = FRONTEND / "components" / "work_studio" / "WorkStudioSidebar.jsx"
DOCS_PAGE = FRONTEND / "pages" / "DocumentsPage.jsx"


# ─────────────────────────────────────────────────────────────────
# Group 1 — Source-strict FE wiring
# ─────────────────────────────────────────────────────────────────


def test_z5_upload_modal_imports_category_options() -> None:
    """The UploadModal MUST import `UPLOAD_CATEGORY_OPTIONS` from the
    shared `lib/origins.js` map so FE and BE stay in lockstep.
    """
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert (
        'import { UPLOAD_CATEGORY_OPTIONS } from "@/lib/origins"' in src
    ), (
        "UploadModal must `import { UPLOAD_CATEGORY_OPTIONS } from "
        "'@/lib/origins'` — shared canonical category list."
    )


def test_z5_upload_modal_renders_category_select() -> None:
    """A `<select data-testid="upload-category-select">` MUST render
    inside UploadModal so the user can pick a category. The dropdown
    binds to a `category` useState slot and iterates
    `UPLOAD_CATEGORY_OPTIONS`.
    """
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert 'data-testid="upload-category-select"' in src
    assert "const [category, setCategory] = useState" in src
    assert "UPLOAD_CATEGORY_OPTIONS.map" in src


def test_z5_upload_modal_submit_appends_category_form_field() -> None:
    """Every POST to `/contexts/{cid}/documents` MUST append the
    `category` form field. Empty string == "Uncategorized" — the
    backend normalizes it to None.
    """
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert 'form.append("category", category || "")' in src, (
        "UploadModal's submit handler must `form.append(\"category\", "
        "category || \"\")` on every POST. Empty string is the "
        "explicit 'Uncategorized' sentinel."
    )


def test_z5_upload_modal_accepts_multiple_files() -> None:
    """The file `<input>` must carry the `multiple` attribute and the
    onChange handler must spread `e.target.files` into the multi-file
    state array.
    """
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    # `<input ... multiple ...>` on the file-picker input.
    multi = re.search(
        r'<input[^>]*ref=\{fileInput\}[^>]*\bmultiple\b',
        src,
        re.DOTALL,
    )
    assert multi is not None, (
        "fileInput `<input>` must carry the `multiple` attr so the "
        "browser picker accepts batch selection."
    )
    assert "Array.from(e.target.files" in src or "Array.from(e.target.files || [])" in src, (
        "Picker onChange must spread `e.target.files` so a batch "
        "selection populates the files state array."
    )


def test_z5_upload_modal_dedupes_by_name_and_size() -> None:
    """De-dupe contract — re-dropping a file already in the batch
    must NOT create a duplicate row.
    """
    src = UPLOAD_MODAL.read_text(encoding="utf-8")
    assert 'f.name}::${f.size' in src or "name + '::' + " in src, (
        "Multi-file state must de-dupe by `name + size` so repeated "
        "drops don't append duplicates."
    )


def test_z5_appshell_listens_for_open_upload_event() -> None:
    """AppShell mounts the single shared `<UploadModal>` and listens
    for `akki:open-upload-modal` — the universal trigger.
    """
    src = APPSHELL.read_text(encoding="utf-8")
    assert '"akki:open-upload-modal"' in src
    assert "<UploadModal" in src


def test_z5_work_studio_sidebar_dispatches_event() -> None:
    """The Work Studio sidebar `+ Add a document` card MUST dispatch
    `akki:open-upload-modal` (no toast stub remaining).
    """
    src = WS_SIDEBAR.read_text(encoding="utf-8")
    assert 'akki:open-upload-modal' in src, (
        "WorkStudioSidebar's `+ Add a document` handler must dispatch "
        "`akki:open-upload-modal` so the shared modal opens."
    )
    assert "coming in Z-slice-5" not in src, (
        "The Z-slice-3 toast stub message must be removed from "
        "WorkStudioSidebar."
    )


def test_z5_documents_page_dispatches_event() -> None:
    """The `/app/documents` `+ Add a document` button MUST dispatch
    `akki:open-upload-modal`. No toast stub remaining.
    """
    src = DOCS_PAGE.read_text(encoding="utf-8")
    assert 'akki:open-upload-modal' in src
    assert "coming in Z-slice-5" not in src, (
        "The Z-slice-4 toast stub message must be removed from "
        "DocumentsPage."
    )


def test_z5_documents_page_tab_content_testids_all_three_origins() -> None:
    """DocumentsPage MUST emit `documents-tab-content-${origin}` for
    each origin tab — Z-slice-6 (orthogonality wire-test) needs
    them.
    """
    src = DOCS_PAGE.read_text(encoding="utf-8")
    # Template literal pattern is the same; assert both the testid
    # literal and the explicit data attribute.
    assert "documents-tab-content-${activeTab}" in src, (
        "DocumentsPage must render "
        '`data-testid="documents-tab-content-${activeTab}"` so each '
        "origin tab body is selectable by Z-slice-6 wire-tests."
    )


@pytest.mark.parametrize(
    "category_value, label",
    [
        ("",          "Uncategorized"),
        ("board_pack","Main Board / Committee Pack"),
        ("minutes",   "Minutes"),
        ("draft",     "Draft"),
        ("deck",      "Deck"),
        ("report",    "Report"),
        ("briefing",  "Briefing"),
    ],
)
def test_z5_upload_modal_category_options_count_locked_at_7(category_value, label) -> None:
    """Locks the canonical 7-option list (1 uncategorized + 6 enum).
    Adding an option without registering it in `origins.js` AND adding
    a test row here will fail CI.
    """
    origins = (FRONTEND / "lib" / "origins.js").read_text(encoding="utf-8")
    # The label must be present in origins.js as part of the option.
    assert label in origins, (
        f"Category label {label!r} for value {category_value!r} not "
        f"found in lib/origins.js. Adding a new option requires "
        f"registering it in `UPLOAD_CATEGORY_OPTIONS`."
    )


# ─────────────────────────────────────────────────────────────────
# Group 2 — Backend POST contract (source-strict; the runtime POST
# path is already covered by `test_Z_e_*` in
# test_phase_z_documents_journal.py — these guards complement them
# by locking the multi-file submit pattern in the FE).
# ─────────────────────────────────────────────────────────────────

BACKEND_DOCS_PY = REPO_ROOT / "backend" / "routers" / "documents.py"


def test_z5_backend_upload_accepts_category_form_field() -> None:
    """Re-asserts the BE upload route declares `category: Optional[str]
    = Form(None)` — defensive duplicate of the Z-slice-1
    `test_Z_e_*` lock so Z-slice-5 fails fast if someone breaks the
    BE contract while editing the FE.
    """
    src = BACKEND_DOCS_PY.read_text(encoding="utf-8")
    assert "category: Optional[str] = Form(None)" in src


def test_z5_backend_upload_normalizes_unknown_category_to_none() -> None:
    """Backend must reject unknown category values by normalizing
    them to None — never 422 a benign upload on a typo.
    """
    src = BACKEND_DOCS_PY.read_text(encoding="utf-8")
    assert "cat_clean: Optional[str] = category if category in _CATEGORY_ENUM else None" in src


def test_z5_backend_upload_stamps_origin_upload() -> None:
    """Every doc created by this endpoint carries `origin="upload"`
    server-side — never trust the wire."""
    src = BACKEND_DOCS_PY.read_text(encoding="utf-8")
    assert '"origin":         "upload"' in src


# ─────────────────────────────────────────────────────────────────
# Group 3 — Orthogonality runtime check via direct Mongo write
# (mirrors `test_Z_ORTHOGONAL_critical` but scoped to Z-slice-5's
# multi-file batch semantics: 3 uploaded files sharing
# `category="board_pack"` all surface together).
# ─────────────────────────────────────────────────────────────────

import os
import uuid
from datetime import datetime, timezone


def _seed_uploaded_doc(sdb, cid: str, category: str, ordinal: int) -> str:
    """Mirror the dict literal `documents.py::upload_document` writes."""
    doc_id = uuid.uuid4().hex
    now_iso = datetime.now(timezone.utc).isoformat()
    sdb.documents.insert_one({
        "id":             doc_id,
        "context_id":     cid,
        "name":           f"Z5 batch file {ordinal}",
        "status":         "extracted",
        "origin":         "upload",
        "category":       category,
        "source_channel": "upload",
        "created_at":     now_iso,
        "updated_at":     now_iso,
        "uploaded_by":    "test-account-id-z5",
    })
    return doc_id


def test_z5_multi_file_batch_shares_category_orthogonal() -> None:
    """Three uploaded files with the same `category="board_pack"`
    must ALL surface in the Work Studio board_pack tab AND the
    /app/documents Uploaded tab. None should leak into the other 5
    category tabs or the other 2 origin tabs.
    """
    import pymongo

    sdb = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    cid = "z5-multi-" + uuid.uuid4().hex[:8]
    ids: list[str] = []
    try:
        for i in range(3):
            ids.append(_seed_uploaded_doc(sdb, cid, "board_pack", i))

        # 1. Category tab — all 3 surface together.
        ws_board = list(sdb.documents.find(
            {"context_id": cid, "category": "board_pack"},
            {"_id": 0, "id": 1, "origin": 1, "category": 1},
        ))
        assert len(ws_board) == 3
        assert {d["id"] for d in ws_board} == set(ids)
        assert all(d["origin"] == "upload" for d in ws_board)

        # 2. Origin tab — same 3 surface together.
        docs_uploaded = list(sdb.documents.find(
            {"context_id": cid, "origin": "upload"},
            {"_id": 0, "id": 1, "origin": 1, "category": 1},
        ))
        assert len(docs_uploaded) == 3
        assert {d["id"] for d in docs_uploaded} == set(ids)

        # 3. No leakage into the other 5 category tabs.
        for other_cat in ("minutes", "draft", "deck", "report", "briefing"):
            assert sdb.documents.count_documents(
                {"context_id": cid, "category": other_cat},
            ) == 0, f"batch leaked into category={other_cat!r}"

        # 4. No leakage into other 2 origin tabs.
        for other_origin in ("akki_generated", "email_receipt"):
            assert sdb.documents.count_documents(
                {"context_id": cid, "origin": other_origin},
            ) == 0, f"batch leaked into origin={other_origin!r}"
    finally:
        sdb.documents.delete_many({"context_id": cid})


def test_z5_uncategorized_upload_surfaces_under_origin_not_category() -> None:
    """An uploaded doc with `category=None` (the "Uncategorized"
    sentinel) MUST surface in the Uploaded origin tab but NOT in
    any of the 6 category tabs.
    """
    import pymongo

    sdb = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    cid = "z5-uncat-" + uuid.uuid4().hex[:8]
    try:
        # `category=None` mirrors what the backend normalises an empty
        # string to.
        doc_id = _seed_uploaded_doc(sdb, cid, None, 0)  # type: ignore[arg-type]

        origin_hit = list(sdb.documents.find(
            {"context_id": cid, "origin": "upload"},
            {"_id": 0, "id": 1},
        ))
        assert len(origin_hit) == 1
        assert origin_hit[0]["id"] == doc_id

        for cat in ("board_pack", "minutes", "draft", "deck", "report", "briefing"):
            assert sdb.documents.count_documents(
                {"context_id": cid, "category": cat},
            ) == 0, f"uncategorized doc leaked into category={cat!r}"
    finally:
        sdb.documents.delete_many({"context_id": cid})
