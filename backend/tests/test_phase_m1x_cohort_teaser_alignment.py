"""Sprint M.1.x (2026-02 dispatch 12) — Homepage COHORT_TEASER alignment
with the /cohort hold (dispatch 11). Pricing claim removed from the
homepage so prospects don't see promises that /cohort doesn't keep.
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
COPY_JS = REPO / "frontend" / "src" / "website" / "copy" / "index.js"


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── New holding-state body locked verbatim ────────────────────────────


def test_m1x_cohort_teaser_holding_body_verbatim():
    s = _r(COPY_JS)
    # Locate the COHORT_TEASER block.
    idx = s.find("export const COHORT_TEASER = {")
    assert idx > 0
    end = s.find("};", idx)
    block = s[idx:end]
    # Sprint M.5 (2026-02) — new early-access body locked verbatim.
    expected_tail = "Akki is in early access. Request a place below."
    assert expected_tail in block, (
        f"Expected early-access body in COHORT_TEASER.body; block: {block!r}"
    )


# ── Banned pricing patterns absent from the teaser block ──────────────


BANNED_PATTERNS = [
    "early-access pricing",
    "pricing locked",
    "locked for two years",
    "early-access",
    "first six months",  # the discount-trigger phrasing also goes
]


def test_m1x_cohort_teaser_no_banned_pricing_language():
    s = _r(COPY_JS)
    idx = s.find("export const COHORT_TEASER = {")
    end = s.find("};", idx)
    block = s[idx:end].lower()
    hits = [p for p in BANNED_PATTERNS if p.lower() in block]
    assert not hits, (
        f"COHORT_TEASER block must not carry pricing language; found: {hits}"
    )


# ── CTA still points at /cohort ───────────────────────────────────────


def test_m1x_cohort_teaser_cta_points_at_cohort_page():
    s = _r(COPY_JS)
    idx = s.find("export const COHORT_TEASER = {")
    end = s.find("};", idx)
    block = s[idx:end]
    # Sprint M.5 (2026-02) — CTA label switched to "Request access"
    # in line with the early-access framing. Route preserved (/cohort).
    assert 'cta: { label: "Request access", href: "/cohort" }' in block


# ── Voice-lint full-surface guard (CI gate enforces same on PR) ───────


def test_m1x_voice_lint_clean_post_alignment():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan, DEFAULT_TARGETS
    hits = scan(DEFAULT_TARGETS)
    rendered = [(str(p.relative_to(REPO)), ln, w) for p, ln, w, _ in hits]
    assert not hits, f"voice-lint must remain clean post-M.1.x; got: {rendered}"
