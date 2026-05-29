"""Phase Z2 Batch 2 (2026-02 fork-resume v2) — source-strict lockdown.

Locks the Z2.2 + Z2.3 changes:

  Z2.2 — Every right-aligned drawer in the app uses a scrollable body.
         For Sheet-based drawers (Radix dialog), the SheetContent
         carries `overflow-y-auto` OR contains a `flex-1 overflow-y-auto`
         body. For custom-div drawers, the inner content area MUST be
         scrollable.

  Z2.3 — The FeedbackWidget detects ANY open right-side drawer
         (role="dialog" not closed, anchored to the right edge of the
         viewport) and shifts the trigger pill + panel left by
         applying a `right: ${vw - drawerLeft + 8}px` inline style.
         When no drawer is open, the pill returns to its base
         `right-5` gutter position.

Inventory of right-side drawers swept this batch (10 surfaces):

  1. components/documents/DocumentDrawer.jsx       — `document-drawer`
  2. components/tasks/TaskDrawer.jsx                — `task-drawer`
  3. components/synisense/PreviewDrawer.jsx         — `syn-preview-drawer`
  4. components/monitor/ObjectivesProjectsPanel.jsx — `obj-drawer`
  5. components/monitor/StrategicGoalsPanel.jsx     — `goal-drawer`
  6. components/pulse/AcrossBoardsPanel.jsx         — `pulse-across-boards-drawer`
  7. components/solva/artefact_v2/SessionLogPanel.jsx — `solva-v2-session-log-panel`
  8. pages/Questions.jsx (QuestionDrawer)           — `question-drawer`
  9. pages/WorkStudio.jsx (BriefDrawer)             — `work-studio-brief-drawer`
 10. pages/admin/CohortConsole.jsx (drilldown)      — `cohort-console-drilldown`
"""
from __future__ import annotations
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"


# ─── Helpers ────────────────────────────────────────────────────────────

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _has_scrollable_body(src: str, testid: str) -> bool:
    """Heuristic: source containing the testid must also carry
    `overflow-y-auto` somewhere in its file (on the SheetContent or
    on a flex-1 child)."""
    if f'data-testid="{testid}"' not in src:
        return False
    return "overflow-y-auto" in src


# ─── Z2.2 — Drawer scroll across all 10 surfaces ───────────────────────


def test_z2_2_document_drawer_has_scrollable_body():
    src = _read(FRONTEND / "components" / "documents" / "DocumentDrawer.jsx")
    assert 'data-testid="document-drawer"' in src
    # Body uses `flex-1 overflow-y-auto` + `min-h-0` (load-bearing for
    # flexbox-min-content scroll behaviour, see file comment).
    assert "flex-1 overflow-y-auto" in src
    assert "min-h-0" in src


def test_z2_2_task_drawer_has_scrollable_body_with_min_h_0():
    src = _read(FRONTEND / "components" / "tasks" / "TaskDrawer.jsx")
    assert 'data-testid="task-drawer"' in src
    # Z2.2 added `min-h-0` to both the SheetContent flex column and the
    # body so scroll actually engages.
    assert "p-0 flex flex-col min-h-0" in src
    assert 'data-testid="task-drawer-body"' in src
    assert "flex-1 overflow-y-auto px-6 py-5 min-h-0" in src


def test_z2_2_preview_drawer_scrollable():
    src = _read(FRONTEND / "components" / "synisense" / "PreviewDrawer.jsx")
    assert _has_scrollable_body(src, "syn-preview-drawer")


def test_z2_2_obj_drawer_scrollable():
    src = _read(FRONTEND / "components" / "monitor" / "ObjectivesProjectsPanel.jsx")
    assert _has_scrollable_body(src, "obj-drawer")


def test_z2_2_goal_drawer_scrollable():
    src = _read(FRONTEND / "components" / "monitor" / "StrategicGoalsPanel.jsx")
    assert _has_scrollable_body(src, "goal-drawer")


def test_z2_2_pulse_across_boards_drawer_scrollable():
    src = _read(FRONTEND / "components" / "pulse" / "AcrossBoardsPanel.jsx")
    assert 'data-testid="pulse-across-boards-drawer"' in src
    # Z2.2 added `overflow-y-auto` to the SheetContent so the metadata
    # cards never silently exceed the viewport.
    assert 'className="w-full sm:max-w-[480px] bg-[var(--cream)] overflow-y-auto"' in src


def test_z2_2_solva_v2_session_log_panel_scrollable():
    src = _read(FRONTEND / "components" / "solva" / "artefact_v2" / "SessionLogPanel.jsx")
    assert 'data-testid="solva-v2-session-log-panel"' in src
    # `<aside ... flex flex-col>` with `flex-1 overflow-y-auto` body.
    assert "flex-1 overflow-y-auto" in src


def test_z2_2_question_drawer_scrollable():
    src = _read(FRONTEND / "pages" / "Questions.jsx")
    assert _has_scrollable_body(src, "question-drawer")


def test_z2_2_work_studio_brief_drawer_scrollable():
    src = _read(FRONTEND / "pages" / "WorkStudio.jsx")
    assert _has_scrollable_body(src, "work-studio-brief-drawer")


def test_z2_2_cohort_console_drilldown_scrollable():
    src = _read(FRONTEND / "pages" / "admin" / "CohortConsole.jsx")
    assert _has_scrollable_body(src, "cohort-console-drilldown")


# ─── Z2.3 — Feedback pill offset ───────────────────────────────────────


def test_z2_3_feedback_widget_uses_dynamic_drawer_detection():
    """The MutationObserver in FeedbackWidget must query a BROAD
    selector that picks up Radix Sheet (data-state="open"),
    SessionLogPanel (<aside role="dialog">), and custom-div drilldown
    drawers — NOT just the legacy `aside[role="dialog"][data-state="open"]`
    pattern which never matched Radix Sheet's `<div>` content."""
    src = _read(FRONTEND / "components" / "feedback" / "FeedbackWidget.jsx")
    # Locked selector pattern
    assert '[role="dialog"]:not([data-state="closed"])' in src
    # Z2.3 has migrated from boolean drawerOpen → numeric drawerLeft
    assert "drawerLeft" in src
    assert "setDrawerLeft" in src
    # The pill exclude its own panel from detection
    assert '"feedback-widget-panel"' in src


def test_z2_3_feedback_widget_shifts_via_inline_right_style():
    src = _read(FRONTEND / "components" / "feedback" / "FeedbackWidget.jsx")
    # The shift uses inline `style={{ right: ... }}` rather than a
    # className toggle, so the offset adapts to actual drawer width.
    assert "rightOffsetStyle" in src
    assert "right: `${Math.max(20, window.innerWidth - drawerLeft + 8)}px`" in src
    # Both trigger and panel carry the shifted style.
    assert "data-drawer-shifted" in src
    assert src.count('data-drawer-shifted') >= 2


def test_z2_3_feedback_widget_resize_listener_attached():
    """Window resize must re-fire detect() so the pill keeps the
    correct offset across viewport changes."""
    src = _read(FRONTEND / "components" / "feedback" / "FeedbackWidget.jsx")
    assert 'window.addEventListener("resize", detect)' in src
    assert 'window.removeEventListener("resize", detect)' in src
