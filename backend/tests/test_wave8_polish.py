"""
Wave 8 — Polish fixes CI guards (2026-05-27).

Three locks:
  W8.1 — Work Studio compile CTAs sit ABOVE the document listing/
         search bar (verified by source order via a regex pair).
  W8.2 — Task tile readiness number is locked at 24px (NOT 32px) and
         the stack uses `leading-none` + `marginTop: 1` so the right
         cluster doesn't elongate the row beyond the title's natural
         height.
  W8.3 — Every top-level page surface carries
         `data-testid="page-subtext"` in source. The page list is
         a frozen tuple at module top — adding a new top-level
         surface without registering it AND adding the testid will
         fail this guard.

These are source-strict assertions on the JSX file content. Runtime
DOM-level verification is delivered via the multi-viewport Playwright
screenshots captured during dispatch (see PHASE_LEDGER Wave 8 row).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"


# ─────────────────────────────────────────────────────────────────
# Wave 8.3 — H1 subtext audit (Recurrence #5)
# ─────────────────────────────────────────────────────────────────

# Frozen list of files that carry a top-level page H1. Adding a new
# top-level surface to the app means adding its file here AND adding a
# `data-testid="page-subtext"` element below its <h1>. This guard
# enforces both halves of that contract.
PAGE_SUBTEXT_FILES = (
    # AppHome dispatches to one of three pages; all three carry their own H1.
    "pages/home/HomeUndeclared.jsx",
    "pages/ContextPortfolio.jsx",
    "pages/CompanyHome.jsx",
    # Chat — empty-state H1 ("Your private AI workspace.").
    "pages/Chat.jsx",
    # Solva — H1 lives in the picker component mounted under SolvaApp.
    "components/solva/SolvaLanding.jsx",
    "pages/WorkStudio.jsx",
    "pages/TaskManager.jsx",
    "pages/Monitor.jsx",
    "pages/Pulse.jsx",
    "pages/Learn.jsx",
    "pages/DocumentsPage.jsx",
    "pages/admin/CohortConsole.jsx",
    "pages/admin/CohortCopyEditor.jsx",
    "pages/admin/AdminUsers.jsx",
    "pages/EarlyAccessOptIn.jsx",
)


@pytest.mark.parametrize("rel_path", PAGE_SUBTEXT_FILES)
def test_w83_top_level_surface_carries_page_subtext_testid(rel_path: str) -> None:
    """Every top-level surface MUST carry a `data-testid="page-subtext"`
    element in source. Recurrence #5 — the H1 subtext audit lesson
    locked institutionally.
    """
    src = (FRONTEND / rel_path).read_text(encoding="utf-8")
    assert 'data-testid="page-subtext"' in src, (
        f"Top-level page {rel_path!r} is missing "
        f'`data-testid="page-subtext"`. Wave 8.3 requires every '
        f"top-level surface to render a sober executive subtext line "
        f"under its <h1>. See PHASE_LEDGER Recurrence #5."
    )


def test_w83_page_subtext_files_all_exist_on_disk() -> None:
    """The frozen page list MUST point at files that actually exist —
    otherwise a future rename could quietly bypass the guard.
    """
    for rel_path in PAGE_SUBTEXT_FILES:
        full = FRONTEND / rel_path
        assert full.is_file(), (
            f"Wave 8.3 page-subtext lockfile {rel_path!r} not found at "
            f"{full!s}. If the file was renamed, update "
            f"PAGE_SUBTEXT_FILES in this test."
        )


def test_w83_page_subtext_count_locked_at_15() -> None:
    """We currently lock 15 surfaces (AppHome dispatches to 3 of them).
    If you add a new top-level surface, this assertion will fail and
    you'll be forced to register it in PAGE_SUBTEXT_FILES AND add the
    `page-subtext` testid to its source.
    """
    assert len(PAGE_SUBTEXT_FILES) == 15


# ─────────────────────────────────────────────────────────────────
# Wave 8.2 — Task tile readiness layout
# ─────────────────────────────────────────────────────────────────
#
# SUPERSEDED by Phase Y (2026-02 fork-resume). The Wave 8.2 24px
# readiness number stack has been replaced by the shared
# `<StrategicRow>` primitive's ScoreBar (label + bar + value +
# narrative). Phase Y locks Task card layout against Monitor goal row
# layout pixel-for-pixel via the same primitive.
#
# Replacement CI guards live in:
#   - tests/test_wave4_task_listing.py        (W4_1f — legacy classes gone)
#   - tests/test_strategic_row_primitive.py   (primitive shape)
#   - tests/test_task_card_uses_primitive.py  (Task card composition)


# ─────────────────────────────────────────────────────────────────
# Wave 8.1 — Work Studio compile CTAs above the listing
# ─────────────────────────────────────────────────────────────────

WORK_STUDIO = FRONTEND / "pages" / "WorkStudio.jsx"


def test_w81_compile_buttons_render_above_doc_listing() -> None:
    """The Compile / Enhance / Create CTAs must mount in the
    `preBody` slot of <ListingShell> (which renders ABOVE the body).
    Wave 8.1 relocated the buttons there from a sibling render below
    the listing — the legacy mount has been removed.
    """
    src = WORK_STUDIO.read_text(encoding="utf-8")
    # The ListingShell's preBody slot carries <ContextActions>.
    pre_body = re.search(
        r'preBody=\{\s*<div\s+data-testid="ws-tab-compile-actions">\s*<ContextActions',
        src,
    )
    assert pre_body is not None, (
        "Wave 8.1: <ContextActions> must mount inside ListingShell's "
        "`preBody=` slot (which renders ABOVE the listing body). "
        "Source pattern not found — the buttons either drifted out of "
        "preBody or the wrapper testid `ws-tab-compile-actions` was "
        "renamed."
    )
    # And there must NOT be a second sibling <ContextActions /> mount
    # in WorkStudio.jsx (legacy below-listing render removed).
    context_actions_mounts = re.findall(r'<ContextActions\b', src)
    assert len(context_actions_mounts) == 1, (
        f"Wave 8.1: exactly one <ContextActions> mount expected in "
        f"WorkStudio.jsx (the preBody one); found {len(context_actions_mounts)}. "
        f"A duplicate mount duplicates the Compile CTAs in the UI."
    )
