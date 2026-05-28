"""Phase O — Document Drawer Universal Discipline CI guards (2026-05-27).

Per Phase E.3 spec, every doc-open surface in the app MUST route through
the canonical `?doc_id=` URL contract → universal `<DocumentDrawer>` mount.
Surface-level audit (Phase O Stage-1B inventory, 2026-05-27) found 17
doc-open surfaces:
  • 11 already compliant (use `navigate("?doc_id=…")` or equivalent)
  • 2 non-compliant — both in WorkStudio.jsx:
      1. BriefRow click → setDrawerAid+setDrawerOpen → legacy <BriefDrawer>
      2. DocumentCardsSection minutes/decks/reports click →
         setOverlayAid+setOverlayOpen → legacy <DocumentOverlay>
  • 2 theoretical (AskPanel.onCitationClick) — AskPanel has ZERO importers,
    dead code, no live concern.
  • 1 out-of-scope (NedMeeting page — Workspace artefact, not a doc-open).

This guard locks the compliance baseline AND blocks regressions.
"""
from __future__ import annotations

import re

import pytest
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
WS = REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx"

# Surfaces that MUST use the canonical `?doc_id=` URL contract OR
# DocumentDrawer-targeted navigation. Pinned to actual files.
COMPLIANT_SURFACES = [
    REPO / "frontend" / "src" / "pages" / "WorkStudioActivity.jsx",
    REPO / "frontend" / "src" / "pages" / "TaskManager.jsx",
    REPO / "frontend" / "src" / "pages" / "Pulse.jsx",
    REPO / "frontend" / "src" / "pages" / "Cycle.jsx",
    REPO / "frontend" / "src" / "pages" / "Workspace.jsx",
    REPO / "frontend" / "src" / "pages" / "Events.jsx",
    REPO / "frontend" / "src" / "components" / "mentions" / "MentionInbox.jsx",
    REPO / "frontend" / "src" / "components" / "shell" / "AppShell.jsx",
    REPO / "frontend" / "src" / "components" / "compilation" / "CompilationRail.jsx",
    REPO / "frontend" / "src" / "components" / "follow_up_drafts" / "FollowUpDraftsCard.jsx",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# Positive — all compliant surfaces use `?doc_id=` URL contract
# ─────────────────────────────────────────────────────────────────

def test_o_compliant_surfaces_use_doc_id_url_contract():
    """Every previously-compliant surface MUST keep its `?doc_id=`
    canonical navigation. Regression guard."""
    failing = []
    for p in COMPLIANT_SURFACES:
        if not p.exists():
            continue
        src = _read(p)
        # Either a `navigate("/app/work-studio?doc_id=…")` call OR a
        # `searchParams set({doc_id: ...})` OR a hardcoded link to the
        # legacy `/app/documents/:id` redirect (per App.js).
        ok = (
            "doc_id=" in src
            or "doc_id:" in src
            or "/app/documents/" in src
        )
        if not ok:
            failing.append(str(p.relative_to(REPO)))
    assert not failing, (
        f"Surfaces lost the canonical `?doc_id=` URL contract: {failing}"
    )


# ─────────────────────────────────────────────────────────────────
# Negative regression — WorkStudio entry points DON'T bypass via setters
# ─────────────────────────────────────────────────────────────────

def test_o_workstudio_briefrow_click_uses_canonical_url():
    """The Work Studio listing-row click handler `onOpenBrief` must
    redirect through `setSearchParams({ doc_id: … })` per Phase O,
    NOT through the legacy `setDrawerAid + setDrawerOpen` toggle."""
    src = _read(WS)
    # Strip comments first.
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    # Find the `onOpenBrief` arrow body.
    m = re.search(
        r"const\s+onOpenBrief\s*=\s*\(?row\)?\s*=>\s*\{([\s\S]*?)\};",
        code,
    )
    assert m, "onOpenBrief handler not found."
    body = m.group(1)
    # Positive — uses setSearchParams or navigate with ?doc_id=
    assert "setSearchParams" in body and "doc_id" in body, (
        "onOpenBrief must route through `setSearchParams({ doc_id: ... })` "
        "per Phase O canonical URL contract."
    )
    # Negative — the legacy state toggles MUST be gone from this body
    assert "setDrawerAid" not in body, (
        "onOpenBrief must NOT call setDrawerAid (legacy BriefDrawer bypass)."
    )
    assert "setDrawerOpen" not in body, (
        "onOpenBrief must NOT call setDrawerOpen (legacy BriefDrawer bypass)."
    )


@pytest.mark.skip(reason="Superseded by Phase Z-slice-2 (2026-05-27) — DocumentCardsSection REMOVED from WorkStudio.jsx (unified documents listing subsumes its role). The canonical-URL contract is preserved by DocumentRow's onOpen handler — see `test_phase_z_documents_journal.py::test_Z2_o_row_click_other_categories_open_via_doc_id`.")
def test_o_workstudio_document_cards_section_uses_canonical_url():
    """DocumentCardsSection.onOpenDocument minutes/decks/reports branch
    must redirect through `setSearchParams({ doc_id: … })`, NOT through
    `setOverlayAid + setOverlayOpen` (legacy DocumentOverlay bypass)."""
    src = _read(WS)
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    m = re.search(
        r"<DocumentCardsSection[\s\S]*?onOpenDocument=\{[\s\S]*?\}\}\s*\n?\s*/>",
        code,
    )
    assert m, "DocumentCardsSection onOpenDocument handler not found."
    block = m.group(0)
    # Negative — the legacy state setters must be gone from this block
    assert "setOverlayAid" not in block, (
        "DocumentCardsSection onOpenDocument must NOT call setOverlayAid."
    )
    assert "setOverlayOpen" not in block, (
        "DocumentCardsSection onOpenDocument must NOT call setOverlayOpen."
    )
    # Positive — setSearchParams with doc_id, OR navigate to dedicated page
    assert "setSearchParams" in block, (
        "DocumentCardsSection onOpenDocument must use setSearchParams "
        "for the minutes/decks/reports branch."
    )


def test_o_window_event_listener_redirects_to_canonical_url():
    """The `akki:open-document-overlay` window event listener is
    belt-and-suspenders: even if a legacy code path fires the event,
    it must redirect through the canonical URL contract instead of
    mounting the legacy DocumentOverlay."""
    src = _read(WS)
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    # Find the listener body.
    m = re.search(
        r"const\s+onOpenOverlay\s*=\s*\([^)]*\)\s*=>\s*\{([\s\S]*?)\};",
        code,
    )
    assert m, "akki:open-document-overlay listener body not found."
    body = m.group(1)
    assert "setSearchParams" in body and "doc_id" in body, (
        "Window-event listener must redirect to canonical `?doc_id=` URL."
    )
    assert "setOverlayAid" not in body, (
        "Window-event listener must NOT set legacy overlay state."
    )


def test_o_document_drawer_mount_still_present():
    """The Universal DocumentDrawer mount (the receiving end of every
    `?doc_id=` URL navigation) MUST remain mounted in WorkStudio.jsx."""
    src = _read(WS)
    assert "<DocumentDrawer" in src, (
        "Universal <DocumentDrawer> mount MUST remain in WorkStudio.jsx — "
        "it's the canonical mount per Phase E.3 spec."
    )


# ─────────────────────────────────────────────────────────────────
# Source-strict: no NEW non-canonical surfaces introduced
# ─────────────────────────────────────────────────────────────────

def test_o_no_new_documentoverlay_mounts_outside_workstudio():
    """No `<DocumentOverlay>` mount may appear outside WorkStudio.jsx's
    legacy-defended stub mount. If a new mount appears, it bypasses
    Phase O discipline and must be redirected to the canonical URL."""
    import subprocess
    out = subprocess.run(
        ["grep", "-rEln", r"<DocumentOverlay\b",
         str(REPO / "frontend" / "src")],
        capture_output=True, text=True,
    )
    files = [
        ln for ln in (out.stdout or "").splitlines()
        if "_archived" not in ln and "node_modules" not in ln
    ]
    # Allowlist: WorkStudio.jsx's legacy stub mount (kept for back-compat
    # while the file itself stays in the tree) + DocumentOverlay's own
    # definition file + WorkStudioDocumentPage which uses DocumentOverlay
    # as the rendering shell for the dedicated W3 full-page surface
    # (G8 ratified: Board Pack + Committee Pack get a dedicated page,
    # not the side drawer).
    allowlist = {
        str(REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx"),
        str(REPO / "frontend" / "src" / "pages" / "WorkStudioDocumentPage.jsx"),
        str(REPO / "frontend" / "src" / "components" / "work_studio" / "overlay" / "DocumentOverlay.jsx"),
    }
    rogue = [f for f in files if f not in allowlist]
    assert not rogue, (
        f"DocumentOverlay mounts found outside Phase O allowlist: {rogue}. "
        f"Every doc-open MUST use `?doc_id=` → <DocumentDrawer>."
    )
