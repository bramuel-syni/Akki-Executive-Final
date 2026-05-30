"""Sprint M.1 (2026-02 fork-resume v3 dispatch 9) — Hero rewrite lockdown.

User picked Option B + red-lined the sub-hero. Voice-clean. Locked verbatim.

Hero:     "Akki refuses to invent."
Sub-hero: "Board papers. Briefings. Reports. Every claim cited. Every bias
           is named. Decisions stay yours. Your data never leaves your
           account."
CTAs:     "See the work"  (primary) → #evidence
          "Join the cohort" (secondary) → /cohort
Image:    /marketing/hero_executive_reading.png — alt "An executive
           reading a board pack." — width 1408 height 768 — loading eager.
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"
HOME_JSX = FE / "website" / "pages" / "Home.jsx"
COPY_JS = FE / "website" / "copy" / "index.js"


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── Verbatim copy locks ────────────────────────────────────────────────


def test_m1_hero_headline_locked_verbatim():
    src = _r(COPY_JS)
    assert 'headline: "Akki refuses to invent."' in src


def test_m1_hero_lift_word_locked():
    src = _r(COPY_JS)
    # Lift word is `refuses` per dispatch — the rendering splits at the
    # lift token so the oxblood emphasis lands mid-sentence.
    assert 'lift: "refuses"' in src


def test_m1_hero_sub_hero_locked_verbatim():
    src = _r(COPY_JS)
    expected = (
        "Board papers. Briefings. Reports. Every claim cited. "
        "Every bias is named. Decisions stay yours. "
        "Your data never leaves your account."
    )
    assert f'dek: "{expected}"' in src


def test_m1_hero_primary_cta_locked():
    src = _r(COPY_JS)
    assert 'primaryCta: { label: "See the work",   href: "#evidence" }' in src


def test_m1_hero_secondary_cta_locked():
    src = _r(COPY_JS)
    assert 'tertiary:   { label: "Join the cohort", href: "/cohort"   }' in src


# ── Previously-deployed strings absent ─────────────────────────────────


def test_m1_previous_hero_strings_removed_from_copy():
    src = _r(COPY_JS)
    # Old HERO export removed.
    assert 'headline: "Safe AI for executive work.' not in src
    assert 'lift: "Safe"' not in src
    assert "For executives who want to use AI fully" not in src
    assert "Join the founding cohort" not in src
    assert '"See how it works"' not in src


def test_m1_previous_hero_strings_removed_from_jsx():
    src = _r(HOME_JSX)
    # Old hero image import + alt text gone.
    assert 'import heroImg' not in src
    assert "A senior executive at a desk" not in src
    assert "An executive at a desk, reading paper materials in a quiet study." not in src
    # The previous WebsiteShell title is gone.
    assert 'title="Akki — Safe AI for executive work"' not in src


# ── Hero JSX shape locks ───────────────────────────────────────────────


def test_m1_hero_picture_with_webp_source_first():
    src = _r(HOME_JSX)
    # <picture> with WebP source preceding the <img> fallback.
    assert "<picture>" in src
    assert '<source srcSet="/marketing/hero_executive_reading.webp" type="image/webp" />' in src
    assert 'src="/marketing/hero_executive_reading.png"' in src


def test_m1_hero_img_attributes_locked():
    src = _r(HOME_JSX)
    assert 'alt="An executive reading a board pack."' in src
    assert 'width="1408"' in src
    assert 'height="768"' in src
    assert 'loading="eager"' in src
    assert 'fetchPriority="high"' in src


def test_m1_hero_headline_renderer_splits_at_lift():
    src = _r(HOME_JSX)
    # The HeroHeadline component must split at the lift token so the
    # oxblood emphasis lands at the natural location in the headline,
    # not at the start (the previous renderer placed `<em>` first).
    assert "function HeroHeadline" in src
    assert "headline.split(lift)" in src
    # The old leading-em pattern is gone.
    assert '<em className="lift">{HERO.lift}</em>{HERO.headline.replace' not in src


def test_m1_hero_dek_carries_testid():
    src = _r(HOME_JSX)
    assert 'data-testid="home-hero-dek"' in src


# ── WebsiteShell hero re-write ────────────────────────────────────────


def test_m1_websiteshell_description_matches_sub_hero():
    src = _r(HOME_JSX)
    # The page description (used for SEO + social) mirrors the dek so
    # the voice is single-sourced.
    assert (
        'description="Board papers. Briefings. Reports. Every claim '
        'cited. Every bias is named. Decisions stay yours. Your data '
        'never leaves your account."' in src
    )


def test_m1_websiteshell_og_image_points_at_hero():
    src = _r(HOME_JSX)
    assert 'ogImage="/marketing/hero_executive_reading.png"' in src


# ── Voice-lint full-surface check ─────────────────────────────────────


def test_m1_full_surface_voice_lint_clean():
    """Voice-lint must remain green over the entire marketing surface
    after the rewrite. The M.1b CI gate enforces the same invariant
    on every PR; this test is the local pre-commit equivalent."""
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan, DEFAULT_TARGETS
    hits = scan(DEFAULT_TARGETS)
    rendered = [(str(p.relative_to(REPO)), ln, w) for p, ln, w, _ in hits]
    assert not hits, f"voice-lint must be clean post-M.1; got: {rendered}"
