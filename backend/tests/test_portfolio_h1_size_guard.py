"""Per-page H1 size guard — 2026-05-26.

Background: user requested a 20% INCREASE on the "My Companies"
H1 in ContextPortfolio (`pages/ContextPortfolio.jsx`). The canonical
`.akki-greeting` design token is shared by 16 other surfaces and
MUST stay at its current 28px — only ContextPortfolio overrides.

These tests lock that contract in:
  T1. ContextPortfolio H1 carries the 34px inline override + the
      stable `portfolio-companies-h1` testid.
  T2. The other 15+ `.akki-greeting` surfaces do NOT carry any
      per-instance font-size override (no inline style or
      `text-[<N>px]` Tailwind utility) on their `akki-greeting` H1.
  T3. The `.akki-greeting` CSS rule in index.css still sets
      `font-size: 28px` (tripwire on the token).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

CONTEXT_PORTFOLIO = FE / "pages" / "ContextPortfolio.jsx"
INDEX_CSS = FE / "index.css"

# Per-page H1s that share the `.akki-greeting` design token. These
# surfaces MUST NOT carry a per-instance font-size override.
AKKI_GREETING_PEERS = [
    FE / "pages" / "Prepare.jsx",
    FE / "pages" / "Manage.jsx",
    FE / "pages" / "RespondToChecklist.jsx",
    FE / "pages" / "InfluenceMap.jsx",
    FE / "pages" / "Pulse.jsx",
    FE / "pages" / "Questions.jsx",
    FE / "pages" / "WorkStudio.jsx",
    FE / "pages" / "Learn.jsx",
    FE / "pages" / "Monitor.jsx",
    FE / "pages" / "admin" / "AuthEvents.jsx",
    FE / "pages" / "admin" / "HealthDashboard.jsx",
    FE / "pages" / "admin" / "AdminIndex.jsx",
    FE / "pages" / "admin" / "LLMSpend.jsx",
    FE / "pages" / "marketing" / "BlogAdmin.jsx",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. ContextPortfolio H1 carries the 34px override + testid ──
def test_portfolio_companies_h1_carries_34px_override():
    src = _read(CONTEXT_PORTFOLIO)
    # Stable testid so the runtime guard can reliably pin it.
    assert 'data-testid="portfolio-companies-h1"' in src, (
        "Portfolio 'My Companies' H1 must carry the "
        "`portfolio-companies-h1` testid for runtime size assertion."
    )
    # Inline style override at 34px (20% increase from canonical 28px).
    # We accept either `fontSize: "34px"` or `fontSize: '34px'`.
    assert (
        'fontSize: "34px"' in src
        or "fontSize: '34px'" in src
    ), (
        "Portfolio 'My Companies' H1 must carry inline "
        "`style={{ fontSize: '34px' }}` to override the canonical "
        ".akki-greeting 28px (per-page 20% increase decision)."
    )
    # H1 still uses the akki-greeting class for font-family/weight
    # inheritance (we only override the size).
    assert (
        'className="akki-greeting"' in src
        or 'className={`akki-greeting' in src
    )


# ── T2. Peers do NOT carry a per-instance font-size override ────
@pytest.mark.parametrize("page_path", AKKI_GREETING_PEERS, ids=lambda p: p.name)
def test_akki_greeting_peer_h1_has_no_per_instance_font_size_override(page_path):
    """Each peer page that uses `.akki-greeting` on its H1 must NOT
    carry a per-instance font-size override (inline style or
    Tailwind arbitrary `text-[<N>px]`). Stops accidental drift to
    the per-page-override pattern from spreading."""
    src = _read(page_path)
    # Locate each `<h1 ... akki-greeting ...>` element. Allow either
    # className="akki-greeting" or className="akki-greeting <other>".
    # We scan the source for h1 elements containing akki-greeting and
    # then check the SAME h1 tag for any size override.
    pattern = re.compile(
        r"<h1\s+[^>]*?className=[\"'`][^\"'`]*akki-greeting[^\"'`]*[\"'`][^>]*?>",
        re.DOTALL,
    )
    matches = pattern.findall(src)
    assert matches, (
        f"{page_path.name}: expected at least one <h1> with "
        "`.akki-greeting` class but found none — audit drift."
    )
    for m in matches:
        # No inline fontSize style.
        assert "fontSize" not in m, (
            f"{page_path.name}: h1 tag {m[:140]!r} carries an inline "
            "fontSize override. Per-page font-size on `.akki-greeting` "
            "is reserved for ContextPortfolio (My Companies) only."
        )
        # No Tailwind arbitrary text-[Npx] inside the className.
        assert not re.search(r"text-\[\d+(\.\d+)?px\]", m), (
            f"{page_path.name}: h1 tag {m[:140]!r} carries a Tailwind "
            "`text-[<N>px]` size override. Per-page font-size on "
            "`.akki-greeting` is reserved for ContextPortfolio only."
        )


# ── T3. Canonical .akki-greeting token still at 28px ──────────────
def test_akki_greeting_token_remains_28px():
    """Tripwire — if anyone touches the canonical token in index.css,
    this fails immediately."""
    css = _read(INDEX_CSS)
    rule_match = re.search(
        r"\.akki-greeting\s*\{[^}]*?font-size:\s*([0-9]+(?:\.[0-9]+)?)px",
        css, flags=re.DOTALL,
    )
    assert rule_match, (
        ".akki-greeting rule with explicit font-size not found in "
        "frontend/src/index.css — token may have been moved or "
        "renamed."
    )
    size = float(rule_match.group(1))
    assert size == 28, (
        f".akki-greeting font-size is {size}px in index.css; the "
        "canonical token must stay at 28px. Per-page reductions are "
        "via per-instance overrides (e.g. inline style on the H1)."
    )
