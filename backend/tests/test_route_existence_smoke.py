"""Route-existence smoke (Phase C — replaces test_iter9_refactor_smoke.py).

Per QUARANTINE_TRIAGE_PLAN.md Phase-5 recipe for
`test_iter9_refactor_smoke.py`:

  > Convert to in-process httpx route-existence smoke — for each of
  > ~20 critical paths, assert that `/api/docs` lists the path. This
  > is faster, doesn't need auth, and validates that no router include
  > got dropped accidentally.

We use `app.openapi()` directly instead of scraping `/api/docs` HTML
because the OpenAPI schema is the source of truth and reads in <50 ms
without spinning up the test client. The single-purpose test then
asserts that every locked path is present, with the expected method.

Adding a router that doesn't include any of the locked paths is fine.
Removing or renaming a locked path WILL break this test — that is the
intended regression signal.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402


# Locked critical paths the refactor smoke originally guarded. These
# are the paths that the legacy iter9 file hit over the network.
# Format: (HTTP method, path-template-as-in-openapi).
_LOCKED_PATHS = [
    # misc router — health + root.
    ("GET", "/api/"),
    ("GET", "/api/health"),
    # auth router.
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("GET", "/api/auth/me"),
    # contexts router.
    ("GET", "/api/contexts/{context_id}"),
    ("GET", "/api/contexts/{context_id}/members"),
    ("GET", "/api/contexts/{context_id}/invitations"),
    # documents router.
    ("POST", "/api/contexts/{context_id}/documents"),
    ("GET", "/api/contexts/{context_id}/documents"),
    ("GET", "/api/contexts/{context_id}/documents/{doc_id}/download"),
    # signals_ask + briefings (shielding regression surfaces).
    ("POST", "/api/contexts/{context_id}/signals/generate"),
    ("POST", "/api/contexts/{context_id}/ask"),
    ("POST", "/api/contexts/{context_id}/briefings"),
]


@pytest.fixture(scope="module")
def openapi_index():
    """Parse `app.openapi()` once → returns {path: {method, …}}.

    The OpenAPI schema lower-cases methods, so the lookup table does
    too. Path templates are kept verbatim (with `{name}` placeholders)
    so callers compare against the same shape FastAPI emits.
    """
    schema = app.openapi()
    index: dict[str, set[str]] = {}
    for path, path_item in schema.get("paths", {}).items():
        index[path] = {m.lower() for m in path_item.keys() if m != "parameters"}
    return index


@pytest.mark.parametrize("method,path", _LOCKED_PATHS)
def test_locked_path_present(openapi_index, method, path):
    """Every legacy iter9 path is still served and on the same verb."""
    assert path in openapi_index, (
        f"locked path missing from openapi: {method} {path}. "
        f"A router include may have been dropped."
    )
    methods = openapi_index[path]
    assert method.lower() in methods, (
        f"{path} is mounted but with wrong methods. "
        f"Expected {method!r}, got {sorted(methods)!r}."
    )


def test_openapi_schema_is_well_formed():
    """Sanity check: the schema parses and has the standard root keys.

    Catches the case where a router throws at OpenAPI emit time
    (mis-configured response_model, etc.) — that would surface as a
    truncated `paths` block here.
    """
    schema = app.openapi()
    assert "paths" in schema
    assert "info" in schema
    assert "openapi" in schema
    # Plausibility floor: a healthy AKKI build serves >100 routes.
    assert len(schema["paths"]) > 100, (
        f"OpenAPI emitted only {len(schema['paths'])} paths — "
        f"likely a missing router include."
    )
