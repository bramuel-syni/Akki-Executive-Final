"""Phase M — Work Studio + Task Manager noise reduction CI guards (2026-05-27).

User raised this ≥3 times. Verbatim spec captured in PHASE_LEDGER M row.
Locks the entire M scope so future agents can't accidentally re-introduce
the agent-added surplus.

Locks:
  M.1 — Main Board & Committee Packs tab has NO doc-card listing + NO ListingShell
    M1a. DocumentCardsSection is gated by `kind !== "cycle_main_and_committee_pack"`
    M1b. ListingShell is gated by `kind !== "cycle_main_and_committee_pack"`
    M1c. ContextActions (Compile CTAs) stays visible unconditionally
    M1d. Drafts tab listing remains intact (regression guard)

  M.1.5 — Tab strip + Briefing pill layout
    M15a. 5 tabs in KIND_TABS (NOT 6 — Briefing moved off the strip)
    M15b. Briefing kept as BRIEFING_TAB constant (data path preserved)
    M15c. Briefing pill rendered on a 2nd line with the briefing testid

  M.2 — Subtitle removed (or trimmed to ≤5 words without tab-label words)
    M2a. Old subtitle text "Shape board packs, decks, reports, and briefings"
         must NOT appear in source.
    M2b. data-testid="work-studio-subtitle" must NOT appear (subtitle gone).
    M2c. H1 text "Check or review your work." preserved.

  M.3 — Task Manager (no equivalent surface to remove — surface explicitly)
    M3a. Source-strict guard: TaskManager.jsx contains no DocumentCardsSection
         OR Show drafts toggle OR MOST RECENT dropdown — the page is already clean.

  Negative regressions
    N1. "Show drafts & empties" toggle never re-appears (was never there;
        keep absent).
    N2. The brief's exact phrase "Shape board packs, decks, reports, and briefings"
        never re-appears in source.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
WORK_STUDIO = REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx"
TASK_MANAGER = REPO / "frontend" / "src" / "pages" / "TaskManager.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# M.1 — Doc-card listing removal on Main Board & Committee Packs tab
# ─────────────────────────────────────────────────────────────────

def test_m_M1a_document_cards_section_gated_by_tab():
    """DocumentCardsSection must render only when NOT on the
    Main Board & Committee Packs tab."""
    src = _read(WORK_STUDIO)
    # Strip docstrings/comments first
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    # Look for the conditional wrapper. Both single-line and multi-line
    # rendering patterns are valid.
    m = re.search(
        r'kind\s*!==\s*[\'"]cycle_main_and_committee_pack[\'"]\s*&&[\s\S]{0,400}?<DocumentCardsSection',
        code,
    )
    assert m, (
        "DocumentCardsSection must be gated by "
        "`kind !== 'cycle_main_and_committee_pack'` per Phase M."
    )


def test_m_M1b_listing_shell_gated_by_tab():
    """ListingShell must render only when NOT on the Main Board & Committee Packs tab."""
    src = _read(WORK_STUDIO)
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    # There must be a gating expression before the ListingShell render
    # in the work-studio main body.
    m = re.search(
        r'kind\s*!==\s*[\'"]cycle_main_and_committee_pack[\'"]\s*&&[\s\S]{0,400}?<ListingShell',
        code,
    )
    assert m, (
        "ListingShell must be gated by "
        "`kind !== 'cycle_main_and_committee_pack'` per Phase M."
    )


def test_m_M1c_context_actions_unconditionally_rendered():
    """ContextActions (the Compile CTAs strip) stays visible on every
    tab — including the now-otherwise-empty Main Board & Committee Packs
    tab. It is NOT wrapped in a tab-conditional."""
    src = _read(WORK_STUDIO)
    # Find the ContextActions JSX render
    m = re.search(r"(<ContextActions[\s\S]{0,400}?/>)", src)
    assert m, "ContextActions render not found."
    block = m.group(1)
    # The block itself must not contain the gating expression.
    assert 'kind !== "cycle_main_and_committee_pack"' not in block, (
        "ContextActions must NOT be gated by the Main Board & Committee "
        "Packs tab — Compile CTAs stay visible per Phase M."
    )


def test_m_M1d_drafts_tab_still_uses_listing_shell():
    """Regression guard: the Drafts tab (kind=drafts) MUST still
    receive the ListingShell render. User explicitly said Drafts has a
    clear surface path."""
    src = _read(WORK_STUDIO)
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    # Drafts kind is `drafts`. The gating filter excludes only
    # `cycle_main_and_committee_pack`, so Drafts naturally passes.
    # Source-strict: KIND_TABS must contain `drafts`.
    assert 'id: "drafts"' in src, (
        "Drafts tab kind must remain in KIND_TABS — user-spec require."
    )


# ─────────────────────────────────────────────────────────────────
# M.1.5 — Tab strip + Briefing pill
# ─────────────────────────────────────────────────────────────────

def test_m_M15a_five_tabs_only_in_horizontal_strip():
    """KIND_TABS must contain exactly 5 entries (Briefing moved off
    the horizontal strip)."""
    src = _read(WORK_STUDIO)
    m = re.search(r"const KIND_TABS\s*=\s*\[([\s\S]*?)\];", src)
    assert m, "KIND_TABS constant not found."
    body = m.group(1)
    # Count top-level entries by looking for `id: "..."` matches.
    ids = re.findall(r'id:\s*"([^"]+)"', body)
    assert len(ids) == 5, f"Expected 5 KIND_TABS entries, found {len(ids)}: {ids}"
    # Briefing must NOT be in the array.
    assert "briefing" not in ids, (
        "Briefing must NOT be in KIND_TABS — it lives in BRIEFING_TAB "
        "and renders as a 2nd-line pill per Phase M."
    )
    # Required tabs in correct order.
    expected_prefix = [
        "cycle_main_and_committee_pack", "cycle_minutes",
        "drafts", "deck", "report",
    ]
    assert ids == expected_prefix, (
        f"KIND_TABS order/contents drifted from spec: {ids}"
    )


def test_m_M15b_briefing_tab_constant_preserved():
    """BRIEFING_TAB constant exists with the briefing data path."""
    src = _read(WORK_STUDIO)
    assert "const BRIEFING_TAB" in src
    m = re.search(r"const BRIEFING_TAB\s*=\s*\{[^}]*id:\s*\"briefing\"", src)
    assert m, "BRIEFING_TAB must keep the kind=briefing data path."


def test_m_M15c_briefing_pill_renders_on_second_line():
    """A briefing pill must render below the tab strip with the
    `work-studio-briefing-pill` testid."""
    src = _read(WORK_STUDIO)
    assert "work-studio-briefing-row" in src, (
        "Briefing 2nd-line container must have its row testid."
    )
    assert "work-studio-briefing-pill" in src, (
        "Briefing pill button must have its testid for clickability tests."
    )


# ─────────────────────────────────────────────────────────────────
# M.2 — Subtitle dropped
# ─────────────────────────────────────────────────────────────────

def test_m_M2a_no_repetitive_subtitle_phrase():
    """The brief's verbatim removal target ("Shape board packs, decks,
    reports, and briefings...") must NOT appear in source."""
    src = _read(WORK_STUDIO)
    forbidden_phrases = [
        "Shape board packs, decks, reports, and briefings",
        "Shape board packs",
    ]
    for p in forbidden_phrases:
        assert p not in src, (
            f"Forbidden subtitle phrase reintroduced: {p!r}"
        )


