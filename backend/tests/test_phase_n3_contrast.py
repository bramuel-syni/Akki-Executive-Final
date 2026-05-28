"""Phase N.3 (2026-05-27) — axe a11y color-contrast lockdown.

Locks the fixed violations + prevents regression:
  • No `color: var(--graphite-light)` in any CSS file — that token
    has ~2.0:1 contrast on white (FAILS WCAG AA Normal Text 4.5:1).
    Use `color: var(--graphite)` (4.91:1 on white) or `--muted`
    (6.40:1 on white) or `--ink` (~14:1 on white).
  • The `--graphite-light` token may still be used as a BORDER /
    BACKGROUND / DIVIDER colour where text-contrast doesn't apply.
  • The marketing-page band index at `style.css` line ~464 (the
    rotated vertical mono label) MUST use `var(--graphite)` not the
    light token.

N.3 deliberately leaves the `--graphite-light` token VALUE unchanged
(`#B8B6AF`) so brand reads as before. Only text-color use is migrated.
A future N.4 follow-up can enumerate any axe violations that survive
this minimal fix (would require running axe against the deployed UI
and capturing the per-selector failures).
"""
from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent.parent

# CSS files we audit. Index.css + the website style.css are the only
# vanilla CSS in the SPA; tailwind utilities live inline in JSX.
CSS_FILES = [
    REPO / "frontend" / "src" / "index.css",
    REPO / "frontend" / "src" / "website" / "style.css",
]


def test_N3_a_no_text_color_uses_graphite_light():
    """`color: var(--graphite-light)` must not appear in any CSS file.

    The token can still be used for `border`, `background`, `outline`,
    etc. — text-contrast WCAG only applies to text colour.
    """
    pattern = re.compile(r"\bcolor:\s*var\(--graphite-light\)")
    violations = []
    for path in CSS_FILES:
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        for m in pattern.finditer(src):
            # Capture the line for the failure message.
            line_no = src[: m.start()].count("\n") + 1
            violations.append(f"{path.name}:{line_no}")
    assert not violations, (
        "N.3 contrast lockdown — `color: var(--graphite-light)` causes WCAG AA "
        f"Normal Text fail (2.0:1 on white). Found at: {violations}. "
        "Migrate to `var(--graphite)` (4.91:1) or `var(--muted)` (6.40:1)."
    )


def test_N3_b_border_and_background_uses_of_graphite_light_remain_allowed():
    """Belt-and-braces: confirm we DIDN'T accidentally remove the
    decorative border/background uses (those still work and don't
    trigger contrast violations)."""
    style_css = (REPO / "frontend" / "src" / "website" / "style.css").read_text(encoding="utf-8")
    # The evidence-strip border rule is one example; the scrollbar
    # thumb in index.css is another. Both should still be present.
    assert "border-top: 1px solid var(--graphite-light)" in style_css, \
        "Decorative border use of --graphite-light should remain (non-text contexts pass contrast)"
    index_css = (REPO / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    assert "background: var(--graphite-light)" in index_css, \
        "Scrollbar thumb background use of --graphite-light should remain"


def test_N3_c_band_index_label_uses_graphite_not_light():
    """The marketing-page rotated band-index label at style.css ~line 464
    must use `var(--graphite)` (the locked N.3 fix)."""
    src = (REPO / "frontend" / "src" / "website" / "style.css").read_text(encoding="utf-8")
    # The label has the `font-family: var(--mono); font-size: 11px;` +
    # `writing-mode: vertical-rl;` signature. Confirm it picks up the
    # darker token.
    idx = src.find("writing-mode: vertical-rl")
    assert idx > 0, "Marketing band-index label block must exist"
    # Slice forward to the next closing brace.
    block_end = src.find("}", idx)
    block = src[idx:block_end]
    assert "color: var(--graphite);" in block, \
        "Marketing band-index label must use `color: var(--graphite)` (not graphite-light)"
