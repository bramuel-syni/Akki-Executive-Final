"""
R.followup.2 (2026-05-27) — Page-level superadmin enforcement on
`/app/admin/*` and `/admin/*` routes.

The dispatch directive:

  > Add a superadmin role check at the route-guard level for ALL
  > /app/admin/* routes, not just data endpoints. Non-superadmin →
  > 403 redirect to /app. ~20 lines.

Implementation:
  • `frontend/src/components/SuperadminRoute.jsx` — a sibling of
    `ProtectedRoute` that adds `account.is_superadmin` as a hard
    third state (besides bootstrapping + unauthenticated).
  • All 10 admin routes in `App.js` wrap in `<SuperadminRoute>`
    (the 4 `/app/admin/*` routes + the 6 `/admin/*` routes; the
    `/app/blog-admin` content-editor route stays gated on auth
    only).

Source-strict locks (offline) — no runtime dependency on a live
preview pod:
  1. SuperadminRoute file exists + exports default + reads
     `account.is_superadmin`.
  2. Every locked admin path in `App.js` references SuperadminRoute
     in its element.
  3. `useAuth` is imported in SuperadminRoute (state source).
  4. Non-superadmin redirect target is `/app/`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"
SUPERADMIN_ROUTE = FRONTEND / "components" / "SuperadminRoute.jsx"
APP_JS = FRONTEND / "App.js"


# All admin routes that MUST be wrapped in SuperadminRoute. The
# blog-admin path is content-editor (CMS) tooling and stays on
# the auth-only `<Gated>` wrapper — separate concern.
LOCKED_ADMIN_PATHS = (
    "/app/admin/cohort",
    "/app/admin/users",
    "/app/admin/cohort/copy",
    "/app/admin/synisense-observability",
    "/admin/health",
    "/admin/sandbox-kpi",
    "/admin/signal-kpi",
    "/admin/llm-spend",
    "/admin/auth-events",
    "/admin",
)


def test_rf2_superadmin_route_file_exists() -> None:
    assert SUPERADMIN_ROUTE.is_file()


def test_rf2_superadmin_route_default_export_present() -> None:
    src = SUPERADMIN_ROUTE.read_text(encoding="utf-8")
    assert "export default function SuperadminRoute" in src


def test_rf2_superadmin_route_reads_is_superadmin() -> None:
    src = SUPERADMIN_ROUTE.read_text(encoding="utf-8")
    assert "account.is_superadmin" in src


def test_rf2_superadmin_route_imports_useAuth() -> None:
    src = SUPERADMIN_ROUTE.read_text(encoding="utf-8")
    assert "useAuth" in src
    assert "@/contexts/AuthContext" in src


def test_rf2_non_superadmin_redirects_to_app_root() -> None:
    """The negative-superadmin branch must `<Navigate to="/app/"`
    (NOT `/signin` — they ARE authed, just not authorised)."""
    src = SUPERADMIN_ROUTE.read_text(encoding="utf-8")
    pattern = r'!account\.is_superadmin[\s\S]*?to="/app/"'
    assert re.search(pattern, src), (
        "SuperadminRoute non-superadmin branch must `<Navigate "
        'to="/app/" replace />` (not /signin) so authed users land '
        "back on their workspace home, not the sign-in form."
    )


def test_rf2_app_js_imports_superadmin_route() -> None:
    src = APP_JS.read_text(encoding="utf-8")
    assert 'import SuperadminRoute from "@/components/SuperadminRoute"' in src


@pytest.mark.parametrize("path", LOCKED_ADMIN_PATHS)
def test_rf2_admin_route_wrapped_in_superadmin_route(path: str) -> None:
    """Each admin path's `<Route ... element=...>` must reference
    `<SuperadminRoute>`."""
    src = APP_JS.read_text(encoding="utf-8")
    # Match a `<Route path="<path>" element={... SuperadminRoute ...}>`
    # pattern by locating the route line first then asserting the
    # element references SuperadminRoute.
    line_pattern = rf'<Route\s+path="{re.escape(path)}"\s+element=\{{(?P<elem>[^}}]+)\}}'
    m = re.search(line_pattern, src)
    assert m is not None, (
        f"Route declaration for path={path!r} not found in App.js."
    )
    elem = m.group("elem")
    assert "SuperadminRoute" in elem, (
        f"Route {path!r} element does not reference SuperadminRoute. "
        f"Element: {elem.strip()!r}"
    )


def test_rf2_blog_admin_stays_on_gated_only() -> None:
    """`/app/blog-admin` is content-editor tooling, not founder
    superadmin tooling. It must NOT wrap in SuperadminRoute (any
    contributor with `<Gated>` access can edit blog drafts)."""
    src = APP_JS.read_text(encoding="utf-8")
    blog_line = re.search(
        r'<Route\s+path="/app/blog-admin"\s+element=\{([^}]+)\}',
        src,
    )
    assert blog_line is not None, "/app/blog-admin route missing from App.js."
    elem = blog_line.group(1)
    assert "SuperadminRoute" not in elem, (
        "/app/blog-admin must NOT wrap in SuperadminRoute — it's a "
        "content-editor surface, not founder superadmin tooling."
    )
