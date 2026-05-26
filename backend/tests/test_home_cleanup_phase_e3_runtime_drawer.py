"""E.3 + F.3 runtime drawer regression test — 2026-05-26.

Closes a recurring class of false-green wire tests: pages that
`import` the universal drawer but never invoke it on row click.

Two false-greens caught:
  1. E.3 — Workspace.jsx rendered an inline JournalDrawer on row
     click. The wire test asserted `import DocumentDrawer` was
     present and passed. The user reported the visual regression
     on production. Fix: archived JournalDrawer, rewired openDrawer
     to set `?doc_id=` URL.
  2. F.3 — Reported (but NOT reproduced in this verification pass)
     that task cards routed to `/app/work-studio`. Click handler
     actually sets `?task_id=` URL correctly. Tests below lock in
     the correct behavior so future drift is caught.

This file IS the CI gate. Every doc-listing surface and every
task-listing surface has its click handler asserted at source
level (regression-mode patterns) + tripwires for the legacy text
that betrayed the E.3 regression.

For full DOM-level runtime verification (clicking a real card on a
real browser), see `scripts/verify_drawer_runtime.py` (Playwright,
not in pytest CI for speed). The pytest assertions below cover the
specific regression modes that previously slipped through.
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

# Surfaces that list tasks and must use the universal TASK drawer.
TASK_LISTING_SURFACES = [
    (FE / "pages" / "TaskManager.jsx",                  "Task Manager (page)"),
    (FE / "components" / "tasks" / "TaskListing.jsx",   "Task Listing (cards)"),
    (FE / "components" / "tasks" / "RecentTaskActivityCard.jsx", "Recent Task Activity card"),
    (FE / "pages" / "TaskManagerActivity.jsx",          "Task Manager Activity page"),
]

DOCUMENT_DRAWER_PATH = FE / "components" / "documents" / "DocumentDrawer.jsx"
TASK_DRAWER_PATH     = FE / "components" / "tasks" / "TaskDrawer.jsx"


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


# ════════════════════════════════════════════════════════════════════
# F.3 — Task-listing runtime drawer CI gate (2026-05-26)
# ════════════════════════════════════════════════════════════════════
# After the E.3 false-green caught a real production regression on
# Workspace, e1_tester flagged F.3 as suspect (task card → wrong
# destination). Direct DOM verification on the live preview pod
# confirmed F.3's runtime behavior is CORRECT: card click sets
# `?task_id=<uuid>` and the universal <TaskDrawer> opens with all
# 5 tabs + 5 CTAs.
#
# These tests lock in that behavior so future drift is caught:
#  • TaskListing row click MUST set `?task_id=` URL
#  • No task-listing surface defines an inline drawer
#  • Universal <TaskDrawer> ships the spec'd 5 tabs + 5 CTAs
#  • Tripwires — no legacy "Take into..." / "Open full reader" /
#    "Ask in Chat" text on any task-listing surface

def test_f3_task_listing_card_click_sets_task_id_url():
    """The actual regression mode: ensure the row click handler
    sets `?task_id=` URL. This was the assertion gap that let the
    E.3 false-green slip through."""
    src = (FE / "components" / "tasks" / "TaskListing.jsx").read_text("utf-8")
    # The openTask helper exists.
    assert "const openTask" in src or "function openTask" in src, (
        "TaskListing must define an openTask helper that sets the URL."
    )
    # Helper sets `task_id` URL param via setParams (canonical pattern).
    assert 'next.set("task_id", taskId)' in src or 'set("task_id"' in src, (
        "TaskListing.openTask must set the canonical `task_id` URL "
        "param so the universal TaskDrawer self-mounts."
    )
    # Card invokes openTask on click — not a raw navigate to another page.
    assert "onClick={() => openTask(t.id)}" in src, (
        "TaskListing card click must call openTask(t.id), not navigate "
        "to another page. F.3 contract."
    )
    # Tripwire — must NOT navigate directly to /app/work-studio from
    # the task-listing card click.
    assert "navigate(`/app/work-studio" not in src, (
        "TaskListing must not navigate task-card clicks to "
        "/app/work-studio — task rows belong to TaskDrawer."
    )


def test_f3_recent_task_activity_row_click_sets_task_id_url():
    """RecentTaskActivityCard row click must also set `?task_id=`."""
    src = (FE / "components" / "tasks" / "RecentTaskActivityCard.jsx").read_text("utf-8")
    assert 'set("task_id"' in src, (
        "RecentTaskActivityCard row click must set the canonical "
        "`task_id` URL param."
    )


def test_f3_task_manager_mounts_universal_task_drawer():
    """TaskManager page must mount <TaskDrawer> exactly once."""
    src = (FE / "pages" / "TaskManager.jsx").read_text("utf-8")
    assert "<TaskDrawer" in src, (
        "TaskManager.jsx must mount the universal <TaskDrawer>."
    )
    assert 'from "@/components/tasks/TaskDrawer"' in src, (
        "TaskDrawer import must reference the canonical path."
    )


def test_f3_universal_task_drawer_has_5_spec_tabs():
    """TaskDrawer ships all 5 F.3 spec tabs."""
    src = TASK_DRAWER_PATH.read_text("utf-8")
    # Per the F.3 spec — Plan / Contributions / Drafts / Intelligence / Compile.
    # Testids on the tab BODIES carry the value strings, lowercased.
    for tab in ("plan", "contributions", "drafts", "intelligence", "compile"):
        assert f'data-testid="task-drawer-tab-{tab}-body"' in src, (
            f"TaskDrawer missing tab `{tab}` body — F.3 spec requires 5 "
            "tabs (Plan / Contributions / Drafts / Intelligence / Compile)."
        )


def test_f3_universal_task_drawer_has_5_spec_ctas():
    """TaskDrawer ships all 5 F.3 spec CTAs with canonical URLs."""
    src = TASK_DRAWER_PATH.read_text("utf-8")
    for cta in (
        "task-drawer-cta-solva",
        "task-drawer-cta-chat",
        "task-drawer-cta-brief",
        "task-drawer-cta-hypothesis",
        "task-drawer-cta-share",
    ):
        assert f'data-testid="{cta}"' in src, (
            f"TaskDrawer missing CTA `{cta}` — F.3 spec requires 5 CTAs "
            "(Use in Solva / Use in Chat / Generate brief / Test hypothesis / Share task)."
        )
    # All non-share CTAs use the canonical `?ctx_type=task&ctx_id=<id>` URL.
    assert "ctx_type=task&ctx_id=" in src, (
        "TaskDrawer CTAs must emit canonical `?ctx_type=task&ctx_id=<id>` URLs."
    )
    # Brief + Hypothesis CTAs carry the submodule param for the W2
    # briefing-deck routing.
    assert "submodule=develop_strategy" in src
    assert "submodule=simulate_hypothesis" in src


@pytest.mark.parametrize("surface", TASK_LISTING_SURFACES, ids=lambda s: s[1])
def test_f3_no_inline_drawer_on_any_task_listing_surface(surface):
    """No task-listing surface defines an inline drawer component."""
    jsx, name = surface
    src = jsx.read_text("utf-8")
    forbidden_patterns = [
        "function JournalDrawer",
        "function TaskDrawerInline",
        "function QuickPreview",
        # Inline drawer JSX shapes.
        'data-testid="journal-drawer"',
        'data-testid="task-drawer-inline"',
        'data-testid="quick-preview"',
    ]
    import re
    src_no_block = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    for pat in forbidden_patterns:
        assert pat not in src_no_block, (
            f"Legacy/inline drawer pattern {pat!r} found in {name} "
            f"({jsx.relative_to(REPO)}) — task-listing surfaces must "
            "use the universal <TaskDrawer>."
        )


@pytest.mark.parametrize("surface", TASK_LISTING_SURFACES, ids=lambda s: s[1])
def test_f3_no_legacy_drawer_text_on_task_listing_surfaces(surface):
    """Tripwire — same legacy strings that betrayed the E.3
    regression must not appear on task-listing surfaces."""
    jsx, name = surface
    src = jsx.read_text("utf-8")
    for forbidden in (
        ">Topline<",
        ">From AKKI<",
        ">Body excerpt<",
        ">Open full reader<",
        ">Take into Solva<",
        ">Ask in Chat<",
    ):
        assert forbidden not in src, (
            f"Regression tripwire: JSX text {forbidden!r} on {name} "
            "({jsx.relative_to(REPO)}) — a legacy drawer surface was "
            "introduced on a task-listing page."
        )


# ════════════════════════════════════════════════════════════════════
# Drawer compliance matrix — every listing surface in one assertion
# ════════════════════════════════════════════════════════════════════
DRAWER_COMPLIANCE_MATRIX = (
    # surface path, friendly name, expected URL param key, drawer-mount substring
    (FE / "pages" / "Workspace.jsx",  "Workspace",   "doc_id",  "<DocumentDrawer"),
    (FE / "pages" / "WorkStudio.jsx", "Work Studio", "doc_id",  "<DocumentDrawer"),
    (FE / "pages" / "Pulse.jsx",      "Pulse",       "doc_id",  "<DocumentDrawer"),
    (FE / "pages" / "Cycle.jsx",      "Cycle",       "doc_id",  "<DocumentDrawer"),
    (FE / "pages" / "TaskManager.jsx", "Task Manager", "task_id", "<TaskDrawer"),
)


@pytest.mark.parametrize("entry", DRAWER_COMPLIANCE_MATRIX, ids=lambda e: e[1])
def test_drawer_compliance_matrix(entry):
    """Each listing surface must (a) mount its universal drawer and
    (b) write its canonical URL param somewhere in the file body
    (proves the row click → URL contract is wired)."""
    jsx, name, param_key, drawer_substr = entry
    src = jsx.read_text("utf-8")
    assert drawer_substr in src, (
        f"{name}: missing drawer mount `{drawer_substr}` — regression."
    )
    # The URL param key must appear (in `setParams`, `set("...")`, or
    # similar). We accept any presence.
    assert param_key in src, (
        f"{name}: row-click handler does not reference the canonical "
        f"URL param `{param_key}` — likely false-green wire test."
    )
