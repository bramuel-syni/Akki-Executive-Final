"""E.3 runtime drawer regression test — 2026-05-26.

The original F.3 wire test
`test_e3_document_drawer_mounted_on_every_primary_surface` checked
JSX imports and passed by false-green. A user on production
(akki.syni.ai) reported the Workspace Document Journal rendering an
inline legacy `JournalDrawer` (TOPLINE / FROM AKKI / BODY EXCERPT
sections + 5 wrong CTAs) instead of the spec'd universal
`DocumentDrawer` (5 tabs + 5 canonical-URL CTAs).

These tests close that gap with assertions that catch the **runtime
shape** of each doc-listing surface, not just import presence:

  T1. No doc-listing page defines an inline legacy drawer
      (no `function JournalDrawer`, no `function QuickPreview*`,
      no `<aside ... data-testid="journal-drawer*">` in render).

  T2. Each surface's row-click handler routes to the canonical
      `?doc_id=<uuid>` URL contract — setting URL params rather
      than mounting a local drawer.

  T3. The universal `<DocumentDrawer>` is mounted on every
      doc-listing page AND carries the spec'd 5 tabs + 5 CTAs.

  T4. The legacy JournalDrawer module IS archived (sentinel file
      exists in `_archived_coverage_loss/`).

Together these catch any future divergence from the E.3 spec on
either side — defining a new inline drawer OR breaking the URL
contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

# Surfaces that list documents and must use the universal drawer.
# Each entry: (path_to_jsx, friendly_name, row_click_expectation)
DOC_LISTING_SURFACES = [
    # File path, friendly name
    (FE / "pages" / "Workspace.jsx",  "Workspace"),
    (FE / "pages" / "WorkStudio.jsx", "Work Studio"),
    (FE / "pages" / "Pulse.jsx",      "Pulse"),
    (FE / "pages" / "Cycle.jsx",      "Cycle"),
]

DOCUMENT_DRAWER_PATH = FE / "components" / "documents" / "DocumentDrawer.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. No inline legacy drawer on any doc-listing surface ─────────
def test_no_inline_legacy_drawer_definitions_on_doc_listing_surfaces():
    """The regression mode was an inline `function JournalDrawer` /
    `QuickPreview` / `function FooDrawer` defined IN the same file as
    the doc-listing page. We assert no such inline drawer component
    is defined on any of the 4 spec'd surfaces."""
    legacy_patterns = [
        "function JournalDrawer",
        "function QuickPreview",
        "function QuickPreviewDrawer",
        "function DocumentJournalDrawer",
        # Inline drawer JSX shapes
        'data-testid="journal-drawer"',
        'data-testid="journal-drawer-panel"',
        'data-testid="quick-preview"',
        # Legacy CTA labels from the regression report
        "Open full reader",
        "Take into Solva",
        "Add to Cycle",
        "Add to Work Studio",
        "Ask in Chat",
    ]
    for jsx, name in DOC_LISTING_SURFACES:
        src = _read(jsx)
        # Strip block comments before scanning so doc-comments don't
        # produce false positives.
        import re
        src_no_block = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
        for pat in legacy_patterns:
            assert pat not in src_no_block, (
                f"Legacy-drawer pattern {pat!r} found in {name} "
                f"({jsx.relative_to(REPO)}) — the universal DocumentDrawer "
                f"must be the only drawer surface for doc rows."
            )


# ── T2. Row click routes via canonical ?doc_id= URL ────────────────
def test_workspace_row_click_sets_doc_id_url_param():
    """Workspace.jsx — the regression surface. The row click must
    set `?doc_id=` on the URL (driving the universal drawer) and
    must NOT set local `drawerDoc` state for legacy rendering."""
    src = _read(FE / "pages" / "Workspace.jsx")
    # Row click invokes `openDrawer(row.id)`.
    assert "onClick={() => openDrawer(row.id)}" in src
    # openDrawer body must set the URL param, NOT a local doc state
    # for a legacy drawer body.
    assert 'sp.set("doc_id"' in src, (
        "Workspace.openDrawer must set the canonical `doc_id` URL "
        "param so the universal DocumentDrawer self-mounts."
    )
    # No leftover local-state drawer rendering.
    assert "<JournalDrawer" not in src
    # Mount the universal drawer.
    assert "<DocumentDrawer" in src


def test_all_doc_listing_surfaces_mount_universal_drawer():
    """Every spec'd doc-listing surface mounts <DocumentDrawer>."""
    for jsx, name in DOC_LISTING_SURFACES:
        src = _read(jsx)
        assert "<DocumentDrawer" in src, (
            f"{name} ({jsx.relative_to(REPO)}) is missing the universal "
            "<DocumentDrawer> mount — E.3 drawer regression."
        )
        # Import must reference the canonical path.
        assert 'from "@/components/documents/DocumentDrawer"' in src, (
            f"{name} must import <DocumentDrawer> from the canonical path "
            "to avoid drift via aliased copies."
        )


