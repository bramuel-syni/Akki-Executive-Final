"""Sprint M.1a (2026-02 fork-resume v3 dispatch 5) — latent-vocab cleanup
lockdown.

Eighteen banned-vocab violations across the marketing/website surface
were cleared with editorial recasts. The voice can't drift back. Each
fix below locks (a) the banned phrase is ABSENT and (b) the replacement
phrase is PRESENT verbatim.

The voice lint scanner has a separate test asserting the whole surface
is clean. This file is the per-fix audit trail.
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"


def _r(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


# ── dashboard recast ───────────────────────────────────────────────────


def test_m1a_sharpest_use_case_recast():
    s = _r("components/marketing/SharpestUseCase.jsx")
    assert "KPI dashboard" not in s
    assert "A KPI tracker three cycles behind." in s


# ── senior recasts (14) ────────────────────────────────────────────────


def test_m1a_website_footer_recast():
    s = _r("website/WebsiteFooter.jsx")
    assert "senior people running serious operations" not in s
    assert "A workspace for executives running serious operations" in s


def test_m1a_why_akki_title_recast():
    s = _r("website/pages/WhyAkki.jsx")
    assert "Senior work has structure" not in s
    assert "Why Akki — Executive work has structure" in s


def test_m1a_why_akki_description_recast():
    s = _r("website/pages/WhyAkki.jsx")
    assert "Senior work is neither." not in s
    assert "Executive work is neither." in s


def test_m1a_what_akki_does_description_recast():
    s = _r("website/pages/WhatAkkiDoes.jsx")
    assert "A workspace for senior people." not in s
    assert "A workspace for executives. Solva, Akki Chat" in s


def test_m1a_what_akki_does_h2_recast():
    s = _r("website/pages/WhatAkkiDoes.jsx")
    assert "moment in senior work" not in s
    assert "Each surface answers a recurring moment in executive work." in s


def test_m1a_for_exco_description_recast():
    s = _r("website/pages/ForExco.jsx")
    assert "senior leadership team" not in s
    assert (
        "A workspace for the executive committee preparing what the board will read."
        in s
    )


def test_m1a_pricing_inverted_cta_recast():
    s = _r("website/pages/Pricing.jsx")
    assert "Twenty senior people will use Akki" not in s
    assert "Twenty executives will use Akki first." in s


def test_m1a_methodology_prose_recast():
    s = _r("website/pages/Methodology.jsx")
    assert "the question senior people actually ask" not in s
    assert "the question executives actually ask" in s


def test_m1a_methodology_solva_h2_recast():
    s = _r("website/pages/Methodology.jsx")
    assert "not how senior people reason" not in s
    assert "We invented Solva because chat is not how executives reason." in s


def test_m1a_for_organisations_headline_recast():
    s = _r("website/pages/ForOrganisations.jsx")
    assert "Roll Akki out to your senior team" not in s
    assert "Roll Akki out to your executive team." in s


def test_m1a_home_description_recast():
    # SUPERSEDED by M.1 (dispatch 9): the WebsiteShell description now
    # mirrors the red-lined hero sub-hero text. The M.1a recast string
    # is intentionally absent. M.1 lockdown test
    # `test_m1_websiteshell_description_matches_sub_hero` owns the new value.
    s = _r("website/pages/Home.jsx")
    assert "A workspace for senior people who want to use AI fully" not in s


def test_m1a_home_hero_alt_recast():
    # SUPERSEDED by M.1 (dispatch 9): the hero image is now
    # /marketing/hero_executive_reading.png with alt "An executive
    # reading a board pack." — M.1 lockdown test
    # `test_m1_hero_img_attributes_locked` owns the new value.
    s = _r("website/pages/Home.jsx")
    assert "A senior executive at a desk" not in s


def test_m1a_home_audiences_h2_recast():
    s = _r("website/pages/Home.jsx")
    assert "Senior work, three shapes." not in s
    assert "Executive work, three shapes." in s


def test_m1a_home_triptych_alt_recast():
    s = _r("website/pages/Home.jsx")
    assert "Three senior readers in private study" not in s
    assert (
        'alt="Three executives reading in private study and library settings."'
        in s
    )


def test_m1a_solva_modes_h2_recast():
    s = _r("website/pages/product/Solva.jsx")
    assert "moment in senior thinking" not in s
    assert "Each mode is a faithful answer to a moment in executive thinking." in s


# ── end-to-end recasts (2) ─────────────────────────────────────────────


def test_m1a_methodology_jsdoc_comment_recast():
    s = _r("website/pages/Methodology.jsx")
    assert "long-form, end-to-end reading" not in s
    assert "long-form, continuous reading" in s


def test_m1a_methodology_audit_chain_claim_recast():
    s = _r("website/pages/Methodology.jsx")
    # Replaced the generic "end-to-end" claim with the specific provable claim.
    assert "prove the chain\n          end-to-end" not in s
    assert "prove the chain end-to-end without trusting" not in s
    assert "prove the chain\n          from genesis to current row" in s


# ── full-surface lock ──────────────────────────────────────────────────


def test_m1a_full_surface_voice_lint_clean():
    """The full marketing surface passes the voice lint scanner with
    no hits. Any new banned vocab introduced anywhere will fail this."""
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan, DEFAULT_TARGETS
    hits = scan(DEFAULT_TARGETS)
    rendered = [
        (str(p.relative_to(REPO)), ln, w) for p, ln, w, _snip in hits
    ]
    assert not hits, f"voice-lint must be clean across the marketing surface; got: {rendered}"


# ── copy/index.js & copy/legal.js recasts (additional surface discovered
#    after the .js-extension on the scanner — same dispatch, batched here) ──


def _c(name: str) -> str:
    return (FE / "website" / "copy" / name).read_text(encoding="utf-8")


def test_m1a_copy_jsdoc_no_enumerated_ban_list():
    """The original JSDoc literally enumerated banned words ('empower /
    unlock / leverage / ...') which made the file fail its own lint.
    Recast to a non-enumerating description that points at the brief."""
    s = _c("index.js")
    assert "No \"empower / unlock" not in s
    assert "docs/WEBSITE_BRIEF_V3.md §1.3" in s


def test_m1a_copy_hero_kicker_recast():
    s = _c("index.js")
    assert 'FOR SENIOR PEOPLE' not in s
    assert 'kicker: "FOR EXECUTIVES"' in s


def test_m1a_copy_hero_dek_recast():
    # SUPERSEDED by M.1 (dispatch 9): the HERO.dek is now the red-lined
    # sub-hero text. The M.1a recast string is intentionally absent.
    # M.1 lockdown test `test_m1_hero_sub_hero_locked_verbatim` owns
    # the new value.
    s = _c("index.js")
    assert "For senior people who want to use AI fully" not in s


def test_m1a_copy_tier2_dek_recast():
    s = _c("index.js")
    assert "Senior decisions get made together" not in s
    assert (
        'dek: "Executive decisions get made together, over weeks, across boards. '
        "The workspace mirrors that.\"" in s
    )


def test_m1a_copy_audiences_exco_title_recast():
    s = _c("index.js")
    assert '"The senior leadership team."' not in s
    assert 'title: "The executive committee."' in s


def test_m1a_copy_cohort_teaser_body_recast():
    s = _c("index.js")
    assert "senior leadership-team members" not in s
    assert "committee-level operators to use it first" in s


def test_m1a_copy_why_block_recast():
    s = _c("index.js")
    assert '"Senior work has structure.' not in s
    assert "Senior work is neither" not in s
    assert "Senior work is private work" not in s
    assert 'headline: "Executive work has structure."' in s
    assert "Executive work is neither" in s
    assert 'title: "Executive work is private work."' in s


def test_m1a_copy_what_dek_recast():
    s = _c("index.js")
    assert "moment that recurs in senior work" not in s
    assert "moment that recurs in executive work" in s


def test_m1a_copy_for_executives_image_alt_recast():
    s = _c("index.js")
    assert "A senior executive annotating a printed report" not in s
    assert (
        'image_alt: "An executive annotating a printed report at a quiet desk."'
        in s
    )


def test_m1a_copy_for_exco_headline_recast():
    s = _c("index.js")
    assert "For the senior leadership team preparing what the board will read." not in s
    assert (
        'headline: "For the executive committee preparing what the board will read."'
        in s
    )


def test_m1a_copy_cohort_headline_recast():
    s = _c("index.js")
    assert "twenty senior people" not in s
    assert 'headline: "Used first by roughly twenty executives."' in s


def test_m1a_copy_about_recast():
    s = _c("index.js")
    assert "senior leadership teams preparing what the board" not in s
    assert "Senior work is neither" not in s
    assert "committee-level operators preparing what the board will read" in s
    assert "Executive work is neither" in s


def test_m1a_copy_contact_recast():
    s = _c("index.js")
    assert "a senior leadership-team member" not in s
    assert "applying as an executive, an NED, or a committee-level operator" in s


def test_m1a_legal_privacy_recast():
    s = _c("legal.js")
    assert "private working environment for senior people" not in s
    # PRIVACY block
    assert (
        'p: "Akki Limited (\\"Akki\\", \\"we\\") provides a private working '
        'environment for executives to use AI.' in s
    )


def test_m1a_legal_terms_recast():
    s = _c("legal.js")
    assert "What we provide\", p: \"A private working environment for senior people" not in s
    assert (
        '"What we provide", p: "A private working environment for executives to '
        'use AI.' in s
    )
