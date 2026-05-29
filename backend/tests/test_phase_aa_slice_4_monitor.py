"""
Phase AA-slice-4 (2026-05-27) — Monitor surface rewrite.

Locks the dual capsule-tab shell + the new TasksInitiativesPanel
including the institutional provenance chip on LLM-extracted rows.

Source-strict assertions only (the runtime DOM behaviour is
covered by the multi-viewport Playwright probe in the dispatch +
will be wired into the AA-slice-7 orthogonality wire-test).
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"
MONITOR = FRONTEND / "pages" / "Monitor.jsx"
TASKS_PANEL = FRONTEND / "components" / "monitor" / "TasksInitiativesPanel.jsx"


# ─────────────────────────────────────────────────────────────────
# Capsule tabs at the top of Monitor
# ─────────────────────────────────────────────────────────────────


def test_aa4_capsule_tabs_present_with_count_badges() -> None:
    src = MONITOR.read_text(encoding="utf-8")
    assert 'data-testid="monitor-capsule-tabs"' in src
    assert 'data-testid="monitor-tab-goals"' in src
    assert 'data-testid="monitor-tab-tasks"' in src
    assert 'data-testid="monitor-tab-goals-count"' in src
    assert 'data-testid="monitor-tab-tasks-count"' in src


def test_aa4_default_tab_is_goals() -> None:
    """`useState(...)` initial value resolves to "goals" unless the
    URL carries `?tab=tasks`. Lock the literal."""
    src = MONITOR.read_text(encoding="utf-8")
    pattern = r't\s*===\s*"tasks"\s*\?\s*"tasks"\s*:\s*"goals"'
    assert re.search(pattern, src), (
        'Default tab logic must be `t === "tasks" ? "tasks" : "goals"` '
        'so the URL ?tab= param wins but anything else defaults to Goals.'
    )


def test_aa4_tab_bodies_carry_locked_testids() -> None:
    src = MONITOR.read_text(encoding="utf-8")
    assert 'data-testid="monitor-tab-content-goals"' in src
    assert 'data-testid="monitor-tab-content-tasks"' in src


def test_aa4_simple_list_view_removed() -> None:
    """The legacy `<ObjectivesProjectsPanel>` simple-list view that
    the user explicitly called out for removal must NOT mount in
    Monitor anymore. JSX mounts + ES imports are policed; passing
    mentions inside `{/* … */}` JSX comments or `// …` line
    comments are tolerated."""
    raw = MONITOR.read_text(encoding="utf-8")
    # Strip JSX block comments (`{/* … */}`) and JS block / line
    # comments before scanning so prose references inside comments
    # don't false-positive as JSX mounts.
    src = re.sub(r'\{/\*.*?\*/\}', '', raw, flags=re.DOTALL)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.DOTALL)
    src = re.sub(r'^\s*//.*$', '', src, flags=re.MULTILINE)
    jsx_mount = re.search(r'<ObjectivesProjectsPanel[\s/>]', src)
    assert jsx_mount is None, (
        "Monitor must no longer JSX-mount <ObjectivesProjectsPanel> "
        "— the simple-list view was retired in AA-slice-4."
    )
    es_import = re.search(
        r'^\s*import\s+ObjectivesProjectsPanel\b',
        src,
        re.MULTILINE,
    )
    assert es_import is None, (
        "Monitor must no longer `import ObjectivesProjectsPanel` — "
        "retire the import alongside the JSX mount."
    )


def test_aa4_url_param_sync_present() -> None:
    """`switchTab(next)` writes `?tab=` back to history.replaceState
    so the URL stays shareable."""
    src = MONITOR.read_text(encoding="utf-8")
    assert "sp.set(\"tab\", next);" in src
    assert "window.history.replaceState" in src


# ─────────────────────────────────────────────────────────────────
# TasksInitiativesPanel structural contract
# ─────────────────────────────────────────────────────────────────


def test_aa4_tasks_panel_root_testid_locked() -> None:
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert 'data-testid="tasks-initiatives-panel"' in src


def test_aa4_tasks_panel_emits_status_filter_tabs_with_counts() -> None:
    """Phase AA-slice-4 — Tasks panel renders the 6 status-filter
    buckets (all + 5 status keys) with a count badge per tab.

    UPDATED 2026-02 fork-resume (Monitor status-filter harmonization):
    the inline JSX was extracted into the shared `<StatusFilterTabs>`
    primitive at `/components/monitor/StatusFilterTabs.jsx`. The
    contract now asserts:
      • All 6 STATUS_FILTER_TABS keys remain declared in the panel.
      • The panel renders the primitive with `testIdPrefix=
        "tasks-status-tab"` (preserves the legacy testid namespace
        `tasks-status-tab-<key>` + `tasks-status-tab-<key>-count`).
      • The primitive itself renders the testids — verified separately
        in `test_monitor_status_filter_harmonization.py`.
    """
    src = TASKS_PANEL.read_text(encoding="utf-8")
    # The 6 status keys (+ "all" sentinel) live in STATUS_FILTER_TABS.
    for key in ("all", "on_track", "at_risk", "off_track", "achieved", "not_started"):
        assert f'key: "{key}"' in src, (
            f"Status filter tab `{key}` missing from "
            "STATUS_FILTER_TABS in TasksInitiativesPanel."
        )
    # Panel must consume the shared primitive.
    assert "<StatusFilterTabs" in src, (
        "TasksInitiativesPanel must render <StatusFilterTabs> "
        "(2026-02 fork-resume Monitor status-filter harmonization)."
    )
    # testIdPrefix must be the legacy `tasks-status-tab` so existing
    # downstream probes (`tasks-status-tab-${t.key}` and
    # `tasks-status-tab-${t.key}-count`) still resolve at runtime.
    assert 'testIdPrefix="tasks-status-tab"' in src, (
        "TasksInitiativesPanel must pass testIdPrefix=\"tasks-status-tab\" "
        "to preserve existing testid namespace."
    )


def test_aa4_tasks_panel_card_locks_all_required_fields() -> None:
    """Each TaskCard MUST render the 7 locked field testids:
    category, status, perf-bar, prob-bar, owner (when present),
    last-reassessed, provenance (LLM only)."""
    src = TASKS_PANEL.read_text(encoding="utf-8")
    required = (
        'task-card-category-${task.id}',
        'task-card-status-${task.id}',
        'task-card-perf-bar-${task.id}',
        'task-card-prob-bar-${task.id}',
        'task-card-owner-${task.id}',
        'task-card-last-reassessed-${task.id}',
        'task-card-provenance-${task.id}',
        'task-card-provenance-doc-link-${task.id}',
    )
    for r in required:
        assert r in src, f"Missing TaskCard testid: `{r}`."


def test_aa4_provenance_chip_only_renders_for_llm_rows() -> None:
    """Manual entries (`extracted_by !== "llm"`) MUST NOT render
    the provenance chip — institutional trust signal stays
    accurate."""
    src = TASKS_PANEL.read_text(encoding="utf-8")
    pattern = r'if\s*\(\s*task\.extracted_by\s*!==\s*"llm"\s*\)\s*return\s+null;'
    assert re.search(pattern, src), (
        "ProvenanceChip must `return null` when "
        "`task.extracted_by !== \"llm\"` so manual rows render "
        "without the LLM provenance chip."
    )


def test_aa4_provenance_chip_copy_locked() -> None:
    """Lock the exact chip copy fragments per the AA-slice-4 spec:
    "Extracted by Sonnet 4.5 from {doc_name} · {relative_date}"."""
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert "Extracted by Sonnet" in src
    assert "4.5 from" in src
    # The doc name is a click-through Link to the source doc drawer
    # at `/app/documents?doc_id=…`.
    assert "/app/documents?doc_id=${docId}" in src


def test_aa4_tasks_panel_empty_state_copy_locked() -> None:
    """User-visible empty-state copy is the spec — lock the redispatch
    version: "No tasks yet" + "Upload a document with extraction
    enabled to populate this view."."""
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert 'data-testid="tasks-empty-headline"' in src
    assert 'data-testid="tasks-empty-helper"' in src
    assert "No tasks yet" in src
    assert "Upload a document with extraction enabled to populate this view." in src
    # Disabled "+ Add" placeholder per AA-4 redispatch.
    assert 'data-testid="tasks-empty-add-btn"' in src
    assert "Coming in AA-slice-5" in src


