"""Sprint M.5 (2026-02 fork-resume v3 dispatch 21) — Founding Cohort →
Early access language swap.

User directive: "Founding Cohort" framing reads as exclusivity inflation
against the senior-peer voice register. Swap to standard "early access"
plumbing language across the public website.

Surfaces touched:
  • Hero secondary CTA (HERO.tertiary) — "Join the cohort" → "Request access"
  • Homepage teaser (COHORT_TEASER) — headline / body / cta rewritten
  • /cohort page (WebsiteCohort) — title / description / submit / success
  • /cohort copy block (COHORT) — kicker / dek / body / holding
  • Pricing page (PRICING) — dek / footnote / table header / CTAs
  • Audience pricing lines (AUDIENCE_PAGES) — Executive + NED
  • Contact paths (CONTACT) — "For the founding cohort" → "For early access"
  • Methodology — "with the founding cohort." → "with the early-access group."
  • WebsiteFooter — "Founding cohort" link label → "Early access"
  • Inverted CTA — "THE FOUNDING COHORT" kicker → "EARLY ACCESS"
  • Backend cohort_applications router — applicant confirmation body +
    founder notify subject + body
  • /early-access route — now a Navigate alias to /cohort
  • Voice-lint — new BANNED_PHRASES regex flags `\\bfounding cohort\\b`
    and `\\bjoin the cohort\\b` (case-insensitive, word-boundary)

What does NOT change:
  • /cohort route URL (SEO)
  • POST /api/cohort/applications endpoint
  • Mongo collection name `cohort_applications`
  • Founder notify recipients
  • Form field shape
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"
COPY_JS = FE / "website" / "copy" / "index.js"
HOME_JSX = FE / "website" / "pages" / "Home.jsx"
COHORT_JSX = FE / "website" / "pages" / "Cohort.jsx"
PRICING_JSX = FE / "website" / "pages" / "Pricing.jsx"
METHODOLOGY_JSX = FE / "website" / "pages" / "Methodology.jsx"
FOOTER_JSX = FE / "website" / "WebsiteFooter.jsx"
FOR_EXCO_JSX = FE / "website" / "pages" / "ForExco.jsx"
FOR_NEDS_JSX = FE / "website" / "pages" / "ForNeds.jsx"
FOR_EXECUTIVES_JSX = FE / "website" / "pages" / "ForExecutives.jsx"
APP_JS = FE / "App.js"
ROUTER_PY = REPO / "backend" / "routers" / "cohort_applications.py"
LINT_SCRIPT = REPO / "scripts" / "lint_voice.py"


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── New strings present verbatim ──────────────────────────────────────


def test_m5_hero_secondary_cta_request_access():
    s = _r(COPY_JS)
    assert 'tertiary:   { label: "Request access", href: "/cohort"   }' in s


def test_m5_cohort_teaser_new_body_verbatim():
    s = _r(COPY_JS)
    idx = s.find("export const COHORT_TEASER = {")
    end = s.find("};", idx)
    block = s[idx:end]
    assert 'headline: "Akki is in early access."' in block
    assert 'body: "Akki is in early access. Request a place below."' in block
    assert 'cta: { label: "Request access", href: "/cohort" }' in block


def test_m5_inverted_cta_kicker_swapped():
    s = _r(COPY_JS)
    assert 'kicker: "EARLY ACCESS"' in s
    assert "THE FOUNDING COHORT" not in s


def test_m5_cohort_block_kicker_and_dek_swapped():
    s = _r(COPY_JS)
    idx = s.find("export const COHORT = {")
    end = s.find("};", idx)
    block = s[idx:end]
    assert 'kicker: "EARLY ACCESS"' in block
    assert "early-access group" in block
    assert "founding cohort" not in block.lower()


def test_m5_cohort_holding_line_verbatim():
    s = _r(COPY_JS)
    expected = (
        "Akki is in early access. Request a place. "
        "We will share the offer with you before launch."
    )
    assert f'holding: "{expected}"' in s


def test_m5_pricing_dek_and_footnote_swapped():
    s = _r(COPY_JS)
    idx = s.find("export const PRICING = {")
    end = s.find("};", idx)
    block = s[idx:end]
    assert "Early-access pricing is locked for two years." in block
    assert "Early-access pricing is admission-only." in block
    assert "founding cohort" not in block.lower()


def test_m5_audience_pricing_lines_swapped():
    s = _r(COPY_JS)
    # Both Executive + NED rows carry the new "Early-access price" wording.
    assert (
        'pricing_line: "Executive — $179 / month. '
        'Early-access price: $116 / month, locked for two years."'
    ) in s
    assert (
        'pricing_line: "NED — $129 / month. '
        'Early-access price: $84 / month, locked for two years."'
    ) in s


def test_m5_contact_path_label_swapped():
    s = _r(COPY_JS)
    assert 'label: "For early access"' in s
    # No "founding cohort" anywhere in the file.
    assert "founding cohort" not in s.lower()


def test_m5_methodology_prose_swapped():
    s = _r(METHODOLOGY_JSX)
    assert "early-access group" in s
    assert "founding cohort" not in s.lower()


def test_m5_footer_link_label_swapped():
    s = _r(FOOTER_JSX)
    assert '["Early access",        "/cohort"]' in s
    assert "Founding cohort" not in s


def test_m5_audience_primary_ctas_swapped():
    for path in (FOR_EXCO_JSX, FOR_NEDS_JSX, FOR_EXECUTIVES_JSX):
        src = _r(path)
        assert (
            'primaryCta={{ label: "Request access", href: "/cohort" }}'
            in src
        ), f"{path.name} must carry the new Request-access CTA"
        assert "founding cohort" not in src.lower(), (
            f"{path.name} must not carry founding-cohort language"
        )


def test_m5_pricing_page_table_header_and_cta_swapped():
    s = _r(PRICING_JSX)
    assert "Early access (2 yrs)" in s
    assert 'primaryCta={{ label: "Request access", href: "/cohort" }}' in s
    assert 'headline="Request early access."' in s
    assert 'ctaLabel="Request access"' in s
    assert "founding cohort" not in s.lower()


def test_m5_cohort_page_title_and_description_swapped():
    s = _r(COHORT_JSX)
    assert 'title="Early access — Akki"' in s
    assert (
        'description="Akki is in early access. Request a place to use it before launch."'
        in s
    )


def test_m5_cohort_page_submit_button_label_swapped():
    s = _r(COHORT_JSX)
    assert (
        '{status === "submitting" ? "Submitting…" : "Request access"}'
        in s
    )
    assert "Register interest" not in s


def test_m5_cohort_page_success_message_swapped():
    s = _r(COHORT_JSX)
    assert "We have your request on file." in s
    assert "share the\n            offer with you before launch." in s
    assert "members before launch" not in s


# ── Banned strings absent ─────────────────────────────────────────────


_PUBLIC_SURFACES = [
    COPY_JS, HOME_JSX, COHORT_JSX, PRICING_JSX, METHODOLOGY_JSX,
    FOOTER_JSX, FOR_EXCO_JSX, FOR_NEDS_JSX, FOR_EXECUTIVES_JSX,
]


def test_m5_banned_phrases_absent_from_public_website():
    """The two locked phrases (`founding cohort`, `join the cohort`)
    must be absent from every public-website surface, case-insensitive."""
    banned = ["founding cohort", "join the cohort"]
    for path in _PUBLIC_SURFACES:
        src = _r(path).lower()
        for needle in banned:
            assert needle not in src, (
                f"{path.name} still carries banned phrase {needle!r}"
            )


def test_m5_old_labels_absent_from_public_website():
    """Customer-facing CTA labels and headings that were retired must
    no longer surface anywhere on the public website."""
    retired_labels = [
        "Join the cohort",
        "Register interest",
        "Founding Cohort applications are open",
        "Read about the cohort",
        "Apply for the founding cohort",
    ]
    for path in _PUBLIC_SURFACES:
        src = _r(path)
        for label in retired_labels:
            assert label not in src, (
                f"{path.name} still carries retired label {label!r}"
            )


# ── Backend rewrites ──────────────────────────────────────────────────


def test_m5_router_applicant_confirmation_swapped():
    s = _r(ROUTER_PY)
    assert "Thank you for requesting access to Akki." in s
    assert "We have your " in s
    assert "request on file" in s
    assert "in early access" in s
    # Old strings gone.
    assert "founding cohort" not in s.lower()
    assert "Register your interest" not in s


def test_m5_router_founder_notify_subject_swapped():
    s = _r(ROUTER_PY)
    assert (
        'subject=f"Akki early access — new request from {app_row[\'organisation\']}"'
        in s
    )
    assert "New cohort application" not in s


def test_m5_router_founder_notify_body_uses_request_language():
    s = _r(ROUTER_PY)
    assert "New Akki early-access request." in s


# ── /early-access route alias ─────────────────────────────────────────


def test_m5_early_access_route_redirects_to_cohort():
    """The /early-access route now serves a Navigate alias to /cohort
    so future links can use the cleaner URL without breaking SEO on
    the existing /cohort route."""
    s = _r(APP_JS)
    assert (
        '<Route path="/early-access" element={<Navigate to="/cohort" replace />} />'
        in s
    )
    # The old direct-mount must be gone.
    assert '<Route path="/early-access" element={<EarlyAccess />} />' not in s


# ── Voice-lint phrase bans ────────────────────────────────────────────


def test_m5_lint_voice_carries_phrase_bans():
    s = _r(LINT_SCRIPT)
    assert "BANNED_PHRASES" in s
    assert '"founding cohort"' in s
    assert '"join the cohort"' in s
    assert "_PHRASE_RE" in s


def test_m5_lint_voice_clean_after_swap():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan, DEFAULT_TARGETS, _PHRASE_RE  # noqa: F401
    hits = scan(DEFAULT_TARGETS)
    rendered = [(str(p.relative_to(REPO)), ln, w) for p, ln, w, _ in hits]
    assert not hits, (
        f"voice-lint must be clean post-M.5 swap; got: {rendered}"
    )


def test_m5_lint_voice_phrase_regex_flags_offenders():
    """Compile-test the new phrase regex — must catch both bans
    case-insensitively at word boundaries."""
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import _PHRASE_RE
    for s in (
        "Join the cohort today",
        "join the cohort.",
        "the Founding Cohort applications",
        "founding cohort pricing",
        "FOUNDING COHORT applications are",
    ):
        assert _PHRASE_RE.search(s), (
            f"phrase regex must match {s!r}"
        )
    # Negative — substring overlap that shouldn't match.
    for s in (
        "Early access pricing",
        "the cohort lifted off",       # no founding/join prefix
        "joinder of the cohort",       # no "join the" boundary match
    ):
        assert not _PHRASE_RE.search(s), (
            f"phrase regex must NOT match {s!r}"
        )