# ── T3. Universal DocumentDrawer ships 5 tabs + 5 spec'd CTAs ─────
def test_document_drawer_has_5_spec_tabs():
    src = _read(DOCUMENT_DRAWER_PATH)
    for tab in ("document", "intelligence", "notes", "signals", "related"):
        assert f'data-testid="drawer-tab-{tab}"' in src, (
            f"DocumentDrawer is missing tab `{tab}` — E.3 spec requires "
            "5 tabs (Document / Intelligence / Summary & Notes / Signals / Related)."
        )


def test_document_drawer_has_5_spec_ctas_with_canonical_urls():
    src = _read(DOCUMENT_DRAWER_PATH)
    # Five spec'd CTAs.
    for cta in (
        "drawer-cta-use-in-solva",
        "drawer-cta-use-in-chat",
        "drawer-cta-generate-brief",
        "drawer-cta-test-hypothesis",
        "drawer-cta-share",
    ):
        assert f'data-testid="{cta}"' in src, (
            f"DocumentDrawer missing CTA `{cta}` — E.3 spec requires 5 "
            "CTAs: Use in Solva / Use in Chat / Generate brief / Test "
            "hypothesis / Share document."
        )
    # All CTAs use the canonical `?ctx_type=document&ctx_id=...` URL.
    assert "ctx_type=document&ctx_id=" in src, (
        "DocumentDrawer CTAs must emit canonical `?ctx_type=document&"
        "ctx_id=<id>` URLs per the Phase D.3 contract."
    )
    # Brief + Hypothesis CTAs carry the submodule param so Solva
    # routes to the correct briefing-deck area (W2 contract).
    assert "submodule=develop_strategy" in src
    assert "submodule=simulate_hypothesis" in src


# ── T4. Legacy JournalDrawer archived (sentinel) ───────────────────
def test_legacy_journaldrawer_archived_to_quarantine():
    archived = FE / "_archived_coverage_loss" / "JournalDrawer.jsx"
    assert archived.exists(), (
        "Legacy JournalDrawer should be archived to "
        "_archived_coverage_loss/JournalDrawer.jsx for git-history "
        "continuity."
    )
    body = _read(archived)
    # The archived file should mark itself as quarantined.
    assert "ARCHIVED" in body or "Archived" in body or "archived" in body


# ── T5. Recent Drafts / Recent Activity cards also route via URL ───
def test_recent_drafts_card_routes_via_doc_id_url():
    """The F.2/F.6 FollowUpDraftsCard surfaces draft rows. Clicking
    one should navigate via the canonical `?doc_id=` URL contract
    (the universal drawer self-mounts on the target page) and must
    NOT render an inline preview on the card itself."""
    src = _read(FE / "components" / "tasks" / "FollowUpDraftsCard.jsx")
    # No inline drawer or modal body.
    assert "function JournalDrawer" not in src
    assert "QuickPreview" not in src
    # Card row click navigates to the canonical drawer URL.
    assert "doc_id=" in src, (
        "FollowUpDraftsCard rows must navigate via the canonical "
        "`?doc_id=<uuid>` URL contract so the universal DocumentDrawer "
        "self-mounts on the destination page."
    )


def test_recent_task_activity_card_routes_via_link():
    """The F.6 RecentTaskActivityCard must navigate via canonical
    URL params, not open an inline drawer."""
    src = _read(FE / "components" / "tasks" / "RecentTaskActivityCard.jsx")
    assert "function JournalDrawer" not in src
    assert "QuickPreview" not in src


# ── T6. Hostage check — known regression SECTION OVERLINES never reappear
@pytest.mark.parametrize("surface", DOC_LISTING_SURFACES, ids=lambda s: s[1])
def test_known_regression_strings_absent_from_doc_listing_surfaces(surface):
    """Tripwire — these literal JSX text strings come verbatim from
    the user's regression screenshot (TOPLINE / FROM AKKI / BODY
    EXCERPT section overlines + 5 wrong CTA button labels). If any
    of them reappear in render-visible JSX text on a doc-listing
    page, the legacy drawer is back.

    We match the JSX-text-content shape `>LABEL<` (between a `>` and
    `<`) so we don't false-positive on lowercase property names like
    `detail.topline?.doc_count`."""
    jsx, name = surface
    src = _read(jsx)
    # JSX text content shapes — labels rendered as visible text.
    for forbidden in (
        ">Topline<",
        ">From AKKI<",
        ">Body excerpt<",
        ">Open full reader<",
        ">Take into Solva<",
        ">Ask in Chat<",
        ">Add to Cycle<",
        ">Add to Work Studio<",
    ):
        assert forbidden not in src, (
            f"Regression tripwire: JSX text {forbidden!r} reappeared in "
            f"{name} ({jsx.relative_to(REPO)}). The legacy JournalDrawer "
            "has been reintroduced — restore the universal DocumentDrawer."
        )
    # Also forbid the legacy section overline strings with surrounding
    # whitespace shape `>\s*LABEL\s*<` to catch multi-line JSX.
    import re
    for label in ("Topline", "From AKKI", "Body excerpt"):
        pat = re.compile(r">\s*" + re.escape(label) + r"\s*<")
        assert not pat.search(src), (
            f"Regression tripwire: multi-line JSX text overline {label!r} "
            f"reappeared in {name} — legacy drawer body detected."
        )
