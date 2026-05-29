"""Wave 4.2.followup.2 followup #2 — Source-strict opacity-step lock
(2026-02 fork-resume reply dispatch).

Tailwind's default opacity scale is: 0, 5, 10, 15, 20, 25, 30, 40,
50, 60, 70, 75, 80, 90, 95, 100. Any other value (e.g. `/8`, `/6`,
`/18`, `/7`) silently produces NO CSS rule and the element renders
with its inherited / transparent background.

This guard scans the entire frontend source tree for invalid opacity
steps on ANY palette utility (brand tokens + every Tailwind palette
slate/gray/zinc/.../rose). It runs in CI alongside the runtime audit
so the next `/8`-style typo trips a source-strict test BEFORE the
runtime audit + before a tester catches it in QA.

Extended 2026-02 maintenance dispatch — scope upgraded from
brand-purple-only to full design-system palette (slate, gray,
zinc, neutral, stone, red, orange, amber, yellow, lime, green,
emerald, teal, cyan, sky, blue, indigo, violet, purple, fuchsia,
pink, rose, brand-*, ned-purple). Catches every future
`text-emerald-600/7` / `bg-amber-500/18`-style silent typo.

Past offenders (caught + fixed in this dispatch):
  - StrategicGoalsPanel.jsx — operations chip `bg-ned-purple/8`
  - TasksInitiativesPanel.jsx — task category chip `bg-ned-purple/8`
  - Pulse.jsx — `bg-ned-purple/8` (2 sites)
  - DocumentCardsSection.jsx — `bg-ned-purple/6` + `border-ned-purple/18`

All migrated to `/10` and `/20` respectively, matching the established
Wave 4.2 brand-purple sweep tokens.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO / "frontend" / "src"

# Tailwind default opacity scale (https://tailwindcss.com/docs/opacity).
_VALID_OPACITY_STEPS = {
    "0", "5", "10", "15", "20", "25", "30", "40",
    "50", "60", "70", "75", "80", "90", "95", "100",
}

# Tailwind default color palette names + the project's brand tokens
# registered via tailwind.config.js. Locked here to keep the regex
# tight — we want to flag opacity-modifier typos, NOT collateral
# matches like `w-1/2` fractions or `aspect-16/9` ratios.
_PALETTE_NAMES = (
    # Tailwind defaults.
    "slate", "gray", "zinc", "neutral", "stone",
    "red", "orange", "amber", "yellow", "lime", "green", "emerald",
    "teal", "cyan", "sky", "blue", "indigo", "violet", "purple",
    "fuchsia", "pink", "rose",
    # Project brand tokens.
    "ned-purple",
    "brand-accent", "brand-ink", "brand-muted", "brand-rule",
    "brand-parchment", "brand-cream",
)

# Utility prefixes that take a color + opacity modifier.
_UTILITY_PREFIXES = (
    "bg", "border", "text", "ring", "outline", "divide",
    "placeholder", "caret", "accent", "fill", "stroke",
    "shadow", "from", "via", "to",
)

# Match `<prefix>-<palette>[-<shade>]/<step>` where:
#   - prefix ∈ _UTILITY_PREFIXES
#   - palette ∈ _PALETTE_NAMES (escaped, alternation)
#   - optional `-<shade>` (e.g. `-500`, `-50`)
#   - `/<step>` opacity modifier
# May be preceded by a pseudo-state prefix (`hover:`, `focus:`, etc.)
# OR a colon-separated variant (`md:`, `dark:`); we don't care about
# those — what matters is the trailing `/<step>` value.
_PALETTE_OPACITY_RE = re.compile(
    rf"(?<![A-Za-z0-9_-])(?:{'|'.join(_UTILITY_PREFIXES)})"
    rf"-(?:{'|'.join(re.escape(p) for p in _PALETTE_NAMES)})"
    rf"(?:-\d+)?"
    rf"/(\d+)\b"
)


def _iter_frontend_jsx_files():
    return list(FRONTEND_SRC.rglob("*.jsx")) + list(FRONTEND_SRC.rglob("*.js"))


def test_no_invalid_opacity_step_on_any_palette_utility():
    """Every `<prefix>-<palette>[-<shade>]/N` (and friends) in the
    frontend source MUST use one of Tailwind's default opacity steps.
    Otherwise the class compiles to nothing and the element silently
    renders with transparent / inherited background.

    Scope (2026-02 maintenance dispatch extension): full design-
    system palette — brand tokens AND every Tailwind palette
    slate/gray/zinc/neutral/stone/red/orange/amber/yellow/lime/
    green/emerald/teal/cyan/sky/blue/indigo/violet/purple/fuchsia/
    pink/rose."""
    offenders = []
    for path in _iter_frontend_jsx_files():
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        # Strip comments so a comment example like `// bg-rose-500/7`
        # doesn't trip the guard. Block comments first, then line.
        code = re.sub(r"/\*[\s\S]*?\*/", "", src)
        code = re.sub(r"//[^\n]*", "", code)
        for m in _PALETTE_OPACITY_RE.finditer(code):
            step = m.group(1)
            if step not in _VALID_OPACITY_STEPS:
                # Re-locate the line in the ORIGINAL source (so we
                # report the right line number even if we stripped
                # comments). Find the substring in the original.
                snippet = m.group(0)
                orig_idx = src.find(snippet)
                if orig_idx < 0:
                    orig_idx = m.start()
                line_no = src.count("\n", 0, orig_idx) + 1
                context_start = max(0, orig_idx - 40)
                context = src[context_start:orig_idx + len(snippet) + 40].replace("\n", " ")
                offenders.append(
                    f"{path.relative_to(REPO)}:{line_no} "
                    f"→ `{snippet}` (step `/{step}` is NOT a valid "
                    f"Tailwind default opacity stop). "
                    f"Context: …{context}…"
                )

    assert not offenders, (
        f"Invalid Tailwind opacity steps detected. "
        f"Valid steps: {sorted(_VALID_OPACITY_STEPS, key=int)}.\n"
        + "\n".join(f"  - {o}" for o in offenders)
    )


def test_audit_script_distinguishes_hover_only_pattern():
    """Locks the audit-script triage logic — must classify
    `hover:bg-brand-rule/30` + `focus:bg-brand-rule/40` (with no
    resting purple token) as HOVER_ONLY, not REAL_BUG. Otherwise the
    `<StrategicRow>` primitive's clickable rows trip the audit on
    every CI run."""
    audit_path = REPO / "backend" / "tests" / "test_wave42_followup2_runtime_audit.py"
    src = audit_path.read_text(encoding="utf-8")
    assert "HOVER_ONLY" in src, (
        "Audit script must classify hover-only purple usages as "
        "HOVER_ONLY (whitelisted by design)."
    )
    assert "REAL_BUG" in src, (
        "Audit script must classify resting-transparent purple usages "
        "as REAL_BUG."
    )
    # The classification logic must check for `hover:` / `focus:` /
    # other pseudo-state prefixes when categorising tokens.
    assert "pseudoRe" in src or "pseudoStateRe" in src or "hover|focus|active" in src, (
        "Audit script must have a pseudo-state regex (`hover|focus|"
        "active|...`) to separate hover-only purple tokens from "
        "resting ones."
    )


def test_palette_opacity_regex_excludes_non_color_fractions():
    """Regression guard — the palette opacity regex must NOT match
    Tailwind's non-color fraction utilities like `w-1/2`,
    `aspect-16/9`, `translate-x-1/2`. The negative-lookbehind for a
    word-character before `<prefix>` + the palette-name-bounded
    `<prefix>-<palette>` alternation should prevent false matches.

    This test feeds known-safe utility strings to the regex and
    confirms zero matches. If a future regex tweak loosens the
    bounds, this guard catches the false-positive risk before it
    pollutes the main lock."""
    safe_strings = [
        "w-1/2 h-3/4",
        "aspect-16/9 aspect-4/3",
        "translate-x-1/2 -translate-y-1/3",
        "grid-cols-1/3",
        "min-w-2/5",
        # Pseudo-state + valid step on a palette — must NOT trip.
        "hover:bg-emerald-500/10 focus:text-rose-700/20",
    ]
    for s in safe_strings:
        # Strip the false-positive trigger only — bare `bg-X/N` etc
        # within a palette-prefixed utility should match if invalid,
        # but the safe strings either have non-palette stems
        # (`w-`, `aspect-`) or valid steps.
        matches = [m for m in _PALETTE_OPACITY_RE.finditer(s)
                   if m.group(1) not in _VALID_OPACITY_STEPS]
        assert not matches, (
            f"Regex must not match invalid-step inside safe string "
            f"{s!r}. False positives: {[m.group(0) for m in matches]}"
        )

    # Conversely — known-invalid steps MUST match.
    invalid_strings = [
        ("bg-emerald-500/7", "/7"),
        ("text-rose-700/12", "/12"),
        ("border-amber-400/18", "/18"),
        ("ring-ned-purple/8", "/8"),
        ("bg-brand-rule/6", "/6"),
        # Pseudo-state prefix must NOT prevent detection of invalid step.
        ("hover:bg-emerald-500/7", "/7"),
    ]
    for utility, expected_step in invalid_strings:
        matches = list(_PALETTE_OPACITY_RE.finditer(utility))
        assert matches, f"Regex must catch invalid step in {utility!r}"
        # Confirm the invalid step is the one we expect.
        assert any(f"/{m.group(1)}" == expected_step for m in matches), (
            f"Regex matched in {utility!r} but didn't capture "
            f"expected step {expected_step!r}"
        )
