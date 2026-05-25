"""T2 frontend wire-checks.

Static file-source assertions that prove the T2 UI invariants are in
place without needing a browser.

T2.1 — Document Journal filter tabs (D3/D4)
T2.2 — Pulse signal-card body (X3 step 2)
T2.3 — Monitor drawer redesign (X5)
T2.4 — Strategic Goals filters (X6 G11 + X8 G12)
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    p = REPO / rel
    assert p.exists(), f"missing source file: {rel}"
    return p.read_text(encoding="utf-8")


# ── T2.1 ────────────────────────────────────────────────────────────
def test_t2_1_workspace_renders_four_filter_tabs_in_spec_order():
    src = _read("frontend/src/pages/Workspace.jsx")
    # The four labels must appear in the spec-defined order.
    labels_block = src[src.find("workspace-filter-tabs"):]
    pos_all       = labels_block.find('label: "All"')
    pos_uploaded  = labels_block.find('label: "Uploaded"')
    pos_akki      = labels_block.find('label: "Akki Generated"')
    pos_brief     = labels_block.find('label: "Briefings"')
    for name, p in [
        ("All", pos_all), ("Uploaded", pos_uploaded),
        ("Akki Generated", pos_akki), ("Briefings", pos_brief),
    ]:
        assert p != -1, f"D3 filter tab '{name}' is missing"
    assert pos_all < pos_uploaded < pos_akki < pos_brief, (
        "Filter tabs must appear in spec D3 order: All, Uploaded, "
        "Akki Generated, Briefings."
    )


def test_t2_1_workspace_default_filter_tab_is_all():
    src = _read("frontend/src/pages/Workspace.jsx")
    # Default tab on mount is "all" per D3 step 4.
    assert 'useState("all")' in src
    assert "filterTab" in src


def test_t2_1_workspace_origin_derivation_includes_akki_channels():
    src = _read("frontend/src/pages/Workspace.jsx")
    # Both Akki-generated source_channel values must be in the set.
    assert "cycle_compilation" in src
    assert "work_studio_export" in src
    assert 'origin === "briefing"' in src
    assert 'origin === "akki_generated"' in src


def test_t2_1_workspace_fetches_briefings_in_parallel():
    src = _read("frontend/src/pages/Workspace.jsx")
    # Briefings live in a separate endpoint; the listing must Promise.all
    # docs + briefings so the tabs reflect both.
    assert "/briefings" in src
    assert "Promise.all" in src


def test_t2_1_workspace_drawer_meta_includes_origin_badge():
    src = _read("frontend/src/pages/Workspace.jsx")
    # Drawer metadata must include "Uploaded" / "Akki Generated" per D4.
    # The drawer's derivation looks up source_channel client-side.
    block = src[src.find("akki-meta mt-0.5"):src.find("akki-meta mt-0.5") + 1400]
    assert "Akki Generated" in block
    assert "Uploaded" in block


# ── T2.2 ────────────────────────────────────────────────────────────
def test_t2_2_pulse_card_summary_uses_split_to_bullets():
    src = _read("frontend/src/pages/Pulse.jsx")
    # The card body must route through splitToBullets so two-or-more
    # points render as bullets and citations are stripped first.
    anchor = "Headline + body"
    idx = src.find(anchor)
    assert idx != -1
    block = src[idx:idx + 2200]
    assert "splitToBullets(card.summary)" in block
    # The raw <p>{card.summary}</p> rendering must be gone.
    assert "{card.summary}" not in block


# ── T2.3 ────────────────────────────────────────────────────────────
def test_t2_3_monitor_drawer_order_status_description_update_citations_timeline():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # In drawer render order: Status → Description → Update CTA → Citations → Timeline.
    pos_status     = src.find('data-testid="obj-drawer-rag"')
    pos_desc       = src.find('data-testid="obj-drawer-description"')
    pos_update     = src.find('data-testid="obj-drawer-update-block"')
    pos_citations  = src.find('data-testid="obj-drawer-citations"')
    pos_timeline   = src.find('data-testid="obj-drawer-timeline"')
    assert pos_status   != -1
    assert pos_desc     != -1
    assert pos_update   != -1
    assert pos_citations!= -1
    assert pos_timeline != -1
    assert pos_status < pos_desc < pos_update < pos_citations < pos_timeline, (
        "Monitor drawer block order does not match spec X5: Status → "
        "Description → Update CTA → Citations Card → Timeline."
    )


def test_t2_3_monitor_drawer_button_label_is_kind_aware():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    assert '"Update Project"' in src
    assert '"Update Objective"' in src
    # The old generic "Update goal" label is replaced.
    assert '"Update goal"' not in src.replace(
        # Allow the historical comment reference but not the literal button text.
        "/* QA-2026-05-16", "/* QA-2026-05-16",
    ) or src.count('"Update goal"') == 0


def test_t2_3_monitor_drawer_no_data_offers_upload_button():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # The X5 step 3 "no relevant docs" branch must offer an Upload
    # Document affordance that opens a file picker, replacing the
    # old plain "Open Document Journal" link.
    assert "obj-drawer-no-data-upload-btn" in src
    assert "obj-drawer-no-data-upload-input" in src
    # The previous Document Journal link is gone from the no-data block.
    assert "obj-drawer-no-data-doc-journal-link" not in src


def test_t2_3_monitor_drawer_akki_status_label_removed():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # X5 step 1: delete the Akki Status section header.
    assert "Akki status" not in src


def test_t2_3_monitor_drawer_citations_card_renders_doc_names():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # The citations card iterates over supporting_docs (name-resolved
    # server-side) — not supporting_doc_ids (raw IDs).
    block = src[src.find('data-testid="obj-drawer-citations"'):]
    assert "supporting_docs" in block[:1500]
    assert "d.name" in block[:1500]


# ── T2.4 ────────────────────────────────────────────────────────────
def test_t2_4_strategic_goals_status_tabs_six_in_spec_order():
    src = _read("frontend/src/components/monitor/StrategicGoalsPanel.jsx")
    block = src[src.find("STATUS_FILTER_TABS"):]
    # Order verbatim from spec X8 step 1.
    seq = ["All", "On Track", "At Risk", "Off Track", "Achieved", "Not Started"]
    last = -1
    for lbl in seq:
        i = block.find(f'label: "{lbl}"')
        assert i != -1, f"Status tab '{lbl}' missing"
        assert i > last, f"Status tab '{lbl}' is out of spec order"
        last = i


def test_t2_4_x6_g11_probability_thresholds_are_verbatim():
    src = _read("frontend/src/components/monitor/StrategicGoalsPanel.jsx")
    # G11 ratified: ≥70 green, 40-69 amber, <40 red.
    assert "value >= 70" in src
    assert "value >= 40" in src


def test_t2_4_x6_dual_rag_bars_independent_colours():
    src = _read("frontend/src/components/monitor/StrategicGoalsPanel.jsx")
    # Performance bar must use statusBarClass (status RAG).
    # Probability bar must use probabilityBarClass (band RAG).
    assert "barClass={statusBarClass(goal.status)}" in src
    assert "barClass={probabilityBarClass(prob)}" in src
    # The previous category-coloured performance bar must be gone.
    assert "barClass={cat.bar}" not in src
    # The previous ink-only probability bar must be gone.
    assert 'barClass="bg-[var(--ink)]"' not in src


def test_t2_4_x8_g12_category_filter_dynamic_with_fallback():
    src = _read("frontend/src/components/monitor/StrategicGoalsPanel.jsx")
    # Dynamic source from goal.department.
    assert "deriveCategoryOptions" in src
    assert "g.department" in src
    # Fallback list (verbatim from G12).
    assert (
        'G12_FALLBACK_CATEGORIES = ["Operations", "People", "Compliance", '
        '"Product", "Commercial"]'
    ) in src


def test_t2_4_x8_filters_combine_status_and_category():
    src = _read("frontend/src/components/monitor/StrategicGoalsPanel.jsx")
    # The filter useMemo must apply BOTH status and category filters.
    block = src[src.find("const filtered ="):]
    assert "statusFilter" in block[:600]
    assert "categoryFilter" in block[:600]