def test_aa4_tasks_panel_listing_testid_present() -> None:
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert 'data-testid="tasks-listing"' in src


def test_aa4_tasks_panel_loads_via_aa1_endpoint() -> None:
    """The panel must call the AA-slice-1 `tasks-initiatives`
    endpoint — not the legacy `initiatives_count` field on goals.
    """
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert "/tasks-initiatives" in src


def test_aa4_tasks_panel_uses_aa1_status_enum_in_filters() -> None:
    """Tasks filter tabs use the AA-1 5-status enum (not_started,
    not the goals `abandoned`)."""
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert '{ key: "not_started"' in src
    # Negative — goals' "abandoned" is NOT a task status.
    assert 'key: "abandoned"' not in src


def test_aa4_tasks_panel_status_bar_class_helper_present() -> None:
    src = TASKS_PANEL.read_text(encoding="utf-8")
    assert "function statusBarClass(" in src
    assert "function probabilityBarClass(" in src


# ─────────────────────────────────────────────────────────────────
# Wiring back to Monitor
# ─────────────────────────────────────────────────────────────────


def test_aa4_monitor_imports_tasks_panel() -> None:
    src = MONITOR.read_text(encoding="utf-8")
    assert "TasksInitiativesPanel" in src
    assert "from \"@/components/monitor/TasksInitiativesPanel\"" in src


def test_aa4_monitor_passes_count_callbacks() -> None:
    src = MONITOR.read_text(encoding="utf-8")
    # Both panels receive `onCountChange` so the capsule-tab badges
    # update as panels load.
    assert "onCountChange={setGoalsCount}" in src
    assert "onCountChange={setTasksCount}" in src
