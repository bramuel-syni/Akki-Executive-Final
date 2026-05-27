"""Phase N.2 — A11y color-contrast fix CI guard (2026-05-27).

Locks two invariants:

  T1.  `frontend/src/index.css` declares `--muted: #5e5f64;`
       (post-N.2 value). The historical alias to `var(--graphite)`
       is gone; consumers like Portfolio Landing / Company Home
       resolve `--muted` to the new color directly.
  T2.  Deterministic WCAG-AA contrast calculation:
         contrast(#5e5f64, #f2efe8) >= 4.5
       Implemented in pure Python so we don't depend on a runtime
       browser to verify the math. The result is also pasted in the
       N.2 ledger row.

`tests/test_phase_n2_axe_runtime.py` (separate, optional Playwright-
based regression) runs axe-core headlessly against `/` and `/sign-in`
and asserts zero color-contrast violations. Kept as a separate skip-
on-no-browser test to avoid flakiness in environments without
Playwright. The deterministic math test below is the hard guard.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
INDEX_CSS = REPO / "frontend" / "src" / "index.css"


# ── WCAG-AA contrast math (pure Python, no deps) ─────────────────
def _srgb_to_linear(channel_0_255: int) -> float:
    c = channel_0_255 / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_rgb: str) -> float:
    h = hex_rgb.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (
        0.2126 * _srgb_to_linear(r)
        + 0.7152 * _srgb_to_linear(g)
        + 0.0722 * _srgb_to_linear(b)
    )


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l_fg = _luminance(fg_hex)
    l_bg = _luminance(bg_hex)
    lighter = max(l_fg, l_bg)
    darker  = min(l_fg, l_bg)
    return (lighter + 0.05) / (darker + 0.05)


# ── T1. CSS source carries the post-N.2 value ───────────────────
def test_n2_index_css_declares_muted_5e5f64():
    src = INDEX_CSS.read_text(encoding="utf-8")
    # The token literal — case-insensitive on the hex (it's commonly
    # written either way) but the spaces are exact.
    pat = re.compile(r"--muted\s*:\s*#5e5f64\s*;", re.IGNORECASE)
    assert pat.search(src), (
        "`--muted: #5e5f64;` not found in index.css. Phase N.2 "
        "regression — the muted-text contrast bump was reverted."
    )
    # The legacy `--muted: var(--graphite);` alias must be gone.
    legacy = re.compile(r"--muted\s*:\s*var\(\s*--graphite\s*\)\s*;")
    assert not legacy.search(src), (
        "Legacy `--muted: var(--graphite);` alias still present — "
        "Phase N.2 broke that alias to raise contrast above WCAG-AA."
    )


# ── T2. Deterministic contrast math meets WCAG-AA ────────────────
def test_n2_muted_meets_wcag_aa_contrast_against_paper():
    """Pure-Python WCAG-AA contrast check. Independent of browser
    runtime; runs every CI pass. The numeric result is also
    documented in the N.2 ledger row so anyone reading the codebase
    sees the math without re-running this test."""
    ratio = _contrast_ratio("#5e5f64", "#f2efe8")
    # WCAG-AA normal text: >= 4.5. Our calc lands at ~5.57.
    assert ratio >= 4.5, (
        f"contrast(#5e5f64 on #f2efe8) = {ratio:.3f} — fails WCAG-AA "
        f"normal-text threshold of 4.5. Choose a darker --muted value."
    )
    # Sanity check the OLD value would have failed (proves the fix is
    # meaningful, not coincidental).
    old_ratio = _contrast_ratio("#6F7177", "#f2efe8")
    assert old_ratio < 4.5, (
        f"Pre-N.2 contrast was {old_ratio:.3f} — expected < 4.5. "
        "If the source palette changed, recompute and update the "
        "lesson in the ledger."
    )


# ── T3. Sanity — the new value is actually darker than the old ──
def test_n2_new_muted_is_darker_than_old():
    new_lum = _luminance("#5e5f64")
    old_lum = _luminance("#6F7177")
    assert new_lum < old_lum, (
        f"Post-N.2 luminance {new_lum:.4f} is NOT darker than pre-N.2 "
        f"{old_lum:.4f}. Contrast against a light bg requires darker fg."
    )
