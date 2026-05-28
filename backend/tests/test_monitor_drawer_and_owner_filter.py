"""Item 4 + Item 5 (2026-02 fork-resume consolidated dispatch).

- Item 4: Monitor goal drawer intelligence wiring. Closed-row narrative
  snippets are bucket-template strings generated client-side by
  `performanceNarrative()` / `probabilityNarrative()`. The drawer
  was rendering only the score numbers without the bucket text. Fix
  surfaces the same templates inside the drawer (full text, not
  truncated), plus an empty milestone tracker + a recommended-action
  callout when the performance score < 65.

- Item 5: Monitor strategic-goals "CATEGORY" filter renamed to
  "OWNER" + "All categories" → "All owners". The values shown were
  always department-roles (CFO/CEO/...); the label was misleading.

Backend follow-up for Item 4 (filed in PHASE_LEDGER): Phase
AA.followup.10 — LLM-generated `performance_explanation`,
`probability_explanation`, `recommended_action`, `milestones[]`
on the goal model.
"""
from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


# ─────────────────────────────────────────────────────────────────
# Item 4 — drawer intel testids + bucket-narrative wiring
# ─────────────────────────────────────────────────────────────────


def test_item4_drawer_intelligence_panel_present():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    required = (
        "goal-drawer-intelligence",
        "goal-drawer-performance-signal",
        "goal-drawer-performance-signal-text",
        "goal-drawer-probability-signal",
        "goal-drawer-probability-signal-text",
        # AA.followup.10 REVISED — Progress timeline replaces the old
        # manual milestones tracker.
        "goal-drawer-progress-timeline",
        "goal-drawer-progress-timeline-empty",
        "goal-drawer-recommended-action",
    )
    for tid in required:
        assert f'data-testid="{tid}"' in src, (
            f"StrategicGoalsPanel.jsx must carry data-testid={tid!r}"
        )


def test_item4_drawer_uses_client_side_narratives_when_backend_field_absent():
    """Drawer must fall back to `performanceNarrative()` /
    `probabilityNarrative()` (the bucket templates) when the goal lacks
    backend-supplied LLM explanations."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # Both narrative functions must be referenced inside the drawer block.
    drawer_idx = src.find("goal-drawer-intelligence")
    assert drawer_idx > 0
    drawer_block = src[drawer_idx:drawer_idx + 3000]
    assert "performanceNarrative(goal?.current_score)" in drawer_block, (
        "Drawer must call performanceNarrative(goal?.current_score) so "
        "the bucket text matches the closed row."
    )
    assert "probabilityNarrative(goal?.probability)" in drawer_block, (
        "Drawer must call probabilityNarrative(goal?.probability)."
    )
    # The backend-explanation field must be checked first (LLM intel
    # supersedes the client bucket when available — see Phase
    # AA.followup.10 backlog).
    assert "performance_explanation" in drawer_block
    assert "probability_explanation" in drawer_block


def test_item4_progress_timeline_replaces_manual_milestones():
    """AA.followup.10 REVISED — the manual `+ Add milestone` direction
    was wrong. Drawer renders auto-derived Progress timeline instead."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # Old milestone testids must be gone.
    for legacy in ("goal-drawer-milestones-empty", "goal-drawer-add-milestone-btn", "goal-drawer-milestones\""):
        assert legacy.rstrip('"') not in src or f'"{legacy.rstrip(chr(34))}"' not in src or src.count(f'data-testid="{legacy.rstrip(chr(34))}"') == 0, (
            f"Legacy milestone testid {legacy!r} must be removed; "
            f"replaced by Progress timeline."
        )
    # Empty-state copy per spec.
    assert "No progress signals recorded yet." in src, (
        "Progress timeline empty-state copy must match spec exactly"
    )
    assert "+ Add milestone" not in src, (
        "Manual `+ Add milestone` CTA must be REMOVED from the drawer "
        "(AA.followup.10 REVISED course-correction)"
    )


def test_item4_recommended_action_uses_brand_purple_callout():
    """The "Recommended action" callout must use the brand-purple
    Tailwind-config-registered color (ned-purple/N), not the silent-
    fail `[var(--ned-purple)]/N` form."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    idx = src.find("goal-drawer-recommended-action")
    block = src[idx:idx + 800]
    # Must use Tailwind-config-registered colors so opacity composites.
    assert "bg-ned-purple/10" in block or "bg-ned-purple/8" in block, (
        "Recommended-action callout must use `bg-ned-purple/N` "
        "(Tailwind-config short name) so opacity composites correctly. "
        "`bg-[var(--ned-purple)]/N` silently fails."
    )


# ─────────────────────────────────────────────────────────────────
# Item 5 — Owner filter rename
# ─────────────────────────────────────────────────────────────────


def test_item5_filter_label_is_owner_not_category():
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    # New testid.
    assert "strategic-goals-owner-select" in src, (
        "Owner filter testid must be `strategic-goals-owner-select`."
    )
    # Label text.
    label_idx = src.find("strategic-goals-owner-select")
    label_block = src[max(0, label_idx - 600):label_idx]
    assert ">Owner</label>" in label_block or "Owner\n" in label_block or '"Owner"' in label_block, (
        "Filter label text must read 'Owner' (uppercase via tracking-wider)."
    )
    # Default option.
    assert "All owners" in src, (
        'Default option text must read "All owners".'
    )


def test_item5_legacy_category_testids_removed():
    """The old `strategic-goals-category-*` testids must be gone (no
    leftover references to the misleading label)."""
    src = (REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx").read_text(encoding="utf-8")
    assert "strategic-goals-category-select" not in src, (
        "Legacy `strategic-goals-category-select` testid must be removed."
    )
    assert "All categories" not in src, (
        'Legacy "All categories" default option text must be removed.'
    )
