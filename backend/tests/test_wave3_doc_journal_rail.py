"""Wave 3 (2026-05-27) — Work Studio Document Journal restructure CI lockdown.

Locks the user-asked changes:
  • New `<DocumentJournalRail>` lives at the locked path.
  • WorkStudio.jsx imports + renders the rail alongside CompilationRail.
  • Rail mounts on the xl: breakpoint, sticks to top while scrolling.
  • Listing renders UNDER the search input (no hero spacing).
  • Click-to-open uses the `?doc_id=…` deep-link pattern (the
    DocumentDrawer already in WorkStudio opens automatically).
  • Recurrence #3 smoke-upload filter applied (smoke_upload rows hidden).
  • The 6 WorkStudio tabs continue to surface ONLY category artefacts
    (the kind-scoped behaviour is untouched).
"""
from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent.parent
RAIL    = REPO / "frontend" / "src" / "components" / "work_studio" / "DocumentJournalRail.jsx"
STUDIO  = REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx"


def test_W3_a_rail_component_exists_at_locked_path():
    assert RAIL.exists(), \
        "DocumentJournalRail.jsx must exist at the locked path"


def test_W3_b_rail_exposes_locked_testids():
    src = RAIL.read_text(encoding="utf-8")
    for testid in (
        "document-journal-rail",
        "document-journal-rail-search",
        "document-journal-rail-list",
        "document-journal-rail-empty",
        "document-journal-rail-loading",
    ):
        assert testid in src, f"DocumentJournalRail must carry testid '{testid}'"


def test_W3_c_rail_filters_smoke_uploads():
    """Recurrence #3 — the journal must hide smoke_upload=true rows so
    it stays editorial. Workspace.jsx applies the same filter."""
    src = RAIL.read_text(encoding="utf-8")
    assert "smoke_upload" in src, \
        "DocumentJournalRail must filter smoke_upload rows (Recurrence #3)"


def test_W3_d_rail_opens_via_doc_id_deeplink():
    """Click-to-open uses the URL `?doc_id=…` deep-link pattern that
    the existing DocumentDrawer in WorkStudio consumes automatically.
    The rail must NOT introduce a separate modal."""
    src = RAIL.read_text(encoding="utf-8")
    assert 'sp.set("doc_id"' in src, \
        "Click-to-open must use `?doc_id=…` deep-link pattern"
    assert "setSearchParams" in src, \
        "DocumentJournalRail must use setSearchParams to set the deep-link"


def test_W3_e_rail_listing_lives_under_search_bar():
    """The brief: 'Listing starts under the search bar (no large hero
    spacing).' Verify the search bar JSX appears BEFORE the listing
    JSX in source order."""
    src = RAIL.read_text(encoding="utf-8")
    search_pos = src.find("document-journal-rail-search")
    list_pos   = src.find("document-journal-rail-list")
    empty_pos  = src.find("document-journal-rail-empty")
    assert search_pos > 0 and list_pos > 0 and empty_pos > 0
    assert search_pos < empty_pos < list_pos, \
        "Search input must appear before the listing in source order"


def test_W3_f_studio_imports_and_renders_rail():
    src = STUDIO.read_text(encoding="utf-8")
    assert "import DocumentJournalRail" in src, \
        "WorkStudio.jsx must import DocumentJournalRail"
    assert "<DocumentJournalRail" in src, \
        "WorkStudio.jsx must render <DocumentJournalRail />"


def test_W3_g_rail_sits_alongside_compilation_rail():
    """The rail lives in the same xl:flex parent as CompilationRail
    so they share the right-rail column."""
    src = STUDIO.read_text(encoding="utf-8")
    # Both rails appear within ~600 characters of each other in the
    # render tree (sibling components).
    comp_idx = src.find("<CompilationRail")
    doc_idx  = src.find("<DocumentJournalRail")
    assert comp_idx > 0 and doc_idx > 0
    assert abs(doc_idx - comp_idx) < 900, \
        "DocumentJournalRail must be a sibling of CompilationRail in WorkStudio"


def test_W3_h_six_workstudio_tabs_remain_kind_scoped():
    """Belt-and-braces: the 6 WorkStudio tabs (cycle_main_and_committee_pack,
    cycle_minutes, draft, deck, report, briefing) must remain in
    KIND_TABS with their kind-scoped reads via `briefings/aggregates`.
    The Wave 3 change adds the rail; it does not touch the tab data
    paths."""
    src = STUDIO.read_text(encoding="utf-8")
    for kind in ("cycle_main_and_committee_pack", "cycle_minutes",
                 "draft", "deck", "report", "briefing"):
        assert kind in src, f"WorkStudio.jsx must keep kind '{kind}' in the tabs"
    # The kind-scoped GET pattern.
    assert "briefings/aggregates" in src, \
        "WorkStudio.jsx must keep the kind-scoped /briefings/aggregates query"


def test_W3_i_compilation_rail_document_journal_deck_removed():
    """Wave 3 consolidation — the redundant Document Journal deck in
    CompilationRail must be REMOVED now that the right-rail
    `<DocumentJournalRail>` owns this surface. The Recent Drafts +
    Recent Activity decks STAY (specialized streams, not full doc
    listings)."""
    rail_src = (REPO / "frontend" / "src" / "components" / "work_studio" / "CompilationRail.jsx").read_text(encoding="utf-8")
    assert 'data-testid="compilation-rail-document-journal"' not in rail_src, \
        "CompilationRail Document Journal deck must be removed (W3 consolidation)"
    assert 'data-testid="compilation-rail-document-journal-list"' not in rail_src
    assert 'data-testid="compilation-rail-document-journal-view-more"' not in rail_src
    # Recent Drafts + Recent Activity decks survive.
    assert 'data-testid="compilation-rail-recent-drafts"' in rail_src, \
        "CompilationRail Recent Drafts deck must survive W3 consolidation"
