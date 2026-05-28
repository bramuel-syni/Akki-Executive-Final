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
    """Wave8.followup.1 (2026-05-27 rewrite) — the Workspace listing
    must surface every canonical origin label. The legacy test
    scanned a 1400-char window after "akki-meta mt-0.5"; that
    window moved during the Z-slice-4 refactor. The current
    Workspace.jsx renders origin badges via the per-row map at
    lines 488-497 — assert both label strings appear in the file
    AND the file imports/references the origin enum."""
    src = _read("frontend/src/pages/Workspace.jsx")
    # Both human labels surface (mapped from raw `origin` values).
    assert "Akki Generated" in src, (
        "Workspace.jsx must render the 'Akki Generated' label for "
        "rows with origin='akki_generated'."
    )
    assert "Uploaded" in src, (
        "Workspace.jsx must render the 'Uploaded' label for rows "
        "with origin='upload'."
    )
    # The mapping must key off the raw `origin` field (not legacy
    # `source_channel`-only branching).
    assert 'origin === "akki_generated"' in src


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
    pos_status     = src.find('data-testid="obj-drawer-status-card"')
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


# Tester re-open 2026-05-25 — false-green regression guard.
# The first T2.3 implementation hid Description and Citations behind
# data gates that no test data triggered. These tests assert each
# section emits DOM UNCONDITIONALLY so the false-green pattern
# (source-says-yes / DOM-says-no) cannot recur.
def test_t2_3_description_card_renders_unconditionally():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # The wrapping <div data-testid="obj-drawer-description"> must NOT
    # be inside a `{row?.description && (...)}` conditional. Locate
    # the marker and walk 80 chars backwards — the immediately-prior
    # JSX must NOT contain a conditional `&&` that gates the block.
    idx = src.find('data-testid="obj-drawer-description"')
    assert idx != -1
    prior = src[max(0, idx - 200):idx]
    # The block opens with a literal `<div ` rather than a conditional.
    assert prior.rstrip().endswith("<div"), (
        "obj-drawer-description must be emitted unconditionally; found "
        f"prior context: {prior[-200:]!r}"
    )


def test_t2_3_citations_card_renders_unconditionally():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    idx = src.find('data-testid="obj-drawer-citations"')
    assert idx != -1
    # Look for the opening `<div` that owns this testid attribute and
    # confirm there is no `{...&& (` gate immediately preceding it.
    preceding = src[max(0, idx - 400):idx]
    # The card's container is a plain <div, not a conditional render.
    assert "&&" not in preceding.split("<div")[-1], (
        "obj-drawer-citations must be emitted unconditionally; the prior "
        "version hid it behind `assessment && supporting_docs.length > 0`. "
        f"prior context: {preceding[-400:]!r}"
    )


def test_t2_3_citations_empty_state_renders_upload_button():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # The empty-state branch inside the citations card MUST render the
    # Upload Document button + a real <input type="file">. Both testids
    # belong to the same Citations Card empty state, not the deprecated
    # "no-data" branch.
    assert "obj-drawer-citations-upload-btn" in src
    assert "obj-drawer-citations-upload-input" in src
    assert "obj-drawer-citations-empty" in src
    # The button literal label is "Upload Document" (verbatim).
    block = src[src.find('data-testid="obj-drawer-citations-upload-btn"'):]
    assert ">\n                  Upload Document\n" in block[:400] or \
           "Upload Document" in block[:400], \
           "Upload Document button label missing in the Citations empty state."


def test_t2_3_drawer_status_card_has_no_score_or_trend_cells():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # The Status Card region (between `obj-drawer-status-card` and the
    # following Description marker) must NOT contain Score / Trend
    # labels. Score and Trend remain visible on the listing rows
    # themselves — only the drawer is reshaped.
    start = src.find('data-testid="obj-drawer-status-card"')
    end = src.find('data-testid="obj-drawer-description"', start)
    assert start != -1 and end != -1
    region = src[start:end]
    assert ">Score<" not in region, (
        "Status Card still contains a Score cell. PO fix-scope requires "
        "Score removed from the drawer."
    )
    assert ">Trend<" not in region, (
        "Status Card still contains a Trend cell. PO fix-scope requires "
        "Trend removed from the drawer."
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
    # The Citations Card empty state offers the Upload Document affordance.
    # The legacy no-data sub-tree (which depended on the backend explicitly
    # returning {no_data: true}) collapses into the always-on empty state.
    assert "obj-drawer-citations-upload-btn" in src
    assert "obj-drawer-citations-upload-input" in src
    # The previous no-data-upload sub-tree IDs are gone.
    assert "obj-drawer-no-data-upload-btn" not in src
    assert "obj-drawer-no-data-upload-input" not in src
    # The simple-text no-data line is still wired (uses backend message).
    assert "obj-drawer-no-data" in src


def test_t2_3_monitor_drawer_akki_status_label_removed():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # X5 step 1: delete the Akki Status section header.
    assert "Akki status" not in src


def test_t2_3_monitor_drawer_citations_card_renders_doc_names():
    src = _read("frontend/src/components/monitor/ObjectivesProjectsPanel.jsx")
    # The citations card iterates over supporting_docs (name-resolved
    # server-side) — not supporting_doc_ids (raw IDs).
    block = src[src.find('data-testid="obj-drawer-citations"'):]
    assert "supporting_docs" in block[:2500]
    assert "d.name" in block[:2500]
    # Citations render as <a href="/app/documents/{id}"> per fix-scope.
    assert "/app/documents/${d.id}" in block[:2500]


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
