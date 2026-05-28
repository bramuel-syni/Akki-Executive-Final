"""Wave 2 (2026-05-27) — Monitor capsule tabs restructure CI lockdown.

Locks the user-asked changes:
  • Capsule tab nav with labels "Strategic Objectives/Goals" and
    "Strategic Projects/Tasks".
  • Tab style: dark-pill-on-light treatment (matches the
    owner-role strip + the user's circled screenshot reference).
  • Default tab on mount: "Strategic Objectives/Goals" (the
    objective kind).
  • Listings under each tab show only the items for that kind
    (already enforced by the existing `kind` state — relock).
"""
from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent.parent
OBJ_PANEL = REPO / "frontend" / "src" / "components" / "monitor" / "ObjectivesProjectsPanel.jsx"


def _capsule_block(src):
    """Return the capsule tab JSX block (between the
    `obj-panel-kind-capsule` testid and the closing </div>)."""
    m = re.search(
        r'data-testid="obj-panel-kind-capsule"[\s\S]*?</div>',
        src,
    )
    assert m, "Capsule tab nav block must exist with testid 'obj-panel-kind-capsule'"
    return m.group(0)


def test_W2_a_capsule_nav_carries_locked_testid():
    src = OBJ_PANEL.read_text(encoding="utf-8")
    assert 'data-testid="obj-panel-kind-capsule"' in src, \
        "Strategic capsule tab nav must carry testid 'obj-panel-kind-capsule'"
    assert 'role="tablist"' in src, "Capsule nav must declare role='tablist' for a11y"


def test_W2_b_strategic_objectives_label_locked():
    block = _capsule_block(OBJ_PANEL.read_text(encoding="utf-8"))
    assert "Strategic Objectives/Goals" in block, \
        "Capsule tab 0 label must be 'Strategic Objectives/Goals'"


def test_W2_c_strategic_projects_label_locked():
    block = _capsule_block(OBJ_PANEL.read_text(encoding="utf-8"))
    assert "Strategic Projects/Tasks" in block, \
        "Capsule tab 1 label must be 'Strategic Projects/Tasks'"


def test_W2_d_default_tab_is_objective():
    src = OBJ_PANEL.read_text(encoding="utf-8")
    # `useState("objective")` initial state — the default capsule tab.
    assert 'useState("objective")' in src, \
        "Default kind state must be 'objective' (Strategic Objectives/Goals tab)"


def test_W2_e_active_pill_uses_dark_on_light():
    block = _capsule_block(OBJ_PANEL.read_text(encoding="utf-8"))
    # Dark-pill-on-light: active = bg ink + text parchment.
    assert "bg-[var(--ink)] text-[var(--parchment)]" in block, \
        "Active capsule tab must use the dark-pill-on-light treatment"
    # Inactive matches the owner-role strip's hover affordance.
    assert "hover:bg-[var(--cream-deep)]" in block, \
        "Inactive capsule tab must use the same hover affordance as the owner strip"


def test_W2_f_legacy_outline_style_removed():
    block = _capsule_block(OBJ_PANEL.read_text(encoding="utf-8"))
    # The pre-W2 style used `bg-white border` for active — must be GONE
    # from the capsule block.
    assert "bg-white border border-[var(--ink)]" not in block, \
        "Legacy capsule outline style must be removed"


def test_W2_g_listings_remain_kind_scoped():
    """Belt-and-braces: confirm the `kind` state still drives the list
    query so each tab shows only its items. The existing `useCallback`
    references `kind` in the dependency array AND the URL path."""
    src = OBJ_PANEL.read_text(encoding="utf-8")
    # The GET request hits `/monitor/{kind}` where kind ∈ {objective, project}.
    assert "/monitor/${kind}" in src, \
        "Listing query must be kind-scoped (`/monitor/${kind}`)"
