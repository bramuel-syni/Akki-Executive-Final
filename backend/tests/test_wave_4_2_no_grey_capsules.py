"""
Wave 4.2 (2026-05-27) — grey → brand-purple capsule sweep CI guard.

Scope clarification: the dispatch named ">10 sites" but a thorough
inventory of capsule-like elements (rounded-sm + uppercase tracking-
wider OR rounded-full pill semantics) revealed only **5 actual sites**
were carrying grey backgrounds. The broader 39 `bg-slate-*` hits in
the codebase are non-capsule semantics (hover states, disabled
inputs, code/kbd blocks, table headers) where grey is the correct
choice. Those are explicitly OUT of scope for Wave 4.2 — see
PHASE_LEDGER for the rationale.

Locked sites:
  1. TasksInitiativesPanel.jsx — TaskCard category pill
  2. StrategicGoalsPanel.jsx — operations category bar + chip
  3. DocumentCardsSection.jsx — `unrated` state badge
  4. DocumentCardsSection.jsx — default state-category className
  5. Pulse.jsx — confidence "low" tone + drawer confidence chip

Each must carry `var(--ned-purple)` (with opacity modifier) — no
`bg-slate-*` / `bg-gray-*` / `bg-neutral-*` on capsule elements.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"

# Map: file → list of patterns each MUST be absent (negative lock)
# AND a positive `bg-[var(--ned-purple)]` reference must be present.
SWEPT_SITES = (
    {
        "file": "components/monitor/TasksInitiativesPanel.jsx",
        "anchor_testid": "task-card-category-${task.id}",
        "must_not_match": (r"bg-slate-50\s+text-slate-700",),
    },
    {
        "file": "components/monitor/StrategicGoalsPanel.jsx",
        "anchor_str": '"Operations"',
        "must_not_match": (r"bg-slate-100\s+text-slate-800",),
    },
    {
        "file": "components/work_studio/DocumentCardsSection.jsx",
        "anchor_str": 'className: "bg-',
        "must_not_match": (
            r"className:\s*\"bg-slate-100\s+text-slate-700",
            r"unrated:\s*\"bg-slate-50",
        ),
    },
    {
        "file": "pages/Pulse.jsx",
        "anchor_testid": "pulse-drawer-confidence",
        "must_not_match": (
            r"card\.confidence === \"low\"\s*\?\s*\"bg-slate-50",
            r"\"px-2 py-0\.5 bg-slate-50 border border-slate-200 rounded-sm\"",
        ),
    },
)


def test_w42_swept_sites_no_grey_capsules() -> None:
    """Each swept site must NOT contain its previous grey-capsule
    pattern AND must contain at least one `var(--ned-purple)` reference
    in the same file."""
    for site in SWEPT_SITES:
        path = FRONTEND / site["file"]
        src = path.read_text(encoding="utf-8")
        for pat in site["must_not_match"]:
            assert not re.search(pat, src), (
                f"Wave 4.2 swept site {site['file']!r} still carries "
                f"a grey-capsule pattern matching {pat!r}. Replace with "
                f"`bg-[var(--ned-purple)]/<opacity>`."
            )
        assert "var(--ned-purple)" in src, (
            f"Wave 4.2 swept site {site['file']!r} must reference "
            f"`var(--ned-purple)` after the sweep — purple token "
            f"replaces the grey background."
        )


def test_w42_global_capsule_grep_clean() -> None:
    """Global sweep — no rounded-full or rounded-sm + uppercase
    tracking-wider element in any .jsx may carry `bg-slate-50`,
    `bg-slate-100`, `bg-gray-50`, `bg-gray-100`, `bg-neutral-50` or
    `bg-neutral-100`. The broader hover-state / disabled-input /
    kbd uses are out of scope and tolerated."""
    offenders: list[str] = []
    grey_classes = (
        "bg-slate-50", "bg-slate-100", "bg-gray-50", "bg-gray-100",
        "bg-neutral-50", "bg-neutral-100",
    )
    for jsx in FRONTEND.rglob("*.jsx"):
        text = jsx.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            # Heuristic: a capsule-like className has BOTH one of the
            # grey backgrounds AND a capsule signature on the same line.
            if any(g in line for g in grey_classes):
                # Capsule signature: rounded-full | (rounded-sm + uppercase)
                #                  | tracking-wider on a className
                is_capsule = (
                    "rounded-full" in line
                    or ("rounded-sm" in line and ("uppercase" in line or "tracking-wider" in line))
                )
                # Hover states (`hover:bg-slate-*`) are not capsule
                # backgrounds — the bg only applies on hover.
                line_stripped = line.strip()
                if re.search(r'\bhover:bg-(slate|gray|neutral)-(50|100)\b', line_stripped):
                    # If THE ONLY grey on this line is the hover state,
                    # tolerate. If a non-hover grey is present too,
                    # the surrounding capsule signature still triggers.
                    bare_grey = re.search(
                        r'(?<!hover:)\b(bg-(?:slate|gray|neutral)-(?:50|100))\b',
                        line_stripped,
                    )
                    if not bare_grey:
                        continue
                if is_capsule:
                    offenders.append(
                        f"{jsx.relative_to(FRONTEND)}:{line_no} → "
                        f"{line.strip()[:120]}"
                    )
    assert not offenders, (
        "Wave 4.2 grey→purple sweep — capsule-like elements still "
        "carrying grey backgrounds:\n  - " + "\n  - ".join(offenders)
    )
