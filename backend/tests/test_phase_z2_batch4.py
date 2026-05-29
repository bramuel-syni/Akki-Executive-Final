"""Phase Z2 Batch 4 (2026-02 fork-resume v2) — Z2.7 lockdown.

Z2.7 — Sources visible on every artefact category in the universal
DocumentDrawer. The DocumentDrawer's Intelligence tab renders a new
`drawer-intel-sources` section unconditionally for any doc whose
`category` is on the artefact whitelist (board_pack, minutes, draft,
deck, report, briefing, committee_pack). Either:

  • populated → `<ul data-testid="drawer-intel-sources-list">` with
    one `<li data-testid="drawer-intel-sources-item">` per source
    doc id pulled from `doc.source_doc_ids`; OR
  • fallback → `<p data-testid="drawer-intel-sources-fallback">
    Sources: not applicable for this artefact type.</p>`

— never silently hidden, even when no provenance data exists. This is
the canonical user-visible surface (BriefDrawer in WorkStudio.jsx is
dead code; the live route is `?doc_id=<aid>` → `<DocumentDrawer>`).
"""
from __future__ import annotations
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"
DRAWER = FRONTEND / "components" / "documents" / "DocumentDrawer.jsx"


BANNED_WORDS = [
    "leverage", "empower", "AI-powered", "AI-driven", "insights",
    "dashboard", "seamless", "revolutionary", "cutting-edge",
    "disrupt", "frictionless", "unlock", "supercharge", "synergy",
    "game-changer",
]


def _voice_lint(snippet: str) -> list[str]:
    lc = snippet.lower()
    return [w for w in BANNED_WORDS if w in lc]


def test_z2_7_artefact_category_whitelist_complete():
    src = DRAWER.read_text(encoding="utf-8")
    # The whitelist locks every artefact type the brief named —
    # committee_pack, minutes, draft, deck, report — plus board_pack
    # and briefing for completeness.
    expected = ["board_pack", "minutes", "draft", "deck", "report", "briefing", "committee_pack"]
    for cat in expected:
        assert f'"{cat}"' in src, f"Missing category {cat!r} in _ARTEFACT_CATEGORIES"
    assert "const _ARTEFACT_CATEGORIES = [" in src


def test_z2_7_sources_section_rendered_in_document_drawer():
    src = DRAWER.read_text(encoding="utf-8")
    assert 'data-testid="drawer-intel-sources"' in src
    assert 'data-testid="drawer-intel-sources-list"' in src
    assert 'data-testid="drawer-intel-sources-item"' in src
    assert 'data-testid="drawer-intel-sources-fallback"' in src
    # Fallback copy verbatim
    assert "Sources: not applicable for this artefact type." in src


def test_z2_7_section_renders_for_every_artefact_category():
    """The render gate is purely category-based — no `mode` filter,
    so the Sources block surfaces on uploaded artefacts AND akki-
    generated artefacts uniformly. Locked here so a future change
    cannot accidentally restrict it back to `mode === "reference"`."""
    src = DRAWER.read_text(encoding="utf-8")
    gate = "{_ARTEFACT_CATEGORIES.includes((doc?.category || \"\").toLowerCase()) && ("
    assert gate in src, "Render gate must be category-based, not mode-based"


def test_z2_7_populated_branch_uses_source_doc_ids():
    src = DRAWER.read_text(encoding="utf-8")
    # The populated branch iterates `doc.source_doc_ids`, the canonical
    # field for derived artefacts (board_pack, briefing, deck, report).
    assert "doc.source_doc_ids" in src
    assert "doc.source_doc_ids.length > 0" in src


def test_z2_7_fallback_copy_passes_voice_lint():
    hits = _voice_lint("Sources: not applicable for this artefact type.")
    assert not hits, f"Voice-lint failed on fallback copy: {hits}"


def test_z2_7_loc_budget_under_50():
    """The Z2.7 dispatch had a hard 50-LOC cap. Counts the lines
    between the locked markers below — both the constant declaration
    and the rendered block."""
    src = DRAWER.read_text(encoding="utf-8")
    # Constant block
    c_start = "// Z2.7 (2026-02) — artefact categories"
    c_end_marker = "];"
    c_start_idx = src.find(c_start)
    c_end_idx = src.find(c_end_marker, c_start_idx)
    assert c_start_idx >= 0 and c_end_idx >= 0
    const_block = src[c_start_idx: c_end_idx + len(c_end_marker)]

    # JSX block
    j_start = "/* Z2.7 (2026-02) — Sources block for every"
    j_end = "})()"  # not present; use the closing of the conditional
    j_start_idx = src.find(j_start)
    # The block ends with `</section>\n      )}`
    j_end_marker = "</section>\n      )}"
    j_end_idx = src.find(j_end_marker, j_start_idx)
    assert j_start_idx >= 0 and j_end_idx >= 0
    jsx_block = src[j_start_idx: j_end_idx + len(j_end_marker)]

    total_loc = const_block.count("\n") + 1 + jsx_block.count("\n") + 1
    assert total_loc <= 50, f"Z2.7 LOC budget exceeded: {total_loc} > 50"
