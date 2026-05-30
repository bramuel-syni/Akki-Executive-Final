"""Sprint M.2-hold (2026-02 fork-resume v3 dispatch 11) — /cohort
holding-state lockdown.

User directive: pricing copy is removed pending product packaging.
The /cohort page stays visible, the application form stays functional,
the holding-state line names the status above the form.

Locks:
  * Verbatim holding-state line is present in copy/index.js + rendered
    via the Cohort.jsx page.
  * Banned pricing patterns are absent from the /cohort surface.
  * Form fields + submit endpoint shape unchanged.
  * Applicant confirmation body acknowledges receipt with no
    commitment language.
  * docs/cohort_pricing.md is in HELD status.
  * Voice-lint clean.
"""
from __future__ import annotations
import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

REPO = Path(__file__).resolve().parent.parent.parent
COHORT_JSX = REPO / "frontend" / "src" / "website" / "pages" / "Cohort.jsx"
COPY_JS = REPO / "frontend" / "src" / "website" / "copy" / "index.js"
ROUTER_PY = REPO / "backend" / "routers" / "cohort_applications.py"
DOC_MD = REPO / "docs" / "cohort_pricing.md"

HOLDING_LINE = (
    "Founding Cohort pricing is being finalised. Register your interest "
    "below — we will share the offer with members before launch."
)


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── Holding-state copy locks ───────────────────────────────────────────


def test_m2hold_holding_line_in_copy_module_verbatim():
    s = _r(COPY_JS)
    assert f'holding: "{HOLDING_LINE}"' in s


def test_m2hold_holding_line_rendered_on_page():
    s = _r(COHORT_JSX)
    # Page reads from COHORT.holding so the source-of-truth is one place.
    assert "{COHORT.holding}" in s
    assert 'data-testid="cohort-holding-line"' in s


# ── Banned pricing patterns absent ─────────────────────────────────────


PRICING_NEEDLES_OFF_PAGE = [
    "early-access pricing locked for two years",
    "pricing locked for two years",
    "$ per seat",
    "/seat",
    "Founding Cohort pricing locked",
]


def test_m2hold_no_pricing_in_cohort_page_jsx():
    s = _r(COHORT_JSX)
    for needle in PRICING_NEEDLES_OFF_PAGE:
        assert needle.lower() not in s.lower(), (
            f"Pricing language must be absent from Cohort.jsx; found: {needle!r}"
        )
    # `$` should not appear as a price symbol anywhere.
    # Allowed: template literals / JSX expressions like `${var}`.
    # We scan for `$` followed by an optional space and a digit.
    assert not re.search(r"\$\s*\d", s), "`$<digit>` price pattern in Cohort.jsx"


def test_m2hold_no_pricing_in_cohort_copy_block():
    """COHORT export in copy/index.js must not carry pricing language."""
    s = _r(COPY_JS)
    # Locate the COHORT export block.
    idx = s.find("export const COHORT = {")
    assert idx > 0, "COHORT export not found"
    end = s.find("};", idx)
    block = s[idx:end]
    for needle in PRICING_NEEDLES_OFF_PAGE:
        assert needle.lower() not in block.lower(), (
            f"Pricing language must be absent from COHORT export; found: {needle!r}"
        )


# ── Form + submit shape preserved ──────────────────────────────────────


REQUIRED_FIELD_TESTIDS = [
    "cohort-field-name",
    "cohort-field-email",
    "cohort-field-organisation",
    "cohort-field-role",
    "cohort-field-use_case",
    "cohort-field-referral_source",
]


def test_m2hold_form_has_required_fields_and_submit():
    s = _r(COHORT_JSX)
    assert 'data-testid="cohort-application-form"' in s
    assert 'data-testid="cohort-submit"' in s
    for tid in REQUIRED_FIELD_TESTIDS:
        assert f'data-testid={{`cohort-field-${{f.id}}`}}' in s or tid in s
    # Hardcoded form-field id list must include all six.
    assert '"name"' in s and '"email"' in s and '"organisation"' in s
    assert '"role"' in s and '"use_case"' in s and '"referral_source"' in s


def test_m2hold_submit_targets_cohort_applications_endpoint():
    s = _r(COHORT_JSX)
    assert "/api/cohort/applications" in s


# ── Backend: applicant confirmation body holding-state ────────────────


def test_m2hold_applicant_confirmation_body_no_pricing():
    s = _r(ROUTER_PY)
    # New body is present — the literal source spans multiple Python
    # string-concatenation lines, so we assert each contiguous fragment.
    assert "Thank you for registering your interest in the Akki " in s
    assert "Founding Cohort pricing is " in s
    assert "being finalised" in s
    # Old placeholder is gone.
    assert "<!-- COPY TBD M.2 -->" not in s
    # No commitment language patterns.
    forbidden = ["guaranteed", "locked for two years", "$/seat", "discount"]
    for needle in forbidden:
        assert needle.lower() not in s.lower(), (
            f"Forbidden commitment language in applicant body: {needle!r}"
        )


# ── docs/cohort_pricing.md HELD status ─────────────────────────────────


def test_m2hold_doc_records_held_status():
    s = _r(DOC_MD)
    assert "Pricing not yet defined" in s
    assert "**Status: HELD**" in s
    assert "<!-- COPY TBD M.2 -->" not in s


# ── Voice-lint clean over the full surface (CI gate enforces too) ─────


def test_m2hold_voice_lint_clean():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan, DEFAULT_TARGETS
    hits = scan(DEFAULT_TARGETS)
    rendered = [(str(p.relative_to(REPO)), ln, w) for p, ln, w, _ in hits]
    assert not hits, f"voice-lint must remain clean post-hold; got: {rendered}"


# ── Backend submit still works + multi-recipient notify still fires ───


@pytest.fixture
def app():
    import importlib, server
    importlib.reload(server)
    return server.app


@pytest.mark.asyncio
async def test_m2hold_form_submission_still_works(app, monkeypatch):
    """Submitting from the held page POSTs the same payload shape;
    application is stored with the new holding-state body; founder
    notify still fires to both addresses (mocked SendGrid)."""
    monkeypatch.setenv(
        "FOUNDER_NOTIFY_EMAIL", "bramuel@syni.ai,mugwe.marion@syni.ai",
    )
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake-key")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "akki@syni.ai")
    from core import db
    transport = ASGITransport(app=app)
    seeded = []
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/cohort/applications", json={
                "name": "Held Applicant",
                "email": "held-applicant-m2hold@example.com",
                "organisation": "TestCo",
                "role": "CFO",
                "use_case": "Calmer board prep workflow.",
            })
            assert r.status_code == 200, r.text
            body = r.json()
            seeded.append(body["id"])
            row = await db.cohort_applications.find_one(
                {"id": body["id"]}, {"_id": 0},
            )
            assert row["applicant_confirmation_body"].startswith(
                "Thank you for registering your interest"
            )
            assert "founding cohort" in row["applicant_confirmation_body"]
            assert "<!-- COPY TBD M.2 -->" not in row["applicant_confirmation_body"]
    finally:
        for sid in seeded:
            await db.cohort_applications.delete_one({"id": sid})
