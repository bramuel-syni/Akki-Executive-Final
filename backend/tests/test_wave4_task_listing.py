"""Wave 4.1 (2026-05-27) — Task Manager listing restructure CI lockdown.

Locks the user-asked changes (W4.1 only — W4.2 system-wide grey→purple
sweep is HALTED-AND-AWAITING-USER-APPROVAL because the inventory
exceeded the 10-site threshold per the locked rule):
  • Readiness score moved to the top-right cluster, directly UNDER
    the state pill ("Active" marker).
  • Attention pill ("Needs your input") moved to TOP-RIGHT, positioned
    to the LEFT of the state pill (paired in a flex row).
  • Active rows take a brand-purple highlight on hover
    (border + tinted background, both reading `--ned-purple`).
"""
from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent.parent
LISTING = REPO / "frontend" / "src" / "components" / "tasks" / "TaskListing.jsx"


def _task_card_block(src):
    """Return the rendered task-card `<button>` block (one task row)."""
    m = re.search(
        r'data-testid=\{`task-card-\$\{t\.id\}`\}[\s\S]*?</button>',
        src,
    )
    assert m, "Task-card button block must exist"
    return m.group(0)


def test_W4_1a_readiness_lives_in_top_right_cluster():
    src = LISTING.read_text(encoding="utf-8")
    # The readiness inline-span MUST be inside the same parent div as
    # the state-pill row (top-right cluster). The clearest proxy: the
    # readiness testid appears BEFORE the objective paragraph (which
    # used to be above it in pre-W4.1 layout).
    readiness_pos = src.find("task-card-readiness-")
    objective_pos = src.find("t.objective &&")
    assert readiness_pos > 0 and objective_pos > 0
    assert readiness_pos < objective_pos, \
        "Readiness must render in source-order BEFORE the objective body " \
        "(top-right cluster, not bottom row)"


def test_W4_1b_attention_pill_is_in_state_pill_row():
    """The attention pill ('Needs your input') must render IMMEDIATELY
    BEFORE the StatusPill in the top-right cluster — left of the
    Active marker per the spec."""
    src = LISTING.read_text(encoding="utf-8")
    # Find the StatusPill render; the needs-your-input span must
    # appear before it in source order WITHIN the top-right cluster.
    needs_pos = src.find('task-card-needs-your-input-')
    pill_pos  = src.find('<StatusPill')
    assert needs_pos > 0 and pill_pos > 0
    assert needs_pos < pill_pos, \
        "Attention pill must render to the left of (source-order before) the StatusPill"


def test_W4_1c_active_row_uses_brand_purple_highlight():
    src = LISTING.read_text(encoding="utf-8")
    # Active rows pick up the brand-purple token for border + background
    # on hover. The colour cite reads through `--ned-purple` (Wave 1.5
    # locked the same token for the Monitor probability bar).
    assert "var(--ned-purple)" in src, \
        "Active task rows must use the brand-purple token (--ned-purple)"
    assert "isActiveRow" in src, \
        "Active row state must be computed via `isActiveRow` flag"


def test_W4_1d_card_root_carries_active_data_attribute():
    """For testing + CSS-target hooks: each card's root button MUST
    declare `data-active-highlight={...}` so source-strict CI and
    Playwright probes can lock the highlight state."""
    src = LISTING.read_text(encoding="utf-8")
    assert 'data-active-highlight=' in src, \
        "Task card root button must declare `data-active-highlight=...`"


def test_W4_1e_legacy_bottom_left_attention_pill_removed():
    """The pre-W4.1 implementation rendered the attention pill at the
    bottom-left (`ml-2` after the compile pill). Verify the new layout
    DOES NOT render the attention pill in a position that suggests
    bottom-left placement (no `ml-2` className on the needs-your-input
    span)."""
    src = LISTING.read_text(encoding="utf-8")
    m = re.search(
        r'data-testid=\{`task-card-needs-your-input-\$\{t\.id\}`\}[\s\S]{0,200}',
        src,
    )
    assert m, "needs-your-input testid must be present in the source"
    # The legacy `ml-2` indented the pill into the bottom-left row.
    # The new W4.1 placement uses `gap-1.5` in a flex cluster — no
    # `ml-2` on the badge itself.
    badge_block = m.group(0)
    assert " ml-2" not in badge_block, \
        "Legacy `ml-2` indent on the attention pill (bottom-left placement) must be removed"
