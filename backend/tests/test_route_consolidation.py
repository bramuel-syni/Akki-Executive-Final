"""Phase H.5 — Route consolidation CI guard (2026-05-27).

Locks in the route consolidation per the user's mandate:
"Old Home 1 and Home 2 are still main route — let's keep backlog at
minimum. We don't have a 'companies' page. Log in → land on Home 1,
what we just shipped. Select company → land on Home 2, what we just
shipped. Everything else remove."

Locks:
  T1.  Home1 is NOT imported in any active file (only in
       `frontend/src/_archived/Home1.jsx`).
  T2.  `/app/portfolio` is a redirect (Navigate) to `/app`.
  T3.  `/app/companies` is a redirect to `/app`.
  T4.  `/app/contexts` is a redirect to `/app`.
  T5.  `App.js` no longer defines `PortfolioRoute`.
  T6.  AppHome's no-active-context branch renders ContextPortfolio.
  T7.  SignIn defaults post-login navigation to `/app`.
  T8.  Home2's "Back to portfolio" handler navigates to `/app`.
  T9.  NewsStub's back-link targets `/app`.
  T10. Home1.jsx exists at the archived path.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE = REPO / "frontend" / "src"

APP_JS         = FE / "App.js"
APP_HOME       = FE / "pages" / "AppHome.jsx"
SIGN_IN        = FE / "pages" / "SignIn.jsx"
HOME2_LIVE     = FE / "pages" / "home" / "Home2.jsx"
HOME2_ARCHIVED = FE / "_archived" / "Home2.jsx"
HOME2          = HOME2_LIVE if HOME2_LIVE.exists() else HOME2_ARCHIVED
NEWS_STUB      = FE / "pages" / "NewsStub.jsx"
HOME1_LIVE     = FE / "pages" / "home" / "Home1.jsx"
HOME1_ARCHIVED = FE / "_archived" / "Home1.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── T1. Home1 is not imported in active code ────────────────────
def test_h5_home1_not_imported_in_active_code():
    """Walk every .js/.jsx/.ts/.tsx file under frontend/src/ and
    assert none import from `home/Home1` (except `_archived/`).
    Comments referencing `Home1` are fine — only live imports fail."""
    offenders = []
    for path in FE.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        # Skip the archived file itself.
        rel = path.relative_to(FE).as_posix()
        if rel.startswith("_archived/"):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"import\s+[^'\"\n]*\s+from\s+['\"][^'\"]*home/Home1['\"]", text):
            offenders.append(rel)
        if re.search(r"import\(\s*['\"][^'\"]*home/Home1['\"]\s*\)", text):
            offenders.append(rel)
    assert not offenders, (
        f"Home1 must only live in _archived/. Active imports found: {offenders}"
    )


# ── T2 / T3 / T4. Legacy routes redirect to /app ────────────────
def test_h5_legacy_portfolio_route_redirects_to_app():
    src = _read(APP_JS)
    assert (
        '<Route path="/app/portfolio" element={<Navigate to="/app" replace />} />'
        in src
    ), "/app/portfolio must redirect to /app"


def test_h5_legacy_companies_route_redirects_to_app():
    src = _read(APP_JS)
    assert (
        '<Route path="/app/companies" element={<Navigate to="/app" replace />} />'
        in src
    ), "/app/companies must redirect to /app"


def test_h5_legacy_contexts_route_redirects_to_app():
    src = _read(APP_JS)
    assert (
        '<Route path="/app/contexts" element={<Navigate to="/app" replace />} />'
        in src
    ), "/app/contexts must redirect to /app"


# ── T5. PortfolioRoute removed ──────────────────────────────────
def test_h5_portfolio_route_function_removed():
    src = _read(APP_JS)
    assert "function PortfolioRoute" not in src, (
        "PortfolioRoute() (Home1 wrapper) must be gone — Home1 is archived."
    )
    assert "<PortfolioRoute" not in src


# ── T6. AppHome dispatcher routes to ContextPortfolio ───────────
def test_h5_app_home_dispatcher_routes_to_context_portfolio():
    src = _read(APP_HOME)
    assert "import ContextPortfolio" in src
    assert "<ContextPortfolio />" in src
    # Home1 reference is gone (except in the comment marker).
    # We check the import block specifically — no `import Home1` line.
    assert not re.search(r"^import\s+Home1\b", src, flags=re.MULTILINE)


# ── T7. SignIn default post-login redirect is /app ──────────────
def test_h5_signin_post_login_default_is_app_root():
    src = _read(SIGN_IN)
    assert 'location.state?.from || "/app"' in src, (
        "SignIn default post-login must be `/app` (was /app/portfolio)."
    )
    # Must NOT have stale /app/portfolio default.
    assert 'location.state?.from || "/app/portfolio"' not in src


# ── T8. Home2 back-to-portfolio navigates to /app ───────────────
def test_h5_home2_back_to_portfolio_routes_to_app():
    src = _read(HOME2)
    # The handler navigates to /app (not /app/portfolio).
    m = re.search(
        r"onBackToPortfolio\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\n\s*\}",
        src, flags=re.DOTALL,
    )
    assert m, "onBackToPortfolio handler not found in Home2"
    handler = m.group(1)
    # Strip JS line-comments so prose explanations don't trip the
    # stale-route check.
    handler_code = re.sub(r"//[^\n]*", "", handler)
    assert 'navigate("/app")' in handler_code, (
        "Home2 onBackToPortfolio must navigate to `/app`."
    )
    assert '/app/portfolio' not in handler_code, (
        "Stale `/app/portfolio` navigation in Home2 — must be `/app`."
    )


# ── T9. NewsStub back link targets /app ─────────────────────────
def test_h5_news_stub_back_link_targets_app():
    src = _read(NEWS_STUB)
    assert 'to="/app"' in src, "NewsStub back-link must target `/app`."
    assert 'to="/app/companies"' not in src, (
        "Stale NewsStub back-link `/app/companies` — must be `/app`."
    )


# ── T10. Archive present, live path empty ───────────────────────
def test_h5_home1_archived_file_exists_and_no_live_file():
    assert HOME1_ARCHIVED.exists(), (
        f"Home1 archived file must exist at {HOME1_ARCHIVED.as_posix()}."
    )
    assert not HOME1_LIVE.exists(), (
        f"Home1 must NOT exist at the live path {HOME1_LIVE.as_posix()}."
    )


# ── T11. /app route still mounts AppHome ────────────────────────
def test_h5_app_root_mounts_app_home():
    src = _read(APP_JS)
    assert '<Route path="/app" element={<Gated><AppHome /></Gated>} />' in src
