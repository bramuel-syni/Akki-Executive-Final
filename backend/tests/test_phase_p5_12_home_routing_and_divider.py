"""P5.12 — Post-login home routing + duplicate divider lockdowns.

P5.12.1 — `ContextPortfolio.jsx` MUST NOT carry a `lg:border-r`
          rule on `portfolio-listing-column`; the canonical edge-
          to-edge hairline lives on the absolute-positioned
          `portfolio-vertical-divider` standalone div.
P5.12.2 — `AuthContext.jsx` MUST NOT auto-pick a context on
          post-login (`afterAuth`) or cold-start (`bootstrap`)
          paths. The post-login default landing is Home 1
          (ContextPortfolio) — admin lands on `/app` and renders
          `portfolio-landing`, NOT `company-home`.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


# ─────────────────────────────────────────────────────────────────
# P5.12.1 — Duplicate divider on ContextPortfolio
# ─────────────────────────────────────────────────────────────────


def test_context_portfolio_listing_column_has_no_border_r():
    """The duplicate hairline came from `lg:border-r` on the
    listing column stacking against the absolute-positioned
    standalone divider. Lock the absence of `lg:border-r` on
    that element so it cannot regress."""
    src = (REPO / "frontend" / "src" / "pages" / "ContextPortfolio.jsx").read_text(encoding="utf-8")
    m = re.search(
        r'<div\s+([^>]*?)data-testid="portfolio-listing-column"',
        src, flags=re.DOTALL,
    )
    assert m, "could not find the portfolio-listing-column div"
    attrs = m.group(1)
    assert "lg:border-r" not in attrs, (
        "portfolio-listing-column still has `lg:border-r` — the "
        "duplicate-divider bug is back. The absolute-positioned "
        "portfolio-vertical-divider is the canonical hairline; "
        "the listing column must NOT also paint a border-right."
    )


def test_context_portfolio_keeps_absolute_standalone_divider():
    """The fix removed the column border-r; the absolute hairline
    MUST remain (it's the surviving canonical divider)."""
    src = (REPO / "frontend" / "src" / "pages" / "ContextPortfolio.jsx").read_text(encoding="utf-8")
    assert 'data-testid="portfolio-vertical-divider"' in src
    # And it MUST still carry the absolute + top-0/bottom-0 spans
    # so it's edge-to-edge across the wrapper height. We grab the
    # entire opening tag (attribute order in JSX is flexible) and
    # then sniff the className anywhere in the block.
    m = re.search(
        r'<div\s+([^>]*?data-testid="portfolio-vertical-divider"[^>]*?)/?>',
        src, flags=re.DOTALL,
    )
    assert m, "absolute standalone divider tag missing"
    block = m.group(1)
    cls_match = re.search(r'className="([^"]*)"', block)
    assert cls_match, f"divider has no className: {block!r}"
    cls = cls_match.group(1)
    for required in ("absolute", "top-0", "bottom-0", "w-px"):
        assert required in cls, f"divider className missing `{required}`: {cls!r}"


def test_company_home_listing_column_has_no_border_r():
    """CompanyHome.jsx uses the same absolute-divider pattern and
    should also NOT carry a stacked border-right on its main
    column. Today it doesn't — lock the invariant."""
    src = (REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx").read_text(encoding="utf-8")
    m = re.search(
        r'<main\s+([^>]*?)data-testid="company-home-listing-column"',
        src, flags=re.DOTALL,
    )
    assert m, "could not find the company-home-listing-column main"
    attrs = m.group(1)
    assert "lg:border-r" not in attrs, (
        "company-home-listing-column has `lg:border-r` — it stacks "
        "against the absolute company-home-vertical-divider and "
        "produces a duplicate hairline."
    )


# ─────────────────────────────────────────────────────────────────
# P5.12.2 — Post-login routing default
# ─────────────────────────────────────────────────────────────────


def test_auth_context_post_login_does_not_auto_pick_context():
    """The `afterAuth(data)` handler MUST NOT call
    `persistActiveContext(ctxs[0].id)` (or any equivalent
    auto-pick). It MUST land the user with a null active context
    so AppHome.jsx dispatches to ContextPortfolio (Home 1)."""
    src = (REPO / "frontend" / "src" / "contexts" / "AuthContext.jsx").read_text(encoding="utf-8")
    # Locate the afterAuth function body.
    m = re.search(
        r"const afterAuth\s*=\s*useCallback\(async\s*\([^)]*\)\s*=>\s*\{(.*?)\},\s*\[",
        src, flags=re.DOTALL,
    )
    assert m, "could not locate afterAuth callback body in AuthContext"
    body = m.group(1)
    # The auto-pick line that used to land the user in Home 2.
    assert "persistActiveContext(ctxs[0].id)" not in body, (
        "afterAuth still auto-picks ctxs[0].id on login — Home 2 "
        "routing bug is back. Post-login MUST land on Home 1."
    )
    # And the explicit null-write MUST still be present so login
    # actively clears any stale active context from sessionStorage.
    assert "persistActiveContext(null)" in body, (
        "afterAuth no longer explicitly clears the active context; "
        "the user could carry over a stale id from a prior session."
    )


def test_auth_context_cold_start_does_not_auto_pick_context():
    """The `bootstrap()` cold-start branch (when no sessionStorage
    cached id exists AND the cookie session is valid) MUST NOT
    auto-pick the first membership any more. Same rationale as
    afterAuth — fresh tab should land on Home 1."""
    src = (REPO / "frontend" / "src" / "contexts" / "AuthContext.jsx").read_text(encoding="utf-8")
    # Locate the bootstrap function body.
    m = re.search(
        r"const bootstrap\s*=\s*useCallback\(async\s*\(\)\s*=>\s*\{(.*?)\},\s*\[",
        src, flags=re.DOTALL,
    )
    assert m, "could not locate bootstrap callback body in AuthContext"
    body = m.group(1)
    # The legacy cold-start auto-pick branch.
    assert "else if (!cached && ctxs.length >= 1)" not in body, (
        "bootstrap still has the cold-start auto-pick branch — "
        "fresh tabs will silently warp into a company instead of "
        "landing on Home 1."
    )


def test_auth_context_preserves_membership_revoked_safety_net():
    """The mid-session safety net (cached id but no longer a valid
    membership → auto-pick the first valid membership so the SPA
    isn't left in a broken state) is OUT of scope for P5.12.2 and
    MUST be preserved."""
    src = (REPO / "frontend" / "src" / "contexts" / "AuthContext.jsx").read_text(encoding="utf-8")
    m = re.search(
        r"const bootstrap\s*=\s*useCallback\(async\s*\(\)\s*=>\s*\{(.*?)\},\s*\[",
        src, flags=re.DOTALL,
    )
    body = m.group(1)
    # The revoked-id branch:
    assert "if (cached && !cachedStillValid)" in body, (
        "the mid-session membership-revoked safety net is missing; "
        "users whose cached context goes stale will land in a hole."
    )


def test_app_home_dispatch_to_context_portfolio_when_no_active_context():
    """Pin the dispatcher contract: when `activeContext` is falsy,
    AppHome renders ContextPortfolio (Home 1), not CompanyHome."""
    src = (REPO / "frontend" / "src" / "pages" / "AppHome.jsx").read_text(encoding="utf-8")
    # The exact line order matters — undeclared first, then
    # no-active-context (Home 1), then CompanyHome (Home 2).
    assert "if (!activeContext) return <ContextPortfolio />;" in src, (
        "AppHome dispatcher no longer routes the no-active-context "
        "branch to ContextPortfolio (Home 1)."
    )
    assert "return <CompanyHome />;" in src, (
        "AppHome no longer falls through to CompanyHome (Home 2) "
        "when an active context exists."
    )
