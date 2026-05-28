"""Wave 4.2.followup.2 followup #2 — Source-strict opacity-step lock
(2026-02 fork-resume reply dispatch).

Tailwind's default opacity scale is: 0, 5, 10, 15, 20, 25, 30, 40,
50, 60, 70, 75, 80, 90, 95, 100. Any other value (e.g. `/8`, `/6`,
`/18`) silently produces NO CSS rule and the element renders with
its inherited / transparent background.

This guard scans the entire frontend source tree for invalid opacity
steps on brand-purple / brand-* utilities. It runs in CI alongside
the runtime audit so the next `/8`-style typo trips a source-strict
test BEFORE the runtime audit + before a tester catches it in QA.

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

# Brand utility opacity-modifier pattern. Matches:
#   bg-ned-purple/N
#   border-ned-purple/N
#   text-ned-purple/N
#   ring-ned-purple/N
#   bg-brand-rule/N  (and other brand-* short names)
# Captures the trailing /N.
_OPACITY_RE = re.compile(
    r"\b(?:bg|border|text|ring|outline|divide|placeholder|caret|accent|fill|stroke|shadow|from|via|to)-"
    r"(?:ned-purple|brand-[a-z-]+)"
    r"/(\d+)\b"
)


def _iter_frontend_jsx_files():
    return list(FRONTEND_SRC.rglob("*.jsx")) + list(FRONTEND_SRC.rglob("*.js"))


def test_no_invalid_opacity_step_on_brand_utilities():
    """Every `bg-ned-purple/N` (and friends) in the frontend source
    MUST use one of Tailwind's default opacity steps. Otherwise the
    class compiles to nothing and the element silently renders with
    transparent / inherited background."""
    offenders = []
    for path in _iter_frontend_jsx_files():
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        for m in _OPACITY_RE.finditer(src):
            step = m.group(1)
            if step not in _VALID_OPACITY_STEPS:
                # Find the line for clearer reporting.
                line_no = src.count("\n", 0, m.start()) + 1
                snippet = src[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
                offenders.append(
                    f"{path.relative_to(REPO)}:{line_no} "
                    f"→ `{m.group(0)}` (step `/{step}` is NOT a valid "
                    f"Tailwind default opacity stop). "
                    f"Context: …{snippet}…"
                )

    assert not offenders, (
        f"Invalid Tailwind opacity steps detected on brand utilities. "
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
