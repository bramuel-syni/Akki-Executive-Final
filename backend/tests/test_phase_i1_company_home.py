"""Phase I.1 — Company Home layout shell CI guard (2026-05-27).

Locks:
  T1.  `CompanyHome.jsx` exists at the canonical path.
  T2.  AppHome dispatcher routes active-context → CompanyHome
       (not Home2; H.5 already routed no-active-context → ContextPortfolio).
  T3.  H1 testid `company-home-h1` carries inline 32px (not a token).
  T4.  H1 text uses `Inside {companyName}.` interpolation.
  T5.  Subtitle present: "Here is what's on your plate."
  T6.  Readiness placeholder strip rendered with `—%` value.
  T7.  5 attention cards present with `data-card-kind="attention"`,
       all 5 `data-card-id` values: drafts/reports/pulse/questions/events.
  T8.  Right rail has 3 chips (Pulse default selected),
       3 testids: company-home-top-signals-chip-{pulse,monitor,documents}.
  T9.  `+ Add Document` + `All docs` icon buttons present.
  T10. Breadcrumb `← Back to Portfolio` present with onClick handler
       that calls `clearActiveContext` then `navigate("/app")`.
  T11. CompanyHome does NOT touch `.akki-greeting` token.
  T12. Pulse chip is default-selected on initial render (useState default).
  T13. Each attention card carries an aria-label and focus-visible ring.
  T14. AuthContext exposes `clearActiveContext` in the value object.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

COMPANY_HOME    = FE / "pages" / "CompanyHome.jsx"
APP_HOME        = FE / "pages" / "AppHome.jsx"
AUTH_CONTEXT    = FE / "contexts" / "AuthContext.jsx"
INDEX_CSS       = FE / "index.css"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. File exists at canonical path ────────────────────────────
def test_i1_company_home_file_exists():
    assert COMPANY_HOME.exists(), (
        f"CompanyHome.jsx must exist at {COMPANY_HOME.as_posix()}"
    )


# ── T2. AppHome routes active-context → CompanyHome ──────────────
def test_i1_app_home_routes_active_context_to_company_home():
    src = _read(APP_HOME)
    assert "import CompanyHome" in src, "AppHome must import CompanyHome"
    # Active-context branch returns <CompanyHome />.
    assert "return <CompanyHome />" in src, (
        "AppHome's active-context branch must render <CompanyHome />, "
        "not <Home2 />."
    )
    # Home2 import is gone from AppHome (Phase I.6 will archive Home2).
    assert "import Home2" not in src
    # No-active-context branch still routes to ContextPortfolio.
    assert "return <ContextPortfolio />" in src


# ── T3. H1 has inline 32px style ────────────────────────────────
def test_i1_h1_has_inline_32px_size():
    src = _read(COMPANY_HOME)
    assert 'data-testid="company-home-h1"' in src
    # Inline style or Tailwind class — both forms accepted.
    assert 'style={{ fontSize: "32px" }}' in src or \
           'text-[32px]' in src, (
        "H1 must carry an inline 32px size (NOT via .akki-greeting token)."
    )


# ── T4. H1 text uses `Inside {companyName}.` interpolation ───────
def test_i1_h1_text_is_inside_company_name_dot():
    src = _read(COMPANY_HOME)
    assert "Inside {companyName}." in src, (
        "H1 must say 'Inside {companyName}.' (with active context name "
        "interpolation)."
    )


# ── T5. Subtitle ─────────────────────────────────────────────────
def test_i1_subtitle_present():
    src = _read(COMPANY_HOME)
    assert "Here is what's on your plate." in src
    assert 'data-testid="company-home-subtitle"' in src


# ── T6. Readiness placeholder ────────────────────────────────────
def test_i1_readiness_placeholder_strip_present():
    src = _read(COMPANY_HOME)
    assert 'data-testid="company-home-readiness-strip"' in src
    assert 'data-testid="company-home-readiness-value"' in src
    # The placeholder dash + percent.
    assert "—%" in src, (
        "Readiness placeholder must render `—%` (em-dash + percent) "
        "until I.2 wires the value."
    )


# ── T7. 5 attention cards with the correct ids ───────────────────
def test_i1_five_attention_cards_with_correct_ids():
    src = _read(COMPANY_HOME)
    assert 'data-card-kind="attention"' in src, (
        "Each attention card must carry data-card-kind=\"attention\"."
    )
    # The testid template uses `${card.id}` interpolation. Confirm
    # the template and the array of 5 ids.
    assert "company-home-attention-${card.id}" in src, (
        "Attention card testid must use template `company-home-attention-${card.id}`."
    )
    # All 5 ids declared in ATTENTION_CARDS.
    arr_match = re.search(
        r"ATTENTION_CARDS\s*=\s*\[(.*?)\]\s*;",
        src, flags=re.DOTALL,
    )
    assert arr_match, "ATTENTION_CARDS array not found"
    arr = arr_match.group(1)
    for cid in ("drafts", "reports", "pulse", "questions", "events"):
        assert f'"{cid}"' in arr or f"'{cid}'" in arr, (
            f"Attention card id `{cid}` not declared in ATTENTION_CARDS."
        )


# ── T8. Right rail has 3 chips, Pulse default selected ──────────
def test_i1_right_rail_has_three_chips_pulse_default():
    src = _read(COMPANY_HOME)
    # Chip testids use a template literal `${c.id}`.
    assert "company-home-top-signals-chip-${c.id}" in src, (
        "Chip testid must use template `company-home-top-signals-chip-${c.id}`."
    )
    # Pulse is the default useState value.
    assert 'useState("pulse")' in src, (
        "Pulse chip must be the default-selected useState value."
    )


# ── T9. Add Document + All Docs ───────────────────────────────────
def test_i1_right_rail_has_add_doc_and_all_docs_buttons():
    src = _read(COMPANY_HOME)
    assert 'data-testid="company-home-add-doc-btn"' in src
    assert 'data-testid="company-home-all-docs-btn"' in src
    assert "Add Document" in src


# ── T10. Breadcrumb back-to-portfolio ────────────────────────────
def test_i1_breadcrumb_back_to_portfolio_clears_context_and_routes():
    src = _read(COMPANY_HOME)
    assert 'data-testid="company-home-back-to-portfolio"' in src
    assert "Back to Portfolio" in src
    # Handler calls clearActiveContext then navigates to /app.
    m = re.search(
        r"onBackToPortfolio\s*=\s*useCallback\(\s*\(\s*\)\s*=>\s*\{(.*?)\}\s*,",
        src, flags=re.DOTALL,
    )
    assert m, "onBackToPortfolio handler not found"
    handler = m.group(1)
    assert "clearActiveContext" in handler, (
        "Back-to-portfolio handler must call clearActiveContext()."
    )
    assert 'navigate("/app")' in handler, (
        "Back-to-portfolio handler must navigate to /app."
    )


# ── T11. .akki-greeting token NOT touched ────────────────────────
def test_i1_does_not_mutate_akki_greeting_token():
    """The token is locked at 28px. CompanyHome's 32px H1 uses an
    inline override, never the token. We check that no JSX className
    uses `akki-greeting` — references in /* comments */ are fine."""
    src = _read(COMPANY_HOME)
    # Strip block comments first.
    stripped = re.sub(r"/\*[\s\S]*?\*/", "", src)
    # Strip line comments.
    stripped = re.sub(r"//[^\n]*", "", stripped)
    assert "akki-greeting" not in stripped, (
        "CompanyHome must NOT reference .akki-greeting class in JSX. "
        "Use inline 32px instead. Doc comments referencing it are fine."
    )


# ── T12. Pulse chip is default-selected on render ────────────────
def test_i1_pulse_chip_is_default_selected_on_render():
    src = _read(COMPANY_HOME)
    # The chip array order is pulse, monitor, documents.
    arr_match = re.search(
        r"TOP_SIGNAL_CHIPS\s*=\s*\[(.*?)\]\s*;",
        src, flags=re.DOTALL,
    )
    assert arr_match, "TOP_SIGNAL_CHIPS array not found"
    arr = arr_match.group(1)
    assert arr.find('"pulse"') < arr.find('"monitor"'), (
        "Pulse must precede Monitor in TOP_SIGNAL_CHIPS."
    )
    assert arr.find('"monitor"') < arr.find('"documents"'), (
        "Monitor must precede Documents in TOP_SIGNAL_CHIPS."
    )


# ── T13. Each attention card aria-label + focus ring ─────────────
def test_i1_attention_cards_carry_aria_label_and_focus_ring():
    src = _read(COMPANY_HOME)
    m = re.search(
        r"function AttentionCard\(.*?\}\s*\)\s*\{(.*?)\n\}\n",
        src, flags=re.DOTALL,
    )
    assert m, "AttentionCard function not found"
    card_body = m.group(1)
    assert "aria-label=" in card_body, "AttentionCard missing aria-label"
    assert "focus-visible:ring-2" in card_body, (
        "AttentionCard missing focus-visible ring."
    )


# ── T14. AuthContext exposes clearActiveContext ──────────────────
def test_i1_auth_context_exposes_clear_active_context():
    src = _read(AUTH_CONTEXT)
    assert "const clearActiveContext = useCallback(" in src, (
        "AuthContext must declare a `clearActiveContext` callback."
    )
    assert "clearActiveContext" in src
    # It's in the context value object.
    assert re.search(
        r"const value = useMemo\([\s\S]*?clearActiveContext",
        src,
    ), "clearActiveContext must be in the AuthContext value object."
