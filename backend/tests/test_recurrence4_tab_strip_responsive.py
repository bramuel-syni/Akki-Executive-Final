"""Work Studio Briefing tab — RECURRENCE #4 fix (2026-05-27).

**Structural root cause (institutional memory to break the loop):**

Recurrence #3 locked these assertions for tab-row layout work:
  - briefing.parentElement === reports.parentElement
  - briefing.getBoundingClientRect().top === reports.getBoundingClientRect().top

Both assertions PASSED at the probe viewport (1280×900) — but the
container had `flex-wrap: wrap` in effect. At narrow viewports
(<=820 CSS px), the row WRAPPED while still sharing the same DOM
parent. Briefing landed on a 2nd visual line at 768px (iPad portrait
and common Samsung Tab S dimensions); at 600px (Samsung Tab A
portrait), THREE tabs (Decks/Reports/Briefing) wrapped to the 2nd
line. Single-viewport probes were INSUFFICIENT and constituted a
false-green.

**Fix (Option A — minimum-risk responsive pattern):**
  - Container: `flex-wrap` → `overflow-x-auto` + `no-scrollbar`
  - Buttons: added `flex-shrink-0 whitespace-nowrap` so tab labels
    don't shrink or wrap inside the button.

**New locked institutional rule for tab-row probes (Recurrence #4):**
Every future tab-row layout probe MUST run at minimum 3 viewports
(1280, 768, 600 CSS px) AND assert `unique(top px) === 1` at EACH.
Single-viewport probes are a false-green pattern.

Locks:
  R4.a — Container className uses `overflow-x-auto` + NOT `flex-wrap`
  R4.b — Tab buttons carry `flex-shrink-0` + `whitespace-nowrap`
  R4.c — `no-scrollbar` utility exists in index.css
  R4.d — (Source-strict regression guard) the literal pattern
         `flex items-stretch gap-0 flex-wrap` must NEVER reappear
         in WorkStudio.jsx — the regression signature is that exact
         class string.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
WORK_STUDIO = REPO / "frontend" / "src" / "pages" / "WorkStudio.jsx"
INDEX_CSS = REPO / "frontend" / "src" / "index.css"


def _strip_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def test_R4_a_container_uses_overflow_x_auto_not_flex_wrap():
    """The tab strip container className must include
    `overflow-x-auto` AND NOT include `flex-wrap`. The class string
    is the smoking gun of the regression."""
    src = _strip_comments(WORK_STUDIO.read_text(encoding="utf-8"))
    # Find the tab strip container — it's the inner div inside
    # `data-testid="work-studio-tabs"`.
    m = re.search(
        r'data-testid="work-studio-tabs"[^>]*>\s*<div\s+className="([^"]+)"',
        src,
    )
    assert m, "Tab strip container className not found"
    classes = m.group(1)
    assert "overflow-x-auto" in classes, (
        f"Container must use `overflow-x-auto`. Current classes: {classes!r}"
    )
    assert "flex-wrap" not in classes, (
        f"Container must NOT use `flex-wrap` (Recurrence #4 root cause). "
        f"Current classes: {classes!r}"
    )


def test_R4_b_tab_buttons_have_flex_shrink_0_and_whitespace_nowrap():
    """Each tab button must carry `flex-shrink-0` and
    `whitespace-nowrap` so the labels don't compress or wrap when the
    container scrolls."""
    src = _strip_comments(WORK_STUDIO.read_text(encoding="utf-8"))
    # Find the button className inside the KIND_TABS.map render
    # (the active/inactive ternary).
    m = re.search(
        r"KIND_TABS\.map[\s\S]*?<button[\s\S]*?className=\{`([^`]+)`",
        src,
    )
    assert m, "KIND_TABS button className not found"
    button_class_template = m.group(1)
    assert "flex-shrink-0" in button_class_template, (
        f"Tab button must carry `flex-shrink-0`. Found: {button_class_template!r}"
    )
    assert "whitespace-nowrap" in button_class_template, (
        f"Tab button must carry `whitespace-nowrap`. Found: {button_class_template!r}"
    )


def test_R4_c_no_scrollbar_utility_exists():
    """The `no-scrollbar` utility class must be defined in index.css."""
    css = INDEX_CSS.read_text(encoding="utf-8")
    assert ".no-scrollbar" in css, (
        "no-scrollbar utility class must be defined in index.css"
    )
    assert "scrollbar-width: none" in css, (
        "no-scrollbar must set scrollbar-width: none (Firefox)"
    )
    assert "::-webkit-scrollbar { display: none" in css or \
           "::-webkit-scrollbar {display:none" in css or \
           "::-webkit-scrollbar { display:none" in css, (
        "no-scrollbar must hide ::-webkit-scrollbar (Chromium/Safari)"
    )


def test_R4_d_legacy_flex_wrap_signature_never_reappears():
    """Strict regression guard: the exact legacy class string that
    produced Recurrence #4 must NEVER reappear in source. If a future
    agent rewrites the tab strip, this test catches accidental
    reintroduction of `flex-wrap` on the container."""
    src = WORK_STUDIO.read_text(encoding="utf-8")
    forbidden = "flex items-stretch gap-0 flex-wrap"
    assert forbidden not in src, (
        f"Recurrence #4 regression: forbidden class string {forbidden!r} "
        f"reappeared in WorkStudio.jsx. The tab container must use "
        f"`overflow-x-auto` instead of `flex-wrap`."
    )


def test_R4_documentation_locked_multi_viewport_probe_rule():
    """The new institutional rule must be captured in the PHASE_LEDGER
    NOTES line for Recurrence #4. This test reads the ledger and
    asserts the rule's verbatim presence — future agents can't quietly
    drop it."""
    ledger = (REPO / "memory" / "sprints" / "PHASE_LEDGER.md").read_text(encoding="utf-8")
    # Look for the multi-viewport rule phrase
    assert "multi-viewport" in ledger.lower() or "3 viewports" in ledger.lower(), (
        "PHASE_LEDGER must capture the multi-viewport-probe institutional rule "
        "(Recurrence #4 lesson)"
    )
    # The 3 reference viewports (the new locked probe set)
    for vp in ("1280", "768", "600"):
        assert vp in ledger, (
            f"PHASE_LEDGER must reference the {vp}px probe viewport"
        )
