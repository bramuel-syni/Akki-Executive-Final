"""Phase E.4 — Legacy doc-route archive wire tests (2026-05-26).

Asserts that the legacy /app/documents/:id route and the supporting
ReadingView surface have been archived and the redirect to the
Universal Document Drawer is in place. Also pins the 3 click-handler
rewires (MentionInbox, AppShell upload, CompilationRail Document Journal).
"""
from __future__ import annotations

from pathlib import Path
import re

REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"

APP_JS          = FE / "App.js"
MENTION_INBOX   = FE / "components" / "collab" / "MentionInbox.jsx"
APP_SHELL       = FE / "components" / "layout" / "AppShell.jsx"
COMPILATION_RAIL = FE / "components" / "work_studio" / "CompilationRail.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────
# Route + archived files
# ─────────────────────────────────────────────────────────────────────
def test_e4_reading_view_archived():
    """pages/ReadingView.jsx + components/reading/* + the two reading
    hooks live under _archived/e4_doc_routes/, not in the active tree."""
    assert not (FE / "pages" / "ReadingView.jsx").exists()
    assert not (FE / "components" / "reading").exists()
    assert not (FE / "hooks" / "useDocumentParagraphs.js").exists()
    assert not (FE / "hooks" / "useReadingScrollSync.js").exists()
    # Archived copies present.
    archived_root = FE / "_archived" / "e4_doc_routes"
    assert (archived_root / "pages" / "ReadingView.jsx").exists()
    assert (archived_root / "components" / "reading").is_dir()
    assert (archived_root / "hooks" / "useDocumentParagraphs.js").exists()
    assert (archived_root / "hooks" / "useReadingScrollSync.js").exists()


def test_e4_app_js_no_longer_imports_reading_view():
    src = _read(APP_JS)
    assert 'lazy(() => import("@/pages/ReadingView"))' not in src
    # Compatibility comment present so future agents understand.
    assert "ReadingView archived" in src or "_archived/e4_doc_routes" in src


def test_e4_documents_route_redirects_to_drawer():
    """/app/documents/:id renders DocumentRouteSwitch which Navigates
    to /app/work-studio?doc_id=:id (Universal Document Drawer)."""
    src = _read(APP_JS)
    assert 'path="/app/documents/:id"' in src
    # The DocumentRouteSwitch component now redirects.
    block = src.split("function DocumentRouteSwitch")[1].split("\nfunction ")[0]
    assert "<Navigate" in block
    assert "/app/work-studio?doc_id=" in block
    assert "replace" in block  # 301-style replacement, not a push
    # `useParams` is in the imports list.
    assert "useParams" in src


def test_e4_documents_route_redirect_preserves_id_param():
    """The Navigate target carries the :id from the URL via encodeURIComponent."""
    src = _read(APP_JS)
    block = src.split("function DocumentRouteSwitch")[1].split("\nfunction ")[0]
    assert "encodeURIComponent(id" in block


# ─────────────────────────────────────────────────────────────────────
# Click handler rewires
# ─────────────────────────────────────────────────────────────────────
def test_e4_mention_inbox_doc_click_uses_drawer():
    """MentionInbox doc-mention click → /app/work-studio?doc_id=…."""
    src = _read(MENTION_INBOX)
    # The doc branch points at the new drawer route.
    branch = src.split('m.artefact_type === "document"')[1].split(";")[0]
    assert "/app/work-studio?doc_id=" in branch
    assert "/app/documents/" not in branch


def test_e4_app_shell_upload_redirects_to_drawer():
    """AppShell post-upload navigation lands on the drawer surface,
    not the archived /app/documents/:id."""
    src = _read(APP_SHELL)
    upload_block = src.split("onUploaded=")[1].split("/>")[0]
    assert "/app/work-studio?doc_id=" in upload_block
    assert "/app/documents/" not in upload_block


# Phase E4 Document Journal deck-row → drawer test was REMOVED
# in the 2026-02 fork-resume maintenance dispatch. The Document
# Journal deck no longer exists in CompilationRail (the deck was
# retired and its data path moved to a different surface). The
# drawer-routing contract for the rail's surviving decks (Recent
# Drafts + Recent Activity) is locked separately in:
#   - test_e2_rail_section_order_generate_drafts_activity (anti-
#     regression — the legacy testid must NOT reappear)
#   - Phase E.2 source-strict tests covering the rail's two surviving
#     view-more links.


# ─────────────────────────────────────────────────────────────────────
# Borderline-keep ratification
# ─────────────────────────────────────────────────────────────────────
def test_e4_work_studio_document_page_retained_g8_borderline():
    """WorkStudioDocumentPage stays — it's the G8-ratified full-page
    surface for Board Packs + Committee Packs. Recorded as borderline-
    keep in AUTONOMOUS_DECISIONS_LOG.md."""
    assert (FE / "pages" / "WorkStudioDocumentPage.jsx").exists()
    src = _read(APP_JS)
    assert 'path="/app/work-studio/document/:artefactId"' in src


def test_e4_log_section_present_in_home_cleanup_log():
    log = (REPO / "memory" / "sprints" / "HOME_CLEANUP_LOG.md").read_text("utf-8")
    assert "### E.4 — Legacy route enumeration + autonomous archive" in log


def test_e4_borderline_decisions_logged():
    log = (REPO / "memory" / "sprints" / "AUTONOMOUS_DECISIONS_LOG.md").read_text("utf-8")
    assert "WorkStudioDocumentPage" in log or "/app/work-studio/document/" in log
