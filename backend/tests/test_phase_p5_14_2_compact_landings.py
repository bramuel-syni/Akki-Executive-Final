"""P5.14.2 — hotfix lockdown.

Two regressions closed:
  1. ContextPortfolio `portfolio-landing` wrapper missing `relative` →
     absolute divider anchored to viewport, creating the doubled-line at
     lg breakpoint 1024 and rail-hug at 1280.
  2. SolvaLanding top-heavy (`padding: 120px ... 80px` + 64 px subtitle
     gap + thick trust banner) → 2 of 4 picker cards sat below the
     1280×800 fold.

Source-strict tests — they grep the live React source so a future agent
can't quietly re-introduce either regression without flipping these.
"""
from pathlib import Path


def _read(p: str) -> str:
    return Path(p).read_text(encoding="utf-8")


def test_portfolio_landing_wrapper_is_positioned():
    """`relative` MUST be present on the portfolio-landing wrapper so the
    absolute divider anchors to it (not the viewport)."""
    src = _read("/app/frontend/src/pages/ContextPortfolio.jsx")
    # The hotfix line — note the trailing `relative` token.
    assert (
        'flex gap-10 relative"\n        data-testid="portfolio-landing"' in src
        or 'flex gap-10 relative" data-testid="portfolio-landing"' in src
    ), "portfolio-landing wrapper must have Tailwind `relative` to anchor the divider"


def test_portfolio_vertical_divider_still_absolute():
    """Divider stays absolute-positioned at the locked offset; the only
    fix is the wrapper getting `relative`. Lock both sides so a future
    edit can't quietly move either."""
    src = _read("/app/frontend/src/pages/ContextPortfolio.jsx")
    assert 'data-testid="portfolio-vertical-divider"' in src
    assert "hidden lg:block absolute top-0 bottom-0 w-px" in src
    assert "calc(340px + 40px + 32px)" in src


def test_solva_trust_banner_is_slim():
    """Banner was thinned to bring the picker grid above the fold.
    Lock the slim classes; explicitly forbid the thick pre-fix combo."""
    src = _read("/app/frontend/src/pages/SolvaApp.jsx")
    assert "mb-3 mt-2" in src, "trust banner outer margin should be mt-2 mb-3 (P5.14.2)"
    assert "px-3 py-1.5 text-xs" in src, "trust banner inner padding should be slim (P5.14.2)"
    # Forbid the pre-fix thick combo.
    assert "mb-6 mt-4" not in src, "thick mt-4 mb-6 must not return"
    assert "px-4 py-2 text-sm" not in src, "thick px-4 py-2 text-sm must not return"


def test_solva_landing_top_padding_trimmed():
    """SolvaLanding top padding was 120 → 40 (compact-like-Home)."""
    src = _read("/app/frontend/src/components/solva/SolvaLanding.jsx")
    assert 'padding: "40px 24px 60px"' in src, (
        "SolvaLanding outer padding should be 40 top / 24 side / 60 bottom (P5.14.2)"
    )
    assert 'padding: "120px 24px 80px"' not in src, (
        "pre-fix 120px top padding must not return"
    )


def test_solva_landing_subtitle_gap_trimmed():
    """Subtitle margin was 64 → 28; h1 margin trimmed 12 → 8; h1 size 44 → 40."""
    src = _read("/app/frontend/src/components/solva/SolvaLanding.jsx")
    assert 'margin: "0 0 28px 0"' in src, "subtitle bottom margin must be 28 (P5.14.2)"
    assert 'margin: "0 0 64px 0"' not in src, "pre-fix 64 subtitle margin must not return"
    assert 'margin: "0 0 8px 0"' in src, "h1 bottom margin must be 8 (P5.14.2)"
    assert "fontSize: 40," in src, "h1 fontSize must be 40 (P5.14.2)"
    assert "fontSize: 44," not in src, "pre-fix h1 fontSize 44 must not return"


def test_p5_14_2_does_not_touch_solva_v1():
    """Sanity: this hotfix only touches FE files; no v1 reasoning code drift."""
    # The byte-identical guard is the canonical check; this is a
    # cheap belt-and-braces grep — `services/solva_v1/` stays empty
    # of any P5.14.2 marker.
    import subprocess
    proc = subprocess.run(
        ["grep", "-r", "P5.14.2", "/app/backend/services/solva/"],
        capture_output=True, text=True, check=False,
    )
    assert "P5.14.2" not in proc.stdout, (
        f"P5.14.2 marker leaked into Solva v1 reasoning code: {proc.stdout}"
    )