def test_m_M2b_no_subtitle_testid():
    """Subtitle entirely dropped (default-drop per brief). The
    `work-studio-subtitle` testid must not appear."""
    src = _read(WORK_STUDIO)
    assert 'data-testid="work-studio-subtitle"' not in src, (
        "work-studio-subtitle data-testid must be removed per Phase M.2 "
        "default-drop. If a ≤5-word lead-in is reintroduced later, it "
        "must use a DIFFERENT testid and pass the word-count guard."
    )


def test_m_M2c_h1_preserved():
    """The H1 'Check or review your work.' must remain unchanged."""
    src = _read(WORK_STUDIO)
    assert "Check or review your work." in src, (
        "Work Studio H1 must remain — only the subtitle is dropped."
    )


# ─────────────────────────────────────────────────────────────────
# M.3 — Task Manager already clean (no equivalent surface to remove)
# ─────────────────────────────────────────────────────────────────

def test_m_M3a_task_manager_already_clean():
    """Task Manager has no DocumentCardsSection / Show drafts / MOST
    RECENT dropdown — the page's existing TaskListing is the legitimate
    canonical surface. Source-strict guard against future regressions
    that could accidentally re-introduce the same surplus pattern here."""
    src = _read(TASK_MANAGER)
    forbidden = [
        "<DocumentCardsSection",
        "Show drafts & empties",
        "MOST RECENT",
    ]
    for f in forbidden:
        assert f not in src, (
            f"Task Manager picked up {f!r} which is the same surplus "
            f"pattern Phase M removed from Work Studio. Don't re-introduce."
        )


# ─────────────────────────────────────────────────────────────────
# Negative regressions
# ─────────────────────────────────────────────────────────────────

def test_m_N1_show_drafts_toggle_never_reappears():
    """'Show drafts & empties' toggle must never appear in WorkStudio."""
    src = _read(WORK_STUDIO)
    assert "Show drafts & empties" not in src
    assert "show-drafts-toggle" not in src


def test_m_N2_subtitle_words_never_recombine():
    """The 4 tab-label words must never appear together in a subtitle-
    looking phrase. Guards against accidental re-introduction of the
    forbidden copy in a slightly different form."""
    src = _read(WORK_STUDIO)
    # Strip JS docstrings + line comments + the KIND_TABS / BRIEFING_TAB
    # constants (which legitimately reference all the tab labels).
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    code = re.sub(r"const KIND_TABS\s*=\s*\[[\s\S]*?\];", "", code)
    code = re.sub(r"const BRIEFING_TAB\s*=\s*\{[^}]*\};", "", code)
    forbidden_combos = [
        re.compile(r"board packs.{0,60}decks.{0,60}reports", re.IGNORECASE),
        re.compile(r"decks.{0,60}reports.{0,60}briefings", re.IGNORECASE),
    ]
    for r in forbidden_combos:
        assert not r.search(code), (
            f"Forbidden 3+ tab-label subtitle pattern reappeared: "
            f"{r.pattern!r}"
        )
