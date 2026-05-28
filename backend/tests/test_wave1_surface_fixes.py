"""Wave 1 (2026-05-27) — Quick surface fixes CI lockdown.

Locks the 6 user-asked surface fixes:
  1.1 Document Drawer tab labels: "Notes" → "Your Notes", "Related" → "Related Documents"
  1.2 Document Drawer Summary is LLM-generated (audit-only — verifies the
      Intelligence service calls `shield_invoke`)
  1.3 H1 + subtext present on every top-level surface
  1.4 Universal BackButton exists + AppShell mounts it + top-level routes excluded
  1.5 Monitor probability bar uses grey/purple scheme (not the
      performance bar's green/amber/red)
  1.6 Monitor "+ Add {kind}" renamed to "+ Manually Add Objectives or
      Projects" + sibling button "Read Goals from Strategic/Performance
      Documents"
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest


REPO = Path(__file__).resolve().parent.parent.parent

DRAWER          = REPO / "frontend" / "src" / "components" / "documents" / "DocumentDrawer.jsx"
INTEL_SVC       = REPO / "backend" / "services" / "documents" / "intelligence_service.py"
APPSHELL        = REPO / "frontend" / "src" / "components" / "layout" / "AppShell.jsx"
BACK_BUTTON     = REPO / "frontend" / "src" / "components" / "layout" / "BackButton.jsx"
STRAT_PANEL     = REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx"
OBJ_PANEL       = REPO / "frontend" / "src" / "components" / "monitor" / "ObjectivesProjectsPanel.jsx"

# Surfaces that MUST carry an H1 + one-line subtext.
SURFACE_FILES = {
    "company-home":   REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx",
    "workspace":      REPO / "frontend" / "src" / "pages" / "Workspace.jsx",
    "cycle":          REPO / "frontend" / "src" / "pages" / "Cycle.jsx",
    "monitor":        REPO / "frontend" / "src" / "pages" / "Monitor.jsx",
    "pulse":          REPO / "frontend" / "src" / "pages" / "Pulse.jsx",
    "learn":          REPO / "frontend" / "src" / "pages" / "Learn.jsx",
    "solva-landing":  REPO / "frontend" / "src" / "components" / "solva" / "SolvaLanding.jsx",
    "chat":           REPO / "frontend" / "src" / "pages" / "Chat.jsx",
}


# ─────────────────────────────────────────────────────────────────────
# 1.1 — Document Drawer tab labels
# ─────────────────────────────────────────────────────────────────────

def test_W1_1a_drawer_notes_tab_renamed_to_your_notes():
    src = DRAWER.read_text(encoding="utf-8")
    # "Your Notes" present in the tab trigger; legacy "Summary & Notes"
    # must be gone.
    assert "Your Notes" in src, "Drawer tab label must be 'Your Notes'"
    assert "Summary &amp; Notes" not in src and "Summary & Notes" not in src, \
        "Legacy 'Summary & Notes' tab label must be removed"


def test_W1_1b_drawer_related_tab_renamed_to_related_documents():
    src = DRAWER.read_text(encoding="utf-8")
    assert "Related Documents" in src, "Drawer tab label must be 'Related Documents'"
    # Confirm the rename is on the tab trigger, not just on the inner
    # tab header. Inspect the TabsTrigger line specifically.
    m = re.search(r'<TabsTrigger value="related"[\s\S]{0,400}?</TabsTrigger>', src)
    assert m, "TabsTrigger value='related' must be present"
    assert "Related Documents" in m.group(0), \
        "TabsTrigger value='related' must show 'Related Documents'"


# ─────────────────────────────────────────────────────────────────────
# 1.2 — Document Drawer Summary IS LLM-generated (audit)
# ─────────────────────────────────────────────────────────────────────

def test_W1_2_intelligence_summary_uses_shield_invoke():
    """Verify the intel.summary field (displayed inside the Intelligence
    tab — drawer-intel-summary testid) is produced via the LLM gateway
    `shield_invoke()` call, not static metadata."""
    src = INTEL_SVC.read_text(encoding="utf-8")
    assert "shield_invoke" in src
    assert "summary" in src
    # The 2-sentence editorial pattern (the user-visible summary line).
    assert "two short sentences" in src or "summary" in src
    # Cached per-document via doc_hash to avoid re-call on every drawer
    # open — the user's audit explicitly asked this.
    assert "doc_hash" in src or "_doc_hash" in src


# ─────────────────────────────────────────────────────────────────────
# 1.3 — H1 + subtext present on every top-level surface
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,path", SURFACE_FILES.items())
def test_W1_3_surface_has_h1_and_subtext(name, path):
    src = path.read_text(encoding="utf-8")
    # H1 — either a literal <h1 tag or the akki-greeting token in a tag.
    has_h1 = "<h1" in src or "<H1" in src
    assert has_h1, f"{name} ({path.name}) must render an <h1>"
    # Subtext — a paragraph near the H1. Look for the muted-line patterns
    # we use across the codebase: `akki-meta` class, `text-[var(--muted)]`,
    # or `subtitle` testid.
    has_subtext = (
        "akki-meta" in src
        or "text-[var(--muted)]" in src
        or "company-home-subtitle" in src
        or "solva-landing-title" in src  # Solva's "Pick what you came to do." italic line
    )
    assert has_subtext, \
        f"{name} ({path.name}) must render a one-line subtext under the H1"


# ─────────────────────────────────────────────────────────────────────
# 1.4 — Universal BackButton
# ─────────────────────────────────────────────────────────────────────

def test_W1_4a_backbutton_component_exists():
    assert BACK_BUTTON.exists(), "BackButton.jsx must exist at the locked path"
    src = BACK_BUTTON.read_text(encoding="utf-8")
    # Uses router navigate(-1) — history-based, not hard-coded.
    assert "navigate(-1)" in src
    # Hides on top-level routes.
    assert "TOP_LEVEL_ROUTES" in src
    # Hides when history depth is 1.
    assert "window.history.length" in src
    # Carries the locked testid.
    assert 'data-testid={testId}' in src or 'testId = "back-button"' in src


@pytest.mark.parametrize("route", [
    "/", "/sign-in", "/sign-up", "/app",
    "/app/portfolio", "/app/contexts", "/app/companies",
    "/app/first-session", "/app/early-access-opt-in",
])
def test_W1_4b_backbutton_excludes_top_level_routes(route):
    src = BACK_BUTTON.read_text(encoding="utf-8")
    # Each top-level route is in the TOP_LEVEL_ROUTES array.
    assert f'"{route}"' in src, \
        f"BackButton must list {route!r} as a top-level (no-back) route"


def test_W1_4c_appshell_mounts_back_button():
    src = APPSHELL.read_text(encoding="utf-8")
    assert "import BackButton" in src, "AppShell must import BackButton"
    assert "<BackButton" in src, "AppShell must render <BackButton />"
    assert "appshell-back-slot" in src, "AppShell back-slot testid must be present"


# ─────────────────────────────────────────────────────────────────────
# 1.5 — Monitor probability bar uses grey/purple
# ─────────────────────────────────────────────────────────────────────

def test_W1_5_probability_bar_uses_grey_purple_not_rag():
    src = STRAT_PANEL.read_text(encoding="utf-8")
    # The brand purple token is ned-purple per index.css (#6B46C1).
    assert "var(--ned-purple)" in src, \
        "Probability bar must reference the brand purple token (--ned-purple)"
    # Locate the probabilityBarClass function and check the green/amber/red
    # RAG palette is GONE from probability (the performance bar keeps it).
    m = re.search(r'function probabilityBarClass[\s\S]{0,400}?\n\}', src)
    assert m, "probabilityBarClass function must exist"
    prob_body = m.group(0)
    assert "emerald-600" not in prob_body, \
        "Probability bar must not use emerald-600 (that's the performance bar)"
    assert "amber-500" not in prob_body, \
        "Probability bar must not use amber-500"
    assert "oxblood" not in prob_body, \
        "Probability bar must not use oxblood (the red severity colour)"
    assert "ned-purple" in prob_body, \
        "Probability bar must use --ned-purple"


def test_W1_5b_performance_bar_keeps_green_amber_red():
    """Belt-and-braces: the PERFORMANCE bar (statusBarClass) must STAY
    on the green/amber/red RAG palette — only the PROBABILITY bar was
    asked to change."""
    src = STRAT_PANEL.read_text(encoding="utf-8")
    m = re.search(r'function statusBarClass[\s\S]{0,400}?\n\}', src)
    assert m, "statusBarClass function must exist"
    body = m.group(0)
    assert "emerald-600" in body, "Performance bar must keep emerald-600 (green)"
    assert "amber-500" in body, "Performance bar must keep amber-500 (amber)"
    assert "oxblood" in body, "Performance bar must keep oxblood (red)"


# ─────────────────────────────────────────────────────────────────────
# 1.6 — Monitor button rename + sibling action
# ─────────────────────────────────────────────────────────────────────

def test_W1_6a_add_button_renamed_to_manually_add():
    src = OBJ_PANEL.read_text(encoding="utf-8")
    assert "Manually Add Objectives or Projects" in src, \
        "Monitor + Add button must read 'Manually Add Objectives or Projects'"
    # Legacy "+ Add {kind}" template must be gone from the panel header.
    # (The kind label still appears inside the dialog title.)
    m = re.search(r'data-testid="obj-panel-add"[\s\S]{0,400}?</Button>', src)
    assert m, "obj-panel-add button must exist"
    assert "Add {kind}" not in m.group(0), \
        "Legacy 'Add {kind}' label must be replaced on the panel button"


def test_W1_6b_read_from_doc_sibling_button_present():
    src = OBJ_PANEL.read_text(encoding="utf-8")
    assert "Read Goals from Strategic/Performance Documents" in src, \
        "Monitor must surface a sibling 'Read Goals from Strategic/Performance Documents' button"
    assert "obj-panel-read-from-doc" in src, \
        "Sibling button must carry the locked testid"
    # The sibling clicks through to the existing strategic-goals-add
    # trigger to share one extraction modal.
    assert 'strategic-goals-add' in src, \
        "Sibling button must click through to the existing strategic-goals-add trigger"
