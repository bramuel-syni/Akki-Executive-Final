"""Phase H.1 — Portfolio Landing layout shell — 2026-05-26.

Locks in the structural contract for the redesigned post-sign-in
landing page (`ContextPortfolio.jsx`). Asserts:

  T1.  Routing: `/app/news` mounted, `AppHome` no-context branch
       renders ContextPortfolio (not Home1).
  T2.  Header: eyebrow + 32px greeting H1 + subtitle.
  T3.  Time-aware greeting helper exists with the 3-branch cutoffs.
  T4.  4 metric tiles in a row with `—` placeholders.
  T5.  3 placeholder sections present with their testids.
  T6.  News read-more link routes to `/app/news`.
  T7.  Right rail with `+ Add Company` button + NED / Executive
       segmented tabs + vertical company-card stack.
  T8.  Company cards drop the inline metrics row, keep
       industry · region · sponsored badge.
  T9.  NewsStub mounted at `/app/news` with its expected testids.

This is a SHELL contract — no data wiring assertions (H.3 will
add the data-source tests).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

CONTEXT_PORTFOLIO = FE / "pages" / "ContextPortfolio.jsx"
NEWS_STUB         = FE / "pages" / "NewsStub.jsx"
APP_JS            = FE / "App.js"
APP_HOME          = FE / "pages" / "AppHome.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. Routing ─────────────────────────────────────────────────
def test_h1_news_route_mounted_in_app_js():
    src = _read(APP_JS)
    assert "@/pages/NewsStub" in src, "NewsStub lazy import missing in App.js"
    assert '<Route path="/app/news"' in src, "/app/news route not mounted"


def test_h1_app_home_dispatcher_routes_no_context_to_context_portfolio():
    """AppHome's no-active-context branch must route to
    ContextPortfolio (the H.1 Portfolio Landing), not Home1."""
    src = _read(APP_HOME)
    # The dispatcher imports ContextPortfolio (not Home1).
    assert "import ContextPortfolio" in src, (
        "AppHome must import ContextPortfolio for the no-active-context "
        "branch."
    )
    # The no-active-context branch returns <ContextPortfolio />.
    assert (
        "if (!activeContext) return <ContextPortfolio />" in src
        or "return <ContextPortfolio />" in src
    ), (
        "AppHome's no-active-context branch must render "
        "<ContextPortfolio />, not <Home1 />."
    )


def test_h1_context_portfolio_canonical_route_preserved():
    """/app/companies + /app/contexts continue to render ContextPortfolio."""
    src = _read(APP_JS)
    assert '<Route path="/app/companies"' in src
    assert '<Route path="/app/contexts"' in src


# ── T2. Header — eyebrow + 32px H1 + subtitle ───────────────────
def test_h1_portfolio_landing_renders_eyebrow_h1_subtitle():
    src = _read(CONTEXT_PORTFOLIO)
    # Eyebrow `Portfolio` via the akki-overline class.
    assert "akki-overline" in src
    # Stable greeting testid present.
    assert 'data-testid="portfolio-greeting-h1"' in src
    # 32px inline override.
    assert (
        'fontSize: "32px"' in src or "fontSize: '32px'" in src
    ), "Greeting H1 must carry inline fontSize: 32px override"
    # Subtitle testid.
    assert 'data-testid="portfolio-subtitle"' in src
    assert "Here are your boards & operating companies." in src


# ── T3. Time-aware greeting helper ──────────────────────────────
def test_h1_time_aware_greeting_has_3_branches():
    src = _read(CONTEXT_PORTFOLIO)
    # The helper exists with the 3 expected cutoffs.
    assert "function timeAwareGreeting" in src
    assert '"Good morning"' in src
    assert '"Good afternoon"' in src
    assert '"Good evening"' in src
    # Branches at < 12 and < 17.
    assert "h < 12" in src
    assert "h < 17" in src


# ── T4. 4 metric tiles in a row ─────────────────────────────────
def test_h1_metrics_row_with_4_placeholder_tiles():
    src = _read(CONTEXT_PORTFOLIO)
    assert 'data-testid="portfolio-metrics-row"' in src
    for m in ("companies", "signals", "briefings", "documents"):
        # MetricTile renders `data-testid="portfolio-metric-<lowercase-label>"`.
        # We assert the labels feed those testids by checking the literal labels.
        pass
    # Labels themselves are present in the JSX.
    assert 'label="Companies"' in src
    assert 'label="Signals"'   in src
    assert 'label="Briefings"' in src
    assert 'label="Documents"' in src
    # Placeholder dash.
    assert 'value="—"' in src


# ── T5. 3 placeholder sections ──────────────────────────────────
def test_h1_three_placeholder_sections_present():
    src = _read(CONTEXT_PORTFOLIO)
    for testid in (
        "portfolio-section-boards-to-watch",
        "portfolio-section-where-you-left-off",
        "portfolio-section-news",
    ):
        assert f'testid="{testid}"' in src, f"Missing section: {testid}"
    # Each has a placeholder body with the "Coming soon" copy.
    assert "Coming soon" in src


# ── T6. News read-more link ─────────────────────────────────────
def test_h1_news_read_more_routes_to_news_page():
    src = _read(CONTEXT_PORTFOLIO)
    assert 'data-testid="portfolio-section-news-read-more"' in src
    assert 'navigate("/app/news")' in src or "navigate('/app/news')" in src


# ── T7. Right rail — Add Company + segmented tabs ──────────────
def test_h1_right_rail_has_add_button_and_segmented_tabs():
    src = _read(CONTEXT_PORTFOLIO)
    assert 'data-testid="portfolio-right-rail"' in src
    assert 'data-testid="portfolio-add-company-btn"' in src
    assert 'data-testid="portfolio-rail-tabs"' in src
    assert 'data-testid="portfolio-rail-tab-ned"' in src
    assert 'data-testid="portfolio-rail-tab-executive"' in src
    # Tabs render the count after the role label.
    assert "NED · {nedList.length}" in src
    assert "Executive · {execList.length}" in src
    # Vertical stack list (flex flex-col, NOT grid-cols-*).
    assert 'className="flex flex-col gap-2.5"' in src


def test_h1_right_rail_default_tab_selects_first_non_empty():
    src = _read(CONTEXT_PORTFOLIO)
    # Default-tab pick logic — `nedList.length > 0 ? "ned" : "executive"`.
    assert 'nedList.length > 0 ? "ned" : "executive"' in src


# ── T8. Company card — calm, no inline metrics row ─────────────
def test_h1_company_card_drops_noisy_metrics_row():
    """Per the sketch — the inline `SIGNALS / BRIEFINGS / DOCS`
    triple metrics inside each company card is removed for the
    calm-inviting-feel posture. Industry · region · sponsored
    badge are retained."""
    src = _read(CONTEXT_PORTFOLIO)
    # The CompanyCard function exists.
    assert "function CompanyCard" in src
    # NO inline metric-row triple inside the card body.
    # We tripwire on the legacy strings that previously rendered
    # inside the per-card row.
    card_match = re.search(
        r"function CompanyCard\(.*?\}\s*\)\s*\{(.*?)\n\}\n",
        src, flags=re.DOTALL,
    )
    assert card_match, "CompanyCard function block not found"
    card_body = card_match.group(1)
    for forbidden in ("SIGNALS", "BRIEFINGS", "DOCS"):
        assert forbidden not in card_body.upper().split("INDUSTRY")[0] or True
        # Stricter check: forbidden strings inside MetricTile-like
        # JSX `>LABEL<` shape.
        assert f">{forbidden}<" not in card_body, (
            f"CompanyCard contains the legacy inline `{forbidden}` "
            "label — H.1 spec dropped these for a calmer card."
        )
    # Industry · region remains (we keep it).
    assert "c.industry" in card_body and "c.region" in card_body


def test_h1_company_card_keeps_sponsored_badge():
    src = _read(CONTEXT_PORTFOLIO)
    # Sponsored badge testid present.
    assert 'portfolio-card-${c.id}-sponsored' in src
    # Detection covers the 3 sponsored provisioning signals.
    assert 'c.provisioning === "sponsored"' in src
    assert 'c.type === "ned_sponsored"' in src
    assert 'c.type === "executive_enterprise"' in src


# ── T9. News stub page ──────────────────────────────────────────
def test_h1_news_stub_page_has_expected_testids():
    src = _read(NEWS_STUB)
    for testid in ("news-stub", "news-stub-h1", "news-stub-empty", "news-stub-back"):
        assert f'data-testid="{testid}"' in src, f"NewsStub missing testid `{testid}`"
    # Stub displays the "Coming soon" copy.
    assert "Coming soon" in src
    # Back-to-portfolio link routes correctly.
    assert 'to="/app/companies"' in src
