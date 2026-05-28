"""Wave 4.1 (2026-05-27) + Phase Y (2026-02 fork-resume) — Task Manager
listing CI lockdown.

Locks the W4.1 placement intent against Phase Y's primitive composition:
  • Readiness must surface in the right-anchored ScoreBar slot of the
    `<StrategicRow>` primitive, NOT below the title.
  • Attention pill ("Needs your input") sits in the statusChip slot
    LEFT of the StatusPill (so it source-orders first in the chip row).
  • Active rows carry brand-purple (`--ned-purple`) border on the
    wrapping `<li>`, plus `data-active-highlight` attribute.
  • The card root `<li>` carries `data-card-kind="task"` for runtime
    selector compatibility (`test_task_drawer_tab_prefix_guard`).
"""
from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent.parent
LISTING = REPO / "frontend" / "src" / "components" / "tasks" / "TaskListing.jsx"


def test_W4_1a_readiness_renders_in_right_side_score_slot():
    """Phase Y composition — readiness flows into the StrategicRow
    primitive's `rightSideScores` slot, which renders BEFORE the
    description (objective) slot in source order. The primitive's
    contract: top row carries chips + scores; metadata + description
    follow underneath. Reading source-order top-to-bottom, the
    readiness testid must precede the objective `description={...}`
    binding."""
    src = LISTING.read_text(encoding="utf-8")
    readiness_pos = src.find('`task-card-readiness-${t.id}`')
    description_pos = src.find("description={t.objective}")
    assert readiness_pos > 0, (
        "Readiness testid `task-card-readiness-${t.id}` must surface "
        "in TaskListing.jsx via the StrategicRow `rightSideScores` slot."
    )
    assert description_pos > 0, (
        "Objective must bind to the StrategicRow `description` slot."
    )
    assert readiness_pos < description_pos, (
        "Readiness must render in source-order BEFORE the description "
        "slot binding — the primitive lays out the right-anchored "
        "scores on the top row, description on the bottom."
    )


def test_W4_1b_attention_pill_source_orders_before_status_pill():
    """The needs-your-input pill must source-order BEFORE the
    `<StatusPill>` render inside the statusChip fragment. This locks
    the visual "left of the Active marker" placement the user asked
    for in Wave 4.1."""
    src = LISTING.read_text(encoding="utf-8")
    needs_pos = src.find('task-card-needs-your-input-')
    pill_pos  = src.find('<StatusPill state={t.state}')
    assert needs_pos > 0, "needs-your-input testid must exist"
    assert pill_pos > 0, "<StatusPill state={t.state}/> must render"
    assert needs_pos < pill_pos, (
        "Needs-your-input pill must source-order before <StatusPill> "
        "so it renders LEFT of the Active marker in the statusChip slot."
    )


def test_W4_1c_active_row_uses_brand_purple_highlight():
    src = LISTING.read_text(encoding="utf-8")
    assert "var(--ned-purple)" in src, (
        "Active task rows must use the brand-purple token (--ned-purple) "
        "on the wrapping <li> border."
    )
    assert "isActiveRow" in src, (
        "Active row state must be computed via `isActiveRow` flag."
    )


def test_W4_1d_card_root_carries_active_data_attribute():
    """For testing + CSS-target hooks: each card's wrapping <li> must
    declare `data-active-highlight={...}` so source-strict CI and
    Playwright probes can lock the highlight state."""
    src = LISTING.read_text(encoding="utf-8")
    assert 'data-active-highlight=' in src, (
        "Task card wrapper must declare `data-active-highlight=...`"
    )


def test_W4_1e_card_root_carries_data_card_kind_task():
    """Phase F.3 selector lock — the wrapping <li> must carry
    `data-card-kind="task"` so existing Playwright probes
    (e.g. test_task_drawer_tab_prefix_guard) still resolve the card."""
    src = LISTING.read_text(encoding="utf-8")
    assert 'data-card-kind="task"' in src, (
        "Task card wrapper must carry `data-card-kind=\"task\"` for "
        "runtime selector compatibility."
    )


def test_W4_1f_legacy_24px_readiness_stack_removed():
    """Phase Y supersedes Wave 8.2 — the 24px readiness number stack
    (`readiness-number` / `readiness-stack` / `readiness-label` class
    triple, with inline 24px fontSize) is gone, replaced by the
    StrategicRow ScoreBar."""
    src = LISTING.read_text(encoding="utf-8")
    for legacy_class in ("readiness-number", "readiness-stack", "readiness-label"):
        assert legacy_class not in src, (
            f"Legacy Wave 8.2 class {legacy_class!r} must be removed. "
            f"Phase Y replaces the 24px readiness stack with the shared "
            f"<StrategicRow> ScoreBar."
        )
    # The inline `fontSize: 24` declaration must be gone too.
    assert not re.search(r"fontSize:\s*24\b", src), (
        "Inline `fontSize: 24` on readiness number must be removed; "
        "Phase Y ScoreBar handles sizing via Tailwind classes."
    )
