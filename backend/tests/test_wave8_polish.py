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
# Wave 8.2 — Task tile readiness 24px + compact stack
# ─────────────────────────────────────────────────────────────────

TASK_LISTING = FRONTEND / "components" / "tasks" / "TaskListing.jsx"


def test_w82_readiness_number_font_size_is_24px() -> None:
    """User correction: readiness number was originally specced at
    32px; live render was too heavy. Locked at 24px.
    """
    src = TASK_LISTING.read_text(encoding="utf-8")
    # Locate the readiness-number style declaration.
    match = re.search(
        r'className="readiness-number[^"]*"\s*style=\{\{\s*fontSize:\s*(\d+)\s*,',
        src,
    )
    assert match is not None, (
        "Could not find readiness-number fontSize literal in "
        "TaskListing.jsx. The W8.2 spec requires the style declaration "
        "to be inline so this regex can lock the value."
    )
    assert match.group(1) == "24", (
        f"Wave 8.2 amendment: readiness number must be 24px (was {match.group(1)}px). "
        "User overrode the original 32px spec after seeing it rendered."
    )


def test_w82_readiness_number_not_32px() -> None:
    """Negative guard — the legacy 32px value must NOT reappear anywhere
    in the readiness-number declaration.
    """
    src = TASK_LISTING.read_text(encoding="utf-8")
    bad = re.search(
        r'className="readiness-number[^"]*"\s*style=\{\{\s*fontSize:\s*32\s*,',
        src,
    )
    assert bad is None, (
        "Wave 8.2 readiness-number fontSize regressed to 32px. "
        "Locked at 24px per the user's amendment."
    )


def test_w82_readiness_stack_uses_leading_none() -> None:
    """Compactness lock — the readiness stack and its inner children
    must use `leading-none` so the right cluster doesn't elongate the
    row beyond the title's natural height.
    """
    src = TASK_LISTING.read_text(encoding="utf-8")
    # readiness-stack span carries leading-none
    stack = re.search(
        r'className="readiness-stack[^"]*\bleading-none\b',
        src,
    )
    assert stack is not None, (
        "readiness-stack span must carry `leading-none` for Wave 8.2 "
        "compactness — see PHASE_LEDGER amend row."
    )
    # readiness-label also carries leading-none
    label = re.search(
        r'className="readiness-label[^"]*\bleading-none\b',
        src,
    )
    assert label is not None, (
        "readiness-label span must carry `leading-none` for Wave 8.2 "
        "compactness."
    )


def test_w82_readiness_label_margin_top_is_at_most_1() -> None:
    """The label below the readiness number must sit immediately under
    it with at most 1px of marginTop — no extra vertical gap.
    """
    src = TASK_LISTING.read_text(encoding="utf-8")
    match = re.search(
        r'className="readiness-label[^"]*"\s*style=\{\{\s*fontSize:\s*\d+\s*,\s*marginTop:\s*(\d+)\s*\}\}',
        src,
    )
    assert match is not None, (
        "Could not find readiness-label marginTop literal in "
        "TaskListing.jsx — the inline style declaration must include "
        "both fontSize and marginTop so this guard can pin the value."
    )
    assert int(match.group(1)) <= 1, (
        f"Wave 8.2 amendment: readiness-label marginTop must be ≤1px "
        f"(was {match.group(1)}px). User flagged the elongation gap."
    )


def test_w82_task_card_outer_row_uses_items_start() -> None:
    """Per the W8.2 amendment: the outer flex row of the task card
    must use `items-start` so the right cluster's vertical height
    never stretches the left side (title) downward.
    """
    src = TASK_LISTING.read_text(encoding="utf-8")
    assert (
        'className="flex items-start justify-between gap-3 mb-1.5"' in src
    ), (
        "Task card outer row must be `flex items-start justify-between "
        "gap-3 mb-1.5` — locked by Wave 8.2 amendment."
    )


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
